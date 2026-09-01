import datetime

test = datetime.date(2026, 10, 15).fromisoformat("2026-10-15")


def render_week() -> None:
    week_start_day = 0  # Monday
    try:
        # First, try to use the provided settings
        week_start_day_str = "monday"
        # Map string to day number (Monday=0, Sunday=6)
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
    except Exception:
        week_start_day = 0

    # Get the reference date (today or the one passed in)
    ref_date = date.today()
    # Calculate the start of the week (the week_start_day)
    days_to_subtract = (ref_date.weekday() - week_start_day) % 7
    week_start = ref_date - timedelta(days=days_to_subtract)

    # Generate the week days (from week_start to week_start + 6 days)
    days = []
    for i in range(7):
        current_day = week_start + timedelta(days=i)
        day_name = current_day.strftime("%a")  # Mon, Tue, etc.
        # Determine if the day is done, missed, or pending
        if current_day > date.today():
            # Future day: pending
            icon = "·"
            status_class = "status-pending"
        else:
            # Past or today: check if goals are met
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
            if all_goals_met:
                icon = "✓"
                status_class = "status-done"
            else:
                icon = "✗"
                status_class = "status-miss"
        days.append((day_name, icon, status_class))
    print(days)


if __name__ == "__main__":
    render_week()
