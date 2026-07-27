cbuffer CB_SCALE : register(b0)
{
    float2 scale : packoffset(c0);
    float2 pixelSize : packoffset(c0.z);
    float2 resolution : packoffset(c1);
    float2 _padding : packoffset(c1.z);
}

SamplerState LinearClampClamp : register(s6);
Texture2D<float4> inputClouds : register(t0);

float4 mainPS(
    float4 position : SV_Position0,
    float2 uv : UV0,
    float2 unscaledUv : UNSCALED_UV0
) : SV_Target0
{
    float2 sampleUv = unscaledUv * scale + 0.25 * pixelSize;
    sampleUv = min(sampleUv, scale - pixelSize);
    return inputClouds.SampleLevel(LinearClampClamp, sampleUv, 0.0);
}
