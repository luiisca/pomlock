from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.widgets import Label


class LegendWidget(Vertical):
    """Activity legend box."""

    DEFAULT_CLASSES = "card-container legend-box"

    def compose(self) -> ComposeResult:
        yield Label("legend", classes="card-title")
        yield Label("■ sleep", classes="legend-item legend-sleep")
        yield Label("■ coding", classes="legend-item legend-coding")
        yield Label("■ studying", classes="legend-item legend-studying")


class TodayStatsWidget(Vertical):
    """Placeholder view for Today stats breakdowns."""

    DEFAULT_CLASSES = "stats-content-area"

    def compose(self) -> ComposeResult:
        yield Label("<< 16/8 >>", classes="date-range-header")

        with Grid(classes="today-stats-grid"):
            # Total activity bars
            with Vertical(classes="card-sub-box"):
                yield Label("total", classes="chart-sub-title")
                total_art = (
                    "6h │            \n"
                    "5h │            \n"
                    "4h │    █       \n"
                    "3h │ █  █     █ \n"
                    "2h │ █  █     █ \n"
                    "1h │ █  █  █  █ \n"
                    "───┴────────────\n"
                    "  slp cod std chn"
                )
                yield Label(total_art, classes="ascii-chart")

            # Sleep breakdown
            with Vertical(classes="card-sub-box"):
                yield Label("Sleep", classes="chart-sub-title")
                sleep_art = (
                    "1h  │       \n"
                    "54m │ █     \n"
                    "27m │ █  █  \n"
                    "0m  ┴───────\n"
                    "    0-6 6-12 12-18 18-24"
                )
                yield Label(sleep_art, classes="ascii-chart")

            # Coding breakdown
            with Vertical(classes="card-sub-box"):
                yield Label("coding", classes="chart-sub-title")
                cod_art = (
                    "1h  │       \n"
                    "54m │       \n"
                    "27m │    █  \n"
                    "0m  ┴───────\n"
                    "    0-6 6-12 12-18 18-24"
                )
                yield Label(cod_art, classes="ascii-chart")

            # Studying breakdown
            with Vertical(classes="card-sub-box"):
                yield Label("studying", classes="chart-sub-title")
                std_art = (
                    "1h  │       \n"
                    "54m │       \n"
                    "27m │    █  \n"
                    "0m  ┴───────\n"
                    "    0-6 6-12 12-18 18-24"
                )
                yield Label(std_art, classes="ascii-chart")


class WeekStatsWidget(Vertical):
    """Placeholder view for This Week stats view."""

    DEFAULT_CLASSES = "stats-content-area"

    def compose(self) -> ComposeResult:
        yield Label("<< 10/8 - 16/8 >>", classes="date-range-header")

        with Horizontal(classes="week-top-row"):
            # Stacked daily bars
            with Vertical(classes="card-sub-box week-bar-col"):
                yield Label("this week", classes="chart-sub-title")
                week_art = (
                    "6h │                  █     \n"
                    "5h │      █           █     \n"
                    "4h │  █   █       █   █     \n"
                    "3h │  █   █   █   █   █     \n"
                    "2h │  █   █   █   █   █     \n"
                    "1h │  █   █   █   █   █   █ \n"
                    "───┴────────────────────────\n"
                    "     10  11  12  13  14  15 16"
                )
                yield Label(week_art, classes="ascii-chart")

            # Focus history matrix
            with Vertical(classes="card-sub-box week-history-col"):
                yield Label("focus history", classes="chart-sub-title")
                hist_art = (
                    "S │ █                                  \n"
                    "S │       █                            \n"
                    "F │                                    \n"
                    "T │             ████                   \n"
                    "W │                                    \n"
                    "T │                                    \n"
                    "M │       ████            ██           \n"
                    "──┴────────────────────────────────────\n"
                    "  0       6       12      18      24   "
                )
                yield Label(hist_art, classes="ascii-chart")

        with Horizontal(classes="week-bottom-row"):
            # Average focus breakdown
            with Vertical(classes="card-sub-box avg-focus-col"):
                yield Label("avg focus breakdown", classes="chart-sub-title")
                avg_art = (
                    "1h  │ █       █ \n"
                    "54m │ █       █ \n"
                    "27m │ █   █   █ \n"
                    "0m  ┴───────────\n"
                    "     0-6 6-12 12-18 18-24"
                )
                yield Label(avg_art, classes="ascii-chart")

            yield LegendWidget()


class MonthStatsWidget(Vertical):
    """Placeholder view for This Month stats view."""

    DEFAULT_CLASSES = "stats-content-area"

    def compose(self) -> ComposeResult:
        yield Label("<< 08/26 >>", classes="date-range-header")

        # Weekly aggregated bars
        month_bars = (
            "6h │   █   █   █   █   █   █   █   █   █   █   █   █   █   █\n"
            "4h │ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █\n"
            "2h │ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █\n"
            "───┴────────────────────────────────────────────────────────\n"
            "    10  11  12  13  14  15  16  10  11  12  13  14  15  16"
        )
        yield Label(month_bars, classes="ascii-chart")

        with Horizontal(classes="month-bottom-row"):
            with Vertical(classes="card-sub-box"):
                yield Label("avg focus breakdown", classes="chart-sub-title")
                avg_art = (
                    "1h  │ █       █ \n"
                    "54m │ █       █ \n"
                    "27m │ █   █   █ \n"
                    "0m  ┴───────────\n"
                    "     0-6 6-12 12-18 18-24"
                )
                yield Label(avg_art, classes="ascii-chart")

            # Calendar matrix
            with Vertical(classes="card-sub-box cal-matrix-box"):
                yield Label("Mon  Tue  Wed  Thu  Fri  Sat  Sun", classes="cal-header")
                cal_table = (
                    "                 13   14   15 \n"
                    " 16   17   18   19   20   21   22 \n"
                    " 23   24   25   26   27   28   29 \n"
                    " 30   31    1    2    3    4    5 \n"
                    "  6    7    8    9   10  [27]  28 "
                )
                yield Label(cal_table, classes="cal-body")

            yield LegendWidget()


class YearStatsWidget(Vertical):
    """Placeholder view for This Year stats view."""

    DEFAULT_CLASSES = "stats-content-area"

    def compose(self) -> ComposeResult:
        yield Label("<< 2026 >>", classes="date-range-header")

        # Yearly waves / sparklines
        year_art = (
            "5h │    /\\       /\\         /\\       /\\      /\\     \n"
            "   │   /  \\     /  \\       /  \\     /  \\    /  \\    \n"
            "2h │  /    \\_  /    \\_    /    \\_  /    \\__/    \\_  \n"
            "0m └──┴──────┴─┴──────┴───┴──────┴─┴──────────────┴─\n"
            "     jan  feb mar  apr may jun  jul aug sep oct nov dec"
        )
        yield Label(year_art, classes="ascii-chart")

        with Horizontal(classes="year-bottom-row"):
            with Vertical(classes="card-sub-box"):
                yield Label("avg focus breakdown", classes="chart-sub-title")
                avg_art = (
                    "1h  │ █       █ \n"
                    "54m │ █       █ \n"
                    "27m │ █   █   █ \n"
                    "0m  ┴───────────\n"
                    "     0-6 6-12 12-18 18-24"
                )
                yield Label(avg_art, classes="ascii-chart")

            yield LegendWidget()
