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
    payload = "TEMP=23.4;HUM=58.1;PRES=1012.3;CRC=abc123"

    reading = parse_serial_payload(payload)

    assert isinstance(reading, SensorReading)
    assert reading.temperature == 23.4
    assert reading.humidity == 58.1
    assert reading.pressure == 1012.3


def test_parse_serial_payload_rejects_bad_message() -> None:
    with pytest.raises(ValueError, match="Formato inválido"):
        parse_serial_payload("TEMP=bad;HUM=58.1;PRES=1012.3")


def test_serial_protocol_sets_default_delimiters() -> None:
    protocol = SerialProtocol()

    assert protocol.start_marker == "<"
    assert protocol.end_marker == ">"
    assert protocol.separator == ";"


def test_serial_reader_reads_measurement_from_mocked_port() -> None:
    fake_port = FakeSerialPort(["<TEMP=21.5;HUM=60.0;PRES=1009.2;CRC=ok>\n"])
    reader = SerialReader(
        port="/dev/ttyUSB0",
        serial_factory=lambda *args, **kwargs: fake_port,
    )

    reading = reader.read_measurement()

    assert reading.temperature == 21.5
    assert reading.humidity == 60.0
    assert reading.pressure == 1009.2
    reader.close()


def test_main_reads_serial_data_and_persists_it(tmp_path, monkeypatch) -> None:
    fake_port = FakeSerialPort(["<TEMP=19.7;HUM=62.4;PRES=1008.3;CRC=ok>\n"])
    output_file = tmp_path / "measurements.csv"

    monkeypatch.setattr("estacao_raspberry.main.DEFAULT_SETTINGS", type("Settings", (), {"data_dir": tmp_path, "log_dir": tmp_path / "logs", "ensure_directories": lambda self: None})())

    main(port="/dev/ttyUSB0", serial_factory=lambda *args, **kwargs: fake_port, file_path=output_file)

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "19.7" in content
    assert "62.4" in content
    assert "1008.3" in content
