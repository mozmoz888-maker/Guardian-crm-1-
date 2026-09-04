"""Family Welcome Agent — drafts a plain-language welcome message for families."""

from models.intake_schemas import FamilyWelcomeInput, FamilyWelcomeOutput
from agents.base_agent import BaseAgent  # <-- FIXED: absolute import


class FamilyWelcomeAgent(BaseAgent):
    """
    Family Welcome Agent.
    
    Input: resident_name, medical_summary
    Output: welcome_message (plain language), tone
    """
    
    name = "family_welcome_agent"
    input_schema = FamilyWelcomeInput
    output_schema = FamilyWelcomeOutput
    
    system_prompt = (
        "You are a warm, plain-language family-communication assistant for a residential elder-care "
        "facility. Given a resident's name and a clinical medical summary, write a short welcome "
        "message for the family that avoids medical jargon, is reassuring but honest, and highlights "
        "that the care team has a plan in place. \n\n"
        "The tone should be warm, compassionate, and easy to understand. "
        "Do NOT use clinical terms like 'hypertension' — use 'high blood pressure' instead. "
        "Do NOT use 'osteoarthritis' — use 'joint pain' instead.\n\n"
        "Respond ONLY with a JSON object matching this schema: "
        "{\"welcome_message\": str, \"tone\": str}."
    )
    
    def build_prompt(self, validated_input: FamilyWelcomeInput) -> str:
        return (
            f"Resident name: {validated_input.resident_name}\n\n"
            f"Clinical summary (translate to plain language, do not quote jargon):\n"
            f"{validated_input.medical_summary}\n\n"
            "Write the family welcome message per the schema. "
            "Make it warm, reassuring, and highlight that the care team has a plan."
        )