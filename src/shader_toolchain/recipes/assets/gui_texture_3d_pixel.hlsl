SamplerState guiSampler : register(s3);
Texture3D<float4> guiVolume : register(t0);

float4 mainPS(
    float4 position : SV_Position0,
    float4 tint : TEXCOORD0,
    float2 textureCoordinates : TEXCOORD1
) : SV_Target0
{
    float4 sampled = guiVolume.Sample(
        guiSampler, float3(textureCoordinates, 0.0)
    );
    return tint * sampled;
}
