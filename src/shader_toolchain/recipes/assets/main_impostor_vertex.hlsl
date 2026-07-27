#include "include/post_fxaa_abi.hlsl"
#include "include/impostors_abi.hlsl"

struct ImpostorVertexOutput
{
    float4 position : SV_Position0;
    float2 atlasUv : TEXCOORD0;
    float4 atlasLayer : TEXCOORD1;
#if defined(GBUFFER)
    float4 screenUv : TEXCOORD2;
    float4 facingSlice : TEXCOORD3;
    float4 blendSlices : TEXCOORD4;
    float4 blendWeights : TEXCOORD5;
    uint4 packedData : TEXCOORD6;
#endif
};

ImpostorVertexOutput mainVS(
    uint2 data : DATA0,
    float2 localToWorld0 : LTW0,
    float4 localToWorld1 : LTW1,
    float4 localToWorld2 : LTW2,
    float2 positionData : POS0,
    float3 viewDirection : VIEW_DIR0,
    uint vertexId : SV_VertexID0)
{
    static const float2 corners[4] = {
        float2(-1.0, 1.0), float2(-1.0, -1.0),
        float2(1.0, 1.0), float2(1.0, -1.0)
    };
    uint slot = data.x << 1u;
    float radius = vecImpostorSlots[slot].fRadius;
    float3 center = vecImpostorSlots[slot].vCenter;
    float2 corner = corners[vertexId & 3u];
    float4 center4 = float4(center, 1.0);
    float3 transformedCenter;
    transformedCenter.x = dot(float4(localToWorld0, localToWorld1.xy), center4);
    transformedCenter.y = dot(localToWorld1, center4);
    transformedCenter.z = dot(localToWorld2, center4);
    transformedCenter.xz += positionData;
    float3 facing = normalize(viewDirection);
    float3 right = normalize(cross(float3(0.0, 1.0, 0.0), facing));
    float3 up = cross(facing, right);
    float3 worldPosition = transformedCenter
        + right * (corner.x * radius)
        + up * (corner.y * radius);
    ImpostorVertexOutput output;
    output.position = mul(float4(worldPosition, 1.0), worldToViewProjection);
    output.atlasUv = corner * float2(0.5, -0.5) + 0.5;
    output.atlasLayer.x = (float)data.x;
#if defined(GBUFFER)
    float2 ndc = output.position.xy / output.position.w;
    output.screenUv.xy = (ndc * float2(0.5, -0.5) + 0.5)
        * (float2)cb_vuViewportSize * (1.0 / 128.0);
    output.facingSlice.y = atan2(viewDirection.x, viewDirection.z);
    output.blendSlices = float4(0.0, 1.0, 2.0, 3.0);
    output.blendWeights.xyz = abs(viewDirection);
    output.packedData.z = data.y;
#endif
    return output;
}
