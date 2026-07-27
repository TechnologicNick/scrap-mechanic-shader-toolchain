struct FxaaVertexOutput
{
    float4 position : SV_Position0;
    float4 uv : UV0;
};

FxaaVertexOutput mainVS(uint vertexId : SV_VertexID0)
{
    static const float2 positions[3] =
    {
        float2(-1.0, -1.0),
        float2( 3.0, -1.0),
        float2(-1.0,  3.0),
    };
    static const float2 textureCoordinates[3] =
    {
        float2(0.0,  1.0),
        float2(2.0,  1.0),
        float2(0.0, -1.0),
    };

    FxaaVertexOutput output;
    output.position = float4(positions[vertexId], 0.0, 1.0);

    float2 centerUv = textureCoordinates[vertexId] * cb_vRenderScale;
    output.uv.xy = centerUv;
    output.uv.zw = centerUv - 0.75 * cb_vContainerPixelSize;
    return output;
}
