struct FullscreenVertexOutput
{
    float4 position : SV_Position0;
    float2 uv : UNSCALED_UV0;
};

FullscreenVertexOutput triangleVS(uint vertexId : SV_VertexID0)
{
    static const float2 positions[3] = {
        float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0)
    };
    static const float2 coordinates[3] = {
        float2(0.0, 0.0), float2(2.0, 0.0), float2(0.0, 2.0)
    };
    FullscreenVertexOutput output;
    output.position = float4(positions[vertexId], 0.0, 1.0);
    output.uv = coordinates[vertexId];
    return output;
}
