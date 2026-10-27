"""Registry of all effects in the pack."""

from ..params import norm_key
from .delay import Delay
from .freqecho import FreqEcho
from .plate import Plate
from .room import Room
from .shimmer import Shimmer
from .spacemod import SpaceModulator
from .supermassive import Supermassive
from .ubermod import UberMod
from .vintageverb import VintageVerb

EFFECTS = {
    cls.NAME: cls
    for cls in (VintageVerb, Room, Plate, Shimmer, Supermassive, Delay, FreqEcho, SpaceModulator, UberMod)
}

_ALIASES = {
    "vv": "vintageverb",
    "spacemodulator": "spacemod",
    "valhalladelay": "delay",
    "valhallaroom": "room",
    "valhallaplate": "plate",
    "valhallashimmer": "shimmer",
    "valhallavintageverb": "vintageverb",
    "valhallasupermassive": "supermassive",
    "valhallafreqecho": "freqecho",
    "valhallaspacemodulator": "spacemod",
    "valhallaubermod": "ubermod",
}


def get_effect(name: str):
    key = norm_key(name.replace("Ü", "U").replace("ü", "u"))
    key = _ALIASES.get(key, key)
    if key.startswith("valhalla") and key[8:] in EFFECTS:
        key = key[8:]
    if key not in EFFECTS:
        raise KeyError(f"unknown effect {name!r}; available: {', '.join(EFFECTS)}")
    return EFFECTS[key]


__all__ = ["EFFECTS", "get_effect"] + [cls.__name__ for cls in EFFECTS.values()]
