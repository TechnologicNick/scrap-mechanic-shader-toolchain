#include "include/post_fxaa_abi.hlsl"

#if defined(VS_TRANSFORM_BUFFER)
#include "include/billboard_transforms_abi.hlsl"
#endif

struct BillboardVertexOutput
{
    float4 position : SV_Position0;
    float3 texcoord : TEXCOORD0;
    float alphaScale : TEXCOORD1;
    uint packedColor : COLOR0;
    float depthOffset : TEXCOORD2;
    float minimumSize : TEXCOORD3;
    float3 viewPosition : VIEW_POSITION0;
};

float3 CameraFacingOffset(float3 center, float2 dimensions, float2 corner)
{
    float3 toCamera = normalize(viewToWorld._m23_m03_m13 - center.zxy);
    float3 right = normalize(float3(-toCamera.z, toCamera.x, 0.0));
    float3 up = cross(right, toCamera);
    return right * (corner.x * dimensions.x) + up * (corner.y * dimensions.y);
}

BillboardVertexOutput mainVS(
    float4 centerAndLayer : POSITION0,
    float4 centerData : CD0,
    float3 dimensionsAndTransform : CD1,
    float2 depthData : CD2,
    float2 pixelOffset : CD3,
    uint packedColor : COLOR0,
    uint vertexId : SV_VertexID0)
{
    static const float4 quad[6] =
    {
        float4(1.0, 1.0, 0.5, 0.5),
        float4(0.0, 0.0, -0.5, -0.5),
        float4(0.0, 1.0, -0.5, 0.5),
        float4(1.0, 0.0, 0.5, -0.5),
        float4(0.0, 0.0, -0.5, -0.5),
        float4(1.0, 1.0, 0.5, 0.5),
    };

    float4 vertex = quad[vertexId];
    BillboardVertexOutput output;
    output.texcoord = float3(vertex.xy, centerData.w);
    output.alphaScale = depthData.x;
    output.packedColor = packedColor;
    output.depthOffset = depthData.y;
    output.minimumSize = min(dimensionsAndTransform.x, dimensionsAndTransform.y);

#if defined(VS_TRANSFORM_BUFFER)
    uint transformIndex = uint(dimensionsAndTransform.z);
    float3 center = mul(transformArray[transformIndex], float4(centerData.xyz, 1.0)).xyz;
    center += CameraFacingOffset(center, dimensionsAndTransform.xy, vertex.zw);
    float4 viewPosition = mul(worldToView, float4(center, 1.0));
    output.viewPosition = viewPosition.xyz;
    float projectedDepth = cb_xViewToProjection._m23
        / (cb_xViewToProjection._m22 + viewPosition.z + depthData.x * depthData.y);
    output.position = mul(cb_xViewToProjection, viewPosition);
    output.position.z = projectedDepth * output.position.w;
#elif defined(VS_CLIP_SPACE)
    float2 corner = (vertex.zw + pixelOffset) * dimensionsAndTransform.xy;
    float4 anchor = mul(worldToViewProjection, float4(centerData.xyz, 1.0));
    float2 pixelSize = 2.0 * cb_vInvRenderScale * cb_vContainerPixelSize * anchor.w;
    float2 snapped = floor((anchor.xy + corner * pixelSize) / pixelSize) * pixelSize;
    output.position = float4(snapped, anchor.zw);
    output.viewPosition = mul(worldToView, float4(centerData.xyz, 1.0)).xyz;
#if defined(VS_OVERLAY_DEPTH_OFFSET)
    float viewDepth = output.viewPosition.z + depthData.x * depthData.y;
    float projectedDepth = cb_xViewToProjection._m23
        / (cb_xViewToProjection._m22 + viewDepth);
    output.position.z = projectedDepth * output.position.w;
#endif
#else
    float3 center = centerData.xyz;
    center += CameraFacingOffset(center, dimensionsAndTransform.xy, vertex.zw);
    float4 viewPosition = mul(worldToView, float4(center, 1.0));
    output.viewPosition = viewPosition.xyz;
    output.position = mul(cb_xViewToProjection, viewPosition);
#endif
    return output;
}
