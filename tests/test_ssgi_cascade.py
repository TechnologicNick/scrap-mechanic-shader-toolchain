from shader_toolchain.recipes.common import asset
from shader_toolchain.recipes.ssgi_cascade import (
    _lift_bilateral_weights,
    _lift_cascade_accumulations,
    _lift_cascade_neighborhood_gathers,
    _lift_cascade_quad_contributions,
    _name_cascade_neighborhoods,
)


def test_cascade_asset_exposes_typed_quad_and_contribution_helpers() -> None:
    source = asset("ssgi_cascade_primitives.hlsl")
    assert "struct CascadeQuad" in source
    assert "struct CascadeContribution" in source
    assert "struct CascadeFilterContext" in source
    assert "CascadeQuad DecodeCascadeQuad" in source
    assert "CascadeContribution ResolveCascadeContribution" in source
    assert "CascadeContribution GatherCascadeNeighborhood" in source
    assert "void AccumulateCascadeContribution" in source
    assert source.count("// SM_COVERAGE_CANARY: cascade_contribution") == 1


def test_weighted_gather_cluster_becomes_one_typed_contribution() -> None:
    source = """  // Decode the gathered 6:5:5 indirect-light words.
  colorState.xyz = DecodeCascadeIndirect((uint)packedState.x);
  sampleOne.xyz = DecodeCascadeIndirect((uint)packedState.y);
  sampleTwo.xyz = DecodeCascadeIndirect((uint)packedState.z);
  sampleThree.xyz = DecodeCascadeIndirect((uint)packedState.w);
  weights.xyzw = float4(0.25,0.25,0.25,0.25) * rawWeights.xyzw;
  weightSum.x = weights.x + weights.y;
  weightSum.x = rawWeights.z * 0.25 + weightSum.x;
  weightSum.x = rawWeights.w * 0.25 + weightSum.x;
  totalWeight.x = weightSum.x + totalWeight.x;
  scratch.xyz = weights.yyy * sampleOne.xyz;
  scratch.xyz = colorState.xyz * weights.xxx + scratch.xyz;
  nextScratch.xyz = sampleTwo.xyz * weights.zzz + scratch.xyz;
  nextScratch.xyz = sampleThree.xyz * weights.www + nextScratch.xyz;
  totalColor.xyz = nextScratch.xyz + totalColor.xyz;
"""

    lifted = _lift_cascade_quad_contributions(source)

    assert "CascadeContribution filteredNeighborhood0" in lifted
    assert "ResolveCascadeContribution(" in lifted
    assert "(uint4)packedState, rawWeights.xyzw);" in lifted
    assert "totalWeight.x = filteredNeighborhood0.weight + totalWeight.x;" in lifted
    assert "totalColor.xyz = filteredNeighborhood0.indirect + totalColor.xyz;" in lifted
    assert "DecodeCascadeIndirect" not in lifted


def test_bilateral_lift_accepts_a_separate_combined_scratch_register() -> None:
    source = """  distance.xyzw = deltaY.xyzw * deltaY.xyzw;
  distance.xyzw = deltaX.xyzw * deltaX.xyzw + distance.xyzw;
  distance.xyzw = deltaZ.xyzw * deltaZ.xyzw + distance.xyzw;
  distance.xyzw = sqrt(distance.xyzw);
  accepted.xyzw = cmp(filterState.yyyy >= distance.xyzw);
  accepted.xyzw = accepted.xyzw ? float4(1,1,1,1) : 0;
  inverse.xyzw = max(float4(0.00100000005,0.00100000005,0.00100000005,0.00100000005), distance.xyzw);
  inverse.xyzw = rcp(inverse.xyzw);
  deltaX.xyzw = inverse.xyzw * deltaX.xyzw;
  deltaY.xyzw = inverse.xyzw * deltaY.xyzw;
  deltaY.xyzw = deltaY.xyzw * -planeState.zzzz;
  planeWeight.xyzw = deltaX.xyzw * -planeState.yyyy + deltaY.xyzw;
  deltaZ.xyzw = inverse.xyzw * deltaZ.xyzw;
  planeWeight.xyzw = saturate(deltaZ.xyzw * -planeState.wwww + planeWeight.xyzw);
  planeWeight.xyzw = float4(1,1,1,1) + -planeWeight.xyzw;
  distanceWeight.xyzw = distance.xyzw * filterState.wwww;
  distanceWeight.xyzw = min(float4(1,1,1,1), distanceWeight.xyzw);
  distanceWeight.xyzw = float4(1,1,1,1) + -distanceWeight.xyzw;
  planeWeight.xyzw = -planeWeight.xyzw * planeWeight.xyzw + float4(1,1,1,1);
  distanceWeight.xyzw = distanceWeight.xyzw * distanceWeight.xyzw;
  planeWeight.xyzw = distanceWeight.xyzw * planeWeight.xyzw;
  planeWeight.xyzw = planeWeight.xyzw * accepted.xyzw;
"""

    lifted = _lift_bilateral_weights(source)

    assert "ComputeCascadeBilateralWeights(" in lifted
    assert "deltaX.xyzw, deltaY.xyzw, deltaZ.xyzw" in lifted
    assert "-planeState.y, -planeState.z, -planeState.w" in lifted
    assert "filterState.y, filterState.w" in lifted


def test_repeated_weight_and_indirect_additions_become_one_accumulation() -> None:
    source = """  totalWeight.x = contribution.weight + totalWeight.x;
  totalIndirect.xyz = contribution.indirect + totalIndirect.xyz;
"""

    lifted = _lift_cascade_accumulations(source)

    assert lifted == """  AccumulateCascadeContribution(
      totalWeight.x, totalIndirect.xyz, contribution);
"""


def test_gather_depth_filter_and_decode_become_one_neighborhood_call() -> None:
    source = """  packed.xyzw = tSsgi.Gather(PointClampClamp_s, sampleUv.xy).xyzw;
  depth.xyzw = tSsgi.GatherGreen(PointClampClamp_s, sampleUv.xy).xyzw;
  depth.xyzw = depth.xyzw * depth.xyzw;
  depth.xyzw = depth.xyzw * depthState.xxxx + float4(0.100000001,0.100000001,0.100000001,0.100000001);
  deltaX.xyzw = rays.xxxx * depth.xyzw + -center.xxxx;
  deltaY.xyzw = rays.yyyy * depth.xyzw + -center.yyyy;
  deltaZ.xyzw = -depth.xyzw + -center.zzzz;
  // Plane- and distance-aware neighborhood rejection.
  weights.xyzw = ComputeCascadeBilateralWeights(
      deltaX.xyzw, deltaY.xyzw, deltaZ.xyzw,
      plane.x, plane.y, plane.z,
      limits.x, limits.y);
  packedWords.xyzw = packed.xyzw * float4(65535,65535,65535,65535) + float4(0.5,0.5,0.5,0.5);
  packedWords.xyzw = (uint4)packedWords.xyzw;
  CascadeContribution contribution = ResolveCascadeContribution(
      (uint4)packedWords, weights.xyzw);
"""

    lifted = _lift_cascade_neighborhood_gathers(source)

    assert "CascadeFilterContext cascadeFilterContext" in lifted
    assert "GatherCascadeNeighborhood(" in lifted
    assert "tSsgi, PointClampClamp_s, sampleUv.xy" in lifted
    assert "rays.xxxx, rays.yyyy, cascadeFilterContext" in lifted
    assert "ComputeCascadeBilateralWeights" not in lifted
    assert "GatherGreen" not in lifted


def test_neighborhoods_receive_spatial_names() -> None:
    source = """  float2 cascadeNeighborhoodUv0 = sampleUv;
  CascadeContribution filteredNeighborhood1 = GatherCascadeNeighborhood();
  CascadeContribution filteredNeighborhood8 = GatherCascadeNeighborhood();
"""

    named = _name_cascade_neighborhoods(source)

    assert "northWestUv" in named
    assert "northWestContribution" in named
    assert "southEastContribution" in named
    assert "filteredNeighborhood" not in named
