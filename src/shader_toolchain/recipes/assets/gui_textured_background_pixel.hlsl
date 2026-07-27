cbuffer CB_TEXTURE_DATA : register(b0)
{
    float4 backgroundColor;
    float arrayIndex;
}

SamplerState guiSampler : register(s3);
Texture2D<float4> guiTexture : register(t0);

float4 mainPS_TexturedBackground(
    float4 position : SV_Position0,
    float4 color : TEXCOORD0,
    float2 uv : TEXCOORD1
) : SV_Target0
{
    float4 sampled = guiTexture.SampleLevel(guiSampler, uv, 0.0);
    float uncovered = 1.0 - sampled.a;
    float4 filled = backgroundColor * uncovered + sampled;
    return color * filled;
}
