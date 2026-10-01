"""Módulo de sensores e leitura de dados."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SensorReading:
    """Estrutura de leitura de um sensor."""

    temperature: float | None = None
    humidity: float | None = None
    rain_accumulated: float | None = None


class Sensor:
    """Classe base para sensores da estação."""

    VALID_SENSOR_TYPES = {"mock"}

    def __init__(self, sensor_type: str = "mock") -> None:
        """Inicializa o sensor com o backend desejado."""
        normalized_type = sensor_type.lower()
        if normalized_type not in self.VALID_SENSOR_TYPES:
            valid_types = ", ".join(sorted(self.VALID_SENSOR_TYPES))
            raise ValueError(
                f"Tipo de sensor '{sensor_type}' não suportado. Tipos válidos: {valid_types}."
            )
        self.sensor_type = normalized_type

    def read(self) -> SensorReading:
        """Retorna a leitura do sensor.

        O backend inicial é simulado, mas a estrutura da classe já permite evoluir para
        drivers reais de sensores de hardware.
        """
        if self.sensor_type == "mock":
            return SensorReading(temperature=25.0, humidity=55.0, rain_accumulated=0.0)

        raise ValueError(f"Tipo de sensor '{self.sensor_type}' não implementado.")
