import pytest

from estacao_raspberry.main import main
from estacao_raspberry.sensor import SensorReading
from estacao_raspberry.serial_reader import SerialProtocol, SerialReader, parse_serial_payload


class FakeSerialPort:
    def __init__(self, payloads: list[str]) -> None:
        self._payloads = iter(payloads)

    def readline(self) -> bytes:
        try:
            return next(self._payloads).encode("utf-8")
        except StopIteration:
            return b""

    def close(self) -> None:
        return None


def test_parse_serial_payload_valid_message() -> None:
    payload = "TEMP=23.4;HUM=58.1;RAIN=12.3;CRC=abc123"

    reading = parse_serial_payload(payload)

    assert isinstance(reading, SensorReading)
    assert reading.temperature == 23.4
    assert reading.humidity == 58.1
    assert reading.rain_accumulated == 12.3


def test_parse_serial_payload_rejects_bad_message() -> None:
    with pytest.raises(ValueError, match="Formato inválido"):
        parse_serial_payload("TEMP=bad;HUM=58.1;RAIN=12.3")


def test_serial_protocol_sets_default_delimiters() -> None:
    protocol = SerialProtocol()

    assert protocol.start_marker == "<"
    assert protocol.end_marker == ">"
    assert protocol.separator == ";"


def test_serial_reader_reads_measurement_from_mocked_port() -> None:
    fake_port = FakeSerialPort(["<TEMP=21.5;HUM=60.0;RAIN=9.2;CRC=ok>\n"])
    reader = SerialReader(
        port="/dev/ttyUSB0",
        serial_factory=lambda *args, **kwargs: fake_port,
    )

    reading = reader.read_measurement()

    assert reading.temperature == 21.5
    assert reading.humidity == 60.0
    assert reading.rain_accumulated == 9.2
    reader.close()


def test_main_reads_serial_data_and_persists_it(tmp_path, monkeypatch) -> None:
    fake_port = FakeSerialPort(["<TEMP=19.7;HUM=62.4;RAIN=8.3;CRC=ok>\n"])
    output_file = tmp_path / "measurements.csv"

    monkeypatch.setattr("estacao_raspberry.main.DEFAULT_SETTINGS", type("Settings", (), {"data_dir": tmp_path, "log_dir": tmp_path / "logs", "ensure_directories": lambda self: None})())

    main(port="/dev/ttyUSB0", serial_factory=lambda *args, **kwargs: fake_port, file_path=output_file)

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "19.7" in content
    assert "62.4" in content
    assert "8.3" in content


def test_main_syncs_after_persisting_when_supabase_is_configured(tmp_path, monkeypatch) -> None:
    fake_port = FakeSerialPort(["<TEMP=19.7;HUM=62.4;RAIN=8.3;CRC=ok>\n"])
    output_file = tmp_path / "measurements.csv"
    sync_calls = []

    class Settings:
        data_dir = tmp_path
        log_dir = tmp_path / "logs"
        device_id = "rpi-test"
        resolved_supabase_url = "https://example.supabase.co"
        resolved_supabase_key = "test-key"

        def ensure_directories(self) -> None:
            return None

    class FakeSyncClient:
        def __init__(self, **kwargs) -> None:
            sync_calls.append({"config": kwargs})

        def send_measurement(self, reading) -> bool:
            sync_calls.append({"reading": reading})
            return True

    monkeypatch.setattr("estacao_raspberry.main.DEFAULT_SETTINGS", Settings())
    monkeypatch.setattr("estacao_raspberry.main.SupabaseSyncClient", FakeSyncClient)

    main(port="/dev/ttyUSB0", serial_factory=lambda *args, **kwargs: fake_port, file_path=output_file)

    assert output_file.exists()
    assert len(sync_calls) == 2
    assert sync_calls[1]["reading"].rain_accumulated == 8.3


def test_main_keeps_local_measurement_when_supabase_sync_fails(tmp_path, monkeypatch, capsys) -> None:
    fake_port = FakeSerialPort(["<TEMP=19.7;HUM=62.4;RAIN=8.3;CRC=ok>\n"])
    output_file = tmp_path / "measurements.csv"

    class Settings:
        data_dir = tmp_path
        log_dir = tmp_path / "logs"
        device_id = "rpi-test"
        resolved_supabase_url = "https://example.supabase.co"
        resolved_supabase_key = "test-key"

        def ensure_directories(self) -> None:
            return None

    class FailingSyncClient:
        def __init__(self, **kwargs) -> None:
            pass

        def send_measurement(self, reading) -> bool:
            raise RuntimeError("network unavailable")

    monkeypatch.setattr("estacao_raspberry.main.DEFAULT_SETTINGS", Settings())
    monkeypatch.setattr("estacao_raspberry.main.SupabaseSyncClient", FailingSyncClient)

    main(port="/dev/ttyUSB0", serial_factory=lambda *args, **kwargs: fake_port, file_path=output_file)

    content = output_file.read_text(encoding="utf-8")
    assert "8.3" in content
    assert "leitura mantida no CSV" in capsys.readouterr().out
