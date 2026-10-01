"""Configurações gerais do projeto."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Parâmetros básicos da aplicação."""

    app_name: str = "estacao_raspberry"
    data_dir: Path = Path("data")
    log_dir: Path = Path("logs")
    device_id: str = "raspberry-pi"
    supabase_url: str | None = None
    supabase_key: str | None = None

    def ensure_directories(self) -> None:
        """Cria diretórios necessários para a aplicação."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    @property
    def resolved_supabase_url(self) -> str:
        return (self.supabase_url or os.getenv("SUPABASE_URL") or "").rstrip("/")

    @property
    def resolved_supabase_key(self) -> str:
        return self.supabase_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or ""


DEFAULT_SETTINGS = Settings(
    device_id=os.getenv("DEVICE_ID", "raspberry-pi"),
    supabase_url=os.getenv("SUPABASE_URL"),
    supabase_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY"),
)
