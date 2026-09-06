from datetime import date, datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from textual_plot import PlotWidget

from pomlock.constants import SessionKind
from pomlock.history_store import HistoryStore
from pomlock.settings import Settings
import pomlock.settings as settings_module
from pomlock.ui.app import PomlockApp
from pomlock.ui.screens.main_screen import MainScreen
from pomlock.ui.widgets.stats_chart_card import StatsChartCard
from textual.app import App, ComposeResult
from textual.widgets import Button


class TestStatsChartLogic(unittest.TestCase):
    """Test date boundaries, activity filtering, and week focus calculations."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_stats.db"
        self.store = HistoryStore(db_path=self.db_path)
        Settings.reset()

    def tearDown(self):
        self.temp_dir.cleanup()
        Settings.reset()

    def test_week_start_day_monday(self):
        ref_date = date(2026, 9, 5)
        label, days = self.store.get_weekly_focus_by_day(
            week_offset=0,
            week_start_day="monday",
            reference_date=ref_date,
        )

        self.assertEqual(len(days), 7)
        self.assertEqual(days[0][0], date(2026, 8, 31))
        self.assertEqual(days[6][0], date(2026, 9, 6))
        self.assertEqual(label, "31/8 - 6/9")

    def test_week_start_day_sunday(self):
        ref_date = date(2026, 9, 5)
        label, days = self.store.get_weekly_focus_by_day(
            week_offset=0,
            week_start_day="sunday",
            reference_date=ref_date,
        )

        self.assertEqual(len(days), 7)
        self.assertEqual(days[0][0], date(2026, 8, 30))
        self.assertEqual(days[6][0], date(2026, 9, 5))
        self.assertEqual(label, "30/8 - 5/9")

    def test_year_boundary_crossing(self):
        ref_date = date(2026, 1, 1)
        label, days = self.store.get_weekly_focus_by_day(
            week_offset=0,
            week_start_day="monday",
            reference_date=ref_date,
        )

        self.assertEqual(len(days), 7)
        self.assertEqual(days[0][0], date(2025, 12, 29))
        self.assertEqual(days[6][0], date(2026, 1, 4))
        self.assertEqual(label, "29/12 - 4/1")

    def test_week_offset_navigation(self):
        ref_date = date(2026, 9, 5)

        # Previous week (-1)
        _, prev_days = self.store.get_weekly_focus_by_day(
            week_offset=-1,
            week_start_day="monday",
            reference_date=ref_date,
        )
        self.assertEqual(prev_days[0][0], date(2026, 8, 24))
        self.assertEqual(prev_days[6][0], date(2026, 8, 30))

        # Next week (+1)
        _, next_days = self.store.get_weekly_focus_by_day(
            week_offset=1,
            week_start_day="monday",
            reference_date=ref_date,
        )
        self.assertEqual(next_days[0][0], date(2026, 9, 7))
        self.assertEqual(next_days[6][0], date(2026, 9, 13))

    def test_focus_logs_aggregated_and_breaks_ignored(self):
        b1 = self.store.start_block(
            activity="coding",
            kind=SessionKind.POMODORO,
            cycle=1,
            session=1,
            timestamp=datetime(2026, 9, 1, 10, 0).isoformat(),
        )
        self.store.update_block_duration(b1, duration_s=3600, completed=True)

        # 15m break (must be ignored)
        b2 = self.store.start_block(
            activity="coding",
            kind=SessionKind.SHORT_BREAK,
            cycle=1,
            session=1,
            timestamp=datetime(2026, 9, 1, 11, 0).isoformat(),
        )
        self.store.update_block_duration(b2, duration_s=900, completed=True)

        # 30m studying pomodoro
        b3 = self.store.start_block(
            activity="studying",
            kind=SessionKind.POMODORO,
            cycle=1,
            session=2,
            timestamp=datetime(2026, 9, 1, 14, 0).isoformat(),
        )
        self.store.update_block_duration(b3, duration_s=1800, completed=True)

        # 120m coding pomodoro
        b4 = self.store.start_block(
            activity="coding",
            kind=SessionKind.POMODORO,
            cycle=2,
            session=1,
            timestamp=datetime(2026, 9, 2, 9, 0).isoformat(),
        )
        self.store.update_block_duration(b4, duration_s=7200, completed=True)

        ref_date = date(2026, 9, 5)

        # Query all activities
        _, days_all = self.store.get_weekly_focus_by_day(
            week_offset=0,
            activity="all",
            week_start_day="monday",
            reference_date=ref_date,
        )
        self.assertEqual(days_all[1][1], 90)
        self.assertEqual(days_all[2][1], 120)

        # Query only coding
        _, days_coding = self.store.get_weekly_focus_by_day(
            week_offset=0,
            activity="coding",
            week_start_day="monday",
            reference_date=ref_date,
        )
        self.assertEqual(days_coding[1][1], 60)
        self.assertEqual(days_coding[2][1], 120)

        # Query only studying
        _, days_studying = self.store.get_weekly_focus_by_day(
            week_offset=0,
            activity="studying",
            week_start_day="monday",
            reference_date=ref_date,
        )
        self.assertEqual(days_studying[1][1], 30)
        self.assertEqual(days_studying[2][1], 0)


class TestStatsChartPlotWidget(unittest.IsolatedAsyncioTestCase):
    """Test PlotWidget integration and scaling within StatsChartCard."""

    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_pw.db"
        self.history_store = HistoryStore(db_path=self.db_path)
        Settings.reset()

    async def asyncTearDown(self):
        Settings.reset()
        self.temp_dir.cleanup()

    async def test_card_composes_plot_widget(self):
        class MockApp(App):
            def compose(self) -> ComposeResult:
                yield StatsChartCard()

        app = MockApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            card = app.query_one(StatsChartCard)
            plot = card.query_one(PlotWidget)
            self.assertIsNotNone(plot)

    async def test_relative_y_axis_scaling(self):
        # Insert 3h coding session
        b = self.history_store.start_block(
            activity="coding",
            kind=SessionKind.POMODORO,
            cycle=1,
            session=1,
            timestamp=datetime.now().isoformat(),
        )
        self.history_store.update_block_duration(b, duration_s=10800, completed=True)

        class MockApp(App):
            def __init__(self, store):
                super().__init__()
                self.history_store = store

            def compose(self) -> ComposeResult:
                yield StatsChartCard()

        app = MockApp(self.history_store)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            card = app.query_one(StatsChartCard)
            plot = card.query_one(PlotWidget)
            self.assertEqual(plot._user_y_max, 3.0)
            self.assertEqual(plot._user_y_min, 0.0)

    async def test_zero_focus_has_minimum_baseline(self):
        class MockApp(App):
            def __init__(self, store):
                super().__init__()
                self.history_store = store

            def compose(self) -> ComposeResult:
                yield StatsChartCard()

        app = MockApp(self.history_store)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            card = app.query_one(StatsChartCard)
            plot = card.query_one(PlotWidget)
            self.assertEqual(plot._user_y_max, 1.0)
            self.assertEqual(plot._user_y_min, 0.0)

    async def test_x_axis_displays_weekday_names(self):
        class MockApp(App):
            def __init__(self, store):
                super().__init__()
                self.history_store = store

            def compose(self) -> ComposeResult:
                yield StatsChartCard()

        app = MockApp(self.history_store)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            card = app.query_one(StatsChartCard)
            plot = card.query_one(PlotWidget)
            margin_bottom = plot.query_one("#margin-bottom")
            rendered = [margin_bottom.render_line(y).text for y in range(margin_bottom.size.height)]
            combined = " ".join(rendered)
            self.assertTrue(any(day in combined for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")))


class TestStatsChartAppIntegration(unittest.IsolatedAsyncioTestCase):
    """Test Textual UI interaction, button clicking, and 'a' shortcut."""

    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_app_stats.db"
        self.history_store = HistoryStore(db_path=self.db_path)

        self._conf_path = Path(self.temp_dir.name) / "test.conf"
        Settings.reset()
        self._conf_patcher = patch.object(settings_module, "DEFAULT_CONFIG_FILE", self._conf_path)
        self._conf_patcher.start()

    async def asyncTearDown(self):
        Settings.reset()
        self._conf_patcher.stop()
        self.temp_dir.cleanup()

    async def test_chart_activity_shortcut_and_navigation(self):
        app = PomlockApp(history_store=self.history_store)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            self.assertIsInstance(app.screen, MainScreen)

            chart_card = app.screen.query_one(StatsChartCard)
            self.assertEqual(chart_card._selected_activity, "all")

            # Press 'a' to cycle activity
            await pilot.press("a")
            await pilot.pause()
            self.assertNotEqual(chart_card._selected_activity, "all")

            # Press prev week button
            prev_btn = chart_card.query_one("#btn-chart-prev", Button)
            await pilot.click(prev_btn)
            await pilot.pause()
            self.assertEqual(chart_card._week_offset, -1)

            # Press next week button
            next_btn = chart_card.query_one("#btn-chart-next", Button)
            await pilot.click(next_btn)
            await pilot.pause()
            self.assertEqual(chart_card._week_offset, 0)


if __name__ == "__main__":
    unittest.main()
