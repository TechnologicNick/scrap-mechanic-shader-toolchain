SamplerState PointClampClamp : register(s1);
Texture2D<float> shadowCache : register(t0);

float mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Depth
{
    return shadowCache.Sample(PointClampClamp, uv);
}
