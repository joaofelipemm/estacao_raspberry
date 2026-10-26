from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitSecretNotFoundError


load_dotenv()


DEFAULT_CSV_PATH = Path("data/measurements.csv")
SUPABASE_PAGE_SIZE = 1000
DASHBOARD_REFRESH_SECONDS = 60
DASHBOARD_TIMEZONE = "America/Sao_Paulo"
MEASUREMENTS_SESSION_KEY = "dashboard_measurements"
SKIP_NEXT_MEASUREMENTS_POLL_KEY = "skip_next_measurements_poll"
MEASUREMENT_COLUMNS = [
    "id",
    "timestamp",
    "temperature",
    "humidity",
    "rain_accumulated",
    "solar_radiation",
    "device_id",
    "source",
]


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


def _is_missing_solar_radiation_column(error: requests.HTTPError) -> bool:
    """Identifica um Supabase que ainda não recebeu a migração de radiação."""
    response = error.response
    if response is None or response.status_code != 400:
        return False
    message = response.text.lower()
    return "solar_radiation" in message and (
        "does not exist" in message or "schema cache" in message
    )


def fetch_supabase_measurements(after_id: int | None = None) -> pd.DataFrame:
    """Busca leituras do Supabase em páginas, opcionalmente após um ID."""
    url, key = get_supabase_settings()
    if not url or not key:
        return pd.DataFrame(columns=MEASUREMENT_COLUMNS)

    endpoint = f"{url.rstrip('/')}/rest/v1/measurements"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    try:
        payload = []
        offset = 0
        select_columns = (
            "id,measured_at,temperature,humidity,rain_accumulated,"
            "solar_radiation,device_id,source"
        )
        while True:
            params = {
                "select": select_columns,
                "order": "id.asc",
                "limit": str(SUPABASE_PAGE_SIZE),
                "offset": str(offset),
            }
            if after_id is not None:
                params["id"] = f"gt.{after_id}"
            try:
                response = requests.get(
                    endpoint, headers=headers, params=params, timeout=30
                )
                response.raise_for_status()
            except requests.HTTPError as exc:
                if (
                    "solar_radiation" not in select_columns
                    or not _is_missing_solar_radiation_column(exc)
                ):
                    raise
                select_columns = (
                    "id,measured_at,temperature,humidity,rain_accumulated,"
                    "device_id,source"
                )
                payload = []
                offset = 0
                continue
            page = response.json()
            if not isinstance(page, list):
                raise ValueError("A resposta da API do Supabase não é uma lista de medições.")
            if not page:
                break
            payload.extend(page)
            offset += len(page)
    except (requests.RequestException, ValueError) as exc:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        status = f" (HTTP {status_code})" if status_code else ""
        st.error(
            "Falha ao consultar o Supabase"
            f"{status}. Confira a URL, a chave pública e as permissões de leitura."
        )
        return pd.DataFrame(columns=MEASUREMENT_COLUMNS)

    if not payload:
        return pd.DataFrame(columns=MEASUREMENT_COLUMNS)

    data = []
    for row in payload:
        measured_at = row.get("measured_at")
        if measured_at is None:
            continue
        data.append(
            {
                "id": int(row["id"]) if row.get("id") is not None else None,
                "timestamp": pd.to_datetime(measured_at),
                "temperature": float(row.get("temperature", 0.0)),
                "humidity": float(row.get("humidity", 0.0)),
                "rain_accumulated": (
                    float(row["rain_accumulated"])
                    if row.get("rain_accumulated") is not None
                    else None
                ),
                "solar_radiation": (
                    float(row["solar_radiation"])
                    if row.get("solar_radiation") is not None
                    else None
                ),
                "device_id": row.get("device_id"),
                "source": row.get("source"),
            }
        )

    if not data:
        return pd.DataFrame(columns=MEASUREMENT_COLUMNS)

    dataframe = (
        pd.DataFrame(data)
        .sort_values(["timestamp", "id"], kind="stable")
        .reset_index(drop=True)
    )
    return dataframe


def load_measurements(csv_path: str | Path = DEFAULT_CSV_PATH) -> pd.DataFrame:
    """Carrega medições do Supabase primeiro e usa CSV local como fallback."""
    remote = fetch_supabase_measurements()
    if not remote.empty:
        return remote

    path = Path(csv_path)
    if not path.exists():
        return pd.DataFrame(
            columns=[
                "timestamp",
                "temperature",
                "humidity",
                "rain_accumulated",
                "solar_radiation",
            ]
        )

    dataframe = pd.read_csv(path)
    if dataframe.empty:
        return dataframe

    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"], errors="coerce", utc=True, format="mixed"
    )
    if "rain_accumulated" not in dataframe.columns:
        dataframe["rain_accumulated"] = pd.NA
    if "solar_radiation" not in dataframe.columns:
        dataframe["solar_radiation"] = pd.NA
    dataframe = (
        dataframe.dropna(subset=["timestamp"])
        .sort_values("timestamp", kind="stable")
        .reset_index(drop=True)
    )
    return dataframe


def merge_new_measurements(
    existing: pd.DataFrame, new_measurements: pd.DataFrame
) -> pd.DataFrame:
    """Acrescenta leituras novas ao histórico sem duplicar IDs já carregados."""
    if new_measurements.empty:
        return existing
    if existing.empty:
        return new_measurements.sort_values(["timestamp", "id"], kind="stable").reset_index(
            drop=True
        )

    combined = pd.concat([existing, new_measurements], ignore_index=True)
    if "id" in combined.columns:
        identified = combined[combined["id"].notna()].drop_duplicates("id", keep="last")
        local_only = combined[combined["id"].isna()]
        combined = pd.concat([local_only, identified], ignore_index=True)
    return combined.sort_values(["timestamp", "id"], kind="stable").reset_index(drop=True)


def get_latest_measurement_id(measurements: pd.DataFrame) -> int | None:
    """Retorna o maior ID Supabase já carregado, se houver."""
    if "id" not in measurements.columns:
        return None
    ids = pd.to_numeric(measurements["id"], errors="coerce").dropna()
    return int(ids.max()) if not ids.empty else None


def format_metric_delta(current: float, previous: float | None, unit: str) -> str | None:
    """Formata a variação em relação à leitura imediatamente anterior."""
    if previous is None or pd.isna(current) or pd.isna(previous):
        return None
    return f"{current - previous:+.2f} {unit}"


def _to_dashboard_timezone(timestamps: pd.Series) -> pd.Series:
    """Interpreta timestamps sem fuso como UTC e converte para o horário da estação."""
    return pd.to_datetime(timestamps, errors="coerce", utc=True).dt.tz_convert(
        DASHBOARD_TIMEZONE
    )


def prepare_latest_day_measurements(measurements: pd.DataFrame) -> pd.DataFrame:
    """Retorna as medições do dia mais recente disponível."""
    data = measurements.copy()
    data["timestamp"] = _to_dashboard_timezone(data["timestamp"])
    data = data.dropna(subset=["timestamp"]).sort_values("timestamp")
    if data.empty:
        return data

    latest_day = data["timestamp"].iloc[-1].date()
    return data[data["timestamp"].dt.date == latest_day].reset_index(drop=True)


def get_available_measurement_dates(
    measurements: pd.DataFrame, value_column: str | None = None
) -> list[str]:
    """Retorna os dias disponíveis no fuso da estação, do mais recente ao antigo."""
    timestamps = _to_dashboard_timezone(measurements["timestamp"])
    if value_column is not None:
        if value_column not in measurements.columns:
            return []
        valid_values = pd.to_numeric(measurements[value_column], errors="coerce").notna()
        timestamps = timestamps[valid_values]
    timestamps = timestamps.dropna()
    return sorted(timestamps.dt.strftime("%Y-%m-%d").unique().tolist(), reverse=True)


def prepare_measurements_for_date(
    measurements: pd.DataFrame, selected_date: str
) -> pd.DataFrame:
    """Retorna as medições de uma data selecionada no fuso da estação."""
    data = measurements.copy()
    data["timestamp"] = _to_dashboard_timezone(data["timestamp"])
    data = data.dropna(subset=["timestamp"]).sort_values("timestamp")
    selected_day = pd.Timestamp(selected_date).date()
    return data[data["timestamp"].dt.date == selected_day].reset_index(drop=True)


def prepare_sensor_chart_data(
    measurements: pd.DataFrame,
    selected_date: str,
    value_column: str,
    value_label: str,
) -> pd.DataFrame:
    """Prepara os dados do gráfico com horário e série em português."""
    data = prepare_measurements_for_date(measurements, selected_date)
    return pd.DataFrame(
        {
            "Horário (Brasília)": data["timestamp"].dt.tz_localize(None),
            value_label: pd.to_numeric(data[value_column], errors="coerce"),
        }
    )


def render_sensor_line_chart(chart_data: pd.DataFrame, value_label: str) -> None:
    """Renderiza uma série temporal com eixos e tooltip em português."""
    if chart_data.empty or chart_data[value_label].notna().sum() == 0:
        st.info(f"Sem dados de {value_label.lower()} para esta data.")
        return

    time_column = "Horário (Brasília)"
    chart = (
        alt.Chart(chart_data)
        .mark_line()
        .encode(
            x=alt.X(
                field=time_column,
                type="temporal",
                title=time_column,
                axis=alt.Axis(
                    format="%H:%M",
                    labelAngle=-45,
                    tickCount={"interval": "hour", "step": 2},
                ),
            ),
            y=alt.Y(field=value_label, type="quantitative", title=value_label),
            tooltip=[
                alt.Tooltip(
                    field=time_column,
                    type="temporal",
                    title=time_column,
                    format="%d/%m/%Y %H:%M",
                ),
                alt.Tooltip(field=value_label, type="quantitative", title=value_label),
            ],
        )
        .properties(height=320)
    )
    st.altair_chart(chart, width="stretch")


def calculate_rainfall_changes(measurements: pd.DataFrame) -> pd.DataFrame:
    """Calcula as variações do acumulador de chuva, incluindo reinicializações."""
    counter_columns = [
        column for column in ("source", "device_id") if column in measurements.columns
    ]
    data = measurements[["timestamp", "rain_accumulated", *counter_columns]].copy()
    data["timestamp"] = _to_dashboard_timezone(data["timestamp"])
    data["rain_accumulated"] = pd.to_numeric(data["rain_accumulated"], errors="coerce")
    data = (
        data.dropna(subset=["timestamp", "rain_accumulated"])
        .sort_values("timestamp", kind="stable")
    )
    if counter_columns:
        changes = data.groupby(counter_columns, dropna=False, sort=False)[
            "rain_accumulated"
        ].diff()
    else:
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
    data["timestamp"] = _to_dashboard_timezone(data["timestamp"])
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


@st.fragment(run_every=DASHBOARD_REFRESH_SECONDS, key="supabase-poll")
def poll_measurements() -> None:
    """Consulta apenas leituras novas e rerenderiza o painel se houver mudanças."""
    if st.session_state.pop(SKIP_NEXT_MEASUREMENTS_POLL_KEY, False):
        return

    measurements = st.session_state[MEASUREMENTS_SESSION_KEY]
    if not all(get_supabase_settings()):
        refreshed = load_measurements(DEFAULT_CSV_PATH)
        if not measurements.equals(refreshed):
            st.session_state[MEASUREMENTS_SESSION_KEY] = refreshed
            st.rerun()
        return

    latest_id = get_latest_measurement_id(measurements)
    new_measurements = (
        fetch_supabase_measurements(after_id=latest_id)
        if latest_id is not None
        else fetch_supabase_measurements()
    )
    if new_measurements.empty:
        return

    st.session_state[MEASUREMENTS_SESSION_KEY] = merge_new_measurements(
        measurements, new_measurements
    )
    st.session_state[SKIP_NEXT_MEASUREMENTS_POLL_KEY] = True
    st.rerun()


def render_dashboard(measurements: pd.DataFrame) -> None:
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

    st.subheader("Temperatura")
    available_dates = get_available_measurement_dates(measurements)
    if available_dates:
        selected_date = st.selectbox(
            "Data das medições",
            available_dates,
            format_func=lambda date: pd.Timestamp(date).strftime("%d/%m/%Y"),
            key="temperature_chart_date",
        )
        temperature_data = prepare_sensor_chart_data(
            measurements,
            selected_date,
            "temperature",
            "Temperatura (°C)",
        )
        render_sensor_line_chart(temperature_data, "Temperatura (°C)")
    else:
        st.info("Não há datas válidas disponíveis para o gráfico de temperatura.")

    st.subheader("Umidade")
    if available_dates:
        selected_humidity_date = st.selectbox(
            "Data das medições de umidade",
            available_dates,
            format_func=lambda date: pd.Timestamp(date).strftime("%d/%m/%Y"),
            key="humidity_chart_date",
        )
        humidity_data = prepare_sensor_chart_data(
            measurements,
            selected_humidity_date,
            "humidity",
            "Umidade (%)",
        )
        render_sensor_line_chart(humidity_data, "Umidade (%)")
    else:
        st.info("Não há datas válidas disponíveis para o gráfico de umidade.")

    st.subheader("Radiação solar")
    radiation_dates = get_available_measurement_dates(
        measurements, value_column="solar_radiation"
    )
    if radiation_dates:
        selected_radiation_date = st.selectbox(
            "Data das medições de radiação solar",
            radiation_dates,
            format_func=lambda date: pd.Timestamp(date).strftime("%d/%m/%Y"),
            key="solar_radiation_chart_date",
        )
        radiation_data = prepare_sensor_chart_data(
            measurements,
            selected_radiation_date,
            "solar_radiation",
            "Radiação solar (W/m²)",
        )
        render_sensor_line_chart(radiation_data, "Radiação solar (W/m²)")
    else:
        st.info(
            "Ainda não há medições de radiação solar. Configure o STM32 para enviar "
            "o campo RAD em W/m² e aplique a migração do Supabase."
        )

    month_label, rainfall_data = prepare_monthly_rainfall(measurements)
    st.subheader(f"Chuva diária — {month_label}" if month_label else "Chuva diária")
    if rainfall_data["rainfall"].notna().any():
        rainfall_chart = rainfall_data.rename(
            columns={"day": "Dia do mês", "rainfall": "Chuva (mm)"}
        )
        st.bar_chart(
            rainfall_chart.assign(
                **{"Chuva (mm)": rainfall_chart["Chuva (mm)"].fillna(0)}
            ),
            x="Dia do mês",
            y="Chuva (mm)",
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
    if MEASUREMENTS_SESSION_KEY not in st.session_state:
        st.session_state[MEASUREMENTS_SESSION_KEY] = load_measurements(DEFAULT_CSV_PATH)
        st.session_state[SKIP_NEXT_MEASUREMENTS_POLL_KEY] = True

    render_dashboard(st.session_state[MEASUREMENTS_SESSION_KEY])
    poll_measurements()


if __name__ == "__main__":
    main()
