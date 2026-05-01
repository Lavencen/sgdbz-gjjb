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

    if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
        return False, None

    channel_std = np.std(template.reshape(-1, template.shape[2]), axis=0)
    if bool(np.all(channel_std == 0.0)):
        return _match_flat_template(screen, template, threshold)

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= threshold:
        h, w = template.shape[:2]
        center = (max_loc[0] + w // 2, max_loc[1] + h // 2)
        return True, center
    return False, None


def _match_flat_template(
    screen,
    template,
    threshold: float,
) -> tuple[bool, tuple[int, int] | None]:
    result = cv2.matchTemplate(screen, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)
    score = 1.0 - min_val
    if score >= threshold:
        h, w = template.shape[:2]
        center = (min_loc[0] + w // 2, min_loc[1] + h // 2)
        return True, center
    return False, None
