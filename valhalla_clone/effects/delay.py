"""ValhallaDelay-style echo with tape, BBD, digital, pitch and reverse modes."""

import numpy as np

from ..dsp import echo_delay, reverse_chunks
from ..params import Param, mix_param
from .base import Effect, echo_tail

# name: (flutter, noise, bbd, digital bits, pitch blend, extra diffusion, reverse)
MODES = {
    "Tape": (1.0, 1.0, 0, 0, 0.0, 0.0, False),
    "HiFi": (0.0, 0.0, 0, 0, 0.0, 0.0, False),
    "BBD": (0.2, 1.0, 1, 0, 0.0, 0.0, False),
    "Digital": (0.0, 0.0, 0, 12, 0.0, 0.0, False),
    "Ghost": (0.5, 0.5, 0, 0, 0.5, 0.4, False),
    "Pitch": (0.0, 0.0, 0, 0, 1.0, 0.0, False),
    "RevTape": (1.0, 1.0, 0, 0, 0.0, 0.0, True),
}
STYLES = ("Single", "Dual", "PingPong")


class Delay(Effect):
    NAME = "delay"
    TITLE = "ValhallaDelay"
    PARAMS = (
        mix_param(30.0),
        Param("DelayL", 1.0, 5000.0, 375.0, "ms", skew=2.0, aliases=("delay", "delaytime", "delayleft")),
        Param("DelayR", 1.0, 5000.0, 375.0, "ms", skew=2.0, aliases=("delayright",)),
        Param("Feedback", 0.0, 110.0, 40.0, "%"),
        Param("Width", 0.0, 100.0, 100.0, "%"),
        Param("Age", 0.0, 100.0, 25.0, "%"),
        Param("Drive", 0.0, 100.0, 0.0, "%"),
        Param("Diffusion", 0.0, 100.0, 0.0, "%"),
        Param("Ducking", 0.0, 100.0, 0.0, "%"),
        Param("ModRate", 0.01, 10.0, 0.5, "Hz", skew=2.0),
        Param("ModDepth", 0.0, 100.0, 20.0, "%"),
        Param("LowCut", 10.0, 2000.0, 80.0, "Hz", skew=2.0),
        Param("HighCut", 200.0, 20000.0, 8000.0, "Hz", skew=2.0),
        Param("Pitch", -12.0, 12.0, 12.0, "st", aliases=("pitchshift",)),
        Param("Mode", choices=tuple(MODES), default="Tape"),
        Param("Style", choices=STYLES, default="Single"),
    )

    def tail_seconds(self):
        return echo_tail(max(self["DelayL"], self["DelayR"]), self["Feedback"] / 100.0)

    def render(self, xl, xr, sr):
        s = self.settings
        flutter, noise, bbd, bits, pitch_amt, diff_add, reverse = MODES[self.choice("Mode")]
        style = s["Style"]
        dr = s["DelayL"] if style == 0 else s["DelayR"]
        if reverse:
            xl = reverse_chunks(xl, s["DelayL"] * sr / 1000.0)
            xr = reverse_chunks(xr, dr * sr / 1000.0)
        # above 100% the loop runs away; soft clipping inside keeps it bounded
        return echo_delay(
            xl, xr, sr, s["DelayL"], dr, s["Feedback"] / 100.0, style,
            s["Width"] / 100.0, s["Age"] / 100.0, s["Drive"] / 100.0,
            min(s["Diffusion"] / 100.0 + diff_add, 1.0), s["Ducking"] / 100.0,
            s["ModRate"], 2.0 * s["ModDepth"] / 100.0 * (1.0 if flutter or bbd else 0.25), flutter,
            s["LowCut"], s["HighCut"], bbd, bits,
            2.0 ** (s["Pitch"] / 12.0), pitch_amt, noise,
        )
