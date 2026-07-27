#include "include/post_fxaa_abi.hlsl"

SamplerState LinearWrap : register(s3);
SamplerState LinearClamp : register(s6);
Texture2DArray<float4> diffuseLayers : register(t0);
Texture2DArray<float4> asgLayers : register(t1);
Texture2DArray<float4> normalLayers : register(t2);
Texture2DArray<float4> materialWeightsA : register(t3);
Texture2DArray<float4> materialWeightsB : register(t4);

struct LayerSample
{
    float3 diffuse;
    float3 asg;
    float2 normal;
};

LayerSample SampleLayer(float2 worldUv, uint layer)
{
    LayerSample sample;
    sample.diffuse = diffuseLayers.SampleBias(
        LinearWrap, float3(worldUv, float(layer)), cb_fMipBias).rgb;
    sample.asg = asgLayers.SampleBias(
        LinearWrap, float3(worldUv, float(layer)), cb_fMipBias).yzw;
    sample.normal = normalLayers.SampleBias(
        LinearWrap, float3(worldUv, float(layer)), cb_fMipBias).rg;
    return sample;
}

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

struct TerrainGBuffer
{
    float4 albedo : SV_Target0;
    float2 encodedNormal : SV_Target1;
    float4 material : SV_Target2;
};

TerrainGBuffer mainPS(
    float4 position : SV_Position0,
    float2 materialUv : UV0,
    float2 worldUv : WORLD_UV0,
    float3 vertexColor : COLOR0,
    nointerpolation uint tileIndex : TILE_INDEX0,
    float4 tangentInput : TEXCOORD5,
    float4 bitangentInput : TEXCOORD6,
    float3 normalInput : TEXCOORD7)
{
    float4 packedA = materialWeightsA.Sample(
        LinearClamp, float3(materialUv, float(tileIndex))).zxwy;
    float4 packedB = materialWeightsB.Sample(
        LinearClamp, float3(materialUv, float(tileIndex))).zxwy;
    float weightsByLayer[8] = {
        packedA.y, packedA.w, packedA.x, packedA.z,
        packedB.y, packedB.w, packedB.x, packedB.z,
    };

    float3 strongestWeights;
    uint3 strongestLayers;
    TakeStrongest(weightsByLayer, strongestWeights.x, strongestLayers.x);
    TakeStrongest(weightsByLayer, strongestWeights.y, strongestLayers.y);
    TakeStrongest(weightsByLayer, strongestWeights.z, strongestLayers.z);
    SortByLayer(strongestWeights, strongestLayers);

    float4 baseDiffuseTexture = diffuseLayers.SampleBias(
        LinearWrap, float3(worldUv, 8.0), cb_fMipBias);
    LayerSample baseLayer = SampleLayer(worldUv, 8u);
    float coverage = min(1.0, 2.0 * baseDiffuseTexture.a);
    float3 diffuse = coverage * baseLayer.diffuse;
    float3 asg = coverage * baseLayer.asg;
    float2 normalMap = coverage * baseLayer.normal;

    [unroll] for (uint index = 0; index < 3; ++index)
    {
        if (strongestWeights[index] > 0.0)
        {
            uint layer = strongestLayers[index];
            float4 layerDiffuse = diffuseLayers.SampleBias(
                LinearWrap, float3(worldUv, float(layer)), cb_fMipBias);
            LayerSample sample = SampleLayer(worldUv, layer);
            float blend = min(
                1.0, 2.0 * strongestWeights[index] * layerDiffuse.a);
            diffuse = lerp(diffuse, sample.diffuse, blend);
            asg = lerp(asg, sample.asg, blend);
            normalMap = lerp(normalMap, sample.normal, blend);
        }
    }

    float2 tangentNormal = normalMap * 1.99215686 - 1.0;
    float tangentZ = sqrt(max(0.0, 1.0 - dot(tangentNormal, tangentNormal)));
    float3 tangent = normalize(tangentInput.xyz).zxy;
    float3 bitangent = normalize(bitangentInput.xyz).zxy;
    float3 normal = normalize(normalInput).zxy;
    float3 mappedNormal = normal * tangentNormal.y;
    mappedNormal = mad(bitangent, tangentNormal.x, mappedNormal);
    float3 viewNormal = normalize(mad(tangent, tangentZ, mappedNormal));

    TerrainGBuffer output;
    output.albedo = float4(1.29999995 * vertexColor * diffuse, asg.y);
    output.encodedNormal = EncodeViewNormal(viewNormal);
    output.material = float4(asg.z, asg.x, 0.0, 0.0);
    return output;
}
