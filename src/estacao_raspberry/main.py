"""Ponto de entrada da aplicação da estação Raspberry."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .config import DEFAULT_SETTINGS
from .sensor import SensorReading
from .serial_reader import SerialReader
from .storage import MeasurementStore
from .supabase_sync import sync_measurements_from_csv


def main(
    port: str | None = None,
    *,
    baudrate: int = 9600,
    timeout: float = 1.0,
    serial_factory: Callable[..., Any] | None = None,
    file_path: str | Path | None = None,
) -> SensorReading:
    """Lê uma mensagem serial enviada pelo STM32 e salva no armazenamento local."""
    print("Estação Raspberry iniciada.")
    settings = DEFAULT_SETTINGS
    settings.ensure_directories()

    serial_port = port or "/dev/ttyUSB0"
    store = MeasurementStore(file_path or settings.data_dir / "measurements.csv")
    reader = SerialReader(
        port=serial_port,
        baudrate=baudrate,
        timeout=timeout,
        serial_factory=serial_factory,
    )

    try:
        reading = reader.read_measurement()
    finally:
        reader.close()

    store.save(reading)

    supabase_url = getattr(settings, "resolved_supabase_url", "")
    supabase_key = getattr(settings, "resolved_supabase_key", "")
    if supabase_url and supabase_key:
        try:
            synced_count = sync_measurements_from_csv(
                store.file_path,
                url=supabase_url,
                key=supabase_key,
                device_id=getattr(settings, "device_id", "raspberry-pi"),
            )
            print(f"Leituras sincronizadas com o Supabase: {synced_count}")
        except Exception as exc:
            print(f"Aviso: falha ao sincronizar com Supabase; leituras pendentes mantidas no CSV: {exc}")

    print(f"Temperatura: {reading.temperature} C")
    print(f"Umidade: {reading.humidity} %")
    print(f"Chuva acumulada: {reading.rain_accumulated} mm")
    print(f"Dados salvos em: {store.file_path}")
    return reading


if __name__ == "__main__":
    main()
