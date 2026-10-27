"""Parameter descriptions shared by all effects."""

from __future__ import annotations

import re
from dataclasses import dataclass


def norm_key(name: str) -> str:
    """Normalise a parameter / choice name for case- and punctuation-insensitive lookup."""
    return re.sub(r"[^0-9a-z]", "", str(name).lower())


@dataclass(frozen=True)
class Param:
    name: str
    minimum: float = 0.0
    maximum: float = 1.0
    default: float | str = 0.0
    unit: str = ""
    choices: tuple[str, ...] = ()
    skew: float = 1.0  # >1 gives finer resolution at the low end of the normalised range
    aliases: tuple[str, ...] = ()

    @property
    def is_choice(self) -> bool:
        return bool(self.choices)

    def choice_index(self, value) -> int:
        if isinstance(value, str):
            key = norm_key(value)
            for i, c in enumerate(self.choices):
                if norm_key(c) == key:
                    return i
            try:
                value = float(value)
            except ValueError:
                raise ValueError(
                    f"{self.name}: unknown choice {value!r}; expected one of {', '.join(self.choices)}"
                ) from None
        return int(min(max(round(float(value)), 0), len(self.choices) - 1))

    def clamp(self, value):
        if self.is_choice:
            return self.choice_index(value)
        return float(min(max(float(value), self.minimum), self.maximum))

    def default_value(self):
        return self.clamp(self.default)

    def to_normalized(self, value) -> float:
        value = self.clamp(value)
        if self.is_choice:
            return value / max(len(self.choices) - 1, 1)
        span = self.maximum - self.minimum
        return ((value - self.minimum) / span) ** (1.0 / self.skew) if span else 0.0

    def from_normalized(self, n) -> float | int:
        n = min(max(float(n), 0.0), 1.0)
        if self.is_choice:
            return int(round(n * (len(self.choices) - 1)))
        return self.minimum + (self.maximum - self.minimum) * n**self.skew

    def display(self, value) -> str:
        value = self.clamp(value)
        if self.is_choice:
            return self.choices[value]
        return f"{value:g}{(' ' + self.unit) if self.unit else ''}"


def mix_param(default=50.0) -> Param:
    return Param("Mix", 0.0, 100.0, default, "%", aliases=("wet", "drywet"))
