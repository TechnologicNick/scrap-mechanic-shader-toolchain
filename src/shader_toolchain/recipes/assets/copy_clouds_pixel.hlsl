#include "include/post_fxaa_abi.hlsl"

SamplerState LinearClampClamp : register(s6);
Texture2D<float4> inputClouds : register(t0);
Texture2D<float> screenNoise : register(t1);

float4 SampleClouds(float2 uv)
{
    return inputClouds.SampleLevel(
        LinearClampClamp, min(cb_vUvLimitMipDown, uv), 0.0
    );
}

float4 mainPS(
    float4 position : SV_Position0,
    float2 uv : UV0,
    float2 unscaledUv : UNSCALED_UV0
) : SV_Target0
{
    float2 pixel = cb_vContainerPixelSize;
    float2 corner = 0.75 * pixel;

    float4 sum = SampleClouds(uv - corner);
    float4 northEast = SampleClouds(uv + float2(corner.x, -corner.y));
    float4 southEast = SampleClouds(uv + corner);
    sum = 2.0 * sum + 2.0 * northEast;
    sum = 2.0 * SampleClouds(uv + float2(-corner.x, corner.y)) + sum;
    sum = 2.0 * southEast + sum;
    sum = SampleClouds(uv + float2(0.0, 1.5 * pixel.y)) + sum;
    sum = SampleClouds(uv + float2(0.0, -1.5 * pixel.y)) + sum;
    sum = sum + SampleClouds(uv + float2(-1.5 * pixel.x, 0.0));
    sum = SampleClouds(uv + float2(1.5 * pixel.x, 0.0)) + sum;

    float4 average = 0.0833333358 * sum;
    float outputAlpha = sum.a < 9.0
        ? 0.75 * (average.a * average.a)
        : average.a;

    uint2 noisePixel = ((uint2)(uv * cb_vuViewportSize)) & 63;
    float noise = screenNoise.Load(uint3(noisePixel, 0));
    noise = noise * 0.00499999989 - 0.00249999994;
    noise *= cb_vRenderScale.x * cb_vRenderScale.x;
    return float4(average.rgb + noise * average.a, outputAlpha);
}
