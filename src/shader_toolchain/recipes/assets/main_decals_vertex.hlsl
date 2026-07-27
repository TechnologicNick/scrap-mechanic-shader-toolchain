#include "include/post_fxaa_abi.hlsl"
#include "include/decals_abi.hlsl"
#include "include/decals_offset_abi.hlsl"

struct DecalVertexOutput
{
    float4 position : SV_Position0;
    float2 screenUv : TEXCOORD0;
    nointerpolation uint decalIndex : INDEX0;
};

DecalVertexOutput mainVS(float4 position : POSITION0, uint instanceId : SV_InstanceID0)
{
    DecalVertexOutput output;
    uint decalIndex = instanceId + cb_uDecalOffset;
    float3 viewPosition = float3(
        dot(cb_arrDecals[decalIndex].Row0, position),
        dot(cb_arrDecals[decalIndex].Row1, position),
        dot(cb_arrDecals[decalIndex].Row2, position));
    output.position = mul(float4(viewPosition, position.w), cb_xViewToProjection);
    output.screenUv = output.position.xy / output.position.w
        * float2(0.5, -0.5) + 0.5;
    output.decalIndex = decalIndex;
    return output;
}
