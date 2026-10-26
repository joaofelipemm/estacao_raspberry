"""Parser de mensagens serial recebidas do STM32."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from .sensor import SensorReading


def list_serial_ports() -> list[str]:
    """Retorna as portas seriais disponíveis no sistema."""
    try:
        from serial.tools import list_ports
    except ImportError as exc:  # pragma: no cover - depends on environment.
        raise RuntimeError(
            "A biblioteca pyserial não está instalada. Instale com pip install pyserial."
        ) from exc
    return [port.device for port in list_ports.comports()]


def resolve_serial_port(port: str | None = None) -> str:
    """Usa a porta informada ou seleciona a única porta serial disponível."""
    if port:
        return port

    ports = list_serial_ports()
    if not ports:
        raise RuntimeError("Nenhuma porta serial encontrada. Conecte o dispositivo USB e tente novamente.")
    if len(ports) > 1:
        available = ", ".join(ports)
        raise RuntimeError(
            f"Mais de uma porta serial encontrada ({available}); informe qual porta usar."
        )
    return ports[0]


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
    - <TEMP=23.4;HUM=58.1;RAIN=12.5;RAD=450;CRC=abc123>
    - TEMP=23.4;HUM=58.1;RAIN=12.5;RAD=450
    - DADOS:...;23.4;58.1;12.5;450 (radiação em W/m² opcional)
    """
    if not isinstance(payload, str):
        raise ValueError("Formato inválido: payload deve ser uma string.")

    protocol = protocol or SerialProtocol()
    message = payload.strip()

    if not message:
        raise ValueError("Formato inválido: mensagem serial vazia.")

    if message.upper().startswith("DADOS:"):
        fields = [field.strip() for field in message.split(":", 1)[1].split(";")]
        if len(fields) not in {6, 7} or not fields[0]:
            raise ValueError(
                "Formato inválido: DADOS deve conter dispositivo, data, hora, temperatura, umidade, chuva e, opcionalmente, radiação solar."
            )
        try:
            measured_at = datetime.strptime(
                f"{fields[1]} {fields[2]}", "%d/%m/%Y %H:%M:%S"
            ).astimezone()
            temperature, humidity, rain_accumulated = map(float, fields[3:6])
            solar_radiation = float(fields[6]) if len(fields) == 7 else None
        except ValueError as exc:
            raise ValueError("Formato inválido: valores incorretos no registro DADOS.") from exc

        return SensorReading(
            temperature=temperature,
            humidity=humidity,
            rain_accumulated=rain_accumulated,
            solar_radiation=solar_radiation,
            measured_at=measured_at,
            device_id=fields[0],
        )

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

    required = {"TEMP", "HUM", "RAIN"}
    missing = sorted(required - digest.keys())
    if missing:
        raise ValueError(f"Formato inválido: campos ausentes: {', '.join(missing)}")

    try:
        temperature = float(digest["TEMP"])
        humidity = float(digest["HUM"])
        rain_accumulated = float(digest["RAIN"])
        solar_radiation = float(digest["RAD"]) if "RAD" in digest else None
    except ValueError as exc:  # pragma: no cover - branch covered by bad payload tests
        raise ValueError(
            "Formato inválido: valores numéricos esperados em TEMP, HUM, RAIN e RAD."
        ) from exc

    return SensorReading(
        temperature=temperature,
        humidity=humidity,
        rain_accumulated=rain_accumulated,
        solar_radiation=solar_radiation,
    )


class SerialReader:
    """Lê mensagens do STM32 em uma porta serial e converte em SensorReading."""

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
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
        """Lê uma medição DADOS ou um quadro legado pela porta serial."""
        serial_port = self.open()
        while True:
            raw = serial_port.readline()
            if not raw:
                continue
            payload = raw.decode("utf-8", errors="replace").strip()
            if not payload:
                continue
            if not (
                payload.upper().startswith("DADOS:")
                or payload.startswith(self.protocol.start_marker)
                or "TEMP=" in payload.upper()
            ):
                continue
            try:
                return parse_serial_payload(payload, protocol=self.protocol)
            except ValueError as exc:
                print(f"Aviso: mensagem serial inválida descartada: {exc}")

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None
