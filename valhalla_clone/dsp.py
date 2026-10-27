"""Sample-level DSP kernels.

Every kernel is a plain function over float64 arrays and scalars so numba can
compile it; the effect classes translate user-facing settings into these
arguments.  The algorithms are original textbook structures (feedback delay
networks, Dattorro's plate, Hilbert frequency shifting, delay-line pitch
shifting) tuned to follow the parameter set of each Valhalla plug-in.
"""

import math

import numpy as np

from ._jit import jit

TWO_PI = 2.0 * math.pi


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


@jit
def lp_coef(fc, sr):
    """Pole of a one-pole low-pass: y += (1 - a) * (x - y)."""
    fc = min(max(fc, 1.0), 0.49 * sr)
    return math.exp(-TWO_PI * fc / sr)


@jit
def read_frac(buf, w, delay):
    """Read `delay` samples behind write index `w` with linear interpolation."""
    n = buf.shape[0]
    pos = w - delay
    while pos < 0.0:
        pos += n
    i = int(pos)
    frac = pos - i
    if i >= n:
        i -= n
    j = i + 1
    if j >= n:
        j = 0
    return buf[i] * (1.0 - frac) + buf[j] * frac


@jit
def read_frac_row(buf, row, w, delay):
    n = buf.shape[1]
    pos = w - delay
    while pos < 0.0:
        pos += n
    i = int(pos)
    frac = pos - i
    if i >= n:
        i -= n
    j = i + 1
    if j >= n:
        j = 0
    return buf[row, i] * (1.0 - frac) + buf[row, j] * frac


@jit
def soft_clip(x):
    return math.tanh(x)


@jit
def hadamard(v):
    """In-place orthonormal fast Walsh-Hadamard transform (len must be a power of two)."""
    n = v.shape[0]
    h = 1
    while h < n:
        for i in range(0, n, h * 2):
            for j in range(i, i + h):
                a = v[j]
                b = v[j + h]
                v[j] = a + b
                v[j + h] = a - b
        h *= 2
    s = 1.0 / math.sqrt(n)
    for i in range(n):
        v[i] *= s


@jit
def pitch_tick(buf, w, phase, ratio, window):
    """Two-grain delay-line pitch shifter.

    `buf` must already contain the current input at index `w`.  `phase` is a
    1-element array holding the grain phase; returns the shifted sample.
    """
    p = phase[0]
    d1 = 1.0 + p * window
    p2 = p + 0.5
    if p2 >= 1.0:
        p2 -= 1.0
    d2 = 1.0 + p2 * window
    y = read_frac(buf, w, d1) * math.sin(math.pi * p) + read_frac(buf, w, d2) * math.sin(math.pi * p2)
    p += (1.0 - ratio) / window
    while p >= 1.0:
        p -= 1.0
    while p < 0.0:
        p += 1.0
    phase[0] = p
    return y * 0.7071


@jit
def decay_gain(delay_samples, rt60, sr):
    if rt60 <= 0.0:
        return 0.0
    return 10.0 ** (-3.0 * delay_samples / (rt60 * sr))


# --------------------------------------------------------------------------
# feedback delay network reverb (VintageVerb, Room, Shimmer, Supermassive)
# --------------------------------------------------------------------------


@jit
def fdn_reverb(
    xl, xr, sr,
    predelay_ms, rt60, size,
    delays_ms,
    in_diff_ms, in_diff_gain,
    attack, loop_diff_gain,
    mod_rate, mod_depth_ms, mod_random,
    bass_mult, bass_xover, high_mult, high_xover,
    lowcut, highcut, width,
    fb_override,
    shift_ratio, shift_amount, shift_stereo,
    er_taps_ms, er_gains, er_level, er_send, late_level,
    gate_time, color_bits, color_sr,
    rand_rate=0.0, er_mod_rate=0.0, er_mod_depth_ms=0.0, er_width=1.0,
):
    n = xl.shape[0]
    nl = delays_ms.shape[0]
    yl = np.zeros(n)
    yr = np.zeros(n)

    # pre-delay line also feeds the early-reflection taps
    er_max = 0.0
    for k in range(er_taps_ms.shape[0]):
        er_max = max(er_max, er_taps_ms[k])
    pd = predelay_ms * sr / 1000.0
    er_md = er_mod_depth_ms * sr / 1000.0
    pre_len = int(pd + er_max * sr / 1000.0 + 2.0 * er_md) + 4
    er_ph = 0.0
    pre_l = np.zeros(pre_len)
    pre_r = np.zeros(pre_len)
    pw = 0

    # input diffusion: 4 allpasses per channel, plus 2 "attack" smearing stages
    nd = in_diff_ms.shape[0]
    diff_len = np.zeros(nd + 2, dtype=np.int64)
    for k in range(nd):
        diff_len[k] = max(1, int(in_diff_ms[k] * math.sqrt(size) * sr / 1000.0))
    diff_len[nd] = max(1, int((7.0 + 90.0 * attack) * sr / 1000.0))
    diff_len[nd + 1] = max(1, int((11.0 + 140.0 * attack) * sr / 1000.0))
    dmax = 1
    for k in range(nd + 2):
        dmax = max(dmax, int(diff_len[k]) + 1)
    dbuf = np.zeros((2 * (nd + 2), dmax))
    didx = np.zeros(2 * (nd + 2), dtype=np.int64)
    att_gain = 0.72 * attack

    # delay lines
    dl = np.zeros(nl)
    for i in range(nl):
        dl[i] = max(4.0, delays_ms[i] * size * sr / 1000.0)
    mdepth = mod_depth_ms * sr / 1000.0
    lmax = 0
    for i in range(nl):
        lmax = max(lmax, int(dl[i] + mdepth * 1.5) + 4)
    lines = np.zeros((nl, lmax))
    lw = 0
    # in-loop allpasses
    ap_len = np.zeros(nl, dtype=np.int64)
    for i in range(nl):
        ap_len[i] = max(1, int(dl[i] * 0.23))
    apmax = 1
    for i in range(nl):
        apmax = max(apmax, int(ap_len[i]) + 1)
    apbuf = np.zeros((nl, apmax))
    apidx = np.zeros(nl, dtype=np.int64)

    # per-line gains for three bands
    g_lo = np.zeros(nl)
    g_mid = np.zeros(nl)
    g_hi = np.zeros(nl)
    for i in range(nl):
        # an allpass of length L adds L samples of average group delay to the loop
        loop_len = dl[i] + (ap_len[i] if loop_diff_gain != 0.0 else 0)
        if fb_override >= 0.0:
            g_mid[i] = fb_override
            g_lo[i] = min(fb_override * bass_mult, 0.9995)
            g_hi[i] = fb_override * min(high_mult, 1.0)
        else:
            g_mid[i] = decay_gain(loop_len, rt60, sr)
            g_lo[i] = decay_gain(loop_len, rt60 * bass_mult, sr)
            g_hi[i] = decay_gain(loop_len, rt60 * high_mult, sr)
    a_bx = lp_coef(bass_xover, sr)
    a_hx = lp_coef(max(high_xover, bass_xover * 1.5), sr)
    s_bx = np.zeros(nl)
    s_hx = np.zeros(nl)

    # modulation: one LFO per line, optionally with slow random wander
    phase = np.zeros(nl)
    for i in range(nl):
        phase[i] = i / nl
    rnd = np.zeros(nl)
    rnd_t = np.zeros(nl)
    seed = 12345

    # shimmer pitch shifter
    ps_len = int(0.25 * sr) + 4
    ps_buf_l = np.zeros(ps_len)
    ps_buf_r = np.zeros(ps_len)
    ps_ph_l = np.zeros(1)
    ps_ph_r = np.zeros(1)
    ps_ph_r[0] = 0.25
    ps_w = 0
    ps_win = 0.1 * sr
    ps_hp = np.zeros(2)
    a_pshp = lp_coef(120.0, sr)

    # output filters / colour
    a_lc = lp_coef(lowcut, sr)
    a_hc = lp_coef(highcut, sr)
    olc = np.zeros(2)
    ohc1 = np.zeros(2)
    ohc2 = np.zeros(2)
    hold_ctr = 0.0
    hold_l = 0.0
    hold_r = 0.0
    q = 2.0 ** (color_bits - 1) if color_bits > 0 else 0.0

    # non-linear gate
    env = 0.0
    gate = 0.0
    gate_left = 0.0
    a_env = lp_coef(30.0, sr)
    a_gate = lp_coef(60.0, sr)

    v = np.zeros(nl)
    outv = np.zeros(nl)
    last_l = 0.0
    last_r = 0.0
    in_scale = 1.0 / math.sqrt(nl / 2.0)
    out_scale = 1.0 / math.sqrt(nl)

    for t in range(n):
        # pre-delay + early reflections
        pre_l[pw] = xl[t]
        pre_r[pw] = xr[t]
        il = read_frac(pre_l, pw, pd)
        ir = read_frac(pre_r, pw, pd)
        el = 0.0
        er = 0.0
        for k in range(er_taps_ms.shape[0]):
            d = pd + er_taps_ms[k] * sr / 1000.0 + er_md * (1.0 + math.sin(TWO_PI * (er_ph + 0.137 * k)))
            if k % 2 == 0:
                el += read_frac(pre_l, pw, d) * er_gains[k]
            else:
                er += read_frac(pre_r, pw, d) * er_gains[k]
        er_ph += er_mod_rate / sr
        if er_ph >= 1.0:
            er_ph -= 1.0
        if er_width < 1.0:
            em = 0.5 * (el + er)
            es = 0.5 * (el - er) * er_width
            el = em + es
            er = em - es
        pw += 1
        if pw >= pre_len:
            pw = 0

        sl = il + er_send * el
        sr_ = ir + er_send * er
        # input diffusion chains (left uses even buffers, right odd)
        for k in range(nd + 2):
            g = in_diff_gain if k < nd else att_gain
            if g == 0.0:
                continue
            L = diff_len[k]
            for c in range(2):
                b = 2 * k + c
                idx = didx[b]
                rd = idx - L
                if rd < 0:
                    rd += dmax
                dv = dbuf[b, rd]
                x = sl if c == 0 else sr_
                wv = x + g * dv
                y = dv - g * wv
                dbuf[b, idx] = wv
                idx += 1
                if idx >= dmax:
                    idx = 0
                didx[b] = idx
                if c == 0:
                    sl = y
                else:
                    sr_ = y

        # shimmer: pitch-shift the previous tank output and re-inject it
        sh_l = 0.0
        sh_r = 0.0
        if shift_amount > 0.0:
            ps_buf_l[ps_w] = last_l
            ps_buf_r[ps_w] = last_r
            sh_l = pitch_tick(ps_buf_l, ps_w, ps_ph_l, shift_ratio, ps_win)
            sh_r = pitch_tick(ps_buf_r, ps_w, ps_ph_r, shift_ratio, ps_win)
            ps_w += 1
            if ps_w >= ps_len:
                ps_w = 0
            if shift_stereo == 0:
                m = 0.5 * (sh_l + sh_r)
                sh_l = m
                sh_r = m
            # keep low end out of the shimmer loop
            ps_hp[0] = a_pshp * ps_hp[0] + (1.0 - a_pshp) * sh_l
            ps_hp[1] = a_pshp * ps_hp[1] + (1.0 - a_pshp) * sh_r
            sh_l = soft_clip((sh_l - ps_hp[0]) * shift_amount)
            sh_r = soft_clip((sh_r - ps_hp[1]) * shift_amount)

        # read lines, loop allpass, damping
        for i in range(nl):
            if mod_random > 0.0:
                rnd_t[i] -= 1.0
                if rnd_t[i] <= 0.0:
                    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
                    rnd[i] = (seed / 2147483647.0) * 2.0 - 1.0
                    rnd_t[i] = sr / max(rand_rate if rand_rate > 0.0 else mod_rate * 4.0, 0.05)
            lfo = math.sin(TWO_PI * phase[i])
            phase[i] += mod_rate * (1.0 + 0.07 * i) / sr
            if phase[i] >= 1.0:
                phase[i] -= 1.0
            md = mdepth * ((1.0 - mod_random) * lfo + mod_random * rnd[i])
            x = read_frac_row(lines, i, lw, dl[i] + md + mdepth * 0.5 + 1.0)

            if loop_diff_gain != 0.0:
                L = ap_len[i]
                idx = apidx[i]
                rd = idx - L
                if rd < 0:
                    rd += apmax
                dv = apbuf[i, rd]
                wv = x + loop_diff_gain * dv
                x = dv - loop_diff_gain * wv
                apbuf[i, idx] = wv
                idx += 1
                if idx >= apmax:
                    idx = 0
                apidx[i] = idx

            s_bx[i] = a_bx * s_bx[i] + (1.0 - a_bx) * x
            s_hx[i] = a_hx * s_hx[i] + (1.0 - a_hx) * x
            lo = s_bx[i]
            mid = s_hx[i] - lo
            hi = x - s_hx[i]
            outv[i] = x
            v[i] = lo * g_lo[i] + mid * g_mid[i] + hi * g_hi[i]

        hadamard(v)
        for i in range(nl):
            inj = (sl + sh_l) if i % 2 == 0 else (sr_ + sh_r)
            lines[i, lw] = v[i] + inj * in_scale
        lw += 1
        if lw >= lmax:
            lw = 0

        ol = 0.0
        orr = 0.0
        for i in range(nl):
            ol += outv[i] * (1.0 if i % 2 == 0 else -1.0)
            orr += outv[i] * (1.0 if (i // 2) % 2 == 0 else -1.0)
        ol *= out_scale
        orr *= out_scale
        last_l = ol
        last_r = orr

        # stereo width
        mm = 0.5 * (ol + orr)
        ss = 0.5 * (ol - orr) * width
        ol = mm + ss
        orr = mm - ss
        ol = late_level * ol + er_level * el
        orr = late_level * orr + er_level * er

        # gated / non-linear envelope
        if gate_time > 0.0:
            lvl = abs(xl[t]) + abs(xr[t])
            env = a_env * env + (1.0 - a_env) * lvl
            if env > 0.01:
                gate_left = gate_time * sr
            target = 1.0 if gate_left > 0.0 else 0.0
            gate_left -= 1.0
            gate = a_gate * gate + (1.0 - a_gate) * target
            ol *= gate
            orr *= gate

        # colour: sample-rate and bit-depth reduction
        if color_sr > 0.0:
            hold_ctr += color_sr / sr
            if hold_ctr >= 1.0:
                hold_ctr -= 1.0
                hold_l = ol
                hold_r = orr
                if q > 0.0:
                    hold_l = math.floor(hold_l * q + 0.5) / q
                    hold_r = math.floor(hold_r * q + 0.5) / q
            ol = hold_l
            orr = hold_r

        # output EQ
        olc[0] = a_lc * olc[0] + (1.0 - a_lc) * ol
        olc[1] = a_lc * olc[1] + (1.0 - a_lc) * orr
        ol -= olc[0]
        orr -= olc[1]
        ohc1[0] = a_hc * ohc1[0] + (1.0 - a_hc) * ol
        ohc1[1] = a_hc * ohc1[1] + (1.0 - a_hc) * orr
        ohc2[0] = a_hc * ohc2[0] + (1.0 - a_hc) * ohc1[0]
        ohc2[1] = a_hc * ohc2[1] + (1.0 - a_hc) * ohc1[1]
        yl[t] = ohc2[0]
        yr[t] = ohc2[1]
    return yl, yr


# --------------------------------------------------------------------------
# Dattorro plate (ValhallaPlate)
# --------------------------------------------------------------------------


@jit
def _ap_step(buf, w, L, g, x):
    n = buf.shape[0]
    rd = w - L
    if rd < 0:
        rd += n
    dv = buf[rd]
    wv = x + g * dv
    buf[w] = wv
    return dv - g * wv


@jit
def _tap(buf, w, d):
    n = buf.shape[0]
    i = w - d
    while i < 0:
        i += n
    return buf[i]


@jit
def plate_reverb(
    xl, xr, sr, predelay_ms, rt60, size, width,
    bandwidth, damping, in_diff1, in_diff2, dec_diff1, dec_diff2,
    mod_rate, mod_depth, lowcut, highcut, bass_mult, bass_xover,
):
    n = xl.shape[0]
    yl = np.zeros(n)
    yr = np.zeros(n)
    k = sr / 29761.0
    ks = k * size

    pd = predelay_ms * sr / 1000.0
    pre_len = int(pd) + 4
    pre = np.zeros(pre_len)
    pw = 0

    i1 = max(1, int(142 * k))
    i2 = max(1, int(107 * k))
    i3 = max(1, int(379 * k))
    i4 = max(1, int(277 * k))
    b_i1 = np.zeros(i1 + 1)
    b_i2 = np.zeros(i2 + 1)
    b_i3 = np.zeros(i3 + 1)
    b_i4 = np.zeros(i4 + 1)
    w_i = np.zeros(4, dtype=np.int64)

    md = mod_depth * k
    ma = 672.0 * ks
    mb = 908.0 * ks
    la1 = int(4453 * ks) + 1
    la2 = int(1800 * ks) + 1
    la3 = int(3720 * ks) + 1
    lb1 = int(4217 * ks) + 1
    lb2 = int(2656 * ks) + 1
    lb3 = int(3163 * ks) + 1
    b_ma = np.zeros(int(ma + md) + 4)
    b_mb = np.zeros(int(mb + md) + 4)
    b_a1 = np.zeros(la1 + 1)
    b_a2 = np.zeros(la2 + 1)
    b_a3 = np.zeros(la3 + 1)
    b_b1 = np.zeros(lb1 + 1)
    b_b2 = np.zeros(lb2 + 1)
    b_b3 = np.zeros(lb3 + 1)
    w_ma = 0
    w_mb = 0
    w_a1 = 0
    w_a2 = 0
    w_a3 = 0
    w_b1 = 0
    w_b2 = 0
    w_b3 = 0

    # each half of the tank applies the decay gain twice
    half = (672.0 + 4453.0 + 1800.0 + 3720.0) * ks
    g = decay_gain(half / 2.0, rt60, sr)
    g_lo = min(decay_gain(half / 2.0, rt60 * bass_mult, sr), 0.9995)
    a_bx = lp_coef(bass_xover, sr)

    bw_state = 0.0
    da = 0.0
    db = 0.0
    bx_a = 0.0
    bx_b = 0.0
    fb_a = 0.0
    fb_b = 0.0
    ph = 0.0

    a_lc = lp_coef(lowcut, sr)
    a_hc = lp_coef(highcut, sr)
    lc = np.zeros(2)
    hc = np.zeros(2)

    def_taps = np.array([266, 2974, 1913, 1996, 1990, 187, 1066, 353, 3627, 1228, 2673, 2111, 335, 121])
    taps = np.zeros(14, dtype=np.int64)
    for i in range(14):
        taps[i] = max(1, int(def_taps[i] * ks))

    for t in range(n):
        pre[pw] = 0.5 * (xl[t] + xr[t])
        x = _tap(pre, pw, int(pd)) if pd >= 1.0 else pre[pw]
        pw += 1
        if pw >= pre_len:
            pw = 0

        bw_state += bandwidth * (x - bw_state)
        x = bw_state
        x = _ap_step(b_i1, w_i[0], i1, in_diff1, x)
        x = _ap_step(b_i2, w_i[1], i2, in_diff1, x)
        x = _ap_step(b_i3, w_i[2], i3, in_diff2, x)
        x = _ap_step(b_i4, w_i[3], i4, in_diff2, x)
        w_i[0] = (w_i[0] + 1) % b_i1.shape[0]
        w_i[1] = (w_i[1] + 1) % b_i2.shape[0]
        w_i[2] = (w_i[2] + 1) % b_i3.shape[0]
        w_i[3] = (w_i[3] + 1) % b_i4.shape[0]

        lfo = math.sin(TWO_PI * ph)
        ph += mod_rate / sr
        if ph >= 1.0:
            ph -= 1.0

        # half A
        a_in = x + fb_b
        dv = read_frac(b_ma, w_ma, ma + md * lfo + md + 1.0)
        wv = a_in - dec_diff1 * dv  # Dattorro uses a negated coefficient here
        b_ma[w_ma] = wv
        a = dv + dec_diff1 * wv
        w_ma = (w_ma + 1) % b_ma.shape[0]
        b_a1[w_a1] = a
        a = _tap(b_a1, w_a1, la1 - 1)
        da += (1.0 - damping) * (a - da)
        bx_a = a_bx * bx_a + (1.0 - a_bx) * da
        a = bx_a * g_lo + (da - bx_a) * g
        a = _ap_step(b_a2, w_a2, la2 - 1, dec_diff2, a)
        b_a3[w_a3] = a
        fb_a = _tap(b_a3, w_a3, la3 - 1) * g

        # half B
        b_in = x + fb_a
        dv = read_frac(b_mb, w_mb, mb - md * lfo + md + 1.0)
        wv = b_in - dec_diff1 * dv
        b_mb[w_mb] = wv
        b = dv + dec_diff1 * wv
        w_mb = (w_mb + 1) % b_mb.shape[0]
        b_b1[w_b1] = b
        b = _tap(b_b1, w_b1, lb1 - 1)
        db += (1.0 - damping) * (b - db)
        bx_b = a_bx * bx_b + (1.0 - a_bx) * db
        b = bx_b * g_lo + (db - bx_b) * g
        b = _ap_step(b_b2, w_b2, lb2 - 1, dec_diff2, b)
        b_b3[w_b3] = b
        fb_b = _tap(b_b3, w_b3, lb3 - 1) * g

        ol = (
            _tap(b_b1, w_b1, taps[0]) + _tap(b_b1, w_b1, taps[1]) - _tap(b_b2, w_b2, taps[2])
            + _tap(b_b3, w_b3, taps[3]) - _tap(b_a1, w_a1, taps[4]) - _tap(b_a2, w_a2, taps[5])
            - _tap(b_a3, w_a3, taps[6])
        )
        orr = (
            _tap(b_a1, w_a1, taps[7]) + _tap(b_a1, w_a1, taps[8]) - _tap(b_a2, w_a2, taps[9])
            + _tap(b_a3, w_a3, taps[10]) - _tap(b_b1, w_b1, taps[11]) - _tap(b_b2, w_b2, taps[12])
            - _tap(b_b3, w_b3, taps[13])
        )
        w_a1 = (w_a1 + 1) % b_a1.shape[0]
        w_a2 = (w_a2 + 1) % b_a2.shape[0]
        w_a3 = (w_a3 + 1) % b_a3.shape[0]
        w_b1 = (w_b1 + 1) % b_b1.shape[0]
        w_b2 = (w_b2 + 1) % b_b2.shape[0]
        w_b3 = (w_b3 + 1) % b_b3.shape[0]

        ol *= 0.6
        orr *= 0.6
        mm = 0.5 * (ol + orr)
        ss = 0.5 * (ol - orr) * width
        ol = mm + ss
        orr = mm - ss
        lc[0] = a_lc * lc[0] + (1.0 - a_lc) * ol
        lc[1] = a_lc * lc[1] + (1.0 - a_lc) * orr
        ol -= lc[0]
        orr -= lc[1]
        hc[0] = a_hc * hc[0] + (1.0 - a_hc) * ol
        hc[1] = a_hc * hc[1] + (1.0 - a_hc) * orr
        yl[t] = hc[0]
        yr[t] = hc[1]
    return yl, yr


# --------------------------------------------------------------------------
# tape / BBD / digital echo (ValhallaDelay)
# --------------------------------------------------------------------------


@jit
def echo_delay(
    xl, xr, sr, delay_l_ms, delay_r_ms, feedback, style,
    width, age, drive, diffusion, ducking,
    mod_rate, mod_depth_ms, flutter,
    lowcut, highcut, bbd, digital_bits,
    pitch_ratio, pitch_amount, noise,
):
    """style: 0 single (mono sum), 1 dual (independent L/R), 2 ping-pong."""
    n = xl.shape[0]
    yl = np.zeros(n)
    yr = np.zeros(n)
    dL = max(1.0, delay_l_ms * sr / 1000.0)
    dR = max(1.0, delay_r_ms * sr / 1000.0)
    mdepth = mod_depth_ms * sr / 1000.0
    ln = int(max(dL, dR) + mdepth * 2.0 + 0.12 * sr) + 8
    bl = np.zeros(ln)
    br = np.zeros(ln)
    w = 0

    # diffusion allpasses in the feedback path (two per side)
    ap_l = np.array([0.0071, 0.0113]) * sr
    dbuf = np.zeros((4, int(0.0113 * 1.2 * sr) + 3))
    dw = np.zeros(4, dtype=np.int64)

    # age: progressively darker repeats; BBD bandwidth falls with delay time
    hc = highcut * (1.0 - 0.8 * age)
    if bbd > 0:
        hc = min(hc, 2.0e5 / max(delay_l_ms, 10.0) + 2500.0)
    a_hc = lp_coef(hc, sr)
    a_lc = lp_coef(lowcut, sr)
    fl = np.zeros(4)

    ps_len = int(0.2 * sr) + 4
    ps_l = np.zeros(ps_len)
    ps_r = np.zeros(ps_len)
    ph_l = np.zeros(1)
    ph_r = np.zeros(1)
    ph_r[0] = 0.5
    ps_w = 0
    ps_win = 0.08 * sr

    env = 0.0
    a_env = lp_coef(8.0, sr)
    ph = 0.0
    ph2 = 0.0
    seed = 22222
    q = 2.0 ** (digital_bits - 1) if digital_bits > 0 else 0.0
    pre_gain = 1.0 + 6.0 * drive

    for t in range(n):
        inl = xl[t]
        inr = xr[t]
        if style == 0:
            m = 0.5 * (inl + inr)
            inl = m
            inr = m
        elif style == 2:
            inl = 0.5 * (xl[t] + xr[t])
            inr = 0.0

        lfo = math.sin(TWO_PI * ph) + flutter * 0.3 * math.sin(TWO_PI * ph2)
        ph += mod_rate / sr
        ph2 += (mod_rate * 7.3 + 5.0) / sr
        if ph >= 1.0:
            ph -= 1.0
        if ph2 >= 1.0:
            ph2 -= 1.0
        m_off = mdepth * (1.0 + lfo)
        dl_ = read_frac(bl, w, dL + m_off + 1.0)
        dr_ = read_frac(br, w, dR + m_off * 0.97 + 1.0)

        # feedback processing
        fbl = dl_
        fbr = dr_
        for c in range(2):
            x = fbl if c == 0 else fbr
            fl[c] = a_lc * fl[c] + (1.0 - a_lc) * x
            x -= fl[c]
            fl[2 + c] = a_hc * fl[2 + c] + (1.0 - a_hc) * x
            x = fl[2 + c]
            if diffusion > 0.0:
                for k in range(2):
                    b = 2 * c + k
                    L = int(ap_l[k] * (1.0 + 0.13 * c))
                    x = _ap_step(dbuf[b], dw[b], L, diffusion * 0.7, x)
                    dw[b] += 1
                    if dw[b] >= dbuf.shape[1]:
                        dw[b] = 0
            if drive > 0.0 or age > 0.0:
                x = soft_clip(x * pre_gain) / pre_gain if drive > 0.0 else soft_clip(x)
            if noise > 0.0:
                seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
                x += noise * age * 0.002 * ((seed / 2147483647.0) - 0.5)
            if q > 0.0:
                x = math.floor(x * q + 0.5) / q
            if c == 0:
                fbl = x
            else:
                fbr = x

        if pitch_amount > 0.0:
            ps_l[ps_w] = fbl
            ps_r[ps_w] = fbr
            pl = pitch_tick(ps_l, ps_w, ph_l, pitch_ratio, ps_win)
            pr = pitch_tick(ps_r, ps_w, ph_r, pitch_ratio, ps_win)
            ps_w += 1
            if ps_w >= ps_len:
                ps_w = 0
            fbl = fbl * (1.0 - pitch_amount) + pl * pitch_amount
            fbr = fbr * (1.0 - pitch_amount) + pr * pitch_amount

        if style == 2:
            bl[w] = inl + feedback * fbr
            br[w] = inr + feedback * fbl
        else:
            bl[w] = inl + feedback * fbl
            br[w] = inr + feedback * fbr
        w += 1
        if w >= ln:
            w = 0

        env = a_env * env + (1.0 - a_env) * (abs(xl[t]) + abs(xr[t]))
        duck = 1.0 / (1.0 + ducking * env * 20.0)
        mm = 0.5 * (dl_ + dr_)
        ss = 0.5 * (dl_ - dr_) * width
        yl[t] = (mm + ss) * duck
        yr[t] = (mm - ss) * duck
    return yl, yr


# --------------------------------------------------------------------------
# frequency shifting echo (Freq Echo)
# --------------------------------------------------------------------------

_HILB_A = np.array([0.6923878, 0.9360654322959, 0.9882295226860, 0.9987488452737])
_HILB_B = np.array([0.4021921162426, 0.8561710882420, 0.9722909545651, 0.9952884791278])


@jit
def _hilbert_chain(coefs, state, x):
    """Four 2nd-order allpasses; state rows hold (x1, x2, y1, y2)."""
    for k in range(4):
        c = coefs[k] * coefs[k]
        y = c * (x + state[k, 3]) - state[k, 1]
        state[k, 1] = state[k, 0]
        state[k, 0] = x
        state[k, 3] = state[k, 2]
        state[k, 2] = y
        x = y
    return x


@jit
def freq_echo(xl, xr, sr, delay_ms, feedback, shift_hz, width, lowcut, highcut, analog, ca, cb):
    n = xl.shape[0]
    yl = np.zeros(n)
    yr = np.zeros(n)
    d = max(1.0, delay_ms * sr / 1000.0)
    ln = int(d) + 8
    bl = np.zeros(ln)
    br = np.zeros(ln)
    w = 0
    sa = np.zeros((2, 4, 4))
    sb = np.zeros((2, 4, 4))
    bprev = np.zeros(2)
    ph = 0.0
    a_lc = lp_coef(lowcut, sr)
    a_hc = lp_coef(highcut * (0.6 if analog else 1.0), sr)
    f = np.zeros(4)
    out = np.zeros(2)
    for t in range(n):
        rl = read_frac(bl, w, d)
        rr = read_frac(br, w, d)
        ph += shift_hz / sr
        ph -= math.floor(ph)
        for c in range(2):
            # the right channel's oscillator is offset by up to 90 degrees for width
            pc = ph + (0.25 * width if c == 1 else 0.0)
            cs = math.cos(TWO_PI * pc)
            sn = math.sin(TWO_PI * pc)
            x = rl if c == 0 else rr
            re = _hilbert_chain(ca, sa[c], x)
            im_now = _hilbert_chain(cb, sb[c], x)
            im = bprev[c]
            bprev[c] = im_now
            s = re * cs + im * sn
            f[c] = a_lc * f[c] + (1.0 - a_lc) * s
            s -= f[c]
            f[2 + c] = a_hc * f[2 + c] + (1.0 - a_hc) * s
            s = f[2 + c]
            if analog:
                s = soft_clip(s * 1.5) / 1.5
            out[c] = s
        bl[w] = xl[t] + feedback * out[0]
        br[w] = xr[t] + feedback * out[1]
        w += 1
        if w >= ln:
            w = 0
        yl[t] = out[0]
        yr[t] = out[1]
    return yl, yr


# --------------------------------------------------------------------------
# flanger / chorus / barber-pole (Space Modulator)
# --------------------------------------------------------------------------


@jit
def space_mod(xl, xr, sr, rate, depth, feedback, manual_ms, width, mode, max_ms):
    """mode: 0 flange, 1 through-zero, 2 barberpole up, 3 barberpole down,
    4 chorus, 5 doubler, 6 vibrato."""
    n = xl.shape[0]
    yl = np.zeros(n)
    yr = np.zeros(n)
    ln = int((max_ms * 2.0 + 45.0) * sr / 1000.0) + 8
    bl = np.zeros(ln)
    br = np.zeros(ln)
    w = 0
    ph = 0.0
    fbl = 0.0
    fbr = 0.0
    man = manual_ms * sr / 1000.0
    dep = depth * max_ms * sr / 1000.0
    ref = man + dep  # through-zero reference tap
    outs = np.zeros(2)
    for t in range(n):
        bl[w] = xl[t] + feedback * fbl
        br[w] = xr[t] + feedback * fbr
        for c in range(2):
            p = ph + (0.25 * width if c == 1 else 0.0)
            p -= math.floor(p)
            buf = bl if c == 0 else br
            if mode == 2 or mode == 3:
                # two overlapping one-way sweeps with complementary crossfade
                y = 0.0
                for g in range(2):
                    pg = p + 0.5 * g
                    pg -= math.floor(pg)
                    sweep = pg if mode == 3 else 1.0 - pg
                    y += read_frac(buf, w, 1.0 + man + dep * sweep) * math.sin(math.pi * pg)
                y *= 0.7071
            else:
                tri = 2.0 * abs(2.0 * p - 1.0) - 1.0
                sine = math.sin(TWO_PI * p)
                if mode == 0:
                    d = 1.0 + man + dep * 0.5 * (1.0 + tri)
                elif mode == 1:
                    d = 1.0 + man + dep * (1.0 + tri)
                elif mode == 4:
                    d = 1.0 + man + 7.0 * sr / 1000.0 + dep * 0.5 * (1.0 + sine)
                elif mode == 5:
                    d = 1.0 + man + 22.0 * sr / 1000.0 + dep * 0.1 * (1.0 + sine)
                else:
                    d = 1.0 + man + dep * 0.5 * (1.0 + sine)
                y = read_frac(buf, w, d)
                if mode == 1:
                    y = 0.5 * (y + read_frac(buf, w, 1.0 + ref))
            outs[c] = y
        fbl = soft_clip(outs[0])
        fbr = soft_clip(outs[1])
        ph += rate / sr
        if ph >= 1.0:
            ph -= 1.0
        w += 1
        if w >= ln:
            w = 0
        if mode == 6 or mode == 1:
            yl[t] = outs[0]
            yr[t] = outs[1]
        else:
            # comb against the dry path gives the classic notch pattern
            yl[t] = 0.5 * (xl[t] + outs[0]) if mode < 4 else outs[0]
            yr[t] = 0.5 * (xr[t] + outs[1]) if mode < 4 else outs[1]
    return yl, yr


# --------------------------------------------------------------------------
# modulated multi-tap delay (ValhallaUberMod)
# --------------------------------------------------------------------------


@jit
def multitap(
    xl, xr, sr, delay_ms, taps, warp, feedback, density, width,
    mod_rate, mod_depth_ms, lowcut, highcut, drive, age, tap_decay,
):
    n = xl.shape[0]
    yl = np.zeros(n)
    yr = np.zeros(n)
    d = max(1.0, delay_ms * sr / 1000.0)
    mdepth = mod_depth_ms * sr / 1000.0
    ln = int(d + 2.0 * mdepth) + 8
    bl = np.zeros(ln)
    br = np.zeros(ln)
    w = 0
    pos = np.zeros(taps)
    gain = np.zeros(taps)
    pan = np.zeros(taps)
    expo = 2.0**warp
    gsum = 0.0
    for k in range(taps):
        r = (k + 1.0) / taps
        pos[k] = max(1.0, d * r**expo)
        gain[k] = 1.0 - tap_decay * k / max(taps, 1)
        pan[k] = (1.0 if k % 2 == 0 else -1.0) * width * (0.4 + 0.6 * r)
        gsum += gain[k]
    gnorm = 1.0 / math.sqrt(max(gsum, 1.0))

    dbuf = np.zeros((4, int(0.017 * sr) + 3))
    dw = np.zeros(4, dtype=np.int64)
    dlens = np.array([0.0057, 0.0083, 0.0119, 0.0161]) * sr
    a_hc = lp_coef(highcut * (1.0 - 0.75 * age), sr)
    a_lc = lp_coef(lowcut, sr)
    f = np.zeros(4)
    ph = 0.0
    fbl = 0.0
    fbr = 0.0
    pre = 1.0 + 5.0 * drive
    for t in range(n):
        bl[w] = xl[t] + feedback * fbl
        br[w] = xr[t] + feedback * fbr
        ol = 0.0
        orr = 0.0
        for k in range(taps):
            m = mdepth * (1.0 + math.sin(TWO_PI * (ph + k * 0.618)))
            sl = read_frac(bl, w, pos[k] + m) * gain[k]
            sr_ = read_frac(br, w, pos[k] + m * 0.9) * gain[k]
            ol += sl * (1.0 + pan[k]) * 0.5 + sr_ * (1.0 - pan[k]) * 0.5 * (1.0 - width)
            orr += sr_ * (1.0 - pan[k]) * 0.5 + sl * (1.0 + pan[k]) * 0.5 * (1.0 - width)
        ol *= gnorm
        orr *= gnorm
        ph += mod_rate / sr
        if ph >= 1.0:
            ph -= 1.0
        for c in range(2):
            x = ol if c == 0 else orr
            if density > 0.0:
                for k in range(2):
                    b = 2 * c + k
                    x = _ap_step(dbuf[b], dw[b], int(dlens[2 * c + k]), 0.65 * density, x)
                    dw[b] += 1
                    if dw[b] >= dbuf.shape[1]:
                        dw[b] = 0
            f[c] = a_lc * f[c] + (1.0 - a_lc) * x
            x -= f[c]
            f[2 + c] = a_hc * f[2 + c] + (1.0 - a_hc) * x
            x = f[2 + c]
            if drive > 0.0:
                x = soft_clip(x * pre) / pre
            if c == 0:
                ol = x
            else:
                orr = x
        # feedback from the last tap region keeps the rhythmic pattern repeating
        fbl = soft_clip(read_frac(bl, w, d) * 0.5 + ol * 0.5)
        fbr = soft_clip(read_frac(br, w, d) * 0.5 + orr * 0.5)
        w += 1
        if w >= ln:
            w = 0
        yl[t] = ol
        yr[t] = orr
    return yl, yr


# --------------------------------------------------------------------------
# numpy helpers (not jitted)
# --------------------------------------------------------------------------


def reverse_chunks(x, chunk):
    """Play the signal back in reversed, Hann-crossfaded chunks (reverse delay).

    Each chunk is emitted once it has been fully recorded, so the result lags
    the input by one chunk, like a hardware reverse delay.
    """
    chunk = max(int(chunk), 16)
    hop = chunk // 2
    win = np.sin(np.pi * (np.arange(chunk) + 0.5) / chunk) ** 2
    xp = np.concatenate([np.zeros(hop), x, np.zeros(chunk)])
    out = np.zeros(len(xp) + chunk)
    for start in range(0, len(x) + hop, hop):
        out[start + chunk:start + 2 * chunk] += xp[start:start + chunk][::-1] * win
    return out[hop:hop + len(x)]
