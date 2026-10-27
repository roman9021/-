"""ValhallaShimmer-style pitch-shifting reverb."""

import numpy as np

from ..dsp import fdn_reverb, reverse_chunks
from ..params import Param, mix_param
from .base import Effect

LINES = (31.1, 37.3, 41.9, 47.3, 53.9, 59.1, 67.3, 73.1)
IN_DIFF = (4.77, 3.59, 12.73, 9.31)

# name: (stereo pitch shifter, reverse input, bloom: extra attack smear)
REVERB_MODES = {
    "Mono": (0, False, 0.0),
    "Stereo": (1, False, 0.0),
    "Reverse": (1, True, 0.0),
    "Bloom": (1, False, 1.0),
}


class Shimmer(Effect):
    NAME = "shimmer"
    TITLE = "ValhallaShimmer"
    PARAMS = (
        mix_param(50.0),
        Param("PreDelay", 0.0, 500.0, 0.0, "ms"),
        Param("Size", 0.0, 100.0, 60.0, "%"),
        Param("Feedback", 0.0, 100.0, 80.0, "%", aliases=("decay",)),
        Param("Diffusion", 0.0, 100.0, 80.0, "%"),
        Param("Shift", -24.0, 24.0, 12.0, "st", aliases=("pitch", "pitchshift")),
        Param("ShiftMix", 0.0, 100.0, 50.0, "%", aliases=("shimmer",)),
        Param("ModRate", 0.01, 10.0, 0.4, "Hz", skew=2.0),
        Param("ModDepth", 0.0, 100.0, 40.0, "%"),
        Param("LowCut", 10.0, 2000.0, 120.0, "Hz", skew=2.0),
        Param("HighCut", 200.0, 20000.0, 7000.0, "Hz", skew=2.0),
        Param("Mode", choices=tuple(REVERB_MODES), default="Stereo", aliases=("reverbmode",)),
    )

    def tail_seconds(self):
        fb = self["Feedback"] / 100.0
        return self["PreDelay"] / 1000.0 + 1.0 + 25.0 * fb**3

    def render(self, xl, xr, sr):
        s = self.settings
        stereo, reverse, bloom = REVERB_MODES[self.choice("Mode")]
        size = 0.4 + 1.6 * s["Size"] / 100.0
        if reverse:
            chunk = (0.15 + 0.5 * s["Size"] / 100.0) * sr
            xl = reverse_chunks(xl, chunk)
            xr = reverse_chunks(xr, chunk)
        fb = 0.985 * (s["Feedback"] / 100.0) ** 0.5
        return fdn_reverb(
            xl, xr, sr,
            s["PreDelay"], 0.0, size,
            np.array(LINES),
            np.array(IN_DIFF), 0.75 * s["Diffusion"] / 100.0,
            0.3 + 0.7 * bloom, 0.6 * s["Diffusion"] / 100.0,
            s["ModRate"], 1.5 * s["ModDepth"] / 100.0, 0.2,
            1.0, 300.0, 0.6, 4000.0,
            s["LowCut"], s["HighCut"], 1.0,
            fb,
            2.0 ** (s["Shift"] / 12.0), 1.2 * s["ShiftMix"] / 100.0 * s["Feedback"] / 100.0, stereo,
            np.zeros(0), np.zeros(0), 0.0, 0.0, 1.0,
            0.0, 0, 0.0,
        )
