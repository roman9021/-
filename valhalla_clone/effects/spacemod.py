"""Valhalla Space Modulator-style flanger / chorus."""

from ..dsp import space_mod
from ..params import Param, mix_param
from .base import Effect

MODES = ("Flange", "ThruZero", "Barberpole Up", "Barberpole Down", "Chorus", "Doubler", "Vibrato")


class SpaceModulator(Effect):
    NAME = "spacemod"
    TITLE = "Valhalla Space Modulator"
    PARAMS = (
        mix_param(50.0),
        Param("Rate", 0.01, 10.0, 0.25, "Hz", skew=2.0),
        Param("Depth", 0.0, 100.0, 50.0, "%"),
        Param("Feedback", -99.0, 99.0, 50.0, "%"),
        Param("Manual", 0.0, 10.0, 0.5, "ms"),
        Param("Width", 0.0, 100.0, 50.0, "%"),
        Param("Mode", choices=MODES, default="Flange"),
    )

    def tail_seconds(self):
        return 0.1 + 0.3 * abs(self["Feedback"]) / 99.0

    def render(self, xl, xr, sr):
        s = self.settings
        return space_mod(
            xl, xr, sr, s["Rate"], s["Depth"] / 100.0, s["Feedback"] / 100.0, s["Manual"],
            s["Width"] / 100.0, s["Mode"], 10.0,
        )
