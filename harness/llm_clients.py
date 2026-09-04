
import json
import random
import time
from abc import ABC, abstractmethod
from typing import Any

from .exceptions import RetryableError


class LLMClient(ABC):
    @abstractmethod
    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str:
        raise NotImplementedError


class AnthropicLLMClient(LLMClient):
    def __init__(self, model: str, api_key: str | None = None):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model


    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str:
        import anthropic
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.RateLimitError as exc:
            raise RetryableError(str(exc), status_code=429) from exc
        except anthropic.InternalServerError as exc:
            raise RetryableError(str(exc), status_code=500) from exc
        except anthropic.APIStatusError as exc:
            status = getattr(exc, "status_code", None)
            if status and 500 <= status < 600:
                raise RetryableError(str(exc), status_code=status) from exc
            raise
        parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        return "\n".join(parts)


class MockLLMClient(LLMClient):
    def __init__(self, force_error_sequence: list[str] | None = None, force_latency: float = 0.0):
        self._error_sequence = list(force_error_sequence or [])
        self._call_count = 0
        self._force_latency = force_latency
        self._success_probability = 1.0

    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str:
        self._call_count += 1
        if self._error_sequence:
            behavior = self._error_sequence.pop(0)
            if behavior == "rate_limit":
                raise RetryableError("mock 429 rate limit", status_code=429)
            if behavior == "server_error":
                raise RetryableError("mock 500 internal server error", status_code=500)
            if behavior == "timeout":
                time.sleep(self._force_latency or 0)
                raise TimeoutError("mock timeout")
        if self._force_latency:
            time.sleep(self._force_latency)
        return self._route(system, prompt)

    def _route(self, system: str, prompt: str) -> str:
        s = (system or "").lower()
        
        if "regulatory" in s or "regulatory_compliance" in s:
            return self._compliance_check(prompt)
        elif "staffing" in s or "staffing_agent" in s:
            return self._staffing_check(prompt)
        elif "family" in s or "family_welcome" in s:
            return self._family_welcome(prompt)
        elif "medical" in s or "medical_history" in s:
            return self._medical_summary(prompt)
        elif "incident_validation" in s:
            return self._field_validation(prompt)
        elif "incident_classification" in s or "classify" in s:
            return self._incident_classification(prompt)
        elif "validation" in s:
            return self._field_validation(prompt)
        return json.dumps({"summary": "Mock response: no specialized route matched."})

    def _compliance_check(self, prompt: str) -> str:
        missing = []
        staff_ratio_note = "Facility-reported ratio meets or exceeds the state minimum."
        
        import re
        forms_match = re.search(r"Forms submitted for this resident: (\[.*?\])", prompt)
        submitted_forms = []
        if forms_match:
            try:
                forms_str = forms_match.group(1)
                forms_str = forms_str.replace("'", '"')
                submitted_forms = json.loads(forms_str)
            except:
                submitted_forms = []
        
        if not submitted_forms:
            if "admission_agreement" in prompt:
                submitted_forms.append("admission_agreement")
            if "care_plan" in prompt:
                submitted_forms.append("care_plan")
            if "medication_authorization" in prompt:
                submitted_forms.append("medication_authorization")
        
        state = "Unknown"
        state_match = re.search(r"State: (\w+)", prompt)
        if state_match:
            state = state_match.group(1).upper()
        
        import config
        rules = config.REGULATORY_RULES.get(state, {})
        required_forms = rules.get('required_forms', [])
        min_ratio = rules.get('min_staff_ratio')
        
        for form in required_forms:
            if form not in submitted_forms:
                missing.append(form)
        
        ratio_match = re.search(r"Facility-reported staff ratio: ([\d:]+)", prompt)
        if ratio_match and min_ratio:
            ratio = ratio_match.group(1)
            def ratio_value(r):
                parts = r.split(':')
                if len(parts) == 2:
                    try:
                        return int(parts[0]) / int(parts[1])
                    except:
                        return 0
                return 0
            
            reported_value = ratio_value(ratio)
            required_value = ratio_value(min_ratio)
            
            if reported_value < required_value:
                staff_ratio_note = f"WARNING: Facility-reported ratio ({ratio}) is below the {state} minimum of {min_ratio}."
                if "staff_ratio" not in missing:
                    missing.append("staff_ratio")
            elif reported_value >= required_value:
                staff_ratio_note = f"Facility-reported ratio ({ratio}) meets or exceeds the {state} minimum of {min_ratio}."
        elif ratio_match and not min_ratio:
            staff_ratio_note = f"{state} has no state minimum staff ratio in the demo."
        
        compliant = len(missing) == 0
        
        return json.dumps({
            "compliant": compliant,
            "missing_forms": missing,
            "staff_ratio_note": staff_ratio_note
        })

    def _family_welcome(self, prompt: str) -> str:
        return json.dumps({
            "welcome_message": (
                "We're so glad to welcome your loved one to our community. "
                "Our care team has reviewed their health history and put together "
                "a personalized care plan focused on comfort, safety, and staying active. "
                "We'll keep you updated every step of the way, and please don't hesitate "
                "to reach out with any questions."
            ),
            "tone": "warm_plain_language",
        })

    def _medical_summary(self, prompt: str) -> str:
        conditions = []
        if "hypertension" in prompt:
            conditions.append("hypertension")
        if "osteoarthritis" in prompt:
            conditions.append("osteoarthritis")
        if "dementia" in prompt:
            conditions.append("dementia")
        if "diabetes" in prompt:
            conditions.append("type 2 diabetes")
        if "COPD" in prompt:
            conditions.append("COPD")
        if "heart failure" in prompt:
            conditions.append("heart failure")
        if "depression" in prompt:
            conditions.append("depression")
        
        risk_flags = ["fall_risk_mild"] if "fall risk" in prompt.lower() else []
        if "dementia" in prompt.lower():
            risk_flags.append("cognitive_decline_risk")
        
        return json.dumps({
            "summary": f"Resident presents with {', '.join(conditions) if conditions else 'various age-related conditions'}. "
                      f"No known drug allergies reported. "
                      f"Ambulatory with assistance as needed.",
            "risk_flags": risk_flags if risk_flags else ["needs_review"],
            "medications_mentioned": 3,
            "confidence": 0.86,
        })

    def _staffing_check(self, prompt: str) -> str:
        flags = []
        staffing_note = "All staffing requirements met."
        recommended_action = "No action required."
        
        training_compliant = True
        if "2023" in prompt or "2022" in prompt or "2021" in prompt:
            training_compliant = False
            flags.append("nurse_training_expired")
            staffing_note = "Nurse's training is expired. Immediate action required."
            recommended_action = "Schedule refresher training for nurse within 7 days."
        else:
            staffing_note = "Nurse training is current and compliant."
        
        hours_compliant = True
        if "13" in prompt or "14" in prompt or "15" in prompt or "16" in prompt:
            hours_compliant = False
            if "nurse_exceeds_max_hours" not in flags:
                flags.append("nurse_exceeds_max_hours")
            staffing_note = "Nurse has exceeded maximum allowed hours (12 hours)."
            recommended_action = "Immediately relieve nurse from duty and arrange coverage."
        
        doctor_compliant = True
        if "Doctor on site: No" in prompt and "Doctor on call: No" in prompt:
            doctor_compliant = False
            flags.append("no_doctor_available")
            staffing_note = "No doctor available on site or on call."
            recommended_action = "Contact on-call physician immediately."
        
        overall_compliant = training_compliant and hours_compliant and doctor_compliant
        
        if not overall_compliant and staffing_note == "All staffing requirements met.":
            staffing_note = f"Compliance issues detected: {', '.join(flags)}"
        
        return json.dumps({
            "doctor_on_shift_compliant": doctor_compliant,
            "nurse_training_compliant": training_compliant,
            "nurse_hours_compliant": hours_compliant,
            "overall_compliant": overall_compliant,
            "flags": flags,
            "staffing_note": staffing_note,
            "recommended_action": recommended_action
        })

    def _incident_classification(self, prompt: str) -> str:
        p = prompt.lower()
        if "fell" in p or "fall" in p:
            category = "fall"
            confidence = 0.92
        elif "medication" in p or "wrong dose" in p or "missed dose" in p:
            category = "medication_error"
            confidence = 0.88
        elif "wandered" in p or "left the facility" in p or "elopement" in p:
            category = "elopement"
            confidence = 0.85
        elif "hit" in p or "bruise" in p or "allegation" in p or "abuse" in p:
            category = "abuse_allegation"
            confidence = 0.80
        elif "died" in p or "deceased" in p or "death" in p:
            category = "death"
            confidence = 0.95
        else:
            category = "other"
            confidence = 0.70
        return json.dumps({"category": category, "confidence": confidence})

    def _field_validation(self, prompt: str) -> str:
        try:
            start = prompt.index("{")
            data, _ = json.JSONDecoder().raw_decode(prompt[start:])
        except (ValueError, json.JSONDecodeError):
            data = {}
        required = ["incident_type", "date_time", "resident_name", "description", "witnesses", "immediate_action_taken"]
        missing = [f for f in required if not data.get(f)]
        return json.dumps({"missing_fields": missing, "is_complete": len(missing) == 0})
