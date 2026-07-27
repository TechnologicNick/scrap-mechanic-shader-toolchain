#include "include/post_godrays_projection_abi.hlsl"
#include "include/post_godrays_perframe_abi.hlsl"
#include "include/post_godrays_hdr_abi.hlsl"

SamplerState PointClampClamp : register(s1);
#if defined(PS_UNDER_WATER)
SamplerState LinearWrapWrap : register(s3);
#endif
SamplerState LinearClampClamp : register(s6);
SamplerComparisonState ShadowSamplerLinear : register(s12);

Texture2D<float> sceneDepthTexture : register(t0);
Texture2DArray<float4> cascadeShadowTexture : register(t1);
Texture2D<float> temporalTexture : register(t3);
Texture2D<float> volatilityTexture : register(t4);
#if defined(PS_UNDER_WATER)
Texture2D<float2> waterNormalTexture : register(t5);
#endif

static const uint GOD_RAY_STEP_COUNT = 42;
static const float GOD_RAY_STEP_COUNT_RCP = 1.0 / 41.0;
static const float SHADOW_FILTER_NORMALIZATION = 1.0 / 7.0;

struct GodRayPixelInput
{
    float4 position : SV_Position0;
    float2 uv : UV0;
    float2 unscaledUv : UNSCALED_UV0;
};

struct GodRayPixelOutput
{
    float4 color : SV_Target0;
    float4 history : SV_Target1;
};

float3 ReconstructNormalizedViewRay(float2 unscaledUv, float viewDepth)
{
    float2 screenPosition = unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
    screenPosition = screenPosition * 2.0 - 1.0;
    float2 viewPlane = cb_vNearFarViewCorner.zw * screenPosition;
    float3 viewPosition = float3(viewPlane * viewDepth, -viewDepth);
    float inverseLength = rsqrt(dot(viewPosition, viewPosition));
    return viewPosition * inverseLength;
}

float3 TransformViewRayToWorld(float3 viewRay)
{
    float3 worldRay = viewToWorld._m01_m11_m21 * viewRay.y;
    worldRay = viewToWorld._m00_m10_m20 * viewRay.x + worldRay;
    worldRay = viewToWorld._m02_m12_m22 * viewRay.z + worldRay;
    float inverseLength = rsqrt(dot(worldRay, worldRay));
    return worldRay * inverseLength;
}

float3 TransformWorldToCascade1(float3 worldPosition)
{
    float3 cascadePosition = cb_arrCascades[1]._m01_m11_m21 * worldPosition.y;
    cascadePosition =
        cb_arrCascades[1]._m00_m10_m20 * worldPosition.x + cascadePosition;
    cascadePosition =
        cb_arrCascades[1]._m02_m12_m22 * worldPosition.z + cascadePosition;
    return cb_arrCascades[1]._m03_m13_m23 + cascadePosition;
}

bool IsInsideCascade(float3 cascadePosition)
{
    bool3 inside = abs(cascadePosition - 0.5) <= 0.5;
    return inside.x && inside.y && inside.z;
}

// Recovered four-gather optimized 7-tap comparison filter. Keeping the
// interpolation order explicit prevents the compiler from reassociating the
// shadow reduction differently from the recovered DXBC.
float FilterCascadeShadow(float3 cascadePosition)
{
    float2 texelPosition =
        cb_vCascadeSize.yx * cascadePosition.yx + float2(0.5, 0.5);
    float2 integerTexel = floor(texelPosition.yx);
    float2 texelFraction = texelPosition - integerTexel.yx;
    float2 shadowUv = cb_vCascadePixelSize.xy * integerTexel;
    float3 sampleLocation = float3(shadowUv, 1.0);

    float4 northWest = cascadeShadowTexture.GatherCmp(
        ShadowSamplerLinear, sampleLocation, cascadePosition.z, int2(-1, -1));
    float2 inverseFraction = 1.0 - texelFraction;
    float halfInverseX = -texelFraction.y * 0.5 + 0.5;
    float2 horizontalWeights =
        texelFraction.y * float2(-0.5, 0.5) + float2(1.0, 0.5);

    float2 northWestPair = horizontalWeights.xx * northWest.zy;
    northWestPair = northWest.wx * halfInverseX + northWestPair;

    float4 northEast = cascadeShadowTexture.GatherCmp(
        ShadowSamplerLinear, sampleLocation, cascadePosition.z, int2(1, -1));
    float2 northEastPair = northEast.zy * texelFraction.y;
    northEastPair = 0.5 * northEastPair;
    northEastPair = northEast.wx * horizontalWeights.yy + northEastPair;

    float upperLeft = northEastPair.x * inverseFraction.x;
    upperLeft = inverseFraction.x * northWestPair.x + upperLeft;
    float lowerLeft = northEastPair.y * texelFraction.x;
    lowerLeft = texelFraction.x * northWestPair.y + lowerLeft;

    float4 southWest = cascadeShadowTexture.GatherCmp(
        ShadowSamplerLinear, sampleLocation, cascadePosition.z, int2(-1, 1));
    float2 southWestPair = southWest.zy * horizontalWeights.xx;
    southWestPair = southWest.wx * halfInverseX + southWestPair;
    upperLeft = inverseFraction.x * southWestPair.x + upperLeft;
    lowerLeft = texelFraction.x * southWestPair.y + lowerLeft;

    float upperCenter = northWest.x * inverseFraction.y + northWest.y;
    float lowerCenter = southWest.w * inverseFraction.y + southWest.z;

    float4 southEast = cascadeShadowTexture.GatherCmp(
        ShadowSamplerLinear, sampleLocation, cascadePosition.z, int2(1, 1));
    float2 southEastPair = southEast.zy * texelFraction.y;
    southEastPair = 0.5 * southEastPair;
    southEastPair = southEast.wx * horizontalWeights.yy + southEastPair;

    float4 filteredRows;
    filteredRows.x = inverseFraction.x * southEastPair.x + upperLeft;
    filteredRows.y = texelFraction.x * southEastPair.y + lowerLeft;
    filteredRows.z = inverseFraction.x * upperCenter
                   + inverseFraction.x * (northEast.y * texelFraction.y + northEast.x);
    filteredRows.w = texelFraction.x * lowerCenter
                   + texelFraction.x * (southEast.z * texelFraction.y + southEast.w);
    return dot(filteredRows, float4(1.0, 1.0, 1.0, 1.0));
}

#if defined(PS_UNDER_WATER)
float SampleWaterCaustics(float3 worldPosition, float lightTravelDistance)
{
    float2 waterUv = cb_vWaterScroll + worldPosition.xy;
    float curvedDistance = 0.25 * lightTravelDistance * lightTravelDistance;
    curvedDistance = min(curvedDistance, lightTravelDistance);
    waterUv = cb_vDirectionalLightToWaterWorld.xy * curvedDistance + waterUv;

    float4 distanceBands =
        float4(0.1, 0.05, 1.0 / 60.0, 0.25) * lightTravelDistance;
    float wholeBand = floor(distanceBands.w);
    float3 bandWindow = float3(-2.0, 1.0, -1.0) + wholeBand;
    bandWindow.xz = saturate(0.01 * bandWindow.xz);
    bandWindow.xz = 1.0 - bandWindow.xz;

    float firstScale = bandWindow.x * wholeBand;
    firstScale = max(0.1, -firstScale * 0.3 + 1.25);
    float secondScale = bandWindow.y * bandWindow.z;
    secondScale = max(0.1, -secondScale * 0.3 + 1.25);

    waterUv /= cb_fWaterMapPatchSize;
    distanceBands.xyz = saturate(distanceBands.xyz);
    distanceBands.xy = 1.0 - distanceBands.xy + float2(0.0, 1.0);
    distanceBands.x += distanceBands.x;

    float2 firstNormal = waterNormalTexture.SampleLevel(
        LinearWrapWrap, waterUv * firstScale, distanceBands.x);
    float2 secondNormal = waterNormalTexture.SampleLevel(
        LinearWrapWrap, waterUv * secondScale, distanceBands.x);
    float bandBlend = (-wholeBand * 4.0 + lightTravelDistance) * 0.25;
    float2 blendedNormal =
        bandBlend * (secondNormal - firstNormal) + firstNormal;
    blendedNormal = blendedNormal * 2.0 - 1.0;

    float causticShape = 1.0 - min(1.0, abs(dot(blendedNormal, 1.0)));
    causticShape = log2(causticShape);
    causticShape = distanceBands.y * causticShape;
    causticShape = distanceBands.z * causticShape;
    causticShape = exp2(20.0 * causticShape);
    float distanceFade = 1.0 - (1.0 - saturate(0.2 * lightTravelDistance));
    return causticShape * distanceFade;
}
#endif

float2 ReprojectToPreviousFrame(float3 worldPosition, out bool valid)
{
    float3 previousClip =
        cb_xPrevWorldToViewProjection._m01_m11_m31 * worldPosition.y;
    previousClip =
        cb_xPrevWorldToViewProjection._m00_m10_m30 * worldPosition.x + previousClip;
    previousClip =
        cb_xPrevWorldToViewProjection._m02_m12_m32 * worldPosition.z + previousClip;
    previousClip = cb_xPrevWorldToViewProjection._m03_m13_m33 + previousClip;
    bool2 inside = abs(previousClip.xy) < previousClip.z;
    valid = inside.x && inside.y;
    float2 previousUv = previousClip.xy / previousClip.z;
    previousUv = previousUv * float2(0.5, -0.5) + 0.5;
    return cb_vPrevRenderScale * previousUv;
}

float3 EncodeHdrColor(float3 color)
{
    float3 encoded = log2(saturate(color));
    encoded = cb_hdr.fPow * encoded;
    encoded = exp2(encoded);
    encoded = encoded - cb_hdr.fBase;
    return saturate(cb_hdr.fRangeRcp * encoded);
}

GodRayPixelOutput mainPS(GodRayPixelInput input)
{
    GodRayPixelOutput output;
    float viewDepth = sceneDepthTexture.SampleLevel(PointClampClamp, input.uv, 0.0);
    float3 viewRay = ReconstructNormalizedViewRay(input.unscaledUv, viewDepth);
    float3 worldRay = TransformViewRayToWorld(viewRay);
    float3 worldPosition = viewToWorld._m03_m13_m23;

#if defined(PS_UNDER_WATER)
    float lightFacing = dot(-cb_vDirectionalLightDirectionView, viewRay);
    lightFacing = lightFacing * 0.5 + 0.5;
    float stepLength = min(8.0, viewDepth) * GOD_RAY_STEP_COUNT_RCP;
    bool waterLightHasHeight =
        1.1920929e-7 < cb_vDirectionalLightToWaterWorld.z;
    float integratedVisibility = 0.0;
    float acceptedSamples = 0.0;
    float rejectedSamples = 0.0;

    [loop]
    for (uint stepIndex = 0; stepIndex < GOD_RAY_STEP_COUNT; ++stepIndex)
    {
        worldPosition = worldRay * stepLength + worldPosition;
        float lightTravelDistance =
            (cb_fWaterSurface - worldPosition.z)
            / cb_vDirectionalLightToWaterWorld.z;
        lightTravelDistance = waterLightHasHeight ? lightTravelDistance : 0.0;
        if (lightTravelDistance > 0.0)
        {
            float contribution =
                SampleWaterCaustics(worldPosition, lightTravelDistance);
            float3 cascadePosition = TransformWorldToCascade1(worldPosition);
            if (IsInsideCascade(cascadePosition))
            {
                contribution *= FilterCascadeShadow(cascadePosition);
                contribution *= SHADOW_FILTER_NORMALIZATION;
            }
            integratedVisibility = contribution + integratedVisibility;
            acceptedSamples = 1.0 + acceptedSamples;
        }
        else
        {
            rejectedSamples = 1.0 + rejectedSamples;
        }
    }

    float denominator = max(10.0, acceptedSamples - rejectedSamples);
    float currentVisibility = integratedVisibility / denominator;
#else
    float lightFacing = dot(-cb_vDirectionalLightDirectionView, viewRay);
    lightFacing = max(0.0, lightFacing);
    lightFacing = 1.0 - lightFacing;
    lightFacing = 1.0 - lightFacing * lightFacing;
    float stepLength = min(16.0, viewDepth) * GOD_RAY_STEP_COUNT_RCP;
    float integratedVisibility = 0.0;
    float zeroVisibilitySamples = 0.0;
    float cascadeSamples = 0.0;

    [loop]
    for (uint stepIndex = 0; stepIndex < GOD_RAY_STEP_COUNT; ++stepIndex)
    {
        worldPosition = worldRay * stepLength + worldPosition;
        float3 cascadePosition = TransformWorldToCascade1(worldPosition);
        if (IsInsideCascade(cascadePosition))
        {
            float filteredShadow = FilterCascadeShadow(cascadePosition);
            bool hasVisibility = filteredShadow > 0.0;
            if (hasVisibility)
            {
                integratedVisibility =
                    filteredShadow * SHADOW_FILTER_NORMALIZATION
                    + integratedVisibility;
            }
            else
            {
                zeroVisibilitySamples = 1.0 + zeroVisibilitySamples;
            }
            cascadeSamples = 1.0 + cascadeSamples;
        }
    }

    float denominator = max(10.0, cascadeSamples - zeroVisibilitySamples * 0.5);
    float averageVisibility = integratedVisibility / denominator;
    float zeroVisibilityFraction = zeroVisibilitySamples / cascadeSamples;
    zeroVisibilityFraction = cascadeSamples != 0.0 ? zeroVisibilityFraction : 0.0;
    float distanceFade = saturate(0.125 * viewDepth);
    distanceFade = 1.0 - distanceFade;
    distanceFade = 1.0 - distanceFade * distanceFade;
    zeroVisibilityFraction = max(cb_fTodFactor, zeroVisibilityFraction);
    distanceFade = zeroVisibilityFraction * distanceFade;
    float currentVisibility = averageVisibility * distanceFade;
#endif

    bool historyValid;
    float2 previousUv = ReprojectToPreviousFrame(worldPosition, historyValid);
    float previousVisibility = 0.0;
    float historyWeight = 0.0;
    if (historyValid)
    {
        previousVisibility =
            temporalTexture.SampleLevel(LinearClampClamp, previousUv, 0.0);
        float volatility =
            volatilityTexture.SampleLevel(LinearClampClamp, input.unscaledUv, 0.0);
        historyWeight = 1.0 - abs(volatility);
    }

#if defined(PS_UNDER_WATER)
    historyWeight *= 0.5;
#else
    historyWeight *= 0.8;
#endif
    float historyDelta = previousVisibility - currentVisibility;
    float resolvedVisibility = historyWeight * historyDelta + currentVisibility;

#if defined(PS_UNDER_WATER)
    lightFacing = max(0.5, lightFacing);
    lightFacing = cb_fGodRaysIntensity * lightFacing;
    lightFacing = cb_fGodRaysCloudCover * lightFacing;
    lightFacing = resolvedVisibility * lightFacing;
    float3 godRayColor = EncodeHdrColor(cb_vDirectionalLightColor);
    godRayColor *= max(0.5, cb_fDirectionalLightIntensity);
#else
    lightFacing = cb_fGodRaysCloudCover * lightFacing;
    lightFacing = resolvedVisibility * lightFacing;
    float3 godRayColor = EncodeHdrColor(cb_vGodRaysColor);
#endif

    output.color = float4(godRayColor * lightFacing, 1.0);
    output.history = float4(resolvedVisibility.xxx, 1.0);
    return output;
}
