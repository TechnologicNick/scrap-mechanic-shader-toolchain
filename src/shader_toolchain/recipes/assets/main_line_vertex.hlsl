float fLineWidth;
float fTextureAspect;
float fScroll;
float _fPadding;
#include "include/post_fxaa_abi.hlsl"

struct LineVertexOutput
{
    float4 position : SV_Position0;
    float2 uv : TEXCOORD0;
    float4 endFade : TEXCOORD1;
    float4 length : TEXCOORD2;
    float4 color : COLOR0;
#if defined(TRANSFER_SCREEN_UV)
    float3 screenUv : SCREEN_UV0;
#endif
};

float4 TransformView(float3 position)
{
    float4 transformed = worldToView._m01_m11_m21_m31 * position.y;
    transformed = mad(worldToView._m00_m10_m20_m30, position.x, transformed);
    transformed = mad(worldToView._m02_m12_m22_m32, position.z, transformed);
    return worldToView._m03_m13_m23_m33 + transformed;
}

float4 TransformProjection(float4 viewPosition)
{
    float4 projected = cb_xViewToProjection._m01_m11_m21_m31 * viewPosition.y;
    projected = mad(cb_xViewToProjection._m00_m10_m20_m30,
                    viewPosition.x, projected);
    projected = mad(cb_xViewToProjection._m02_m12_m22_m32,
                    viewPosition.z, projected);
    return mad(cb_xViewToProjection._m03_m13_m23_m33,
               viewPosition.w, projected);
}

LineVertexOutput mainVS(
    float3 startPosition : POSITION_A0,
    float3 endPosition : POSITION_B0,
    float4 inputColor : COLOR0,
    uint vertexId : SV_VertexID0)
{
    static const float4 corners[6] =
    {
        float4( 1.0, -1.0, 0.0, -1.0),
        float4(-1.0,  0.0, 0.0,  0.0),
        float4(-1.0, -1.0, 1.0, -1.0),
        float4(-1.0, -1.0, 1.0, -1.0),
        float4(-1.0,  0.0, 0.0,  0.0),
        float4( 1.0,  0.0, 1.0,  0.0),
    };
    float4 corner = corners[vertexId];
    bool useEndAsCenter = (int)corner.w != 0;
    float3 centerWorld = useEndAsCenter ? endPosition : startPosition;
    float3 otherWorld = useEndAsCenter ? startPosition : endPosition;

    float3 centerAux;
    centerAux.x = dot(worldToView._m10_m11_m12, centerWorld);
    centerAux.y = dot(worldToView._m20_m21_m22, centerWorld);
    centerAux.z = dot(worldToView._m00_m01_m02, centerWorld);
    centerAux += worldToView._m13_m23_m03;
    float4 centerView = TransformView(otherWorld);
    float3 midpointDirection = normalize(
        0.5 * (centerView.zxy + centerAux.zxy));
    float3 segmentDirection = normalize(centerAux - centerView.yzx);

    float3 ribbonNormal;
    ribbonNormal.x = midpointDirection.z * segmentDirection.y
        - midpointDirection.x * segmentDirection.x;
    ribbonNormal.y = midpointDirection.x * segmentDirection.z
        - midpointDirection.y * segmentDirection.y;
    ribbonNormal.z = midpointDirection.y * segmentDirection.x
        - midpointDirection.z * segmentDirection.z;
    float normalLength = length(ribbonNormal);
    if (normalLength < 0.00100000005)
    {
        float3 fallback;
        fallback.x = -segmentDirection.z;
        fallback.y = 0.0;
        fallback.z = segmentDirection.x;
        normalLength = max(0.0000999999975, length(fallback.xz));
        ribbonNormal = fallback;
    }
    ribbonNormal /= normalLength;
    centerView.xyz += corner.x * fLineWidth * ribbonNormal;

    LineVertexOutput output;
    output.position = TransformProjection(centerView);
    float worldLength = length(startPosition - endPosition);
    float textureLength = worldLength / (fLineWidth + fLineWidth);
    output.uv = float2(corner.y * fTextureAspect * textureLength, corner.z);
    output.endFade.z = corner.z;
    output.length.x = worldLength;
    output.color.yzw = inputColor.wzy;
#if defined(TRANSFER_SCREEN_UV)
    float3 ndc = output.position.xyz / output.position.w;
    float3 screen = mad(ndc, float3(0.5, -0.5, 1.0), float3(0.5, 0.5, 0.0));
    output.screenUv = float3(cb_vRenderScale * screen.xy, screen.z);
#endif
    return output;
}
