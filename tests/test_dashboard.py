from pathlib import Path

import pandas as pd
import pytest
import requests

from dashboard import (
    fetch_supabase_measurements,
    format_metric_delta,
    get_supabase_settings,
    load_measurements,
    prepare_daily_history,
    prepare_latest_day_measurements,
    prepare_monthly_rainfall,
)


def test_format_metric_delta_compares_with_previous_reading() -> None:
    assert format_metric_delta(23.5, 22.0, "°C") == "+1.50 °C"
    assert format_metric_delta(58.0, 60.0, "%") == "-2.00 %"
    assert format_metric_delta(1.2, None, "mm") is None
    assert format_metric_delta(float("nan"), 1.0, "mm") is None


def test_prepare_latest_day_measurements_keeps_only_latest_date() -> None:
    measurements = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-10-23T23:55:00+00:00",
                    "2026-10-24T03:00:00+00:00",
                    "2026-10-24T23:55:00+00:00",
                ]
            ),
            "temperature": [20.0, 21.0, 22.0],
            "humidity": [55.0, 60.0, 65.0],
        }
    )

    latest_day = prepare_latest_day_measurements(measurements)

    assert len(latest_day) == 2
    assert latest_day["temperature"].tolist() == [21.0, 22.0]
    assert latest_day["humidity"].tolist() == [60.0, 65.0]


def test_prepare_monthly_rainfall_calculates_daily_differences_and_resets() -> None:
    measurements = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-09-30T23:59:00+00:00",
                    "2026-10-01T00:00:00+00:00",
                    "2026-10-01T12:00:00+00:00",
                    "2026-10-02T00:00:00+00:00",
                    "2026-10-02T12:00:00+00:00",
                    "2026-10-03T00:00:00+00:00",
                ]
            ),
            "rain_accumulated": [10.0, 10.2, 10.8, 11.1, 0.1, 0.3],
        }
    )

    month, chart_data = prepare_monthly_rainfall(measurements)
    daily_rainfall = chart_data.set_index("day")["rainfall"]

    assert month == "outubro de 2026"
    assert len(chart_data) == 31
    assert daily_rainfall.loc[1] == pytest.approx(0.9)
    assert daily_rainfall.loc[2] == pytest.approx(0.3)
    assert pd.isna(daily_rainfall.loc[3])
    assert pd.isna(daily_rainfall.loc[4])


def test_prepare_daily_history_aggregates_sensor_values_and_monthly_rainfall() -> None:
    measurements = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-09-30T23:59:00+00:00",
                    "2026-10-01T00:00:00+00:00",
                    "2026-10-01T12:00:00+00:00",
                    "2026-10-02T00:00:00+00:00",
                    "2026-10-02T12:00:00+00:00",
                    "2026-10-03T00:00:00+00:00",
                ]
            ),
            "temperature": [18.0, 19.0, 24.0, 20.0, 22.0, 17.0],
            "humidity": [55.0, 60.0, 75.0, 62.0, 80.0, 58.0],
            "rain_accumulated": [10.0, 10.2, 10.8, 11.1, 0.1, 0.3],
        }
    )

    history = prepare_daily_history(measurements).set_index("date")

    assert history.loc["30/09/2026", "temperature_max"] == 19.0
    assert history.loc["30/09/2026", "temperature_min"] == 18.0
    assert history.loc["30/09/2026", "humidity_max"] == 60.0
    assert history.loc["30/09/2026", "humidity_min"] == 55.0
    assert history.loc["30/09/2026", "daily_rainfall"] == pytest.approx(0.2)
    assert history.loc["01/10/2026", "temperature_max"] == 24.0
    assert history.loc["01/10/2026", "temperature_min"] == 20.0
    assert history.loc["01/10/2026", "humidity_max"] == 75.0
    assert history.loc["01/10/2026", "humidity_min"] == 62.0
    assert history.loc["01/10/2026", "daily_rainfall"] == pytest.approx(0.9)
    assert history.loc["01/10/2026", "monthly_rainfall"] == pytest.approx(0.9)
    assert history.loc["02/10/2026", "daily_rainfall"] == pytest.approx(0.3)
    assert history.loc["02/10/2026", "monthly_rainfall"] == pytest.approx(1.2)


def test_prepare_daily_history_keeps_rain_counters_separate_by_source_and_device() -> None:
    measurements = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-10-05T19:15:00+00:00",
                    "2026-10-05T19:15:57+00:00",
                    "2026-10-05T19:20:00+00:00",
                    "2026-10-05T19:22:57+00:00",
                    "2026-10-05T19:25:00+00:00",
                    "2026-10-05T19:57:58+00:00",
                ]
            ),
            "temperature": [20.0, 20.1, 20.2, 20.3, 20.4, 20.5],
            "humidity": [60.0, 61.0, 62.0, 63.0, 64.0, 65.0],
            "rain_accumulated": [272.034, 0.4, 272.034, 0.8, 272.034, 1.0],
            "source": ["csv_import", "stm32", "csv_import", "stm32", "csv_import", "stm32"],
            "device_id": [
                "estacao-experimental-csv",
                "est_01",
                "estacao-experimental-csv",
                "est_01",
                "estacao-experimental-csv",
                "est_01",
            ],
        }
    )

    history = prepare_daily_history(measurements).set_index("date")

    assert history.loc["05/10/2026", "daily_rainfall"] == pytest.approx(0.6)
    assert history.loc["05/10/2026", "monthly_rainfall"] == pytest.approx(0.6)


def test_get_supabase_settings_accepts_supabase_key_alias(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test-key")

    assert get_supabase_settings() == ("https://example.supabase.co", "test-key")


def test_get_supabase_settings_prefers_publishable_key(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "publishable-test-key")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "old-anon-key")

    assert get_supabase_settings() == ("https://example.supabase.co", "publishable-test-key")


def test_get_supabase_settings_reads_streamlit_secrets(monkeypatch) -> None:
    for name in (
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_SECRET_KEY",
        "SUPABASE_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    secrets = {
        "SUPABASE_URL": "https://secrets.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "publishable-secret-value",
    }
    monkeypatch.setattr("dashboard._get_streamlit_secret", secrets.get)

    assert get_supabase_settings() == (
        "https://secrets.supabase.co",
        "publishable-secret-value",
    )


def test_get_supabase_settings_does_not_use_privileged_keys(monkeypatch) -> None:
    for name in ("SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY", "SUPABASE_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "privileged-key")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret-key")
    monkeypatch.setattr("dashboard._get_streamlit_secret", lambda name: None)

    assert get_supabase_settings() == ("https://example.supabase.co", None)


def test_load_measurements_reads_csv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
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

        def __init__(self, rows: list[dict]) -> None:
            self.rows = rows

        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict]:
            return self.rows

    rows = [
        {
            "measured_at": "2026-10-01T12:00:00+00:00",
            "temperature": 21.4,
            "humidity": 63.1,
            "rain_accumulated": 3.8,
        }
    ]
    calls = []

    def fake_get(*args, **kwargs) -> FakeResponse:
        calls.append(kwargs["params"])
        offset = int(kwargs["params"]["offset"])
        return FakeResponse(rows[offset : offset + 1000])

    monkeypatch.setattr("dashboard.requests.get", fake_get)

    dataframe = load_measurements()

    assert isinstance(dataframe, pd.DataFrame)
    assert len(dataframe) == 1
    assert len(calls) == 2
    assert calls[0]["offset"] == "0"
    assert calls[1]["offset"] == "1"
    assert dataframe.iloc[0]["temperature"] == 21.4
    assert dataframe.iloc[0]["humidity"] == 63.1
    assert dataframe.iloc[0]["rain_accumulated"] == 3.8


def test_fetch_supabase_measurements_reads_more_than_ten_thousand_rows(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    rows = [
        {
            "measured_at": f"2026-10-{(index // 1440) + 1:02}T00:00:00+00:00",
            "temperature": 20.0 + index / 10000,
            "humidity": 60.0,
            "rain_accumulated": 0.0,
        }
        for index in range(10_037)
    ]
    offsets = []

    class FakeResponse:
        status_code = 200

        def __init__(self, page: list[dict]) -> None:
            self.page = page

        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict]:
            return self.page

    def fake_get(*args, **kwargs) -> FakeResponse:
        offset = int(kwargs["params"]["offset"])
        offsets.append(offset)
        return FakeResponse(rows[offset : offset + 777])

    monkeypatch.setattr("dashboard.requests.get", fake_get)

    dataframe = fetch_supabase_measurements()

    assert len(dataframe) == len(rows)
    assert offsets[0] == 0
    assert offsets[-1] == len(rows)
    assert len(offsets) > 10


def test_fetch_supabase_measurements_reports_request_errors(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    errors = []

    def raise_connection_error(*args, **kwargs):
        raise requests.ConnectionError("connection failed")

    monkeypatch.setattr("dashboard.requests.get", raise_connection_error)
    monkeypatch.setattr("dashboard.st.error", errors.append)

    dataframe = fetch_supabase_measurements()

    assert dataframe.empty
    assert errors == [
        "Falha ao consultar o Supabase. Confira a URL, a chave pública e as permissões de leitura."
    ]


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
