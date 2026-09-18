import cv2
import numpy as np

SCOUTER_YELLOW = (0, 215, 255)  # BGR


def _triangle(frame, apex, base_top, base_bottom, color):
    pts = np.array([apex, base_top, base_bottom], dtype=int)
    cv2.fillPoly(frame, [pts], color)


def draw_scouter_overlay(frame, color=SCOUTER_YELLOW, alpha=1.0):
    h, w = frame.shape[:2]
    canvas = frame if alpha >= 1.0 else frame.copy()

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

    if alpha >= 1.0:
        return canvas
    return cv2.addWeighted(canvas, alpha, frame, 1 - alpha, 0)
