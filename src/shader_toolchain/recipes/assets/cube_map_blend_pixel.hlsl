cbuffer CB_PARAMS : register(b0)
{
    struct
    {
        float fBlend;
        float3 _padding;
    } cb_param : packoffset(c0);
}

SamplerState PointWrapWrap_s : register(s0);
TextureCubeArray<float3> tA : register(t0);
TextureCubeArray<float3> tB : register(t1);

struct CubeFaces
{
    float3 positiveX : SV_Target0;
    float3 negativeX : SV_Target1;
    float3 positiveY : SV_Target2;
    float3 negativeY : SV_Target3;
    float3 positiveZ : SV_Target4;
    float3 negativeZ : SV_Target5;
};

float3 BlendDirection(float3 direction)
{
    float4 location = float4(direction, 0.0);
    float3 previous = tA.SampleLevel(PointWrapWrap_s, location, 0.0);
    float3 current = tB.SampleLevel(PointWrapWrap_s, location, 0.0);
    return previous + cb_param.fBlend * (current - previous);
}

CubeFaces mainPS(float4 position : SV_Position, float2 uv : UV0)
{
    float2 positive = uv * 2.0 - 1.0;
    float2 negative = 1.0 - uv * 2.0;

    CubeFaces output;
    output.positiveX = BlendDirection(float3(1.0, negative.y, negative.x));
    output.negativeX = BlendDirection(float3(-1.0, negative.y, positive.x));
    output.positiveY = BlendDirection(float3(positive.x, 1.0, positive.y));
    output.negativeY = BlendDirection(float3(positive.x, -1.0, negative.y));
    output.positiveZ = BlendDirection(float3(positive.x, negative.y, 1.0));
    output.negativeZ = BlendDirection(float3(negative.x, negative.y, -1.0));
    return output;
}
