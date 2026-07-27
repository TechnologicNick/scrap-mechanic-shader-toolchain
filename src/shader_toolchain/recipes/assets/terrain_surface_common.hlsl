struct LayerSample
{
    float3 diffuse;
    float3 asg;
    float2 normal;
};

void TakeStrongest(inout float weightsByLayer[8], out float weight, out uint layer)
{
    weight = weightsByLayer[0] > 0.0 ? weightsByLayer[0] : 0.0;
    layer = 0u;
    [unroll] for (uint candidate = 1u; candidate < 8u; ++candidate)
    {
        if (weight < weightsByLayer[candidate])
        {
            weight = weightsByLayer[candidate];
            layer = candidate;
        }
    }
    weightsByLayer[layer] = 0.0;
}

void SortByLayer(inout float3 weights, inout uint3 layers)
{
    if (layers.x > layers.y)
    {
        uint layer = layers.x; layers.x = layers.y; layers.y = layer;
        float weight = weights.x; weights.x = weights.y; weights.y = weight;
    }
    if (layers.y > layers.z)
    {
        uint layer = layers.y; layers.y = layers.z; layers.z = layer;
        float weight = weights.y; weights.y = weights.z; weights.z = weight;
    }
    if (layers.x > layers.y)
    {
        uint layer = layers.x; layers.x = layers.y; layers.y = layer;
        float weight = weights.x; weights.x = weights.y; weights.y = weight;
    }
}

float2 EncodeViewNormal(float3 viewNormal)
{
    float3 octahedron = normalize(viewNormal);
    octahedron /= dot(abs(octahedron), 1.0);
    float2 wrapped = (1.0 - abs(octahedron.zy))
        * float2(octahedron.y >= 0.0 ? 1.0 : -1.0,
                 octahedron.z >= 0.0 ? 1.0 : -1.0);
    return 0.5 * (octahedron.x >= 0.0 ? octahedron.yz : wrapped) + 0.5;
}
