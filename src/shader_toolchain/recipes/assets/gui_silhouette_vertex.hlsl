void mainVS(
    float3 position : POSITION0,
    float4 color : COLOR0,
    float2 textureCoordinates : TEXCOORD0,
    out float4 clipPosition : SV_Position0,
    out float2 outputTextureCoordinates : TEXCOORD0,
    out float4 outputColor : TEXCOORD1
)
{
    clipPosition = float4(position, 1.0);
    outputTextureCoordinates = textureCoordinates;
    outputColor = color;
}
