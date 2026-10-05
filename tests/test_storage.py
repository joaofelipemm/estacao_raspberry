from estacao_raspberry.sensor import SensorReading
from estacao_raspberry.storage import MeasurementStore
from datetime import datetime


def test_measurement_store_writes_csv(tmp_path) -> None:
    file_path = tmp_path / "data" / "measurements.csv"
    store = MeasurementStore(file_path)
    reading = SensorReading(temperature=22.5, humidity=60.0, rain_accumulated=12.0)

    store.save(reading)

    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert "timestamp" in content.lower()
    assert "22.5" in content
    assert "60.0" in content
    assert "12.0" in content
    assert "rain_accumulated" in content


def test_measurement_store_creates_directory(tmp_path) -> None:
    file_path = tmp_path / "nested" / "logs" / "measurements.csv"
    store = MeasurementStore(file_path)

    store.save(SensorReading(temperature=19.1, humidity=58.5, rain_accumulated=15.2))

    assert file_path.exists()


def test_measurement_store_migrates_legacy_pressure_csv_without_relabeling_it(tmp_path) -> None:
    file_path = tmp_path / "measurements.csv"
    file_path.write_text(
        "timestamp,temperature,humidity,pressure\n"
        "2026-10-01T12:00:00+00:00,22.5,60.0,1012.0\n",
        encoding="utf-8",
    )

    store = MeasurementStore(file_path)
    store.save(SensorReading(temperature=23.0, humidity=61.0, rain_accumulated=2.5))

    records = store.read_all()
    assert records[0]["rain_accumulated"] is None
    assert records[1]["rain_accumulated"] == 2.5


def test_measurement_store_preserves_device_id_and_device_timestamp(tmp_path) -> None:
    file_path = tmp_path / "measurements.csv"
    store = MeasurementStore(file_path)
    reading = SensorReading(
        temperature=23.66,
        humidity=77.06,
        rain_accumulated=0.4,
        measured_at=datetime.fromisoformat("2026-10-05T16:15:57+00:00"),
        device_id="est_01",
    )

    store.save(reading)

    saved = MeasurementStore(file_path).read_all()[0]
    assert saved["timestamp"] == "2026-10-05T16:15:57+00:00"
    assert saved["device_id"] == "est_01"
