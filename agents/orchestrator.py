"""Orchestrator agent for the resident-intake swarm.

Triggered by a new intake-form submission. Fans out to three
sub-agents (medical history, regulatory compliance, family
welcome), each running through the shared LLMHarness. If any
sub-agent fails (schema validation, retries exhausted, timeout with no
fallback), the orchestrator does NOT abort the whole workflow -- it
records which step failed in `incomplete_steps` and continues with the
rest, matching the spec: "If any sub-agent fails, the orchestrator
continues and flags what is incomplete."
"""
from __future__ import annotations

from typing import Optional

from harness.llm_clients import LLMClient
from models.intake_schemas import (
    IntakeForm,
    IntakeWorkflowResult,
)
from agents.medical_history_agent import MedicalHistoryAgent
from agents.regulatory_compliance_agent import RegulatoryComplianceAgent
from agents.family_welcome_agent import FamilyWelcomeAgent


class IntakeOrchestrator:
    """
    Orchestrator for the resident intake swarm.
    
    Triggers three sub-agents in parallel:
    1. Medical History Agent - Summarizes clinical notes, identifies risks
    2. Regulatory Compliance Agent - Checks state regulations, missing forms
    3. Family Welcome Agent - Drafts welcome message for family
    
    If any agent fails, the orchestrator continues and records the failure.
    """
    
    def __init__(self, client: Optional[LLMClient] = None):
        self.medical_agent = MedicalHistoryAgent(client=client)
        self.compliance_agent = RegulatoryComplianceAgent(client=client)
        self.family_agent = FamilyWelcomeAgent(client=client)

    def run(self, raw_intake: dict) -> IntakeWorkflowResult:
        """
        Process a resident intake form through the agent swarm.
        
        Args:
            raw_intake: Dictionary containing intake form data
                Required fields: resident_name, dob, state, clinical_notes
                Optional fields: submitted_forms, staff_ratio, family_name, etc.
        
        Returns:
            IntakeWorkflowResult with:
                - medical: MedicalHistoryOutput (summary, risk_flags, etc.)
                - compliance: ComplianceOutput (compliant, missing_forms, etc.)
                - family_welcome: FamilyWelcomeOutput (welcome_message, tone)
                - incomplete_steps: List of any failed steps
                - overall_status: "complete" | "partial" | "failed"
        """
        # --- STEP 1: Validate critical data ---
        missing_critical = []
        resident_name = raw_intake.get("resident_name", "unknown")
        
        if not raw_intake.get("clinical_notes") or raw_intake.get("clinical_notes", "").strip() == "":
            missing_critical.append("Missing clinical notes")
        if not raw_intake.get("state") or raw_intake.get("state", "").strip() == "":
            missing_critical.append("Missing state")
        if not raw_intake.get("dob") or raw_intake.get("dob", "").strip() == "":
            missing_critical.append("Missing DOB")
        if not raw_intake.get("resident_name") or raw_intake.get("resident_name", "").strip() == "":
            missing_critical.append("Missing resident name")
        
        if missing_critical:
            return IntakeWorkflowResult(
                resident_name=resident_name,
                incomplete_steps=missing_critical,
                overall_status="failed",
            )
        
        # --- STEP 2: Parse and validate intake form ---
        try:
            intake = IntakeForm(**raw_intake)
        except Exception as exc:
            return IntakeWorkflowResult(
                resident_name=resident_name,
                incomplete_steps=[f"intake_form_validation: {exc}"],
                overall_status="failed",
            )

        # --- STEP 3: Initialize result ---
        result = IntakeWorkflowResult(resident_name=intake.resident_name)
        incomplete: list[str] = []

        # --- STEP 4: Run Medical History Sub-Agent ---
        medical_result = self.medical_agent.run({"clinical_notes": intake.clinical_notes})
        if medical_result.success and medical_result.output is not None:
            result.medical = medical_result.output
        else:
            incomplete.append(f"medical_history: {medical_result.error or 'Unknown error'}")

        # --- STEP 5: Run Regulatory Compliance Sub-Agent ---
        compliance_result = self.compliance_agent.run({
            "state": intake.state,
            "submitted_forms": intake.submitted_forms,
            "staff_ratio": intake.staff_ratio,
        })
        if compliance_result.success and compliance_result.output is not None:
            result.compliance = compliance_result.output
            if not compliance_result.output.compliant:
                incomplete.append("regulatory_compliance_failed")
        else:
            incomplete.append(f"regulatory_compliance: {compliance_result.error or 'Unknown error'}")

        # --- STEP 6: Run Family Welcome Sub-Agent ---
        medical_summary_text = (
            result.medical.summary if result.medical is not None
            else "General intake completed; detailed clinical summary pending."
        )
        family_result = self.family_agent.run({
            "resident_name": intake.resident_name,
            "medical_summary": medical_summary_text,
        })
        if family_result.success and family_result.output is not None:
            result.family_welcome = family_result.output
        else:
            incomplete.append(f"family_welcome: {family_result.error or 'Unknown error'}")

        # --- STEP 7: Determine overall status ---
        result.incomplete_steps = incomplete
        
        # Check if compliance failed (even if agent succeeded)
        compliance_failed = result.compliance is not None and not result.compliance.compliant
        
        if not incomplete and not compliance_failed:
            result.overall_status = "complete"
        elif not incomplete and compliance_failed:
            # Compliance failed, but all agents ran successfully
            result.overall_status = "partial"
            if "regulatory_compliance_failed" not in incomplete:
                incomplete.append("regulatory_compliance_failed")
        elif len(incomplete) < 3:
            # Some agents failed, but not all
            result.overall_status = "partial"
        else:
            # All agents failed
            result.overall_status = "failed"

        return result