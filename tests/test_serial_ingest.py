import pytest

from estacao_raspberry.main import main
from estacao_raspberry.sensor import SensorReading
from estacao_raspberry.serial_reader import (
    SerialProtocol,
    SerialReader,
    parse_serial_payload,
    resolve_serial_port,
)


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


def test_parse_serial_payload_accepts_stm32_dados_record() -> None:
    reading = parse_serial_payload("DADOS:est_01;05/10/2026;16:15:57;23.66;77.06;0.4")

    assert reading.device_id == "est_01"
    assert reading.measured_at is not None
    assert reading.measured_at.strftime("%d/%m/%Y %H:%M:%S") == "05/10/2026 16:15:57"
    assert reading.temperature == 23.66
    assert reading.humidity == 77.06
    assert reading.rain_accumulated == 0.4
    assert reading.solar_radiation is None


def test_parse_serial_payload_accepts_optional_solar_radiation() -> None:
    reading = parse_serial_payload(
        "DADOS:est_01;05/10/2026;16:15:57;23.66;77.06;0.4;456.7"
    )

    assert reading.solar_radiation == 456.7


def test_parse_serial_payload_accepts_legacy_frame_with_optional_rad() -> None:
    reading = parse_serial_payload("<TEMP=23.4;HUM=58.1;RAIN=12.5;RAD=456.7>")

    assert reading.solar_radiation == 456.7


def test_parse_serial_payload_rejects_malformed_stm32_record() -> None:
    with pytest.raises(ValueError, match="Formato inválido"):
        parse_serial_payload("DADOS:est_01;data;hora;23.66;77.06;0.4")


def test_parse_serial_payload_rejects_bad_message() -> None:
    with pytest.raises(ValueError, match="Formato inválido"):
        parse_serial_payload("TEMP=bad;HUM=58.1;RAIN=12.3")


def test_serial_protocol_sets_default_delimiters() -> None:
    protocol = SerialProtocol()

    assert protocol.start_marker == "<"
    assert protocol.end_marker == ">"
    assert protocol.separator == ";"


def test_serial_reader_reads_measurement_from_mocked_port() -> None:
    fake_port = FakeSerialPort(["<TEMP=21.5;HUM=60.0;RAIN=9.2;CRC=ok>"])
    reader = SerialReader(
        port="/dev/ttyUSB0",
        serial_factory=lambda *args, **kwargs: fake_port,
    )

    reading = reader.read_measurement()

    assert reading.temperature == 21.5
    assert reading.humidity == 60.0
    assert reading.rain_accumulated == 9.2
    reader.close()


def test_serial_reader_skips_invalid_frame_and_reads_next_measurement(capsys) -> None:
    fake_port = FakeSerialPort(
        [
            "<TEMP=bad;HUM=60.0;RAIN=9.2>",
            "<TEMP=21.5;HUM=60.0;RAIN=9.2>",
        ]
    )
    reader = SerialReader(
        port="COM11",
        serial_factory=lambda *args, **kwargs: fake_port,
    )

    reading = reader.read_measurement()

    assert reading.temperature == 21.5
    assert "mensagem serial inválida descartada" in capsys.readouterr().out
    reader.close()


def test_serial_reader_ignores_status_lines_and_reads_dados_record() -> None:
    fake_port = FakeSerialPort(
        [
            "TX: PERGUNTA:1:7 -> OK\n",
            "RX: RESPOSTA:1:7:est_01;05/10/2026;16:15:57;23.66;77.06;0.4\n",
            "DADOS:est_01;05/10/2026;16:15:57;23.66;77.06;0.4\n",
        ]
    )
    reader = SerialReader(
        port="COM11",
        serial_factory=lambda *args, **kwargs: fake_port,
    )

    reading = reader.read_measurement()

    assert reading.device_id == "est_01"
    assert reading.temperature == 23.66
    reader.close()


def test_resolve_serial_port_uses_the_only_detected_port(monkeypatch) -> None:
    monkeypatch.setattr("estacao_raspberry.serial_reader.list_serial_ports", lambda: ["COM11"])

    assert resolve_serial_port() == "COM11"


def test_resolve_serial_port_rejects_ambiguous_ports(monkeypatch) -> None:
    monkeypatch.setattr(
        "estacao_raspberry.serial_reader.list_serial_ports", lambda: ["COM3", "COM11"]
    )

    with pytest.raises(RuntimeError, match="Mais de uma porta serial"):
        resolve_serial_port()


def test_main_reads_serial_data_and_persists_it(tmp_path, monkeypatch) -> None:
    fake_port = FakeSerialPort(["<TEMP=19.7;HUM=62.4;RAIN=8.3;CRC=ok>\n"])
    output_file = tmp_path / "measurements.csv"

    monkeypatch.setattr("estacao_raspberry.main.DEFAULT_SETTINGS", type("Settings", (), {"data_dir": tmp_path, "log_dir": tmp_path / "logs", "ensure_directories": lambda self: None})())

    main(
        port="/dev/ttyUSB0",
        serial_factory=lambda *args, **kwargs: fake_port,
        file_path=output_file,
        max_readings=1,
    )

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

    def fake_sync(csv_path, **kwargs) -> int:
        sync_calls.append({"csv_path": csv_path, "config": kwargs})
        assert output_file.exists()
        assert "8.3" in output_file.read_text(encoding="utf-8")
        return 1

    monkeypatch.setattr("estacao_raspberry.main.DEFAULT_SETTINGS", Settings())
    monkeypatch.setattr("estacao_raspberry.main.sync_measurements_from_csv", fake_sync)

    main(
        port="/dev/ttyUSB0",
        serial_factory=lambda *args, **kwargs: fake_port,
        file_path=output_file,
        max_readings=1,
    )

    assert output_file.exists()
    assert len(sync_calls) == 1
    assert sync_calls[0]["csv_path"] == output_file
    assert sync_calls[0]["config"]["device_id"] == "rpi-test"


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

    def failing_sync(csv_path, **kwargs) -> int:
        assert output_file.exists()
        raise RuntimeError("network unavailable")

    monkeypatch.setattr("estacao_raspberry.main.DEFAULT_SETTINGS", Settings())
    monkeypatch.setattr("estacao_raspberry.main.sync_measurements_from_csv", failing_sync)

    main(
        port="/dev/ttyUSB0",
        serial_factory=lambda *args, **kwargs: fake_port,
        file_path=output_file,
        max_readings=1,
    )

    content = output_file.read_text(encoding="utf-8")
    assert "8.3" in content
    assert "leituras pendentes mantidas no CSV" in capsys.readouterr().out


def test_main_keeps_reading_and_saves_each_measurement(tmp_path, monkeypatch) -> None:
    fake_port = FakeSerialPort(
        [
            "<TEMP=19.7;HUM=62.4;RAIN=8.3>",
            "<TEMP=20.1;HUM=61.9;RAIN=8.4>",
        ]
    )
    output_file = tmp_path / "measurements.csv"

    class Settings:
        data_dir = tmp_path
        log_dir = tmp_path / "logs"
        resolved_supabase_url = ""
        resolved_supabase_key = ""

        def ensure_directories(self) -> None:
            return None

    monkeypatch.setattr("estacao_raspberry.main.DEFAULT_SETTINGS", Settings())

    saved_count = main(
        port="COM11",
        serial_factory=lambda *args, **kwargs: fake_port,
        file_path=output_file,
        max_readings=2,
    )

    assert saved_count == 2
    content = output_file.read_text(encoding="utf-8")
    assert "19.7" in content
    assert "20.1" in content
