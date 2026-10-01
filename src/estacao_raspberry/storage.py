"""Persistência de leituras do sensor em arquivo local."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from .sensor import SensorReading


class MeasurementStore:
    """Armazena leituras em CSV com timestamp."""

    CSV_COLUMNS = [
        "measurement_id",
        "timestamp",
        "temperature",
        "humidity",
        "rain_accumulated",
        "sync_status",
    ]

    def __init__(self, file_path: str | Path = "data/measurements.csv") -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists() or self.file_path.stat().st_size == 0:
            self._write_header()
        else:
            self._migrate_legacy_csv()

    def _migrate_legacy_csv(self) -> None:
        with self.file_path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames == self.CSV_COLUMNS:
                return
            rows = list(reader)

        with NamedTemporaryFile(
            "w", encoding="utf-8", newline="", dir=self.file_path.parent, delete=False
        ) as temporary_file:
            writer = csv.DictWriter(temporary_file, fieldnames=self.CSV_COLUMNS)
            writer.writeheader()
            for row in rows:
                rain_accumulated = row.get("rain_accumulated", "")
                writer.writerow(
                    {
                        "measurement_id": row.get("measurement_id") or str(uuid4()),
                        "timestamp": row.get("timestamp", ""),
                        "temperature": row.get("temperature", ""),
                        "humidity": row.get("humidity", ""),
                        "rain_accumulated": rain_accumulated,
                        "sync_status": row.get(
                            "sync_status", "pending" if rain_accumulated else "not_applicable"
                        ),
                    }
                )
            temporary_path = Path(temporary_file.name)
        temporary_path.replace(self.file_path)

    def _write_header(self) -> None:
        with self.file_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(self.CSV_COLUMNS)

    def save(self, reading: SensorReading) -> str:
        """Salva uma leitura pendente e retorna seu identificador estável."""
        measurement_id = str(uuid4())
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        row = [
            measurement_id,
            timestamp,
            reading.temperature,
            reading.humidity,
            reading.rain_accumulated,
            "pending" if reading.rain_accumulated is not None else "not_applicable",
        ]
        with self.file_path.open("a", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(row)
        return measurement_id

    def read_all(self) -> list[dict[str, str | float | None]]:
        """Retorna todas as leituras salvas."""
        records: list[dict[str, str | float | None]] = []
        if not self.file_path.exists():
            return records

        with self.file_path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                records.append(
                    {
                        "measurement_id": row.get("measurement_id"),
                        "timestamp": row.get("timestamp"),
                        "temperature": self._to_float(row.get("temperature")),
                        "humidity": self._to_float(row.get("humidity")),
                        "rain_accumulated": self._to_float(row.get("rain_accumulated")),
                        "sync_status": row.get("sync_status"),
                    }
                )
        return records

    def mark_synced(self, measurement_id: str) -> bool:
        """Marca uma leitura como sincronizada sem reescrever parcialmente o CSV."""
        with self.file_path.open("r", encoding="utf-8", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))

        found = False
        for row in rows:
            if row.get("measurement_id") == measurement_id:
                row["sync_status"] = "synced"
                found = True

        if not found:
            return False

        with NamedTemporaryFile(
            "w", encoding="utf-8", newline="", dir=self.file_path.parent, delete=False
        ) as temporary_file:
            writer = csv.DictWriter(temporary_file, fieldnames=self.CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
            temporary_path = Path(temporary_file.name)
        temporary_path.replace(self.file_path)
        return True

    @staticmethod
    def _to_float(value: str | None) -> float | None:
        if value is None or value == "":
            return None
        return float(value)
