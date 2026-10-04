"""Bounded arithmetic over already verified, available canonical business metrics."""

import re
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Any


@dataclass(frozen=True)
class MetricOperand:
    label: str
    unit: str
    value: Decimal


def metric_operand(metric: Any) -> MetricOperand | None:
    if (
        not isinstance(metric, dict)
        or not {"code", "label", "value", "unit", "available", "source"}.issubset(metric)
        or not isinstance(metric["code"], str)
        or metric.get("available") is not True
    ):
        return None
    label, unit, value = metric.get("label"), metric.get("unit"), metric.get("value")
    if not isinstance(label, str) or not 1 <= len(label) <= 240:
        return None
    if (
        not isinstance(unit, str)
        or unit not in {"COUNT", "AMOUNT", "PERCENT"}
        or isinstance(value, bool)
    ):
        return None
    if not isinstance(value, str | int | float):
        return None
    text = str(value)
    if not re.fullmatch(r"-?\d{1,30}(?:\.\d{1,18})?", text):
        return None
    number = Decimal(text)
    if unit == "COUNT" and number != number.to_integral_value():
        return None
    return MetricOperand(label, unit, number)


def verified_calculations(payload: Any, operands: dict[int, MetricOperand]) -> list[str]:
    """The model selects an operation; this function computes every displayed result."""
    if not isinstance(payload, list) or not 1 <= len(payload) <= 8:
        raise ValueError("Calculations must be bounded")
    lines = []
    for item in payload:
        if not isinstance(item, dict) or set(item) != {"operation", "claim_indices"}:
            raise ValueError("Invalid calculation shape")
        operation, indices = item["operation"], item["claim_indices"]
        if not isinstance(operation, str) or operation not in {
            "SUM",
            "DIFFERENCE",
            "RATIO",
            "PERCENT_CHANGE",
        }:
            raise ValueError("Unsupported operation")
        if not isinstance(indices, list) or not 2 <= len(indices) <= 8:
            raise ValueError("Invalid operand count")
        if any(type(index) is not int or index not in operands for index in indices):
            raise ValueError("Only current verified available metric values can be operands")
        if len(set(indices)) != len(indices):
            raise ValueError("An operand cannot be counted twice")
        selected = [operands[index] for index in indices]
        if len({operand.unit for operand in selected}) != 1:
            raise ValueError("Metric units cannot be mixed")
        if operation != "SUM" and len(selected) != 2:
            raise ValueError("Binary operation requires two operands")
        values = [operand.value for operand in selected]
        unit = selected[0].unit
        with localcontext() as context:
            context.prec = 80
            if operation == "SUM":
                result, title, symbol = sum(values, Decimal(0)), "Jumlah", " + "
            elif operation == "DIFFERENCE":
                result, title, symbol = values[0] - values[1], "Selisih", " - "
            elif operation == "RATIO":
                if values[1] == 0:
                    raise ValueError("Ratio denominator is zero")
                result, title, symbol = values[0] / values[1], "Rasio", " / "
                unit = "RATIO"
            else:
                if values[1] <= 0:
                    raise ValueError("Percentage change requires a positive baseline")
                result = (values[0] - values[1]) / values[1] * 100
                title, symbol, unit = "Perubahan", " dibanding ", "PERCENT"
            rounded = result.quantize(Decimal("0.000001"))
        display = format(rounded, "f").rstrip("0").rstrip(".")
        if rounded == 0:
            display = "0"
        suffix = "%" if unit == "PERCENT" else " kali" if unit == "RATIO" else ""
        prefix = "Rp " if unit == "AMOUNT" else ""
        formula = symbol.join(operand.label for operand in selected)
        lines.append(f"{title} ({formula}): {prefix}{display}{suffix}.")
    return lines
