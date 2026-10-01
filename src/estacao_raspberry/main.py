"""Ponto de entrada da aplicação da estação Raspberry."""

from __future__ import annotations

from .config import DEFAULT_SETTINGS
from .sensor import Sensor
from .storage import MeasurementStore


def main() -> None:
    """Executa uma leitura simples e salva os dados em arquivo local."""
    print("Estação Raspberry iniciada.")
    settings = DEFAULT_SETTINGS
    settings.ensure_directories()

    sensor = Sensor()
    reading = sensor.read()
    store = MeasurementStore(settings.data_dir / "measurements.csv")
    store.save(reading)

    print(f"Temperatura: {reading.temperature} C")
    print(f"Umidade: {reading.humidity} %")
    print(f"Pressão: {reading.pressure} hPa")
    print(f"Dados salvos em: {store.file_path}")


if __name__ == "__main__":
    main()
