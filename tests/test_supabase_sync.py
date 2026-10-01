from __future__ import annotations

from datetime import datetime

from requests.exceptions import RequestException

from estacao_raspberry.sensor import SensorReading
from estacao_raspberry.storage import MeasurementStore
from estacao_raspberry.supabase_sync import SupabaseSyncClient
from estacao_raspberry.supabase_sync import sync_measurements_from_csv


class FakeResponse:
    def __init__(self, status_code: int = 201, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = "ok"

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, response_codes: list[int] | None = None) -> None:
        self.calls: list[dict] = []
        self.response_codes = iter(response_codes or [201])

    def post(self, url: str, json: dict, headers: dict, timeout: float | None = None, **kwargs) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout, **kwargs})
        return FakeResponse(status_code=next(self.response_codes))


def test_supabase_client_sends_measurement_payload(monkeypatch) -> None:
    fake_session = FakeSession()
    monkeypatch.setattr(
        "estacao_raspberry.supabase_sync.requests",
        type("RequestsStub", (), {"Session": lambda *args, **kwargs: fake_session})(),
    )

    client = SupabaseSyncClient(
        url="https://example.supabase.co",
        key="service-key",
        device_id="rpi-test-01",
    )
    reading = SensorReading(temperature=22.5, humidity=60.0, rain_accumulated=12.4)

    sent = client.send_measurement(reading, measured_at=datetime(2026, 1, 1, 12, 0, 0))

    assert sent is True
    assert len(fake_session.calls) == 1
    payload = fake_session.calls[0]["json"]
    assert payload["device_id"] == "rpi-test-01"
    assert payload["temperature"] == 22.5
    assert payload["humidity"] == 60.0
    assert payload["rain_accumulated"] == 12.4
    assert fake_session.calls[0]["params"] == {"on_conflict": "sync_id"}
    assert fake_session.calls[0]["headers"]["Prefer"] == "resolution=ignore-duplicates,return=minimal"
    assert payload["source"] == "stm32"
    assert payload["status"] == "synced"


def test_sync_pending_csv_retries_and_marks_measurement_synced(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "measurements.csv"
    store = MeasurementStore(csv_path)
    measurement_id = store.save(
        SensorReading(temperature=22.5, humidity=60.0, rain_accumulated=12.4)
    )
    fake_session = FakeSession([503, 503, 201])

    class RequestsStub:
        Session = lambda *args, **kwargs: fake_session
        RequestException = RequestException

    monkeypatch.setattr("estacao_raspberry.supabase_sync.requests", RequestsStub())
    monkeypatch.setattr("estacao_raspberry.supabase_sync.time.sleep", lambda delay: None)

    synced_count = sync_measurements_from_csv(
        csv_path,
        url="https://example.supabase.co",
        key="service-key",
        max_attempts=3,
    )

    assert synced_count == 1
    assert len(fake_session.calls) == 3
    assert all(call["json"]["sync_id"] == measurement_id for call in fake_session.calls)
    assert MeasurementStore(csv_path).read_all()[0]["sync_status"] == "synced"


def test_sync_pending_csv_keeps_measurement_pending_after_retries_fail(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "measurements.csv"
    store = MeasurementStore(csv_path)
    store.save(SensorReading(temperature=22.5, humidity=60.0, rain_accumulated=12.4))
    fake_session = FakeSession([503, 503, 503])

    class RequestsStub:
        Session = lambda *args, **kwargs: fake_session
        RequestException = RequestException

    monkeypatch.setattr("estacao_raspberry.supabase_sync.requests", RequestsStub())
    monkeypatch.setattr("estacao_raspberry.supabase_sync.time.sleep", lambda delay: None)

    try:
        sync_measurements_from_csv(
            csv_path,
            url="https://example.supabase.co",
            key="service-key",
            max_attempts=3,
        )
    except RuntimeError as error:
        assert "após 3 tentativas" in str(error)
    else:
        raise AssertionError("A sincronização deveria falhar após esgotar as tentativas.")

    assert MeasurementStore(csv_path).read_all()[0]["sync_status"] == "pending"
