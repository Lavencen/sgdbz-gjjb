import inspect
import tempfile
from pathlib import Path

import cv2
import numpy as np

from agent.matcher import match_template


class TestMatchTemplate:
    def test_exact_match_returns_true(self):
        screen = np.zeros((600, 800, 3), dtype=np.uint8)
        screen[:] = (128, 128, 128)
        template = np.zeros((50, 50, 3), dtype=np.uint8)
        template[:] = (255, 0, 0)
        x, y = 100, 200
        screen[y : y + 50, x : x + 50] = template

        screen_path = Path(tempfile.gettempdir()) / "test_screen.png"
        tmpl_path = Path(tempfile.gettempdir()) / "test_tmpl.png"
        cv2.imwrite(str(screen_path), screen)
        cv2.imwrite(str(tmpl_path), template)
        try:
            matched, center = match_template(screen_path, tmpl_path, threshold=0.9)
            assert matched is True
            assert center is not None
            cx, cy = center
            assert abs(cx - (x + 25)) < 5
            assert abs(cy - (y + 25)) < 5
        finally:
            screen_path.unlink(missing_ok=True)
            tmpl_path.unlink(missing_ok=True)

    def test_no_match_returns_false(self):
        screen = np.zeros((600, 800, 3), dtype=np.uint8)
        screen[:] = (128, 128, 128)
        template = np.zeros((50, 50, 3), dtype=np.uint8)
        template[:] = (255, 0, 0)

        screen_path = Path(tempfile.gettempdir()) / "test_screen2.png"
        tmpl_path = Path(tempfile.gettempdir()) / "test_tmpl2.png"
        cv2.imwrite(str(screen_path), screen)
        cv2.imwrite(str(tmpl_path), template)
        try:
            matched, center = match_template(screen_path, tmpl_path, threshold=0.9)
            assert matched is False
            assert center is None
        finally:
            screen_path.unlink(missing_ok=True)
            tmpl_path.unlink(missing_ok=True)

    def test_default_threshold_is_0_85(self):
        sig = inspect.signature(match_template)
        assert sig.parameters["threshold"].default == 0.85

    def test_nonexistent_images_return_false(self):
        matched, center = match_template(
            Path("/nonexistent/screen.png"),
            Path("/nonexistent/tmpl.png"),
        )
        assert matched is False
        assert center is None

    def test_scaled_template_returns_true(self):
        screen = np.zeros((600, 800, 3), dtype=np.uint8)
        screen[:] = (128, 128, 128)
        template = np.zeros((40, 40, 3), dtype=np.uint8)
        template[:] = (255, 0, 0)
        cv2.circle(template, (20, 20), 10, (0, 255, 0), -1)
        scaled = cv2.resize(template, None, fx=1.35, fy=1.35, interpolation=cv2.INTER_CUBIC)
        x, y = 500, 300
        h, w = scaled.shape[:2]
        screen[y : y + h, x : x + w] = scaled

        screen_path = Path(tempfile.gettempdir()) / "test_scaled_screen.png"
        tmpl_path = Path(tempfile.gettempdir()) / "test_scaled_tmpl.png"
        cv2.imwrite(str(screen_path), screen)
        cv2.imwrite(str(tmpl_path), template)
        try:
            matched, center = match_template(screen_path, tmpl_path, threshold=0.9)
            assert matched is True
            assert center is not None
            cx, cy = center
            assert abs(cx - (x + w // 2)) < 5
            assert abs(cy - (y + h // 2)) < 5
        finally:
            screen_path.unlink(missing_ok=True)
            tmpl_path.unlink(missing_ok=True)

    def test_locate_template_returns_confidence_and_center(self):
        from agent.matcher import locate_template

        screen = np.zeros((600, 800, 3), dtype=np.uint8)
        screen[:] = (128, 128, 128)
        template = np.zeros((40, 40, 3), dtype=np.uint8)
        template[:] = (255, 0, 0)
        cv2.circle(template, (20, 20), 10, (0, 255, 0), -1)
        x, y = 320, 240
        screen[y : y + 40, x : x + 40] = template

        screen_path = Path(tempfile.gettempdir()) / "test_locate_screen.png"
        tmpl_path = Path(tempfile.gettempdir()) / "test_locate_tmpl.png"
        cv2.imwrite(str(screen_path), screen)
        cv2.imwrite(str(tmpl_path), template)
        try:
            result = locate_template(screen_path, tmpl_path, threshold=0.9)
            assert result.matched is True
            assert result.center is not None
            assert result.confidence >= 0.9
            assert abs(result.center[0] - (x + 20)) < 5
            assert abs(result.center[1] - (y + 20)) < 5
        finally:
            screen_path.unlink(missing_ok=True)
            tmpl_path.unlink(missing_ok=True)

    def test_locate_template_reports_best_unmatched_confidence(self, monkeypatch):
        from agent import matcher

        screen = np.zeros((20, 20, 3), dtype=np.uint8)
        template = np.zeros((4, 4, 3), dtype=np.uint8)
        screen_path = Path(tempfile.gettempdir()) / "test_best_conf_screen.png"
        tmpl_path = Path(tempfile.gettempdir()) / "test_best_conf_tmpl.png"
        cv2.imwrite(str(screen_path), screen)
        cv2.imwrite(str(tmpl_path), template)

        scores = iter([(0.8, (2, 2)), (0.5, (3, 3))])

        def fake_score_template(screen_image, template_image):
            try:
                return next(scores)
            except StopIteration:
                return 0.5, (3, 3)

        monkeypatch.setattr(matcher, "_score_template", fake_score_template)
        try:
            result = matcher.locate_template(screen_path, tmpl_path, threshold=0.9)
            assert result.matched is False
            assert result.confidence == 0.8
            assert result.scale == 1.0
        finally:
            screen_path.unlink(missing_ok=True)
            tmpl_path.unlink(missing_ok=True)
