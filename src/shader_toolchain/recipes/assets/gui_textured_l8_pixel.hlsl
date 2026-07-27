SamplerState guiSampler : register(s3);
Texture2D<float4> guiTexture : register(t0);

float4 mainPS_TexturedL8(
    float4 position : SV_Position0,
    float4 color : TEXCOORD0,
    float2 uv : TEXCOORD1
) : SV_Target0
{
    float luminance = guiTexture.SampleLevel(guiSampler, uv, 0.0).r;
    return color * float4(1.0, 1.0, 1.0, luminance);
}
