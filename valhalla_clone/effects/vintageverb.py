"""ValhallaVintageVerb-style algorithmic reverb."""

import numpy as np

from ..dsp import fdn_reverb
from ..params import Param, mix_param
from .base import Effect

HALL = (29.7, 37.1, 41.1, 43.7, 53.3, 59.9, 67.1, 79.3)
ROOM = (11.3, 13.7, 17.9, 19.1, 23.3, 27.1, 31.9, 37.3)
PLATE = (7.9, 11.3, 14.9, 17.1, 21.7, 24.9, 28.3, 33.7)
CHAMBER = (17.3, 21.1, 25.7, 29.3, 33.1, 37.9, 41.3, 47.9)
AMBIENCE = (5.3, 7.1, 8.9, 10.7, 12.1, 14.3, 16.9, 19.7)
LARGE = (31.1, 37.3, 41.9, 47.3, 53.9, 59.1, 67.3, 73.1, 79.9, 83.3, 89.7, 97.1, 103.9, 109.3, 117.1, 127.3)
IN_DIFF = (4.77, 3.59, 12.73, 9.31)

# name: (delay set, size scale, early-diffusion scale, late-diffusion scale,
#        random modulation 0..1, modulation depth scale, brightness, gate seconds)
REVERB_MODES = {
    "Concert Hall": (HALL, 1.00, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0),
    "Bright Hall": (HALL, 1.00, 1.0, 1.0, 0.0, 1.0, 1.6, 0.0),
    "Plate": (PLATE, 1.00, 1.1, 0.9, 0.0, 0.8, 1.3, 0.0),
    "Room": (ROOM, 1.00, 0.9, 1.0, 0.0, 0.7, 1.0, 0.0),
    "Chamber": (CHAMBER, 1.00, 1.0, 1.1, 0.0, 0.8, 1.1, 0.0),
    "Random Space": (HALL, 1.10, 0.9, 1.0, 0.8, 1.0, 1.0, 0.0),
    "Chorus Space": (HALL, 1.05, 0.9, 1.0, 0.0, 3.0, 1.0, 0.0),
    "Ambience": (AMBIENCE, 1.00, 1.0, 0.8, 0.0, 0.5, 1.2, 0.0),
    "Sanctuary": (LARGE, 1.20, 1.0, 1.1, 0.3, 1.2, 0.9, 0.0),
    "Dirty Hall": (HALL, 1.00, 0.8, 0.8, 0.5, 1.5, 0.8, 0.0),
    "Dirty Plate": (PLATE, 1.00, 0.9, 0.8, 0.5, 1.5, 1.0, 0.0),
    "Smooth Plate": (PLATE, 1.00, 1.2, 1.2, 0.0, 0.6, 1.1, 0.0),
    "Smooth Room": (ROOM, 1.00, 1.2, 1.2, 0.0, 0.5, 1.0, 0.0),
    "Smooth Random": (HALL, 1.00, 1.2, 1.2, 0.7, 0.8, 1.0, 0.0),
    "Nonlin": (ROOM, 1.00, 1.0, 1.0, 0.0, 0.5, 1.2, 0.35),
    "Chaotic Hall": (HALL, 1.10, 1.0, 1.0, 1.0, 2.0, 1.0, 0.0),
    "Chaotic Chamber": (CHAMBER, 1.00, 1.0, 1.0, 1.0, 2.0, 1.0, 0.0),
    "Chaotic Neutral": (CHAMBER, 1.00, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0),
    "Cathedral": (LARGE, 1.50, 1.0, 1.1, 0.2, 1.0, 0.9, 0.0),
    "Palace": (LARGE, 1.30, 1.1, 1.1, 0.2, 1.0, 1.1, 0.0),
    "Chamber1979": (CHAMBER, 1.00, 0.9, 0.9, 0.0, 0.6, 0.8, 0.0),
    "Hall1984": (HALL, 1.00, 0.9, 0.9, 0.0, 0.8, 0.9, 0.0),
}

# colour: (internal sample rate, bit depth, highcut ceiling)
COLOR_MODES = {"1970s": (10_000.0, 12, 4_500.0), "1980s": (24_000.0, 16, 10_000.0), "Now": (0.0, 0, 20_000.0)}


class VintageVerb(Effect):
    NAME = "vintageverb"
    TITLE = "ValhallaVintageVerb"
    MODE_PARAM = "ReverbMode"
    PARAMS = (
        mix_param(50.0),
        Param("PreDelay", 0.0, 500.0, 0.0, "ms"),
        Param("Decay", 0.2, 70.0, 2.0, "s", skew=3.0),
        Param("Size", 0.0, 100.0, 50.0, "%"),
        Param("Attack", 0.0, 100.0, 50.0, "%"),
        Param("EarlyDiffusion", 0.0, 100.0, 70.0, "%", aliases=("earlydiff",)),
        Param("LateDiffusion", 0.0, 100.0, 70.0, "%", aliases=("latediff",)),
        Param("ModRate", 0.01, 10.0, 0.5, "Hz", skew=2.0),
        Param("ModDepth", 0.0, 100.0, 50.0, "%"),
        Param("HighCut", 200.0, 20000.0, 8000.0, "Hz", skew=2.0),
        Param("LowCut", 10.0, 2000.0, 10.0, "Hz", skew=2.0),
        Param("BassMult", 0.25, 4.0, 1.2, "x"),
        Param("BassXover", 100.0, 2000.0, 600.0, "Hz", skew=2.0),
        Param("HighShelf", -24.0, 0.0, -3.0, "dB"),
        Param("HighFreq", 1000.0, 20000.0, 6000.0, "Hz", skew=2.0),
        Param("ColorMode", choices=tuple(COLOR_MODES), default="1980s", aliases=("color",)),
        Param("ReverbMode", choices=tuple(REVERB_MODES), default="Concert Hall", aliases=("mode", "algorithm")),
    )

    def tail_seconds(self):
        return self["PreDelay"] / 1000.0 + self["Decay"] * 1.2 + 0.3

    def render(self, xl, xr, sr):
        s = self.settings
        delays, size_k, ed_k, ld_k, rand, md_k, bright, gate = REVERB_MODES[self.choice("ReverbMode")]
        c_sr, c_bits, c_hc = COLOR_MODES[self.choice("ColorMode")]
        size = (0.3 + 1.4 * s["Size"] / 100.0) * size_k
        high_mult = max(10.0 ** (s["HighShelf"] / 20.0) * bright, 0.05)
        return fdn_reverb(
            xl, xr, sr,
            s["PreDelay"], s["Decay"], size,
            np.array(delays),
            np.array(IN_DIFF), min(0.75 * ed_k * s["EarlyDiffusion"] / 100.0, 0.8),
            s["Attack"] / 100.0, min(0.6 * ld_k * s["LateDiffusion"] / 100.0, 0.75),
            s["ModRate"], 1.5 * md_k * s["ModDepth"] / 100.0, rand,
            s["BassMult"], s["BassXover"], min(high_mult, 1.0), s["HighFreq"],
            s["LowCut"], min(s["HighCut"], c_hc), 1.0,
            -1.0,
            1.0, 0.0, 0,
            np.zeros(0), np.zeros(0), 0.0, 0.0, 1.0,
            gate, c_bits, min(c_sr, sr) if c_sr else 0.0,
        )
