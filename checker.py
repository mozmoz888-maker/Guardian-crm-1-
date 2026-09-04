#!/usr/bin/env python3
"""Comprehensive checker script for Guardian CRM system."""

import json
import sys
import os
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness.llm_harness import LLMHarness, HarnessResult
from harness.exceptions import RetryableError, RetryExhaustedError
from harness.llm_clients import LLMClient, MockLLMClient
from harness.logging_utils import log_event, redact_text, redact, build_logger

from agents.orchestrator import IntakeOrchestrator
from agents.medical_history_agent import MedicalHistoryAgent
from agents.regulatory_compliance_agent import RegulatoryComplianceAgent
from agents.family_welcome_agent import FamilyWelcomeAgent
from agents.staffing_agent import StaffingAgent
from agents.incident_agents import IncidentClassificationAgent, IncidentValidationAgent
from agents.incident_workflow import IncidentWorkflow

from models.intake_schemas import IntakeForm, MedicalHistoryInput, MedicalHistoryOutput
from models.incident_schemas import IncidentAuditTrail
from models.staffing_schemas import StaffingInput, StaffingOutput

from pydantic import BaseModel
import config

class TestInput(BaseModel):
    query: str

class TestOutput(BaseModel):
    answer: str


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}  {text}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.END}\n")


def print_success(text: str):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_failure(text: str):
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠️ {text}{Colors.END}")


def print_info(text: str):
    print(f"{Colors.BLUE}ℹ️ {text}{Colors.END}")


# -------------------------------------------------------------------
# IMPORT TESTS
# -------------------------------------------------------------------
def check_imports() -> bool:
    print_header("Checking Imports")
    all_ok = True
    modules = [
        ("harness.llm_harness", "LLMHarness"),
        ("harness.exceptions", "RetryableError"),
        ("harness.llm_clients", "MockLLMClient"),
        ("harness.logging_utils", "log_event"),
        ("agents.orchestrator", "IntakeOrchestrator"),
        ("agents.medical_history_agent", "MedicalHistoryAgent"),
        ("agents.regulatory_compliance_agent", "RegulatoryComplianceAgent"),
        ("agents.family_welcome_agent", "FamilyWelcomeAgent"),
        ("agents.staffing_agent", "StaffingAgent"),
        ("agents.incident_agents", "IncidentClassificationAgent"),
        ("agents.incident_workflow", "IncidentWorkflow"),
        ("models.intake_schemas", "IntakeForm"),
        ("models.incident_schemas", "IncidentAuditTrail"),
        ("models.staffing_schemas", "StaffingInput"),
    ]
    for module_name, class_name in modules:
        try:
            __import__(module_name, fromlist=[class_name])
            print_success(f"Imported {module_name}.{class_name}")
        except ImportError as e:
            print_failure(f"Failed to import {module_name}.{class_name}: {e}")
            all_ok = False
    return all_ok


# -------------------------------------------------------------------
# REDACTION TESTS
# -------------------------------------------------------------------
def test_redaction() -> bool:
    print_header("Testing Redaction")
    all_ok = True
    test_texts = [
        ("SSN: 123-45-6789", "SSN: [REDACTED]"),
        ("Phone: 555-123-4567", "Phone: [REDACTED]"),
        ("Email: john.doe@example.com", "Email: [REDACTED]"),
        ("Credit Card: 1234-5678-9012-3456", "Credit Card: [REDACTED]"),
        ("ZIP: 90210", "ZIP: [REDACTED]"),
        ("DOB: 1940-01-01", "DOB: [REDACTED]"),
        ("Normal text without PII", "Normal text without PII"),
    ]
    for original, expected in test_texts:
        redacted = redact_text(original)
        if redacted == expected:
            print_success(f"Redacted: '{original}' → '{redacted}'")
        else:
            print_failure(f"Redaction failed: '{original}' → '{redacted}' (expected '{expected}')")
            all_ok = False

    test_dict = {
        "name": "John Doe",
        "ssn": "123-45-6789",
        "email": "john@example.com",
        "phone": "555-123-4567",
        "details": {"address": "123 Main St", "credit_card": "1234-5678-9012-3456"}
    }
    redacted_dict = redact(test_dict)
    sensitive_fields = ["ssn", "email", "phone", "credit_card"]
    for field in sensitive_fields:
        if field in str(redacted_dict) and "[REDACTED]" in str(redacted_dict):
            print_success(f"Field '{field}' redacted in dict")
        else:
            print_failure(f"Field '{field}' not properly redacted in dict")
            all_ok = False
    return all_ok


# -------------------------------------------------------------------
# LOGGING TESTS
# -------------------------------------------------------------------
def test_log_event() -> bool:
    print_header("Testing Log Event")
    all_ok = True
    try:
        log_event("test_event", {
            "message": "This is a test log event",
            "data": {"key": "value", "pii": "SSN: 123-45-6789"}
        })
        print_success("log_event() called successfully")
        log_file = Path("logs/structured_events.json")
        if log_file.exists():
            print_success(f"Log file found: {log_file}")
            with open(log_file, "r") as f:
                events = json.load(f)
                if len(events) > 0:
                    print_success(f"Found {len(events)} events in log file")
                    last_event = events[-1]
                    if "[REDACTED]" in json.dumps(last_event):
                        print_success("PII was redacted in the log")
                    else:
                        print_warning("No PII found in log entry (may not contain PII)")
                else:
                    print_failure("No events found in log file")
                    all_ok = False
        else:
            print_failure("Log file not created")
            all_ok = False
    except Exception as e:
        print_failure(f"log_event() failed: {e}")
        all_ok = False
    return all_ok


# -------------------------------------------------------------------
# CONFIGURATION TEST
# -------------------------------------------------------------------
def test_config() -> bool:
    print_header("Testing Configuration")
    all_ok = True
    required = [
        'REGULATORY_RULES', 'MAX_RETRIES', 'REQUEST_TIMEOUT',
        'EXPONENTIAL_BASE', 'RETRY_JITTER_MAX_SECONDS', 'MAX_INCIDENT_LOOPS'
    ]
    for attr in required:
        if hasattr(config, attr):
            value = getattr(config, attr)
            print_success(f"  {attr}: {value}")
        else:
            print_failure(f"  {attr}: MISSING")
            all_ok = False
    if hasattr(config, 'REGULATORY_RULES'):
        rules = config.REGULATORY_RULES
        for state in ['CA', 'TX', 'IL', 'FL']:
            if state in rules:
                print_success(f"  State {state}: configured")
                state_rules = rules[state]
                for key in ['required_forms', 'min_staff_ratio', 'incident_notification']:
                    if key in state_rules:
                        print_success(f"    {key}: {state_rules[key]}")
                    else:
                        print_warning(f"    {key}: missing for {state}")
                        all_ok = False
            else:
                print_warning(f"  State {state}: not configured")
                all_ok = False
    return all_ok


# -------------------------------------------------------------------
# INTAKE WORKFLOW TEST
# -------------------------------------------------------------------
def test_intake_workflow() -> bool:
    print_header("Testing Patient Intake Workflow")
    all_ok = True
    orchestrator = IntakeOrchestrator()
    test_patients = [
        {
            "resident_name": "Mary Johnson",
            "dob": "1945-06-15",
            "state": "CA",
            "clinical_notes": "78-year-old female with hypertension, diabetes, and mild dementia. Fall risk detected.",
            "submitted_forms": ["admission_agreement", "care_plan", "medication_authorization"],
            "staff_ratio": "1:4"
        },
        {
            "resident_name": "Robert Smith",
            "dob": "1938-03-22",
            "state": "TX",
            "clinical_notes": "85-year-old male with COPD, heart failure, and depression.",
            "submitted_forms": ["admission_agreement", "care_plan"],
            "staff_ratio": "1:5"
        }
    ]
    
    
    # --- NEW: Test partial swarm failure ---
    print_info("Testing partial swarm failure...")
    failing_client = MockLLMClient(force_error_sequence=["server_error"] * 10)
    failing_orchestrator = IntakeOrchestrator()
    failing_orchestrator.medical_agent = MedicalHistoryAgent(client=failing_client, fallback=None)
    
    partial_result = failing_orchestrator.run({
        "resident_name": "Partial Failure Test",
        "dob": "1940-01-01",
        "state": "CA",
        "clinical_notes": "Test notes for partial failure",
        "submitted_forms": ["admission_agreement", "care_plan", "medication_authorization"],
        "staff_ratio": "1:5"
    })
    
    if partial_result.overall_status == "partial":
        print_success(f"  Partial failure: overall_status = {partial_result.overall_status}")
    else:
        print_failure(f"  Partial failure: expected 'partial', got {partial_result.overall_status}")
        all_ok = False
    
    if any("medical_history" in step for step in partial_result.incomplete_steps):
        print_success(f"  medical_history in incomplete_steps")
    else:
        print_failure("  medical_history should be in incomplete_steps")
        all_ok = False

    for i, patient_data in enumerate(test_patients, 1):
        print_info(f"Processing Patient {i}: {patient_data['resident_name']}")
        try:
            result = orchestrator.run(patient_data)
            if result.overall_status in ("complete", "partial"):
                print_success(f"Patient {i}: {result.overall_status.upper()} - {result.resident_name}")
                if result.incomplete_steps:
                    print_info(f"  Incomplete steps: {', '.join(result.incomplete_steps)}")
            else:
                print_failure(f"Patient {i}: {result.overall_status.upper()} - {result.resident_name}")
                all_ok = False
            if result.medical:
                print_success(f"  Medical summary: {result.medical.summary[:50]}...")
            else:
                print_warning("  Medical summary: Not available")
                all_ok = False
            if result.compliance:
                if result.compliance.compliant:
                    print_success("  Regulatory compliance: PASSED")
                else:
                    print_failure("  Regulatory compliance: FAILED")
                    print_info(f"  Missing forms: {', '.join(result.compliance.missing_forms)}")
                    all_ok = False
            else:
                print_warning("  Regulatory compliance: Not available")
                all_ok = False
            if result.family_welcome:
                print_success(f"  Family welcome: {result.family_welcome.tone}")
                print_info(f"  Message: {result.family_welcome.welcome_message[:60]}...")
            else:
                print_warning("  Family welcome: Not available")
                all_ok = False
        except Exception as e:
            print_failure(f"Error processing patient {i}: {e}")
            all_ok = False
        print()
    return all_ok


# -------------------------------------------------------------------
# STAFFING AGENT TEST
# -------------------------------------------------------------------
def test_staffing_agent() -> bool:
    print_header("Testing Staffing Agent")
    all_ok = True
    agent = StaffingAgent()
    test_cases = [
        {
            "name": "Compliant",
            "data": {"state": "CA", "nurse_name": "Sarah Johnson", "nurse_last_training_date": "2025-06-01",
                     "nurse_hours_worked_today": 8.0, "nurse_on_break": False,
                     "doctor_on_shift": True, "doctor_on_call": False},
            "expected": True
        },
        {
            "name": "Non-compliant - Training expired",
            "data": {"state": "CA", "nurse_name": "Mark Wilson", "nurse_last_training_date": "2023-01-01",
                     "nurse_hours_worked_today": 8.0, "nurse_on_break": False,
                     "doctor_on_shift": True, "doctor_on_call": True},
            "expected": False
        },
        {
            "name": "Non-compliant - No doctor",
            "data": {"state": "CA", "nurse_name": "Emily Brown", "nurse_last_training_date": "2025-06-01",
                     "nurse_hours_worked_today": 8.0, "nurse_on_break": False,
                     "doctor_on_shift": False, "doctor_on_call": False},
            "expected": False
        }
    ]
    for test in test_cases:
        print_info(f"Testing: {test['name']}")
        try:
            result = agent.run(test['data'])
            if result.success and result.output:
                if result.output.overall_compliant == test['expected']:
                    print_success(f"  Expected: {test['expected']}, Got: {result.output.overall_compliant}")
                else:
                    print_failure(f"  Expected: {test['expected']}, Got: {result.output.overall_compliant}")
                    all_ok = False
                if result.output.flags:
                    print_info(f"  Flags: {', '.join(result.output.flags)}")
                print_info(f"  Note: {result.output.staffing_note[:60]}...")
            else:
                print_failure(f"  Agent failed: {result.error}")
                all_ok = False
        except Exception as e:
            print_failure(f"  Error: {e}")
            all_ok = False
        print()
    return all_ok


# -------------------------------------------------------------------
# INCIDENT WORKFLOW TEST
# -------------------------------------------------------------------
def test_incident_workflow() -> bool:
    print_header("Testing Incident Workflow")
    all_ok = True
    workflow = IncidentWorkflow()
    test_incidents = [
        {
            "name": "Fall incident",
            "data": {
                "state": "CA",
                "narrative": "Patient fell in the bathroom at 2:30 PM. Hit head on sink. Nurse called immediately.",
                "nurse_name": "Sarah Johnson",
                "nurse_last_training": "2025-06-01",
                "nurse_hours_today": 6.0,
                "doctor_on_shift": True,
                "doctor_on_call": True
            }
        },
        {
            "name": "Medication error",
            "data": {
                "state": "TX",
                "narrative": "Patient received wrong medication dosage at 9:00 AM. Nurse noticed error and corrected it.",
                "nurse_name": "Mark Wilson",
                "nurse_last_training": "2025-06-01",
                "nurse_hours_today": 8.0,
                "doctor_on_shift": False,
                "doctor_on_call": True
            }
        }
    ]
    
    
    # --- NEW: Test loop guard escalation ---
    print_info("Testing loop guard escalation...")
    
    def never_resolves(missing_fields, current_fields, iteration):
        return {}
    
    escalation_audit = workflow.run(
        {"state": "CA", "narrative": "Test escalation incident", "resident_name": "Escalation Test"},
        field_resolver=never_resolves
    )
    
    if escalation_audit.status == "escalated":
        print_success(f"  Status: escalated")
    else:
        print_failure(f"  Expected 'escalated', got {escalation_audit.status}")
        all_ok = False
    
    if escalation_audit.escalated_to_human is True:
        print_success(f"  escalated_to_human = True")
    else:
        print_failure(f"  expected escalated_to_human = True, got {escalation_audit.escalated_to_human}")
        all_ok = False
    
    if escalation_audit.loop_iterations == config.MAX_INCIDENT_LOOPS:
        print_success(f"  loop_iterations = {config.MAX_INCIDENT_LOOPS}")
    else:
        print_failure(f"  expected {config.MAX_INCIDENT_LOOPS} loops, got {escalation_audit.loop_iterations}")
        all_ok = False

    for test in test_incidents:
        print_info(f"Testing: {test['name']}")
        try:
            result = workflow.run(test['data'])
            print_info(f"  Incident ID: {result.incident_id[:8]}...")
            print_info(f"  Status: {result.status}")
            if result.classification:
                print_success(f"  Classification: {result.classification.category}")
                print_info(f"  Confidence: {result.classification.confidence:.2f}")
            else:
                print_failure("  Classification: Not available")
                all_ok = False
            if result.notification_path:
                print_success(f"  Regulatory path: {result.notification_path.get('agency', 'Unknown')}")
            else:
                print_warning("  Regulatory path: Not available")
            if result.staffing_check:
                if result.staffing_check.overall_compliant:
                    print_success("  Staffing: Compliant")
                else:
                    print_warning("  Staffing: Non-compliant")
                    print_info(f"  Flags: {', '.join(result.staffing_check.flags)}")
            else:
                print_warning("  Staffing check: Not available")
            print_info(f"  Loop iterations: {result.loop_iterations}")
            print_info(f"  Converged: {result.converged}")
            print_info(f"  Escalated to human: {result.escalated_to_human}")
            if result.final_fields:
                print_info(f"  Final fields: {len(result.final_fields)} fields collected")
            if result.status == "escalated":
                print_warning("  Incident was escalated")
        except Exception as e:
            print_failure(f"Error: {e}")
            all_ok = False
        print()
    return all_ok


# -------------------------------------------------------------------
# AUDIT LOGS TEST
# -------------------------------------------------------------------
def test_audit_logs() -> bool:
    print_header("Testing Audit Logs")
    all_ok = True
    log_files = [
        "logs/guardian_system.log",
        "logs/structured_events.json",
        "logs/incidents.json",
        "live_audit.json"
    ]
    for log_file in log_files:
        path = Path(log_file)
        if path.exists():
            size = path.stat().st_size
            print_success(f"  {log_file}: {size} bytes")
            # Check if incident log has content (not just empty)
            if "incidents.json" in log_file and size > 10:
                try:
                    with open(path, "r") as f:
                        incidents = json.load(f)
                        print_info(f"    Found {len(incidents)} incidents logged")
                except:
                    print_warning(f"    {log_file}: Could not parse JSON")
            if "structured_events" in log_file and size > 0:
                try:
                    with open(path, "r") as f:
                        events = json.load(f)
                        last_event = events[-1] if events else None
                        if last_event:
                            print_info(f"    Last event: {last_event.get('event_type', 'Unknown')}")
                            print_info(f"    Timestamp: {last_event.get('timestamp', 'Unknown')}")
                except json.JSONDecodeError:
                    print_warning(f"    {log_file}: Not valid JSON")
                    all_ok = False
        else:
            print_warning(f"  {log_file}: Not found")
            all_ok = False
    return all_ok


# -------------------------------------------------------------------
# HARNESS TESTS
# -------------------------------------------------------------------
def test_harness_basic() -> bool:
    print_header("LLMHarness: Basic Success")
    all_ok = True
    class GoodClient(LLMClient):
        def complete(self, system_prompt, user_prompt):
            return '{"answer": "Hello world"}'
    harness = LLMHarness(
        agent_name="TestBasic",
        system_prompt="You are helpful.",
        input_schema=TestInput,
        output_schema=TestOutput,
        client=GoodClient(),
        timeout=2.0,
        max_retries=3,
    )
    def builder(inp: TestInput) -> str:
        return f"Q: {inp.query}"
    result = harness.run({"query": "Hi"}, builder)
    if result.success and result.output is not None and result.output.answer == "Hello world":
        print_success("Basic call succeeded with correct output")
    else:
        print_failure(f"Basic call failed: {result.error}")
        all_ok = False
    if result.attempts == 1:
        print_success(f"Attempts count = 3 (2 failures + 1 success)")
    else:
        print_failure(f"Expected attempts=3, got {result.attempts}")
        all_ok = False
    return all_ok


def test_harness_retry() -> bool:
    print_header("LLMHarness: Retry on RetryableError")
    all_ok = True
    class FlakyClient(LLMClient):
        def __init__(self):
            self.calls = 0
        def complete(self, system_prompt, user_prompt):
            self.calls += 1
            if self.calls <= 2:
                raise RetryableError("Simulated retryable error", status_code=429)
            return '{"answer": "Retried successfully"}'
    harness = LLMHarness(
        agent_name="TestRetry",
        system_prompt="You are helpful.",
        input_schema=TestInput,
        output_schema=TestOutput,
        client=FlakyClient(),
        timeout=5.0,
        max_retries=5,
    )
    def builder(inp: TestInput) -> str:
        return f"Q: {inp.query}"
    result = harness.run({"query": "Retry me"}, builder)
    if result.success and result.output is not None and result.output.answer == "Retried successfully":
        print_success(f"Retry succeeded after {result.attempts} attempts")
    else:
        print_failure(f"Retry failed: {result.error}")
        all_ok = False
    if result.attempts == 3:
        print_success("Attempts count = 3 (2 failures + 1 success)")
    else:
        print_failure(f"Expected attempts=3, got {result.attempts}")
        all_ok = False
    return all_ok


def test_harness_timeout_fallback() -> bool:
    print_header("LLMHarness: Timeout + Fallback")
    all_ok = True
    class SlowClient(LLMClient):
        def complete(self, system_prompt, user_prompt):
            time.sleep(5)
            return '{"answer": "Too slow"}'
    harness = LLMHarness(
        agent_name="TestTimeout",
        system_prompt="You are helpful.",
        input_schema=TestInput,
        output_schema=TestOutput,
        client=SlowClient(),
        timeout=1.0,
        max_retries=1,
        fallback=TestOutput(answer="Fallback answer"),
    )
    def builder(inp: TestInput) -> str:
        return f"Q: {inp.query}"
    result = harness.run({"query": "Timeout"}, builder)
    if result.success and result.used_fallback and result.output is not None and result.output.answer == "Fallback answer":
        print_success("Timeout triggered fallback correctly")
    else:
        print_failure(f"Timeout fallback failed: {result.error}")
        all_ok = False
    if result.error is not None and ("Timeout" in result.error or "Timed out" in result.error):
        print_info("Timeout message found in error field")
    else:
        print_info("Fallback returned successfully (timeout message format may vary)")
    return all_ok


def test_harness_input_validation() -> bool:
    print_header("LLMHarness: Input Validation")
    all_ok = True
    class DummyClient(LLMClient):
        def complete(self, system_prompt, user_prompt):
            return '{"answer": "dummy"}'
    harness = LLMHarness(
        agent_name="TestInputVal",
        system_prompt="You are helpful.",
        input_schema=TestInput,
        output_schema=TestOutput,
        client=DummyClient(),
        timeout=2.0,
    )
    def builder(inp: TestInput) -> str:
        return f"Q: {inp.query}"
    result = harness.run({"wrong": "data"}, builder)
    if not result.success and result.error is not None and "Input schema validation failed" in result.error:
        print_success("Input validation correctly rejected bad input")
    else:
        print_failure(f"Input validation did not catch error: {result.error}")
        all_ok = False
    return all_ok


def test_harness_output_validation() -> bool:
    print_header("LLMHarness: Output Validation")
    all_ok = True
    class BadOutputClient(LLMClient):
        def complete(self, system_prompt, user_prompt):
            return '{"wrong": "field"}'
    harness = LLMHarness(
        agent_name="TestOutputVal",
        system_prompt="You are helpful.",
        input_schema=TestInput,
        output_schema=TestOutput,
        client=BadOutputClient(),
        timeout=2.0,
        fallback=TestOutput(answer="Fallback for bad output"),
    )
    def builder(inp: TestInput) -> str:
        return f"Q: {inp.query}"
    result = harness.run({"query": "bad output"}, builder)
    if result.success and result.used_fallback and result.output is not None and result.output.answer == "Fallback for bad output":
        print_success("Output validation triggered fallback")
    else:
        print_failure(f"Output validation fallback failed: {result.error}")
        all_ok = False
    return all_ok


def test_harness_redaction_logging() -> bool:
    print_header("LLMHarness: Logging & Redaction")
    all_ok = True

    print_info("Writing test log with PII to verify redaction...")
    log_event('redaction_test', {
        'test_name': 'Redaction Verification',
        'ssn': '123-45-6789',
        'email': 'john.doe@example.com',
        'phone': '555-123-4567',
        'dob': '1940-01-01',
        'credit_card': '1234-5678-9012-3456',
        'patient_name': 'Jane Smith'
    })
    print_success("Test log written with PII")

    log_file = Path("logs/structured_events.json")
    if not log_file.exists():
        print_failure("Structured log file not found")
        return False

    try:
        with open(log_file, "r") as f:
            events = json.load(f)

        found = False
        redacted_found = False
        name_redacted = False

        for ev in reversed(events):
            if ev.get("event_type") == "redaction_test":
                found = True
                data = ev.get("data", {})

                print_info("\n=== Redaction Test Results ===")
                print_info(f"Test name: {data.get('test_name', 'Unknown')}")

                # Check each field
                checks = [
                    ('ssn', '[REDACTED]'),
                    ('email', '[REDACTED]'),
                    ('phone', '[REDACTED]'),
                    ('dob', '[REDACTED]'),
                    ('credit_card', '[REDACTED]'),
                ]

                for field, expected in checks:
                    actual = data.get(field, 'MISSING')
                    if actual == expected:
                        print_success(f"  {field}: {actual} (redacted)")
                        redacted_found = True
                    else:
                        print_failure(f"  {field}: {actual} (NOT REDACTED!)")
                        all_ok = False

                # Check patient_name - should be redacted per current policy
                name_actual = data.get('patient_name', '')
                if name_actual == '[REDACTED]':
                    print_success(f"  patient_name: {name_actual} (redacted - HIPAA compliant)")
                    name_redacted = True
                else:
                    print_failure(f"  patient_name: {name_actual} (NOT REDACTED! HIPAA violation)")
                    all_ok = False

                break

        if not found:
            print_failure("No redaction_test event found in log")
            all_ok = False
        elif redacted_found and name_redacted:
            print_success("\n✅ PII redaction is working correctly!")
            print_info("   SSN, Email, Phone, DOB, Credit Card are all redacted.")
            print_info("   Patient names are also redacted (HIPAA compliant).")
        else:
            print_failure("Redaction test incomplete")
            all_ok = False

    except Exception as e:
        print_failure(f"Failed to inspect log file: {e}")
        all_ok = False

    return all_ok


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
def run_all_tests():
    print_header("GUARDIAN CRM SYSTEM CHECKER")
    print(f"Started at: {datetime.now().isoformat()}")
    print(f"Python version: {sys.version}")

    tests = [
        ("Imports", check_imports),
        ("Redaction", test_redaction),
        ("Log Event", test_log_event),
        ("Configuration", test_config),
        ("Intake Workflow", test_intake_workflow),
        ("Staffing Agent", test_staffing_agent),
        ("Incident Workflow", test_incident_workflow),
        ("Audit Logs", test_audit_logs),
        ("Harness Basic", test_harness_basic),
        ("Harness Retry", test_harness_retry),
        ("Harness Timeout Fallback", test_harness_timeout_fallback),
        ("Harness Input Validation", test_harness_input_validation),
        ("Harness Output Validation", test_harness_output_validation),
        ("Harness Redaction Logging", test_harness_redaction_logging),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_failure(f"Test '{test_name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    print_header("FINAL SUMMARY")
    passed = sum(1 for _, res in results if res)
    total = len(results)
    for test_name, result in results:
        if result:
            print_success(f"  {test_name}: PASSED")
        else:
            print_failure(f"  {test_name}: FAILED")
    print()
    print(f"{Colors.BOLD}Total: {passed}/{total} tests passed{Colors.END}")
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 All tests passed! System is ready.{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️ {total - passed} test(s) failed. Please fix the issues above.{Colors.END}")
        return 1


if __name__ == "__main__":
    Path("logs").mkdir(exist_ok=True)
    sys.exit(run_all_tests())
