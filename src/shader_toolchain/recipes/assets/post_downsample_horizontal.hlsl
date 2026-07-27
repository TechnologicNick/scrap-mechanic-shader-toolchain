#include "include/post_fxaa_abi.hlsl"

SamplerState PointClampClamp : register(s1);
Texture2D<float4> inputColor : register(t0);

static const float BLUR_WEIGHTS[11] =
{
    0.012224470265209675,
    0.027834679931402206,
    0.06559061259031296,
    0.12097757309675217,
    0.17466631531715393,
    0.1974126547574997,
    0.17466631531715393,
    0.12097757309675217,
    0.06559061259031296,
    0.027834679931402206,
    0.012224470265209675,
};

float4 mainHorizontalPS(
    float4 position : SV_Position0, float2 uv : UNSCALED_UV0
) : SV_Target0
{
    float3 color = 0.0;
    for (int tap = -5; tap <= 5; ++tap)
    {
        float2 sampleUv = uv + float2(tap * cb_vContainerPixelSize.x, 0.0);
        color += inputColor.Sample(PointClampClamp, sampleUv).rgb
            * BLUR_WEIGHTS[tap + 5];
    }
    return float4(color, 1.0);
}
