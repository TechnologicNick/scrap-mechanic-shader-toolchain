cbuffer CB_PARAMS : register(b0)
{
    struct
    {
        float time;
        float _padding0;
        float _padding1;
        float _padding2;
        float4 color;
    } parameters : packoffset(c0);
}

SamplerState LinearClampClamp : register(s6);
Texture2D<float4> inputTexture : register(t0);

float4 mainPS(
    float4 position : SV_Position0, float2 unscaledUv : UNSCALED_UV0
) : SV_Target0
{
    float pulse = sin(4.0 * parameters.time);
    pulse = pulse * 0.5 + 0.5;
    pulse = pulse * 0.699999988 + 0.300000012;

    float2 sampleUv = unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
    float4 tinted = parameters.color
        * inputTexture.Sample(LinearClampClamp, sampleUv);
    return float4(tinted.rgb, tinted.a * pulse);
}
