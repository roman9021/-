#pragma once
#include <string>
#include <vector>

namespace vc
{
// One user-facing parameter. Continuous values are in real units; for choice
// parameters `def` is the default index. `skew` > 1 gives finer control at the
// low end (plain = min + (max - min) * normalised^skew).
struct ParamSpec
{
    std::string id;
    std::string name;
    float min = 0.0f, max = 1.0f, def = 0.0f;
    std::string unit;
    float skew = 1.0f;
    std::vector<std::string> choices;
};

inline ParamSpec P(std::string name, float mn, float mx, float def, std::string unit = {}, float skew = 1.0f)
{
    return { name, name, mn, mx, def, std::move(unit), skew, {} };
}

inline ParamSpec C(std::string name, std::vector<std::string> choices, int def = 0)
{
    return { name, name, 0.0f, (float) (choices.size() - 1), (float) def, {}, 1.0f, std::move(choices) };
}
} // namespace vc
