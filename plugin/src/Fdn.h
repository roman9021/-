#pragma once
// Feedback delay network reverb used by VintageVerb, Room, Shimmer and
// Supermassive: pre-delay, early reflections, input diffusion, up to 16
// modulated lines with in-loop allpasses and 3-band decay, a Hadamard
// feedback matrix, optional pitch shifting in the loop, gating and a
// sample-rate / bit-depth "colour" stage.
#include "Dsp.h"

namespace vc
{
struct FdnConfig
{
    static constexpr int kMaxLines = 16, kMaxTaps = 16;
    double predelayMs = 0, rt60 = 2, size = 1;
    int numLines = 8;
    std::array<double, kMaxLines> delaysMs {};
    std::array<double, 4> inDiffMs { 4.77, 3.59, 12.73, 9.31 };
    double inDiffGain = 0, attack = 0, loopDiffGain = 0;
    double modRate = 0.5, modDepthMs = 0, modRandom = 0, randRate = 0;
    double bassMult = 1, bassXover = 500, highMult = 1, highXover = 5000;
    double lowCut = 20, highCut = 20000, width = 1;
    double fbOverride = -1; // >= 0: fixed loop gain instead of rt60
    double shiftRatio = 1, shiftAmount = 0;
    bool shiftStereo = true;
    int numTaps = 0;
    std::array<double, kMaxTaps> erTapsMs {}, erGains {};
    double erLevel = 0, erSend = 0, lateLevel = 1, erModRate = 0, erModDepthMs = 0, erWidth = 1;
    double gateTime = 0, colorSr = 0;
    int colorBits = 0;
};

class FdnReverb
{
public:
    static constexpr int N = FdnConfig::kMaxLines;

    void prepare (double sampleRate, double maxLineMs, double maxPreMs)
    {
        sr = sampleRate;
        const double ms = sr / 1000.0;
        pre[0].allocate ((int) (maxPreMs * ms) + 16);
        pre[1].allocate ((int) (maxPreMs * ms) + 16);
        for (int k = 0; k < 6; ++k)
            for (int c = 0; c < 2; ++c)
                diff[k][c].allocate ((int) (160.0 * ms));
        for (int i = 0; i < N; ++i)
        {
            lines[i].allocate ((int) ((maxLineMs + 12.0) * ms) + 8);
            loopAp[i].allocate ((int) (maxLineMs * 0.25 * ms) + 4);
        }
        shifter[0].prepare (sr, 0.1, 0.0f);
        shifter[1].prepare (sr, 0.1, 0.25f);
        reset();
    }

    void reset()
    {
        for (auto& d : pre) d.clear();
        for (auto& row : diff) for (auto& a : row) a.clear();
        for (int i = 0; i < N; ++i)
        {
            lines[i].clear();
            loopAp[i].clear();
            sBass[i].reset();
            sHigh[i].reset();
            phase[i] = (float) i / N;
            rnd[i] = rndSmooth[i] = 0.0f;
            rndTimer[i] = 0.0f;
        }
        for (auto& s : shifter) s.reset();
        for (auto* f : { &shHp[0], &shHp[1], &lc[0], &lc[1], &hc1[0], &hc1[1], &hc2[0], &hc2[1] }) f->reset();
        lastL = lastR = 0.0f;
        erPhase = 0.0f;
        env = gate = 0.0f;
        gateLeft = 0.0f;
        holdCtr = 0.0;
        holdL = holdR = 0.0f;
    }

    void configure (const FdnConfig& c)
    {
        cfg = c;
        const double ms = sr / 1000.0;
        nl = std::clamp (c.numLines, 2, N);
        pd = (float) (c.predelayMs * ms);
        erMd = (float) (c.erModDepthMs * ms);
        for (int k = 0; k < 4; ++k)
            for (int ch = 0; ch < 2; ++ch)
                diff[k][ch].setLength ((int) (c.inDiffMs[(size_t) k] * std::sqrt (c.size) * ms * (ch ? 1.07 : 1.0)));
        for (int ch = 0; ch < 2; ++ch)
        {
            diff[4][ch].setLength ((int) ((7.0 + 90.0 * c.attack) * ms));
            diff[5][ch].setLength ((int) ((11.0 + 140.0 * c.attack) * ms));
        }
        mDepth = (float) (c.modDepthMs * ms);
        for (int i = 0; i < nl; ++i)
        {
            dl[i] = (float) std::clamp (c.delaysMs[(size_t) i] * c.size * ms, 4.0, (double) lines[i].maxDelay() - mDepth * 1.5 - 4.0);
            loopAp[i].setLength ((int) (dl[i] * 0.23f));
            const double loopLen = dl[i] + (c.loopDiffGain != 0.0 ? loopAp[i].len : 0);
            if (c.fbOverride >= 0.0)
            {
                gMid[i] = (float) c.fbOverride;
                gLo[i] = (float) std::min (c.fbOverride * c.bassMult, 0.9995);
                gHi[i] = (float) (c.fbOverride * std::min (c.highMult, 1.0));
            }
            else
            {
                gMid[i] = (float) decayGain (loopLen, c.rt60, sr);
                gLo[i] = (float) std::min (decayGain (loopLen, c.rt60 * c.bassMult, sr), 0.9995);
                gHi[i] = (float) decayGain (loopLen, c.rt60 * c.highMult, sr);
            }
            sBass[i].set (c.bassXover, sr);
            sHigh[i].set (std::max (c.highXover, c.bassXover * 1.5), sr);
        }
        for (int ch = 0; ch < 2; ++ch)
        {
            shHp[ch].set (120.0, sr);
            lc[ch].set (c.lowCut, sr);
            hc1[ch].set (c.highCut, sr);
            hc2[ch].set (c.highCut, sr);
        }
        aEnv = lpCoef (30.0, sr);
        aGate = lpCoef (60.0, sr);
        q = c.colorBits > 0 ? std::pow (2.0f, (float) (c.colorBits - 1)) : 0.0f;
    }

    // In-place: input in l/r is replaced by the 100% wet signal.
    void process (float* l, float* r, int n)
    {
        const double ms = sr / 1000.0;
        const float inScale = 1.0f / std::sqrt (nl / 2.0f);
        const float outScale = 1.0f / std::sqrt ((float) nl);
        const float width = (float) cfg.width;
        float v[N], outv[N];

        for (int t = 0; t < n; ++t)
        {
            const float xl = l[t], xr = r[t];
            pre[0].write (xl);
            pre[1].write (xr);
            float il = pre[0].read (pd), ir = pre[1].read (pd);
            float el = 0.0f, er = 0.0f;
            for (int k = 0; k < cfg.numTaps; ++k)
            {
                double d = pd + cfg.erTapsMs[(size_t) k] * ms + erMd * (1.0 + std::sin (kTwoPi * (erPhase + 0.137 * k)));
                if (k % 2 == 0) el += pre[0].read (d) * (float) cfg.erGains[(size_t) k];
                else            er += pre[1].read (d) * (float) cfg.erGains[(size_t) k];
            }
            erPhase += (float) (cfg.erModRate / sr);
            erPhase -= std::floor (erPhase);
            if (cfg.erWidth < 1.0)
            {
                float em = 0.5f * (el + er), es = 0.5f * (el - er) * (float) cfg.erWidth;
                el = em + es;
                er = em - es;
            }
            pre[0].advance();
            pre[1].advance();

            float sl = il + (float) cfg.erSend * el;
            float sr_ = ir + (float) cfg.erSend * er;
            for (int k = 0; k < 6; ++k)
            {
                float g = k < 4 ? (float) cfg.inDiffGain : 0.72f * (float) cfg.attack;
                if (g == 0.0f) continue;
                sl = diff[k][0].process (sl, g);
                sr_ = diff[k][1].process (sr_, g);
            }

            float shL = 0.0f, shR = 0.0f;
            if (cfg.shiftAmount > 0.0)
            {
                shL = shifter[0].process (lastL, (float) cfg.shiftRatio);
                shR = shifter[1].process (lastR, (float) cfg.shiftRatio);
                if (! cfg.shiftStereo) shL = shR = 0.5f * (shL + shR);
                shL = softClip (shHp[0].hp (shL) * (float) cfg.shiftAmount);
                shR = softClip (shHp[1].hp (shR) * (float) cfg.shiftAmount);
            }

            for (int i = 0; i < nl; ++i)
            {
                if (cfg.modRandom > 0.0)
                {
                    rndTimer[i] -= 1.0f;
                    if (rndTimer[i] <= 0.0f)
                    {
                        rnd[i] = lcg.bipolar();
                        double rate = cfg.randRate > 0.0 ? cfg.randRate : cfg.modRate * 4.0;
                        rndTimer[i] = (float) (sr / std::max (rate, 0.05));
                    }
                    rndSmooth[i] += 0.001f * (rnd[i] - rndSmooth[i]);
                }
                float lfo = (float) std::sin (kTwoPi * phase[i]);
                phase[i] += (float) (cfg.modRate * (1.0 + 0.07 * i) / sr);
                phase[i] -= std::floor (phase[i]);
                float md = mDepth * ((1.0f - (float) cfg.modRandom) * lfo + (float) cfg.modRandom * rndSmooth[i]);
                float x = lines[i].read (dl[i] + md + mDepth * 0.5f + 1.0f);
                if (cfg.loopDiffGain != 0.0)
                    x = loopAp[i].process (x, (float) cfg.loopDiffGain);
                float lo = sBass[i].lp (x);
                float hiSplit = sHigh[i].lp (x);
                outv[i] = x;
                v[i] = lo * gLo[i] + (hiSplit - lo) * gMid[i] + (x - hiSplit) * gHi[i];
            }

            hadamard (v, nl);
            for (int i = 0; i < nl; ++i)
            {
                float inj = (i % 2 == 0) ? sl + shL : sr_ + shR;
                lines[i].write (v[i] + inj * inScale);
                lines[i].advance();
            }

            float ol = 0.0f, orr = 0.0f;
            for (int i = 0; i < nl; ++i)
            {
                ol += outv[i] * (i % 2 == 0 ? 1.0f : -1.0f);
                orr += outv[i] * ((i / 2) % 2 == 0 ? 1.0f : -1.0f);
            }
            ol *= outScale;
            orr *= outScale;
            lastL = ol;
            lastR = orr;

            float mm = 0.5f * (ol + orr), ss = 0.5f * (ol - orr) * width;
            ol = (float) cfg.lateLevel * (mm + ss) + (float) cfg.erLevel * el;
            orr = (float) cfg.lateLevel * (mm - ss) + (float) cfg.erLevel * er;

            if (cfg.gateTime > 0.0)
            {
                env = aEnv * env + (1.0f - aEnv) * (std::abs (xl) + std::abs (xr));
                if (env > 0.01f) gateLeft = (float) (cfg.gateTime * sr);
                float target = gateLeft > 0.0f ? 1.0f : 0.0f;
                gateLeft -= 1.0f;
                gate = aGate * gate + (1.0f - aGate) * target;
                ol *= gate;
                orr *= gate;
            }

            if (cfg.colorSr > 0.0)
            {
                holdCtr += cfg.colorSr / sr;
                if (holdCtr >= 1.0)
                {
                    holdCtr -= 1.0;
                    holdL = ol;
                    holdR = orr;
                    if (q > 0.0f)
                    {
                        holdL = std::floor (holdL * q + 0.5f) / q;
                        holdR = std::floor (holdR * q + 0.5f) / q;
                    }
                }
                ol = holdL;
                orr = holdR;
            }

            ol = lc[0].hp (ol);
            orr = lc[1].hp (orr);
            l[t] = hc2[0].lp (hc1[0].lp (ol));
            r[t] = hc2[1].lp (hc1[1].lp (orr));
        }
    }

private:
    double sr = 44100.0;
    FdnConfig cfg;
    int nl = 8;
    float pd = 0, erMd = 0, mDepth = 0, q = 0;
    DelayLine pre[2];
    Allpass diff[6][2];
    DelayLine lines[N];
    Allpass loopAp[N];
    float dl[N] {}, gLo[N] {}, gMid[N] {}, gHi[N] {};
    OnePole sBass[N], sHigh[N];
    float phase[N] {}, rnd[N] {}, rndSmooth[N] {}, rndTimer[N] {};
    Lcg lcg;
    PitchShifter shifter[2];
    OnePole shHp[2], lc[2], hc1[2], hc2[2];
    float lastL = 0, lastR = 0, erPhase = 0, env = 0, gate = 0, gateLeft = 0, aEnv = 0, aGate = 0;
    double holdCtr = 0;
    float holdL = 0, holdR = 0;
};
} // namespace vc
