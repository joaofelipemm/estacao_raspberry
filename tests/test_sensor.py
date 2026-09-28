import pytest

from estacao_raspberry.sensor import Sensor, SensorReading


def test_sensor_returns_mock_data() -> None:
    sensor = Sensor()
    reading = sensor.read()

    assert reading.temperature == 25.0
    assert reading.humidity == 55.0
    assert reading.pressure == 1013.0


def test_sensor_supports_named_backend() -> None:
    sensor = Sensor(sensor_type="mock")
    reading = sensor.read()

    assert isinstance(reading, SensorReading)
    assert reading.temperature == 25.0
    assert reading.humidity == 55.0
    assert reading.pressure == 1013.0


def test_sensor_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="Tipo de sensor"):
        Sensor(sensor_type="invalido")
