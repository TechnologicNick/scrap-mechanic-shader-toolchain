#include "include/post_fxaa_abi.hlsl"

SamplerState PointClampClamp : register(s1);
SamplerState LinearClampClamp : register(s6);
Texture2D<float3> lowResolutionBloom : register(t0);
Texture2D<float> hierarchicalDepth : register(t1);

float3 SampleBloom(float2 uv)
{
    return lowResolutionBloom.SampleLevel(
        LinearClampClamp, min(cb_vUvLimitMipDown, uv), 0.0
    );
}

float4 DepthWeights(
    float4 neighborDepth, float centerDepth, float tolerance, float scale
)
{
    float4 delta = neighborDepth - centerDepth;
    float4 weights = 1.0 - saturate(delta / tolerance);
    weights = delta > 0.0 ? weights : 1.0;
    return scale * weights;
}

float3 mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    float2 pixel = cb_vPixelSizeMipDown * cb_vDownScaleing;
    float3 southEast = SampleBloom(uv + pixel);
    float3 northWest = SampleBloom(uv - pixel);

    float centerDepth = hierarchicalDepth.SampleLevel(
        PointClampClamp, uv, 1.0
    );
    float depthTolerance = max(0.01, 0.1 * (centerDepth * centerDepth));

    float4 diagonalDepth;
    float2 coordinates = pixel * 2.0 + uv;
    diagonalDepth.w = hierarchicalDepth.SampleLevel(
        PointClampClamp, coordinates, 1.0
    );
    float4 pairedCoordinates = pixel.xyxy
        * float4(-2.0, -2.0, 2.0, -2.0) + uv.xyxy;
    diagonalDepth.x = hierarchicalDepth.SampleLevel(
        PointClampClamp, pairedCoordinates.xy, 1.0
    );
    diagonalDepth.y = hierarchicalDepth.SampleLevel(
        PointClampClamp, pairedCoordinates.zw, 1.0
    );
    pairedCoordinates = pixel.xyxy
        * float4(-2.0, 2.0, 0.0, 4.0) + uv.xyxy;
    diagonalDepth.z = hierarchicalDepth.SampleLevel(
        PointClampClamp, pairedCoordinates.xy, 1.0
    );

    float4 cardinalDepth;
    cardinalDepth.x = hierarchicalDepth.SampleLevel(
        PointClampClamp, pairedCoordinates.zw, 1.0
    );
    float4 eastAndNorthEast = pixel.xyxy
        * float4(4.0, 0.0, 1.0, -1.0) + uv.xyxy;
    cardinalDepth.w = hierarchicalDepth.SampleLevel(
        PointClampClamp, eastAndNorthEast.xy, 1.0
    );

    float4 diagonalWeights = DepthWeights(
        diagonalDepth, centerDepth, depthTolerance, 2.0
    );
    float3 northEast = SampleBloom(eastAndNorthEast.zw);
    northEast = northEast * diagonalWeights.y;
    float3 result = northWest * diagonalWeights.x + northEast;

    float4 southWestAndSouth = pixel.xyxy
        * float4(-1.0, 1.0, 0.0, 2.0) + uv.xyxy;
    southWestAndSouth = min(
        cb_vUvLimitMipDown.xyxy, southWestAndSouth
    );
    float3 southWest = lowResolutionBloom.SampleLevel(
        LinearClampClamp, southWestAndSouth.xy, 0.0
    );
    float3 south = lowResolutionBloom.SampleLevel(
        LinearClampClamp, southWestAndSouth.zw, 0.0
    );
    result = southWest * diagonalWeights.z + result;
    result = southEast * diagonalWeights.w + result;
    float3 center = lowResolutionBloom.SampleLevel(
        LinearClampClamp, uv, 0.0
    );
    result = center * 4.0 + result;

    float4 northAndWestDepthCoordinates = pixel.xyxy
        * float4(0.0, -4.0, -4.0, 0.0) + uv.xyxy;
    cardinalDepth.y = hierarchicalDepth.SampleLevel(
        PointClampClamp, northAndWestDepthCoordinates.xy, 1.0
    );
    cardinalDepth.z = hierarchicalDepth.SampleLevel(
        PointClampClamp, northAndWestDepthCoordinates.zw, 1.0
    );
    float4 cardinalWeights = DepthWeights(
        cardinalDepth, centerDepth, depthTolerance, 1.0
    );

    float4 northAndWestUvs = pixel.xyxy
        * float4(0.0, -2.0, -2.0, 0.0) + uv.xyxy;
    float2 eastUv = pixel * float2(2.0, 0.0) + uv;
    eastUv = min(cb_vUvLimitMipDown, eastUv);
    float3 east = lowResolutionBloom.SampleLevel(
        LinearClampClamp, eastUv, 0.0
    );
    northAndWestUvs = min(cb_vUvLimitMipDown.xyxy, northAndWestUvs);
    float3 north = lowResolutionBloom.SampleLevel(
        LinearClampClamp, northAndWestUvs.xy, 0.0
    );
    float3 west = lowResolutionBloom.SampleLevel(
        LinearClampClamp, northAndWestUvs.zw, 0.0
    );
    north = north * cardinalWeights.y;
    south = south * cardinalWeights.x + north;
    west = west * cardinalWeights.z + south;
    east = east * cardinalWeights.w + west;
    result = east + result;

    precise float cardinalTotal = cardinalWeights.x + cardinalWeights.y;
    cardinalTotal = cardinalTotal + cardinalWeights.z;
    cardinalTotal = cardinalTotal + cardinalWeights.w;
    precise float diagonalTotal = diagonalWeights.x + diagonalWeights.y;
    diagonalTotal = diagonalTotal + diagonalWeights.z;
    diagonalTotal = diagonalTotal + diagonalWeights.w;
    diagonalTotal = 4.0 + diagonalTotal;
    precise float totalWeight = diagonalTotal + cardinalTotal;
    return result / totalWeight;
}
