from pathlib import Path

import pandas as pd

from dashboard import load_measurements


def test_load_measurements_reads_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "measurements.csv"
    csv_file.write_text(
        "timestamp,temperature,humidity,pressure\n"
        "2026-10-01T12:00:00+00:00,22.5,60.0,1012.4\n"
        "2026-10-01T12:05:00+00:00,23.1,58.8,1011.7\n",
        encoding="utf-8",
    )

    dataframe = load_measurements(csv_file)

    assert len(dataframe) == 2
    assert dataframe.iloc[-1]["temperature"] == 23.1
    assert dataframe.iloc[-1]["humidity"] == 58.8
    assert dataframe.iloc[-1]["pressure"] == 1011.7


def test_load_measurements_reads_supabase_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict]:
            return [
                {
                    "measured_at": "2026-10-01T12:00:00+00:00",
                    "temperature": 21.4,
                    "humidity": 63.1,
                    "pressure": 1013.8,
                }
            ]

    monkeypatch.setattr("dashboard.requests.get", lambda *args, **kwargs: FakeResponse())

    dataframe = load_measurements()

    assert isinstance(dataframe, pd.DataFrame)
    assert len(dataframe) == 1
    assert dataframe.iloc[0]["temperature"] == 21.4
    assert dataframe.iloc[0]["humidity"] == 63.1
    assert dataframe.iloc[0]["pressure"] == 1013.8
