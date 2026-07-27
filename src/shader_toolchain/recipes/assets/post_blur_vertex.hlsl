struct FullscreenVertexOutput
{
    float4 position : SV_Position0;
};

FullscreenVertexOutput triangleVS(uint vertexId : SV_VertexID0)
{
    static const float2 positions[3] =
    {
        float2(-1.0, -1.0),
        float2( 3.0, -1.0),
        float2(-1.0,  3.0),
    };

    FullscreenVertexOutput output;
    output.position = float4(positions[vertexId], 0.0, 1.0);
    return output;
}
