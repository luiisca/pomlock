import unittest

from pomlock.ui.widgets.timer_card import ThickProgressBar, TimerCard, render_digital_clock
from textual.app import App, ComposeResult


class TimerCardTestApp(App):
    def compose(self) -> ComposeResult:
        yield TimerCard(activity="coding", cycles_total=4)


class TestTimerCard(unittest.IsolatedAsyncioTestCase):
    def test_render_digital_clock_format(self):
        rendered = render_digital_clock("25:00")
        lines = rendered.splitlines()
        self.assertEqual(len(lines), 5)
        # Verify block characters are present
        self.assertTrue(any("█" in line for line in lines))

    def test_thick_progress_bar_render(self):
        bar = ThickProgressBar(progress=0.5)
        rendered = bar.render()
        self.assertTrue(len(rendered.plain) > 0)
        self.assertIn("█", rendered.plain)

    async def test_timer_card_update_state(self):
        app = TimerCardTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            card = app.query_one(TimerCard)
            pb = app.query_one(ThickProgressBar)
            self.assertIsNotNone(card)

            # Update focus state with float durations
            card.update_state(
                remaining_s=1500,
                progress_pct=0.5,
                cycle=2,
                total_cycles=4,
                pomo_m=25.0,
                break_m=5.0,
                is_break=False,
                is_running=True,
                kind_label="Pomodoro",
            )
            await pilot.pause()

            self.assertEqual(pb.progress, 0.5)
            next_lbl = card.query_one("#timer-next-phase")
            self.assertIn("next: 05:00 break", str(next_lbl.render()))

            # Update break state with sub-minute float duration (test preset 10s)
            card.update_state(
                remaining_s=5,
                progress_pct=0.8,
                cycle=2,
                total_cycles=4,
                pomo_m=0.166667,
                break_m=0.166667,
                is_break=True,
                is_running=True,
                kind_label="Short Break",
            )
            await pilot.pause()

            self.assertEqual(pb.progress, 0.8)
            next_lbl = card.query_one("#timer-next-phase")
            self.assertIn("next: 00:10 focus", str(next_lbl.render()))


if __name__ == "__main__":
    unittest.main()
