from decimal import Decimal

import pytest

from pending_klaim_rule_engine.review_form import (
    FormValidationError,
    StructuredClaimForm,
)


def test_structured_form_accepts_complete_e87_6_evidence():
    form = StructuredClaimForm.from_fields(
        {
            "diagnosis_code": "e87.6",
            "diagnosis_position": "secondary",
            "potassium_value": "2.95",
            "potassium_unit": "mmol/L",
            "potassium_reference": "Lab result, page 2",
            "kcl_injection": "true",
            "kcl_reference": "Medication record, page 4",
        }
    )

    assert form.diagnosis_code == "E87.6"
    assert form.diagnosis_position == "secondary"
    assert form.evidence_values() == {
        "potassium": Decimal("2.95"),
        "kcl_injection": True,
    }
    assert form.evidence_references()["potassium"] == "Lab result, page 2"


def test_blank_evidence_fields_remain_missing_evidence():
    form = StructuredClaimForm.from_fields({"diagnosis_code": "E87.6"})

    assert form.evidence_values() == {"potassium": None, "kcl_injection": None}


@pytest.mark.parametrize(
    "fields",
    [
        {"diagnosis_code": " "},
        {"diagnosis_code": "E87.6", "diagnosis_position": "tertiary"},
        {"diagnosis_code": "E87.6", "potassium_value": "NaN"},
        {
            "diagnosis_code": "E87.6",
            "potassium_value": "2.9",
            "potassium_unit": "mmol/L",
        },
        {"diagnosis_code": "E87.6", "kcl_injection": "yes"},
        {"diagnosis_code": "E87.6", "kcl_injection": "false"},
    ],
)
def test_structured_form_rejects_invalid_or_unreferenced_findings(fields):
    with pytest.raises(FormValidationError):
        StructuredClaimForm.from_fields(fields)