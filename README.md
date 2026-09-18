# Guardian CRM — AI Layer for Residential Care

An AI layer for residential care facility CRM: resident intake, incident reporting, regulatory compliance, and family communication — all built on a reusable LLM harness. Runs on the Anthropic API with your key, or fully offline in demo mode with a built-in mock LLM and a live dashboard.

> This is a working prototype / demo system, not a certified healthcare product. Compliance checking demonstrates the pattern against sample state rules — it is not a substitute for legal or regulatory review.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run (a menu appears: live mode with your API key, or offline demo)
python main.py

# Run the test suite
python checker.py
```

On startup you choose:

1. **Live mode** — real Anthropic API. Paste your API key at the prompt (it's tested with one tiny API call, and you can save it for next time), or set `ANTHROPIC_API_KEY` in advance.
2. **Demo mode** — no key needed. Runs the same continuous patient-processing dashboard on a deterministic mock LLM.

If the key is missing or fails, the app shows the error for 2 seconds and falls back to demo mode instead of crashing.

CLI shortcuts (skip the menu):

```bash
python main.py --mode 1   # 6-step fixed demo suite, no key needed
python main.py --mode 2   # continuous live dashboard (uses env/saved API key)
```

## Architecture

### 1. LLM Harness (`harness/`)

The core component that every agent uses. Provides:

- **Schema validation** — input/output validation with Pydantic
- **Retry with exponential backoff** — only on 429/5xx errors
- **Timeout with graceful fallback** — configurable timeout, returns fallback if provided
- **Redacted logging** — PII automatically redacted before logging
- **Mock LLM support** — run offline with deterministic mock responses

### 2. Agent Swarm (`agents/`)

Multi-agent orchestration for resident intake:

- **MedicalHistoryAgent** — summarizes clinical notes, identifies risks
- **RegulatoryComplianceAgent** — validates forms against state rules (CA, TX, IL, FL)
- **FamilyWelcomeAgent** — drafts plain-language welcome messages for families
- **IntakeOrchestrator** — coordinates all three, continues on partial failure

### 3. Incident Workflow

Dynamic incident reporting with:

- **Classification** — categorizes incidents (fall, medication_error, elopement, abuse_allegation, death, other)
- **State routing** — routes to the correct regulatory agency based on state
- **Validation loop** — bounded loop (max 3 iterations) to collect missing fields
- **Human escalation** — escalates if validation doesn't converge
- **Audit trail** — JSON audit log per incident

## Configuration (`config.py`)

```python
# LLM Backend - "mock" or "anthropic"
LLM_BACKEND = "mock"

# Retry settings
MAX_RETRIES = 3
REQUEST_TIMEOUT = 10.0
EXPONENTIAL_BASE = 2

# Incident loop guard
MAX_INCIDENT_LOOPS = 3

# State regulatory rules (CA, TX, IL, FL)
REGULATORY_RULES = {...}
```

## Testing

```bash
python checker.py
```

## Project Structure

```
guardian-crm/
├── main.py              # Startup menu + live dashboard + demo suite
├── checker.py           # Test suite
├── config.py            # All configuration
├── factory.py           # Patient data generator
├── patient_bank.json    # Demo patient pool for the dashboard
├── agents/              # AI agents
├── harness/             # Reusable LLM harness
├── models/              # Pydantic schemas
├── demo_data/           # Fixed inputs for the 6-step demos
├── logs/                # Structured logs (created at runtime)
└── requirements.txt     # Dependencies
```

## Key Features

### Reusable LLM Harness
- Schema validation before/after LLM calls
- Retry only on rate-limit (429) and server (5xx) errors
- Configurable timeout with fallback values
- Automatic PII redaction in logs

### Multi-Agent Intake Swarm
- Orchestrator runs 3 sub-agents
- Continues on partial failure, flags incomplete steps
- Returns complete/partial/failed status

### Dynamic Incident Workflow
- AI classification of incident type
- State-specific regulatory routing
- Bounded validation loop with max iterations
- Human escalation on non-convergence
- JSON audit trail per incident

### Runs Anywhere
- Demo mode runs fully offline (no API key needed)
- One menu choice switches to the Anthropic API
- 13 tests in the suite (`python checker.py`)
- PII redacted in logs — designed with healthcare-privacy sensitivity in mind, but not a certified compliance product

## Demo Walkthrough

The system includes a complete video walkthrough: `guardian_crm_walkthrough.mp4`

Or run the live dashboard:

```bash
python main.py
```

## License

MIT
