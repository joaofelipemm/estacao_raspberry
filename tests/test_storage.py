from estacao_raspberry.sensor import SensorReading
from estacao_raspberry.storage import MeasurementStore


def test_measurement_store_writes_csv(tmp_path) -> None:
    file_path = tmp_path / "data" / "measurements.csv"
    store = MeasurementStore(file_path)
    reading = SensorReading(temperature=22.5, humidity=60.0, pressure=1012.0)

    store.save(reading)

    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert "timestamp" in content.lower()
    assert "22.5" in content
    assert "60.0" in content
    assert "1012.0" in content


def test_measurement_store_creates_directory(tmp_path) -> None:
    file_path = tmp_path / "nested" / "logs" / "measurements.csv"
    store = MeasurementStore(file_path)

    store.save(SensorReading(temperature=19.1, humidity=58.5, pressure=1015.2))

    assert file_path.exists()
