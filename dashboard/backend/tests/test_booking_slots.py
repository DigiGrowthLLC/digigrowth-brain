"""Unit tests for booking_engine.compute_days (the pure slot math).
Run: python -m pytest dashboard/backend/tests/test_booking_slots.py
  or: python dashboard/backend/tests/test_booking_slots.py"""
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from booking_engine import compute_days  # noqa: E402

DEN = ZoneInfo("America/Denver")
EV = dict(duration_min=60, slot_interval_min=30, buffer_before_min=0, buffer_after_min=0, daily_cap=None)
PAST = datetime(2000, 1, 1, tzinfo=timezone.utc)


def hours(*blocks):
    return [{"weekday": wd, "start_time": time.fromisoformat(s), "end_time": time.fromisoformat(e)} for wd, s, e in blocks]


def utc(d, hhmm, tz=DEN):
    return datetime.combine(d, time.fromisoformat(hhmm), tzinfo=tz).astimezone(timezone.utc)


def z(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


MON = date(2026, 11, 9)  # a Monday


def run(ev=EV, hrs=None, overrides=None, busy=(), counts=None, first=MON, last=MON, earliest=PAST):
    return compute_days({**EV, **ev}, hrs if hrs is not None else hours((0, "09:00", "12:00")),
                        overrides or {}, list(busy), counts or {}, DEN, first, last, earliest)


def test_basic_grid():
    d = run()[0]
    assert d["slots"] == [z(utc(MON, t)) for t in ("09:00", "09:30", "10:00", "10:30", "11:00")]


def test_busy_blocks_overlap_only():
    busy = [(utc(MON, "10:00"), utc(MON, "10:30"))]
    slots = run(busy=busy)[0]["slots"]
    assert z(utc(MON, "09:30")) not in slots and z(utc(MON, "10:00")) not in slots
    assert z(utc(MON, "09:00")) in slots and z(utc(MON, "10:30")) in slots


def test_buffers():
    busy = [(utc(MON, "11:00"), utc(MON, "11:30"))]
    slots = run(ev={"buffer_after_min": 15}, busy=busy)[0]["slots"]
    assert z(utc(MON, "10:00")) not in slots  # 10-11 + 15 min buffer hits 11:00
    assert z(utc(MON, "09:30")) in slots


def test_min_notice():
    slots = run(earliest=utc(MON, "10:15"))[0]["slots"]
    assert slots == [z(utc(MON, "10:30")), z(utc(MON, "11:00"))]


def test_daily_cap():
    assert run(ev={"daily_cap": 2}, counts={MON: 2})[0]["slots"] == []
    assert run(ev={"daily_cap": 2}, counts={MON: 1})[0]["slots"]


def test_override_closed_and_custom():
    assert run(overrides={MON: [{"closed": True, "start_time": None, "end_time": None}]})[0]["slots"] == []
    custom = run(overrides={MON: [{"closed": False, "start_time": time(14), "end_time": time(15)}]})[0]["slots"]
    assert custom == [z(utc(MON, "14:00"))]


def test_weekday_mapping_and_multi_day():
    days = run(hrs=hours((1, "09:00", "10:00")), last=MON + timedelta(days=1))
    assert days[0]["slots"] == [] and days[1]["slots"] == [z(utc(MON + timedelta(days=1), "09:00"))]


def test_dst_fall_back_keeps_local_times():
    sun = date(2026, 11, 1)  # US DST ends this Sunday
    days = compute_days(EV, hours((6, "09:00", "10:00")), {}, [], {}, DEN, sun, sun, PAST)
    assert days[0]["slots"] == ["2026-11-01T16:00:00Z"]  # 9:00 MST = 16:00 UTC (was 15:00 the day before)


def test_dst_spring_forward():
    sun = date(2026, 3, 8)
    days = compute_days(EV, hours((6, "09:00", "10:00")), {}, [], {}, DEN, sun, sun, PAST)
    assert days[0]["slots"] == ["2026-03-08T15:00:00Z"]  # 9:00 MDT


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("pass", name)
