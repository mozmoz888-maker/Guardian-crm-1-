"""Configuration for Guardian CRM system."""

# LLM Configuration
LLM_BACKEND = "mock"
LLM_MODEL = "claude-3-sonnet-20240229"

# Retry Configuration
MAX_RETRIES = 3
REQUEST_TIMEOUT = 10.0
EXPONENTIAL_BASE = 2
RETRY_JITTER_MAX_SECONDS = 0.25

# Incident Workflow Configuration
MAX_INCIDENT_LOOPS = 3

# Regulatory Rules by State
REGULATORY_RULES = {
    'CA': {
        'min_staff_ratio': '1:5',
        'required_forms': ['admission_agreement', 'care_plan', 'medication_authorization'],
        'incident_notification': {
            'fall': {'agency': 'CA Dept of Social Services - Community Care Licensing', 'hours': 24},
            'medication_error': {'agency': 'CA Dept of Social Services - Community Care Licensing', 'hours': 24},
            'elopement': {'agency': 'CA Dept of Social Services - Community Care Licensing', 'hours': 24},
            'abuse_allegation': {'agency': 'Adult Protective Services + CCLD', 'hours': 24},
            'death': {'agency': 'CA Dept of Social Services - Community Care Licensing', 'hours': 24},
            'other': {'agency': 'CA Dept of Social Services - Community Care Licensing', 'hours': 72}
        }
    },
    'TX': {
        'min_staff_ratio': '1:6',
        'required_forms': ['admission_agreement', 'care_plan'],
        'incident_notification': {
            'fall': {'agency': 'TX Health and Human Services - HHSC', 'hours': 24},
            'medication_error': {'agency': 'TX Health and Human Services - HHSC', 'hours': 24},
            'elopement': {'agency': 'TX Health and Human Services - HHSC', 'hours': 24},
            'abuse_allegation': {'agency': 'TX Adult Protective Services + HHSC', 'hours': 24},
            'death': {'agency': 'TX Health and Human Services - HHSC', 'hours': 24},
            'other': {'agency': 'TX Health and Human Services - HHSC', 'hours': 72}
        }
    },
    'IL': {
        'min_staff_ratio': '1:5',
        'required_forms': ['admission_agreement', 'care_plan', 'medication_authorization'],
        'incident_notification': {
            'fall': {'agency': 'IL Department of Public Health', 'hours': 24},
            'medication_error': {'agency': 'IL Department of Public Health', 'hours': 24},
            'elopement': {'agency': 'IL Department of Public Health', 'hours': 24},
            'abuse_allegation': {'agency': 'IL Adult Protective Services', 'hours': 24},
            'death': {'agency': 'IL Department of Public Health', 'hours': 24},
            'other': {'agency': 'IL Department of Public Health', 'hours': 72}
        }
    },
    'FL': {
        'min_staff_ratio': '1:6',
        'required_forms': ['admission_agreement', 'care_plan'],
        'incident_notification': {
            'fall': {'agency': 'FL Agency for Health Care Administration', 'hours': 24},
            'medication_error': {'agency': 'FL Agency for Health Care Administration', 'hours': 24},
            'elopement': {'agency': 'FL Agency for Health Care Administration', 'hours': 24},
            'abuse_allegation': {'agency': 'FL Adult Protective Services', 'hours': 24},
            'death': {'agency': 'FL Agency for Health Care Administration', 'hours': 24},
            'other': {'agency': 'FL Agency for Health Care Administration', 'hours': 72}
        }
    }
}
