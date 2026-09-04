from .base_agent import BaseAgent
from models.incident_schemas import (
    ClassificationInput,
    ClassificationOutput,
    ValidationInput,
    ValidationOutput,
)


class IncidentClassificationAgent(BaseAgent):
    name = "incident_classification_agent"
    input_schema = ClassificationInput
    output_schema = ClassificationOutput
    system_prompt = (
        "You are an incident-classification assistant for a residential elder-care facility. "
        "Read the staff member's free-text narrative and classify it into exactly one category: "
        "fall, medication_error, elopement, abuse_allegation, death, or other. "
        "Respond ONLY with JSON matching: {\"category\": str, \"confidence\": float}."
    )

    def build_prompt(self, validated_input: ClassificationInput) -> str:
        return f"Incident narrative:\n{validated_input.narrative}\n\nClassify per the schema."


class IncidentValidationAgent(BaseAgent):
    name = "incident_validation_agent"
    input_schema = ValidationInput
    output_schema = ValidationOutput
    system_prompt = (
        "You are an incident-report field validation assistant. You are given the fields collected so far "
        "for an incident report as a JSON object. The required fields are: incident_type, date_time, "
        "resident_name, description, witnesses, immediate_action_taken. Identify which required "
        "fields are still missing or empty. Respond ONLY with JSON matching: "
        "{\"missing_fields\": [str], \"is_complete\": bool}."
    )

    def build_prompt(self, validated_input: ValidationInput) -> str:
        return f"Fields collected so far:\n{validated_input.current_fields_json}\n\nValidate per the schema."
