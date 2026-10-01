"""Persistência de leituras do sensor em arquivo local."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from .sensor import SensorReading


class MeasurementStore:
    """Armazena leituras em CSV com timestamp."""

    CSV_COLUMNS = ["timestamp", "temperature", "humidity", "rain_accumulated"]

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
                writer.writerow({column: row.get(column, "") for column in self.CSV_COLUMNS})
            temporary_path = Path(temporary_file.name)
        temporary_path.replace(self.file_path)

    def _write_header(self) -> None:
        with self.file_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(self.CSV_COLUMNS)

    def save(self, reading: SensorReading) -> None:
        """Salva uma leitura no arquivo CSV."""
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        row = [
            timestamp,
            reading.temperature,
            reading.humidity,
            reading.rain_accumulated,
        ]
        with self.file_path.open("a", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(row)

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
                        "timestamp": row.get("timestamp"),
                        "temperature": self._to_float(row.get("temperature")),
                        "humidity": self._to_float(row.get("humidity")),
                        "rain_accumulated": self._to_float(row.get("rain_accumulated")),
                    }
                )
        return records

    @staticmethod
    def _to_float(value: str | None) -> float | None:
        if value is None or value == "":
            return None
        return float(value)
