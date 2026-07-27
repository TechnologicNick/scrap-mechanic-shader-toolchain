cbuffer CB_RECT : register(b0)
{
    struct
    {
        float x;
        float y;
        float width;
        float height;
    } rectangle : packoffset(c0);
}

Texture2D<float> inputDepth : register(t0);

float mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{
    uint2 sourcePixel = (uint2)(uv * rectangle.width + rectangle.x);
    return inputDepth.Load(uint3(sourcePixel, 0));
}
