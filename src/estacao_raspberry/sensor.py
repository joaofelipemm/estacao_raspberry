"""Módulo de sensores e leitura de dados."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SensorReading:
    """Estrutura de leitura de um sensor."""

    temperature: float | None = None
    humidity: float | None = None
    pressure: float | None = None


class Sensor:
    """Classe base para sensores da estação."""

    def read(self) -> SensorReading:
        """Retorna leitura simulada do sensor.

        Este método será substituído por sensores reais no futuro.
        """
        return SensorReading(temperature=25.0, humidity=55.0, pressure=1013.0)
