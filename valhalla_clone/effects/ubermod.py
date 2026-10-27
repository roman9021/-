"""ValhallaUberMod-style modulated multi-tap delay."""

from ..dsp import multitap
from ..params import Param, mix_param
from .base import Effect, echo_tail

# name: (drive add, age add, density add, tap decay)
MODES = {
    "Clean": (0.0, 0.0, 0.0, 0.3),
    "Tape": (0.3, 0.3, 0.0, 0.4),
    "Dark Tape": (0.4, 0.7, 0.0, 0.5),
    "BBD": (0.2, 0.5, 0.1, 0.5),
    "Lo-Fi": (0.8, 0.8, 0.0, 0.3),
    "Diffuse": (0.0, 0.1, 0.6, 0.2),
    "Rhythmic": (0.0, 0.0, 0.0, 0.0),
}


class UberMod(Effect):
    NAME = "ubermod"
    TITLE = "ValhallaUberMod"
    PARAMS = (
        mix_param(50.0),
        Param("Delay", 1.0, 2000.0, 300.0, "ms", skew=2.0),
        Param("Taps", 1.0, 16.0, 4.0, "", aliases=("numtaps",)),
        Param("Warp", -100.0, 100.0, 0.0, "%"),
        Param("Feedback", 0.0, 100.0, 30.0, "%"),
        Param("Density", 0.0, 100.0, 30.0, "%", aliases=("diffusion",)),
        Param("Width", 0.0, 100.0, 100.0, "%"),
        Param("ModRate", 0.01, 10.0, 0.6, "Hz", skew=2.0),
        Param("ModDepth", 0.0, 100.0, 30.0, "%"),
        Param("LowCut", 10.0, 2000.0, 60.0, "Hz", skew=2.0),
        Param("HighCut", 200.0, 20000.0, 9000.0, "Hz", skew=2.0),
        Param("Drive", 0.0, 100.0, 0.0, "%"),
        Param("Age", 0.0, 100.0, 0.0, "%"),
        Param("Mode", choices=tuple(MODES), default="Clean"),
    )

    def tail_seconds(self):
        return echo_tail(self["Delay"], self["Feedback"] / 100.0)

    def render(self, xl, xr, sr):
        s = self.settings
        drive, age, dens, tap_decay = MODES[self.choice("Mode")]
        return multitap(
            xl, xr, sr, s["Delay"], int(round(s["Taps"])), s["Warp"] / 100.0, s["Feedback"] / 100.0,
            min(s["Density"] / 100.0 + dens, 1.0), s["Width"] / 100.0,
            s["ModRate"], 3.0 * s["ModDepth"] / 100.0, s["LowCut"], s["HighCut"],
            min(s["Drive"] / 100.0 + drive, 1.0), min(s["Age"] / 100.0 + age, 1.0), tap_decay,
        )
