"""Valhalla Supermassive-style delay/reverb hybrid."""

import numpy as np

from ..dsp import fdn_reverb
from ..params import Param, mix_param
from .base import Effect

IN_DIFF = (3.1, 4.3, 5.9, 7.7)

# name: (lines, spread exponent, diffusion scale, in-loop diffusion scale, random mod)
MODES = {
    "Gemini": (8, 0.30, 0.20, 0.10, 0.0),
    "Hydra": (8, 0.45, 0.35, 0.15, 0.0),
    "Centaurus": (8, 0.60, 0.50, 0.25, 0.0),
    "Sagittarius": (16, 0.80, 0.80, 0.50, 0.0),
    "Great Annihilator": (16, 1.00, 1.00, 0.80, 0.0),
    "Andromeda": (16, 1.10, 0.90, 0.90, 0.2),
    "Lyra": (8, 0.70, 0.60, 0.40, 0.3),
    "Capricorn": (8, 0.90, 0.70, 0.60, 0.0),
    "Large Magellanic Cloud": (16, 1.20, 0.95, 0.95, 0.0),
    "Triangulum": (16, 0.95, 0.85, 0.70, 0.4),
    "Cirrus Major": (16, 1.30, 1.00, 0.85, 0.5),
    "Cirrus Minor": (8, 1.10, 0.90, 0.75, 0.5),
    "Aquarius": (8, 0.50, 0.30, 0.60, 0.0),
    "Pisces": (8, 0.40, 0.25, 0.50, 0.2),
    "Scorpio": (16, 0.85, 0.60, 0.40, 0.6),
    "Libra": (8, 0.65, 0.40, 0.30, 0.0),
    "Leo": (16, 1.00, 0.75, 0.65, 0.1),
    "Virgo": (16, 1.15, 0.70, 0.90, 0.3),
}


def mode_delays(n, delay_ms, warp, spread):
    """Spread `n` line lengths around `delay_ms`; Warp widens the ratio between them."""
    primes = np.array([2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53], float)[:n]
    ratios = np.log(primes) / np.log(primes).mean()
    k = spread * (0.15 + 1.85 * warp)
    return np.maximum(delay_ms * ratios**k, 1.0)


class Supermassive(Effect):
    NAME = "supermassive"
    TITLE = "Valhalla Supermassive"
    PARAMS = (
        mix_param(50.0),
        Param("Delay", 0.0, 5000.0, 250.0, "ms", skew=2.0, aliases=("delayms",)),
        Param("Warp", 0.0, 100.0, 50.0, "%"),
        Param("Feedback", 0.0, 100.0, 60.0, "%"),
        Param("Density", 0.0, 100.0, 50.0, "%"),
        Param("Width", 0.0, 100.0, 100.0, "%"),
        Param("LowCut", 10.0, 2000.0, 20.0, "Hz", skew=2.0),
        Param("HighCut", 200.0, 20000.0, 10000.0, "Hz", skew=2.0),
        Param("ModRate", 0.01, 10.0, 0.4, "Hz", skew=2.0),
        Param("ModDepth", 0.0, 100.0, 30.0, "%"),
        Param("Mode", choices=tuple(MODES), default="Gemini"),
    )

    def tail_seconds(self):
        fb = self["Feedback"] / 100.0
        d = max(self["Delay"], 20.0) / 1000.0
        return 0.5 + min(d * (1.0 + 60.0 / max(-20 * np.log10(max(fb, 1e-3)), 0.05)), 25.0)

    def render(self, xl, xr, sr):
        s = self.settings
        lines, spread, diff_k, loop_k, rand = MODES[self.choice("Mode")]
        density = s["Density"] / 100.0
        return fdn_reverb(
            xl, xr, sr,
            0.0, 0.0, 1.0,
            mode_delays(lines, max(s["Delay"], 2.0), s["Warp"] / 100.0, spread),
            np.array(IN_DIFF), min(0.8 * diff_k * density, 0.8),
            0.0, min(0.7 * loop_k * density, 0.75),
            s["ModRate"], 3.0 * s["ModDepth"] / 100.0, rand,
            1.0, 300.0, 0.9, 6000.0,
            s["LowCut"], s["HighCut"], s["Width"] / 100.0,
            min(s["Feedback"] / 100.0, 0.995),
            1.0, 0.0, 0,
            np.zeros(0), np.zeros(0), 0.0, 0.0, 1.0,
            0.0, 0, 0.0,
        )
