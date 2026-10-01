from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st


DEFAULT_CSV_PATH = Path("data/measurements.csv")


def get_supabase_settings() -> tuple[str | None, str | None]:
    """Lê as credenciais do Supabase a partir das variáveis de ambiente."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    return url, key


def fetch_supabase_measurements() -> pd.DataFrame:
    """Busca as últimas leituras no Supabase e converte para DataFrame."""
    url, key = get_supabase_settings()
    if not url or not key:
        return pd.DataFrame(columns=["timestamp", "temperature", "humidity", "pressure"])

    endpoint = f"{url.rstrip('/')}/rest/v1/measurements"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    params = {
        "select": "*",
        "order": "measured_at.desc",
        "limit": "100",
    }

    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return pd.DataFrame(columns=["timestamp", "temperature", "humidity", "pressure"])

    if not payload:
        return pd.DataFrame(columns=["timestamp", "temperature", "humidity", "pressure"])

    data = []
    for row in payload:
        measured_at = row.get("measured_at")
        if measured_at is None:
            continue
        data.append(
            {
                "timestamp": pd.to_datetime(measured_at),
                "temperature": float(row.get("temperature", 0.0)),
                "humidity": float(row.get("humidity", 0.0)),
                "pressure": float(row.get("pressure", 0.0)),
            }
        )

    if not data:
        return pd.DataFrame(columns=["timestamp", "temperature", "humidity", "pressure"])

    dataframe = pd.DataFrame(data).sort_values("timestamp").reset_index(drop=True)
    return dataframe


def load_measurements(csv_path: str | Path = DEFAULT_CSV_PATH) -> pd.DataFrame:
    """Carrega medições do Supabase primeiro e usa CSV local como fallback."""
    remote = fetch_supabase_measurements()
    if not remote.empty:
        return remote

    path = Path(csv_path)
    if not path.exists():
        return pd.DataFrame(columns=["timestamp", "temperature", "humidity", "pressure"])

    dataframe = pd.read_csv(path)
    if dataframe.empty:
        return dataframe

    dataframe["timestamp"] = pd.to_datetime(dataframe["timestamp"], errors="coerce")
    dataframe = dataframe.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    return dataframe


def main() -> None:
    """Dashboard simples da estação Raspberry em modo online-first."""
    st.title("Estação Raspberry")
    source = "Supabase" if get_supabase_settings()[0] and get_supabase_settings()[1] else "CSV local"
    st.caption(f"Monitoramento das variáveis recebidas do STM32 — fonte: {source}")

    measurements = load_measurements(DEFAULT_CSV_PATH)

    if measurements.empty:
        st.info("Ainda não há leituras registradas. Aguarde a primeira coleta do STM32 ou configure o Supabase.")
        return

    latest = measurements.iloc[-1]

    col_temp, col_hum, col_press = st.columns(3)
    col_temp.metric("Temperatura", f"{latest['temperature']} °C")
    col_hum.metric("Umidade", f"{latest['humidity']} %")
    col_press.metric("Pressão", f"{latest['pressure']} hPa")

    st.subheader("Última leitura")
    st.json(
        {
            "timestamp": latest["timestamp"].isoformat(timespec="seconds"),
            "temperature": float(latest["temperature"]),
            "humidity": float(latest["humidity"]),
            "pressure": float(latest["pressure"]),
        }
    )

    st.subheader("Histórico")
    st.dataframe(measurements[["timestamp", "temperature", "humidity", "pressure"]])


if __name__ == "__main__":
    main()
