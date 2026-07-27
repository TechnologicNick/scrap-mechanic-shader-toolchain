#include "include/post_clouds_projection_abi.hlsl"
#include "include/post_clouds_perframe_abi.hlsl"

SamplerState LinearWrapWrap : register(s3);
SamplerState LinearWrapClamp : register(s4);
#if defined(PS_TEMPORAL)
SamplerState LinearClampClamp : register(s6);
#endif

Texture2D<float3> skyColorMap : register(t0);
Texture2D<float3> cloudLightColorMap : register(t1);
Texture3D<float> cloudVolume : register(t2);
Texture2D<float> weatherMap : register(t3);
#if defined(PS_TEMPORAL)
Texture2D<float> screenNoise : register(t4);
Texture2D<float2> cloudHistory : register(t5);
Texture2D<float> sceneDepth : register(t7);
#endif

static const float WEATHER_SCALE = 9.2307695e-5;
static const float VOLUME_SCALE = 5.39999979e-4;

struct CloudPixelInput
{
    float4 position : SV_Position0;
    float2 uv : UNSCALED_UV0;
};

struct CloudPixelOutput
{
    float4 color : SV_Target0;
    float2 history : SV_Target1;
};

float3 ReconstructViewRay(float2 uv)
{
    float2 clip = uv * float2(1.0, -1.0) + float2(0.0, 1.0);
    clip = clip * 2.0 - 1.0;
    float3 ray = float3(cb_vNearFarViewCorner.zw * clip, -1.0);
    return ray * rsqrt(dot(ray, ray));
}

float3 ViewRayToWorld(float3 viewRay)
{
    float3 ray = viewToWorld._m01_m11_m21 * viewRay.y;
    ray = viewToWorld._m00_m10_m20 * viewRay.x + ray;
    ray = viewToWorld._m02_m12_m22 * viewRay.z + ray;
    return ray * rsqrt(dot(ray, ray));
}

float ApproximatePolarAngle(float z)
{
    float root = sqrt(1.0 - abs(z));
    float polynomial = abs(z) * -0.0187292993 + 0.0742610022;
    polynomial = polynomial * abs(z) - 0.212114394;
    polynomial = polynomial * abs(z) + 1.57072878;
    float halfAngle = polynomial * root;
    float oppositeHalf = halfAngle * -2.0 + 3.14159274;
    return halfAngle + (z < -z ? oppositeHalf : 0.0);
}

float SmoothCurve(float value)
{
    return value * value * (3.0 - 2.0 * value);
}

struct SkyState
{
    float3 color;
    float distanceBlend;
    float lightAngle;
};

SkyState EvaluateSky(float3 viewRay, float3 worldRay)
{
    SkyState sky;
    float polarAngle = ApproximatePolarAngle(worldRay.z);
    float sunFacing = saturate(dot(-cb_vDirectionalLightDirectionView, viewRay));
    float3 thresholds = cb_fTodFactor
        * float3(-0.0144999623, 0.000999987125, 0.0999999642)
        + float3(0.994499981, 0.995999992, 0.600000024);
    float broadSun = SmoothCurve(saturate(
        (sunFacing - thresholds.x) / (thresholds.y - thresholds.x)));
    float narrowSun = SmoothCurve(saturate(
        (sunFacing - thresholds.z) / (1.0 - thresholds.z)));
    narrowSun *= 0.699999988;
    narrowSun = narrowSun * narrowSun;
    narrowSun = narrowSun * narrowSun;

    float luminance = dot(cb_vDirectionalLightColor,
        float3(0.298999995, 0.587000012, 0.114));
    float3 correctedLight = saturate(cb_vDirectionalLightColor
        * ((1.0 - luminance) * 2.70000005 + 1.0));
    float3 sunColor = correctedLight * narrowSun;
    sunColor = correctedLight * broadSun + sunColor;

    sky.lightAngle = min(1.0, 0.636619747 * polarAngle);
    float3 horizonSample = skyColorMap.SampleLevel(
        LinearWrapClamp, float2(cb_fTimeOfDay, 1.0 - sky.lightAngle), 0.0);
    float3 horizonColor = cb_fDirectionalLightMapMul * horizonSample;
    float horizonBlend = 1.0 - (1.0 - sky.lightAngle);
    horizonBlend *= horizonBlend;
    horizonBlend *= horizonBlend;
    horizonBlend *= cb_fogs[0].cb_vHorizonFog.w;
    horizonColor += horizonBlend
        * (cb_fogs[0].cb_vHorizonFog.xyz - horizonColor);

    bool belowWaterFog = viewToWorld._m23 < cb_fWaterSurface
        && cb_fWaterSurface + worldRay.z * 500.0 + viewToWorld._m23 < 0.0;
    horizonColor += sunColor;
    float skySunBlend = SmoothCurve(saturate(
        (sunFacing - thresholds.x) / (thresholds.y - thresholds.x))) + narrowSun;
    sky.color = horizonColor + skySunBlend * (sunColor - horizonColor);
    if (belowWaterFog)
        sky.color = cb_fogs[1].cb_vHorizonFog.xyz;

    float farHeight = worldRay.z * 6000.0 + viewToWorld._m23;
    float fadeBase = 1.0 - saturate((farHeight - 10.0) * 0.000199999995);
    float fadePower = saturate(viewToWorld._m23 * 0.100000001) * 10.0 + 8.0;
    sky.distanceBlend = exp2(log2(fadeBase) * fadePower);
    return sky;
}

float CloudBoundary(float weather, float heightFraction)
{
    float envelope = 1.0 - heightFraction * weather * 1.5;
    envelope = 1.16999996 - exp2(log2(abs(envelope)) * 1.20000005);
    envelope = max(0.00999999978, envelope);
    float occupancy = min(1.0,
        (weather - cb_clouds.fCloudCoveragesInv) / envelope);
    return 1.0 - occupancy;
}

float SampleDensity(float3 worldPosition, float3 volumePosition,
                    float shellBaseZ, bool useDetail)
{
    float weather = weatherMap.SampleLevel(
        LinearWrapWrap, worldPosition.xy * WEATHER_SCALE, 0.0);
    if (weather < cb_clouds.fCloudCoveragesInv)
        return -1.0;
    float baseNoise = cloudVolume.SampleLevel(
        LinearWrapWrap, volumePosition * VOLUME_SCALE, 0.0);
    float heightFraction = cb_clouds.fMaxHeightRcp
        * (worldPosition.z - shellBaseZ);
    float boundary = CloudBoundary(weather, heightFraction);
    if (useDetail)
    {
        float3 detailPosition = (volumePosition
            + cb_clouds.vScroll * 0.449999988) * 0.00647999998;
        float detail = cloudVolume.SampleLevel(
            LinearWrapWrap, detailPosition, 0.0);
        baseNoise -= weather * weather * detail * 0.100000001;
    }
    if (baseNoise < boundary)
        return -1.0;
    return boundary + baseNoise * (1.0 - boundary);
}

float SampleLightDensity(float3 worldPosition, float3 volumePosition,
                         float shellBaseZ, float distance, bool highQuality)
{
    float3 lightWorld = worldPosition
        - cb_vDirectionalLightDirectionWorld * distance;
    float weather = weatherMap.SampleLevel(
        LinearWrapWrap, lightWorld.xy * WEATHER_SCALE, 0.0);
    if (weather < cb_clouds.fCloudCoveragesInv)
        return -1.0;
    float3 lightVolume = volumePosition + cb_clouds.vInvLightDir * distance;
    float noise = cloudVolume.SampleLevel(
        LinearWrapWrap, lightVolume * VOLUME_SCALE, 0.0);
    if (highQuality)
        noise -= 0.0250000004;
    float heightFraction = cb_clouds.fMaxHeightRcp
        * (lightWorld.z - shellBaseZ);
    float boundary = CloudBoundary(weather, heightFraction);
    if (noise < boundary)
        return -1.0;
    return boundary + noise * (1.0 - boundary);
}

float ShellEntryDistance(float3 worldRay)
{
    float projected = cb_clouds.fPlanetCameraDistanceZ * worldRay.z;
    float root = sqrt(max(0.0, projected * projected - cb_clouds.fC));
    return max(-projected + root, -projected - root);
}

float3 RotateIntoCloudVolume(float3 worldRay)
{
    float3 rotated = cb_clouds.xInvRotation._m01_m11_m21 * worldRay.y;
    rotated = cb_clouds.xInvRotation._m00_m10_m20 * worldRay.x + rotated;
    return cb_clouds.xInvRotation._m02_m12_m22 * worldRay.z + rotated;
}

float3 ShadeCloud(float3 skyColor, float3 worldRay, float accumulatedDensity,
                  float marchDistance, float lightAngle, float timeOffset,
                  out float cloudResponse)
{
    cloudResponse = 1.21000004
        - exp2(-1.44269502 * accumulatedDensity / 8.0);
    float lightFacing = dot(worldRay, -cb_vDirectionalLightDirectionWorld);
    float forwardLobe = max(0.00999999978,
        (lightFacing * -0.449999988 + 0.550000012) * cloudResponse * 4.0);
    forwardLobe *= forwardLobe;
    forwardLobe *= forwardLobe;
    forwardLobe = min(0.150000006, forwardLobe * 0.25);
    cloudResponse += forwardLobe;

    float paletteY = max(0.275999993, cb_clouds.fCloudCoveragesInv);
    paletteY = paletteY * 0.5 + 0.5 - cloudResponse * 0.5;
    float3 palette = cloudLightColorMap.SampleLevel(LinearWrapClamp,
        float2(cb_fTimeOfDay + timeOffset - 0.0125000002, paletteY), 0.0);
    float distanceFade = exp2(-1.44269502
        * saturate(marchDistance * 5.55555562e-5));
    palette = skyColor + distanceFade * (palette - skyColor);

    float daylight = (1.0 - cb_fTodFactor * cb_fTodFactor) * 1.5 + 1.0;
    float3 directionalColor = saturate(cb_vDirectionalLightColor * daylight);
    float angleLimit = cb_fTodFactor * lightAngle;
    angleLimit = lightAngle - angleLimit * 0.5;
    float angular = max(0.00100000005,
        lightFacing * 0.5 + 0.5);
    angular = min(angleLimit,
        exp2(log2(angular) * (cb_fTodFactor * 70.0 + 10.0)));
    angular = max(0.0, angular);
    float coverageBias = cb_clouds.fCloudCoveragesInv
        * (0.300000012 - cb_fTodFactor * 0.100000009);
    float opacity = max(0.100000001,
        1.0 + coverageBias - cloudResponse);
    opacity = exp2(log2(opacity) * 1.5);
    opacity = min(1.0, angular * opacity);
    return palette + directionalColor * opacity;
}

#if defined(PS_TEMPORAL)
bool HasVisibleCloudPixel(float2 uv)
{
    uint2 maxPixel = cb_clouds.vuDepthSize;
    int2 center = int2(uv * float2(maxPixel));
    static const int2 offsets[9] = {
        int2(-4,-4), int2(0,-4), int2(4,-4), int2(-4,0), int2(0,0),
        int2(4,0), int2(-4,4), int2(0,4), int2(4,4)
    };
    [unroll]
    for (uint index = 0; index < 9; ++index)
    {
        uint2 pixel = min(maxPixel, (uint2)(center + offsets[index]));
        float deviceDepth = sceneDepth.Load(int3(pixel, 0));
        float viewDepth = cb_xViewToProjection._m23
            / (cb_xViewToProjection._m22 + deviceDepth);
        if (viewDepth >= cb_clouds.fDepthCheckDistance)
            return true;
    }
    return false;
}
#endif

CloudPixelOutput mainPS(CloudPixelInput input)
{
    CloudPixelOutput output;
#if defined(PS_TEMPORAL)
    if (!HasVisibleCloudPixel(input.uv))
    {
        output.color = 0.0;
        output.history = 0.0;
        return output;
    }
#endif
    float3 viewRay = ReconstructViewRay(input.uv);
    float3 worldRay = ViewRayToWorld(viewRay);
    SkyState sky = EvaluateSky(viewRay, worldRay);
    if (sky.distanceBlend >= 1.0)
    {
        output.color = float4(sky.color, 1.0);
        output.history = 0.0;
        return output;
    }

    float shellEntry = ShellEntryDistance(worldRay);
#if defined(PS_TEMPORAL)
    uint2 noisePixel = (uint2)(input.uv * float2(cb_vuViewportSize)) & 63;
    float noise = screenNoise.Load(int3(noisePixel, 0));
    float jitter = frac(cb_clouds.fNoiseProgress + noise);
    float marchStart = shellEntry
        + cb_clouds.fStep * (jitter * min(1.0, ApproximatePolarAngle(worldRay.z)))
        * 0.949999988;
    float marchEnd = marchStart + cb_clouds.fStep * 20.0;
#else
    float noise = 0.0;
    float marchStart = shellEntry;
    float marchEnd = marchStart + cb_clouds.fStep * 10.0;
#endif
    float3 rotatedRay = RotateIntoCloudVolume(worldRay);
    float3 volumeOrigin = cb_clouds.xInvRotation._m02_m12_m22
        * cb_clouds.fPlanetCameraDistanceZ + cb_clouds.vScroll;
    float shellBaseZ = worldRay.z * marchStart + cb_clouds.vScroll.z;
    float accumulatedDensity = 0.0;
    float3 occupiedVolumePosition = rotatedRay * marchEnd + volumeOrigin;
    float occupiedDistance = marchStart;
    bool occupied = false;

    [loop]
    for (float distance = marchStart; distance < marchEnd;
         distance += cb_clouds.fStep)
    {
        float3 worldPosition = worldRay * distance + cb_clouds.vScroll;
        float3 volumePosition = rotatedRay * distance + volumeOrigin;
        float density = SampleDensity(worldPosition, volumePosition,
            shellBaseZ, 
#if defined(PS_TEMPORAL)
            true
#else
            false
#endif
        );
        if (density < 0.0)
            continue;
        accumulatedDensity += density;
#if defined(PS_TEMPORAL)
        float firstLightDistance = noise * worldRay.z * 53.3333321;
        [unroll]
        for (uint lightStep = 0; lightStep < 8; ++lightStep)
        {
            float lightDistance = firstLightDistance + 20.0 * lightStep;
            float lightDensity = SampleLightDensity(worldPosition,
                volumePosition, shellBaseZ, lightDistance, true);
            if (lightDensity >= 0.0)
                accumulatedDensity += lightDensity;
        }
#else
        [unroll]
        for (uint lightStep = 1; lightStep < 8; ++lightStep)
        {
            float lightDensity = SampleLightDensity(worldPosition,
                volumePosition, shellBaseZ, 16.0 * lightStep, false);
            if (lightDensity >= 0.0)
                accumulatedDensity += lightDensity;
        }
#endif
        occupiedVolumePosition = volumePosition;
        occupiedDistance = distance;
        occupied = true;
        break;
    }

    float cloudResponse;
    float3 cloudColor = ShadeCloud(sky.color, worldRay, accumulatedDensity,
        occupiedDistance, sky.lightAngle,
#if defined(PS_TEMPORAL)
        noise * 0.0250000004,
#else
        0.0,
#endif
        cloudResponse);
    float historyAlpha = occupied ? 1.0 : 0.0;
#if defined(PS_TEMPORAL)
    float3 previousLocal = occupiedVolumePosition - cb_clouds.vPrevScroll;
    float3 previousWorld = cb_clouds.xPrevRotation._m01_m11_m21 * previousLocal.y;
    previousWorld = cb_clouds.xPrevRotation._m00_m10_m20
        * previousLocal.x + previousWorld;
    previousWorld = cb_clouds.xPrevRotation._m02_m12_m22
        * previousLocal.z + previousWorld + cb_clouds.vPrevPlanetCenter;
    float3 previousClip = cb_xPrevWorldToViewProjection._m01_m11_m31
        * previousWorld.y;
    previousClip = cb_xPrevWorldToViewProjection._m00_m10_m30
        * previousWorld.x + previousClip;
    previousClip = cb_xPrevWorldToViewProjection._m02_m12_m32
        * previousWorld.z + previousClip;
    previousClip += cb_xPrevWorldToViewProjection._m03_m13_m33;
    if (all(abs(previousClip.xy) < previousClip.zz))
    {
        float2 historyUv = previousClip.xy / previousClip.z;
        historyUv = historyUv * float2(0.5, -0.5) + 0.5;
        historyUv = min(cb_vPrevUvLimit, cb_vPrevRenderScale * historyUv);
        bool4 validGather = cloudHistory.Gather(LinearClampClamp, historyUv) != 0.0;
        if (validGather.z && validGather.w && validGather.x && validGather.y)
        {
            float2 previous = cloudHistory.SampleLevel(
                LinearClampClamp, historyUv, 0.0);
            cloudResponse += (previous.x - cloudResponse)
                * (occupied ? 0.939999998 : 1.0);
            float responseRate = max(0.00392156886, 4.0 * cb_fAvgDeltaTime);
            historyAlpha = previous.y + (occupied ? responseRate : -responseRate);
        }
    }
#endif
    output.color.xyz = cloudColor + sky.distanceBlend * (sky.color - cloudColor);
    output.color.w = historyAlpha;
    output.history = float2(cloudResponse,
#if defined(PS_TEMPORAL)
        max(0.00392156886, historyAlpha)
#else
        occupied ? 1.0 : 0.00392156886
#endif
    );
    return output;
}
