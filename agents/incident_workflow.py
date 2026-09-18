"""Dynamic incident-reporting workflow."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Callable, Optional

import config
from harness.llm_clients import LLMClient
from models.incident_schemas import IncidentAuditTrail
from agents.incident_agents import IncidentClassificationAgent, IncidentValidationAgent
from agents.staffing_agent import StaffingAgent


# Type alias for the field resolver function
FieldResolver = Callable[[list[str], dict, int], dict]


def default_field_resolver(missing_fields: list[str], current_fields: dict, iteration: int) -> dict:
    """Demo/default resolver: simulates a follow-up prompt to staff."""
    filled = {}
    demo_values = {
        "date_time": "2026-08-07T14:30:00",
        "resident_name": current_fields.get("resident_name") or "Resident on file",
        "description": "Additional detail provided by staff during follow-up.",
        "witnesses": "None reported",
        "immediate_action_taken": "Resident assessed by on-site nurse; vitals stable.",
        "incident_type": current_fields.get("incident_type"),
    }
    for field in missing_fields:
        if demo_values.get(field):
            filled[field] = demo_values[field]
    return filled


class IncidentWorkflow:
    def __init__(self, client: Optional[LLMClient] = None):
        self.classifier = IncidentClassificationAgent(client=client)
        self.validator = IncidentValidationAgent(client=client)
        self.staffing_agent = StaffingAgent(client=client)
        self.incident_log_file = Path("logs/incidents.json")

    def _persist_incident(self, audit: IncidentAuditTrail) -> None:
        """Write incident audit trail to JSON file."""
        try:
            self.incident_log_file.parent.mkdir(exist_ok=True)
            if self.incident_log_file.exists():
                with open(self.incident_log_file, "r") as f:
                    try:
                        incidents = json.load(f)
                    except json.JSONDecodeError:
                        incidents = []
            else:
                incidents = []
            incidents.append(audit.model_dump())
            with open(self.incident_log_file, "w") as f:
                json.dump(incidents, f, indent=2, default=str)
        except Exception as e:
            import logging
            logging.getLogger("guardian").error(f"Failed to persist incident: {e}")

    def run(
        self,
        draft: dict,
        field_resolver: FieldResolver = default_field_resolver,
        max_loops: int = getattr(config, 'MAX_INCIDENT_LOOPS', 5),
    ) -> IncidentAuditTrail:
        incident_id = str(uuid.uuid4())
        state = draft.get("state", "").upper()
        audit = IncidentAuditTrail(incident_id=incident_id, state=state)

        escalation_reasons = []
        staffing_escalated = False

        # --- Step 1: classify ---
        classification_result = self.classifier.run({"narrative": draft.get("narrative", "")})
        audit.steps.append({"step": "classification", **classification_result.to_dict()})

        if not classification_result.success or classification_result.output is None:
            audit.status = "escalated"
            audit.escalated_to_human = True
            escalation_reasons.append("classification_failed")
            audit.steps.append({"step": "escalation", "reason": "classification_failed"})
            self._persist_incident(audit)
            return audit

        audit.classification = classification_result.output
        category = classification_result.output.category

        # --- Step 2: route to regulatory notification path ---
        state_rules = config.REGULATORY_RULES.get(state, {})
        notification_map = state_rules.get("incident_notification", {})
        audit.notification_path = notification_map.get(category, notification_map.get("other", {
            "agency": "State licensing authority (default routing -- state not configured)",
            "hours": 72,
        }))

        # --- Step 3: Staffing compliance check ---
        nurse_name = draft.get("nurse_name", "Unknown")
        nurse_last_training = draft.get("nurse_last_training", "2024-01-01")
        nurse_hours_today = draft.get("nurse_hours_today", 8.0)
        doctor_on_shift = draft.get("doctor_on_shift", True)
        doctor_on_call = draft.get("doctor_on_call", True)

        audit.nurse_on_duty = nurse_name
        audit.doctor_on_duty = "Dr. On Call" if doctor_on_call else "None"

        staffing_result = self.staffing_agent.run({
            "state": state,
            "nurse_name": nurse_name,
            "nurse_last_training_date": nurse_last_training,
            "nurse_hours_worked_today": nurse_hours_today,
            "doctor_on_shift": doctor_on_shift,
            "doctor_on_call": doctor_on_call
        })

        if staffing_result.success and staffing_result.output is not None:
            audit.staffing_check = staffing_result.output
            audit.staffing_flags = staffing_result.output.flags
            audit.steps.append({
                "step": "staffing_check",
                **staffing_result.to_dict()
            })
            if not staffing_result.output.overall_compliant:
                staffing_escalated = True
                escalation_reasons.append(f"Staffing non-compliant: {', '.join(staffing_result.output.flags)}")
                audit.steps.append({
                    "step": "escalation",
                    "reason": f"Staffing non-compliant: {', '.join(staffing_result.output.flags)}"
                })
        else:
            audit.steps.append({
                "step": "staffing_check",
                "success": False,
                "error": staffing_result.error
            })
            audit.staffing_flags.append("staffing_check_failed")
            staffing_escalated = True
            escalation_reasons.append("staffing_check_failed")

        # --- Step 4 & 5: bounded validation loop ---
        current_fields = {k: v for k, v in draft.items() if k not in ("narrative",)}
        current_fields["incident_type"] = current_fields.get("incident_type") or category

        converged = False
        iteration = 0
        while iteration < max_loops:
            iteration += 1
            validation_result = self.validator.run({"current_fields_json": json.dumps(current_fields)})
            audit.steps.append({
                "step": f"validation_iteration_{iteration}",
                **validation_result.to_dict(),
                "fields_snapshot": {k: v for k, v in current_fields.items()}
            })

            if not validation_result.success or validation_result.output is None:
                continue

            if validation_result.output.is_complete:
                converged = True
                break

            missing = validation_result.output.missing_fields
            newly_filled = field_resolver(missing, current_fields, iteration)
            current_fields.update(newly_filled)

        audit.loop_iterations = iteration
        audit.converged = converged
        audit.final_fields = current_fields

        # --- Step 6: Determine final status (preserve staffing escalation) ---
        validation_escalated = not converged
        if validation_escalated:
            escalation_reasons.append(f"validation did not converge within MAX_INCIDENT_LOOPS={max_loops}")

        # FIX: Staffing escalation is preserved and NOT overwritten by convergence
        if staffing_escalated or validation_escalated:
            audit.status = "escalated"
            audit.escalated_to_human = True
            audit.steps.append({
                "step": "escalation",
                "reason": "; ".join(escalation_reasons)
            })
        else:
            audit.status = "complete"
            audit.escalated_to_human = False

        # --- Step 7: Persist to disk ---
        self._persist_incident(audit)

        return audit
