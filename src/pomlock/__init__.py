import sys

from rich import print

from pomlock.constants import DEFAULT_LOG_FILE
from pomlock.settings import Settings

from .history_store import HistoryStore
from .instance_lock import InstanceLock, focus_terminal, read_status
from .logger import logger, setup_logging
from .ui.app import PomlockApp
from .utils import format_hm


def main() -> None:
    instance_lock = InstanceLock()
    if not instance_lock.acquire():
        if focus_terminal(instance_lock.owner_pid()):
            return

        status = read_status()
        print(f"Pomlock already running{f': {status}' if status else '.'}")
        return

    app = None

    try:
        setup_logging(DEFAULT_LOG_FILE, True)
        settings = Settings()

        if "--show-presets" in sys.argv:
            for name, value in settings.get("presets", {}).items():
                print(f"{name}: {value}")
            return

        if "--show-activities" in sys.argv:
            activities_config = settings.get("activities", {})
            for activity, goals in activities_config.items():
                if activity in ("auto_calc", "all", "total"):
                    continue
                if isinstance(goals, dict) and any(k != "color" for k in goals):
                    goals_str = ", ".join(
                        f"{period}={format_hm(value)}"
                        for period, value in goals.items()
                        if period != "color"
                    )
                    print(f"{activity} ({goals_str})")
                else:
                    print(activity)
            return

        # setup_logging(settings.get("log_file"), settings.get("verbose"))
        logger.debug(f"Config after loading: {settings}")

        history_store = HistoryStore()
        app = PomlockApp(history_store=history_store)
        app.run()
    except KeyboardInterrupt:
        logger.info("Exiting...")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
    finally:
        if app is not None:
            app.engine.cleanup()
        instance_lock.release()
        logger.info("Session ended")
