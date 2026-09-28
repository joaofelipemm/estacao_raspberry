from estacao_raspberry.sensor import Sensor


def test_sensor_returns_mock_data() -> None:
    sensor = Sensor()
    reading = sensor.read()

    assert reading.temperature == 25.0
    assert reading.humidity == 55.0
    assert reading.pressure == 1013.0
