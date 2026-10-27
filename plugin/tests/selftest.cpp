// Renders a noise burst through every mode of every effect and checks the
// output stays finite, bounded and non-silent; also measures RT60 of the
// reverbs against the Decay setting. Exit code 0 on success.
#include <cstdio>
#include <memory>
#include <string>

#include "Effects.h"

using namespace vc;

template <class Fx>
std::vector<float> defaults()
{
    std::vector<float> p;
    for (auto& s : Fx::specs()) p.push_back (s.def);
    return p;
}

template <class Fx>
int sweep (const char* name, int modeIndex)
{
    const double sr = 48000.0;
    const auto specs = Fx::specs();
    int failures = 0;
    for (size_t m = 0; m < specs[(size_t) modeIndex].choices.size(); ++m)
    {
        auto p = defaults<Fx>();
        p[(size_t) modeIndex] = (float) m;
        auto fx = std::make_unique<Fx>();
        fx->prepare (sr);
        fx->update (p.data());
        fx->reset();
        const int block = 512, total = (int) sr * 2;
        std::vector<float> l (block), r (block);
        Lcg rng;
        double peak = 0, energy = 0;
        bool finite = true;
        for (int pos = 0; pos < total; pos += block)
        {
            for (int i = 0; i < block; ++i)
            {
                float x = pos + i < 2000 ? 0.3f * rng.bipolar() : 0.0f;
                l[(size_t) i] = x;
                r[(size_t) i] = x;
            }
            if (pos == block * 20) fx->update (p.data()); // reconfigure mid-stream like an automation tick
            fx->process (l.data(), r.data(), block);
            for (int i = 0; i < block; ++i)
            {
                finite &= std::isfinite (l[(size_t) i]) && std::isfinite (r[(size_t) i]);
                peak = std::max (peak, (double) std::max (std::abs (l[(size_t) i]), std::abs (r[(size_t) i])));
                energy += l[(size_t) i] * l[(size_t) i];
            }
        }
        const bool ok = finite && peak < 4.0 && peak > 1e-4;
        failures += ! ok;
        std::printf ("%s %-13s %-24s peak=%.3f energy=%.3g\n", ok ? "  " : "!!", name,
                     specs[(size_t) modeIndex].choices[m].c_str(), peak, energy);
    }
    return failures;
}

template <class Fx>
double measureRt60 (int decayIndex, float decay, int extraIndex = -1, float extraValue = 0)
{
    const double sr = 48000.0;
    auto p = defaults<Fx>();
    p[(size_t) decayIndex] = decay;
    if (extraIndex >= 0) p[(size_t) extraIndex] = extraValue;
    auto fx = std::make_unique<Fx>();
    fx->prepare (sr);
    fx->update (p.data());
    fx->reset();
    const int n = (int) (sr * (decay * 2 + 1));
    std::vector<float> l ((size_t) n, 0.0f), r ((size_t) n, 0.0f);
    l[0] = r[0] = 1.0f;
    fx->process (l.data(), r.data(), n);
    std::vector<double> edc ((size_t) n + 1, 0.0);
    for (int i = n - 1; i >= 0; --i) edc[(size_t) i] = edc[(size_t) i + 1] + (double) l[(size_t) i] * l[(size_t) i];
    int i5 = 0, i35 = 0;
    for (int i = 0; i < n; ++i)
    {
        double db = 10 * std::log10 (edc[(size_t) i] / edc[0] + 1e-30);
        if (! i5 && db < -5) i5 = i;
        if (! i35 && db < -35) { i35 = i; break; }
    }
    return (i35 - i5) / sr * 2.0;
}

int main()
{
    int f = 0;
    f += sweep<VintageVerbFx> ("vintageverb", VintageVerbFx::ReverbMode);
    f += sweep<VintageVerbFx> ("vintageverb", VintageVerbFx::ColorMode);
    f += sweep<RoomFx> ("room", RoomFx::Type);
    f += sweep<PlateFx> ("plate", PlateFx::Mode_);
    f += sweep<ShimmerFx> ("shimmer", ShimmerFx::Mode_);
    f += sweep<SupermassiveFx> ("supermassive", SupermassiveFx::Mode_);
    f += sweep<DelayFx> ("delay", DelayFx::Mode_);
    f += sweep<DelayFx> ("delay", DelayFx::Style);
    f += sweep<FreqEchoFx> ("freqecho", FreqEchoFx::Mode_);
    f += sweep<SpaceModFx> ("spacemod", SpaceModFx::Mode_);
    f += sweep<UberModFx> ("ubermod", UberModFx::Mode_);

    struct { const char* name; double rt; } rts[] = {
        { "vintageverb", measureRt60<VintageVerbFx> (VintageVerbFx::Decay, 3.0f) },
        { "room", measureRt60<RoomFx> (RoomFx::Decay, 3.0f, RoomFx::Depth, 100.0f) },
        { "plate", measureRt60<PlateFx> (PlateFx::Decay, 3.0f) },
    };
    for (auto& x : rts)
    {
        bool ok = x.rt > 2.4 && x.rt < 3.6;
        f += ! ok;
        std::printf ("%s %-13s Decay=3.0s measured RT60=%.2fs\n", ok ? "  " : "!!", x.name, x.rt);
    }
    std::printf (f ? "FAILED: %d checks\n" : "all checks passed\n", f);
    return f ? 1 : 0;
}
