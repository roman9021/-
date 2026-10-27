"""Command line interface: python -m valhalla_clone <command> ..."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from .effects import EFFECTS, get_effect
from .presets import export_factory_bank, load_preset, save_preset
from .wavio import read_wav, write_wav


def _parse_sets(effect, items):
    for item in items or ():
        if "=" not in item:
            raise SystemExit(f"--set expects Name=Value, got {item!r}")
        k, v = item.split("=", 1)
        try:
            effect[k.strip()] = v.strip()
        except (KeyError, ValueError) as e:
            raise SystemExit(str(e)) from None


def _build(args):
    if Path(args.source).is_file():
        effect, ignored = load_preset(args.source, args.effect, args.normalized)
        if ignored:
            print(f"ignored preset keys: {', '.join(ignored)}", file=sys.stderr)
    else:
        try:
            effect = get_effect(args.source)()
        except KeyError as e:
            raise SystemExit(f"{args.source!r} is neither a preset file nor an effect: {e}") from None
    _parse_sets(effect, args.set)
    return effect


def cmd_list(args):
    for name, cls in EFFECTS.items():
        modes = cls.param(cls.MODE_PARAM).choices
        print(f"{name:<14} {cls.TITLE:<26} {len(modes):>2} modes: {', '.join(modes)}")


def cmd_info(args):
    print(_build(args).describe())


def cmd_process(args):
    effect = _build(args)
    x, sr = read_wav(args.input)
    chain = [effect]
    for extra in args.chain or ():
        e, _ = load_preset(extra)
        chain.append(e)
    y = x
    for e in chain:
        y = e.process(y, sr, tail=args.tail)
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if args.normalize and peak > 0:
        y = y * (10 ** (-1.0 / 20.0) / peak)
    elif peak > 1.0:
        print(f"warning: output peaks at {20 * np.log10(peak):+.1f} dBFS (use --normalize)", file=sys.stderr)
    write_wav(args.output, y, sr, bits=args.bits)
    print(f"{' -> '.join(e.TITLE for e in chain)}: {args.input} -> {args.output} ({len(y) / sr:.2f} s)")


def cmd_save(args):
    effect = _build(args)
    save_preset(effect, args.output)
    print(f"saved {effect.TITLE} preset to {args.output}")


def cmd_copy(args):
    """Copy all shared settings from one preset into another effect."""
    src, _ = load_preset(args.source, args.source_effect, args.normalized)
    dst = get_effect(args.target)()
    if args.base:
        dst, _ = load_preset(args.base, args.target)
    copied = dst.copy_settings_from(src)
    save_preset(dst, args.output)
    print(f"{src.TITLE} -> {dst.TITLE}: copied {', '.join(copied) or 'nothing'}")


def cmd_bank(args):
    paths = export_factory_bank(args.output)
    print(f"wrote {len(paths)} presets to {args.output}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="valhalla_clone", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_source(p):
        p.add_argument("source", help="effect name (e.g. vintageverb) or a JSON / Valhalla .vpreset file")
        p.add_argument("--effect", help="effect a preset file belongs to, if it cannot be detected")
        p.add_argument("--set", action="append", metavar="NAME=VALUE", help="override a parameter")
        g = p.add_mutually_exclusive_group()
        g.add_argument("--normalized", dest="normalized", action="store_true", default=None,
                       help="preset values are 0..1 (default: auto-detect for .vpreset)")
        g.add_argument("--plain", dest="normalized", action="store_false", help="preset values are in real units")

    sub.add_parser("list", help="list effects").set_defaults(fn=cmd_list)

    p = sub.add_parser("info", help="show parameters and current values")
    add_source(p)
    p.set_defaults(fn=cmd_info)

    p = sub.add_parser("process", help="process a WAV file")
    add_source(p)
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--chain", action="append", metavar="PRESET", help="further presets applied in series")
    p.add_argument("--tail", type=float, help="seconds of tail to render (default: from decay/feedback)")
    p.add_argument("--bits", type=int, default=24, choices=(16, 24, 32))
    p.add_argument("--normalize", action="store_true", help="normalise the result to -1 dBFS")
    p.set_defaults(fn=cmd_process)

    p = sub.add_parser("save", help="save settings as a JSON preset")
    add_source(p)
    p.add_argument("output")
    p.set_defaults(fn=cmd_save)

    p = sub.add_parser("copy", help="copy identical settings from one effect's preset into another effect")
    p.add_argument("source", help="source preset (JSON or .vpreset)")
    p.add_argument("target", help="target effect name")
    p.add_argument("output", help="JSON preset to write")
    p.add_argument("--source-effect", help="effect of the source preset if it cannot be detected")
    p.add_argument("--base", help="start from this target preset instead of defaults")
    p.add_argument("--normalized", action="store_true", default=None)
    p.set_defaults(fn=cmd_copy)

    p = sub.add_parser("bank", help="export a default preset for every mode of every effect")
    p.add_argument("output", nargs="?", default="presets")
    p.set_defaults(fn=cmd_bank)

    args = ap.parse_args(argv)
    args.fn(args)
    return 0
