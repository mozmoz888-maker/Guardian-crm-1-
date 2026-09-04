"""Input/output schemas for the dynamic incident-reporting workflow."""
from __future__ import annotations

from typing import Optional

from pydantic import Field

from harness.schemas import HarnessSchema
from models.staffing_schemas import StaffingOutput


class ClassificationInput(HarnessSchema):
    narrative: str


class ClassificationOutput(HarnessSchema):
    category: str
    confidence: float = 0.0


class ValidationInput(HarnessSchema):
    current_fields_json: str


class ValidationOutput(HarnessSchema):
    missing_fields: list[str] = Field(default_factory=list)
    is_complete: bool = False


class IncidentAuditTrail(HarnessSchema):
    incident_id: str
    state: str
    reported_by: str = Field(default="", description="Staff member who reported the incident")
    reported_at: str = Field(default="", description="When the report was filed")
    nurse_on_duty: str = Field(default="", description="Nurse on shift during incident")
    doctor_on_duty: str = Field(default="", description="Doctor on duty during incident")
    classification: Optional[ClassificationOutput] = None
    notification_path: Optional[dict] = None
    staffing_check: Optional[StaffingOutput] = None
    staffing_flags: list[str] = Field(default_factory=list)
    loop_iterations: int = 0
    converged: bool = False
    escalated_to_human: bool = False
    final_fields: dict = Field(default_factory=dict)
    steps: list[dict] = Field(default_factory=list)
    status: str = "pending"
