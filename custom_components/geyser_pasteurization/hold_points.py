"""Time-temperature hold table for the Geyser Pasteurization integration.

Legionella die off much faster at higher temperatures, so a hotter hold
needs less time. The table pairs a temperature with the hold time that
counts as a full pasteurization at or above it. The base row is the
configured target temperature and required duration; any additional rows
must be hotter and shorter.

Progress is tracked as a fraction: each interval spent at temperature T
contributes `interval / required_seconds(T)`, and the cycle completes once
the fraction reaches 1.0. `required_seconds` uses the hottest row that T
reaches (a step function, never interpolated), so the result always rounds
in the safe direction.
"""

from __future__ import annotations

import re

HoldPoint = tuple[float, float]  # (temperature °C, minutes)

_SEPARATORS = re.compile(r"[,;\n]+")


def parse_hold_points(text: str | None) -> list[HoldPoint]:
    """Parse "65:2, 70:1" into [(65.0, 2.0), (70.0, 1.0)].

    Raises ValueError for anything that isn't a list of positive
    temperature:minutes pairs. An empty or blank string is an empty list.
    """
    points: list[HoldPoint] = []
    for raw in _SEPARATORS.split(text or ""):
        item = raw.strip()
        if not item:
            continue
        temp_str, sep, minutes_str = item.partition(":")
        if not sep:
            raise ValueError(f"Expected temperature:minutes, got {item!r}")
        temp = float(temp_str)
        minutes = float(minutes_str)
        if temp <= 0 or minutes <= 0:
            raise ValueError(f"Temperature and minutes must be positive, got {item!r}")
        points.append((temp, minutes))
    return points


def build_hold_table(
    base_temp: float, base_minutes: float, extra: list[HoldPoint]
) -> tuple[list[HoldPoint], list[HoldPoint]]:
    """Return (table, rejected) with the table sorted by temperature.

    A row is rejected unless it is hotter than every row before it *and*
    needs strictly less time. That keeps the table monotonic, so a hotter
    reading can never require a longer hold than a cooler one.
    """
    table: list[HoldPoint] = [(base_temp, base_minutes)]
    rejected: list[HoldPoint] = []
    for temp, minutes in sorted(extra):
        last_temp, last_minutes = table[-1]
        if temp > last_temp and minutes < last_minutes:
            table.append((temp, minutes))
        else:
            rejected.append((temp, minutes))
    return table, rejected


def format_hold_points(points: list[HoldPoint]) -> str:
    """Format points back into the "65:2, 70:1" text form."""
    return ", ".join(f"{_num(temp)}:{_num(minutes)}" for temp, minutes in points)


def required_seconds(table: list[HoldPoint], temperature: float | None) -> float | None:
    """Hold time required at `temperature`, or None if below the base row."""
    if temperature is None:
        return None
    required: float | None = None
    for temp, minutes in table:
        if temperature >= temp:
            required = minutes * 60.0
        else:
            break
    return required


def _num(value: float) -> str:
    return f"{value:g}"
