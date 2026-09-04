
#!/usr/bin/env python3
"""
Factory — Only creates/refills the patient bank.
- Generates realistic patients with controlled failure rates
"""

import json
import os
import sys
import random
import subprocess

# --- CONFIGURATION ---
BANK_FILE = "patient_bank.json"
DEFAULT_COUNT = 1000

# --- TUNE THESE RATIOS ---
# Total should equal 1.0 (100%)
RATIO_COMPLETE = 0.75    # 70% - Normal patients
RATIO_PARTIAL = 0.15     # 20% - Missing forms (Partial)
RATIO_FAILED = 0.10      # 10% - Missing critical data (Failed)
# --- END TUNE ---

# --- DATA POOLS ---
FIRST_NAMES = [
    "Eleanor", "John", "Maria", "Robert", "James", "Patricia", "Michael", "Linda",
    "William", "Barbara", "David", "Elizabeth", "Richard", "Jennifer", "Thomas",
    "Susan", "Charles", "Margaret", "Joseph", "Dorothy", "Christopher", "Nancy",
    "Daniel", "Karen", "Matthew", "Betty", "Anthony", "Lisa", "Mark", "Sandra"
]

LAST_NAMES = [
    "Whitfield", "Smith", "Garcia", "Johnson", "Williams", "Brown", "Jones",
    "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson",
    "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez"
]

STATES = ["CA", "TX", "FL", "NY", "IL", "PA", "OH", "GA", "NC", "MI"]

STREETS = [
    "Oak Street", "Pine Road", "Maple Drive", "Elm Avenue", "Cedar Lane",
    "Birch Court", "Spruce Way", "Willow Circle", "Ash Street", "Walnut Place"
]

CITIES = {
    "CA": ["Los Angeles", "San Francisco", "San Diego", "Sacramento"],
    "TX": ["Dallas", "Houston", "Austin", "San Antonio"],
    "FL": ["Miami", "Orlando", "Tampa", "Jacksonville"],
    "NY": ["New York", "Buffalo", "Rochester", "Albany"],
    "IL": ["Chicago", "Springfield", "Peoria", "Naperville"],
    "PA": ["Philadelphia", "Pittsburgh", "Allentown", "Erie"],
    "OH": ["Columbus", "Cleveland", "Cincinnati", "Toledo"],
    "GA": ["Atlanta", "Savannah", "Augusta", "Macon"],
    "NC": ["Charlotte", "Raleigh", "Greensboro", "Durham"],
    "MI": ["Detroit", "Grand Rapids", "Warren", "Sterling Heights"]
}

MOBILITY_LEVELS = [
    "ambulatory_independent", "ambulatory_with_cane", "ambulatory_with_walker",
    "wheelchair", "bedbound"
]

TRAVEL_OPTIONS = ["car", "bus", "van", "wheelchair_accessible_van", "no_travel"]

CONDITIONS = [
    "hypertension", "type 2 diabetes", "osteoarthritis", "heart failure",
    "COPD", "dementia", "depression", "anxiety", "osteoporosis",
    "atrial fibrillation", "chronic kidney disease", "hypothyroidism",
    "peripheral neuropathy", "glaucoma", "macular degeneration", "hearing loss"
]

MEDICATIONS = [
    "lisinopril", "metformin", "amlodipine", "atorvastatin", "aspirin",
    "acetaminophen", "ibuprofen", "sertraline", "gabapentin", "omeprazole",
    "simvastatin", "metoprolol", "losartan", "hydrochlorothiazide", "levothyroxine"
]

COGNITIVE_STATUSES = ["intact", "mild_impairment", "moderate_impairment", "severe_impairment"]

RISK_FLAGS_POOL = [
    "fall_risk_mild", "fall_risk_moderate", "fall_risk_high",
    "medication_interaction_risk", "cognitive_decline_risk",
    "nutritional_risk", "social_isolation_risk", "polypharmacy_risk"
]


def generate_complete_patient():
    """Generate a normal patient with all data."""
    return generate_random_patient()


def generate_partial_patient():
    """Generate a patient with missing forms (Partial)."""
    patient = generate_random_patient()
    patient["resident_name"] = f"⚠️ PARTIAL - {patient['resident_name']}"
    # Remove some forms to cause partial failure
    if "medication_authorization" in patient["submitted_forms"]:
        patient["submitted_forms"].remove("medication_authorization")
    return patient


def generate_failed_patient():
    """Generate a patient with missing critical data (Failed)."""
    patient = generate_random_patient()
    missing_type = random.choice(['clinical_notes', 'state', 'dob'])
    if missing_type == 'clinical_notes':
        patient["clinical_notes"] = ""
        patient["resident_name"] = f"⚠️ FAILED - {patient['resident_name']} (No Notes)"
    elif missing_type == 'state':
        patient["state"] = ""
        patient["resident_name"] = f"⚠️ FAILED - {patient['resident_name']} (No State)"
    elif missing_type == 'dob':
        patient["dob"] = ""
        patient["resident_name"] = f"⚠️ FAILED - {patient['resident_name']} (No DOB)"
    return patient


def generate_random_patient():
    """Generate one random patient with full health/mobility data"""
    state = random.choice(STATES)
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    name = f"{first} {last}"
    
    age = random.randint(65, 95)
    year = 2026 - age
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    dob = f"{year:04d}-{month:02d}-{day:02d}"
    
    street_num = random.randint(100, 9999)
    street = random.choice(STREETS)
    city = random.choice(CITIES[state])
    zip_code = f"{random.randint(10000, 99999)}"
    address = f"{street_num} {street}, {city}, {state} {zip_code}"
    
    num_conditions = random.randint(1, 4)
    conditions = random.sample(CONDITIONS, num_conditions)
    
    num_meds = random.randint(1, 5)
    meds = random.sample(MEDICATIONS, num_meds)
    
    clinical_notes = f"{age}-year-old {random.choice(['male', 'female'])}, " + \
                     f"history of {', '.join(conditions)}. " + \
                     f"Medications: {', '.join(meds)}. "
    
    if random.random() > 0.5:
        clinical_notes += "No known drug allergies. "
    if random.random() > 0.3:
        clinical_notes += f"{random.choice(['Mild', 'Moderate', 'Severe'])} fall risk noted. "
    
    mobility = random.choice(MOBILITY_LEVELS)
    travel = random.choice(TRAVEL_OPTIONS)
    
    cognition = random.choice(COGNITIVE_STATUSES)
    if cognition != "intact":
        clinical_notes += f"Cognitive status: {cognition.replace('_', ' ')}. "
    
    height_inches = random.randint(58, 72)
    weight_lbs = random.randint(100, 250)
    height_ft = height_inches // 12
    height_in = height_inches % 12
    height_str = f"{height_ft}'{height_in}\""
    
    num_risks = random.randint(0, 3)
    risk_flags = random.sample(RISK_FLAGS_POOL, min(num_risks, len(RISK_FLAGS_POOL)))
    
    required_forms = ["admission_agreement", "care_plan", "medication_authorization"]
    optional_forms = ["emergency_contact", "advance_directive", "dental_consent"]
    submitted_forms = required_forms.copy()
    num_optional = random.randint(0, 2)
    if num_optional > 0:
        submitted_forms += random.sample(optional_forms, num_optional)
    
    staff_ratio = "1:4" if state == "CA" else "1:5" if state in ["TX", "FL"] else "1:6"
    
    family_names = ["Robert", "Mary", "Carlos", "Jennifer", "David", "Susan"]
    family_last = last
    family_name = f"{random.choice(family_names)} {family_last}"
    family_phone = f"555-{random.randint(100,999)}-{random.randint(1000,9999)}"
    family_email = f"{family_name.lower().replace(' ', '.')}@example.com"
    
    return {
        "resident_name": name,
        "dob": dob,
        "state": state,
        "address": address,
        "height": height_str,
        "weight": weight_lbs,
        "mobility": mobility,
        "travel": travel,
        "clinical_notes": clinical_notes.strip(),
        "medications": meds,
        "cognition": cognition,
        "risk_flags": risk_flags,
        "submitted_forms": submitted_forms,
        "staff_ratio": staff_ratio,
        "family_name": family_name,
        "family_phone": family_phone,
        "family_email": family_email,
        "last_processed": None,
        "times_processed": 0
    }


def generate_test_patients(count: int) -> bool:
    """Generate test patients using factory.py"""
    print(f"[cyan]Generating {count} test patients...[/cyan]")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    factory_path = os.path.join(script_dir, "factory.py")
    if not os.path.exists(factory_path):
        print(f"[red]Error: factory.py not found in: {factory_path}[/red]")
        return False
    try:
        result = subprocess.run(
            [sys.executable, factory_path, "--count", str(count)],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"[red]Error running factory: {result.stderr}[/red]")
            return False
        print(f"[green]✓ Generated {count} test patients[/green]")
        return True
    except Exception as e:
        print(f"[red]Failed to run factory: {e}[/red]")
        return False


def main(count=DEFAULT_COUNT):
    """Generate and save the patient bank with controlled ratios."""
    print(f"\n{'='*60}")
    print(f"FACTORY — Generating {count} patients")
    print(f"  Complete: {RATIO_COMPLETE*100:.0f}%  (normal)")
    print(f"  Partial:  {RATIO_PARTIAL*100:.0f}%   (missing forms)")
    print(f"  Failed:   {RATIO_FAILED*100:.0f}%   (missing critical data)")
    print(f"{'='*60}")
    
    bank = []
    complete_count = int(count * RATIO_COMPLETE)
    partial_count = int(count * RATIO_PARTIAL)
    failed_count = count - complete_count - partial_count
    
    # Generate each type
    for _ in range(complete_count):
        bank.append(generate_complete_patient())
    for _ in range(partial_count):
        bank.append(generate_partial_patient())
    for _ in range(failed_count):
        bank.append(generate_failed_patient())
    
    # Shuffle so they're mixed
    random.shuffle(bank)
    
    with open(BANK_FILE, "w") as f:
        json.dump(bank, f, indent=2)
    
    print(f"\n[INFO] Created {len(bank)} patients in {BANK_FILE}")
    print(f"  • Complete: {complete_count} (normal)")
    print(f"  • Partial:  {partial_count} (missing forms)")
    print(f"  • Failed:   {failed_count} (missing critical data)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="Number of patients to generate")
    args = parser.parse_args()
    main(args.count)
