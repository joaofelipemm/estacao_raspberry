from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitSecretNotFoundError


load_dotenv()


DEFAULT_CSV_PATH = Path("data/measurements.csv")


st.set_page_config(page_title="Estação Raspberry", page_icon="🌡️", layout="wide")


def get_supabase_settings() -> tuple[str | None, str | None]:
    """Lê credenciais públicas do ambiente ou dos Secrets do Streamlit."""
    url = os.getenv("SUPABASE_URL") or _get_streamlit_secret("SUPABASE_URL")
    key = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY")
        or _get_streamlit_secret("SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
        or _get_streamlit_secret("SUPABASE_ANON_KEY")
    )
    return url, key


def _get_streamlit_secret(name: str) -> str | None:
    """Retorna um Secret, sem falhar quando o app local não tem secrets.toml."""
    try:
        value = st.secrets.get(name)
    except (KeyError, StreamlitSecretNotFoundError):
        return None
    return str(value) if value else None


def fetch_supabase_measurements() -> pd.DataFrame:
    """Busca as últimas leituras no Supabase e converte para DataFrame."""
    url, key = get_supabase_settings()
    if not url or not key:
        return pd.DataFrame(columns=["timestamp", "temperature", "humidity", "rain_accumulated"])

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
    except (requests.RequestException, ValueError) as exc:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        status = f" (HTTP {status_code})" if status_code else ""
        st.error(
            "Falha ao consultar o Supabase"
            f"{status}. Confira a URL, a chave pública e as permissões de leitura."
        )
        return pd.DataFrame(columns=["timestamp", "temperature", "humidity", "rain_accumulated"])

    if not payload:
        return pd.DataFrame(columns=["timestamp", "temperature", "humidity", "rain_accumulated"])

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
                "rain_accumulated": (
                    float(row["rain_accumulated"])
                    if row.get("rain_accumulated") is not None
                    else None
                ),
            }
        )

    if not data:
        return pd.DataFrame(columns=["timestamp", "temperature", "humidity", "rain_accumulated"])

    dataframe = pd.DataFrame(data).sort_values("timestamp").reset_index(drop=True)
    return dataframe


def load_measurements(csv_path: str | Path = DEFAULT_CSV_PATH) -> pd.DataFrame:
    """Carrega medições do Supabase primeiro e usa CSV local como fallback."""
    remote = fetch_supabase_measurements()
    if not remote.empty:
        return remote

    path = Path(csv_path)
    if not path.exists():
        return pd.DataFrame(columns=["timestamp", "temperature", "humidity", "rain_accumulated"])

    dataframe = pd.read_csv(path)
    if dataframe.empty:
        return dataframe

    dataframe["timestamp"] = pd.to_datetime(dataframe["timestamp"], errors="coerce")
    if "rain_accumulated" not in dataframe.columns:
        dataframe["rain_accumulated"] = pd.NA
    dataframe = dataframe.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    return dataframe


def render_dashboard() -> None:
    """Renderiza um painel executivo com indicadores e histórico de dados."""
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.5rem; }
        div[data-testid="stMetric"] > div {
            background: linear-gradient(135deg, #16223f, #0c1222);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 0.8rem 1rem;
            box-shadow: 0 8px 24px rgba(0,0,0,0.18);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    supabase_configured = all(get_supabase_settings())
    source = "Supabase" if supabase_configured else "CSV local"
    st.title("Estação Raspberry")
    st.caption(f"Painel executivo de monitoramento ambiental — dados via {source}")

    measurements = load_measurements(DEFAULT_CSV_PATH)

    if measurements.empty:
        if supabase_configured:
            st.info(
                "A consulta terminou sem leituras válidas. Verifique se "
                "`public.measurements` contém registros."
            )
        else:
            st.info(
                "Supabase não configurado: adicione `SUPABASE_URL` e "
                "`SUPABASE_PUBLISHABLE_KEY` (ou `SUPABASE_ANON_KEY`) aos Secrets."
            )
        return

    latest = measurements.iloc[-1]
    oldest = measurements.iloc[0]

    delta_temp = latest["temperature"] - oldest["temperature"] if len(measurements) > 1 else 0.0
    delta_hum = latest["humidity"] - oldest["humidity"] if len(measurements) > 1 else 0.0
    rain_total = latest.get("rain_accumulated")

    col_temp, col_hum, col_rain = st.columns(3)
    col_temp.metric("Temperatura", f"{latest['temperature']} °C", f"{delta_temp:+.2f} °C")
    col_hum.metric("Umidade", f"{latest['humidity']} %", f"{delta_hum:+.2f} %")
    rain_value = f"{float(rain_total):.2f} mm" if pd.notna(rain_total) else "Sem dado"
    col_rain.metric("Chuva acumulada", rain_value)

    chart_data = measurements[["timestamp", "temperature", "humidity", "rain_accumulated"]].copy()
    chart_data = chart_data.set_index("timestamp")

    col_chart_1, col_chart_2 = st.columns(2)
    with col_chart_1:
        st.subheader("Temperatura e umidade")
        st.line_chart(chart_data[["temperature", "humidity"]])
    with col_chart_2:
        st.subheader("Chuva acumulada")
        if chart_data["rain_accumulated"].notna().any():
            st.area_chart(chart_data[["rain_accumulated"]])
            st.caption("Acumulado informado pelo STM32 (mm)")
        else:
            st.info("Sem dados de chuva. O STM32 deve enviar o campo RAIN em milímetros.")

    st.subheader("Última leitura")
    st.json(
        {
            "timestamp": latest["timestamp"].isoformat(timespec="seconds"),
            "temperature": float(latest["temperature"]),
            "humidity": float(latest["humidity"]),
            "rain_accumulated": (
                float(rain_total) if pd.notna(rain_total) else None
            ),
        }
    )

    st.subheader("Histórico completo")
    st.dataframe(
        measurements[["timestamp", "temperature", "humidity", "rain_accumulated"]].rename(
            columns={
                "timestamp": "Data/Hora",
                "temperature": "Temperatura (°C)",
                "humidity": "Umidade (%)",
                "rain_accumulated": "Chuva acumulada (mm)",
            }
        ),
        width="stretch",
    )


def main() -> None:
    """Dashboard executivo da estação Raspberry em modo online-first."""
    render_dashboard()


if __name__ == "__main__":
    main()
