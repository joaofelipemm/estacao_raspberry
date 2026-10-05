"""Ponto de entrada da aplicação da estação Raspberry."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .config import DEFAULT_SETTINGS
from .sensor import SensorReading
from .serial_reader import SerialReader, resolve_serial_port
from .storage import MeasurementStore
from .supabase_sync import sync_measurements_from_csv


def main(
    port: str | None = None,
    *,
    baudrate: int = 115200,
    timeout: float = 1.0,
    serial_factory: Callable[..., Any] | None = None,
    file_path: str | Path | None = None,
    max_readings: int | None = None,
) -> int:
    """Salva continuamente no CSV as leituras válidas recebidas pela serial."""
    if max_readings is not None and max_readings < 1:
        raise ValueError("max_readings deve ser pelo menos 1.")

    print("Estação Raspberry iniciada.")
    settings = DEFAULT_SETTINGS
    settings.ensure_directories()

    serial_port = resolve_serial_port(port)
    print(f"Escutando {serial_port} a {baudrate} baud.")
    store = MeasurementStore(file_path or settings.data_dir / "measurements.csv")
    reader = SerialReader(
        port=serial_port,
        baudrate=baudrate,
        timeout=timeout,
        serial_factory=serial_factory,
    )

    readings_saved = 0
    try:
        while max_readings is None or readings_saved < max_readings:
            reading = reader.read_measurement()
            store.save(reading)
            readings_saved += 1

            print(f"Temperatura: {reading.temperature} C")
            print(f"Umidade: {reading.humidity} %")
            print(f"Chuva acumulada: {reading.rain_accumulated} mm")
            print(f"Dados salvos em: {store.file_path}")

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
                    print(
                        "Aviso: falha ao sincronizar com Supabase; "
                        f"leituras pendentes mantidas no CSV: {exc}"
                    )
    except KeyboardInterrupt:
        print("\nColeta serial encerrada.")
    finally:
        reader.close()

    return readings_saved


if __name__ == "__main__":
    main()
