#include "include/post_fxaa_abi.hlsl"
#include "include/perframe_abi.hlsl"

SamplerState LinearWrapClamp_s : register(s4);
Texture2D<float3> tColorMap : register(t0);
#ifdef SKY_DITHER
Texture2D<float> tScreenNoise : register(t1);
#endif

float ApproximateAcos(float value)
{
    float magnitude = abs(value);
    float polynomial = magnitude * -0.0187292993 + 0.0742610022;
    polynomial = polynomial * magnitude - 0.212114394;
    polynomial = polynomial * magnitude + 1.57072878;
    float result = polynomial * sqrt(1.0 - magnitude);
    return value < 0.0 ? 3.14159274 - result : result;
}

float SmoothUnit(float value)
{
    return value * value * (3.0 - 2.0 * value);
}

float4 mainPS(
    float4 position : SV_Position,
    float2 uv : UV0,
    float2 unscaledUv : UNSCALED_UV0
) : SV_Target0
{
    float2 ndc = (unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0))
        * 2.0 - 1.0;
    float3 viewDirection = normalize(float3(
        cb_vNearFarViewCorner.zw * ndc,
        -1.0
    ));
    float3 worldDirection = mul(viewDirection, (float3x3)viewToWorld);
    float sunAlignment = saturate(dot(
        -cb_vDirectionalLightDirectionView, viewDirection
    ));
    float elevation = worldDirection.z * rsqrt(dot(worldDirection, worldDirection));
    float angleFromZenith = min(
        1.0, ApproximateAcos(elevation) * 0.636619747
    );
    float horizonCoordinate = 1.0 - angleFromZenith;
    bool rayBelowWater = elevation * 500.0 + viewToWorld._m23
        + cb_fWaterSurface < 0.0;
    float horizonFogWeight = cb_fogs[0].cb_vHorizonFog.a;
    horizonFogWeight *= angleFromZenith * angleFromZenith;
    horizonFogWeight *= angleFromZenith * angleFromZenith;

    float dither = 0.0;
#ifdef SKY_DITHER
    uint2 noiseCoordinate = uint2(uv * float2(cb_vuViewportSize)) & 63;
    dither = tScreenNoise.Load(uint3(noiseCoordinate, 0)).r
        * 0.0500000007 - 0.0250000004;
    dither *= cb_vRenderScale.x * cb_vRenderScale.x;
#endif

    float3 skyMap = tColorMap.SampleLevel(
        LinearWrapClamp_s,
        float2(cb_fTimeOfDay, horizonCoordinate + dither),
        0.0
    );
    float3 sky = skyMap * cb_fDirectionalLightMapMul;
    sky += horizonFogWeight * (
        cb_fogs[0].cb_vHorizonFog.rgb
        - skyMap * cb_fDirectionalLightMapMul
    );

    float directionalLuminance = dot(
        cb_vDirectionalLightColor, float3(0.299, 0.587, 0.114)
    );
    float directionalScale = (1.0 - directionalLuminance) * 2.70000005 + 1.0;
    float3 sunColor = saturate(
        cb_vDirectionalLightColor * directionalScale + dither
    );

    float3 thresholds = cb_fTodFactor
        * float3(-0.0144999623, 0.000999987125, 0.0999999642)
        + float3(0.994499981, 0.995999992, 0.600000024);
    float broadSun = saturate(
        (sunAlignment - thresholds.x) / (thresholds.y - thresholds.x)
    );
    float sharpSun = saturate(
        (sunAlignment - thresholds.z) / (1.0 - thresholds.z)
    );
    sharpSun = SmoothUnit(sharpSun) * 0.699999988;
    sharpSun *= sharpSun;
    sharpSun *= sharpSun;
    float broadCurve = SmoothUnit(broadSun);
    float combinedCurve = broadCurve + sharpSun;
    float3 sunlight = sunColor * broadCurve
        + sunColor * sharpSun;
    float3 skyAndSun = sunlight + sky;
    float3 composed = skyAndSun + combinedCurve * (sunlight - skyAndSun);

    bool cameraBelowWater = viewToWorld._m23 < cb_fWaterSurface;
    float3 finalColor = rayBelowWater && cameraBelowWater
        ? cb_fogs[1].cb_vHorizonFog.rgb
        : composed;
    return float4(finalColor, 1.0);
}
