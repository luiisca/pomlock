import time
import tkinter as tk
import unittest

from pomlock.ui.break_overlay import BreakOverlayManager, detect_monitors, draw_vector_clock


class TestBreakOverlay(unittest.TestCase):
    def test_detect_monitors(self):
        monitors = detect_monitors()
        # Should return a list of tuples with 4 elements (w, h, x, y)
        self.assertIsInstance(monitors, list)
        for m in monitors:
            self.assertEqual(len(m), 4)

    def test_draw_vector_clock_centering(self):
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root, width=1920, height=1080)
            canvas.pack()
            target_cx, target_cy = 960.0, 540.0
            draw_vector_clock(canvas, "05:00", target_cx, target_cy)
            bbox = canvas.bbox("clock_digits")
            self.assertIsNotNone(bbox)
            min_x, min_y, max_x, max_y = bbox
            center_x = (min_x + max_x) / 2.0
            center_y = (min_y + max_y) / 2.0
            # Center of the rendered elements should match target (within 1px tolerance)
            self.assertAlmostEqual(center_x, target_cx, delta=1.0)
            self.assertAlmostEqual(center_y, target_cy, delta=1.0)
        finally:
            root.destroy()

    def test_overlay_lifecycle(self):
        overlay = BreakOverlayManager()
        self.assertFalse(overlay._is_active)

        # Start overlay
        overlay.start_overlay("Short break", 10, "#b48ead")
        self.assertTrue(overlay._is_active)
        self.assertIsNotNone(overlay._proc)

        # Send updates
        overlay.update_timer(9)
        overlay.update_timer(8)

        time.sleep(0.1)

        # Stop overlay
        overlay.stop_overlay()
        self.assertFalse(overlay._is_active)
        self.assertIsNone(overlay._proc)


if __name__ == "__main__":
    unittest.main()
