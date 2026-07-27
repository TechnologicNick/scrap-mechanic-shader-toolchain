cbuffer CB_VIEWPORT : register(b0)
{
    float4 backgroundColor;
    float arrayIndex;
}

SamplerState guiSampler : register(s3);
Texture2DArray<float4> guiTextures : register(t0);

float4 mainPS(
    float4 position : SV_Position0,
    float4 tint : TEXCOORD0,
    float2 textureCoordinates : TEXCOORD1
) : SV_Target0
{
    float4 sampled = guiTextures.Sample(
        guiSampler, float3(textureCoordinates, arrayIndex)
    );
    float uncovered = 1.0 - sampled.a;
    float4 filled = backgroundColor * uncovered + sampled;
    return tint * filled;
}
