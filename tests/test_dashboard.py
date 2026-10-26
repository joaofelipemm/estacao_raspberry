from pathlib import Path

import pandas as pd
import pytest
import requests

from dashboard import (
    fetch_supabase_measurements,
    format_metric_delta,
    get_available_measurement_dates,
    get_supabase_settings,
    get_latest_measurement_id,
    load_measurements,
    merge_new_measurements,
    prepare_daily_history,
    prepare_latest_day_measurements,
    prepare_measurements_for_date,
    prepare_monthly_rainfall,
    prepare_sensor_chart_data,
    render_sensor_line_chart,
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


def test_get_available_measurement_dates_returns_local_days_newest_first() -> None:
    measurements = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-10-23T23:55:00+00:00",
                    "2026-10-24T02:55:00+00:00",
                    "2026-10-24T03:00:00+00:00",
                    "not-a-date",
                ],
                errors="coerce",
                utc=True,
            )
        }
    )

    assert get_available_measurement_dates(measurements) == [
        "2026-10-24",
        "2026-10-23",
    ]


def test_get_available_measurement_dates_filters_days_without_sensor_values() -> None:
    measurements = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-10-23T23:55:00+00:00",
                    "2026-10-24T03:00:00+00:00",
                    "2026-10-25T03:00:00+00:00",
                ]
            ),
            "solar_radiation": [None, 450.5, float("nan")],
        }
    )

    assert get_available_measurement_dates(
        measurements, value_column="solar_radiation"
    ) == ["2026-10-24"]


def test_prepare_measurements_for_date_filters_to_selected_local_day() -> None:
    measurements = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-10-23T23:55:00+00:00",
                    "2026-10-24T02:55:00+00:00",
                    "2026-10-24T03:00:00+00:00",
                ]
            ),
            "temperature": [19.0, 20.0, 21.0],
        }
    )

    selected_day = prepare_measurements_for_date(measurements, "2026-10-23")

    assert selected_day["temperature"].tolist() == [19.0, 20.0]


def test_prepare_sensor_chart_data_uses_portuguese_labels_and_local_time() -> None:
    measurements = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-10-24T03:00:00+00:00",
                    "2026-10-24T04:05:00+00:00",
                ]
            ),
            "temperature": [21.0, 22.0],
        }
    )

    chart_data = prepare_sensor_chart_data(
        measurements,
        "2026-10-24",
        "temperature",
        "Temperatura (°C)",
    )

    assert chart_data.columns.tolist() == ["Horário (Brasília)", "Temperatura (°C)"]
    assert chart_data["Horário (Brasília)"].tolist() == [
        pd.Timestamp("2026-10-24 00:00"),
        pd.Timestamp("2026-10-24 01:05"),
    ]
    assert chart_data["Temperatura (°C)"].tolist() == [21.0, 22.0]


def test_prepare_sensor_chart_data_filters_and_converts_solar_radiation() -> None:
    measurements = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-10-24T03:00:00+00:00",
                    "2026-10-25T03:00:00+00:00",
                ]
            ),
            "solar_radiation": ["450.5", None],
        }
    )

    chart_data = prepare_sensor_chart_data(
        measurements,
        "2026-10-24",
        "solar_radiation",
        "Radiação solar (W/m²)",
    )

    assert chart_data["Horário (Brasília)"].tolist() == [
        pd.Timestamp("2026-10-24 00:00")
    ]
    assert chart_data["Radiação solar (W/m²)"].tolist() == [450.5]


def test_render_sensor_line_chart_uses_temporal_portuguese_axis(monkeypatch) -> None:
    rendered = []
    monkeypatch.setattr(
        "dashboard.st.altair_chart",
        lambda chart, **kwargs: rendered.append((chart, kwargs)),
    )
    chart_data = pd.DataFrame(
        {
            "Horário (Brasília)": pd.to_datetime(["2026-10-24 00:00"]),
            "Radiação solar (W/m²)": [450.5],
        }
    )

    render_sensor_line_chart(chart_data, "Radiação solar (W/m²)")

    specification = rendered[0][0].to_dict()
    assert specification["encoding"]["x"]["type"] == "temporal"
    axis = specification["encoding"]["x"]["axis"]
    assert axis["format"] == "%H:%M"
    assert axis["tickCount"] == {"interval": "hour", "step": 2}
    assert rendered[0][1] == {"width": "stretch"}


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
            "id": 1,
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
    assert dataframe.iloc[0]["id"] == 1


def test_fetch_supabase_measurements_reads_more_than_ten_thousand_rows(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    rows = [
        {
            "id": index + 1,
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
    assert get_latest_measurement_id(dataframe) == len(rows)


def test_fetch_supabase_measurements_queries_only_rows_after_id(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    calls = []

    class FakeResponse:
        status_code = 200

        def __init__(self, rows: list[dict]) -> None:
            self.rows = rows

        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict]:
            return self.rows

    row = {
        "id": 101,
        "measured_at": "2026-10-24T22:00:00+00:00",
        "temperature": 25.0,
        "humidity": 70.0,
        "rain_accumulated": 2.1,
        "solar_radiation": 456.7,
        "device_id": "est_01",
        "source": "stm32",
    }

    def fake_get(*args, **kwargs) -> FakeResponse:
        calls.append(kwargs["params"])
        return FakeResponse([row] if len(calls) == 1 else [])

    monkeypatch.setattr("dashboard.requests.get", fake_get)

    dataframe = fetch_supabase_measurements(after_id=100)

    assert len(dataframe) == 1
    assert dataframe.iloc[0]["id"] == 101
    assert dataframe.iloc[0]["solar_radiation"] == 456.7
    assert calls[0]["id"] == "gt.100"
    assert calls[0]["order"] == "id.asc"
    assert calls[0]["select"].startswith("id,")
    assert "solar_radiation" in calls[0]["select"]
    assert len(calls) == 2


def test_fetch_supabase_measurements_falls_back_before_solar_migration(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    calls = []
    errors = []

    class FakeResponse:
        status_code = 200

        def __init__(self, rows: list[dict], status_code: int = 200) -> None:
            self.rows = rows
            self.status_code = status_code
            self.text = (
                '{"code":"42703","message":"column solar_radiation does not exist"}'
            )

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise requests.HTTPError(response=self)

        def json(self) -> list[dict]:
            return self.rows

    row = {
        "id": 11,
        "measured_at": "2026-10-24T22:00:00+00:00",
        "temperature": 24.0,
        "humidity": 70.0,
        "rain_accumulated": 1.2,
    }

    def fake_get(*args, **kwargs) -> FakeResponse:
        calls.append(kwargs["params"])
        if len(calls) == 1:
            return FakeResponse([], status_code=400)
        return FakeResponse([row] if len(calls) == 2 else [])

    monkeypatch.setattr("dashboard.requests.get", fake_get)
    monkeypatch.setattr("dashboard.st.error", errors.append)

    dataframe = fetch_supabase_measurements()

    assert len(dataframe) == 1
    assert pd.isna(dataframe.iloc[0]["solar_radiation"])
    assert "solar_radiation" in calls[0]["select"]
    assert "solar_radiation" not in calls[1]["select"]
    assert errors == []


def test_fetch_supabase_measurements_returns_empty_when_there_are_no_new_rows(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    calls = []

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict]:
            return []

    def fake_get(*args, **kwargs) -> FakeResponse:
        calls.append(kwargs["params"])
        return FakeResponse()

    monkeypatch.setattr("dashboard.requests.get", fake_get)

    dataframe = fetch_supabase_measurements(after_id=15_317)

    assert dataframe.empty
    assert len(calls) == 1
    assert calls[0]["id"] == "gt.15317"


def test_merge_new_measurements_preserves_history_and_deduplicates_ids() -> None:
    existing = pd.DataFrame(
        {
            "id": [1, 2],
            "timestamp": pd.to_datetime(
                ["2026-10-24T10:00:00+00:00", "2026-10-24T11:00:00+00:00"]
            ),
            "temperature": [20.0, 21.0],
            "humidity": [60.0, 61.0],
            "rain_accumulated": [1.0, 1.2],
        }
    )
    new_measurements = pd.DataFrame(
        {
            "id": [2, 3],
            "timestamp": pd.to_datetime(
                ["2026-10-24T11:00:00+00:00", "2026-10-24T12:00:00+00:00"]
            ),
            "temperature": [21.0, 22.0],
            "humidity": [61.0, 62.0],
            "rain_accumulated": [1.2, 1.4],
        }
    )

    merged = merge_new_measurements(existing, new_measurements)

    assert merged["id"].tolist() == [1, 2, 3]
    assert get_latest_measurement_id(merged) == 3
    assert merge_new_measurements(merged, new_measurements).equals(merged)


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
    assert pd.isna(dataframe.iloc[0]["solar_radiation"])


def test_load_measurements_normalizes_mixed_timezone_timestamps(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    csv_file = tmp_path / "mixed-timezones.csv"
    csv_file.write_text(
        "timestamp,temperature,humidity\n"
        "2026-10-01T12:00:00+00:00,22.5,60.0\n"
        "2026-10-01T09:00:00,23.0,61.0\n",
        encoding="utf-8",
    )

    dataframe = load_measurements(csv_file)

    assert dataframe["timestamp"].dt.tz is not None
    assert dataframe["timestamp"].tolist() == [
        pd.Timestamp("2026-10-01T09:00:00+00:00"),
        pd.Timestamp("2026-10-01T12:00:00+00:00"),
    ]
