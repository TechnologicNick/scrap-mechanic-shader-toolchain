#include "include/post_fxaa_abi.hlsl"

struct SkyVertexOutput
{
    float4 position : SV_Position;
    float2 uv : UV0;
    float2 unscaledUv : UNSCALED_UV0;
};

SkyVertexOutput triangleVS(uint vertexId : SV_VertexID)
{
    static const float2 positions[3] = {
        float2(-1.0, -1.0),
        float2( 3.0, -1.0),
        float2(-1.0,  3.0)
    };
    static const float2 texcoords[3] = {
        float2(0.0, 0.0),
        float2(2.0, 0.0),
        float2(0.0, 2.0)
    };

    SkyVertexOutput output;
    output.position = float4(positions[vertexId], 0.0, 1.0);
    output.uv = texcoords[vertexId] * cb_vRenderScale;
    output.unscaledUv = texcoords[vertexId];
    return output;
}
