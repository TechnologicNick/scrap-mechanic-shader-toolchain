cbuffer CB_VIEWPORT : register(b0)
{
    float4 viewportMixFactor;
}

SamplerState guiSampler : register(s3);
Texture2D<float4> foregroundTexture : register(t0);
Texture2D<float4> blurredBackgroundTexture : register(t1);

float4 mainPS(
    float4 position : SV_Position0,
    float4 tint : TEXCOORD0,
    float2 textureCoordinates : TEXCOORD1
) : SV_Target0
{
    float4 foreground = foregroundTexture.SampleLevel(
        guiSampler, textureCoordinates, 0.0
    );
    float3 tintedForeground = tint.rgb * foreground.rgb;
    if (foreground.a < viewportMixFactor.z)
    {
        return float4(tintedForeground, tint.a * foreground.a);
    }

    float2 screenUv = position.xy / viewportMixFactor.xy;
    float3 background = blurredBackgroundTexture.SampleLevel(
        guiSampler, screenUv, 0.0
    ).rgb;
    background = viewportMixFactor.w * background;
    float3 difference = foreground.rgb * tint.rgb - background;
    return float4(foreground.a * difference + background, tint.a);
}
