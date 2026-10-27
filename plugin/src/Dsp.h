#pragma once
// Real-time DSP building blocks shared by all effects. Buffers are sized in
// prepare(); nothing here allocates while processing.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <vector>

namespace vc
{
constexpr double kPi = 3.141592653589793;
constexpr double kTwoPi = 2.0 * kPi;

inline float lpCoef (double fc, double sr)
{
    fc = std::clamp (fc, 1.0, 0.49 * sr);
    return (float) std::exp (-kTwoPi * fc / sr);
}

inline double decayGain (double samples, double rt60, double sr)
{
    return rt60 <= 0.0 ? 0.0 : std::pow (10.0, -3.0 * samples / (rt60 * sr));
}

inline float softClip (float x) { return std::tanh (x); }

struct OnePole
{
    float a = 0.0f, z = 0.0f;
    void set (double fc, double sr) { a = lpCoef (fc, sr); }
    float lp (float x) { return z = a * z + (1.0f - a) * x; }
    float hp (float x) { return x - lp (x); }
    void reset() { z = 0.0f; }
};

// Circular buffer. Per sample: read(...) relative to the current time step,
// write(x) the current sample, then advance().
struct DelayLine
{
    std::vector<float> buf;
    int w = 0;

    void allocate (int n) { buf.assign ((size_t) std::max (n, 4), 0.0f); w = 0; }
    void clear() { std::fill (buf.begin(), buf.end(), 0.0f); }
    int size() const { return (int) buf.size(); }
    int maxDelay() const { return size() - 2; }
    void write (float x) { buf[(size_t) w] = x; }
    void advance() { if (++w >= size()) w = 0; }

    float read (double d) const
    {
        d = std::clamp (d, 0.0, (double) maxDelay());
        double pos = w - d;
        if (pos < 0.0) pos += size();
        int i = (int) pos;
        float frac = (float) (pos - i);
        if (i >= size()) i -= size();
        int j = i + 1 < size() ? i + 1 : 0;
        return buf[(size_t) i] + frac * (buf[(size_t) j] - buf[(size_t) i]);
    }

    float tap (int d) const
    {
        d = std::clamp (d, 0, maxDelay());
        int i = w - d;
        if (i < 0) i += size();
        return buf[(size_t) i];
    }
};

// Schroeder allpass with a variable length inside a pre-allocated buffer.
struct Allpass
{
    DelayLine d;
    int len = 1;
    void allocate (int maxLen) { d.allocate (maxLen + 3); }
    void clear() { d.clear(); }
    void setLength (int n) { len = std::clamp (n, 1, d.maxDelay()); }
    float process (float x, float g)
    {
        float dv = d.tap (len);
        float wv = x + g * dv;
        d.write (wv);
        d.advance();
        return dv - g * wv;
    }
};

// Two-grain delay-line pitch shifter.
struct PitchShifter
{
    DelayLine d;
    float phase = 0.0f, phase0 = 0.0f, window = 1.0f;

    void prepare (double sr, double windowSec, float startPhase)
    {
        window = (float) (windowSec * sr);
        d.allocate ((int) (window * 1.2f) + 8);
        phase = phase0 = startPhase;
    }
    void reset() { d.clear(); phase = phase0; }

    float process (float x, float ratio)
    {
        d.write (x);
        float p2 = phase + 0.5f;
        if (p2 >= 1.0f) p2 -= 1.0f;
        float y = d.read (1.0 + phase * window) * (float) std::sin (kPi * phase)
                + d.read (1.0 + p2 * window) * (float) std::sin (kPi * p2);
        phase += (1.0f - ratio) / window;
        phase -= std::floor (phase);
        d.advance();
        return y * 0.7071f;
    }
};

inline void hadamard (float* v, int n)
{
    for (int h = 1; h < n; h *= 2)
        for (int i = 0; i < n; i += h * 2)
            for (int j = i; j < i + h; ++j)
            {
                float a = v[j], b = v[j + h];
                v[j] = a + b;
                v[j + h] = a - b;
            }
    const float s = 1.0f / std::sqrt ((float) n);
    for (int i = 0; i < n; ++i)
        v[i] *= s;
}

struct Lcg
{
    uint32_t seed = 12345;
    float bipolar()
    {
        seed = (seed * 1103515245u + 12345u) & 0x7FFFFFFFu;
        return (float) seed / 2147483647.0f * 2.0f - 1.0f;
    }
};

// Reverse delay: plays the input back in reversed,
// crossfaded chunks (two overlapping grains, one chunk of latency).
struct ReverseDelay
{
    DelayLine d;
    float pos = 0.0f;
    void prepare (double sr, double maxSec) { d.allocate ((int) (maxSec * sr * 2.2) + 8); }
    void reset() { d.clear(); pos = 0.0f; }
    float process (float x, float chunk)
    {
        chunk = std::clamp (chunk, 16.0f, (float) d.maxDelay() / 2.0f);
        d.write (x);
        float y = 0.0f;
        for (int g = 0; g < 2; ++g)
        {
            float p = pos + 0.5f * (float) g;
            p -= std::floor (p);
            // reading point moves backwards through the last recorded chunk
            float delay = 2.0f * p * chunk;
            float win = (float) std::sin (kPi * p);
            y += d.read (delay) * win * win;
        }
        pos += 1.0f / chunk;
        pos -= std::floor (pos);
        d.advance();
        return y;
    }
};
} // namespace vc
