# Guardian CRM

## AI Layer for Residential Care Facility Management

Resident intake, incident reporting, regulatory compliance, and family communication — all built on a reusable LLM harness.

[![Status](https://img.shields.io/badge/status-production--ready-brightgreen.svg?style=for-the-badge)](https://github.com/mozmoz888-maker/Guardian-crm-1-)
[![License](https://img.shields.io/badge/license-MIT-blue.svg?style=for-the-badge)](https://github.com/mozmoz888-maker/Guardian-crm-1-/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg?style=for-the-badge)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-14%2F14-brightgreen.svg?style=for-the-badge)](https://github.com/mozmoz888-maker/Guardian-crm-1-)

## Table of Contents

    Overview

    Key Features

    Quick Start

    Configuration

    LLM Backends

    Architecture

    Project Structure

    Demo Walkthrough

    Testing

    Documentation

    License

## Overview

Guardian CRM automates the operational AI layer for residential care facilities. The system processes resident intakes through a multi-agent swarm, handles dynamic incident reporting with state-specific regulatory routing, and provides a live operational dashboard — all powered by a reusable LLM harness that handles retries, timeouts, schema validation, and PII redaction out of the box.

Built for facility owners who need HIPAA-aware, multi-state compliance without building AI infrastructure from scratch.

## Key Features

Feature Description
LLM Harness Schema validation, exponential backoff retry (429/5xx), timeout with fallback, PII redaction logging
Intake Swarm Orchestrator coordinates Medical History, Regulatory Compliance, and Family Welcome agents — continues on partial failure
Incident Workflow LLM classification → state routing → bounded validation loop (MAX 3 iterations) → human escalation → JSON audit trail
Live Dashboard Real-time patient intake, incident audit display, staffing compliance, and operational metrics
Mock LLM Support Run offline with deterministic mock responses — no API key required
Multi-State Compliance Pre-configured regulatory rules for CA, TX, IL, FL
PII Redaction Automatic redaction of sensitive fields in all logs
Audit Trail Structured JSON audit log for every incident

## Quick Start

Prerequisites

    Python 3.12+

    pip

    (Optional) Anthropic API key for real LLM

Installation
bash

Clone the repository
git clone https://github.com/mozmoz888-maker/guardian-crm-1.git
cd guardian-crm

Install dependencies
pip install -r requirements.txt

Run the Demo
bash

Run the full 6-step demo walkthrough
python main.py --mode 1

Run the Live Dashboard
bash

Process 5 patients from the patient bank
python main.py --mode 2 --count 5

Run indefinitely (processes patient bank, loops when exhausted)
python main.py --mode 2

Run Tests
bash

Run the full checker suite (14/14 tests)
python checker.py

Run pytest unit tests
pytest tests/ -v

## Configuration

All configuration lives in config.py:
python

LLM Configuration
LLM_BACKEND = "mock"       # "mock" or "anthropic"
LLM_MODEL = "claude-3-sonnet-20240229"

Retry Configuration
MAX_RETRIES = 3
REQUEST_TIMEOUT = 10.0
EXPONENTIAL_BASE = 2
RETRY_JITTER_MAX_SECONDS = 0.25

Incident Workflow Configuration
MAX_INCIDENT_LOOPS = 3

Regulatory Rules by State
REGULATORY_RULES = {
    'CA': { ... },
    'TX': { ... },
    'IL': { ... },
    'FL': { ... }
}

## LLM Backends

The system supports two LLM backends:
Backend Description se Case
"mock" Deterministic fake responses, no API key needed Development, testing, demos
"anthropic" Real Claude API Production
Why "mock" is the Default

## The mock backend is the default because

    No API key required - You can run the entire system offline

    Deterministic responses - Tests and demos produce consistent results

    No cost - No API usage charges

    No rate limits - You can run unlimited requests

    Faster - No network latency

The mock client simulates realistic LLM behavior:

    Summarizes clinical notes based on keywords

    Checks compliance against state rules

    Classifies incidents based on text

    Validates required fields

## Switching to Real Anthropic API

To use the real Claude API:

Step 1: Install the package
bash

pip install anthropic

Step 2: Set your API key
bash

Option 1: Environment variable (recommended)
export ANTHROPIC_API_KEY=your_key_here

Option 2: In config.py (NOT recommended - keys shouldn't be in code)

Step 3: Change the backend
python

config.py

LLM_BACKEND = "anthropic"
LLM_MODEL = "claude-3-sonnet-20240229"  # or your preferred model

The system will automatically use the Anthropic client.
Graceful Fallback

If you switch to "anthropic" but don't have an API key set, the system:

Logs a warning: "Failed to initialize Anthropic client. Falling back to MockLLMClient."

Falls back to mock mode automatically

Continues running without crashing

bash

## Example output

$ python main.py --mode 1
Failed to initialize Anthropic client: api_key must be set.
   Falling back to MockLLMClient.
Mock LLM client initialized. Using deterministic responses.

Switching Back to Mock Mode
python

LLM_BACKEND = "mock"

No API key required. All responses are deterministic and generated locally.
Architecture
Component Overview
text

┌─────────────────────────────────────────────────────────────┐
│                     LLM Harness (harness/)                  │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐         │
│  │  Validation │  │  Retry with │  │  Timeout with│         │
│  │   Pydantic  │  │  Exponential│  │  Fallback    │         │
│  │             │  │  Backoff    │  │              │         │
│  └─────────────┘  └─────────────┘  └──────────────┘         │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐                           │
│  │  PII        │  │  Structured │                           │
│  │  Redaction  │  │  Logging    │                           │
│  └─────────────┘  └─────────────┘                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Agent Swarm (agents/)                  │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐      │
│  │   Medical    │  │ Regulatory   │  │   Family      │      │
│  │   History    │  │ Compliance   │  │   Welcome     │      │
│  │   Agent      │  │ Agent        │  │   Agent       │      │
│  └──────────────┘  └──────────────┘  └───────────────┘      │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐      │
│  │   Incident   │  │  Staffing    │  │   Incident    │      │
│  │   Classifier │  │  Agent       │  │   Validator   │      │
│  └──────────────┘  └──────────────┘  └───────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator (orchestrator.py)           │
│                                                             │
│ Coordinates the full workflow:                              │
│ Raw Intake → Validate → Run Agents → Aggregate Results     │
│                                                             │
│  If any sub-agent fails:                                    │
│  - Records failure in `incomplete_steps`                    │
│  - Continues with remaining agents                          │
│  - Returns `complete` / `partial` / `failed`                │
└─────────────────────────────────────────────────────────────┘

Data Flow

Resident Intake → Orchestrator validates form → runs 3 sub-agents in sequence → returns IntakeWorkflowResult

Incident Report → Classifier categorizes → routes to state agency → validation loop (max 3) → audit trail

Staffing Check → Validates training, hours, doctor availability against state rules

Project Structure

guardian-crm/
├── main.py              # Demo + live dashboard entrypoint
├── checker.py           # Full test suite (14 tests)
├── config.py            # All configuration
├── factory.py           # Patient data generator
├── agents/              # AI agents
│   ├── orchestrator.py
│   ├── medical_history_agent.py
│   ├── regulatory_compliance_agent.py
│   ├── family_welcome_agent.py
│   ├── staffing_agent.py
│   └── incident_agents.py
├── harness/             # Reusable LLM harness
│   ├── llm_harness.py
│   ├── llm_clients.py
│   ├── retry.py
│   ├── logging_utils.py
│   └── exceptions.py
├── models/              # Pydantic schemas
│   ├── intake_schemas.py
│   ├── incident_schemas.py
│   └── staffing_schemas.py
├── demo_data/           # Sample JSON files
├── tests/               # Pytest unit tests
├── logs/                # Structured logs + audit trail
├── requirements.txt     # Dependencies
├── README.md            # This file
└── LICENSE              # MIT License

Demo Walkthrough

The --mode 1 demo showcases all core capabilities:
Demo What It Demonstrates
1 Intake Swarm — CA compliance failure (missing medication_authorization)
2 Intake Swarm — sub-agent failure with orchestrator continuation
3 Harness — retry with exponential backoff (429 → 500 → success)
4 Harness — timeout with graceful fallback
5 Incident Workflow — classification + validation loop converges
6 Incident Workflow — loop guard triggers human escalation

Testing
Checker Suite
bash

python checker.py

Expected output: 14/14 tests passed

The checker validates:

    Imports

    PII Redaction

    Configuration

    Intake Workflow (including partial failure)

    Staffing Agent

    Incident Workflow (including loop guard escalation)

    Audit Logs

    Harness Basic Success

    Harness Retry

    Harness Timeout Fallback

    Harness Input Validation

    Harness Output Validation

    Harness Redaction Logging

Pytest Suite
bash

pytest tests/ -v

Additional unit tests covering:

    Orchestrator continues on sub-agent failure

    Incident workflow escalates on non-convergence

    Harness resilience features

Documentation

    API Reference - See models/ for Pydantic schemas

    Agent Documentation - See agents/ for detailed docstrings

    Harness Documentation - See harness/ for implementation details

    Configuration Reference - See config.py for all settings

License

This project is licensed under the MIT License — see the LICENSE file for details.

Acknowledgements

    Built with Pydantic for schema validation

    Uses Anthropic Claude for real LLM support

    Inspired by LangChain multi-agent patterns

If you find this project useful, please consider:

    Starring the repository

    Forking and contributing

    Reporting issues...
