import cv2
import numpy as np

SCOUTER_YELLOW = (0, 215, 255)  # BGR


def _glyph_cluster(frame, cx, cy, scale, color):
    """외계 문자 느낌의 각진 사각형 묶음 (우상단/우하단 심볼)."""
    bars = [
        (-2.0, -1.5, 0.7, 2.2),
        (-0.9, -2.0, 0.5, 3.0),
        (0.2, -1.2, 1.4, 0.6),
        (0.2, 0.4, 0.6, 1.6),
        (1.1, -1.8, 0.5, 2.2),
    ]
    for dx, dy, bw, bh in bars:
        x1 = int(cx + dx * scale)
        y1 = int(cy + dy * scale)
        x2 = int(x1 + bw * scale)
        y2 = int(y1 + bh * scale)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)


def _circle_tail(frame, cx, cy, scale, color, thickness=3):
    """좌상단의 원 + 꼬리선 심볼."""
    r = int(scale * 1.1)
    cv2.circle(frame, (cx, cy), r, color, thickness)
    tail_end = (cx + int(scale * 1.8), cy + int(scale * 1.8))
    cv2.line(frame, (cx + r, cy), tail_end, color, thickness)
    cv2.circle(frame, tail_end, max(int(scale * 0.35), 2), color, -1)


def _triangle(frame, apex, base_top, base_bottom, color):
    pts = np.array([apex, base_top, base_bottom], dtype=int)
    cv2.fillPoly(frame, [pts], color)


def draw_scouter_overlay(frame, color=SCOUTER_YELLOW, alpha=1.0):
    """DBZ 스카우터 화면 속 노란 그래픽(원+꼬리, 외계문자 묶음, 마주보는 삼각형)을
    frame 위에 그려서 반환한다. alpha<1.0 이면 반투명하게 합성한다."""
    h, w = frame.shape[:2]
    scale = min(w, h) * 0.02

    canvas = frame if alpha >= 1.0 else frame.copy()

    # 좌측 상단: 원 + 꼬리 심볼
    _circle_tail(canvas, int(w * 0.14), int(h * 0.14), scale * 1.4, color)

    # 우측 상단: 외계 문자 느낌 묶음
    _glyph_cluster(canvas, int(w * 0.80), int(h * 0.15), scale, color)

    # 중앙 좌/우 대형 삼각형 (서로 마주보는 형태)
    mid_y = int(h * 0.5)
    tri_half = int(h * 0.13)

    _triangle(
        canvas,
        apex=(int(w * 0.30), mid_y),
        base_top=(int(w * 0.17), mid_y - tri_half),
        base_bottom=(int(w * 0.17), mid_y + tri_half),
        color=color,
    )
    _triangle(
        canvas,
        apex=(int(w * 0.70), mid_y),
        base_top=(int(w * 0.83), mid_y - tri_half),
        base_bottom=(int(w * 0.83), mid_y + tri_half),
        color=color,
    )

    # 우측 하단: 외계 문자 느낌 묶음 (2번째)
    _glyph_cluster(canvas, int(w * 0.80), int(h * 0.75), scale, color)

    if alpha >= 1.0:
        return canvas
    return cv2.addWeighted(canvas, alpha, frame, 1 - alpha, 0)
