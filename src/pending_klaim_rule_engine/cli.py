from collections.abc import Callable

from sqlalchemy.orm import Session

from pending_klaim_rule_engine.database import create_database_engine
from pending_klaim_rule_engine.review_form import StructuredClaimForm
from pending_klaim_rule_engine.review_service import (
    evaluate_claim,
    format_review_report,
)
from pending_klaim_rule_engine.rule_lifecycle import get_active_rule_version


def collect_review_form(
    input_fn: Callable[[str], str] | None = None,
    *,
    diagnosis_code: str | None = None,
    position_required: bool = False,
) -> StructuredClaimForm:
    if input_fn is None:
        input_fn = input

    fields: dict[str, str] = {
        "diagnosis_code": diagnosis_code or input_fn("Kode diagnosis yang ditelaah: "),
    }
    if position_required:
        fields["diagnosis_position"] = input_fn(
            "Posisi diagnosis (primary/secondary): "
        )
    fields["potassium_value"] = input_fn(
        "Nilai kalium, kosong bila tidak ditemukan: "
    )
    if fields["potassium_value"].strip():
        fields["potassium_unit"] = input_fn("Satuan nilai kalium: ")
        fields["potassium_reference"] = input_fn("Rujukan bukti kalium: ")

    fields["kcl_injection"] = input_fn(
        "Terapi injeksi KCl? (ya/tidak, kosong bila tidak ditemukan): "
    )
    if fields["kcl_injection"].strip():
        answer = fields["kcl_injection"].strip().lower()
        if answer in ("ya", "tidak"):
            fields["kcl_injection"] = "true" if answer == "ya" else "false"
        fields["kcl_reference"] = input_fn("Rujukan bukti terapi KCl: ")

    return StructuredClaimForm.from_fields(fields)


def run_review_cli(
    input_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], None] = print,
) -> None:
    if input_fn is None:
        input_fn = input
    diagnosis_code = input_fn("Kode diagnosis yang ditelaah: ")
    engine = create_database_engine()
    try:
        with Session(engine) as session:
            active_version = get_active_rule_version(session, diagnosis_code.strip().upper())
            position_required = bool(
                active_version
                and any(
                    criterion.get("type") == "position_equals"
                    for criterion in active_version.criteria
                )
            )
            form = collect_review_form(
                input_fn,
                diagnosis_code=diagnosis_code,
                position_required=position_required,
            )
            report = evaluate_claim(session, form)
            session.commit()
        output_fn(format_review_report(report))
    finally:
        engine.dispose()