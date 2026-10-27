#pragma once
// The nine effects of the pack: parameter lists (names, ranges, defaults and
// modes mirror the Python package valhalla_clone) and their mapping onto the
// DSP engines. Parameter 0 is always Mix, which the plug-in wrapper applies.
#include <random>
#include <string>

#include "Engines.h"
#include "Fdn.h"
#include "Param.h"

namespace vc
{
inline std::vector<std::string> names (std::initializer_list<const char*> l) { return { l.begin(), l.end() }; }

// ============================================================ VintageVerb
struct VintageVerbFx
{
    struct Mode { const char* name; const double* lines; int n; double size, ed, ld, rand, md, bright, gate; };
    static constexpr double HALL[8] = { 29.7, 37.1, 41.1, 43.7, 53.3, 59.9, 67.1, 79.3 };
    static constexpr double ROOM[8] = { 11.3, 13.7, 17.9, 19.1, 23.3, 27.1, 31.9, 37.3 };
    static constexpr double PLATE[8] = { 7.9, 11.3, 14.9, 17.1, 21.7, 24.9, 28.3, 33.7 };
    static constexpr double CHAMBER[8] = { 17.3, 21.1, 25.7, 29.3, 33.1, 37.9, 41.3, 47.9 };
    static constexpr double AMB[8] = { 5.3, 7.1, 8.9, 10.7, 12.1, 14.3, 16.9, 19.7 };
    static constexpr double LARGE[16] = { 31.1, 37.3, 41.9, 47.3, 53.9, 59.1, 67.3, 73.1, 79.9, 83.3, 89.7, 97.1, 103.9, 109.3, 117.1, 127.3 };
    static const Mode* modes()
    {
        static const Mode m[] = {
            { "Concert Hall", HALL, 8, 1.00, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0 },
            { "Bright Hall", HALL, 8, 1.00, 1.0, 1.0, 0.0, 1.0, 1.6, 0.0 },
            { "Plate", PLATE, 8, 1.00, 1.1, 0.9, 0.0, 0.8, 1.3, 0.0 },
            { "Room", ROOM, 8, 1.00, 0.9, 1.0, 0.0, 0.7, 1.0, 0.0 },
            { "Chamber", CHAMBER, 8, 1.00, 1.0, 1.1, 0.0, 0.8, 1.1, 0.0 },
            { "Random Space", HALL, 8, 1.10, 0.9, 1.0, 0.8, 1.0, 1.0, 0.0 },
            { "Chorus Space", HALL, 8, 1.05, 0.9, 1.0, 0.0, 3.0, 1.0, 0.0 },
            { "Ambience", AMB, 8, 1.00, 1.0, 0.8, 0.0, 0.5, 1.2, 0.0 },
            { "Sanctuary", LARGE, 16, 1.20, 1.0, 1.1, 0.3, 1.2, 0.9, 0.0 },
            { "Dirty Hall", HALL, 8, 1.00, 0.8, 0.8, 0.5, 1.5, 0.8, 0.0 },
            { "Dirty Plate", PLATE, 8, 1.00, 0.9, 0.8, 0.5, 1.5, 1.0, 0.0 },
            { "Smooth Plate", PLATE, 8, 1.00, 1.2, 1.2, 0.0, 0.6, 1.1, 0.0 },
            { "Smooth Room", ROOM, 8, 1.00, 1.2, 1.2, 0.0, 0.5, 1.0, 0.0 },
            { "Smooth Random", HALL, 8, 1.00, 1.2, 1.2, 0.7, 0.8, 1.0, 0.0 },
            { "Nonlin", ROOM, 8, 1.00, 1.0, 1.0, 0.0, 0.5, 1.2, 0.35 },
            { "Chaotic Hall", HALL, 8, 1.10, 1.0, 1.0, 1.0, 2.0, 1.0, 0.0 },
            { "Chaotic Chamber", CHAMBER, 8, 1.00, 1.0, 1.0, 1.0, 2.0, 1.0, 0.0 },
            { "Chaotic Neutral", CHAMBER, 8, 1.00, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0 },
            { "Cathedral", LARGE, 16, 1.50, 1.0, 1.1, 0.2, 1.0, 0.9, 0.0 },
            { "Palace", LARGE, 16, 1.30, 1.1, 1.1, 0.2, 1.0, 1.1, 0.0 },
            { "Chamber1979", CHAMBER, 8, 1.00, 0.9, 0.9, 0.0, 0.6, 0.8, 0.0 },
            { "Hall1984", HALL, 8, 1.00, 0.9, 0.9, 0.0, 0.8, 0.9, 0.0 },
        };
        return m;
    }
    static constexpr int kNumModes = 22;

    enum { Mix, PreDelay, Decay, Size, Attack, EarlyDiff, LateDiff, ModRate, ModDepth, HighCut, LowCut,
           BassMult, BassXover, HighShelf, HighFreq, ColorMode, ReverbMode };

    static std::vector<ParamSpec> specs()
    {
        std::vector<std::string> modeNames;
        for (int i = 0; i < kNumModes; ++i) modeNames.push_back (modes()[i].name);
        return { P ("Mix", 0, 100, 50, "%"), P ("PreDelay", 0, 500, 0, "ms"), P ("Decay", 0.2f, 70, 2, "s", 3),
                 P ("Size", 0, 100, 50, "%"), P ("Attack", 0, 100, 50, "%"), P ("EarlyDiffusion", 0, 100, 70, "%"),
                 P ("LateDiffusion", 0, 100, 70, "%"), P ("ModRate", 0.01f, 10, 0.5f, "Hz", 2), P ("ModDepth", 0, 100, 50, "%"),
                 P ("HighCut", 200, 20000, 8000, "Hz", 2), P ("LowCut", 10, 2000, 10, "Hz", 2), P ("BassMult", 0.25f, 4, 1.2f, "x"),
                 P ("BassXover", 100, 2000, 600, "Hz", 2), P ("HighShelf", -24, 0, -3, "dB"), P ("HighFreq", 1000, 20000, 6000, "Hz", 2),
                 C ("ColorMode", names ({ "1970s", "1980s", "Now" }), 1), C ("ReverbMode", modeNames, 0) };
    }

    FdnReverb fdn;
    void prepare (double sr) { fdn.prepare (sr, 127.3 * 2.55 + 5.0, 500.0); }
    void reset() { fdn.reset(); }
    void process (float* l, float* r, int n) { fdn.process (l, r, n); }

    void update (const float* p)
    {
        const Mode& m = modes()[(int) p[ReverbMode]];
        static constexpr double colSr[3] = { 10000.0, 24000.0, 0.0 }, colHc[3] = { 4500.0, 10000.0, 20000.0 };
        static constexpr int colBits[3] = { 12, 16, 0 };
        const int col = (int) p[ColorMode];
        FdnConfig c;
        c.predelayMs = p[PreDelay];
        c.rt60 = p[Decay];
        c.size = (0.3 + 1.4 * p[Size] / 100.0) * m.size;
        c.numLines = m.n;
        std::copy (m.lines, m.lines + m.n, c.delaysMs.begin());
        c.inDiffGain = std::min (0.75 * m.ed * p[EarlyDiff] / 100.0, 0.8);
        c.attack = p[Attack] / 100.0;
        c.loopDiffGain = std::min (0.6 * m.ld * p[LateDiff] / 100.0, 0.75);
        c.modRate = p[ModRate];
        c.modDepthMs = 1.5 * m.md * p[ModDepth] / 100.0;
        c.modRandom = m.rand;
        c.bassMult = p[BassMult];
        c.bassXover = p[BassXover];
        c.highMult = std::min (std::max (std::pow (10.0, p[HighShelf] / 20.0) * m.bright, 0.05), 1.0);
        c.highXover = p[HighFreq];
        c.lowCut = p[LowCut];
        c.highCut = std::min ((double) p[HighCut], colHc[col]);
        c.gateTime = m.gate;
        c.colorBits = colBits[col];
        c.colorSr = colSr[col];
        fdn.configure (c);
    }
};

// =================================================================== Room
struct RoomFx
{
    struct Mode { const char* name; bool space; int taps; double curve, size, bright, gate; };
    static const Mode* modes()
    {
        static const Mode m[] = {
            { "Large Room", false, 12, 1.0, 1.2, 1.0, 0.0 },  { "Medium Room", false, 10, 1.0, 0.9, 1.0, 0.0 },
            { "Bright Room", false, 10, 1.0, 1.0, 1.6, 0.0 }, { "Large Chamber", false, 14, 0.8, 1.4, 1.1, 0.0 },
            { "Dark Room", false, 10, 1.0, 1.0, 0.5, 0.0 },   { "Large Space", true, 14, 0.7, 1.3, 1.0, 0.0 },
            { "Dark Space", true, 12, 0.7, 1.3, 0.5, 0.0 },   { "Small Space", true, 8, 1.2, 0.6, 1.0, 0.0 },
            { "Nonlinear", false, 16, 1.0, 1.0, 1.1, 0.3 },   { "Narrow Tail", false, 10, 1.0, 1.0, 1.0, 0.0 },
        };
        return m;
    }
    static constexpr int kNumModes = 10;
    enum { Mix, PreDelay, Decay, HighCut, Depth, EarlySize, EarlyCross, EarlyModRate, EarlyModDepth, EarlySend, LateSize,
           LateCross, LateModRate, LateModDepth, Diffusion, Spin, Wander, BassMult, BassXover, HighMult, HighXover, Type };

    static std::vector<ParamSpec> specs()
    {
        std::vector<std::string> modeNames;
        for (int i = 0; i < kNumModes; ++i) modeNames.push_back (modes()[i].name);
        return { P ("Mix", 0, 100, 50, "%"), P ("PreDelay", 0, 500, 10, "ms"), P ("Decay", 0.1f, 100, 2, "s", 3),
                 P ("HighCut", 200, 20000, 8000, "Hz", 2), P ("Depth", 0, 100, 50, "%"), P ("EarlySize", 2, 100, 40, "ms"),
                 P ("EarlyCross", 0, 100, 20, "%"), P ("EarlyModRate", 0.1f, 10, 1, "Hz", 2), P ("EarlyModDepth", 0, 100, 20, "%"),
                 P ("EarlySend", 0, 100, 30, "%"), P ("LateSize", 0, 100, 50, "%"), P ("LateCross", 0, 100, 20, "%"),
                 P ("LateModRate", 0.1f, 10, 0.7f, "Hz", 2), P ("LateModDepth", 0, 100, 40, "%"), P ("Diffusion", 0, 100, 80, "%"),
                 P ("Spin", 0, 5, 0.6f, "Hz"), P ("Wander", 0, 100, 20, "%"), P ("BassMult", 0.25f, 4, 1, "x"),
                 P ("BassXover", 100, 2000, 500, "Hz", 2), P ("HighMult", 0.1f, 1, 0.6f, "x"), P ("HighXover", 1000, 20000, 5000, "Hz", 2),
                 C ("Type", modeNames, 0) };
    }

    FdnReverb fdn;
    void prepare (double sr) { fdn.prepare (sr, 71.9 * 2.24 + 5.0, 500.0 + 100.0 + 10.0); }
    void reset() { fdn.reset(); }
    void process (float* l, float* r, int n) { fdn.process (l, r, n); }

    void update (const float* p)
    {
        static constexpr double ROOM[8] = { 13.1, 16.7, 19.3, 23.9, 27.7, 31.3, 37.1, 41.9 };
        static constexpr double SPACE[8] = { 23.3, 29.9, 35.3, 41.1, 47.9, 55.3, 61.7, 71.9 };
        const int mi = (int) p[Type];
        const Mode& m = modes()[mi];
        FdnConfig c;
        c.inDiffMs = { 3.91, 2.87, 9.73, 7.13 };
        c.predelayMs = p[PreDelay];
        c.rt60 = p[Decay];
        c.size = (0.4 + 1.2 * p[LateSize] / 100.0) * m.size;
        c.numLines = 8;
        std::copy (m.space ? SPACE : ROOM, (m.space ? SPACE : ROOM) + 8, c.delaysMs.begin());
        c.inDiffGain = 0.7 * p[Diffusion] / 100.0;
        c.attack = 0.2;
        c.loopDiffGain = 0.55 * p[Diffusion] / 100.0;
        c.modRate = p[LateModRate];
        c.modDepthMs = 1.2 * p[LateModDepth] / 100.0;
        c.modRandom = p[Wander] / 100.0;
        c.randRate = p[Spin] * 4.0;
        c.bassMult = p[BassMult];
        c.bassXover = p[BassXover];
        c.highMult = std::min (p[HighMult] * m.bright, 1.0);
        c.highXover = p[HighXover];
        c.lowCut = 20.0;
        c.highCut = p[HighCut];
        c.width = (1.0 - p[LateCross] / 100.0) * (mi == 9 ? 0.3 : 1.0);
        // deterministic early-reflection pattern per mode
        std::mt19937 rng ((unsigned) (mi * 7919 + 17));
        std::uniform_real_distribution<double> uni (0.04, 1.0);
        c.numTaps = m.taps;
        for (int k = 0; k < m.taps; ++k) c.erTapsMs[(size_t) k] = uni (rng);
        std::sort (c.erTapsMs.begin(), c.erTapsMs.begin() + m.taps);
        for (int k = 0; k < m.taps; ++k)
        {
            double pos = std::pow (c.erTapsMs[(size_t) k], m.curve);
            double sign = (rng() & 1) ? 1.0 : -1.0;
            c.erGains[(size_t) k] = (1.0 - 0.7 * pos) * sign / std::sqrt (m.taps / 2.0);
            c.erTapsMs[(size_t) k] = pos * p[EarlySize];
        }
        const double depth = p[Depth] / 100.0;
        c.erLevel = 1.0 - depth;
        c.erSend = p[EarlySend] / 100.0;
        c.lateLevel = depth;
        c.gateTime = m.gate;
        c.erModRate = p[EarlyModRate];
        c.erModDepthMs = 0.4 * p[EarlyModDepth] / 100.0;
        c.erWidth = 1.0 - p[EarlyCross] / 100.0;
        fdn.configure (c);
    }
};

// ================================================================== Plate
struct PlateFx
{
    struct Mode { const char* name; double bw, damp, i1, i2, d1, d2, size; };
    static const Mode* modes()
    {
        static const Mode m[] = {
            { "Steel", 0.9995, 0.0005, 0.75, 0.625, 0.70, 0.50, 1.00 }, { "Aluminum", 0.9995, 0.0002, 0.78, 0.66, 0.72, 0.55, 0.90 },
            { "Brass", 0.9, 0.12, 0.75, 0.625, 0.70, 0.50, 1.05 },      { "Gold", 0.85, 0.20, 0.76, 0.64, 0.68, 0.48, 1.10 },
            { "Bronze", 0.8, 0.30, 0.74, 0.62, 0.66, 0.46, 1.10 },      { "Copper", 0.88, 0.15, 0.70, 0.58, 0.64, 0.44, 0.95 },
            { "Silver", 0.97, 0.05, 0.78, 0.66, 0.70, 0.52, 0.85 },     { "Platinum", 0.99, 0.02, 0.80, 0.70, 0.74, 0.56, 1.20 },
            { "Titanium", 0.995, 0.01, 0.72, 0.60, 0.70, 0.50, 0.75 },
        };
        return m;
    }
    static constexpr int kNumModes = 9;
    enum { Mix, PreDelay, Decay, Size, Width, ModRate, ModDepth, LowCut, HighCut, BassMult, BassXover, Mode_ };

    static std::vector<ParamSpec> specs()
    {
        std::vector<std::string> modeNames;
        for (int i = 0; i < kNumModes; ++i) modeNames.push_back (modes()[i].name);
        return { P ("Mix", 0, 100, 50, "%"), P ("PreDelay", 0, 500, 0, "ms"), P ("Decay", 0.1f, 60, 2.5f, "s", 3),
                 P ("Size", 0, 100, 50, "%"), P ("Width", 0, 100, 100, "%"), P ("ModRate", 0.01f, 5, 0.8f, "Hz", 2),
                 P ("ModDepth", 0, 100, 30, "%"), P ("LowCut", 10, 2000, 20, "Hz", 2), P ("HighCut", 200, 20000, 9000, "Hz", 2),
                 P ("BassMult", 0.25f, 4, 1, "x"), P ("BassXover", 100, 2000, 400, "Hz", 2), C ("Mode", modeNames, 0) };
    }

    PlateReverb plate;
    void prepare (double sr) { plate.prepare (sr, 1.65 * 1.2); }
    void reset() { plate.reset(); }
    void process (float* l, float* r, int n) { plate.process (l, r, n); }
    void update (const float* p)
    {
        const Mode& m = modes()[(int) p[Mode_]];
        PlateReverb::Config c;
        c.predelayMs = p[PreDelay];
        c.rt60 = p[Decay];
        c.size = (0.35 + 1.3 * p[Size] / 100.0) * m.size;
        c.width = p[Width] / 100.0;
        c.bandwidth = m.bw;
        c.damping = m.damp;
        c.inDiff1 = m.i1;
        c.inDiff2 = m.i2;
        c.decDiff1 = m.d1;
        c.decDiff2 = m.d2;
        c.modRate = p[ModRate];
        c.modDepth = 16.0 * p[ModDepth] / 100.0;
        c.lowCut = p[LowCut];
        c.highCut = p[HighCut];
        c.bassMult = p[BassMult];
        c.bassXover = p[BassXover];
        plate.configure (c);
    }
};

// ================================================================ Shimmer
struct ShimmerFx
{
    enum { Mix, PreDelay, Size, Feedback, Diffusion, Shift, ShiftMix, ModRate, ModDepth, LowCut, HighCut, Mode_ };

    static std::vector<ParamSpec> specs()
    {
        return { P ("Mix", 0, 100, 50, "%"), P ("PreDelay", 0, 500, 0, "ms"), P ("Size", 0, 100, 60, "%"),
                 P ("Feedback", 0, 100, 80, "%"), P ("Diffusion", 0, 100, 80, "%"), P ("Shift", -24, 24, 12, "st"),
                 P ("ShiftMix", 0, 100, 50, "%"), P ("ModRate", 0.01f, 10, 0.4f, "Hz", 2), P ("ModDepth", 0, 100, 40, "%"),
                 P ("LowCut", 10, 2000, 120, "Hz", 2), P ("HighCut", 200, 20000, 7000, "Hz", 2),
                 C ("Mode", names ({ "Mono", "Stereo", "Reverse", "Bloom" }), 1) };
    }

    FdnReverb fdn;
    ReverseDelay rev[2];
    bool reverse = false;
    float chunk = 1000;
    double sr = 44100;

    void prepare (double s)
    {
        sr = s;
        fdn.prepare (sr, 73.1 * 2.0 + 5.0, 500.0);
        rev[0].prepare (sr, 0.7);
        rev[1].prepare (sr, 0.7);
    }
    void reset() { fdn.reset(); rev[0].reset(); rev[1].reset(); }
    void process (float* l, float* r, int n)
    {
        if (reverse)
            for (int t = 0; t < n; ++t)
            {
                l[t] = rev[0].process (l[t], chunk);
                r[t] = rev[1].process (r[t], chunk);
            }
        fdn.process (l, r, n);
    }
    void update (const float* p)
    {
        static constexpr double LINES[8] = { 31.1, 37.3, 41.9, 47.3, 53.9, 59.1, 67.3, 73.1 };
        const int mode = (int) p[Mode_];
        reverse = mode == 2;
        chunk = (float) ((0.15 + 0.5 * p[Size] / 100.0) * sr);
        FdnConfig c;
        c.predelayMs = p[PreDelay];
        c.size = 0.4 + 1.6 * p[Size] / 100.0;
        std::copy (LINES, LINES + 8, c.delaysMs.begin());
        c.inDiffGain = 0.75 * p[Diffusion] / 100.0;
        c.attack = mode == 3 ? 1.0 : 0.3;
        c.loopDiffGain = 0.6 * p[Diffusion] / 100.0;
        c.modRate = p[ModRate];
        c.modDepthMs = 1.5 * p[ModDepth] / 100.0;
        c.modRandom = 0.2;
        c.bassXover = 300;
        c.highMult = 0.6;
        c.highXover = 4000;
        c.lowCut = p[LowCut];
        c.highCut = p[HighCut];
        c.fbOverride = 0.985 * std::sqrt (p[Feedback] / 100.0);
        c.shiftRatio = std::pow (2.0, p[Shift] / 12.0);
        c.shiftAmount = 1.2 * p[ShiftMix] / 100.0 * p[Feedback] / 100.0;
        c.shiftStereo = mode != 0;
        fdn.configure (c);
    }
};

// =========================================================== Supermassive
struct SupermassiveFx
{
    struct Mode { const char* name; int lines; double spread, diff, loop, rand; };
    static const Mode* modes()
    {
        static const Mode m[] = {
            { "Gemini", 8, 0.30, 0.20, 0.10, 0.0 },       { "Hydra", 8, 0.45, 0.35, 0.15, 0.0 },
            { "Centaurus", 8, 0.60, 0.50, 0.25, 0.0 },    { "Sagittarius", 16, 0.80, 0.80, 0.50, 0.0 },
            { "Great Annihilator", 16, 1.00, 1.00, 0.80, 0.0 }, { "Andromeda", 16, 1.10, 0.90, 0.90, 0.2 },
            { "Lyra", 8, 0.70, 0.60, 0.40, 0.3 },         { "Capricorn", 8, 0.90, 0.70, 0.60, 0.0 },
            { "Large Magellanic Cloud", 16, 1.20, 0.95, 0.95, 0.0 }, { "Triangulum", 16, 0.95, 0.85, 0.70, 0.4 },
            { "Cirrus Major", 16, 1.30, 1.00, 0.85, 0.5 }, { "Cirrus Minor", 8, 1.10, 0.90, 0.75, 0.5 },
            { "Aquarius", 8, 0.50, 0.30, 0.60, 0.0 },     { "Pisces", 8, 0.40, 0.25, 0.50, 0.2 },
            { "Scorpio", 16, 0.85, 0.60, 0.40, 0.6 },     { "Libra", 8, 0.65, 0.40, 0.30, 0.0 },
            { "Leo", 16, 1.00, 0.75, 0.65, 0.1 },         { "Virgo", 16, 1.15, 0.70, 0.90, 0.3 },
        };
        return m;
    }
    static constexpr int kNumModes = 18;
    enum { Mix, Delay, Warp, Feedback, Density, Width, LowCut, HighCut, ModRate, ModDepth, Mode_ };

    static std::vector<ParamSpec> specs()
    {
        std::vector<std::string> modeNames;
        for (int i = 0; i < kNumModes; ++i) modeNames.push_back (modes()[i].name);
        return { P ("Mix", 0, 100, 50, "%"), P ("Delay", 0, 5000, 250, "ms", 2), P ("Warp", 0, 100, 50, "%"),
                 P ("Feedback", 0, 100, 60, "%"), P ("Density", 0, 100, 50, "%"), P ("Width", 0, 100, 100, "%"),
                 P ("LowCut", 10, 2000, 20, "Hz", 2), P ("HighCut", 200, 20000, 10000, "Hz", 2),
                 P ("ModRate", 0.01f, 10, 0.4f, "Hz", 2), P ("ModDepth", 0, 100, 30, "%"), C ("Mode", modeNames, 0) };
    }

    FdnReverb fdn;
    void prepare (double sr) { fdn.prepare (sr, 10000.0, 10.0); }
    void reset() { fdn.reset(); }
    void process (float* l, float* r, int n) { fdn.process (l, r, n); }
    void update (const float* p)
    {
        static constexpr double primes[16] = { 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53 };
        const Mode& m = modes()[(int) p[Mode_]];
        const double density = p[Density] / 100.0;
        FdnConfig c;
        c.inDiffMs = { 3.1, 4.3, 5.9, 7.7 };
        c.numLines = m.lines;
        double meanLog = 0;
        for (int i = 0; i < m.lines; ++i) meanLog += std::log (primes[i]) / m.lines;
        const double k = m.spread * (0.15 + 1.85 * p[Warp] / 100.0);
        for (int i = 0; i < m.lines; ++i)
            c.delaysMs[(size_t) i] = std::max (std::max ((double) p[Delay], 2.0) * std::pow (std::log (primes[i]) / meanLog, k), 1.0);
        c.inDiffGain = std::min (0.8 * m.diff * density, 0.8);
        c.loopDiffGain = std::min (0.7 * m.loop * density, 0.75);
        c.modRate = p[ModRate];
        c.modDepthMs = 3.0 * p[ModDepth] / 100.0;
        c.modRandom = m.rand;
        c.bassXover = 300;
        c.highMult = 0.9;
        c.highXover = 6000;
        c.lowCut = p[LowCut];
        c.highCut = p[HighCut];
        c.width = p[Width] / 100.0;
        c.fbOverride = std::min (p[Feedback] / 100.0, 0.995);
        fdn.configure (c);
    }
};

// ================================================================== Delay
struct DelayFx
{
    enum { Mix, DelayL, DelayR, Feedback, Width, Age, Drive, Diffusion, Ducking, ModRate, ModDepth, LowCut, HighCut,
           Pitch, Mode_, Style };

    static std::vector<ParamSpec> specs()
    {
        return { P ("Mix", 0, 100, 30, "%"), P ("DelayL", 1, 5000, 375, "ms", 2), P ("DelayR", 1, 5000, 375, "ms", 2),
                 P ("Feedback", 0, 110, 40, "%"), P ("Width", 0, 100, 100, "%"), P ("Age", 0, 100, 25, "%"),
                 P ("Drive", 0, 100, 0, "%"), P ("Diffusion", 0, 100, 0, "%"), P ("Ducking", 0, 100, 0, "%"),
                 P ("ModRate", 0.01f, 10, 0.5f, "Hz", 2), P ("ModDepth", 0, 100, 20, "%"), P ("LowCut", 10, 2000, 80, "Hz", 2),
                 P ("HighCut", 200, 20000, 8000, "Hz", 2), P ("Pitch", -12, 12, 12, "st"),
                 C ("Mode", names ({ "Tape", "HiFi", "BBD", "Digital", "Ghost", "Pitch", "RevTape" }), 0),
                 C ("Style", names ({ "Single", "Dual", "PingPong" }), 0) };
    }

    EchoDelay echo;
    void prepare (double sr) { echo.prepare (sr, 5000.0 + 5.0); }
    void reset() { echo.reset(); }
    void process (float* l, float* r, int n) { echo.process (l, r, n); }
    void update (const float* p)
    {
        // flutter, noise, bbd, bits, pitch blend, extra diffusion, reverse
        struct M { double flutter, noise; bool bbd; int bits; double pitch, diff; bool rev; };
        static constexpr M modes[7] = { { 1, 1, false, 0, 0, 0, false }, { 0, 0, false, 0, 0, 0, false },
                                        { 0.2, 1, true, 0, 0, 0, false }, { 0, 0, false, 12, 0, 0, false },
                                        { 0.5, 0.5, false, 0, 0.5, 0.4, false }, { 0, 0, false, 0, 1, 0, false },
                                        { 1, 1, false, 0, 0, 0, true } };
        const M& m = modes[(int) p[Mode_]];
        EchoDelay::Config c;
        c.delayL = p[DelayL];
        c.delayR = p[DelayR];
        c.feedback = p[Feedback] / 100.0;
        c.style = (int) p[Style];
        c.width = p[Width] / 100.0;
        c.age = p[Age] / 100.0;
        c.drive = p[Drive] / 100.0;
        c.diffusion = std::min (p[Diffusion] / 100.0 + m.diff, 1.0);
        c.ducking = p[Ducking] / 100.0;
        c.modRate = p[ModRate];
        c.modDepthMs = 2.0 * p[ModDepth] / 100.0 * ((m.flutter > 0 || m.bbd) ? 1.0 : 0.25);
        c.flutter = m.flutter;
        c.lowCut = p[LowCut];
        c.highCut = p[HighCut];
        c.bbd = m.bbd;
        c.digitalBits = m.bits;
        c.pitchRatio = std::pow (2.0, p[Pitch] / 12.0);
        c.pitchAmount = m.pitch;
        c.noise = m.noise;
        c.reverse = m.rev;
        echo.configure (c);
    }
};

// ============================================================== Freq Echo
struct FreqEchoFx
{
    enum { Mix, Delay, Feedback, Shift, LowShift, Width, LowCut, HighCut, Mode_ };
    static std::vector<ParamSpec> specs()
    {
        return { P ("Mix", 0, 100, 50, "%"), P ("Delay", 1, 2000, 200, "ms", 2), P ("Feedback", 0, 100, 50, "%"),
                 P ("Shift", -1000, 1000, 10, "Hz"), C ("LowShift", names ({ "Off", "On" }), 0), P ("Width", 0, 100, 0, "%"),
                 P ("LowCut", 10, 2000, 40, "Hz", 2), P ("HighCut", 200, 20000, 12000, "Hz", 2),
                 C ("Mode", names ({ "Normal", "Analog" }), 0) };
    }
    FreqEchoEngine fe;
    void prepare (double sr) { fe.prepare (sr, 2000.0); }
    void reset() { fe.reset(); }
    void process (float* l, float* r, int n) { fe.process (l, r, n); }
    void update (const float* p)
    {
        FreqEchoEngine::Config c;
        c.delayMs = p[Delay];
        c.feedback = std::min (p[Feedback] / 100.0, 0.999);
        c.shiftHz = p[Shift] / (p[LowShift] > 0.5f ? 100.0 : 1.0);
        c.width = p[Width] / 100.0;
        c.lowCut = p[LowCut];
        c.highCut = p[HighCut];
        c.analog = p[Mode_] > 0.5f;
        fe.configure (c);
    }
};

// ======================================================== Space Modulator
struct SpaceModFx
{
    enum { Mix, Rate, Depth, Feedback, Manual, Width, Mode_ };
    static std::vector<ParamSpec> specs()
    {
        return { P ("Mix", 0, 100, 50, "%"), P ("Rate", 0.01f, 10, 0.25f, "Hz", 2), P ("Depth", 0, 100, 50, "%"),
                 P ("Feedback", -99, 99, 50, "%"), P ("Manual", 0, 10, 0.5f, "ms"), P ("Width", 0, 100, 50, "%"),
                 C ("Mode", names ({ "Flange", "ThruZero", "Barberpole Up", "Barberpole Down", "Chorus", "Doubler", "Vibrato" }), 0) };
    }
    SpaceModEngine sm;
    void prepare (double sr) { sm.prepare (sr); }
    void reset() { sm.reset(); }
    void process (float* l, float* r, int n) { sm.process (l, r, n); }
    void update (const float* p)
    {
        SpaceModEngine::Config c;
        c.rate = p[Rate];
        c.depth = p[Depth] / 100.0;
        c.feedback = p[Feedback] / 100.0;
        c.manualMs = p[Manual];
        c.width = p[Width] / 100.0;
        c.mode = (int) p[Mode_];
        sm.configure (c);
    }
};

// ================================================================ UberMod
struct UberModFx
{
    enum { Mix, Delay, Taps, Warp, Feedback, Density, Width, ModRate, ModDepth, LowCut, HighCut, Drive, Age, Mode_ };
    static std::vector<ParamSpec> specs()
    {
        return { P ("Mix", 0, 100, 50, "%"), P ("Delay", 1, 2000, 300, "ms", 2), P ("Taps", 1, 16, 4),
                 P ("Warp", -100, 100, 0, "%"), P ("Feedback", 0, 100, 30, "%"), P ("Density", 0, 100, 30, "%"),
                 P ("Width", 0, 100, 100, "%"), P ("ModRate", 0.01f, 10, 0.6f, "Hz", 2), P ("ModDepth", 0, 100, 30, "%"),
                 P ("LowCut", 10, 2000, 60, "Hz", 2), P ("HighCut", 200, 20000, 9000, "Hz", 2), P ("Drive", 0, 100, 0, "%"),
                 P ("Age", 0, 100, 0, "%"),
                 C ("Mode", names ({ "Clean", "Tape", "Dark Tape", "BBD", "Lo-Fi", "Diffuse", "Rhythmic" }), 0) };
    }
    MultiTapEngine mt;
    void prepare (double sr) { mt.prepare (sr, 2000.0 + 10.0); }
    void reset() { mt.reset(); }
    void process (float* l, float* r, int n) { mt.process (l, r, n); }
    void update (const float* p)
    {
        // drive add, age add, density add, tap decay
        static constexpr double modes[7][4] = { { 0, 0, 0, 0.3 }, { 0.3, 0.3, 0, 0.4 }, { 0.4, 0.7, 0, 0.5 }, { 0.2, 0.5, 0.1, 0.5 },
                                                { 0.8, 0.8, 0, 0.3 }, { 0, 0.1, 0.6, 0.2 }, { 0, 0, 0, 0 } };
        const double* m = modes[(int) p[Mode_]];
        MultiTapEngine::Config c;
        c.delayMs = p[Delay];
        c.taps = (int) std::lround (p[Taps]);
        c.warp = p[Warp] / 100.0;
        c.feedback = p[Feedback] / 100.0;
        c.density = std::min (p[Density] / 100.0 + m[2], 1.0);
        c.width = p[Width] / 100.0;
        c.modRate = p[ModRate];
        c.modDepthMs = 3.0 * p[ModDepth] / 100.0;
        c.lowCut = p[LowCut];
        c.highCut = p[HighCut];
        c.drive = std::min (p[Drive] / 100.0 + m[0], 1.0);
        c.age = std::min (p[Age] / 100.0 + m[1], 1.0);
        c.tapDecay = m[3];
        mt.configure (c);
    }
};
} // namespace vc
