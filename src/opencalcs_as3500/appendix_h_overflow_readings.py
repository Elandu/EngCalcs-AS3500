# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded design-chart readings for AS/NZS 3500.3:2025 Appendix H.

The tables define conservative envelopes from Figures H.4, H.6(a), H.6(b), and
H.8 (pp. 146, 148, and 150). The lookup selects the next higher sampled flow,
adds the declared visual-reading allowance, and rejects out-of-range inputs.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import ceil

ContextValue = float | int | str
Context = Mapping[str, ContextValue]

_SOURCE = (
    "AS/NZS 3500.3:2025 Figure {figure}; bounded upper flow bracket, "
    "conservative width curve and {allowance:g} mm visual-reading allowance"
)

# Each series is sampled at integer L/s flow values. Values are mm and rounded
# up to a whole millimetre from the chart reading.
_H6A = {
    300: (21, 26, 30, 33, 37, 41, 45, 49, 52, 55, 59, 62, 66, 69),
    375: (18, 22, 26, 29, 32, 35, 39, 42, 45, 48, 51, 54, 57, 60),
    450: (16, 20, 23, 26, 29, 32, 35, 38, 40, 43, 45, 47, 49, 51),
    525: (14, 18, 21, 24, 26, 29, 32, 35, 37, 39, 41, 43, 45, 47),
    600: (13, 16, 19, 22, 24, 27, 29, 31, 33, 35, 37, 39, 41, 43),
}

_H6B = {
    200: (62, 72, 80, 88, 96, 103, 110, 117, 123, 130, 136, 142, 148, 155),
    300: (52, 59, 65, 72, 78, 84, 90, 95, 100, 106, 111, 116, 121, 132),
    450: (44, 49, 55, 60, 65, 69, 74, 78, 82, 86, 90, 94, 97, 102),
}

_H8 = {
    300: (75, 82, 87, 93, 98, 103, 108, 112, 117, 121, 125, 129, 132, 136),
    375: (71, 77, 83, 88, 93, 98, 102, 106, 110, 114, 118, 121, 124, 127),
    450: (68, 73, 78, 83, 88, 92, 96, 100, 104, 107, 111, 114, 116, 119),
    525: (66, 70, 75, 79, 84, 88, 92, 95, 99, 102, 105, 108, 111, 113),
    600: (64, 68, 72, 76, 80, 84, 87, 91, 94, 97, 100, 103, 105, 107),
}

# Figure H.4 distinguishes pipe families by geometry, not only by area. The
# values below are rounded upward to 5 mm from bounded readings of each curve.
# A further 20 mm allowance covers the visual-reading uncertainty. Only whole
# flow samples inside the plotted family extent are retained.
_H4 = {
    "circular_90": (3, (65, 125, 185, 245)),
    "rectangular_100x75": (3, (50, 95, 140, 185, 230)),
    "circular_100": (4, (85, 130, 175, 220)),
    "rectangular_100x100": (5, (85, 125, 165, 205, 245)),
    "circular_125": (6, (70, 105, 140, 175, 210, 245, 280)),
    "rectangular_150x100": (7, (65, 95, 130, 165, 200, 235, 270, 300)),
    "rectangular_125x125": (8, (100, 135, 170, 205, 240, 275, 300)),
    "circular_140": (8, (100, 135, 170, 205, 240, 275, 300)),
    "circular_150": (10, (100, 125, 150, 175, 200, 225, 250)),
    "rectangular_150x150": (12, (90, 110, 130, 150, 170)),
}


def _family(context: Context) -> str | None:
    """Resolve H.4 only from an explicitly identified standard pipe family."""
    named = context.get("pipe_family")
    if isinstance(named, str):
        normalized = named.lower().replace(" ", "").replace("×", "x").replace("ø", "d")
        geometry, separator, size = normalized.partition(":")
        if separator and geometry in ("circular", "rectangular"):
            normalized = f"{geometry}_{size}"
        if normalized in _H4:
            return normalized
        aliases = {
            "d90": "circular_90",
            "dn90": "circular_90",
            "90": "circular_90",
            "100x75": "rectangular_100x75",
            "d100x75": "rectangular_100x75",
            "d100": "circular_100",
            "dn100": "circular_100",
            "100": "circular_100",
            "100x100": "rectangular_100x100",
            "d100x100": "rectangular_100x100",
            "d125": "circular_125",
            "dn125": "circular_125",
            "125": "circular_125",
            "150x100": "rectangular_150x100",
            "125x125": "rectangular_125x125",
            "d140": "circular_140",
            "dn140": "circular_140",
            "140": "circular_140",
            "d150": "circular_150",
            "dn150": "circular_150",
            "150": "circular_150",
            "150x150": "rectangular_150x150",
        }
        family = aliases.get(normalized)
        if family:
            return family

    shape = context.get("pipe_shape")
    if shape == "circular":
        diameter = context.get("diameter_mm")
        if diameter in (90, 100, 125, 140, 150):
            return f"circular_{int(diameter)}"
    if shape == "rectangular":
        width, height = context.get("width_mm"), context.get("height_mm")
        if (width, height) in ((100, 75), (100, 100), (125, 125), (150, 100), (150, 150)):
            return f"rectangular_{int(width)}x{int(height)}"
        if (height, width) in ((100, 75),):
            return "rectangular_100x75"
    return None


def _upper_sample(flow_lps: float, start: int, values: tuple[int, ...]) -> int | None:
    if flow_lps < start:
        return None
    index = max(0, ceil(flow_lps) - start)
    if index >= len(values):
        return None
    return values[index]


def _width_series(
    flow_lps: float, requested_width: float, series: Mapping[int, tuple[int, ...]], start: int
) -> int | None:
    if requested_width <= 0:
        return None
    # A narrower published curve gives a conservative result between widths.
    supported_widths = sorted(series)
    if requested_width > supported_widths[-1]:
        return None
    applicable = [width for width in supported_widths if width <= requested_width]
    if not applicable:
        return None
    selected_width = applicable[-1]
    return _upper_sample(flow_lps, start, series[selected_width])


def lookup_overflow_reading(
    figure: str, flow_lps: float, context: Context
) -> tuple[float, str] | None:
    """Return a conservative bounded Appendix H ordinate and its source.

    Supported figures are H.4, H.6a, H.6b, and H.8. H.4 requires exact pipe
    family geometry. H.6a/H.8 require ``box_width_mm``; H.6b requires
    ``overflow_width_mm``. Unsupported geometry and out-of-chart flows return
    ``None`` so callers can request a sourced manual reading.
    """
    allowance = 0
    if figure == "H.4":
        allowance = 20
        family = _family(context)
        if family is None or family not in _H4:
            return None
        start, values = _H4[family]
        result = _upper_sample(flow_lps, start, values)
    elif figure in ("H.6a", "H.6(a)"):
        allowance = 3
        width = context.get("box_width_mm")
        result = (
            _width_series(flow_lps, float(width), _H6A, 3)
            if isinstance(width, (int, float))
            else None
        )
    elif figure in ("H.6b", "H.6(b)"):
        width = context.get("overflow_width_mm")
        # The 200 mm curve reaches 160 mm at 16 L/s. Its envelope needs a
        # larger allowance than the wider curves; 155 mm would underread it.
        allowance = 10 if isinstance(width, (int, float)) and width < 300 else 3
        result = (
            _width_series(flow_lps, float(width), _H6B, 3)
            if isinstance(width, (int, float))
            else None
        )
    elif figure == "H.8":
        allowance = 3
        width = context.get("box_width_mm")
        result = (
            _width_series(flow_lps, float(width), _H8, 3)
            if isinstance(width, (int, float))
            else None
        )
    else:
        return None

    if result is None:
        return None
    return float(result + allowance), _SOURCE.format(figure=figure, allowance=allowance)
