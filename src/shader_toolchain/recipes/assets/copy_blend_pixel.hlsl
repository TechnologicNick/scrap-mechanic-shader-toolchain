cbuffer CB_PARAMS : register(b0)
{
    struct
    {
        float blendFactor;
        float3 _padding;
    } parameters : packoffset(c0);
}

SamplerState PointClampClamp : register(s1);
Texture2D<float4> firstInput : register(t0);
Texture2D<float4> secondInput : register(t1);

float4 mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    float4 second = secondInput.SampleLevel(PointClampClamp, uv, 0.0);
    float4 first = firstInput.SampleLevel(PointClampClamp, uv, 0.0);
    return parameters.blendFactor * (second - first) + first;
}
