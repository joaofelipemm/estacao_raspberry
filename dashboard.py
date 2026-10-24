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


st.set_page_config(page_title="Estação Experimental", page_icon="🌡️", layout="wide")


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


def format_metric_delta(current: float, previous: float | None, unit: str) -> str | None:
    """Formata a variação em relação à leitura imediatamente anterior."""
    if previous is None or pd.isna(current) or pd.isna(previous):
        return None
    return f"{current - previous:+.2f} {unit}"


def calculate_rainfall_changes(measurements: pd.DataFrame) -> pd.DataFrame:
    """Calcula as variações do acumulador de chuva, incluindo reinicializações."""
    data = measurements[["timestamp", "rain_accumulated"]].copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce")
    data["rain_accumulated"] = pd.to_numeric(data["rain_accumulated"], errors="coerce")
    data = data.dropna(subset=["timestamp", "rain_accumulated"]).sort_values("timestamp")
    changes = data["rain_accumulated"].diff()
    data["rainfall_change"] = changes
    reset = data["rainfall_change"] < 0
    data.loc[reset, "rainfall_change"] = data.loc[reset, "rain_accumulated"]
    return data


def prepare_daily_history(measurements: pd.DataFrame) -> pd.DataFrame:
    """Resume máximas, mínimas e chuva diária/mensal para cada dia com leituras."""
    columns = [
        "date",
        "temperature_max",
        "temperature_min",
        "humidity_max",
        "humidity_min",
        "daily_rainfall",
        "monthly_rainfall",
    ]
    data = measurements.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce")
    for column in ("temperature", "humidity"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["timestamp"]).sort_values("timestamp")
    if data.empty:
        return pd.DataFrame(columns=columns)

    rain_changes = calculate_rainfall_changes(data)
    data["date"] = data["timestamp"].dt.normalize()
    data["month"] = data["timestamp"].dt.strftime("%Y-%m")
    daily = (
        data.groupby(["date", "month"], sort=True)
        .agg(
            temperature_max=("temperature", "max"),
            temperature_min=("temperature", "min"),
            humidity_max=("humidity", "max"),
            humidity_min=("humidity", "min"),
        )
        .reset_index()
    )
    if rain_changes.empty:
        daily["daily_rainfall"] = float("nan")
    else:
        rain_changes["date"] = rain_changes["timestamp"].dt.normalize()
        daily_rainfall = (
            rain_changes.groupby("date")["rainfall_change"]
            .sum(min_count=1)
            .rename("daily_rainfall")
        )
        daily = daily.merge(daily_rainfall, on="date", how="left")

    daily["monthly_rainfall"] = daily.groupby("month")["daily_rainfall"].cumsum()
    daily["date"] = daily["date"].dt.strftime("%d/%m/%Y")
    return daily[columns]


def prepare_monthly_rainfall(measurements: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    """Calcula a chuva diária por variação do acumulador no mês da última leitura."""
    columns = ["day", "rainfall"]
    data = calculate_rainfall_changes(measurements)
    if data.empty:
        return "", pd.DataFrame(columns=columns)

    latest = data.iloc[-1]["timestamp"]
    month_data = data[
        (data["timestamp"].dt.year == latest.year)
        & (data["timestamp"].dt.month == latest.month)
    ].copy()
    daily = (
        month_data.assign(day=month_data["timestamp"].dt.day)
        .groupby("day")["rainfall_change"]
        .sum(min_count=1)
        .rename("rainfall")
    )

    month_start = latest.normalize().replace(day=1)
    day_count = month_start.days_in_month
    chart_data = pd.DataFrame({"day": range(1, day_count + 1)})
    chart_data = chart_data.merge(daily, on="day", how="left")
    month_names = (
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    )
    month_label = f"{month_names[latest.month - 1]} de {latest.year}"
    return month_label, chart_data


@st.fragment(run_every=60, key="dashboard")
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
            min-height: 112px;
            box-sizing: border-box;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    supabase_configured = all(get_supabase_settings())
    st.title("Estação Experimental")
    st.caption("Painel executivo de monitoramento ambiental")

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
    previous = measurements.iloc[-2] if len(measurements) > 1 else None

    delta_temp = format_metric_delta(
        float(latest["temperature"]),
        float(previous["temperature"]) if previous is not None else None,
        "°C",
    )
    delta_hum = format_metric_delta(
        float(latest["humidity"]),
        float(previous["humidity"]) if previous is not None else None,
        "%",
    )
    rain_total = latest.get("rain_accumulated")
    previous_rain = previous.get("rain_accumulated") if previous is not None else None

    col_temp, col_hum, col_rain = st.columns(3)
    col_temp.metric("Temperatura", f"{latest['temperature']} °C", delta_temp)
    col_hum.metric("Umidade", f"{latest['humidity']} %", delta_hum)
    rain_value = f"{float(rain_total):.2f} mm" if pd.notna(rain_total) else "Sem dado"
    delta_rain = format_metric_delta(
        float(rain_total) if pd.notna(rain_total) else float("nan"),
        float(previous_rain) if previous_rain is not None and pd.notna(previous_rain) else None,
        "mm",
    )
    col_rain.metric("Chuva acumulada", rain_value, delta_rain)

    chart_data = measurements.set_index("timestamp")
    st.subheader("Temperatura")
    st.line_chart(
        chart_data[["temperature"]],
        y_label="Temperatura (°C)",
    )
    st.subheader("Umidade")
    st.line_chart(
        chart_data[["humidity"]],
        y_label="Umidade (%)",
    )

    month_label, rainfall_data = prepare_monthly_rainfall(measurements)
    st.subheader(f"Chuva diária — {month_label}" if month_label else "Chuva diária")
    if rainfall_data["rainfall"].notna().any():
        st.bar_chart(
            rainfall_data.assign(rainfall=rainfall_data["rainfall"].fillna(0)),
            x="day",
            y="rainfall",
            x_label="Dia do mês",
            y_label="Chuva (mm)",
        )
    else:
        st.info("Sem dados suficientes para calcular a chuva diária neste mês.")

    st.subheader("Histórico completo")
    st.dataframe(
        prepare_daily_history(measurements).rename(
            columns={
                "date": "Data",
                "temperature_max": "Temperatura máxima (°C)",
                "temperature_min": "Temperatura mínima (°C)",
                "humidity_max": "Umidade máxima (%)",
                "humidity_min": "Umidade mínima (%)",
                "daily_rainfall": "Chuva no dia (mm)",
                "monthly_rainfall": "Chuva acumulada no mês (mm)",
            }
        ),
        width="stretch",
    )


def main() -> None:
    """Dashboard executivo da estação Raspberry em modo online-first."""
    render_dashboard()


if __name__ == "__main__":
    main()
