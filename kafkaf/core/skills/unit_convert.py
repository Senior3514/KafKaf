import re

from kafkaf.core.skills.base import Skill

_LENGTH_TO_METERS = {
    "m": 1, "meter": 1, "meters": 1,
    "km": 1000, "kilometer": 1000, "kilometers": 1000,
    "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01,
    "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001,
    "mi": 1609.344, "mile": 1609.344, "miles": 1609.344,
    "yd": 0.9144, "yard": 0.9144, "yards": 0.9144,
    "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
    "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
}  # fmt: skip

_WEIGHT_TO_KG = {
    "kg": 1, "kilogram": 1, "kilograms": 1,
    "g": 0.001, "gram": 0.001, "grams": 0.001,
    "mg": 0.000001, "milligram": 0.000001, "milligrams": 0.000001,
    "lb": 0.453592, "lbs": 0.453592, "pound": 0.453592, "pounds": 0.453592,
    "oz": 0.0283495, "ounce": 0.0283495, "ounces": 0.0283495,
}  # fmt: skip

_PARSE_RE = re.compile(r"^\s*(-?[\d.]+)\s*([a-zA-Z°]+)\s*(?:to|in|->)\s*([a-zA-Z°]+)\s*$")

_TEMP_UNITS = {"c", "celsius", "f", "fahrenheit", "k", "kelvin"}


def _convert_temperature(value: float, from_unit: str, to_unit: str) -> float | None:
    if from_unit not in _TEMP_UNITS or to_unit not in _TEMP_UNITS:
        return None

    if from_unit.startswith("f"):
        celsius = (value - 32) * 5 / 9
    elif from_unit.startswith("k"):
        celsius = value - 273.15
    else:
        celsius = value

    if to_unit.startswith("f"):
        return celsius * 9 / 5 + 32
    if to_unit.startswith("k"):
        return celsius + 273.15
    return celsius


class UnitConvertSkill(Skill):
    name = "unit_convert"
    description = "Convert a value between units, e.g. '10 km to miles' or '100 f to c'."

    async def run(self, arg: str) -> str:
        match = _PARSE_RE.match(arg)
        if not match:
            return "error: expected format '<value> <unit> to <unit>', e.g. '10 km to miles'"

        value = float(match.group(1))
        from_unit, to_unit = match.group(2).lower(), match.group(3).lower()

        temp_result = _convert_temperature(value, from_unit, to_unit)
        if temp_result is not None:
            return f"{temp_result:.4g}"

        for table in (_LENGTH_TO_METERS, _WEIGHT_TO_KG):
            if from_unit in table and to_unit in table:
                base = value * table[from_unit]
                return f"{base / table[to_unit]:.6g}"

        return f"error: unsupported or mismatched units: {from_unit!r} -> {to_unit!r}"
