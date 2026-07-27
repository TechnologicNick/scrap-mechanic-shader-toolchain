#include "include/post_fxaa_abi.hlsl"
#include "include/terrain_tile_info_abi.hlsl"

struct TerrainVertexOutput
{
    float4 position : SV_Position0;
#if !defined(DEPTH)
    float2 materialUv : UV0;
    float2 worldUv : WORLD_UV0;
    float3 color : COLOR0;
    uint tileIndex : TILE_INDEX0;
    float3 tangent : TEXCOORD5;
    float3 bitangent : TEXCOORD6;
    float3 normal : TEXCOORD7;
#endif
};

TerrainVertexOutput mainVS(
    float2 heights : HEIGHT0,
    float4 packedNormal : NORMAL0,
    uint4 colorAndEdges : COLOR0,
    uint vertexId : SV_VertexID0)
{
    uint tile = vertexId / 576u;
    uint vertexInTile = vertexId - tile * 576u;
    uint row = vertexInTile / 24u;
    uint column = vertexInTile - row * 24u;
    uint2 grid = uint2(column, row);
    float2 world = float2(grid) * arrTileInfo[tile].fScale
        + arrTileInfo[tile].vWorldPos;
    bool edge = (colorAndEdges.w & arrTileInfo[tile].uEdgeFlags) != 0u;
    float height = (edge ? heights.y : heights.x) + 0.0199999996;

    TerrainVertexOutput output;
    output.position = mul(worldToViewProjection, float4(world, height, 1.0));
#if !defined(DEPTH)
    float2 packedSlope = edge ? packedNormal.zw : packedNormal.xy;
    float slopeZ = sqrt(1.0 - dot(packedSlope, packedSlope));
    float3 viewNormal = mul((float3x3)worldToView, float3(packedSlope, slopeZ));
    float3 viewTangent = float3(
        worldToView._m21 * viewNormal.y - worldToView._m11 * viewNormal.z,
        worldToView._m01 * viewNormal.z - worldToView._m21 * viewNormal.x,
        worldToView._m11 * viewNormal.x - worldToView._m01 * viewNormal.y);
    float3 viewBitangent = cross(viewNormal, viewTangent);
    output.materialUv = float2(grid) * 0.0434782617;
    output.worldUv = 0.25 * world;
    output.color = float3(colorAndEdges.xyz) * 0.00390625;
    output.tileIndex = tile;
    output.tangent = viewNormal;
    output.bitangent = viewTangent;
    output.normal = viewBitangent;
#endif
    return output;
}
