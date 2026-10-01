"""Cliente de sincronização com a API REST do Supabase."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests

from .sensor import SensorReading
from .storage import MeasurementStore


@dataclass
class SupabaseSyncClient:
    """Envia leituras do Raspberry para uma tabela `measurements` no Supabase."""

    url: str | None = None
    key: str | None = None
    device_id: str = "raspberry-pi"
    table_name: str = "measurements"
    source: str = "stm32"
    timeout: float = 10.0

    def __post_init__(self) -> None:
        self.url = (self.url or "").rstrip("/")
        self.key = self.key or ""
        if not self.url:
            raise ValueError("SUPABASE_URL deve ser informado para sincronizar com o Supabase.")
        if not self.key:
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY ou SUPABASE_ANON_KEY deve ser informado.")

    @property
    def endpoint(self) -> str:
        return f"{self.url}/rest/v1/{self.table_name}"

    @property
    def headers(self) -> dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates,return=minimal",
        }

    def build_payload(
        self,
        reading: SensorReading,
        measured_at: datetime | None = None,
        status: str = "synced",
        metadata: dict[str, Any] | None = None,
        sync_id: str | None = None,
    ) -> dict[str, Any]:
        if reading.temperature is None or reading.humidity is None or reading.rain_accumulated is None:
            raise ValueError("Leitura incompleta para sincronizar com o Supabase.")

        measurement_time = measured_at or datetime.now(timezone.utc)
        if measurement_time.tzinfo is None:
            measurement_time = measurement_time.replace(tzinfo=timezone.utc)

        return {
            "sync_id": sync_id or str(uuid4()),
            "device_id": self.device_id,
            "measured_at": measurement_time.astimezone(timezone.utc).isoformat(),
            "temperature": reading.temperature,
            "humidity": reading.humidity,
            "rain_accumulated": reading.rain_accumulated,
            "source": self.source,
            "status": status,
            "metadata": metadata or {},
        }

    def send_measurement(
        self,
        reading: SensorReading,
        measured_at: datetime | None = None,
        status: str = "synced",
        metadata: dict[str, Any] | None = None,
        sync_id: str | None = None,
    ) -> bool:
        """Envia uma leitura para o Supabase e retorna True em sucesso."""
        payload = self.build_payload(
            reading,
            measured_at=measured_at,
            status=status,
            metadata=metadata,
            sync_id=sync_id,
        )
        session = requests.Session()
        response = session.post(
            self.endpoint,
            json=payload,
            headers=self.headers,
            params={"on_conflict": "sync_id"},
            timeout=self.timeout,
        )
        if response.status_code in {200, 201, 204}:
            return True

        raise RuntimeError(
            f"Falha ao sincronizar com Supabase: HTTP {response.status_code} - {response.text}"
        )


def sync_measurements_from_csv(
    csv_path: str | Path,
    *,
    url: str | None = None,
    key: str | None = None,
    device_id: str = "raspberry-pi",
    table_name: str = "measurements",
    source: str = "stm32",
    timeout: float = 10.0,
    max_attempts: int = 3,
    retry_delay_seconds: float = 0.5,
) -> int:
    """Sincroniza a fila local com retry exponencial e status persistente."""
    path = Path(csv_path)
    if not path.exists():
        return 0
    if max_attempts < 1:
        raise ValueError("max_attempts deve ser pelo menos 1.")
    if retry_delay_seconds < 0:
        raise ValueError("retry_delay_seconds não pode ser negativo.")

    client = SupabaseSyncClient(
        url=url,
        key=key,
        device_id=device_id,
        table_name=table_name,
        source=source,
        timeout=timeout,
    )
    store = MeasurementStore(path)

    rows_synced = 0
    for row in store.read_all():
        if row["sync_status"] != "pending" or row["rain_accumulated"] is None:
            continue

        timestamp = row["timestamp"]
        try:
            measured_at = datetime.fromisoformat(timestamp) if timestamp else None
        except ValueError:
            measured_at = None

        reading = SensorReading(
            temperature=row["temperature"],
            humidity=row["humidity"],
            rain_accumulated=row["rain_accumulated"],
        )
        for attempt in range(max_attempts):
            try:
                client.send_measurement(
                    reading,
                    measured_at=measured_at,
                    status="synced",
                    sync_id=row["measurement_id"],
                )
                store.mark_synced(row["measurement_id"])
                rows_synced += 1
                break
            except (requests.RequestException, RuntimeError) as exc:
                if attempt + 1 == max_attempts:
                    raise RuntimeError(
                        f"Falha ao sincronizar leitura {row['measurement_id']} após {max_attempts} tentativas."
                    ) from exc
                time.sleep(retry_delay_seconds * (2**attempt))

    return rows_synced
