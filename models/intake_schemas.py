"""Input/output schemas for the resident-intake agent swarm."""
from __future__ import annotations

from typing import Optional

from pydantic import Field, ConfigDict

from harness.schemas import HarnessSchema


# ---- Orchestrator-level intake form (what comes in from the CRM) ----
class IntakeForm(HarnessSchema):
    model_config = ConfigDict(extra="ignore")  # <-- CHANGE THIS BACK TO "ignore"
    
    resident_name: str
    dob: str
    state: str = Field(description="Two-letter US state code, e.g. CA, TX")
    clinical_notes: str
    submitted_forms: list[str] = Field(default_factory=list)
    staff_ratio: Optional[str] = None
    family_name: Optional[str] = None
    family_phone: Optional[str] = None
    family_email: Optional[str] = None


# ---- Medical history sub-agent ----
class MedicalHistoryInput(HarnessSchema):
    clinical_notes: str


class MedicalHistoryOutput(HarnessSchema):
    summary: str
    risk_flags: list[str] = Field(default_factory=list)
    medications_mentioned: int = 0
    confidence: float = 0.0


# ---- Regulatory compliance sub-agent ----
class ComplianceInput(HarnessSchema):
    state: str
    submitted_forms: list[str]
    staff_ratio: Optional[str] = None


class ComplianceOutput(HarnessSchema):
    compliant: bool
    missing_forms: list[str] = Field(default_factory=list)
    staff_ratio_note: str = ""


# ---- Family communication sub-agent ----
class FamilyWelcomeInput(HarnessSchema):
    resident_name: str
    medical_summary: str


class FamilyWelcomeOutput(HarnessSchema):
    welcome_message: str
    tone: str = "warm_plain_language"


# ---- Orchestrator's final combined result ----
class IntakeWorkflowResult(HarnessSchema):
    resident_name: str
    medical: Optional[MedicalHistoryOutput] = None
    compliance: Optional[ComplianceOutput] = None
    family_welcome: Optional[FamilyWelcomeOutput] = None
    incomplete_steps: list[str] = Field(default_factory=list)
    overall_status: str = "pending"  # complete | partial | failed
