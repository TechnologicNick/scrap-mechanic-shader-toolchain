void mainVS_Untextured(
    float3 position : POSITION0,
    float4 color : COLOR0,
    out float4 clipPosition : SV_Position0,
    out float4 outputColor : TEXCOORD0
)
{
    clipPosition = float4(position, 1.0);
    outputColor = color;
}
