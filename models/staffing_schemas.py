from __future__ import annotations

from typing import Optional, List
from pydantic import Field

from harness.schemas import HarnessSchema


class StaffingInput(HarnessSchema):
    """Input for the Staffing Agent — facility state + current staffing data."""
    state: str = Field(description="Two-letter US state code, e.g. CA, TX")
    facility_type: str = Field(default="residential", description="Type of facility: residential, assisted, skilled_nursing")
    
    # Nurse information
    nurse_name: str = Field(description="Full name of nurse on shift")
    nurse_last_training_date: str = Field(description="ISO date of nurse's last training (e.g. 2025-06-01)")
    nurse_hours_worked_today: float = Field(description="Hours the nurse has worked today")
    nurse_on_break: bool = Field(default=False, description="Is the nurse currently on break?")
    
    # Doctor information
    doctor_on_shift: bool = Field(description="Is a doctor physically on site?")
    doctor_on_call: bool = Field(description="Is a doctor on call (available by phone/telehealth)?")
    doctor_name: Optional[str] = Field(None, description="Name of doctor on duty (if applicable)")
    
    # State-specific rules (optional — can be pulled from config)
    state_min_staff_ratio: Optional[str] = Field(None, description="State minimum staff-to-resident ratio")
    state_doctor_required: bool = Field(default=True, description="Does state require a doctor on site?")
    state_max_nurse_hours: float = Field(default=12.0, description="Maximum hours a nurse can work in a day")


class StaffingOutput(HarnessSchema):
    """Output from the Staffing Agent — compliance flags and notes."""
    doctor_on_shift_compliant: bool
    nurse_training_compliant: bool
    nurse_hours_compliant: bool
    overall_compliant: bool
    flags: List[str] = Field(default_factory=list)
    staffing_note: str = ""
    recommended_action: str = ""
