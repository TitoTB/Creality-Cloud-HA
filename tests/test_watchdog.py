"""Tests for automatic recovery rules."""

from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "creality_cloud"
    / "watchdog.py"
)
SPEC = importlib.util.spec_from_file_location("creality_cloud_watchdog", MODULE_PATH)
watchdog = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(watchdog)


NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


class WatchdogTest(unittest.TestCase):
    def test_requires_two_missed_slots(self):
        data = state_with_slots("11:30", "11:50")
        missed = watchdog.missed_schedule_slots(data, NOW, timedelta(minutes=5))
        self.assertEqual([item["id"] for item in missed], ["slot-1", "slot-2"])

        data = state_with_slots("11:50")
        self.assertEqual(
            len(watchdog.missed_schedule_slots(data, NOW, timedelta(minutes=5))),
            1,
        )

    def test_later_execution_proves_the_scheduler_recovered(self):
        data = state_with_slots("11:20", "11:40")
        data["tasks"] = {
            "downloads": {"lastRunAt": "2026-10-11T11:45:00+00:00"}
        }
        self.assertEqual(
            watchdog.missed_schedule_slots(data, NOW, timedelta(minutes=5)), []
        )

    def test_replanned_future_slots_are_not_missed(self):
        data = state_with_slots("12:10", "12:30")
        self.assertEqual(
            watchdog.missed_schedule_slots(data, NOW, timedelta(minutes=5)), []
        )

    def test_valid_long_running_print_is_not_missed(self):
        data = state_with_slots("10:00", "10:30")
        data["scheduler"] = {
            "running": True,
            "runningTask": "print",
            "stale": False,
            "browserMode": "automation",
        }
        self.assertEqual(
            watchdog.missed_schedule_slots(data, NOW, timedelta(minutes=5)), []
        )

    def test_pause_and_interactive_login_suspend_monitoring(self):
        paused = state_with_slots("10:00", "10:30")
        paused["health"] = {
            "state": "paused",
            "pausedUntil": "2026-10-11T13:00:00+00:00",
        }
        self.assertEqual(
            watchdog.missed_schedule_slots(paused, NOW, timedelta(minutes=5)), []
        )

        interactive = state_with_slots("10:00", "10:30")
        interactive["scheduler"]["browserMode"] = "interactive"
        self.assertEqual(
            watchdog.missed_schedule_slots(interactive, NOW, timedelta(minutes=5)),
            [],
        )

    def test_stale_period_starts_at_scheduler_timeout(self):
        data = state_with_slots()
        data["scheduler"].update(
            {
                "running": True,
                "stale": True,
                "runningTask": "downloads",
                "startedAt": "2026-10-11T11:00:00+00:00",
                "timeoutAt": "2026-10-11T11:30:00+00:00",
            }
        )
        self.assertEqual(watchdog.stale_started_at(data, NOW).minute, 30)
        self.assertEqual(
            NOW - watchdog.stale_started_at(data, NOW), timedelta(minutes=30)
        )

    def test_restart_window_ignores_old_attempts(self):
        recent = watchdog.recent_restarts(
            [
                "2026-10-10T11:59:00+00:00",
                "2026-10-11T10:00:00+00:00",
                "invalid",
            ],
            NOW,
            timedelta(hours=24),
        )
        self.assertEqual(recent, [datetime(2026, 10, 11, 10, 0, tzinfo=UTC)])


def state_with_slots(*times: str):
    return {
        "health": {"state": "active", "pausedUntil": ""},
        "scheduler": {
            "running": False,
            "stale": False,
            "browserMode": "idle",
        },
        "tasks": {},
        "printers": [],
        "schedule": {
            "revision": "revision",
            "pending": [
                {
                    "id": f"slot-{index}",
                    "task": "downloads",
                    "plannedAt": f"2026-10-11T{value}:00+00:00",
                }
                for index, value in enumerate(times, start=1)
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
