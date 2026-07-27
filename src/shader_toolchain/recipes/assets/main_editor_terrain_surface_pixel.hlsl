#include "include/post_fxaa_abi.hlsl"

SamplerState LinearWrap : register(s3);
SamplerState LinearClamp : register(s6);
Texture2DArray<float4> diffuseLayers : register(t0);
Texture2DArray<float4> asgLayers : register(t1);
Texture2DArray<float4> normalLayers : register(t2);
Texture2D<float4> materialWeightsA : register(t3);
Texture2D<float4> materialWeightsB : register(t4);

#include "include/terrain_surface_common.hlsl"

LayerSample SampleLayer(float2 worldUv, uint layer)
{
    LayerSample sample;
    sample.diffuse = diffuseLayers.Sample(
        LinearWrap, float3(worldUv, float(layer))).rgb;
    sample.asg = asgLayers.Sample(
        LinearWrap, float3(worldUv, float(layer))).yzw;
    sample.normal = normalLayers.Sample(
        LinearWrap, float3(worldUv, float(layer))).rg;
    return sample;
}

struct TerrainGBuffer
{
    float4 albedo : SV_Target0;
    float2 encodedNormal : SV_Target1;
    float4 material : SV_Target2;
};

TerrainGBuffer mainPS(
    float4 position : SV_Position0,
    float2 materialUv : TEXCOORD1,
    float2 worldUv : TEXCOORD3,
    float4 vertexColor : TEXCOORD2,
    float4 tangentInput : TEXCOORD4,
    float4 bitangentInput : TEXCOORD5,
    float3 normalInput : TEXCOORD6)
{
    float4 packedA = materialWeightsA.Sample(LinearClamp, materialUv).zxwy;
    float4 packedB = materialWeightsB.Sample(LinearClamp, materialUv).zxwy;
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

    float4 baseDiffuseTexture = diffuseLayers.Sample(
        LinearWrap, float3(worldUv, 8.0));
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
            float4 layerDiffuse = diffuseLayers.Sample(
                LinearWrap, float3(worldUv, float(layer)));
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
    output.albedo = float4(
        1.29999995 * vertexColor.rgb * diffuse, asg.y);
    output.encodedNormal = EncodeViewNormal(viewNormal);
    output.material = float4(asg.z, asg.x, 0.0, 0.0);
    return output;
}
