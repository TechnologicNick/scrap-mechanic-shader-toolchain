float4 mainPS_Untextured(
    float4 position : SV_Position0, float4 color : TEXCOORD0
) : SV_Target0
{
    return color;
}
