"""Guardian CRM — End-to-end demo and live service.

Run with: python main.py

- By default, runs in LIVE MODE: reads patients from patient_bank.json.
- To run the 6‑step demo instead, use: python main.py --mode 1
- To generate and process test patients in demo mode: python main.py --mode 1 --demo-patients 10
- To process a specific number of patients in live mode: python main.py --count 100
- Audit log written to live_audit.json.
- Press Ctrl+C to stop.
"""
import random
import time
import json
import os
import sys
import subprocess
import argparse
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from agents.medical_history_agent import MedicalHistoryAgent
from agents.orchestrator import IntakeOrchestrator
from harness.llm_clients import MockLLMClient
from agents.incident_workflow import IncidentWorkflow
from models.intake_schemas import MedicalHistoryOutput

console = Console()

# --- GLOBAL CONFIGURATION ---
LIVE_AUDIT_FILE = "live_audit.json"
BANK_FILE = "patient_bank.json"
DEMO_DATA_DIR = "demo_data"

# --- SHIPPING SWITCHES ---
SHIPPING_MODE = 2
DEMO_GENERATE_PATIENTS = True
DEMO_PATIENT_COUNT = 5
DEMO_SKIP_FIXED_DEMOS = False

# Processing speed (seconds between patients)
PROCESSING_SPEED = 2


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def check_llm_configuration():
    """Warn if using real LLM without API key."""
    import config
    if config.LLM_BACKEND == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            console.print(
                "[bold yellow]⚠️ WARNING: LLM_BACKEND is 'anthropic' but ANTHROPIC_API_KEY is not set.[/bold yellow]\n"
                "[yellow]  Falling back to mock LLM. Set ANTHROPIC_API_KEY to use real LLM.[/yellow]"
            )
            config.LLM_BACKEND = "mock"
        else:
            console.print("[green]✅ ANTHROPIC_API_KEY found. Using real LLM.[/green]")











def load(path: str) -> dict:
    """Load JSON file and return as dict."""
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        console.print(f"[yellow]Warning: File {path} not found.[/yellow]")
        return {}
    except json.JSONDecodeError as e:
        console.print(f"[red]Error: Could not parse JSON from {path}: {e}[/red]")
        return {}


def header(number: str, title: str) -> None:
    console.print()
    console.rule(f"[bold cyan]{number}) {title}[/bold cyan]")


def status_badge(ok: bool, label_true: str = "OK", label_false: str = "FAILED") -> Text:
    return Text(f" {label_true} " if ok else f" {label_false} ",
                style="bold white on green" if ok else "bold white on red")


def overall_badge(status: str) -> Text:
    style = {"complete": "bold white on green", "partial": "bold black on yellow",
             "failed": "bold white on red", "escalated": "bold black on yellow"}.get(status, "bold white on grey50")
    return Text(f" {status.upper()} ", style=style)


def generate_test_patients(count: int) -> bool:
    """Generate test patients using factory.py"""
    console.print(f"[cyan]Generating {count} test patients...[/cyan]")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    factory_path = os.path.join(script_dir, "factory.py")
    if not os.path.exists(factory_path):
        console.print(f"[red]Error: factory.py not found in: {factory_path}[/red]")
        return False
    try:
        result = subprocess.run(
            [sys.executable, factory_path, "--count", str(count)],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            console.print(f"[red]Error running factory: {result.stderr}[/red]")
            return False
        console.print(f"[green]✓ Generated {count} test patients[/green]")
        return True
    except Exception as e:
        console.print(f"[red]Failed to run factory: {e}[/red]")
        return False


# ---------------------------------------------------------------------------
# 1) & 2) INTAKE SWARM DEMOS
# ---------------------------------------------------------------------------
def print_intake_result(result, subtitle: str) -> None:
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("Step")
    table.add_column("Status")
    table.add_column("Result")

    table.add_row("Medical history", status_badge(result.medical is not None),
                  getattr(result.medical, "summary", "No medical summary available") if result.medical else "No medical summary available")
    table.add_row("Regulatory compliance", status_badge(result.compliance is not None),
                  ("Compliant" if result.compliance.compliant else f"Missing: {', '.join(result.compliance.missing_forms)}")
                  if result.compliance else "[dim]not available[/dim]")
    table.add_row("Family welcome message", status_badge(result.family_welcome is not None),
                  (getattr(result.family_welcome, "welcome_message", "Welcome message pending") if result.family_welcome else "Welcome message pending"[:70] + "...") if result.family_welcome else "[dim]not available[/dim]")

    console.print(Panel(
        table,
        title=f"Resident Intake — {result.resident_name}",
        subtitle=subtitle,
        border_style="cyan",
    ))
    console.print("Overall status:", overall_badge(result.overall_status))
    if result.incomplete_steps:
        console.print("[yellow]Flagged incomplete:[/yellow]")
        for step in result.incomplete_steps:
            console.print(f"  • {step}")


def demo_intake_clean():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header("1", f"INTAKE SWARM — partial failure (CA compliance missing medication_authorization) [{timestamp}]")
    orchestrator = IntakeOrchestrator()
    incident_reporter = IncidentDashboardReporter()
    sample_data = load(f"{DEMO_DATA_DIR}/sample_intake.json")
    if not sample_data:
        console.print("[red]Could not load sample_intake.json. Skipping demo.[/red]")
        return
    result = orchestrator.run(sample_data)
    print_intake_result(result, "All sub-agents ran successfully")


def demo_intake_partial_failure():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header("2", f"INTAKE SWARM — one sub-agent fails, orchestrator continues [{timestamp}]")
    failing_client = MockLLMClient(force_error_sequence=["server_error"] * 10)
    orchestrator = IntakeOrchestrator()
    incident_reporter = IncidentDashboardReporter()
    orchestrator.medical_agent = MedicalHistoryAgent(client=failing_client, fallback=None)
    sample_data = load(f"{DEMO_DATA_DIR}/sample_intake.json")
    if not sample_data:
        console.print("[red]Could not load sample_intake.json. Skipping demo.[/red]")
        return
    result = orchestrator.run(sample_data)
    print_intake_result(result, "Medical history agent forced to fail (simulated outage)")


# ---------------------------------------------------------------------------
# 3) & 4) HARNESS RESILIENCE DEMOS
# ---------------------------------------------------------------------------
def demo_retry_recovery():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header("3", f"HARNESS — retry with exponential backoff [{timestamp}]")
    console.print("Simulating: 429 rate-limit → 500 server error → success\n")
    client = MockLLMClient(force_error_sequence=["rate_limit", "server_error", "ok"])
    agent = MedicalHistoryAgent(client=client)
    result = agent.run({"clinical_notes": "Routine notes, stable vitals, no acute issues."})

    table = Table(box=None, padding=(0, 1))
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Outcome", str(status_badge(result.success)))
    table.add_row("Attempts taken", str(result.attempts))
    table.add_row("Total latency", f"{result.latency_seconds:.2f}s")
    table.add_row("Used fallback", "Yes" if result.used_fallback else "No")
    console.print(Panel(table, title="Retry demo result", border_style="green" if result.success else "red"))


def demo_timeout_fallback():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header("4", f"HARNESS — timeout with graceful fallback [{timestamp}]")
    console.print("Simulating a request that takes 15s (exceeds the 10s configured timeout)\n")
    slow_client = MockLLMClient(force_latency=15.0)
    fallback = MedicalHistoryOutput(
        summary="Fallback: clinical summary unavailable, manual review required.",
        risk_flags=["needs_manual_review"],
        confidence=0.0,
    )
    agent = MedicalHistoryAgent(client=slow_client, fallback=fallback)
    result = agent.run({"clinical_notes": "Notes too slow to summarize in this demo."})

    table = Table(box=None, padding=(0, 1))
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Outcome", str(status_badge(result.success)))
    table.add_row("Used fallback", "Yes" if result.used_fallback else "No")
    if result.output is not None and hasattr(result.output, 'summary'):
        fallback_summary = result.output.summary
    else:
        fallback_summary = "-"
    table.add_row("Fallback summary", fallback_summary)
    table.add_row("Total latency", f"{result.latency_seconds:.2f}s")
    console.print(Panel(table, title="Timeout demo result", border_style="yellow"))


# ---------------------------------------------------------------------------
# 5) & 6) INCIDENT WORKFLOW DEMOS
# ---------------------------------------------------------------------------
def print_incident_audit(audit, subtitle: str) -> None:
    table = Table(box=None, padding=(0, 1))
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Incident ID", audit.incident_id[:8] + "…")
    table.add_row("Classification", f"{audit.classification.category} (confidence {audit.classification.confidence:.0%})" if audit.classification else "-")
    if audit.notification_path:
        table.add_row("Notify", f"{audit.notification_path['agency']} within {audit.notification_path['hours']}h")
    table.add_row("Validation loop", f"{audit.loop_iterations} iteration(s), converged: {'Yes' if audit.converged else 'No'}")
    table.add_row("Escalated to human", "Yes" if audit.escalated_to_human else "No")
    table.add_row("Incident date/time", audit.final_fields.get("date_time", "N/A"))
    border = "green" if audit.status == "complete" else "yellow"
    console.print(Panel(table, title="Incident Report Audit Trail", subtitle=subtitle, border_style=border))
    console.print("Final status:", overall_badge(audit.status))
    if audit.final_fields:
        console.print("\n[bold]Fields on file:[/bold]")
        for k, v in audit.final_fields.items():
            console.print(f"  • {k}: {v}")


def demo_incident_converges():
    header("5", "INCIDENT WORKFLOW — classification + validation loop converges")
    workflow = IncidentWorkflow()
    sample_data = load(f"{DEMO_DATA_DIR}/sample_incident.json")
    if not sample_data:
        console.print("[red]Could not load sample_incident.json. Skipping demo.[/red]")
        return
    audit = workflow.run(sample_data)
    print_incident_audit(audit, "Staff supplied all follow-up details when asked")


def demo_incident_escalates():
    header("6", "INCIDENT WORKFLOW — loop guard triggers human escalation")

    def never_resolves(missing_fields, current_fields, iteration):
        current_fields["date_time"] = "2026-08-07T14:30:00"
        return {}

    workflow = IncidentWorkflow()
    sample_data = load(f"{DEMO_DATA_DIR}/sample_incident.json")
    if not sample_data:
        console.print("[red]Could not load sample_incident.json. Skipping demo.[/red]")
        return
    audit = workflow.run(sample_data, field_resolver=never_resolves)
    print_incident_audit(audit, "Required fields never got filled in -> escalated instead of looping forever")


# ---------------------------------------------------------------------------
# DEMO WITH GENERATED PATIENTS
# ---------------------------------------------------------------------------
def demo_with_generated_patients(num_patients: int = 5):
    """Run demo with generated test patients instead of fixed samples."""
    header("DEMO", f"Processing {num_patients} generated test patients")
    console.print(f"\n[cyan]Generating {num_patients} test patients...[/cyan]")

    if not generate_test_patients(num_patients):
        console.print("[red]Failed to generate test patients. Aborting demo.[/red]")
        return

    bank = load_bank()
    if not bank:
        console.print("[yellow]No patient bank found. Generating 1000 patients...[/yellow]")
        if not generate_test_patients(1000):
            console.print("[red]Failed to generate patients. Exiting.[/red]")
            return
        bank = load_bank()
        if not bank:
            console.print("[red]Failed to load generated patients. Exiting.[/red]")
            return

    test_patients = bank[:num_patients]
    orchestrator = IntakeOrchestrator()
    incident_reporter = IncidentDashboardReporter()

    console.print(f"\n[cyan]Processing {len(test_patients)} generated patients...[/cyan]")

    for i, patient in enumerate(test_patients, 1):
        console.print(f"\n[bold cyan]--- Patient #{i}: {patient['resident_name']} ---[/bold cyan]")
        console.print(f"[dim]State: {patient['state']}[/dim]")
        console.print(f"[dim]Clinical notes: {patient['clinical_notes'][:80]}...[/dim]")

        result = orchestrator.run(patient)
        print_intake_result(result, f"Generated patient #{i}")
        time.sleep(1)

    console.print(f"\n[bold green]✓ Processed {len(test_patients)} generated patients[/bold green]")


# ---------------------------------------------------------------------------
# LIVE SERVICE MODE — reads from patient_bank.json
# ---------------------------------------------------------------------------
def load_bank():
    """Load the patient bank from JSON file"""
    if not os.path.exists(BANK_FILE):
        console.print(f"[red]Error: {BANK_FILE} not found. Run factory.py first.[/red]")
        return []
    try:
        with open(BANK_FILE) as f:
            return json.load(f)
    except json.JSONDecodeError:
        console.print(f"[red]Error: {BANK_FILE} contains invalid JSON.[/red]")
        return []




# ---------------------------------------------------------------------------
# INCIDENT DASHBOARD REPORTER
# ---------------------------------------------------------------------------
class IncidentDashboardReporter:
    """Format incident audit data for dashboard display."""
    
    def __init__(self):
        self.last_audit = None
    
    def display(self, audit):
        """Return formatted incident data for dashboard panel."""
        if not audit:
            return {
                "classification": "None",
                "confidence": 0.0,
                "escalated": "No",
                "loop_iterations": 0,
                "converged": "No",
                "audit_id": "—",
                "status": "pending"
            }
        
        return {
            "classification": audit.classification.category if audit.classification else "Unknown",
            "confidence": audit.classification.confidence if audit.classification else 0.0,
            "escalated": "Yes" if audit.escalated_to_human else "No",
            "loop_iterations": audit.loop_iterations,
            "converged": "Yes" if audit.converged else "No",
            "audit_id": audit.incident_id[:8] + "…" if audit.incident_id else "—",
            "status": audit.status
        }

def append_to_audit(patient, result):
    """Append one patient result to the live audit file"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "patient": patient["resident_name"],
        "state": patient["state"],
        "status": result.overall_status if result else "failed",
        "medical_summary": getattr(result.medical, "summary", "No medical summary available") if result.medical else "No medical summary available",
        "compliance": "Compliant" if result and result.compliance and result.compliance.compliant else "Non-compliant",
        "welcome": getattr(result.family_welcome, "welcome_message", "Welcome message pending") if result.family_welcome else "Welcome message pending"
    }

    if os.path.exists(LIVE_AUDIT_FILE):
        try:
            with open(LIVE_AUDIT_FILE) as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = []
    else:
        data = []

    data.append(entry)

    with open(LIVE_AUDIT_FILE, "w") as f:
        json.dump(data, f, indent=2)

    return entry


# ---------------------------------------------------------------------------
# LIVE SERVICE DASHBOARD — stakeholder view
# ---------------------------------------------------------------------------
def run_live_service(target_count=None):
    """Run the live service — stakeholder dashboard view"""
    from collections import defaultdict

    metrics = {
        "total_processed": 0,
        "compliant": 0,
        "non_compliant": 0,
        "complete": 0,
        "partial": 0,
        "failed": 0,
        "incidents": 0,
        "incidents_fall": 0,
        "incidents_medication_error": 0,
        "incidents_other": 0,
        "start_time": datetime.now(),
        "last_patient": None,
        "last_patient_dob": None,
        "last_patient_state": None,
        "last_incident": None,
        "last_compliance_status": "Unknown",
        "last_missing_forms": [],
        "staff_on_shift": 8,
        "patients_on_site": 24,
        "patients_per_staff": 3.0,
        "doctors_on_shift": 2,
        "intakes_today": 12,
        "discharges_today": 4,
        "net_occupancy": 20,
        "avg_los": 14.5,
        "staff_compliance_pct": 98.5,
        "regulatory_breaches": 0
    }

    console.print(Panel.fit(
        "[bold green]GUARDIAN CRM 2 — LIVE DASHBOARD[/bold green]\n"
        f"[dim]Mode: {'Processing ' + str(target_count) + ' patients' if target_count else 'Running continuously'}[/dim]\n"
        f"[dim]Audit log: {LIVE_AUDIT_FILE}[/dim]\n"
        "[dim]Press Ctrl+C to stop[/dim]",
        border_style="bold green",
    ))

    bank = load_bank()
    if not bank:
        console.print("[yellow]Generating patient bank...[/yellow]")
        if not generate_test_patients(50):
            console.print("[red]Failed to generate patients. Exiting.[/red]")
            return
        bank = load_bank()
        if not bank:
            console.print("[red]Failed to load generated patients. Exiting.[/red]")
            return

    orchestrator = IntakeOrchestrator()
    incident_reporter = IncidentDashboardReporter()
    patient_count = 0

    try:
        while True:
            if target_count and patient_count >= target_count:
                console.print(f"\n[bold green]✓ Completed target of {target_count} patients.[/bold green]")
                break

            if patient_count >= len(bank):
                patient_count = 0
                console.print("[yellow]Patient bank exhausted. Generating 1000 new patients...[/yellow]")
                if not generate_test_patients(1000):
                    console.print("[red]Failed to generate new patients. Exiting.[/red]")
                    break
                bank = load_bank()
                if not bank:
                    console.print("[red]Failed to load generated patients. Exiting.[/red]")
                    break

            patient = bank[patient_count]
            patient_count += 1
            metrics["total_processed"] += 1
            metrics["last_patient"] = patient['resident_name']
            metrics["last_patient_dob"] = patient.get('dob', '—')
            metrics["last_patient_state"] = patient.get('state', '—')

            result = orchestrator.run(patient)

            if result and result.compliance:
                metrics['last_compliance_status'] = "Compliant" if result.compliance.compliant else "Non-compliant"
                metrics['last_missing_forms'] = result.compliance.missing_forms
            else:
                metrics['last_compliance_status'] = "Unknown"
                metrics['last_missing_forms'] = []

            append_to_audit(patient, result)

            if result and result.overall_status == "complete":
                metrics["complete"] += 1
            elif result and result.overall_status == "partial":
                metrics["partial"] += 1
            else:
                metrics["failed"] += 1

            if result and result.compliance and result.compliance.compliant:
                metrics["compliant"] += 1
            else:
                metrics["non_compliant"] += 1

            if random.random() < 0.15:
                incident_type = random.choice(["fall", "medication_error", "other"])
                
                # Build incident data
                incident_data = {
                    "state": patient.get("state", "CA"),
                    "narrative": f"Resident {patient['resident_name']} experienced a {incident_type.replace('_', ' ')} incident.",
                    "resident_name": patient["resident_name"],
                    "nurse_name": "Nurse On Duty",
                    "nurse_last_training": "2025-06-01",
                    "nurse_hours_today": 8.0,
                    "doctor_on_shift": True,
                    "doctor_on_call": True
                }
                
                # Run incident workflow
                audit = IncidentWorkflow().run(incident_data)
                incident_display = incident_reporter.display(audit)
                
                metrics["incidents"] += 1
                metrics[f"incidents_{incident_type}"] = metrics.get(f"incidents_{incident_type}", 0) + 1
                metrics["last_incident"] = incident_type.replace('_', ' ').title()
                metrics["last_incident_patient"] = metrics["last_patient"]
                metrics["last_incident_narrative"] = incident_data["narrative"]
                metrics["last_incident_action"] = "Resident assessed by on-site nurse. Vitals stable. Incident logged."
                metrics["last_incident_classification"] = incident_display["classification"]
                metrics["last_incident_confidence"] = incident_display["confidence"]
                metrics["last_incident_escalated"] = incident_display["escalated"]
                metrics["last_incident_loop_iterations"] = incident_display["loop_iterations"]
                metrics["last_incident_converged"] = incident_display["converged"]
                metrics["last_incident_audit_id"] = incident_display["audit_id"]
                metrics["last_incident_status"] = incident_display["status"]

            os.system('clear' if os.name == 'posix' else 'cls')

            runtime = datetime.now() - metrics["start_time"]
            hours = runtime.total_seconds() / 3600
            patients_per_hour = metrics["total_processed"] / hours if hours > 0 else 0

            console.print(Panel.fit(
    "[bold green]GUARDIAN CRM 2 — LIVE DASHBOARD[/bold green]\n"
    f"[dim]Updated: 2026-08-13 {datetime.now().strftime('%H:%M:%S')}[/dim]",
    border_style="bold green",
))
            # Box 1: Patient Intake - DETAILE
            from rich.layout import Layout

            # Create the 4 panels
            panel1 = Panel(
                f"[bold cyan]PATIENT INTAKE[/bold cyan]\n\n"
                f"[bold]Name:[/bold] [white]{metrics['last_patient'] or '—'}[/white]\n"
                f"[bold]DOB:[/bold] [dim]{metrics['last_patient_dob']}[/dim]\n"
                f"[bold]State:[/bold] [dim]{metrics['last_patient_state']}[/dim]\n"
                f"[bold]Doctor:[/bold] [dim]Dr. On Call[/dim]\n"
                f"[bold]Regulatory check:[/bold] {metrics['last_compliance_status']}\n"
                f"[bold]Welcome pack:[/bold] [green]SENT[/green]\n\n"
                f"[bold]Staff on shift:[/bold] [cyan]{metrics['staff_on_shift']}[/cyan]\n"
                f"[bold]Patients on site:[/bold] [cyan]{metrics['patients_on_site']}[/cyan]",
                border_style="cyan",
                padding=(1, 2),
            )

            panel2 = Panel(
                f"[bold red]COMPLAINTS & INCIDENTS[/bold red]\n\n"
                f"[bold]Last incident:[/bold] [dim]{metrics.get('last_incident', 'None')}[/dim]\n"
                f"[bold]Patient:[/bold] [white]{metrics.get('last_incident_patient', '—')}[/white]\n"
                f"[bold]Classification:[/bold] [yellow]{metrics.get('last_incident_classification', '—')}[/yellow]\n"
                f"[bold]Confidence:[/bold] [dim]{metrics.get('last_incident_confidence', 0):.0%}[/dim]\n"
                f"[bold]Escalated:[/bold] [red]{metrics.get('last_incident_escalated', '—')}[/red]\n"
                f"[bold]Loop iterations:[/bold] [dim]{metrics.get('last_incident_loop_iterations', 0)}[/dim]\n"
                f"[bold]Converged:[/bold] [green]{metrics.get('last_incident_converged', '—')}[/green]\n"
                f"[bold]Audit ID:[/bold] [dim]{metrics.get('last_incident_audit_id', '—')}[/dim]\n"
                f"[bold]Status:[/bold] {metrics.get('last_incident_status', '—')}\n\n"
                f"[bold]Total incidents:[/bold] [red]{metrics['incidents']}[/red]\n"
                f"[bold]Fall:[/bold] [yellow]{metrics.get('incidents_fall', 0)}[/yellow]\n"
                f"[bold]Med error:[/bold] [yellow]{metrics.get('incidents_medication_error', 0)}[/yellow]\n"
                f"[bold]Other:[/bold] [yellow]{metrics.get('incidents_other', 0)}[/yellow]",
                border_style="red",
                padding=(1, 2),
            )

            panel3 = Panel(
                f"[bold yellow]INTAKE & STAFFING FLOW[/bold yellow]\n\n"
                f"[bold]Total intakes:[/bold] [cyan]{metrics['total_processed']}[/cyan]\n"
                f"[bold]Complete:[/bold] [green]{metrics['complete']}[/green]\n"
                f"[bold]Partial:[/bold] [yellow]{metrics['partial']}[/yellow]\n"
                f"[bold]Failed:[/bold] [red]{metrics['failed']}[/red]\n\n"
                f"[bold]Staff on shift:[/bold] [cyan]{metrics['staff_on_shift']}[/cyan]\n"
                f"[bold]Patients per staff:[/bold] [cyan]{metrics['patients_per_staff']:.1f}[/cyan]\n"
                f"[bold]Doctors on shift:[/bold] [green]{metrics['doctors_on_shift']}[/green]\n"
                f"[bold]Processing rate:[/bold] [yellow]{patients_per_hour:.1f}[/yellow]/hour",
                border_style="yellow",
                padding=(1, 2),
            )

            panel4 = Panel(
                f"[bold magenta]REAL-TIME FLOW[/bold magenta]\n\n"
                f"[bold]Last refreshed:[/bold] [dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]\n\n"
                f"[bold]Intakes:[/bold] [cyan]{metrics['intakes_today']}[/cyan]\n"
                f"[bold]Discharges:[/bold] [cyan]{metrics['discharges_today']}[/cyan]\n"
                f"[bold]Net occupancy:[/bold] [white]{metrics['net_occupancy']}[/white]\n"
                f"[bold]Avg length of stay:[/bold] [dim]{metrics['avg_los']} days[/dim]\n\n"
                f"[bold]Staff compliance:[/bold] [green]{metrics['staff_compliance_pct']:.1f}%[/green]\n"
                f"[bold]Safety incidents:[/bold] [red]{metrics['incidents']}[/red]",
                border_style="magenta",
                padding=(1, 2),
            )

            # Use Layout to put them side by side
            layout = Layout()
            layout.split_column(
                Layout(name="row1"),
                Layout(name="row2"),
            )
            layout["row1"].split_row(panel1, panel2)
            layout["row2"].split_row(panel3, panel4)

            console.print(layout)

            time.sleep(PROCESSING_SPEED)

    except KeyboardInterrupt:
        console.print("\n\n[bold yellow]✓ Dashboard stopped by user.[/bold yellow]")

    finally:
        if metrics["total_processed"] > 0:
            compliant_pct = metrics["compliant"] / metrics["total_processed"] * 100
        else:
            compliant_pct = 0.0

        console.print(f"\n[bold]FINAL SUMMARY[/bold]")
        console.print(f"  • Total patients processed: {metrics['total_processed']}")
        console.print(f"  • Compliant: {metrics['compliant']} ({compliant_pct:.1f}%)")
        console.print(f"  • Incidents reported: {metrics['incidents']}")
        console.print(f"  • Audit log saved to: {LIVE_AUDIT_FILE}")


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Guardian CRM - AI Layer for Residential Care Facilities"
    )
    parser.add_argument(
        "--mode",
        type=int,
        choices=[1, 2],
        default=2,
        help="Run mode: 1=demo (6-step fixed demo + generated patients), 2=live service (process patient bank)"
    )
    parser.add_argument(
        "--count",
        type=int,
        help="Number of patients to process in live mode (default: process all, then loop)"
    )
    parser.add_argument(
        "--demo-patients",
        type=int,
        default=5,
        help="Number of test patients to generate for demo mode (default: 5)"
    )
    parser.add_argument(
        "--skip-fixed-demos",
        action="store_true",
        help="Skip the original 6-step fixed demos and only process generated patients"
    )
    args = parser.parse_args()

    console.print(Panel.fit(
        f"[bold]Guardian CRM[/bold]\n"
        f"[dim]Mode: {'Demo' if args.mode == 1 else 'Live Service'}[/dim]\n"
        f"[dim]Press Ctrl+C to stop[/dim]",
        border_style="bold blue",
    ))

    if args.mode == 1:
        if DEMO_GENERATE_PATIENTS and args.demo_patients > 0:
            demo_with_generated_patients(args.demo_patients)
            time.sleep(2)

        if not args.skip_fixed_demos:
            console.print(f"\n[bold cyan]=== ORIGINAL 6-STEP DEMOS ===[/bold cyan]")
            demo_intake_clean()
            time.sleep(2)
            demo_intake_partial_failure()
            time.sleep(2)
            demo_retry_recovery()
            time.sleep(2)
            demo_timeout_fallback()
            time.sleep(2)
            demo_incident_converges()
            time.sleep(2)
            demo_incident_escalates()

        console.print()
        console.rule("[bold green]DEMO DONE[/bold green]")

    elif args.mode == 2:
        run_live_service(target_count=args.count)

    else:
        console.print("[red]Invalid mode. Use --mode 1 or --mode 2.[/red]")
        sys.exit(1)
