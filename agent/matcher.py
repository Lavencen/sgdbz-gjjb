from pathlib import Path

import cv2
import numpy as np


def match_template(
    screenshot_path: Path,
    template_path: Path,
    threshold: float = 0.85,
) -> tuple[bool, tuple[int, int] | None]:
    screen = cv2.imread(str(screenshot_path))
    template = cv2.imread(str(template_path))

    if screen is None or template is None:
        return False, None

    if template.shape[0] <= screen.shape[0] and template.shape[1] <= screen.shape[1]:
        score, center = _score_template(screen, template)
        if score >= threshold:
            return True, center

    best = (float("-inf"), None, None)
    for scale in (0.75, 0.85, 0.95, 1.05, 1.15, 1.25, 1.3, 1.35, 1.4, 1.5):
        candidate = _resize_template(template, scale)
        if candidate.shape[0] > screen.shape[0] or candidate.shape[1] > screen.shape[1]:
            continue

        score, center = _score_template(screen, candidate)
        if score > best[0]:
            best = (score, center, scale)

    if best[0] >= threshold:
        return True, best[1]
    return False, None


def _resize_template(template, scale: float):
    if scale == 1.0:
        return template
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    return cv2.resize(template, None, fx=scale, fy=scale, interpolation=interpolation)


def _score_template(screen, template) -> tuple[float, tuple[int, int]]:
    channel_std = np.std(template.reshape(-1, template.shape[2]), axis=0)
    if bool(np.all(channel_std == 0.0)):
        return _score_flat_template(screen, template)

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    h, w = template.shape[:2]
    center = (max_loc[0] + w // 2, max_loc[1] + h // 2)
    return float(max_val), center


def _score_flat_template(screen, template) -> tuple[float, tuple[int, int]]:
    result = cv2.matchTemplate(screen, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)
    score = 1.0 - min_val
    h, w = template.shape[:2]
    center = (min_loc[0] + w // 2, min_loc[1] + h // 2)
    return float(score), center
