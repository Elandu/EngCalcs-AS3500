# SPDX-License-Identifier: AGPL-3.0-only

"""Standard edition metadata and reviewed values used by this module."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StandardReference:
    code: str = "AS/NZS 3500.3"
    edition: str = "2025"
    title: str = "Plumbing and drainage - Part 3: Stormwater drainage"

    def descriptor(self) -> dict[str, str]:
        return {
            "code": self.code,
            "edition": self.edition,
            "title": self.title,
            "amendments": "None included in the cited edition.",
        }


STANDARD = StandardReference()

# AS/NZS 3500.3:2025 Clause 5.4.6(a), Australian runoff coefficients.
AUSTRALIAN_ROOFED_AREA_RUNOFF_COEFFICIENT = 1.0
AUSTRALIAN_UNROOFED_IMPERVIOUS_RUNOFF_COEFFICIENT = 0.9

# AS/NZS 3500.3:2025 Table 5.4.6(A), runoff-coefficient multipliers m.
PERVIOUS_RUNOFF_MULTIPLIERS = (0.8, 0.85, 0.95, 1.0, 1.05, 1.15, 1.2, 1.25)
