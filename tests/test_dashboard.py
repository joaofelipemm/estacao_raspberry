from pathlib import Path

import pandas as pd

from dashboard import get_supabase_settings, load_measurements


def test_get_supabase_settings_accepts_supabase_key_alias(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")

    assert get_supabase_settings() == ("https://example.supabase.co", "test-key")


def test_get_supabase_settings_prefers_publishable_key(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "publishable-test-key")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "old-anon-key")

    assert get_supabase_settings() == ("https://example.supabase.co", "publishable-test-key")


def test_load_measurements_reads_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "measurements.csv"
    csv_file.write_text(
        "timestamp,temperature,humidity,rain_accumulated\n"
        "2026-10-01T12:00:00+00:00,22.5,60.0,2.4\n"
        "2026-10-01T12:05:00+00:00,23.1,58.8,3.7\n",
        encoding="utf-8",
    )

    dataframe = load_measurements(csv_file)

    assert len(dataframe) == 2
    assert dataframe.iloc[-1]["temperature"] == 23.1
    assert dataframe.iloc[-1]["humidity"] == 58.8
    assert dataframe.iloc[-1]["rain_accumulated"] == 3.7


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
                    "rain_accumulated": 3.8,
                }
            ]

    monkeypatch.setattr("dashboard.requests.get", lambda *args, **kwargs: FakeResponse())

    dataframe = load_measurements()

    assert isinstance(dataframe, pd.DataFrame)
    assert len(dataframe) == 1
    assert dataframe.iloc[0]["temperature"] == 21.4
    assert dataframe.iloc[0]["humidity"] == 63.1
    assert dataframe.iloc[0]["rain_accumulated"] == 3.8


def test_load_measurements_does_not_treat_legacy_pressure_as_rain(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    csv_file = tmp_path / "legacy.csv"
    csv_file.write_text(
        "timestamp,temperature,humidity,pressure\n"
        "2026-10-01T12:00:00+00:00,22.5,60.0,1012.4\n",
        encoding="utf-8",
    )

    dataframe = load_measurements(csv_file)

    assert pd.isna(dataframe.iloc[0]["rain_accumulated"])
