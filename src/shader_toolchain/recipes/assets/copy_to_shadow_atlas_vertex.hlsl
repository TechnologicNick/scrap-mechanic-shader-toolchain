void mainVS(
    float4 rectangle : RECT0,
    uint vertexId : SV_VertexID0,
    out float4 clipPosition : SV_Position0,
    out float2 uv : UV0
)
{
    float2 corner;
    if (vertexId == 1)
        corner = rectangle.zw;
    else if (vertexId == 2)
        corner = rectangle.xy;
    else if (vertexId == 3)
        corner = rectangle.xw;
    else
        corner = rectangle.zy;

    uv = corner;
    clipPosition = float4(
        corner.x * 2.0 - 1.0,
        (1.0 - corner.y) * 2.0 - 1.0,
        0.0,
        1.0
    );
}
