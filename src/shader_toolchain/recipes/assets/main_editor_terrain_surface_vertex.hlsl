#include "include/post_fxaa_abi.hlsl"
#include "include/editor_surface_info_abi.hlsl"

struct EditorTerrainVertexOutput
{
    float4 position : SV_Position0;
#if !defined(DEPTH)
    float2 materialUv : TEXCOORD1;
    float2 worldUv : TEXCOORD3;
    float4 color : TEXCOORD2;
    float3 tangent : TEXCOORD4;
    float3 bitangent : TEXCOORD5;
    float3 normal : TEXCOORD6;
#endif
};

EditorTerrainVertexOutput mainVS(
    float3 objectNormal : NORMAL0,
    float heightInput : HEIGHT0,
    float4 vertexColor : COLOR0,
    uint vertexId : SV_VertexID0)
{
    uint row = vertexId / cb_info.uWidth;
    uint column = vertexId - row * cb_info.uWidth;
    float2 grid = float2(column, row);
    float2 world = 2.0 * grid;
    float height = heightInput + 0.0199999996;

    EditorTerrainVertexOutput output;
    output.position = mul(
        worldToViewProjection, float4(world, height, 1.0));
#if !defined(DEPTH)
    float3 viewNormal = mul((float3x3)worldToView, objectNormal);
    float3 viewTangent = float3(
        worldToView._m21 * viewNormal.y - worldToView._m11 * viewNormal.z,
        worldToView._m01 * viewNormal.z - worldToView._m21 * viewNormal.x,
        worldToView._m11 * viewNormal.x - worldToView._m01 * viewNormal.y);
    float3 viewBitangent = cross(viewNormal, viewTangent);
    output.materialUv = cb_info.fUvScale * grid;
    output.worldUv = 0.5 * grid;
    output.color = vertexColor.wzyx;
    output.tangent = viewNormal;
    output.bitangent = viewTangent;
    output.normal = viewBitangent;
#endif
    return output;
}
