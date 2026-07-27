SamplerState LinearClampClamp : register(s6);
Texture2D<float4> inputColor : register(t0);

float3 mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    return inputColor.SampleLevel(LinearClampClamp, uv, 0.0).rgb;
}
