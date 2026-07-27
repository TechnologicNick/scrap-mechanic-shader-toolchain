cbuffer CB_COLOR : register(b0)
{
    float4 silhouetteColor;
}

SamplerState guiSampler : register(s3);
Texture2D<float4> guiTexture : register(t0);

float4 mainPS(
    float4 position : SV_Position0,
    float2 textureCoordinates : TEXCOORD0,
    float4 vertexColor : TEXCOORD1
) : SV_Target0
{
    float4 sampled = guiTexture.SampleLevel(guiSampler, textureCoordinates, 0.0);
    float4 colorDelta = float4(silhouetteColor.rgb - sampled.rgb, 0.0);
    return silhouetteColor.a * colorDelta + sampled;
}
