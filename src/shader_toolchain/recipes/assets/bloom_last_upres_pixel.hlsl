#include "include/hdr_abi.hlsl"

SamplerState PointClampClamp : register(s1);
SamplerState LinearClampClamp : register(s6);
Texture2D<float3> bloomTexture : register(t0);
Texture2D<float3> frameTexture : register(t1);

float3 mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    float3 frame = saturate(
        frameTexture.SampleLevel(PointClampClamp, uv, 0.0)
    );
    frame = exp2(hdr.exponent * log2(frame));
    frame = saturate(hdr.inverseRange * (frame - hdr.baseValue));
    frame = exp2(2.20000005 * log2(frame));

    float3 bloom = bloomTexture.SampleLevel(LinearClampClamp, uv, 0.0);
    float3 combined = 0.200000003 * bloom + frame;
    return exp2(0.454545468 * log2(abs(combined)));
}
