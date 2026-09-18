"""Structured logging with automatic redaction of sensitive fields."""
from __future__ import annotations

import json
import logging
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "guardian_system.log"
REDACTED_PLACEHOLDER = "[REDACTED]"

_PII_REGEX = re.compile(
    r'(\b\d{3}-\d{2}-\d{4}\b)|'
    r'(\b\d{3}-\d{3}-\d{4}\b)|'
    r'(\b\d{4}-\d{4}-\d{4}-\d{4}\b)|'
    r'(\b[\w\.-]+@[\w\.-]+\.\w+\b)|'
    r'(\b\d{5}(?:-\d{4})?\b)'
)

SENSITIVE_FIELD_NAMES = (
    'ssn', 'social', 'phone', 'telephone', 'email',
    'credit_card', 'card_number', 'cvv', 'password',
    'secret', 'token', 'api_key', 'authorization',
    'resident_name', 'patient_name', 'name', 'family_name',
    'first_name', 'last_name', 'full_name'
)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in SENSITIVE_FIELD_NAMES:
                out[k] = REDACTED_PLACEHOLDER
            else:
                out[k] = redact(v)
        return out
    elif isinstance(value, list):
        return [redact(v) for v in value]
    elif isinstance(value, str):
        return redact_text(value)
    else:
        return value


def redact_text(text: str) -> str:
    if not isinstance(text, str):
        return text
    redacted_text = _PII_REGEX.sub(REDACTED_PLACEHOLDER, text)
    redacted_text = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', REDACTED_PLACEHOLDER, redacted_text)
    redacted_text = re.sub(r'\b0\d{3,4}\s?\d{3,4}\s?\d{3,4}\b', REDACTED_PLACEHOLDER, redacted_text)
    redacted_text = re.sub(r'\b\d{10,11}\b', REDACTED_PLACEHOLDER, redacted_text)
    return redacted_text


def build_logger(name: str = "guardian") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def log_event(event_type: str, payload: Dict[str, Any]) -> None:
    safe_payload = redact(deepcopy(payload))
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "data": safe_payload
    }
    structured_log = LOG_DIR / "structured_events.json"
    try:
        if structured_log.exists():
            with open(structured_log, "r") as f:
                events = json.load(f)
        else:
            events = []
        events.append(log_entry)
        with open(structured_log, "w") as f:
            json.dump(events, f, indent=2)
    except Exception as e:
        logger = logging.getLogger("guardian")
        logger.error(f"Failed to write structured log: {e}")
        logger.info(f"Event: {json.dumps(log_entry)}")


def log_request_response(request: Dict[str, Any], response: Dict[str, Any], duration_ms: float, success: bool) -> None:
    logger = build_logger("guardian.api")
    log_entry = {
        "request": redact(request),
        "response": redact(response),
        "duration_ms": duration_ms,
        "success": success
    }
    logger.info(json.dumps(log_entry))
    log_event("api_call", log_entry)


logger = build_logger()
