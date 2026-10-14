# SPDX-License-Identifier: AGPL-3.0-only
"""Conservative, bounded envelopes of the Appendix H.1 and H.3 graphs.

These deliberately coarse derived readings round dimensions upward and select
the adverse sampled corner. They are not fitted equations or exact chart
interpolation. H.1 retains the larger unadjusted depth instead of taking the
gradient reduction; Appendix I exact readings are handled separately.
"""

from bisect import bisect_left
from collections.abc import Mapping

Context = Mapping[str, float | str]

# H.1 bottom-right panel: depth including freeboard BEFORE gradient reduction.
# Each tuple is (sampled flow L/s, upward-rounded conservative depth mm).
_H1 = {
    200: ((3, 125), (6, 170), (10, 205)),
    300: ((3, 115), (6, 140), (10, 170), (16, 205)),
    375: ((3, 110), (6, 130), (10, 155), (16, 190)),
    450: ((3, 105), (6, 125), (10, 145), (16, 175)),
    525: ((3, 100), (6, 120), (10, 140), (16, 165)),
    600: ((3, 95), (6, 115), (10, 130), (16, 155)),
}

# H.3 left panel. Keep the actual named pipe family; equal area is insufficient.
_H3_WATER = {
    "circular:90": ((4, 75), (6, 135)),
    "rectangular:100x75": ((4, 70), (6, 120), (8, 180)),
    "circular:100": ((4, 50), (6, 100), (8, 165)),
    "rectangular:100x100": ((6, 65), (8, 110), (10, 165), (12, 220)),
    "circular:125": ((10, 110), (12, 150), (14, 200), (16, 250)),
    "rectangular:150x100": ((10, 85), (12, 115), (14, 145), (16, 180)),
    "rectangular:125x125": ((11, 80), (12, 100), (14, 130), (16, 180)),
    "circular:140": ((11, 80), (12, 100), (14, 130), (16, 180)),
    "circular:150": ((10, 75), (12, 100), (14, 125), (16, 165)),
    "rectangular:150x150": ((13, 90), (16, 125)),
}

# H.3 right panel. Curves are gutter depth ha, not pipe size. The queried
# vertical ordinate is the ADOPTED rainhead depth hr; return horizontal length.
_H3_LENGTH = {
    100: ((80, 95), (200, 120), (300, 140), (440, 165)),
    125: ((80, 130), (200, 155), (300, 180), (440, 215)),
    150: ((80, 160), (200, 190), (300, 215), (440, 250)),
    170: ((80, 185), (200, 215), (300, 245), (440, 280)),
}


def _upper(x: float, samples: tuple[tuple[int, int], ...]) -> tuple[int, int] | None:
    if not samples[0][0] <= x <= samples[-1][0]:
        return None
    return samples[bisect_left([row[0] for row in samples], x)]


def lookup_roof_reading(figure: str, x: float, context: Context) -> tuple[float, str] | None:
    """Return an adverse sampled reading, or None outside the supported grid."""
    if figure == "H.1":
        width = float(context["box_width_mm"])
        gradient = float(context["gradient"])
        if not 200 <= width <= 600 or not 1 / 200 <= gradient <= 1 / 40:
            return None
        curve = max(w for w in _H1 if w <= width)
        sample = _upper(x, _H1[curve])
        if sample is None:
            return None
        flow, value = sample
        return float(value), (
            "AS/NZS 3500.3:2025 Figure H.1 conservative envelope: "
            f"flow bracket {flow:g} L/s, width curve {curve:g} mm; upward-rounded "
            "unadjusted depth retained without gradient reduction"
        )
    if figure == "H.3.water_depth":
        family = str(context["pipe_family"])
        if family not in _H3_WATER:
            return None
        sample = _upper(x, _H3_WATER[family])
        if sample is None:
            return None
        flow, value = sample
        return float(value), (
            "AS/NZS 3500.3:2025 Figure H.3 conservative water-depth envelope: "
            f"{family}, upper flow bracket {flow:g} L/s; dimension rounded upward"
        )
    if figure == "H.3.length":
        ha = float(context["gutter_depth_at_1_in_200_mm"])
        if not 100 <= ha <= 170:
            return None
        curve = min(h for h in _H3_LENGTH if h >= ha)
        sample = _upper(x, _H3_LENGTH[curve])
        if sample is None:
            return None
        depth, value = sample
        return float(value), (
            "AS/NZS 3500.3:2025 Figure H.3 conservative length envelope: "
            f"ha curve {curve:g} mm, adopted hr upper bracket {depth:g} mm; "
            "length rounded upward"
        )
    return None
