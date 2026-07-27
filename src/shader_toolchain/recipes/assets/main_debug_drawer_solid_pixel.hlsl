float4 mainPS(
    float4 position : SV_Position0,
    float4 viewPosition : VIEW_POSITION0,
    float3 screenUv : SCREEN_UV0,
    nointerpolation float4 color : TEXCOORD0
) : SV_Target0
{
    return color;
}
