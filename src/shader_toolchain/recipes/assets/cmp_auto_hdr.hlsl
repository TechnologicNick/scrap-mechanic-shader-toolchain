#include "include/auto_hdr_abi.hlsl"

struct HDRSetting
{
    float fAvg;
    float fMin;
    float fMax;
    float fHDRSignal;
    float fAvgTarget;
    float fMinTarget;
    float fMaxTarget;
    float fHDRSignalTarget;
    float fLow;
    float fHigh;
    float fLowTarget;
    float fHighTarget;
    float3 vAvgColor;
    float fPow;
    float fGlowy;
    float fGlowyTarget;
    float fBase;
    float fRangeRcp;
    float fMaxDepth;
    float fPrevMaxDepth;
    float fMaxDepthTarget;
    float fPrevPrevMaxDepth;
    float fMaxDepthTarget2;
    float fMaxDepthTarget3;
    float fMaxDepthTarget4;
    float fMaxDepthTarget5;
};

cbuffer cb : register(b0)
{
    uint2 cb_vuMaxPixel : packoffset(c0);
    uint2 cb_vuPrevMaxPixel : packoffset(c0.z);
    uint cb_uDispatchCount : packoffset(c1);
    float3 __padd : packoffset(c1.y);
}

RWStructuredBuffer<uint> sbHDRFeedback : register(u0);
RWStructuredBuffer<HDRSetting> sbHDRSetting : register(u1);

static const float adaptationRate = 0.0133333337;

struct Measurements
{
    float3 averageColor;
    float average;
    float minimum;
    float maximum;
    float hdrSignal;
    float low;
    float high;
    float maximumDepth;
};

Measurements ReadMeasurements()
{
    Measurements result;
    uint pixelCount = max(1u, cb_uDispatchCount * 255u);
    uint sampleCount = max(1u, cb_uDispatchCount);
    result.averageColor = float3(
        sbHDRFeedback[0], sbHDRFeedback[1], sbHDRFeedback[2]) / pixelCount;
    result.average = result.averageColor.x + result.averageColor.y;
    result.average += result.averageColor.z;
    result.average *= 0.333333343;
    result.minimum = (float)sbHDRFeedback[3] / pixelCount;
    result.maximum = (float)sbHDRFeedback[4] / pixelCount;
    result.low = (float)sbHDRFeedback[5] / sampleCount;
    result.high = (float)sbHDRFeedback[6] / sampleCount;
    float averageLuminance = dot(
        cb_hdr.vAvgColor, float3(0.298999995, 0.587000012, 0.114));
    result.hdrSignal = saturate(result.high * 1.5 + averageLuminance);
    float encodedDepth = min(1.0, sbHDRFeedback[7] * 0.00392156886);
    result.maximumDepth = max(10.0, 800.0 * encodedDepth);
    return result;
}

float GlowyTarget(float low, float high)
{
    float lowGate = min(1.0, 5.0 * saturate(low - 0.800000012));
    float highGate = 1.0 - min(1.0, 5.0 * high);
    return highGate * lowGate;
}

void SetIndoorCurve(inout HDRSetting setting, float glowyTarget)
{
    float minimumHdr = setting.fMin * setting.fHDRSignal;
    setting.fPow = mad(1.0 - setting.fHDRSignal, -0.100000001, 1.04999995);
    float rangeA = setting.fMax * mad(setting.fHDRSignal, -6.0, 8.0);
    float rangeBase = mad(minimumHdr, 0.0500000007, 0.5);
    rangeA = min(1.25, max(rangeA, rangeBase));
    float rangeB = max(setting.fMax, rangeBase);
    float range = mad(setting.fHDRSignal, rangeA - rangeB, rangeB);
    range = mad(minimumHdr, -0.0500000007, range);
    setting.fBase = 0.0500000007 * minimumHdr;
    setting.fRangeRcp = rcp(range);
    setting.fGlowyTarget = saturate(glowyTarget);
}

void SetDepthReset(inout HDRSetting setting, float measuredDepth)
{
    float oldDepth = setting.fMaxDepth;
    float oldPreviousDepth = setting.fPrevMaxDepth;
    setting.fMaxDepth = 150.0 * ceil(measuredDepth * 0.00666666683);
    setting.fPrevMaxDepth = oldDepth;
    setting.fMaxDepthTarget = measuredDepth;
    setting.fPrevPrevMaxDepth = oldPreviousDepth;
    setting.fMaxDepthTarget2 = measuredDepth;
    setting.fMaxDepthTarget3 = measuredDepth;
    setting.fMaxDepthTarget4 = measuredDepth;
    setting.fMaxDepthTarget5 = measuredDepth;
}

void SetDepthAdapted(inout HDRSetting setting, float measuredDepth)
{
    float oldDepth = setting.fMaxDepth;
    float oldPreviousDepth = setting.fPrevMaxDepth;
    setting.fMaxDepthTarget = mad(
        measuredDepth - setting.fMaxDepthTarget,
        adaptationRate, setting.fMaxDepthTarget);
    setting.fMaxDepthTarget2 = mad(
        setting.fMaxDepthTarget - setting.fMaxDepthTarget2,
        adaptationRate, setting.fMaxDepthTarget2);
    setting.fMaxDepthTarget3 = mad(
        setting.fMaxDepthTarget2 - setting.fMaxDepthTarget3,
        adaptationRate, setting.fMaxDepthTarget3);
    setting.fMaxDepthTarget4 = mad(
        setting.fMaxDepthTarget3 - setting.fMaxDepthTarget4,
        adaptationRate, setting.fMaxDepthTarget4);
    setting.fMaxDepthTarget5 = mad(
        setting.fMaxDepthTarget4 - setting.fMaxDepthTarget5,
        adaptationRate, setting.fMaxDepthTarget5);
    setting.fMaxDepth = 150.0 * ceil(
        setting.fMaxDepthTarget5 * 0.00666666683);
    setting.fPrevMaxDepth = oldDepth;
    setting.fPrevPrevMaxDepth = oldPreviousDepth;
}

void ResetSettings(inout HDRSetting setting, Measurements measured)
{
    setting.fAvg = min(1.0, measured.average);
    setting.fMin = min(1.0, measured.minimum);
    setting.fMax = min(1.0, measured.maximum);
    setting.fHDRSignal = measured.hdrSignal;
    setting.fAvgTarget = setting.fAvg;
    setting.fMinTarget = setting.fMin;
    setting.fMaxTarget = setting.fMax;
    setting.fHDRSignalTarget = setting.fHDRSignal;
    setting.fLow = min(1.0, measured.low);
    setting.fHigh = min(1.0, measured.high);
    setting.fLowTarget = setting.fLow;
    setting.fHighTarget = setting.fHigh;
    setting.vAvgColor = measured.averageColor;
    setting.fPow = 1.0;
    float desiredGlowy = GlowyTarget(measured.low, measured.high);
#if defined(OUTDOOR)
    setting.fGlowy = 0.0;
    setting.fGlowyTarget = desiredGlowy;
    setting.fBase = 0.0;
    setting.fRangeRcp = 1.0;
#else
    setting.fGlowy = desiredGlowy;
    setting.fGlowyTarget = desiredGlowy;
    SetIndoorCurve(setting, desiredGlowy);
#endif
    SetDepthReset(setting, measured.maximumDepth);
}

float AdaptValue(float current, float target, float measured,
                 out float adaptedTarget)
{
    adaptedTarget = mad(measured - target, adaptationRate, target);
    return saturate(mad(adaptedTarget - current, adaptationRate, current));
}

void AdaptSettings(inout HDRSetting setting, Measurements measured)
{
    setting.fAvg = AdaptValue(
        setting.fAvg, setting.fAvgTarget, measured.average,
        setting.fAvgTarget);
    setting.fMin = AdaptValue(
        setting.fMin, setting.fMinTarget, measured.minimum,
        setting.fMinTarget);
    setting.fMax = AdaptValue(
        setting.fMax, setting.fMaxTarget, measured.maximum,
        setting.fMaxTarget);
    setting.fHDRSignal = AdaptValue(
        setting.fHDRSignal, setting.fHDRSignalTarget, measured.hdrSignal,
        setting.fHDRSignalTarget);
    setting.fLow = AdaptValue(
        setting.fLow, setting.fLowTarget, measured.low,
        setting.fLowTarget);
    setting.fHigh = AdaptValue(
        setting.fHigh, setting.fHighTarget, measured.high,
        setting.fHighTarget);
    setting.vAvgColor = measured.averageColor;
    float desiredGlowy = GlowyTarget(measured.low, measured.high);
#if defined(OUTDOOR)
    setting.fPow = 1.0;
    setting.fGlowy = 0.0;
    setting.fGlowyTarget = saturate(mad(
        desiredGlowy - setting.fGlowyTarget,
        adaptationRate, setting.fGlowyTarget));
    setting.fBase = 0.0;
    setting.fRangeRcp = 1.0;
#else
    setting.fGlowyTarget = mad(
        desiredGlowy - setting.fGlowyTarget,
        adaptationRate, setting.fGlowyTarget);
    setting.fGlowy = saturate(mad(
        setting.fGlowyTarget - setting.fGlowy,
        adaptationRate, setting.fGlowy));
    SetIndoorCurve(setting, setting.fGlowyTarget);
#endif
    SetDepthAdapted(setting, measured.maximumDepth);
}

[numthreads(1, 1, 1)]
void mainCS()
{
    Measurements measured = ReadMeasurements();
    HDRSetting setting = sbHDRSetting[0];
#if defined(RESET)
    ResetSettings(setting, measured);
#else
    AdaptSettings(setting, measured);
#endif
    sbHDRSetting[0] = setting;
#if defined(CLEAR_FEEDBACK)
    [unroll]
    for (uint index = 0; index < 8; ++index)
    {
        sbHDRFeedback[index] = 0;
    }
#endif
}
