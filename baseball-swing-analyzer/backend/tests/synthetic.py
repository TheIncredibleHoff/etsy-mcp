"""Build a synthetic pose sequence for a right-handed swing with known mechanics."""

import math

import numpy as np

FPS = 120
N = 130
STRIDE = (20, 45)  # lead foot moves between these frames
HIP_TURN = (60, 90, 80.0)  # start, end, degrees
SHOULDER_TURN = (68, 94, 70.0)
SWING = (70, 90)  # hands start forward → contact


def _ramp(i, start, end):
    u = min(max((i - start) / (end - start), 0.0), 1.0)
    return u * u * (3 - 2 * u)  # smoothstep


def _accel(i, start, end):
    u = min(max((i - start) / (end - start), 0.0), 1.0)
    return u * u


def make_pose(stride_m=0.25, attack_up=True):
    frames = []
    for i in range(N):
        w = np.zeros((33, 3))
        w[0] = [0.0, -0.75, 0.0]  # nose

        def rotated(half_width, angle_deg, y):
            a = math.radians(angle_deg)
            dx, dz = half_width * math.cos(a), half_width * math.sin(a)
            # lead (left) side is toward -x
            return [-dx, y, -dz], [dx, y, dz]

        hip = HIP_TURN[2] * _ramp(i, HIP_TURN[0], HIP_TURN[1])
        sh = SHOULDER_TURN[2] * _ramp(i, SHOULDER_TURN[0], SHOULDER_TURN[1])
        w[23], w[24] = rotated(0.12, hip, 0.0)
        w[11], w[12] = rotated(0.18, sh, -0.5)

        lead_x = -0.2 - stride_m * _ramp(i, *STRIDE)
        w[27] = [lead_x, 0.85, 0.0]
        w[28] = [0.2, 0.85, 0.0]
        w[29] = [lead_x, 0.9, 0.0]
        w[30] = [0.2, 0.9, 0.0]

        start, contact = np.array([0.15, -0.45]), np.array([-0.4, -0.25])
        if i <= SWING[1]:
            hands = start + (contact - start) * _accel(i, *SWING)
        else:
            # Follow-through: keep going, decelerating, rising if attack_up.
            u = min((i - SWING[1]) / 20, 1.0)
            direction = np.array([-1.0, -0.3 if attack_up else 0.3])
            hands = contact + direction * 0.3 * (u - u * u / 2) * 2
        w[15] = [hands[0], hands[1], 0.0]
        w[16] = [hands[0] + 0.02, hands[1], 0.0]

        image = [[0.5 + p[0] * 0.25, 0.5 + p[1] * 0.25, p[2], 1.0] for p in w]
        frames.append({"image": image, "world": w.tolist()})
    return {"fps": FPS, "width": 1000, "height": 1000, "frame_count": N, "frames": frames}
