from models.staffing_schemas import StaffingInput, StaffingOutput
from .base_agent import BaseAgent


class StaffingAgent(BaseAgent):
    """
    Staffing Agent — validates staffing compliance for residential care facilities.
    
    Input: state, nurse training/hours, doctor availability
    Output: compliance flags, warnings, and a staffing note
    """
    
    name = "staffing_agent"
    input_schema = StaffingInput
    output_schema = StaffingOutput
    
    system_prompt = (
        "You are a staffing compliance assistant for residential care facilities. "
        "Given a facility's current shift roster, nurse training records, and doctor availability, "
        "determine if the facility is compliant with state regulations.\n\n"
        "Rules you must enforce:\n"
        "1. A doctor must be on site or on call at all times.\n"
        "2. Nurses must have completed training within the last 2 years (training date must be ≥ 2 years ago).\n"
        "3. No nurse can work more than 12 hours in a single day.\n"
        "4. The facility must meet the state's minimum staff-to-resident ratio if provided.\n\n"
        "If any rule is violated, set the corresponding 'compliant' flag to False and add a clear explanation to 'flags'.\n"
        "Provide a helpful 'staffing_note' summarizing the situation and a 'recommended_action' for the facility.\n\n"
        "Respond ONLY with a JSON object matching this schema: "
        "{\"doctor_on_shift_compliant\": bool, \"nurse_training_compliant\": bool, "
        "\"nurse_hours_compliant\": bool, \"overall_compliant\": bool, "
        "\"flags\": [str], \"staffing_note\": str, \"recommended_action\": str}. "
        "No prose outside the JSON."
    )
    
    def build_prompt(self, validated_input: StaffingInput) -> str:
        # Build a clear, readable prompt for the LLM
        prompt = f"Facility state: {validated_input.state}\n"
        prompt += f"Facility type: {validated_input.facility_type}\n\n"
        
        prompt += f"--- Nurse Information ---\n"
        prompt += f"Nurse on shift: {validated_input.nurse_name}\n"
        prompt += f"Last training date: {validated_input.nurse_last_training_date}\n"
        prompt += f"Hours worked today: {validated_input.nurse_hours_worked_today}\n"
        prompt += f"On break? {'Yes' if validated_input.nurse_on_break else 'No'}\n\n"
        
        prompt += f"--- Doctor Information ---\n"
        prompt += f"Doctor on site: {'Yes' if validated_input.doctor_on_shift else 'No'}\n"
        prompt += f"Doctor on call: {'Yes' if validated_input.doctor_on_call else 'No'}\n"
        if validated_input.doctor_name:
            prompt += f"Doctor name: {validated_input.doctor_name}\n"
        
        prompt += f"\n--- State-Specific Rules ---\n"
        prompt += f"State minimum staff ratio: {validated_input.state_min_staff_ratio or 'Not specified'}\n"
        prompt += f"Doctor required? {'Yes' if validated_input.state_doctor_required else 'No'}\n"
        prompt += f"Max nurse hours per day: {validated_input.state_max_nurse_hours}\n\n"
        
        prompt += "Based on the above information, determine staffing compliance per the schema."
        
        return prompt
