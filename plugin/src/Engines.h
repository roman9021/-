#pragma once
// Plate, echo, frequency-shift, modulation and multi-tap engines.
#include "Dsp.h"

namespace vc
{
// ------------------------------------------------------------------ plate
// Dattorro's figure-of-eight plate tank.
class PlateReverb
{
public:
    struct Config
    {
        double predelayMs = 0, rt60 = 2.5, size = 1, width = 1;
        double bandwidth = 0.9995, damping = 0.0005, inDiff1 = 0.75, inDiff2 = 0.625, decDiff1 = 0.7, decDiff2 = 0.5;
        double modRate = 0.8, modDepth = 5, lowCut = 20, highCut = 9000, bassMult = 1, bassXover = 400;
    };

    void prepare (double sampleRate, double maxSize)
    {
        sr = sampleRate;
        const double k = sr / 29761.0, ks = k * maxSize;
        pre.allocate ((int) (0.5 * sr) + 8);
        const int inLen[4] = { 142, 107, 379, 277 };
        for (int i = 0; i < 4; ++i)
        {
            inAp[i].allocate ((int) (inLen[i] * k) + 2);
            inAp[i].setLength ((int) (inLen[i] * k));
        }
        modAp[0].allocate ((int) ((672 + 40) * ks) + 8);
        modAp[1].allocate ((int) ((908 + 40) * ks) + 8);
        const int lens[6] = { 4453, 1800, 3720, 4217, 2656, 3163 };
        for (int i = 0; i < 3; ++i)
        {
            del[0][i].allocate ((int) (lens[i] * ks) + 8);
            del[1][i].allocate ((int) (lens[i + 3] * ks) + 8);
        }
        reset();
    }

    void reset()
    {
        pre.clear();
        for (auto& a : inAp) a.clear();
        for (auto& a : modAp) a.clear();
        for (auto& h : del) for (auto& d : h) d.clear();
        bw = 0;
        damp[0] = damp[1] = 0;
        for (auto* f : { &bx[0], &bx[1], &lc[0], &lc[1], &hc[0], &hc[1] }) f->reset();
        fb[0] = fb[1] = 0;
        ph = 0;
    }

    void configure (const Config& c)
    {
        cfg = c;
        const double k = sr / 29761.0, ks = k * c.size;
        len[0][0] = (int) (4453 * ks); len[0][1] = (int) (1800 * ks); len[0][2] = (int) (3720 * ks);
        len[1][0] = (int) (4217 * ks); len[1][1] = (int) (2656 * ks); len[1][2] = (int) (3163 * ks);
        modLen[0] = (float) (672 * ks);
        modLen[1] = (float) (908 * ks);
        md = (float) (c.modDepth * k);
        const double half = (672.0 + 4453.0 + 1800.0 + 3720.0) * ks;
        g = (float) decayGain (half / 2.0, c.rt60, sr); // the gain is applied twice per half
        gLo = (float) std::min (decayGain (half / 2.0, c.rt60 * c.bassMult, sr), 0.9995);
        const int taps[14] = { 266, 2974, 1913, 1996, 1990, 187, 1066, 353, 3627, 1228, 2673, 2111, 335, 121 };
        for (int i = 0; i < 14; ++i)
            tap[i] = std::max (1, (int) (taps[i] * ks));
        for (int ch = 0; ch < 2; ++ch)
        {
            bx[ch].set (c.bassXover, sr);
            lc[ch].set (c.lowCut, sr);
            hc[ch].set (c.highCut, sr);
        }
        pd = (float) (c.predelayMs * sr / 1000.0);
    }

    void process (float* l, float* r, int n)
    {
        const float d1 = (float) cfg.decDiff1, d2 = (float) cfg.decDiff2;
        for (int t = 0; t < n; ++t)
        {
            pre.write (0.5f * (l[t] + r[t]));
            float x = pre.read (pd);
            pre.advance();
            bw += (float) cfg.bandwidth * (x - bw);
            x = inAp[0].process (bw, (float) cfg.inDiff1);
            x = inAp[1].process (x, (float) cfg.inDiff1);
            x = inAp[2].process (x, (float) cfg.inDiff2);
            x = inAp[3].process (x, (float) cfg.inDiff2);

            const float lfo = (float) std::sin (kTwoPi * ph);
            ph += cfg.modRate / sr;
            ph -= std::floor (ph);

            for (int h = 0; h < 2; ++h)
            {
                float in = x + fb[1 - h];
                float dv = modAp[h].d.read (modLen[h] + (h ? -md : md) * lfo + md + 1.0f);
                float wv = in - d1 * dv;
                modAp[h].d.write (wv);
                modAp[h].d.advance();
                float a = dv + d1 * wv;
                del[h][0].write (a);
                a = del[h][0].tap (len[h][0]);
                damp[h] += (1.0f - (float) cfg.damping) * (a - damp[h]);
                float lo = bx[h].lp (damp[h]);
                a = lo * gLo + (damp[h] - lo) * g;
                // decay-diffusion allpass, read in place so output taps can see it
                float dv2 = del[h][1].tap (len[h][1]);
                float w2 = a + d2 * dv2;
                del[h][1].write (w2);
                a = dv2 - d2 * w2;
                del[h][2].write (a);
                fb[h] = del[h][2].tap (len[h][2]) * g;
            }

            auto T = [this] (int h, int i, int k) { return del[h][i].tap (tap[k]); };
            float ol = T (1, 0, 0) + T (1, 0, 1) - T (1, 1, 2) + T (1, 2, 3) - T (0, 0, 4) - T (0, 1, 5) - T (0, 2, 6);
            float orr = T (0, 0, 7) + T (0, 0, 8) - T (0, 1, 9) + T (0, 2, 10) - T (1, 0, 11) - T (1, 1, 12) - T (1, 2, 13);
            for (auto& h : del) for (auto& d : h) d.advance();

            ol *= 0.6f;
            orr *= 0.6f;
            float mm = 0.5f * (ol + orr), ss = 0.5f * (ol - orr) * (float) cfg.width;
            l[t] = hc[0].lp (lc[0].hp (mm + ss));
            r[t] = hc[1].lp (lc[1].hp (mm - ss));
        }
    }

private:
    double sr = 44100.0, ph = 0;
    Config cfg;
    DelayLine pre;
    Allpass inAp[4], modAp[2];
    DelayLine del[2][3];
    int len[2][3] {}, tap[14] {};
    float modLen[2] {}, md = 0, g = 0, gLo = 0, pd = 0, bw = 0, damp[2] {}, fb[2] {};
    OnePole bx[2], lc[2], hc[2];
};

// ------------------------------------------------------------------- echo
class EchoDelay
{
public:
    struct Config
    {
        double delayL = 375, delayR = 375, feedback = 0.4;
        int style = 0; // 0 single, 1 dual, 2 ping-pong
        double width = 1, age = 0.25, drive = 0, diffusion = 0, ducking = 0;
        double modRate = 0.5, modDepthMs = 0.4, flutter = 1, lowCut = 80, highCut = 8000;
        bool bbd = false, reverse = false;
        int digitalBits = 0;
        double pitchRatio = 2, pitchAmount = 0, noise = 0;
    };

    void prepare (double sampleRate, double maxDelayMs)
    {
        sr = sampleRate;
        for (int c = 0; c < 2; ++c)
        {
            line[c].allocate ((int) ((maxDelayMs + 20.0) * sr / 1000.0) + 16);
            ap[c][0].allocate ((int) (0.0081 * sr) + 4);
            ap[c][1].allocate ((int) (0.0128 * sr) + 4);
            ap[c][0].setLength ((int) (0.0071 * sr * (1.0 + 0.13 * c)));
            ap[c][1].setLength ((int) (0.0113 * sr * (1.0 + 0.13 * c)));
            ps[c].prepare (sr, 0.08, c * 0.5f);
            rev[c].prepare (sr, maxDelayMs / 1000.0);
        }
        reset();
    }

    void reset()
    {
        for (int c = 0; c < 2; ++c)
        {
            line[c].clear();
            ap[c][0].clear();
            ap[c][1].clear();
            ps[c].reset();
            rev[c].reset();
            lc[c].reset();
            hc[c].reset();
        }
        env = 0;
        ph = ph2 = 0;
        smoothL = smoothR = -1;
    }

    void configure (const Config& c)
    {
        cfg = c;
        double h = c.highCut * (1.0 - 0.8 * c.age);
        if (c.bbd) h = std::min (h, 2.0e5 / std::max (c.delayL, 10.0) + 2500.0);
        for (int ch = 0; ch < 2; ++ch)
        {
            lc[ch].set (c.lowCut, sr);
            hc[ch].set (h, sr);
        }
        aEnv = lpCoef (8.0, sr);
        aSmooth = lpCoef (3.0, sr);
        q = c.digitalBits > 0 ? std::pow (2.0f, (float) (c.digitalBits - 1)) : 0.0f;
    }

    void process (float* l, float* r, int n)
    {
        const double ms = sr / 1000.0;
        const float targetL = (float) (cfg.delayL * ms);
        const float targetR = (float) ((cfg.style == 0 ? cfg.delayL : cfg.delayR) * ms);
        if (smoothL < 0) { smoothL = targetL; smoothR = targetR; }
        const float mdepth = (float) (cfg.modDepthMs * ms);
        const float fbk = (float) cfg.feedback, preGain = 1.0f + 6.0f * (float) cfg.drive;
        for (int t = 0; t < n; ++t)
        {
            float xl = l[t], xr = r[t];
            float inl = xl, inr = xr;
            if (cfg.style == 0) inl = inr = 0.5f * (xl + xr);
            else if (cfg.style == 2) { inl = 0.5f * (xl + xr); inr = 0.0f; }
            if (cfg.reverse)
            {
                inl = rev[0].process (inl, smoothL);
                inr = rev[1].process (inr, smoothR);
            }

            // glide delay-time changes like a tape machine instead of clicking
            smoothL = aSmooth * smoothL + (1.0f - aSmooth) * targetL;
            smoothR = aSmooth * smoothR + (1.0f - aSmooth) * targetR;
            float lfo = (float) (std::sin (kTwoPi * ph) + cfg.flutter * 0.3 * std::sin (kTwoPi * ph2));
            ph += cfg.modRate / sr;
            ph2 += (cfg.modRate * 7.3 + 5.0) / sr;
            ph -= std::floor (ph);
            ph2 -= std::floor (ph2);
            float mOff = mdepth * (1.0f + lfo);
            float dL = line[0].read (smoothL + mOff + 1.0f);
            float dR = line[1].read (smoothR + mOff * 0.97f + 1.0f);

            float fb[2] = { dL, dR };
            for (int c = 0; c < 2; ++c)
            {
                float x = hc[c].lp (lc[c].hp (fb[c]));
                if (cfg.diffusion > 0.0)
                {
                    x = ap[c][0].process (x, 0.7f * (float) cfg.diffusion);
                    x = ap[c][1].process (x, 0.7f * (float) cfg.diffusion);
                }
                if (cfg.drive > 0.0) x = softClip (x * preGain) / preGain;
                else if (cfg.age > 0.0) x = softClip (x);
                if (cfg.noise > 0.0) x += (float) (cfg.noise * cfg.age * 0.001) * lcg.bipolar();
                if (q > 0.0f) x = std::floor (x * q + 0.5f) / q;
                if (cfg.pitchAmount > 0.0)
                    x += (float) cfg.pitchAmount * (ps[c].process (x, (float) cfg.pitchRatio) - x);
                fb[c] = x;
            }
            if (cfg.style == 2)
            {
                line[0].write (inl + fbk * fb[1]);
                line[1].write (inr + fbk * fb[0]);
            }
            else
            {
                line[0].write (inl + fbk * fb[0]);
                line[1].write (inr + fbk * fb[1]);
            }
            line[0].advance();
            line[1].advance();

            env = aEnv * env + (1.0f - aEnv) * (std::abs (xl) + std::abs (xr));
            float duck = 1.0f / (1.0f + (float) cfg.ducking * env * 20.0f);
            float mm = 0.5f * (dL + dR), ss = 0.5f * (dL - dR) * (float) cfg.width;
            l[t] = (mm + ss) * duck;
            r[t] = (mm - ss) * duck;
        }
    }

private:
    double sr = 44100.0, ph = 0, ph2 = 0;
    Config cfg;
    DelayLine line[2];
    Allpass ap[2][2];
    PitchShifter ps[2];
    ReverseDelay rev[2];
    OnePole lc[2], hc[2];
    Lcg lcg;
    float env = 0, aEnv = 0, aSmooth = 0, q = 0, smoothL = -1, smoothR = -1;
};

// ------------------------------------------------------- frequency shifter
class FreqEchoEngine
{
public:
    struct Config { double delayMs = 200, feedback = 0.5, shiftHz = 10, width = 0, lowCut = 40, highCut = 12000; bool analog = false; };

    void prepare (double sampleRate, double maxDelayMs)
    {
        sr = sampleRate;
        for (auto& d : line) d.allocate ((int) ((maxDelayMs + 10.0) * sr / 1000.0) + 8);
        reset();
    }

    void reset()
    {
        for (auto& d : line) d.clear();
        std::fill (&st[0][0][0][0], &st[0][0][0][0] + 2 * 2 * 4 * 4, 0.0f);
        prevIm[0] = prevIm[1] = 0;
        ph = 0;
        smooth = -1;
        for (auto* f : { &lc[0], &lc[1], &hc[0], &hc[1] }) f->reset();
    }

    void configure (const Config& c)
    {
        cfg = c;
        for (int ch = 0; ch < 2; ++ch)
        {
            lc[ch].set (c.lowCut, sr);
            hc[ch].set (c.highCut * (c.analog ? 0.6 : 1.0), sr);
        }
        aSmooth = lpCoef (3.0, sr);
    }

    void process (float* l, float* r, int n)
    {
        static constexpr float A[4] = { 0.6923878f, 0.9360654322959f, 0.9882295226860f, 0.9987488452737f };
        static constexpr float B[4] = { 0.4021921162426f, 0.8561710882420f, 0.9722909545651f, 0.9952884791278f };
        const float target = (float) (cfg.delayMs * sr / 1000.0);
        if (smooth < 0) smooth = target;
        for (int t = 0; t < n; ++t)
        {
            smooth = aSmooth * smooth + (1.0f - aSmooth) * target;
            ph += cfg.shiftHz / sr;
            ph -= std::floor (ph);
            float out[2];
            for (int c = 0; c < 2; ++c)
            {
                float x = line[c].read (smooth);
                float re = chain (A, st[c][0], x);
                float imNow = chain (B, st[c][1], x);
                float im = prevIm[c];
                prevIm[c] = imNow;
                double pc = ph + (c == 1 ? 0.25 * cfg.width : 0.0);
                float s = re * (float) std::cos (kTwoPi * pc) + im * (float) std::sin (kTwoPi * pc);
                s = hc[c].lp (lc[c].hp (s));
                if (cfg.analog) s = softClip (s * 1.5f) / 1.5f;
                out[c] = s;
            }
            line[0].write (l[t] + (float) cfg.feedback * out[0]);
            line[1].write (r[t] + (float) cfg.feedback * out[1]);
            line[0].advance();
            line[1].advance();
            l[t] = out[0];
            r[t] = out[1];
        }
    }

private:
    // four 2nd-order allpasses; state = (x1, x2, y1, y2)
    static float chain (const float* coefs, float (*s)[4], float x)
    {
        for (int k = 0; k < 4; ++k)
        {
            float c = coefs[k] * coefs[k];
            float y = c * (x + s[k][3]) - s[k][1];
            s[k][1] = s[k][0];
            s[k][0] = x;
            s[k][3] = s[k][2];
            s[k][2] = y;
            x = y;
        }
        return x;
    }

    double sr = 44100.0, ph = 0;
    Config cfg;
    DelayLine line[2];
    float st[2][2][4][4] {};
    float prevIm[2] {}, aSmooth = 0, smooth = -1;
    OnePole lc[2], hc[2];
};

// ---------------------------------------------------- flanger / chorus
class SpaceModEngine
{
public:
    enum Mode { Flange, ThruZero, BarberUp, BarberDown, Chorus, Doubler, Vibrato };
    struct Config { double rate = 0.25, depth = 0.5, feedback = 0.5, manualMs = 0.5, width = 0.5; int mode = Flange; };
    static constexpr double kMaxMs = 10.0;

    void prepare (double sampleRate)
    {
        sr = sampleRate;
        for (auto& d : line) d.allocate ((int) ((kMaxMs * 2.0 + 45.0) * sr / 1000.0) + 8);
        reset();
    }
    void reset() { for (auto& d : line) d.clear(); ph = 0; fb[0] = fb[1] = 0; }
    void configure (const Config& c) { cfg = c; }

    void process (float* l, float* r, int n)
    {
        const double ms = sr / 1000.0;
        const float man = (float) (cfg.manualMs * ms), dep = (float) (cfg.depth * kMaxMs * ms);
        const int mode = cfg.mode;
        for (int t = 0; t < n; ++t)
        {
            float in[2] = { l[t], r[t] }, outs[2];
            line[0].write (in[0] + (float) cfg.feedback * fb[0]);
            line[1].write (in[1] + (float) cfg.feedback * fb[1]);
            for (int c = 0; c < 2; ++c)
            {
                double p = ph + (c == 1 ? 0.25 * cfg.width : 0.0);
                p -= std::floor (p);
                float y;
                if (mode == BarberUp || mode == BarberDown)
                {
                    y = 0.0f;
                    for (int g = 0; g < 2; ++g)
                    {
                        double pg = p + 0.5 * g;
                        pg -= std::floor (pg);
                        double sweep = mode == BarberDown ? pg : 1.0 - pg;
                        y += line[c].read (1.0 + man + dep * sweep) * (float) std::sin (kPi * pg);
                    }
                    y *= 0.7071f;
                }
                else
                {
                    double tri = 2.0 * std::abs (2.0 * p - 1.0) - 1.0, sine = std::sin (kTwoPi * p), d;
                    switch (mode)
                    {
                        case Flange:   d = 1.0 + man + dep * 0.5 * (1.0 + tri); break;
                        case ThruZero: d = 1.0 + man + dep * (1.0 + tri); break;
                        case Chorus:   d = 1.0 + man + 7.0 * ms + dep * 0.5 * (1.0 + sine); break;
                        case Doubler:  d = 1.0 + man + 22.0 * ms + dep * 0.1 * (1.0 + sine); break;
                        default:       d = 1.0 + man + dep * 0.5 * (1.0 + sine); break;
                    }
                    y = line[c].read (d);
                    if (mode == ThruZero) y = 0.5f * (y + line[c].read (1.0 + man + dep));
                }
                outs[c] = y;
            }
            fb[0] = softClip (outs[0]);
            fb[1] = softClip (outs[1]);
            line[0].advance();
            line[1].advance();
            ph += cfg.rate / sr;
            ph -= std::floor (ph);
            for (int c = 0; c < 2; ++c)
            {
                float o = (mode == Vibrato || mode == ThruZero || mode >= Chorus) ? outs[c] : 0.5f * (in[c] + outs[c]);
                (c == 0 ? l : r)[t] = o;
            }
        }
    }

private:
    double sr = 44100.0, ph = 0;
    Config cfg;
    DelayLine line[2];
    float fb[2] {};
};

// ------------------------------------------------------- multi-tap delay
class MultiTapEngine
{
public:
    static constexpr int kMaxTaps = 16;
    struct Config
    {
        double delayMs = 300, warp = 0, feedback = 0.3, density = 0.3, width = 1, modRate = 0.6, modDepthMs = 0.9;
        double lowCut = 60, highCut = 9000, drive = 0, age = 0, tapDecay = 0.3;
        int taps = 4;
    };

    void prepare (double sampleRate, double maxDelayMs)
    {
        sr = sampleRate;
        for (auto& d : line) d.allocate ((int) ((maxDelayMs + 10.0) * sr / 1000.0) + 8);
        const double lens[4] = { 0.0057, 0.0083, 0.0119, 0.0161 };
        for (int i = 0; i < 4; ++i)
        {
            ap[i].allocate ((int) (lens[i] * sr) + 4);
            ap[i].setLength ((int) (lens[i] * sr));
        }
        reset();
    }

    void reset()
    {
        for (auto& d : line) d.clear();
        for (auto& a : ap) a.clear();
        for (auto* f : { &lc[0], &lc[1], &hc[0], &hc[1] }) f->reset();
        fb[0] = fb[1] = 0;
        ph = 0;
        smooth = -1;
    }

    void configure (const Config& c)
    {
        cfg = c;
        nt = std::clamp (c.taps, 1, kMaxTaps);
        const double expo = std::pow (2.0, c.warp);
        float gsum = 0;
        for (int k = 0; k < nt; ++k)
        {
            double rr = (k + 1.0) / nt;
            pos[k] = (float) std::pow (rr, expo);
            gain[k] = (float) (1.0 - c.tapDecay * k / nt);
            pan[k] = (float) ((k % 2 == 0 ? 1.0 : -1.0) * c.width * (0.4 + 0.6 * rr));
            gsum += gain[k];
        }
        gnorm = 1.0f / std::sqrt (std::max (gsum, 1.0f));
        for (int ch = 0; ch < 2; ++ch)
        {
            lc[ch].set (c.lowCut, sr);
            hc[ch].set (c.highCut * (1.0 - 0.75 * c.age), sr);
        }
        aSmooth = lpCoef (3.0, sr);
    }

    void process (float* l, float* r, int n)
    {
        const float target = (float) (cfg.delayMs * sr / 1000.0), mdepth = (float) (cfg.modDepthMs * sr / 1000.0);
        const float w = (float) cfg.width, pre = 1.0f + 5.0f * (float) cfg.drive;
        if (smooth < 0) smooth = target;
        for (int t = 0; t < n; ++t)
        {
            smooth = aSmooth * smooth + (1.0f - aSmooth) * target;
            line[0].write (l[t] + (float) cfg.feedback * fb[0]);
            line[1].write (r[t] + (float) cfg.feedback * fb[1]);
            float ol = 0, orr = 0;
            for (int k = 0; k < nt; ++k)
            {
                float m = mdepth * (1.0f + (float) std::sin (kTwoPi * (ph + k * 0.618)));
                float d = std::max (1.0f, smooth * pos[k]);
                float sl = line[0].read (d + m) * gain[k], sr_ = line[1].read (d + m * 0.9f) * gain[k];
                ol += sl * (1.0f + pan[k]) * 0.5f + sr_ * (1.0f - pan[k]) * 0.5f * (1.0f - w);
                orr += sr_ * (1.0f - pan[k]) * 0.5f + sl * (1.0f + pan[k]) * 0.5f * (1.0f - w);
            }
            ol *= gnorm;
            orr *= gnorm;
            ph += cfg.modRate / sr;
            ph -= std::floor (ph);
            float o[2] = { ol, orr };
            for (int c = 0; c < 2; ++c)
            {
                float x = o[c];
                if (cfg.density > 0.0)
                {
                    x = ap[2 * c].process (x, 0.65f * (float) cfg.density);
                    x = ap[2 * c + 1].process (x, 0.65f * (float) cfg.density);
                }
                x = hc[c].lp (lc[c].hp (x));
                if (cfg.drive > 0.0) x = softClip (x * pre) / pre;
                o[c] = x;
            }
            // feedback blends the full-length tap with the processed output
            fb[0] = softClip (line[0].read (smooth) * 0.5f + o[0] * 0.5f);
            fb[1] = softClip (line[1].read (smooth) * 0.5f + o[1] * 0.5f);
            line[0].advance();
            line[1].advance();
            l[t] = o[0];
            r[t] = o[1];
        }
    }

private:
    double sr = 44100.0, ph = 0;
    Config cfg;
    DelayLine line[2];
    Allpass ap[4];
    OnePole lc[2], hc[2];
    int nt = 4;
    float pos[kMaxTaps] {}, gain[kMaxTaps] {}, pan[kMaxTaps] {}, gnorm = 1, fb[2] {}, aSmooth = 0, smooth = -1;
};
} // namespace vc
