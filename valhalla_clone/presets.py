"""Preset I/O: own JSON presets and import of Valhalla `.vpreset` (XML) files."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .effects import EFFECTS, get_effect
from .params import norm_key

_META_ATTRS = {"pluginversion", "presetname", "version", "name", "author", "category", "comment", "uiwidth", "uiheight"}


def save_preset(effect, path, name: str | None = None):
    data = {"effect": effect.NAME, "title": effect.TITLE, "name": name or Path(path).stem, "settings": effect.to_dict()}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _guess_effect(tag: str):
    key = norm_key(tag)
    try:
        return get_effect(key)
    except KeyError:
        pass
    for name, cls in EFFECTS.items():
        if name in key or norm_key(cls.TITLE) in key:
            return cls
    return None


def read_vpreset(path):
    """Return (effect class or None, {attr: value}) from a Valhalla XML preset."""
    root = ET.parse(path).getroot()
    values = {}
    for k, v in root.attrib.items():
        if norm_key(k) in _META_ATTRS:
            continue
        try:
            values[k] = float(v)
        except ValueError:
            values[k] = v
    return _guess_effect(root.tag), values


def load_preset(path, effect_name: str | None = None, normalized: bool | None = None):
    """Build an effect from a JSON or .vpreset file.

    `.vpreset` files store plug-in parameters as normalised 0..1 values; pass
    `normalized=False` if a file holds plain values instead. Returns
    (effect, ignored_keys).
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace").lstrip()
    if text.startswith("{"):
        data = json.loads(text)
        cls = get_effect(effect_name or data["effect"])
        effect = cls()
        ignored = effect.update(data.get("settings", {}), normalized=bool(normalized))
        return effect, ignored

    cls, values = read_vpreset(path)
    if effect_name:
        cls = get_effect(effect_name)
    if cls is None:
        raise ValueError(f"{path}: cannot tell which effect this preset is for; pass the effect name")
    if normalized is None:
        nums = [v for v in values.values() if isinstance(v, float)]
        normalized = all(0.0 <= v <= 1.0 for v in nums)
    effect = cls()
    ignored = effect.update(values, normalized=normalized)
    return effect, ignored


def export_factory_bank(root):
    """Write an init preset for every mode of every effect; returns the written paths."""
    written = []
    for name, cls in EFFECTS.items():
        mode = cls.param(cls.MODE_PARAM)
        for choice in mode.choices:
            effect = cls(**{mode.name: choice})
            path = Path(root) / name / f"{norm_key(choice)}.json"
            save_preset(effect, path, name=f"{cls.TITLE} - {choice}")
            written.append(path)
    return written
