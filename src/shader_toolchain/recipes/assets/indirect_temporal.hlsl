#include "include/post_fxaa_abi.hlsl"
#if defined(PS_SSGI)
#include "include/hdr_abi.hlsl"
#endif

SamplerState PointClamp : register(s1);
SamplerState LinearClamp : register(s6);
Texture2D<float> currentDepthTexture : register(t1);
Texture2D<float> previousVolatilityTexture : register(t3);
Texture2D<float> previousDepthTexture : register(t4);
#if defined(PS_SSGI)
Texture2D<float2> packedIndirectTexture : register(t0);
Texture2D<float3> previousHdrTexture : register(t5);
#endif

float3 TransformPosition(float4x4 matrixValue, float3 position)
{
    float3 transformed = matrixValue._m01_m11_m21 * position.y;
    transformed = mad(matrixValue._m00_m10_m20, position.x, transformed);
    transformed = mad(matrixValue._m02_m12_m22, position.z, transformed);
    return matrixValue._m03_m13_m23 + transformed;
}

float3 ProjectPosition(float4x4 matrixValue, float3 position)
{
    float3 projected = matrixValue._m01_m11_m31 * position.y;
    projected = mad(matrixValue._m00_m10_m30, position.x, projected);
    projected = mad(matrixValue._m02_m12_m32, position.z, projected);
    return matrixValue._m03_m13_m33 + projected;
}

float3 ReconstructViewPosition(float depth, float2 unscaledUv)
{
    float2 screen = mad(unscaledUv, float2(-1.0, 1.0), float2(1.0, 0.0));
    screen = mad(screen, 2.0, -1.0);
    float2 viewRay = cb_vNearFarViewCorner.wz * screen;
    return float3(viewRay * depth, -depth);
}

float3 ReconstructPreviousWorldPosition(float depth, float2 previousUv)
{
    float2 screen = mad(previousUv, 2.0, -1.0);
    float2 viewRay = cb_vPrevViewCorner * screen;
    return TransformPosition(
        cb_xPrevViewToWorld, float3(viewRay * depth, -depth));
}

float3 EstimateWorldNormal(float3 viewPosition)
{
    // This is the compiler's component ordering for the original coarse
    // derivative cross product. Keeping it explicit preserves edge behavior.
    float3 vertical = ddy_coarse(viewPosition.zyx);
    float3 horizontal = ddx_coarse(viewPosition.xzy);
    float3 products = horizontal * vertical;
    float3 normal = vertical.zxy * horizontal.yzx - products;
    return normal * rsqrt(dot(normal, normal));
}

struct TemporalState
{
    float history;
    float discontinuity;
    float2 projectedUv;
    float2 unscaledUv;
    float3 worldPosition;
};

TemporalState EvaluateTemporalHistory(
    float depth, float2 scaledUv, float2 unscaledUv, float depthMip)
{
    TemporalState state;
    float3 viewPosition = ReconstructViewPosition(depth, unscaledUv);
    state.worldPosition = TransformPosition(viewToWorld, viewPosition);

    float3 previousView = TransformPosition(
        cb_xPrevWorldToView, state.worldPosition);
    float3 clipBounds = ProjectPosition(
        cb_xPrevWorldToViewProjection, state.worldPosition);
    float3 previousClip = ProjectPosition(
        cb_xPrevViewToProjection, previousView);
    float2 previousNdc = previousClip.xy / previousClip.z;
    float2 previousUv = mad(previousNdc, float2(0.5, -0.5), 0.5);
    state.projectedUv = cb_vRenderScale * previousUv;
    state.unscaledUv = cb_vInvRenderScale * state.projectedUv;

    bool onScreen = all(abs(clipBounds.xy) < clipBounds.z);
    if (!onScreen)
    {
        state.history = 1.0;
        state.discontinuity = 1.0;
        return state;
    }

    float3 normal = EstimateWorldNormal(viewPosition);
    float upward = dot(viewToWorld._m20_m21_m22, normal) - 0.899999976;
    upward = saturate(10.0 * upward);

    float threshold = depth * depth;
    threshold *= mad(cb_f720To4K, -0.0199999996, 0.0299999993);
    threshold = min(0.5, max(0.00999999978, threshold));
    float distanceThreshold = max(
        0.00999999978 * max(0.0, depth - 2.0) * max(0.0, depth - 2.0),
        mad(upward, 0.100000001, 0.00100000005));

    float2 previousScaledUv = cb_vPrevRenderScale * state.unscaledUv;
    float previousDepth = previousDepthTexture.SampleLevel(
        LinearClamp, previousScaledUv, depthMip);
    float2 previousWorldUv = float2(
        state.unscaledUv.x,
        1.0 - state.projectedUv.y * cb_vInvRenderScale.y);
    float3 previousWorld = ReconstructPreviousWorldPosition(
        previousDepth, previousWorldUv);
    float3 movement = state.worldPosition - previousWorld;
    float movementDistance = sqrt(dot(movement, movement));

    float4 gatheredDepth = previousDepthTexture.Gather(LinearClamp, scaledUv);
    float averageDepth = dot(gatheredDepth, 0.25);
    float depthDelta = averageDepth - depth;
    bool moved = distanceThreshold < movementDistance;
    bool depthChanged = threshold < abs(depthDelta);

    float volatility = previousVolatilityTexture.SampleLevel(
        LinearClamp, previousScaledUv, 0.0);
    bool forcedHistory = volatility < 0.0;
    volatility = dot(volatility.xxxx, 0.25);
    float depthAttenuation = mad(saturate(0.166666672 * depth), -0.0399999619,
                                 0.959999979);
    volatility *= depthAttenuation;
    volatility = forcedHistory ? 1.0 : volatility;
    volatility = 0.0944881886 >= volatility ? 0.0 : volatility;

    state.history = moved ? (depthChanged ? 1.0 : -1.0) : volatility;
    state.discontinuity = abs(state.history) > 0.100000001 ? 1.0 : 0.0;
    return state;
}

#if defined(PS_SSGI)
float3 DecodePackedIndirect(float encoded)
{
    uint packed = (uint)mad(encoded, 65535.0, 0.5);
    uint intensityBits = (packed >> 10) & 63;
    uint firstChromaBits = packed & 31;
    uint secondChromaBits = (packed >> 5) & 31;
    float intensity = intensityBits * 0.0158730168;
    intensity *= intensity;
    intensity *= intensity;
    intensity *= 64.0;
    float2 chroma = mad(
        float2(firstChromaBits, secondChromaBits), 0.0666666701, -1.0);
    chroma *= abs(chroma);
    precise float doubledSecondChroma = chroma.y + chroma.y;
    precise float redBase = mad(chroma.y, 2.0, 1.0);
    precise float red = mad(-chroma.x, 2.0, redBase);
    precise float green = mad(chroma.x, 2.0, 1.0);
    precise float blueOffset = mad(-chroma.x, 2.0, -doubledSecondChroma);
    precise float blue = 1.0 + blueOffset;
    return max(0.0, float3(red, green, blue) * intensity);
}

float EncodePackedIndirect(float3 indirect)
{
    float redBlue = indirect.r - indirect.b;
    float redBlueAverage = mad(redBlue, 0.5, indirect.b);
    float greenOffset = indirect.g - redBlueAverage;
    float intensity = mad(greenOffset, 0.5, redBlueAverage);
    uint intensityBits = (uint)mad(
        sqrt(sqrt(saturate(intensity * 0.015625))), 63.0, 0.5);
    float inverseIntensity = rcp(max(0.00999999978, intensity));
    float2 chroma = float2(redBlue, greenOffset) * inverseIntensity;
    float2 normalization = rsqrt(max(0.0000999999975, 4.0 * abs(chroma)));
    chroma *= normalization;
    uint2 chromaBits = (uint2)min(30.0, max(0.0, mad(chroma, 15.0, 15.5)));
    uint packed = intensityBits * 1024 + (chromaBits.x << 5) + chromaBits.y;
    return packed * 0.0000152590219;
}

struct TemporalOutput
{
    float volatility : SV_Target0;
    float2 packedIndirectAndDepth : SV_Target1;
    float3 previousHdr : SV_Target2;
};

TemporalOutput mainPS(
    float4 position : SV_Position0,
    float2 scaledUv : UV0,
    float2 unscaledUv : UNSCALED_UV0)
{
    TemporalOutput output;
#if defined(PS_ULTRA)
    const float depthMip = 1.0;
#else
    const float depthMip = 2.0;
#endif
    float depth = currentDepthTexture.SampleLevel(PointClamp, scaledUv, depthMip);
    TemporalState temporal = EvaluateTemporalHistory(
        depth, scaledUv, unscaledUv, depthMip);
    if (depth > 800.0)
    {
        output.volatility = temporal.history;
        output.packedIndirectAndDepth = float2(0.00755321607, 1.0);
        output.previousHdr = 0.0;
        return output;
    }

    float2 motion = unscaledUv
        - temporal.projectedUv * cb_vInvRenderScale;
    float2 historyUv = temporal.unscaledUv
        + temporal.discontinuity * motion;
    historyUv *= cb_vPrevRenderScale;
    float2 movedPacked = packedIndirectTexture.SampleLevel(
        PointClamp, historyUv, 0.0);
    float3 movedIndirect = DecodePackedIndirect(movedPacked.x);

    float reconstructedDepth = mad(
        movedPacked.y * movedPacked.y, hdr.maximumDepth - 0.100000001,
        0.100000001);
    float threshold = reconstructedDepth * reconstructedDepth;
    threshold *= mad(cb_f720To4K, -0.0199999996, 0.0299999993);
    threshold = min(0.5, max(0.00999999978, threshold));
    threshold *= 4.0;
    float3 cameraDelta =
        viewToWorld._m03_m13_m23 - cb_xPrevViewToWorld._m03_m13_m23;
    threshold = max(sqrt(dot(cameraDelta, cameraDelta)), threshold);
    float depthAgreement = 1.0 - min(1.0,
        abs(depth - reconstructedDepth) / threshold);
    movedIndirect *= depthAgreement;

    float2 originalUv = cb_vPrevRenderScale * temporal.unscaledUv;
    float3 stationaryIndirect = DecodePackedIndirect(
        packedIndirectTexture.SampleLevel(PointClamp, originalUv, 0.0).x);
    float historyBlend = mad(abs(temporal.history), -0.375, 0.5);
    float3 indirect = mad(
        stationaryIndirect - movedIndirect, historyBlend, movedIndirect);
    output.packedIndirectAndDepth.x = EncodePackedIndirect(indirect);
    output.packedIndirectAndDepth.y = sqrt(saturate(
        (depth - 0.100000001) / (hdr.maximumDepth - 0.100000001)));

    float3 previousHdr = previousHdrTexture.SampleLevel(
        LinearClamp, originalUv, 0.0);
    previousHdr *= 0.884955764;
    float luminance = dot(previousHdr, float3(0.298999995, 0.587000012, 0.114));
    previousHdr /= mad(luminance, 0.200000003, 1.39999998);
    float indirectScale = max(1.0, dot(indirect, 0.333333343) * 0.125);
    previousHdr *= indirectScale;
    previousHdr *= mad(1.0 - abs(temporal.history), 0.200000003, 0.800000012);
    output.previousHdr = previousHdr;
    output.volatility = temporal.history;
    return output;
}
#else
float mainPS(
    float4 position : SV_Position0,
    float2 scaledUv : UV0,
    float2 unscaledUv : UNSCALED_UV0) : SV_Target0
{
    float depth = currentDepthTexture.SampleLevel(PointClamp, scaledUv, 2.0);
    return EvaluateTemporalHistory(depth, scaledUv, unscaledUv, 2.0).history;
}
#endif
