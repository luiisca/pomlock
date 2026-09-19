import time
from pomlock.settings import Settings
from pomlock.timer_engine import TimerEngine
from pomlock.history_store import HistoryStore

class DummyHistoryStore:
    def start_block(self, activity, kind, cycle, session):
        return f"block-{activity}-{kind}-{cycle}-{session}"
    def update_block_duration(self, block_id, duration_s, completed):
        print(f"update_block_duration: {block_id} duration={duration_s} completed={completed}")
    def __getattr__(self, name):
        return lambda *args, **kwargs: None

def on_tick(remaining_s, progress_pct):
    print(f"tick: remaining={remaining_s} progress={progress_pct}")

def on_phase_change(kind, duration_m):
    print(f"phase_change: kind={kind} duration_m={duration_m}")

settings = Settings()
history = DummyHistoryStore()
engine = TimerEngine(history_store=history, on_tick=on_tick, on_phase_change=on_phase_change)
engine.start()
print("Initial state:")
print(f"  kind={engine.kind} state={engine.state} elapsed_s={engine.elapsed_s} duration_s={engine.duration_s}")
print(f"  remaining_s={engine.remaining_s}")

# Simulate a skip from focus to break
print("\nCalling skip(force=True)")
engine.skip(force=True)
print(f"After skip:")
print(f"  kind={engine.kind} state={engine.state} elapsed_s={engine.elapsed_s} duration_s={engine.duration_s}")
print(f"  remaining_s={engine.remaining_s}")

# Let time advance a bit to see if tick triggers interval end
print("\nSimulating tick after 0.1s")
time.sleep(0.1)
engine.tick()
print(f"After tick:")
print(f"  kind={engine.kind} state={engine.state} elapsed_s={engine.elapsed_s} duration_s={engine.duration_s}")
print(f"  remaining_s={engine.remaining_s}")

# Let time advance to exceed duration (should not happen quickly)
print("\nSimulating tick after 20 seconds (fast forward)")
engine.elapsed_s = engine.duration_s - 1.0  # 1 second before end
engine.tick()
print(f"After tick (near end):")
print(f"  kind={engine.kind} state={engine.state} elapsed_s={engine.elapsed_s} duration_s={engine.duration_s}")
print(f"  remaining_s={engine.remaining_s}")

# Now tick to exceed
engine.elapsed_s = engine.duration_s + 1.0
engine.tick()
print(f"After tick (exceeded):")
print(f"  kind={engine.kind} state={engine.state} elapsed_s={engine.elapsed_s} duration_s={engine.duration_s}")
print(f"  remaining_s={engine.remaining_s}")
