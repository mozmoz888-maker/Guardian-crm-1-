import json

import config
from models.intake_schemas import ComplianceInput, ComplianceOutput
from .base_agent import BaseAgent


class RegulatoryComplianceAgent(BaseAgent):
    name = "regulatory_compliance_agent"
    input_schema = ComplianceInput
    output_schema = ComplianceOutput
    system_prompt = (
        "You are a regulatory compliance assistant for residential care facilities. "
        "Given a state's required forms/staffing rules and the forms actually submitted for a "
        "resident, determine compliance. Respond ONLY with a JSON object matching this schema: "
        "{\"compliant\": bool, \"missing_forms\": [str], \"staff_ratio_note\": str}."
    )

    def build_prompt(self, validated_input: ComplianceInput) -> str:
        rules = config.REGULATORY_RULES.get(validated_input.state.upper(), {})
        return (
            f"State: {validated_input.state}\n"
            f"State required forms: {rules.get('required_forms', [])}\n"
            f"State min staff ratio: {rules.get('min_staff_ratio')}\n"
            f"Forms submitted for this resident: {validated_input.submitted_forms}\n"
            f"Facility-reported staff ratio: {validated_input.staff_ratio}\n\n"
            "Determine compliance per the schema."
        )
