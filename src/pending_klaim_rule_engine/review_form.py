from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping


class FormValidationError(ValueError):
    pass


@dataclass(frozen=True)
class StructuredClaimForm:
    diagnosis_code: str
    diagnosis_position: str | None
    potassium_value: Decimal | None
    potassium_unit: str | None
    potassium_reference: str | None
    kcl_injection: bool | None
    kcl_reference: str | None

    @classmethod
    def from_fields(cls, fields: Mapping[str, object]) -> "StructuredClaimForm":
        diagnosis_code = _required_text(fields, "diagnosis_code").upper()
        diagnosis_position = _optional_text(fields, "diagnosis_position")
        if diagnosis_position not in (None, "primary", "secondary"):
            raise FormValidationError(
                "diagnosis_position must be 'primary' or 'secondary'"
            )

        potassium_raw = _optional_text(fields, "potassium_value")
        potassium_unit = _optional_text(fields, "potassium_unit")
        potassium_reference = _optional_text(fields, "potassium_reference")
        if potassium_raw is None:
            _reject_unpaired_fields(
                "potassium_value", potassium_unit, potassium_reference
            )
            potassium_value = None
        else:
            try:
                potassium_value = Decimal(potassium_raw)
            except InvalidOperation as error:
                raise FormValidationError("potassium_value must be numeric") from error
            if not potassium_value.is_finite():
                raise FormValidationError("potassium_value must be finite")
            if potassium_unit is None or potassium_reference is None:
                raise FormValidationError(
                    "potassium_unit and potassium_reference are required with a result"
                )

        kcl_raw = _optional_text(fields, "kcl_injection")
        kcl_reference = _optional_text(fields, "kcl_reference")
        if kcl_raw is None:
            _reject_unpaired_fields("kcl_injection", kcl_reference)
            kcl_injection = None
        else:
            normalized_kcl = kcl_raw.lower()
            if normalized_kcl not in ("true", "false"):
                raise FormValidationError("kcl_injection must be true or false")
            kcl_injection = normalized_kcl == "true"
            if kcl_reference is None:
                raise FormValidationError(
                    "kcl_reference is required with a treatment finding"
                )

        return cls(
            diagnosis_code=diagnosis_code,
            diagnosis_position=diagnosis_position,
            potassium_value=potassium_value,
            potassium_unit=potassium_unit,
            potassium_reference=potassium_reference,
            kcl_injection=kcl_injection,
            kcl_reference=kcl_reference,
        )

    def evidence_values(self) -> dict[str, object | None]:
        return {
            "potassium": self.potassium_value,
            "kcl_injection": self.kcl_injection,
        }

    def evidence_references(self) -> dict[str, str | None]:
        return {
            "potassium": self.potassium_reference,
            "kcl_injection": self.kcl_reference,
        }


def _required_text(fields: Mapping[str, object], key: str) -> str:
    value = _optional_text(fields, key)
    if value is None:
        raise FormValidationError(f"{key} is required")
    return value


def _optional_text(fields: Mapping[str, object], key: str) -> str | None:
    value = fields.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise FormValidationError(f"{key} must be text")
    normalized = value.strip()
    return normalized or None


def _reject_unpaired_fields(key: str, *related_values: str | None) -> None:
    if any(value is not None for value in related_values):
        raise FormValidationError(f"{key} is required when related fields are set")