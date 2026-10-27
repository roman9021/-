"""DSP clones of the Valhalla DSP plug-in pack with matching parameter sets."""

from .effects import EFFECTS, get_effect
from .presets import load_preset, save_preset

__all__ = ["EFFECTS", "get_effect", "load_preset", "save_preset"]
