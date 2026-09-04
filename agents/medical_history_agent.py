from models.intake_schemas import MedicalHistoryInput, MedicalHistoryOutput
from .base_agent import BaseAgent


class MedicalHistoryAgent(BaseAgent):
    name = "medical_history_agent"
    input_schema = MedicalHistoryInput
    output_schema = MedicalHistoryOutput
    system_prompt = (
        "You are a medical history summarization assistant for a residential elder-care facility. "
        "Read the provided clinical notes and produce a concise, plain-clinical-language summary "
        "for the resident's care team. Identify any risk flags (e.g. fall risk, medication "
        "interactions, cognitive decline indicators). Respond ONLY with a JSON object matching "
        "this schema: {\"summary\": str, \"risk_flags\": [str], \"medications_mentioned\": int, "
        "\"confidence\": float}. No prose outside the JSON."
    )

    def build_prompt(self, validated_input: MedicalHistoryInput) -> str:
        return f"Clinical notes:\n{validated_input.clinical_notes}\n\nSummarize per the schema."
