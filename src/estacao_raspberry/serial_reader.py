"""Parser de mensagens serial recebidas do STM32."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .sensor import SensorReading


@dataclass(frozen=True)
class SerialProtocol:
    """Define a estrutura básica do protocolo de mensagens do STM32."""

    start_marker: str = "<"
    end_marker: str = ">"
    separator: str = ";"
    field_separator: str = "="


def parse_serial_payload(
    payload: str,
    protocol: SerialProtocol | None = None,
) -> SensorReading:
    """Converte uma mensagem serial em uma leitura normalizada.

    Formatos aceitos:
    - <TEMP=23.4;HUM=58.1;PRES=1012.3;CRC=abc123>
    - TEMP=23.4;HUM=58.1;PRES=1012.3
    """
    if not isinstance(payload, str):
        raise ValueError("Formato inválido: payload deve ser uma string.")

    protocol = protocol or SerialProtocol()
    message = payload.strip()

    if not message:
        raise ValueError("Formato inválido: mensagem serial vazia.")

    if message.startswith(protocol.start_marker) and message.endswith(protocol.end_marker):
        message = message[1:-1]

    entries = [part.strip() for part in message.split(protocol.separator) if part.strip()]
    if not entries:
        raise ValueError("Formato inválido: mensagem serial sem campos.")

    digest: dict[str, str] = {}
    for entry in entries:
        if protocol.field_separator not in entry:
            continue
        key, value = entry.split(protocol.field_separator, 1)
        digest[key.strip().upper()] = value.strip()

    required = {"TEMP", "HUM", "PRES"}
    missing = sorted(required - digest.keys())
    if missing:
        raise ValueError(f"Formato inválido: campos ausentes: {', '.join(missing)}")

    try:
        temperature = float(digest["TEMP"])
        humidity = float(digest["HUM"])
        pressure = float(digest["PRES"])
    except ValueError as exc:  # pragma: no cover - branch covered by bad payload tests
        raise ValueError("Formato inválido: valores numéricos esperados em TEMP, HUM e PRES.") from exc

    return SensorReading(
        temperature=temperature,
        humidity=humidity,
        pressure=pressure,
    )


class SerialReader:
    """Lê mensagens do STM32 em uma porta serial e converte em SensorReading."""

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        timeout: float = 1.0,
        protocol: SerialProtocol | None = None,
        serial_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.protocol = protocol or SerialProtocol()
        self.serial_factory = serial_factory or self._default_serial_factory
        self._serial: Any | None = None

    @staticmethod
    def _default_serial_factory(*args: Any, **kwargs: Any) -> Any:
        try:
            import serial  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on environment.
            raise RuntimeError("A biblioteca pyserial não está instalada. Instale com pip install pyserial.") from exc
        return serial.Serial(*args, **kwargs)

    def open(self) -> Any:
        if self._serial is None:
            self._serial = self.serial_factory(
                self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
            )
        return self._serial

    def read_measurement(self) -> SensorReading:
        """Lê uma linha da porta serial e a converte em leitura do sistema."""
        serial_port = self.open()
        while True:
            raw = serial_port.readline()
            if not raw:
                continue
            payload = raw.decode("utf-8", errors="replace").strip()
            if not payload:
                continue
            return parse_serial_payload(payload, protocol=self.protocol)

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None
