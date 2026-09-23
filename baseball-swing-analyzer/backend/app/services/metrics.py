"""Turn per-frame pose landmarks into swing mechanics metrics.

Everything here is derived from body landmarks only. MediaPipe tracks
people, not bats or balls, so bat path is measured through the hands and
launch angle is estimated from the hands' direction of travel at contact
(the swing's attack angle). Those limits are spelled out in each metric's
description so the UI and Claude can be upfront about them.

Assumptions: a fixed camera, one swing per clip, and a roughly side-on view.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

# MediaPipe landmark indices
NOSE = 0
L_SHOULDER, R_SHOULDER = 11, 12
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_ANKLE, R_ANKLE = 27, 28
L_HEEL, R_HEEL = 29, 30

# The nose sits at roughly 93% of standing height.
NOSE_HEIGHT_FRACTION = 0.93
MIN_TRACKED_FRAMES = 10
MPS_TO_MPH = 2.23694


class SwingAnalysisError(ValueError):
    pass


def _interpolate(arr: np.ndarray) -> np.ndarray:
    """Fill NaN gaps along axis 0 by linear interpolation (edges are held)."""
    out = arr.reshape(arr.shape[0], -1).copy()
    idx = np.arange(out.shape[0])
    for col in range(out.shape[1]):
        y = out[:, col]
        good = ~np.isnan(y)
        if good.any():
            out[:, col] = np.interp(idx, idx[good], y[good])
    return out.reshape(arr.shape)


def _smooth(arr: np.ndarray, window: int) -> np.ndarray:
    """Centered moving average along axis 0 with edge padding."""
    if window <= 1 or arr.shape[0] < window:
        return arr
    pad = window // 2
    padded = np.pad(arr, [(pad, pad)] + [(0, 0)] * (arr.ndim - 1), mode="edge")
    kernel = np.ones(window) / window
    flat = padded.reshape(padded.shape[0], -1)
    smoothed = np.stack(
        [np.convolve(flat[:, c], kernel, mode="valid") for c in range(flat.shape[1])], axis=1
    )
    return smoothed.reshape((arr.shape[0],) + arr.shape[1:])


def _angle_deg(dx: np.ndarray, dz: np.ndarray) -> np.ndarray:
    """Heading of a horizontal-plane vector, unwrapped so rotation is continuous."""
    return np.degrees(np.unwrap(np.arctan2(dz, dx)))


def _velocity(series: np.ndarray, fps: float) -> np.ndarray:
    return np.gradient(series, axis=0) * fps


def _r(v: float | None, digits: int = 1) -> float | None:
    if v is None or not math.isfinite(v):
        return None
    return round(float(v), digits)


def _metric(
    key: str,
    label: str,
    value: float | None,
    unit: str,
    category: str,
    description: str,
    digits: int = 1,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": _r(value, digits),
        "unit": unit,
        "category": category,
        "description": description,
    }


def compute_metrics(pose: dict[str, Any], hitter_height_in: float | None = None) -> dict[str, Any]:
    fps = float(pose["fps"])
    width, height = float(pose["width"]), float(pose["height"])
    frames = pose["frames"]
    n = len(frames)

    tracked = np.array([f is not None for f in frames])
    if tracked.sum() < MIN_TRACKED_FRAMES:
        raise SwingAnalysisError(
            f"The hitter was only tracked in {int(tracked.sum())} frames — not enough to measure a swing."
        )

    nan_img = np.full((33, 4), np.nan)
    nan_world = np.full((33, 3), np.nan)
    img = np.array([np.array(f["image"]) if f else nan_img for f in frames], dtype=float)
    world = np.array([np.array(f["world"]) if f else nan_world for f in frames], dtype=float)

    # Low-confidence joints are treated as missing, then gaps are filled.
    low_vis = img[:, :, 3] < 0.3
    img[low_vis, :3] = np.nan
    world[low_vis] = np.nan

    window = max(3, int(round(fps * 0.05)) | 1)
    px = _smooth(_interpolate(img[:, :, :2] * np.array([width, height])), window)  # (n, 33, 2)
    wd = _smooth(_interpolate(world), window)  # (n, 33, 3), meters, y points down

    # ---- Scale -----------------------------------------------------------
    heel_px_y = np.nanmean(px[:, [L_HEEL, R_HEEL], 1], axis=1)
    body_px = float(np.median((heel_px_y - px[:, NOSE, 1]) / NOSE_HEIGHT_FRACTION))
    if not body_px > 0:
        raise SwingAnalysisError("Couldn't measure the hitter's body — make sure they're fully in frame.")
    height_m = hitter_height_in * 0.0254 if hitter_height_in else None

    # ---- Handedness: the stride foot is the lead foot ---------------------
    ankle_range = np.ptp(px[:, [L_ANKLE, R_ANKLE], 0], axis=0)
    lead_is_left = bool(ankle_range[0] >= ankle_range[1])
    lead_ankle, rear_ankle = (L_ANKLE, R_ANKLE) if lead_is_left else (R_ANKLE, L_ANKLE)
    lead_sh, rear_sh = (L_SHOULDER, R_SHOULDER) if lead_is_left else (R_SHOULDER, L_SHOULDER)
    lead_hip, rear_hip = (L_HIP, R_HIP) if lead_is_left else (R_HIP, L_HIP)
    bats = "right" if lead_is_left else "left"

    # ---- Hands: speed and estimated contact ------------------------------
    hands = (px[:, L_WRIST] + px[:, R_WRIST]) / 2  # (n, 2)
    hand_vel = _velocity(hands, fps)
    hand_speed = np.linalg.norm(hand_vel, axis=1) / body_px  # body heights / s
    contact = int(np.argmax(hand_speed))
    peak_speed = float(hand_speed[contact])

    warnings: list[str] = []
    if peak_speed < 1.5:
        warnings.append(
            "The hands never moved fast enough to look like a full swing — results may not be meaningful."
        )
    if contact >= n - 2:
        warnings.append("The clip seems to end at or before contact; include the follow-through.")

    below = np.where(hand_speed[:contact] < 0.25 * peak_speed)[0]
    swing_start = int(below[-1]) if below.size else 0

    # ---- Stride ----------------------------------------------------------
    stance_end = max(1, min(5, swing_start))
    lead_x = px[:, lead_ankle, 0]
    lead_x0 = float(np.median(lead_x[:stance_end]))
    disp = np.abs(lead_x - lead_x0) / body_px
    pre = disp[: contact + 1]
    stride_start = foot_plant = None
    if pre.max() > 0.04:
        moving = np.where(pre > 0.015)[0]
        stride_start = int(moving[0])
        lead_speed = np.abs(_velocity(lead_x, fps)) / body_px
        settled = np.where(
            (np.arange(contact + 1) > stride_start)
            & (pre > 0.6 * pre.max())
            & (lead_speed[: contact + 1] < 0.25)
        )[0]
        foot_plant = int(settled[0]) if settled.size else int(np.argmax(pre))

    # Reference "stance" frames: before the stride (or the swing) begins.
    ref_end = max(1, min(stride_start if stride_start is not None else swing_start, 10))
    ref = slice(0, ref_end)

    ankle_sep = np.abs(px[:, lead_ankle, 0] - px[:, rear_ankle, 0]) / body_px
    stance_width = float(np.median(ankle_sep[ref]))
    stride_frac = float(ankle_sep[foot_plant] - stance_width) if foot_plant is not None else 0.0

    # ---- Rotation (world coordinates, horizontal x/z plane) ---------------
    def heading(a: int, b: int) -> np.ndarray:
        v = wd[:, a] - wd[:, b]
        return _angle_deg(v[:, 0], v[:, 2])

    hip_angle = heading(lead_hip, rear_hip)
    sh_angle = heading(lead_sh, rear_sh)
    hip_rel = hip_angle - np.median(hip_angle[ref])
    sh_rel = sh_angle - np.median(sh_angle[ref])
    # The swing direction decides which way is "open"; flip so rotation into the swing is positive.
    sign = 1.0 if hip_rel[contact] >= 0 else -1.0
    hip_rel *= sign
    sh_rel *= sign
    separation = hip_rel - sh_rel  # hips ahead of shoulders is positive

    window_start = stride_start if stride_start is not None else swing_start
    seg = slice(window_start, contact + 1)
    hip_vel = _velocity(hip_rel, fps)
    sh_vel = _velocity(sh_rel, fps)
    hip_peak_frame = window_start + int(np.argmax(hip_vel[seg]))
    sh_peak_frame = window_start + int(np.argmax(sh_vel[seg]))
    max_sep = float(np.max(separation[seg]))

    # ---- Shoulder tilt (lead shoulder above rear is positive) -------------
    sv = wd[:, rear_sh] - wd[:, lead_sh]
    tilt = np.degrees(np.arctan2(sv[:, 1], np.hypot(sv[:, 0], sv[:, 2])))
    tilt_stance = float(np.median(tilt[ref]))
    tilt_contact = float(tilt[contact])

    # ---- Hand path / attack angle ----------------------------------------
    a, b = max(0, contact - 2), min(n - 1, contact + 1)
    dv = hands[b] - hands[a]
    attack_angle = math.degrees(math.atan2(-dv[1], abs(dv[0]) + 1e-9))
    path = hands[contact] - hands[swing_start]
    path_angle = math.degrees(math.atan2(-path[1], abs(path[0]) + 1e-9))

    # ---- Head movement ----------------------------------------------------
    head_move = float(np.linalg.norm(px[contact, NOSE] - np.median(px[ref, NOSE], axis=0)) / body_px)

    ms = 1000.0 / fps

    def dur(f0: int | None, f1: int | None) -> float | None:
        return (f1 - f0) * ms if f0 is not None and f1 is not None else None

    def inches(frac: float | None) -> float | None:
        return frac * hitter_height_in if (frac is not None and hitter_height_in) else None

    hand_speed_mph = peak_speed * height_m * MPS_TO_MPH if height_m else None

    metrics = [
        # Rotation
        _metric(
            "hip_rotation", "Hip rotation", float(hip_rel[contact]), "°", "rotation",
            "How far the hips turned from the stance to contact (estimated in 3D from the pose).",
        ),
        _metric(
            "shoulder_rotation", "Shoulder rotation", float(sh_rel[contact]), "°", "rotation",
            "How far the shoulders turned from the stance to contact.",
        ),
        _metric(
            "hip_shoulder_separation", "Hip-shoulder separation", max_sep, "°", "rotation",
            "Largest gap between hip and shoulder rotation during the swing — hips opening while "
            "the shoulders stay closed stores energy.",
        ),
        _metric(
            "peak_hip_velocity", "Peak hip rotation speed", float(hip_vel[hip_peak_frame]), "°/s",
            "rotation", "Fastest the hips rotated before contact.", digits=0,
        ),
        _metric(
            "hip_to_shoulder_timing", "Hips lead shoulders by", dur(hip_peak_frame, sh_peak_frame),
            "ms", "rotation",
            "Time between the hips' and shoulders' peak rotation speed. Positive means the hips "
            "fire first, the desired sequence.", digits=0,
        ),
        # Posture
        _metric(
            "shoulder_tilt_stance", "Shoulder tilt at stance", tilt_stance, "°", "posture",
            "Angle of the shoulder line in the stance. Positive = lead shoulder higher.",
        ),
        _metric(
            "shoulder_tilt_contact", "Shoulder tilt at contact", tilt_contact, "°", "posture",
            "Angle of the shoulder line at contact. Positive = lead shoulder higher (rear "
            "shoulder dropped under).",
        ),
        _metric(
            "head_movement", "Head movement", head_move * 100, "% height", "posture",
            "How far the head moved between the stance and contact, as a percentage of body "
            "height. Less movement usually means better pitch tracking.",
        ),
        # Bat path (via the hands)
        _metric(
            "launch_angle_est", "Launch angle (est.)", attack_angle, "°", "bat_path",
            "Estimated from the hands' direction of travel at contact (attack angle). Positive = "
            "swinging up. A true launch angle needs ball tracking, so treat this as a guide.",
        ),
        _metric(
            "swing_plane", "Hand path angle", path_angle, "°", "bat_path",
            "Overall direction of the hands from the start of the swing to contact. Negative = "
            "hands work down toward the ball.",
        ),
        _metric(
            "peak_hand_speed",
            "Peak hand speed",
            hand_speed_mph if hand_speed_mph is not None else peak_speed,
            "mph" if hand_speed_mph is not None else "body heights/s",
            "bat_path",
            "Fastest the hands moved (in the camera's view). Give the hitter's height to see mph.",
        ),
        # Stride
        _metric(
            "stride_length", "Stride length",
            inches(stride_frac) if hitter_height_in else stride_frac * 100,
            "in" if hitter_height_in else "% height", "stride",
            "How much wider the feet are at foot plant than in the stance.",
        ),
        _metric(
            "stance_width", "Stance width",
            inches(stance_width) if hitter_height_in else stance_width * 100,
            "in" if hitter_height_in else "% height", "stride",
            "Distance between the feet in the stance.",
        ),
        # Timing
        _metric(
            "stride_duration", "Stride duration", dur(stride_start, foot_plant), "ms", "timing",
            "From when the lead foot starts moving until it lands.", digits=0,
        ),
        _metric(
            "plant_to_contact", "Foot plant to contact", dur(foot_plant, contact), "ms", "timing",
            "From lead foot landing to contact.", digits=0,
        ),
        _metric(
            "swing_time", "Swing time", dur(swing_start, contact), "ms", "timing",
            "From when the hands start forward to contact.", digits=0,
        ),
    ]

    if stride_start is None:
        warnings.append("No clear stride was detected (the hitter may use a no-stride or toe-tap approach).")
    if fps < 60:
        warnings.append(
            f"The video is {fps:.0f} fps; timings are only accurate to about ±{ms:.0f} ms. "
            "Slow-motion (120/240 fps) video gives much better results."
        )
    coverage = float(tracked.mean())
    if coverage < 0.8:
        warnings.append(f"The hitter was only tracked in {coverage:.0%} of frames.")

    def t(frame: int | None) -> dict[str, Any] | None:
        return None if frame is None else {"frame": frame, "time_s": round(frame / fps, 3)}

    hand_trail = [[round(float(x / width), 4), round(float(y / height), 4)] for x, y in hands]

    def series(arr: np.ndarray, digits: int = 1) -> list[float]:
        return [round(float(v), digits) for v in arr]

    return {
        "bats": bats,
        "fps": fps,
        "hitter_height_in": hitter_height_in,
        "tracking_coverage": round(coverage, 3),
        "phases": {
            "stance": t(0),
            "stride_start": t(stride_start),
            "foot_plant": t(foot_plant),
            "swing_start": t(swing_start),
            "contact": t(contact),
        },
        "metrics": metrics,
        "series": {
            "hip_rotation": series(hip_rel),
            "shoulder_rotation": series(sh_rel),
            "separation": series(separation),
            "hand_speed": series(hand_speed, 2),
        },
        "hand_path": hand_trail,
        "warnings": warnings,
    }
