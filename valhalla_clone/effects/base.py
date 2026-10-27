"""Common machinery for all effects: settings storage, mixing and tails."""

from __future__ import annotations

import numpy as np

from ..params import Param, norm_key


class Effect:
    NAME = ""
    TITLE = ""
    PARAMS: tuple[Param, ...] = ()
    MODE_PARAM = "Mode"
    MAX_TAIL = 30.0

    def __init__(self, **settings):
        self.settings = {p.name: p.default_value() for p in self.PARAMS}
        self.update(settings)

    # ---------------------------------------------------------------- settings
    @classmethod
    def param(cls, name: str) -> Param:
        key = norm_key(name)
        for p in cls.PARAMS:
            if norm_key(p.name) == key or key in (norm_key(a) for a in p.aliases):
                return p
        raise KeyError(f"{cls.TITLE}: unknown parameter {name!r}")

    @classmethod
    def has_param(cls, name: str) -> bool:
        try:
            cls.param(name)
            return True
        except KeyError:
            return False

    def __getitem__(self, name):
        return self.settings[self.param(name).name]

    def __setitem__(self, name, value):
        p = self.param(name)
        self.settings[p.name] = p.clamp(value)

    def update(self, values: dict, normalized: bool = False) -> list[str]:
        """Apply settings; returns the keys that matched no parameter."""
        unknown = []
        for name, value in values.items():
            if not self.has_param(name):
                unknown.append(name)
                continue
            p = self.param(name)
            if normalized and not isinstance(value, str):
                value = p.from_normalized(value)
            self.settings[p.name] = p.clamp(value)
        return unknown

    def choice(self, name: str) -> str:
        p = self.param(name)
        return p.choices[self.settings[p.name]]

    def to_dict(self) -> dict:
        return {
            p.name: p.choices[self.settings[p.name]] if p.is_choice else round(self.settings[p.name], 6)
            for p in self.PARAMS
        }

    def copy_settings_from(self, other: "Effect") -> list[str]:
        """Copy every parameter both effects share (same name). Returns the copied names."""
        copied = []
        for p in other.PARAMS:
            if not self.has_param(p.name):
                continue
            mine = self.param(p.name)
            value = other.settings[p.name]
            if p.is_choice:
                value = p.choices[value]
                if norm_key(value) not in (norm_key(c) for c in mine.choices):
                    continue
            elif mine.is_choice:
                continue
            self.settings[mine.name] = mine.clamp(value)
            copied.append(mine.name)
        return copied

    def clone(self) -> "Effect":
        return type(self)(**self.to_dict())

    # --------------------------------------------------------------- rendering
    def tail_seconds(self) -> float:
        return 2.0

    def process(self, audio, sr: int, tail: float | None = None) -> np.ndarray:
        """Process mono (n,) or multichannel (n, ch) audio; returns (n + tail, 2)."""
        x = np.asarray(audio, dtype=np.float64)
        if x.ndim == 1:
            x = np.stack([x, x], axis=1)
        elif x.shape[1] == 1:
            x = np.repeat(x, 2, axis=1)
        elif x.shape[1] > 2:
            x = x[:, :2]
        tail = min(self.tail_seconds(), self.MAX_TAIL) if tail is None else max(float(tail), 0.0)
        pad = int(round(tail * sr))
        if pad:
            x = np.concatenate([x, np.zeros((pad, 2))])
        xl = np.ascontiguousarray(x[:, 0])
        xr = np.ascontiguousarray(x[:, 1])
        wl, wr = self.render(xl, xr, float(sr))
        mix = self.settings.get("Mix", 100.0) / 100.0
        out = np.empty_like(x)
        out[:, 0] = (1.0 - mix) * xl + mix * wl
        out[:, 1] = (1.0 - mix) * xr + mix * wr
        return out

    def render(self, xl: np.ndarray, xr: np.ndarray, sr: float):
        """Return the 100%-wet stereo signal."""
        raise NotImplementedError

    def describe(self) -> str:
        lines = [f"{self.TITLE} ({self.NAME})"]
        for p in self.PARAMS:
            if p.is_choice:
                rng = " | ".join(p.choices)
            else:
                rng = f"{p.minimum:g} .. {p.maximum:g} {p.unit}".rstrip()
            lines.append(f"  {p.name:<16} = {p.display(self.settings[p.name]):<20} [{rng}]")
        return "\n".join(lines)


def echo_tail(delay_ms: float, feedback: float, floor_db: float = -60.0) -> float:
    """Seconds until a feedback echo decays below `floor_db`."""
    fb = min(abs(feedback), 0.999)
    repeats = 1.0 if fb <= 1e-4 else 1.0 + floor_db / (20.0 * np.log10(fb))
    return delay_ms / 1000.0 * repeats + 0.2
