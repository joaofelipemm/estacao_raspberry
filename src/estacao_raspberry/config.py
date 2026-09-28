"""Configurações gerais do projeto."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Parâmetros básicos da aplicação."""

    app_name: str = "estacao_raspberry"
    data_dir: Path = Path("data")
    log_dir: Path = Path("logs")

    def ensure_directories(self) -> None:
        """Cria diretórios necessários para a aplicação."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


DEFAULT_SETTINGS = Settings()
