"""ValhallaRoom-style reverb: early reflections plus a late FDN tail."""

import numpy as np

from ..dsp import fdn_reverb
from ..params import Param, mix_param
from .base import Effect

IN_DIFF = (3.91, 2.87, 9.73, 7.13)
ROOM_LINES = (13.1, 16.7, 19.3, 23.9, 27.7, 31.3, 37.1, 41.9)
SPACE_LINES = (23.3, 29.9, 35.3, 41.1, 47.9, 55.3, 61.7, 71.9)

# name: (late delay set, er tap count, er density curve, size scale, brightness, gate seconds)
ROOM_MODES = {
    "Large Room": (ROOM_LINES, 12, 1.0, 1.2, 1.0, 0.0),
    "Medium Room": (ROOM_LINES, 10, 1.0, 0.9, 1.0, 0.0),
    "Bright Room": (ROOM_LINES, 10, 1.0, 1.0, 1.6, 0.0),
    "Large Chamber": (ROOM_LINES, 14, 0.8, 1.4, 1.1, 0.0),
    "Dark Room": (ROOM_LINES, 10, 1.0, 1.0, 0.5, 0.0),
    "Large Space": (SPACE_LINES, 14, 0.7, 1.3, 1.0, 0.0),
    "Dark Space": (SPACE_LINES, 12, 0.7, 1.3, 0.5, 0.0),
    "Small Space": (SPACE_LINES, 8, 1.2, 0.6, 1.0, 0.0),
    "Nonlinear": (ROOM_LINES, 16, 1.0, 1.0, 1.1, 0.3),
    "Narrow Tail": (ROOM_LINES, 10, 1.0, 1.0, 1.0, 0.0),
}


def early_pattern(count, curve, seed):
    rng = np.random.default_rng(seed)
    pos = np.sort(rng.uniform(0.04, 1.0, count)) ** curve
    gains = (1.0 - 0.7 * pos) * rng.choice([-1.0, 1.0], count) / np.sqrt(count / 2)
    return pos, gains


class Room(Effect):
    NAME = "room"
    TITLE = "ValhallaRoom"
    MODE_PARAM = "Type"
    PARAMS = (
        mix_param(50.0),
        Param("PreDelay", 0.0, 500.0, 10.0, "ms"),
        Param("Decay", 0.1, 100.0, 2.0, "s", skew=3.0),
        Param("HighCut", 200.0, 20000.0, 8000.0, "Hz", skew=2.0),
        Param("Depth", 0.0, 100.0, 50.0, "%"),
        Param("EarlySize", 2.0, 100.0, 40.0, "ms"),
        Param("EarlyCross", 0.0, 100.0, 20.0, "%"),
        Param("EarlyModRate", 0.1, 10.0, 1.0, "Hz", skew=2.0),
        Param("EarlyModDepth", 0.0, 100.0, 20.0, "%"),
        Param("EarlySend", 0.0, 100.0, 30.0, "%"),
        Param("LateSize", 0.0, 100.0, 50.0, "%"),
        Param("LateCross", 0.0, 100.0, 20.0, "%"),
        Param("LateModRate", 0.1, 10.0, 0.7, "Hz", skew=2.0),
        Param("LateModDepth", 0.0, 100.0, 40.0, "%"),
        Param("Diffusion", 0.0, 100.0, 80.0, "%"),
        Param("Spin", 0.0, 5.0, 0.6, "Hz"),
        Param("Wander", 0.0, 100.0, 20.0, "%"),
        Param("BassMult", 0.25, 4.0, 1.0, "x", aliases=("rtbassmultiply",)),
        Param("BassXover", 100.0, 2000.0, 500.0, "Hz", skew=2.0, aliases=("rtxover",)),
        Param("HighMult", 0.1, 1.0, 0.6, "x", aliases=("rthighmultiply",)),
        Param("HighXover", 1000.0, 20000.0, 5000.0, "Hz", skew=2.0, aliases=("rthighxover",)),
        Param("Type", choices=tuple(ROOM_MODES), default="Large Room", aliases=("mode", "reverbmode")),
    )

    def tail_seconds(self):
        return self["PreDelay"] / 1000.0 + self["Decay"] * 1.2 + 0.3

    def render(self, xl, xr, sr):
        s = self.settings
        mode = self.choice("Type")
        lines, count, curve, size_k, bright, gate = ROOM_MODES[mode]
        pos, gains = early_pattern(count, curve, seed=sum(map(ord, mode)))
        depth = s["Depth"] / 100.0
        width = 1.0 - s["LateCross"] / 100.0
        if mode == "Narrow Tail":
            width *= 0.3
        return fdn_reverb(
            xl, xr, sr,
            s["PreDelay"], s["Decay"], (0.4 + 1.2 * s["LateSize"] / 100.0) * size_k,
            np.array(lines),
            np.array(IN_DIFF), 0.7 * s["Diffusion"] / 100.0,
            0.2, 0.55 * s["Diffusion"] / 100.0,
            s["LateModRate"], 1.2 * s["LateModDepth"] / 100.0, s["Wander"] / 100.0,
            s["BassMult"], s["BassXover"], min(s["HighMult"] * bright, 1.0), s["HighXover"],
            20.0, s["HighCut"], width,
            -1.0,
            1.0, 0.0, 0,
            pos * s["EarlySize"], gains, 1.0 - depth, s["EarlySend"] / 100.0, depth,
            gate, 0, 0.0,
            s["Spin"] * 4.0, s["EarlyModRate"], 0.4 * s["EarlyModDepth"] / 100.0, 1.0 - s["EarlyCross"] / 100.0,
        )
