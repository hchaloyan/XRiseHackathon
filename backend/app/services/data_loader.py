"""Load generated JSON into DataFrames once at startup, cache in module state."""

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.config import settings

TABLES = ("machines", "production_runs", "downtime_events", "quality_events", "inventory")


def _shift(ts: pd.Series) -> pd.Series:
    """Shift A starts 06:00, shift B starts 14:00 (seed.py SHIFT_START_HOUR)."""
    return pd.Series(["A" if h < 14 else "B" for h in ts.dt.hour], index=ts.index)


@lru_cache(maxsize=1)
def load() -> dict[str, pd.DataFrame]:
    """Every table as a DataFrame. Cached: the files never change at runtime."""
    data_dir = Path(settings.data_dir)
    frames = {
        # Not read_json: it coerces `ideal_cycle_time` (a float, but the name
        # ends in _time) into epoch datetimes.
        name: pd.DataFrame(json.loads((data_dir / f"{name}.json").read_text(encoding="utf-8")))
        for name in TABLES
    }

    for name, column in (("production_runs", "start"), ("downtime_events", "start"),
                         ("quality_events", "timestamp")):
        df = frames[name]
        df[column] = pd.to_datetime(df[column])
        df["day"] = df[column].dt.date
        df["shift"] = _shift(df[column])

    frames["downtime_events"]["end"] = pd.to_datetime(frames["downtime_events"]["end"])
    frames["downtime_events"]["duration_minutes"] = (
        frames["downtime_events"]["end"] - frames["downtime_events"]["start"]
    ).dt.total_seconds() / 60
    frames["production_runs"]["end"] = pd.to_datetime(frames["production_runs"]["end"])

    return frames
