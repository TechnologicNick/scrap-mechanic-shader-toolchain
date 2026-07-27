SamplerState PointClampClamp : register(s1);
Texture2D<float4> inputDepth : register(t0);

float mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Depth
{
    return inputDepth.Sample(PointClampClamp, uv).x;
}
