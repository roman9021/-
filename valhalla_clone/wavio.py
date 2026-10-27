"""Minimal WAV reader/writer (PCM 16/24/32-bit and IEEE float) using only numpy."""

import struct

import numpy as np


def read_wav(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError(f"{path}: not a RIFF/WAVE file")
    pos = 12
    fmt = None
    frames = None
    while pos + 8 <= len(data):
        cid, size = struct.unpack("<4sI", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            tag, ch, sr, _, _, bits = struct.unpack("<HHIIHH", body[:16])
            if tag == 0xFFFE and len(body) >= 26:  # WAVE_FORMAT_EXTENSIBLE
                tag = struct.unpack("<H", body[24:26])[0]
            fmt = (tag, ch, sr, bits)
        elif cid == b"data":
            frames = body
        pos += 8 + size + (size & 1)
    if fmt is None or frames is None:
        raise ValueError(f"{path}: missing fmt or data chunk")
    tag, ch, sr, bits = fmt
    if tag == 3:
        x = np.frombuffer(frames, dtype="<f4" if bits == 32 else "<f8").astype(np.float64)
    elif tag == 1 and bits == 16:
        x = np.frombuffer(frames, dtype="<i2") / 32768.0
    elif tag == 1 and bits == 24:
        b = np.frombuffer(frames[: len(frames) // 3 * 3], dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        x = np.where(v >= 1 << 23, v - (1 << 24), v) / 8388608.0
    elif tag == 1 and bits == 32:
        x = np.frombuffer(frames, dtype="<i4") / 2147483648.0
    elif tag == 1 and bits == 8:
        x = (np.frombuffer(frames, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    else:
        raise ValueError(f"{path}: unsupported WAV format (tag {tag}, {bits} bit)")
    x = x[: len(x) // ch * ch].reshape(-1, ch)
    return x, sr


def write_wav(path, audio, sr, bits=24):
    x = np.asarray(audio, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    ch = x.shape[1]
    if bits == 32:
        tag, payload = 3, x.astype("<f4").tobytes()
    elif bits == 16:
        tag, payload = 1, (np.clip(x, -1.0, 1.0) * 32767.0).round().astype("<i2").tobytes()
    elif bits == 24:
        v = (np.clip(x, -1.0, 1.0) * 8388607.0).round().astype(np.int32).reshape(-1)
        b = np.empty((v.size, 3), dtype=np.uint8)
        b[:, 0] = v & 0xFF
        b[:, 1] = (v >> 8) & 0xFF
        b[:, 2] = (v >> 16) & 0xFF
        tag, payload = 1, b.tobytes()
    else:
        raise ValueError("bits must be 16, 24 or 32 (float)")
    block = ch * bits // 8
    fmt = struct.pack("<HHIIHH", tag, ch, int(sr), int(sr) * block, block, bits)
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 4 + 8 + len(fmt) + 8 + len(payload) + (len(payload) & 1)) + b"WAVE")
        f.write(b"fmt " + struct.pack("<I", len(fmt)) + fmt)
        f.write(b"data" + struct.pack("<I", len(payload)) + payload)
        if len(payload) & 1:
            f.write(b"\0")
