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
    float sine;
    float cosine;
    sincos(5.0 * parameters.time, sine, cosine);
    float2 centered = unscaledUv.yx - 0.5;
    float2 rotated;
    rotated.x = centered.y * cosine - centered.x * sine;
    rotated.y = centered.x * cosine + centered.y * sine;
    float2 sampleUv = rotated + 0.5;
    return parameters.color * inputTexture.Sample(LinearClampClamp, sampleUv);
}
