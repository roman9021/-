// Generic JUCE wrapper: one build target per effect, chosen at compile time
// with VC_EFFECT (the effect struct from Effects.h).
#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_dsp/juce_dsp.h>

#include "Effects.h"

#ifndef VC_EFFECT
 #error "define VC_EFFECT, e.g. -DVC_EFFECT=VintageVerbFx"
#endif

namespace
{
using Fx = vc::VC_EFFECT;

juce::AudioProcessorValueTreeState::ParameterLayout makeLayout()
{
    juce::AudioProcessorValueTreeState::ParameterLayout layout;
    for (const auto& s : Fx::specs())
    {
        const juce::ParameterID id { juce::String (s.id), 1 };
        if (! s.choices.empty())
        {
            juce::StringArray items;
            for (const auto& c : s.choices) items.add (c);
            layout.add (std::make_unique<juce::AudioParameterChoice> (id, s.name, items, (int) s.def));
        }
        else
        {
            juce::NormalisableRange<float> range (s.min, s.max);
            range.skew = 1.0f / s.skew;
            auto attrs = juce::AudioParameterFloatAttributes().withLabel (s.unit);
            layout.add (std::make_unique<juce::AudioParameterFloat> (id, s.name, range, s.def, attrs));
        }
    }
    return layout;
}

class CloneProcessor final : public juce::AudioProcessor
{
public:
    CloneProcessor()
        : AudioProcessor (BusesProperties()
                              .withInput ("Input", juce::AudioChannelSet::stereo(), true)
                              .withOutput ("Output", juce::AudioChannelSet::stereo(), true)),
          state (*this, nullptr, "PARAMS", makeLayout())
    {
        for (const auto& s : Fx::specs())
            raw.push_back (state.getRawParameterValue (juce::String (s.id)));
        values.resize (raw.size());
        last.assign (raw.size(), std::numeric_limits<float>::quiet_NaN());
    }

    const juce::String getName() const override { return JucePlugin_Name; }
    bool acceptsMidi() const override { return false; }
    bool producesMidi() const override { return false; }
    double getTailLengthSeconds() const override { return 20.0; }
    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram (int) override {}
    const juce::String getProgramName (int) override { return "Default"; }
    void changeProgramName (int, const juce::String&) override {}

    bool isBusesLayoutSupported (const BusesLayout& layouts) const override
    {
        const auto out = layouts.getMainOutputChannelSet();
        const auto in = layouts.getMainInputChannelSet();
        return out == juce::AudioChannelSet::stereo()
            && (in == juce::AudioChannelSet::stereo() || in == juce::AudioChannelSet::mono());
    }

    void prepareToPlay (double sampleRate, int blockSize) override
    {
        fx.prepare (sampleRate);
        std::fill (last.begin(), last.end(), std::numeric_limits<float>::quiet_NaN());
        pullParameters();
        fx.reset();
        dry.setSize (2, blockSize);
        mix.reset (sampleRate, 0.05);
        mix.setCurrentAndTargetValue (values[0] / 100.0f);
    }

    void releaseResources() override {}

    void processBlock (juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override
    {
        juce::ScopedNoDenormals noDenormals;
        const int n = buffer.getNumSamples();
        if (getTotalNumInputChannels() == 1)
            buffer.copyFrom (1, 0, buffer, 0, 0, n);

        pullParameters();
        mix.setTargetValue (values[0] / 100.0f);
        dry.setSize (2, n, false, false, true);
        dry.copyFrom (0, 0, buffer, 0, 0, n);
        dry.copyFrom (1, 0, buffer, 1, 0, n);

        float* l = buffer.getWritePointer (0);
        float* r = buffer.getWritePointer (1);
        fx.process (l, r, n);

        const float* dl = dry.getReadPointer (0);
        const float* dr = dry.getReadPointer (1);
        for (int i = 0; i < n; ++i)
        {
            const float m = mix.getNextValue();
            l[i] = dl[i] + m * (l[i] - dl[i]);
            r[i] = dr[i] + m * (r[i] - dr[i]);
        }
    }

    bool hasEditor() const override { return true; }
    juce::AudioProcessorEditor* createEditor() override { return new juce::GenericAudioProcessorEditor (*this); }

    void getStateInformation (juce::MemoryBlock& dest) override
    {
        if (auto xml = state.copyState().createXml())
            copyXmlToBinary (*xml, dest);
    }

    void setStateInformation (const void* data, int size) override
    {
        if (auto xml = getXmlFromBinary (data, size))
            if (xml->hasTagName (state.state.getType()))
                state.replaceState (juce::ValueTree::fromXml (*xml));
    }

private:
    // Re-configure the engine only when a parameter actually moved.
    void pullParameters()
    {
        bool changed = false;
        for (size_t i = 0; i < raw.size(); ++i)
        {
            values[i] = raw[i]->load();
            if (values[i] != last[i]) changed = true;
        }
        if (changed)
        {
            fx.update (values.data());
            last = values;
        }
    }

    juce::AudioProcessorValueTreeState state;
    std::vector<std::atomic<float>*> raw;
    std::vector<float> values, last;
    Fx fx;
    juce::AudioBuffer<float> dry;
    juce::SmoothedValue<float> mix;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (CloneProcessor)
};
} // namespace

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter() { return new CloneProcessor(); }
