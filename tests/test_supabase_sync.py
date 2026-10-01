from __future__ import annotations

from datetime import datetime

from estacao_raspberry.sensor import SensorReading
from estacao_raspberry.supabase_sync import SupabaseSyncClient


class FakeResponse:
    def __init__(self, status_code: int = 201, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = "ok"

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def post(self, url: str, json: dict, headers: dict, timeout: float | None = None, **kwargs) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout, **kwargs})
        return FakeResponse()


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
    assert payload["source"] == "stm32"
    assert payload["status"] == "synced"
