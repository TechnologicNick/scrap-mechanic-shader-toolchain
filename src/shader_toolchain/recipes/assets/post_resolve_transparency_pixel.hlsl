SamplerState PointClampClamp : register(s1);
Texture2D<float3> accumulatedColor : register(t0);
Texture2D<float2> accumulatedAlphaWeight : register(t1);

float4 mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    float3 color = accumulatedColor.SampleLevel(PointClampClamp, uv, 0.0);
    float2 alphaWeight = accumulatedAlphaWeight.SampleLevel(
        PointClampClamp, uv, 0.0
    );
    float4 accumulation = float4(color, alphaWeight.x);
    accumulation = alphaWeight.y != 0.0
        ? accumulation / alphaWeight.y
        : accumulation;
    return saturate(float4(accumulation.rgb * accumulation.a, accumulation.a));
}
