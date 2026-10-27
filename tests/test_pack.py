import json

import numpy as np
import pytest

from valhalla_clone import EFFECTS, get_effect, load_preset, save_preset
from valhalla_clone.cli import main
from valhalla_clone.wavio import read_wav, write_wav

SR = 22050


def burst():
    x = np.zeros((SR // 2, 2))
    x[:500] = np.random.default_rng(1).normal(0, 0.3, (500, 2))
    return x


@pytest.mark.parametrize("name", list(EFFECTS))
def test_every_mode_is_finite_and_bounded(name):
    cls = EFFECTS[name]
    mode = cls.param(cls.MODE_PARAM)
    for choice in mode.choices:
        y = cls(**{mode.name: choice}, Mix=100).process(burst(), SR, tail=0.5)
        assert y.shape == (SR, 2)
        assert np.isfinite(y).all(), choice
        assert 1e-4 < np.abs(y).max() < 4.0, choice


@pytest.mark.parametrize("name", list(EFFECTS))
def test_zero_mix_is_dry(name):
    x = burst()
    y = EFFECTS[name](Mix=0).process(x, SR, tail=0)
    np.testing.assert_allclose(y, x)


def rt60(y):
    e = np.cumsum(y[::-1] ** 2)[::-1]
    edc = 10 * np.log10(e / e[0] + 1e-30)
    return (np.argmax(edc < -35) - np.argmax(edc < -5)) / SR * 2


@pytest.mark.parametrize("name", ["vintageverb", "room", "plate"])
def test_decay_parameter_sets_rt60(name):
    imp = np.zeros(SR * 6)
    imp[0] = 1.0
    extra = {"Depth": 100} if name == "room" else {}
    measured = rt60(get_effect(name)(Mix=100, Decay=3.0, **extra).process(imp, SR, tail=0)[:, 0])
    assert 2.4 < measured < 3.6


def test_freq_echo_shifts_up():
    t = np.arange(SR) / SR
    y = get_effect("freqecho")(Mix=100, Shift=100, Feedback=0).process(np.sin(2 * np.pi * 440 * t), SR, tail=0)
    f = np.abs(np.fft.rfft(y[4000:, 0]))
    peak = np.fft.rfftfreq(len(y) - 4000, 1 / SR)[np.argmax(f)]
    assert abs(peak - 540) < 5


def test_settings_case_insensitive_and_clamped():
    e = get_effect("ValhallaVintageVerb")(decay=500, reverbmode="cathedral", colormode="1970S")
    assert e["Decay"] == 70.0
    assert e.choice("ReverbMode") == "Cathedral"
    assert e.choice("ColorMode") == "1970s"
    with pytest.raises(ValueError):
        e["ReverbMode"] = "no such mode"
    with pytest.raises(KeyError):
        e["Nope"] = 1


def test_copy_identical_settings_between_effects():
    src = get_effect("vintageverb")(Mix=22, PreDelay=40, Decay=7, ModRate=1.5, HighCut=5000, LowCut=100)
    dst = get_effect("room")()
    copied = dst.copy_settings_from(src)
    assert {"Mix", "PreDelay", "Decay", "HighCut", "BassMult", "BassXover"} <= set(copied)
    assert dst["Mix"] == 22 and dst["PreDelay"] == 40 and dst["Decay"] == 7


def test_json_roundtrip(tmp_path):
    e = get_effect("supermassive")(Mode="Andromeda", Delay=900, Feedback=85)
    save_preset(e, tmp_path / "p.json")
    loaded, ignored = load_preset(tmp_path / "p.json")
    assert ignored == [] and loaded.to_dict() == e.to_dict()


def test_vpreset_import_normalized(tmp_path):
    p = tmp_path / "x.vpreset"
    p.write_text(
        '<?xml version="1.0"?>\n<ValhallaVintageVerb pluginVersion="3" presetName="Test" '
        'mix="0.25" decay="0.0" reverbMode="1.0" colorMode="0.5" unknownKnob="0.3"/>'
    )
    e, ignored = load_preset(p)
    assert e.NAME == "vintageverb"
    assert e["Mix"] == 25 and e["Decay"] == 0.2
    assert e.choice("ReverbMode") == "Hall1984" and e.choice("ColorMode") == "1980s"
    assert ignored == ["unknownKnob"]


def test_wav_roundtrip(tmp_path):
    x = np.random.default_rng(0).uniform(-0.9, 0.9, (1000, 2))
    for bits, tol in ((16, 1e-4), (24, 1e-6), (32, 1e-7)):
        write_wav(tmp_path / "a.wav", x, SR, bits)
        y, sr = read_wav(tmp_path / "a.wav")
        assert sr == SR
        np.testing.assert_allclose(y, x, atol=tol)


def test_cli_process_and_bank(tmp_path):
    write_wav(tmp_path / "in.wav", burst(), SR)
    assert main(["process", "delay", "--set", "Mode=BBD", "--set", "Feedback=50",
                 str(tmp_path / "in.wav"), str(tmp_path / "out.wav"), "--tail", "1"]) == 0
    y, _ = read_wav(tmp_path / "out.wav")
    assert y.shape == (SR // 2 + SR, 2)
    assert main(["bank", str(tmp_path / "bank")]) == 0
    files = list((tmp_path / "bank").rglob("*.json"))
    assert len(files) == sum(len(c.param(c.MODE_PARAM).choices) for c in EFFECTS.values())
    assert json.loads(files[0].read_text())["settings"]
