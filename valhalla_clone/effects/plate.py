"""ValhallaPlate-style plate reverb built on Dattorro's plate topology."""

from ..dsp import plate_reverb
from ..params import Param, mix_param
from .base import Effect

# name: (input bandwidth, tank damping, input diffusion 1, 2, decay diffusion 1, 2, size scale)
PLATE_MODES = {
    "Steel": (0.9995, 0.0005, 0.75, 0.625, 0.70, 0.50, 1.00),
    "Aluminum": (0.9995, 0.0002, 0.78, 0.66, 0.72, 0.55, 0.90),
    "Brass": (0.9, 0.12, 0.75, 0.625, 0.70, 0.50, 1.05),
    "Gold": (0.85, 0.20, 0.76, 0.64, 0.68, 0.48, 1.10),
    "Bronze": (0.8, 0.30, 0.74, 0.62, 0.66, 0.46, 1.10),
    "Copper": (0.88, 0.15, 0.70, 0.58, 0.64, 0.44, 0.95),
    "Silver": (0.97, 0.05, 0.78, 0.66, 0.70, 0.52, 0.85),
    "Platinum": (0.99, 0.02, 0.80, 0.70, 0.74, 0.56, 1.20),
    "Titanium": (0.995, 0.01, 0.72, 0.60, 0.70, 0.50, 0.75),
}


class Plate(Effect):
    NAME = "plate"
    TITLE = "ValhallaPlate"
    PARAMS = (
        mix_param(50.0),
        Param("PreDelay", 0.0, 500.0, 0.0, "ms"),
        Param("Decay", 0.1, 60.0, 2.5, "s", skew=3.0),
        Param("Size", 0.0, 100.0, 50.0, "%"),
        Param("Width", 0.0, 100.0, 100.0, "%"),
        Param("ModRate", 0.01, 5.0, 0.8, "Hz", skew=2.0),
        Param("ModDepth", 0.0, 100.0, 30.0, "%"),
        Param("LowCut", 10.0, 2000.0, 20.0, "Hz", skew=2.0),
        Param("HighCut", 200.0, 20000.0, 9000.0, "Hz", skew=2.0),
        Param("BassMult", 0.25, 4.0, 1.0, "x"),
        Param("BassXover", 100.0, 2000.0, 400.0, "Hz", skew=2.0),
        Param("Mode", choices=tuple(PLATE_MODES), default="Steel", aliases=("platemode", "type")),
    )

    def tail_seconds(self):
        return self["PreDelay"] / 1000.0 + self["Decay"] * 1.2 + 0.3

    def render(self, xl, xr, sr):
        s = self.settings
        bw, damp, i1, i2, d1, d2, size_k = PLATE_MODES[self.choice("Mode")]
        return plate_reverb(
            xl, xr, sr, s["PreDelay"], s["Decay"], (0.35 + 1.3 * s["Size"] / 100.0) * size_k,
            s["Width"] / 100.0, bw, damp, i1, i2, d1, d2,
            s["ModRate"], 16.0 * s["ModDepth"] / 100.0, s["LowCut"], s["HighCut"],
            s["BassMult"], s["BassXover"],
        )
