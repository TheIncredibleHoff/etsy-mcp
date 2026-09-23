import pytest

from app.services.metrics import SwingAnalysisError, compute_metrics

from .synthetic import FPS, STRIDE, SWING, make_pose


def by_key(result):
    return {m["key"]: m for m in result["metrics"]}


def test_detects_right_handed_hitter_and_phases():
    result = compute_metrics(make_pose())
    assert result["bats"] == "right"
    phases = result["phases"]
    assert abs(phases["contact"]["frame"] - SWING[1]) <= 3
    assert phases["swing_start"]["frame"] < phases["contact"]["frame"]
    assert 0 <= phases["stride_start"]["frame"] - STRIDE[0] <= 8
    assert STRIDE[0] < phases["foot_plant"]["frame"] <= STRIDE[1] + 5


def test_rotation_metrics():
    m = by_key(compute_metrics(make_pose()))
    assert 70 <= m["hip_rotation"]["value"] <= 85
    assert m["shoulder_rotation"]["value"] < m["hip_rotation"]["value"]
    assert m["hip_shoulder_separation"]["value"] > 10
    # Hips peak before the shoulders.
    assert m["hip_to_shoulder_timing"]["value"] > 0


def test_stride_scales_with_height():
    no_height = by_key(compute_metrics(make_pose(stride_m=0.25)))
    assert no_height["stride_length"]["unit"] == "% height"
    assert no_height["stride_length"]["value"] > 10

    with_height = by_key(compute_metrics(make_pose(stride_m=0.25), hitter_height_in=72))
    assert with_height["stride_length"]["unit"] == "in"
    assert with_height["peak_hand_speed"]["unit"] == "mph"
    # 0.25 m of stride on a ~1.77 m tall synthetic body is ~14% of height ≈ 10 in at 6'.
    assert 6 <= with_height["stride_length"]["value"] <= 14


def test_timing_uses_fps():
    m = by_key(compute_metrics(make_pose()))
    swing_ms = m["swing_time"]["value"]
    assert 0 < swing_ms <= (SWING[1] - SWING[0] + 3) * 1000 / FPS


def test_too_few_frames():
    pose = make_pose()
    pose["frames"] = [None] * 50 + pose["frames"][:5]
    with pytest.raises(SwingAnalysisError):
        compute_metrics(pose)


def test_output_is_json_safe():
    import json

    json.dumps(compute_metrics(make_pose()), allow_nan=False)
