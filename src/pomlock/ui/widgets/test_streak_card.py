import datetime as dt

test = datetime.date(2026, 10, 15).fromisoformat("2026-10-15")


def render_week() -> None:
    week_start_day_str = "monday"
    day_map = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    week_start_day = day_map.get(week_start_day_str, 0)

    ref_date = dt.datetime.now()
    days_to_subtract = (ref_date.weekday() - week_start_day) % 7
    week_start = ref_date - timedelta(days=days_to_subtract)

    days = []
    for i in range(7):
        current_day = week_start + timedelta(days=i)
        day_name = current_day.strftime("%a")  # Mon, Tue, etc.
        # Determine if the day is done, missed, or pending
        # Determine logical status (done, miss, pending)
        if current_day > date.today():
            logical_status = "pending"
        else:
            focus_by_activity = self._history_store.get_period_focus_by_activity(
                period=GoalPeriod.DAILY, target_date=current_day
            )
            activities = self._history_store.get_activities()
            all_goals_met = True
            for act in activities:
                daily_goal = act.get("daily_goal", 0)
                if daily_goal > 0:
                    activity_name = act.get("name", "").lower()
                    focused_minutes = focus_by_activity.get(activity_name, 0)
                    if focused_minutes < daily_goal:
                        all_goals_met = False
                        break
            logical_status = "done" if all_goals_met else "miss"
        # Map logical_status to visual icon based on user setting from current settings
        style = current_settings.get("streak_indicator_style", "icon")
        if style == "color-box":
            if logical_status == "done":
                icon = "🟩"
                status_class = "status-done"
            elif logical_status == "miss":
                icon = "🟥"
                status_class = "status-miss"
            else:
                icon = "⬜"
                status_class = "status-pending"
        else:
            if logical_status == "done":
                icon = "✓"
                status_class = "status-done"
            elif logical_status == "miss":
                icon = "✗"
                status_class = "status-miss"
            else:
                icon = "·"
                status_class = "status-pending"
        days.append((day_name, icon, status_class))

    # Week day check indicators
    # Calculate current streak (consecutive done days up to today, respecting gap allowance)
    streak_count = self._calculate_streak_count(days)
    print(streak_count)


if __name__ == "__main__":
    render_week()
