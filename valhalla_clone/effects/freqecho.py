"""Valhalla Freq Echo-style frequency-shifting delay."""

from ..dsp import _HILB_A, _HILB_B, freq_echo
from ..params import Param, mix_param
from .base import Effect, echo_tail

MODES = ("Normal", "Analog")


class FreqEcho(Effect):
    NAME = "freqecho"
    TITLE = "Valhalla Freq Echo"
    PARAMS = (
        mix_param(50.0),
        Param("Delay", 1.0, 2000.0, 200.0, "ms", skew=2.0, aliases=("delaytime",)),
        Param("Feedback", 0.0, 100.0, 50.0, "%"),
        Param("Shift", -1000.0, 1000.0, 10.0, "Hz", aliases=("freqshift", "frequency")),
        Param("LowShift", choices=("Off", "On"), default="Off"),
        Param("Width", 0.0, 100.0, 0.0, "%"),
        Param("LowCut", 10.0, 2000.0, 40.0, "Hz", skew=2.0),
        Param("HighCut", 200.0, 20000.0, 12000.0, "Hz", skew=2.0),
        Param("Mode", choices=MODES, default="Normal"),
    )

    def tail_seconds(self):
        return echo_tail(self["Delay"], self["Feedback"] / 100.0)

    def render(self, xl, xr, sr):
        s = self.settings
        shift = s["Shift"] / (100.0 if s["LowShift"] else 1.0)
        return freq_echo(
            xl, xr, sr, s["Delay"], min(s["Feedback"] / 100.0, 0.999), shift, s["Width"] / 100.0,
            s["LowCut"], s["HighCut"], s["Mode"] == 1, _HILB_A, _HILB_B,
        )
