import json
import os
import re
import html

import pandas as pd
import plotly.express as px
import requests
import sqlalchemy
import streamlit as st

DB_USER = os.environ.get("DB_USER", "agent_readonly")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "troque_esta_senha")
DB_NAME = os.environ.get("DB_NAME", "site_services")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")

# Produção (Cloud SQL): se esta variável existir, o app conecta via
# Cloud SQL Python Connector em vez de TCP direto. Formato esperado:
# "projeto:regiao:nome-da-instancia"
INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME", "")

# Quanto tempo (segundos) os indicadores/gráficos ficam em cache antes de
# reconsultar o banco.
KPI_CACHE_TTL = int(os.environ.get("KPI_CACHE_TTL_SECONDS", "300"))

# OpenRouter — assistente de insights
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_MODELS = [
    OPENROUTER_DEFAULT_MODEL,
    "anthropic/claude-3.5-sonnet",
    "google/gemini-flash-1.5",
    "meta-llama/llama-3.1-70b-instruct",
]
OPENROUTER_MODELS = list(dict.fromkeys(OPENROUTER_MODELS))  # remove duplicatas, preserva ordem

EXAMPLE_QUESTIONS = [
    "Qual o panorama geral do negócio agora?",
    "Quais equipamentos precisam de atenção?",
    "Mostre um gráfico da receita por categoria de serviço.",
]

# =========================================================
# Paleta "canteiro de obras" — amarelo + cinza escuro
# =========================================================

THEME = {
    "yellow": "#F5C518",
    "yellow_soft": "rgba(245, 197, 24, 0.12)",
    "dark_bg": "#1B1C1F",
    "dark_panel": "#26282C",
    "dark_panel_2": "#2F3136",
    "border": "rgba(245, 197, 24, 0.18)",
    "text": "#EDEDED",
    "text_dim": "rgba(237, 237, 237, 0.65)",
}

# =========================================================
# Ícones (Lucide) — SVG inline, herdam a cor do tema via currentColor
# =========================================================

_LUCIDE = {
    "home": '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "bar_chart": '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "message_square": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "refresh": '<path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
    "alert": '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
    "hard_hat": '<path d="M2 18a10 10 0 0 1 20 0"/><path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 0 4 4"/><path d="M12 2a4 4 0 0 0-4 4v2a4 4 0 0 1-4 4"/><path d="M4 18h16"/>',
    "package": '<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    "clipboard_list": '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2"/><path d="M9 12h6"/><path d="M9 16h6"/><path d="M9 8h.01"/><path d="M9 20h.01"/>',
    "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94z"/>',
    "file_clock": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v6h6"/><circle cx="12" cy="16" r="3"/><path d="M12 14.5v1.7l1.1.7"/>',
    "chart": '<path d="M3 3v18h18"/><path d="m7 16 4-5 3 3 5-7"/>',
    "dollar": '<line x1="12" x2="12" y1="2" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "building": '<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/>',
    "check_circle": '<path d="M21.801 10A10 10 0 1 1 17 3.335"/><path d="m9 11 3 3L22 4"/>',
    "sparkles": '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/><path d="M4 17v2"/><path d="M5 18H3"/>',
}


def icon(name: str, size: int = 18, color: str = "currentColor") -> str:
    body = _LUCIDE.get(name, "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle">{body}</svg>'
    )


ALERT_COLORS = {"high": "#dc2626", "medium": "#d97706", "low": "#2563eb", "ok": "#16a34a"}


# =========================================================
# CSS global — tema amarelo/cinza escuro + sidebar em modo
# "sumário" (sem cara de botão)
# =========================================================


def inject_theme_css():
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {THEME['dark_bg']};
        }}
        section[data-testid="stSidebar"] {{
            background-color: {THEME['dark_panel']};
            border-right: 1px solid {THEME['border']};
        }}
        h1, h2, h3 {{
            color: {THEME['text']};
        }}
        hr, div[data-testid="stDivider"] {{
            border-color: {THEME['border']} !important;
        }}

        /* --- Itens de navegação da sidebar como lista/sumário limpo --- */
        section[data-testid="stSidebar"] .nav-list button {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: {THEME['text_dim']} !important;
            text-align: left !important;
            font-weight: 400 !important;
            padding: 6px 10px !important;
            border-left: 3px solid transparent !important;
            border-radius: 4px !important;
            transition: all 0.15s ease-in-out;
        }}
        section[data-testid="stSidebar"] .nav-list button:hover {{
            background: {THEME['yellow_soft']} !important;
            color: {THEME['yellow']} !important;
        }}
        section[data-testid="stSidebar"] .nav-list button[kind="primary"] {{
            background: {THEME['yellow_soft']} !important;
            color: {THEME['yellow']} !important;
            font-weight: 600 !important;
            border-left: 3px solid {THEME['yellow']} !important;
        }}

        /* Botão de atualizar (fora da lista de navegação) mantém leve destaque */
        section[data-testid="stSidebar"] .refresh-btn button {{
            background: transparent !important;
            border: 1px solid {THEME['border']} !important;
            color: {THEME['text_dim']} !important;
        }}
        section[data-testid="stSidebar"] .refresh-btn button:hover {{
            border-color: {THEME['yellow']} !important;
            color: {THEME['yellow']} !important;
        }}

        /* Métricas */
        div[data-testid="stMetric"] {{
            background-color: {THEME['dark_panel']};
            border: 1px solid {THEME['border']};
            border-radius: 8px;
            padding: 12px 14px;
        }}
        div[data-testid="stMetricValue"] {{
            color: {THEME['yellow']} !important;
        }}

        /* Containers com borda (cards de alerta) */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: {THEME['dark_panel_2']};
            border-color: {THEME['border']} !important;
        }}

        /* Overlay fixo de notificações */
        .notification-shell-marker, .notification-panel-marker {{ display: none; }}
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .notification-shell-marker) {{
            position: fixed !important;
            top: 60px !important;
            right: 18px !important;
            width: 42px;
            height: 42px;
            z-index: 9999 !important;
            background: {THEME['dark_panel']};
            border: 1px solid {THEME['border']};
            border-radius: 8px;
            padding: 0 !important;
            gap: 0 !important;
        }}
        .notification-trigger-icon {{
            position: absolute; inset: 0; width: 42px; height: 42px;
            display: flex; align-items: center; justify-content: center;
            pointer-events: none;
        }}
        .notification-trigger-icon svg {{ display: block; }}
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .notification-shell-marker) .stButton {{ position: absolute; inset: 0; z-index: 1; }}
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .notification-shell-marker) .stButton button {{ width: 42px; height: 42px; opacity: 0; padding: 0; }}
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .notification-panel-marker) {{
            position: fixed !important; top: 112px !important; right: 18px !important; z-index: 9999 !important;
            width: min(320px, calc(100vw - 32px)); max-height: calc(100vh - 86px);
            overflow-y: auto; background: {THEME['dark_panel_2']};
            border: 1px solid {THEME['border']}; border-radius: 10px;
            box-shadow: 0 14px 32px rgba(0,0,0,.35); padding: 8px;
        }}
        .notification-summary {{
            list-style: none;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            padding: 12px 14px;
            color: {THEME['text']};
            background: {THEME['yellow_soft']};
            border-bottom: 1px solid {THEME['border']};
        }}
        .notification-card summary::-webkit-details-marker {{ display: none; }}
        .notification-title {{ display: flex; align-items: center; gap: 10px; font-weight: 700; }}
        .notification-icon {{
            width: 30px; height: 30px; display: inline-flex; align-items: center; justify-content: center;
            border-radius: 8px; background: {THEME['yellow']}; color: {THEME['dark_bg']};
            flex: 0 0 auto;
        }}
        .notification-count {{
            min-width: 24px; height: 24px; padding: 0 6px; border-radius: 999px;
            background: {THEME['yellow']}; color: {THEME['dark_bg']};
            font-size: 0.8rem; font-weight: 700; display: inline-flex; align-items: center; justify-content: center;
            border: 1px solid {THEME['dark_bg']};
        }}
        .notification-body {{ padding: 10px; max-height: calc(100vh - 170px); overflow-y: auto; }}
        .notification-empty {{ color: {THEME['text_dim']}; font-size: 0.92rem; padding: 4px 2px; }}
        .notification-entry {{
            display: flex; align-items: flex-start; gap: 10px;
            padding: 10px 8px; margin-bottom: 8px;
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 10px;
            text-decoration: none !important;
            width: 100%;
        }}
        .notification-entry:hover {{ border-color: {THEME['yellow']}; background: {THEME['yellow_soft']}; }}
        .notification-entry-title {{ color: {THEME['text']}; font-weight: 700; font-size: 0.92rem; }}
        .notification-entry-text {{ color: {THEME['text_dim']}; font-size: 0.85rem; margin-top: 2px; line-height: 1.35; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# Tabelas limpas para o usuário final
# =========================================================


def display_table(df: pd.DataFrame, rename: dict | None = None):
    if df is None or df.empty:
        st.info("Nenhum dado encontrado.")
        return
    d = df.copy()
    if rename:
        d = d.rename(columns=rename)
    currency_keywords = ("revenue", "receita", "cost", "custo", "price", "preço", "valor")
    currency_cols = [c for c in d.columns if any(k in c.lower() for k in currency_keywords)]
    pretty_map = {c: c.replace("_", " ").strip().title() for c in d.columns}
    d = d.rename(columns=pretty_map)
    col_config = {
        pretty_map[c]: st.column_config.NumberColumn(pretty_map[c], format="$ %.2f")
        for c in currency_cols
    }
    st.dataframe(d, use_container_width=True, hide_index=True, column_config=col_config)


# =========================================================
# Conexão com o banco (cacheada por sessão)
# =========================================================


def _build_cloud_sql_engine():
    from google.cloud.sql.connector import Connector

    connector = Connector()

    def getconn():
        return connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            password=DB_PASSWORD,
            db=DB_NAME,
        )

    return sqlalchemy.create_engine("postgresql+pg8000://", creator=getconn)


@st.cache_resource(show_spinner="Conectando ao banco de dados...")
def get_engine():
    if INSTANCE_CONNECTION_NAME:
        return _build_cloud_sql_engine()
    db_uri = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return sqlalchemy.create_engine(db_uri)


# =========================================================
# Camada de indicadores (KPIs) — cacheada para não bater no
# banco a cada rerender do Streamlit
# =========================================================


@st.cache_data(show_spinner=False, ttl=KPI_CACHE_TTL)
def load_dashboard_data(_engine):
    queries = {
        "equipment_status": """
            SELECT status, COUNT(*) AS total
            FROM equipment
            GROUP BY status
            ORDER BY total DESC
        """,
        "equipment_by_type": """
            SELECT type, COUNT(*) AS total, ROUND(AVG(hourly_rate), 2) AS avg_rate
            FROM equipment
            GROUP BY type
            ORDER BY total DESC
        """,
        "projects_status": """
            SELECT status, COUNT(*) AS total
            FROM projects
            GROUP BY status
            ORDER BY total DESC
        """,
        "projects_by_type": """
            SELECT project_type, COUNT(*) AS total
            FROM projects
            GROUP BY project_type
            ORDER BY total DESC
        """,
        "permits_status": """
            SELECT status, COUNT(*) AS total
            FROM permits
            GROUP BY status
            ORDER BY total DESC
        """,
        "service_requests_by_category": """
            SELECT sc.group_name, sc.name AS category, COUNT(sr.id) AS total_requests,
                   COALESCE(SUM(sr.final_cost), 0) AS revenue
            FROM service_requests sr
            JOIN service_categories sc ON sc.id = sr.service_category_id
            GROUP BY sc.group_name, sc.name
            ORDER BY revenue DESC
        """,
        "monthly_aggregate_revenue": """
            SELECT DATE_TRUNC('month', delivery_date)::date AS month,
                   SUM(total_price) AS revenue
            FROM aggregate_orders
            WHERE delivery_date IS NOT NULL
            GROUP BY 1
            ORDER BY 1
        """,
        "revenue_by_aggregate": """
            SELECT a.name, SUM(ao.total_price) AS revenue, SUM(ao.quantity) AS qty
            FROM aggregate_orders ao
            JOIN aggregates a ON a.id = ao.aggregate_id
            GROUP BY a.name
            ORDER BY revenue DESC
        """,
        "aggregate_stock": """
            SELECT name, stock_qty, reorder_point
            FROM aggregates
            ORDER BY stock_qty ASC
        """,
        "attention_low_stock": """
            SELECT sku, name, unit, stock_qty, reorder_point, last_updated
            FROM aggregates WHERE stock_qty <= reorder_point ORDER BY stock_qty ASC
        """,
        "attention_equipment_available": """
            SELECT id, name, type, hourly_rate, last_service_date
            FROM equipment WHERE status = 'available' ORDER BY name
        """,
        "attention_projects_active": """
            SELECT p.id, c.name AS client, p.site_address, p.project_type, p.status, p.start_date, p.est_completion
            FROM projects p LEFT JOIN clients c ON c.id = p.client_id
            WHERE p.status IN ('scheduled', 'in_progress') ORDER BY p.est_completion ASC NULLS LAST
        """,
        "attention_projects_overdue": """
            SELECT p.id, c.name AS client, p.site_address, p.project_type, p.status, p.est_completion
            FROM projects p LEFT JOIN clients c ON c.id = p.client_id
            WHERE p.est_completion < CURRENT_DATE AND p.status NOT IN ('completed')
            ORDER BY p.est_completion ASC
        """,
        "attention_services_overdue": """
            SELECT sr.id, p.site_address, sc.name AS service, sr.crew_name, sr.scheduled_date, sr.status
            FROM service_requests sr
            LEFT JOIN projects p ON p.id = sr.project_id
            LEFT JOIN service_categories sc ON sc.id = sr.service_category_id
            WHERE sr.scheduled_date < CURRENT_DATE AND sr.status = 'scheduled'
            ORDER BY sr.scheduled_date ASC
        """,
        "attention_equipment_maintenance": """
            SELECT id, name, type, last_service_date, hourly_rate
            FROM equipment WHERE status = 'maintenance' ORDER BY last_service_date ASC NULLS LAST
        """,
        "attention_permits_pending": """
            SELECT pe.id, p.site_address, pe.permit_type, pe.status, pe.submitted_date, pe.notes
            FROM permits pe LEFT JOIN projects p ON p.id = pe.project_id
            WHERE pe.status IN ('pending', 'submitted') ORDER BY pe.submitted_date ASC NULLS LAST
        """,
        "attention_aggregate_revenue": """
            SELECT ao.id, a.name AS aggregate, c.name AS client, ao.quantity, ao.total_price, ao.delivery_date
            FROM aggregate_orders ao
            LEFT JOIN aggregates a ON a.id = ao.aggregate_id
            LEFT JOIN clients c ON c.id = ao.client_id
            ORDER BY ao.delivery_date DESC NULLS LAST
        """,
        "attention_project_revenue": """
            SELECT p.id, p.site_address, p.project_type, p.status,
                   COALESCE(SUM(ao.total_price), 0) AS aggregate_revenue
            FROM projects p LEFT JOIN aggregate_orders ao ON ao.project_id = p.id
            GROUP BY p.id, p.site_address, p.project_type, p.status
            ORDER BY aggregate_revenue DESC
        """,
        "top_clients": """
            SELECT c.name, COALESCE(SUM(ao.total_price), 0) AS revenue
            FROM clients c
            LEFT JOIN aggregate_orders ao ON ao.client_id = c.id
            GROUP BY c.name
            ORDER BY revenue DESC
            LIMIT 10
        """,
        "crew_workload": """
            SELECT crew_name, COUNT(*) AS total_jobs,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed
            FROM service_requests
            WHERE crew_name IS NOT NULL
            GROUP BY crew_name
            ORDER BY total_jobs DESC
        """,
        "price_history": """
            SELECT a.name, aph.recorded_at, aph.price
            FROM aggregate_price_history aph
            JOIN aggregates a ON a.id = aph.aggregate_id
            ORDER BY a.name, aph.recorded_at
        """,
    }

    data = {}
    with _engine.connect() as conn:
        for key, sql in queries.items():
            try:
                data[key] = pd.read_sql(sql, conn)
            except Exception:
                data[key] = pd.DataFrame()

        scalar_queries = {
            "equipment_available": "SELECT COUNT(*) FROM equipment WHERE status = 'available'",
            "equipment_total": "SELECT COUNT(*) FROM equipment",
            "equipment_maintenance": "SELECT COUNT(*) FROM equipment WHERE status = 'maintenance'",
            "projects_active": "SELECT COUNT(*) FROM projects WHERE status IN ('scheduled', 'in_progress')",
            "projects_total": "SELECT COUNT(*) FROM projects",
            "projects_overdue": "SELECT COUNT(*) FROM projects WHERE est_completion < CURRENT_DATE AND status NOT IN ('completed')",
            "permits_pending": "SELECT COUNT(*) FROM permits WHERE status IN ('pending', 'submitted')",
            "aggregate_revenue_total": "SELECT COALESCE(SUM(total_price), 0) FROM aggregate_orders",
            "low_stock_count": "SELECT COUNT(*) FROM aggregates WHERE stock_qty <= reorder_point",
            "service_requests_overdue": "SELECT COUNT(*) FROM service_requests WHERE scheduled_date < CURRENT_DATE AND status = 'scheduled'",
            "clients_total": "SELECT COUNT(*) FROM clients",
        }
        scalars = {}
        for key, sql in scalar_queries.items():
            try:
                scalars[key] = conn.execute(sqlalchemy.text(sql)).scalar() or 0
            except Exception:
                scalars[key] = 0
        data["scalars"] = scalars

    return data


def compute_alerts(s: dict) -> list[dict]:
    alerts = []
    if s.get("low_stock_count", 0) > 0:
        sev = "high" if s["low_stock_count"] >= 3 else "medium"
        alerts.append({
            "severity": sev, "title": "Estoque baixo",
            "text": f"{s['low_stock_count']} agregado(s) abaixo do ponto de reposição.",
        })
    if s.get("projects_overdue", 0) > 0:
        alerts.append({
            "severity": "high", "title": "Projetos atrasados",
            "text": f"{s['projects_overdue']} projeto(s) com prazo de conclusão vencido.",
        })
    if s.get("service_requests_overdue", 0) > 0:
        alerts.append({
            "severity": "high", "title": "Serviços atrasados",
            "text": f"{s['service_requests_overdue']} solicitação(ões) de serviço atrasada(s).",
        })
    if s.get("equipment_maintenance", 0) > 0:
        alerts.append({
            "severity": "medium", "title": "Equipamentos em manutenção",
            "text": f"{s['equipment_maintenance']} equipamento(s) fora de operação.",
        })
    if s.get("permits_pending", 0) > 5:
        alerts.append({
            "severity": "medium", "title": "Permits pendentes",
            "text": f"{s['permits_pending']} permits aguardando aprovação.",
        })
    return alerts


ALERT_DESTINATIONS = {
    "Estoque baixo": ("low_stock", "Estoque com necessidade de reposição"),
    "Projetos atrasados": ("projects_overdue", "Projetos com prazo vencido"),
    "Serviços atrasados": ("services_overdue", "Solicitações de serviço atrasadas"),
    "Equipamentos em manutenção": ("equipment_maintenance", "Equipamentos em manutenção"),
    "Permits pendentes": ("permits_pending", "Permits aguardando aprovação"),
}

ATTENTION_SHEETS = {
    "equipment_available": ("Planilha de Equipamentos disponíveis", "wrench"),
    "projects_active": ("Planilha de Projetos ativos", "clipboard_list"),
    "low_stock": ("Planilha de Estoque baixo", "package"),
    "projects_overdue": ("Planilha de Projetos atrasados", "clipboard_list"),
    "services_overdue": ("Planilha de Serviços atrasados", "clipboard_list"),
    "equipment_maintenance": ("Planilha de Equipamentos em manutenção", "wrench"),
    "permits_pending": ("Planilha de Permits pendentes", "file_clock"),
    "aggregate_revenue": ("Planilha de Receita de agregados", "dollar"),
    "project_revenue": ("Planilha de Receita por projeto", "dollar"),
}


def render_card_link(container, target: str, key: str):
    with container:
        if st.button("Ver planilha", key=key, use_container_width=True):
            st.session_state.attention = target
            st.session_state.page = "Home"


def render_notification_overlay(alerts: list[dict]):
    count = len(alerts)
    with st.container():
        st.markdown('<div class="notification-shell-marker"></div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="notification-trigger-icon">{icon("bell", 21, THEME["yellow"])}</div>',
            unsafe_allow_html=True,
        )
        if st.button("Abrir notificações", key="notification_trigger", help=f"{count} notificações"):
            st.session_state.notifications_open = not st.session_state.get("notifications_open", False)

    if not st.session_state.get("notifications_open", False):
        return

    with st.container():
        st.markdown('<div class="notification-panel-marker"></div>', unsafe_allow_html=True)
        st.markdown("#### Notificações")
        if not alerts:
            st.markdown('<div class="notification-empty">Nenhum alerta ativo no momento.</div>', unsafe_allow_html=True)
        else:
            for alert in alerts:
                target, _ = ALERT_DESTINATIONS[alert["title"]]
                color = ALERT_COLORS.get(alert["severity"], "#64748b")
                _, alert_icon = ATTENTION_SHEETS[target]
                row_icon, row_button = st.columns([1, 12], vertical_alignment="center")
                with row_icon:
                    st.markdown(icon(alert_icon, 18, color), unsafe_allow_html=True)
                with row_button:
                    if st.button(
                        f"{alert['title']} — {alert['text']}",
                        key=f"notification_{target}",
                        use_container_width=True,
                    ):
                        st.session_state.attention = target
                        st.session_state.page = "Home"
                        st.session_state.notifications_open = False
                        st.rerun()


def render_attention_sheet(data: dict, target: str):
    sheet_name, sheet_icon = ATTENTION_SHEETS.get(
        target, ("Planilha de atenção", "clipboard_list")
    )
    st.markdown(
        f'<h2 style="display:flex;align-items:center;gap:8px;">'
        f'{icon(sheet_icon, 24, THEME["yellow"])}{sheet_name}</h2>',
        unsafe_allow_html=True,
    )
    if st.button("Voltar para a tela inicial", key="close_attention_sheet"):
        st.session_state.pop("attention", None)
        st.session_state.page = "Home"
        st.rerun()
    display_table(data.get(f"attention_{target}", pd.DataFrame()))


def render_sidebar_summary(data: dict):
    s = data["scalars"]
    st.caption("SUMÁRIO")
    rows = [
        ("Equip. disponíveis", f"{s['equipment_available']}/{s['equipment_total']}"),
        ("Projetos ativos", f"{s['projects_active']}/{s['projects_total']}"),
        ("Permits pendentes", s["permits_pending"]),
        ("Clientes", s["clients_total"]),
        ("Receita agregados", f"$ {s['aggregate_revenue_total']:,.0f}"),
    ]
    for label, value in rows:
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;font-size:0.82rem;'
            f'padding:3px 0;border-bottom:1px solid rgba(245,197,24,0.12);">'
            f'<span style="opacity:0.75;">{label}</span>'
            f'<strong style="color:{THEME["yellow"]};">{value}</strong></div>',
            unsafe_allow_html=True,
        )
def sidebar_refresh_button(key: str):
    st.markdown('<div class="refresh-btn">', unsafe_allow_html=True)
    icon_col, btn_col = st.columns([1, 5], vertical_alignment="center")
    with icon_col:
        st.markdown(icon("refresh", color=THEME["text_dim"]), unsafe_allow_html=True)
    with btn_col:
        clicked = st.button("Atualizar", key=key, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    if clicked:
        load_dashboard_data.clear()
        st.rerun()


# =========================================================
# Página: HOME — indicadores principais + alertas + gráficos
# =========================================================


import plotly.express as px
import streamlit as st


def render_home(data: dict):
    with st.sidebar:
        sidebar_refresh_button("refresh_home")

    s = data["scalars"]

    # 1. CABEÇALHO & EXPLICAÇÃO DO APP
    st.markdown(
        f'''
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:1.2rem;">
            <img width="27" height="27"
                 src="https://img.icons8.com/ios/50/crane.png"
                 style="filter: brightness(0) saturate(100%) invert(85%) sepia(77%) saturate(679%) hue-rotate(358deg) brightness(103%) contrast(96%);"
                 alt="crane"/>
            <span  style="font-weight:600; padding-top:2px; font-size:1.08rem; color:{THEME["yellow"]};">Central de Controle Operacional</span>
        </div>
        ''', 
        unsafe_allow_html=True
    )
    st.markdown(
        """
        Bem-vindo ao **Portal de Gestão Integrada**. Este painel consolida os principais indicadores da operação em tempo real:
        * **Frota de Equipamentos:** Disponibilidade e manutenção.
        * **Projetos e Licenças:** Acompanhamento de status, prazos e pendências de *permits*.
        * **Estoque e Suprimentos:** Níveis de agregados e pontos de reposição.
        * **Financeiro:** Receita gerada, média por projeto e curva de clientes.
        """
    )

    st.divider()

    attention = st.session_state.get("attention")
    if attention:
        render_attention_sheet(data, attention)
        st.divider()

    # 2. MÉTRICAS CHAVE (KPIS) AGRUPADAS
    st.subheader("Indicadores Principais")

    # Linha 1: Operações e Projetos
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric(
        "Equipamentos Disponíveis",
        f"{s['equipment_available']}/{s['equipment_total']}",
        help="Quantidade de equipamentos prontos para uso em relação ao total da frota.",
    )
    kpi2.metric(
        "Em Manutenção",
        s["equipment_maintenance"],
        delta="Atenção" if s["equipment_maintenance"] > 0 else "Ideal",
        delta_color="inverse" if s["equipment_maintenance"] > 0 else "normal",
        help="Equipamentos indisponíveis por manutenção preventiva ou corretiva.",
    )
    kpi3.metric(
        "Projetos Ativos",
        f"{s['projects_active']}/{s['projects_total']}",
        help="Projetos em andamento sobre o total cadastrado.",
    )
    kpi4.metric(
        "Projetos Atrasados",
        s["projects_overdue"],
        delta="Crítico" if s["projects_overdue"] > 0 else "No prazo",
        delta_color="inverse" if s["projects_overdue"] > 0 else "normal",
        help="Projetos com cronograma fora do prazo acordado.",
    )

    # Linha 2: Licenciamento, Estoque e Receita
    kpi5, kpi6, kpi7, kpi8 = st.columns(4)
    kpi5.metric(
        "Permits Pendentes",
        s["permits_pending"],
        help="Licenças ou autorizações aguardando aprovação.",
    )
    kpi6.metric(
        "Itens em Estoque Baixo",
        s["low_stock_count"],
        delta="Repor estoque" if s["low_stock_count"] > 0 else "OK",
        delta_color="inverse" if s["low_stock_count"] > 0 else "normal",
        help="Quantidade de materiais/agregados abaixo do ponto de reordenamento.",
    )

    receita_media = (
        (s["aggregate_revenue_total"] / s["projects_total"])
        if s["projects_total"]
        else 0
    )
    kpi7.metric(
        "Receita Agregados (Total)",
        f"${s['aggregate_revenue_total']:,.2f}",
        help="Faturamento total acumulado com venda de agregados.",
    )
    kpi8.metric(
        "Receita Média / Projeto",
        f"${receita_media:,.2f}",
        help="Média de faturamento gerado por projeto ativo.",
    )

    # Cada card leva à planilha detalhada correspondente.
    render_card_link(kpi1, "equipment_available", "card_equipment_available")
    render_card_link(kpi2, "equipment_maintenance", "card_equipment_maintenance")
    render_card_link(kpi3, "projects_active", "card_projects_active")
    render_card_link(kpi4, "projects_overdue", "card_projects_overdue")
    render_card_link(kpi5, "permits_pending", "card_permits_pending")
    render_card_link(kpi6, "low_stock", "card_low_stock")
    render_card_link(kpi7, "aggregate_revenue", "card_aggregate_revenue")
    render_card_link(kpi8, "project_revenue", "card_project_revenue")

    # Exibe imediatamente a planilha escolhida por um dos cards nesta mesma interação.
    if st.session_state.get("attention") and not attention:
        st.divider()
        render_attention_sheet(data, st.session_state.attention)

    st.divider()

    # 4. VISUALIZAÇÕES DETALHADAS ORGANIZADAS EM ABAS
    st.subheader("Análise Detalhada")
    tab_operacoes, tab_financeiro = st.tabs(
        ["Operações, Projetos & Permits", "Financeiro & Estoque"]
    )

    # --- ABA 1: OPERAÇÕES E PROJETOS ---
    with tab_operacoes:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Status da Frota de Equipamentos")
            df = data["equipment_status"]
            if not df.empty:
                fig = px.pie(
                    df,
                    names="status",
                    values="total",
                    hole=0.45,
                    color_discrete_sequence=[
                        THEME["yellow"],
                        "#7A7D84",
                        "#4A4D54",
                        "#B8860B",
                    ],
                )
                fig.update_traces(textinfo="percent+label")
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color=THEME["text"],
                    margin=dict(t=20, b=20, l=10, r=10),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhum dado de equipamento disponível no momento.")

        with col2:
            st.markdown("#### Distribuição de Projetos por Status")
            df = data["projects_status"]
            if not df.empty:
                fig = px.bar(
                    df,
                    x="status",
                    y="total",
                    text="total",
                    color_discrete_sequence=[THEME["yellow"]],
                )
                fig.update_layout(
                    showlegend=False,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color=THEME["text"],
                    margin=dict(t=20, b=20, l=10, r=10),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhum dado de projeto disponível no momento.")

        col3, col4 = st.columns(2)
        with col3:
            st.markdown("#### Situação das Licenças (Permits)")
            df = data["permits_status"]
            if not df.empty:
                fig = px.pie(
                    df,
                    names="status",
                    values="total",
                    hole=0.4,
                    color_discrete_sequence=[
                        THEME["yellow"],
                        "#7A7D84",
                        "#4A4D54",
                        "#B8860B",
                    ],
                )
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color=THEME["text"],
                    margin=dict(t=20, b=20, l=10, r=10),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhum dado de permit disponível no momento.")

        with col4:
            st.markdown("#### Chamados de Serviços Atrasados")
            st.metric(
                "Serviços PENDENTES / Atrasados",
                s["service_requests_overdue"],
                delta=(
                    f"{s['service_requests_overdue']} em atraso"
                    if s["service_requests_overdue"] > 0
                    else "Sem atrasos"
                ),
                delta_color=(
                    "inverse" if s["service_requests_overdue"] > 0 else "normal"
                ),
                help="Quantidade de solicitações de serviço com prazo expirado.",
            )

    # --- ABA 2: FINANCEIRO E ESTOQUE ---
    with tab_financeiro:
        col5, col6 = st.columns(2)
        with col5:
            st.markdown("#### Evolução Mensal da Receita (Agregados)")
            df = data["monthly_aggregate_revenue"]
            if not df.empty:
                fig = px.line(
                    df,
                    x="month",
                    y="revenue",
                    markers=True,
                    color_discrete_sequence=[THEME["yellow"]],
                )
                fig.update_yaxes(tickprefix="$")
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color=THEME["text"],
                    margin=dict(t=20, b=20, l=10, r=10),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhum dado de receita disponível no momento.")

        with col6:
            st.markdown("#### Top 5 Clientes por Faturamento")
            df = data["top_clients"].head(5)
            if not df.empty:
                fig = px.bar(
                    df.sort_values("revenue"),
                    x="revenue",
                    y="name",
                    orientation="h",
                    color_discrete_sequence=[THEME["yellow"]],
                )
                fig.update_layout(
                    xaxis_tickprefix="$",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color=THEME["text"],
                    margin=dict(t=20, b=20, l=10, r=10),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhum dado de clientes disponível no momento.")

        st.markdown("#### Nível de Estoque vs. Ponto de Reposição por Agregado")
        df = data["aggregate_stock"]
        if not df.empty:
            fig = px.bar(
                df,
                x="name",
                y=["stock_qty", "reorder_point"],
                barmode="group",
                labels={
                    "value": "Quantidade",
                    "name": "Tipo de Agregado",
                    "variable": "Métrica",
                },
                color_discrete_sequence=[THEME["yellow"], "#7A7D84"],
            )
            fig.update_layout(
                xaxis_tickangle=-30,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color=THEME["text"],
                margin=dict(t=20, b=20, l=10, r=10),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhum dado de estoque disponível no momento.")
# =========================================================
# Página: Power Bi — dashboards mais detalhados
# =========================================================


def render_bi(data: dict):
    with st.sidebar:
        sidebar_refresh_button("refresh_bi")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Serviços & Receita", "Clientes", "Equipamentos & Equipes", "Agregados"]
    )

    with tab1:
        st.subheader("Receita e volume por categoria de serviço")
        df = data["service_requests_by_category"]
        if not df.empty:
            fig = px.bar(
                df, x="category", y="revenue", color="group_name",
                hover_data=["total_requests"], text_auto=".2s",
                color_discrete_sequence=[THEME["yellow"], "#7A7D84", "#4A4D54", "#B8860B"],
            )
            fig.update_layout(xaxis_tickangle=-30, yaxis_tickprefix="$",
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color=THEME["text"])
            st.plotly_chart(fig, use_container_width=True)
            display_table(df, rename={
                "group_name": "Grupo", "category": "Categoria",
                "total_requests": "Solicitações", "revenue": "Receita",
            })
        else:
            st.info("Sem dados de solicitações de serviço.")

        st.subheader("Projetos por tipo")
        df = data["projects_by_type"]
        if not df.empty:
            fig = px.bar(df, x="project_type", y="total", text="total",
                         color_discrete_sequence=[THEME["yellow"]])
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color=THEME["text"])
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Permits por status")
        df = data["permits_status"]
        if not df.empty:
            fig = px.pie(df, names="status", values="total", hole=0.4,
                         color_discrete_sequence=[THEME["yellow"], "#7A7D84", "#4A4D54", "#B8860B"])
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color=THEME["text"])
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Top 10 clientes por receita")
        df = data["top_clients"]
        if not df.empty:
            fig = px.bar(df.sort_values("revenue"), x="revenue", y="name", orientation="h",
                         color_discrete_sequence=[THEME["yellow"]])
            fig.update_layout(xaxis_tickprefix="$", paper_bgcolor="rgba(0,0,0,0)",
                               plot_bgcolor="rgba(0,0,0,0)", font_color=THEME["text"])
            st.plotly_chart(fig, use_container_width=True)
            display_table(df, rename={"name": "Cliente", "revenue": "Receita"})
        else:
            st.info("Sem dados de clientes.")

    with tab3:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Equipamentos por tipo")
            df = data["equipment_by_type"]
            if not df.empty:
                fig = px.bar(df, x="type", y="total", hover_data=["avg_rate"], text="total",
                             color_discrete_sequence=[THEME["yellow"]])
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   font_color=THEME["text"])
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("Produtividade das equipes")
            df = data["crew_workload"]
            if not df.empty:
                fig = px.bar(df, x="crew_name", y=["total_jobs", "completed"], barmode="group",
                             color_discrete_sequence=[THEME["yellow"], "#7A7D84"])
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   font_color=THEME["text"])
                st.plotly_chart(fig, use_container_width=True)

    with tab4:
        st.subheader("Receita por tipo de agregado")
        df = data["revenue_by_aggregate"]
        if not df.empty:
            fig = px.bar(df.sort_values("revenue"), x="revenue", y="name", orientation="h",
                         color_discrete_sequence=[THEME["yellow"]])
            fig.update_layout(xaxis_tickprefix="$", paper_bgcolor="rgba(0,0,0,0)",
                               plot_bgcolor="rgba(0,0,0,0)", font_color=THEME["text"])
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Histórico de preços por agregado")
        df = data["price_history"]
        if not df.empty:
            options = sorted(df["name"].unique().tolist())
            selected_agg = st.multiselect("Selecione agregados", options, default=options[:3])
            filtered = df[df["name"].isin(selected_agg)] if selected_agg else df
            fig = px.line(filtered, x="recorded_at", y="price", color="name", markers=True,
                          color_discrete_sequence=[THEME["yellow"], "#7A7D84", "#B8860B", "#4A4D54"])
            fig.update_yaxes(tickprefix="$")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color=THEME["text"])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem histórico de preços.")


# =========================================================
# Assistente de insights (OpenRouter)
# =========================================================


def call_openrouter(messages: list[dict], model: str, temperature: float = 0.3, max_tokens: int = 900) -> str:
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def build_dashboard_context(data: dict) -> str:
    parts = [f"scalars: {json.dumps(data.get('scalars', {}), default=str)}"]
    for key, df in data.items():
        if key == "scalars" or df is None or df.empty:
            continue
        sample = df.head(8).to_dict(orient="records")
        parts.append(f"{key} (colunas: {list(df.columns)}): {json.dumps(sample, default=str)}")
    return "\n".join(parts)


CHART_BLOCK_RE = re.compile(r"```chart\s*(\{.*?\})\s*```", re.DOTALL)


def extract_chart_spec(reply: str):
    match = CHART_BLOCK_RE.search(reply)
    if not match:
        return reply.strip(), None
    text = CHART_BLOCK_RE.sub("", reply).strip()
    try:
        spec = json.loads(match.group(1))
    except Exception:
        spec = None
    return text, spec


def build_chart_from_spec(spec: dict, data: dict):
    if not spec:
        return None
    try:
        df = data.get(spec.get("data_key"))
        if df is None or df.empty:
            return None
        x, y = spec.get("x"), spec.get("y")
        if x not in df.columns or (y and y not in df.columns):
            return None
        chart_type = spec.get("type", "bar")
        title = spec.get("title", "")
        if chart_type == "line":
            fig = px.line(df, x=x, y=y, title=title, markers=True,
                          color_discrete_sequence=[THEME["yellow"]])
        elif chart_type == "pie":
            fig = px.pie(df, names=x, values=y, title=title,
                        color_discrete_sequence=[THEME["yellow"], "#7A7D84", "#4A4D54", "#B8860B"])
        else:
            fig = px.bar(df, x=x, y=y, title=title, color_discrete_sequence=[THEME["yellow"]])
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font_color=THEME["text"])
        return fig
    except Exception:
        return None


def ask_ai(question: str, data: dict, model: str):
    context = build_dashboard_context(data)
    system = (
        "Você é um analista de BI de uma empresa de terraplenagem, perfuração, água/fossas, "
        "paisagismo e venda de agregados. Você recebe abaixo indicadores e tabelas já agregados "
        "do negócio (formato chave: colunas e amostra de dados). Responda SEMPRE em português, "
        "de forma objetiva, com números concretos, tendências e, quando fizer sentido, "
        "recomendações práticas.\n\n"
        "Se um gráfico ajudar a ilustrar sua resposta, inclua ao final um bloco exatamente neste "
        "formato:\n```chart\n"
        '{"data_key": "<uma_das_chaves_abaixo>", "type": "bar|line|pie", '
        '"x": "<coluna>", "y": "<coluna>", "title": "<título>"}\n'
        "```\n"
        "Use apenas chaves e nomes de coluna que existem nos dados abaixo. Se um gráfico não "
        "ajudar, não inclua o bloco.\n\nDados disponíveis:\n" + context
    )
    reply = call_openrouter(
        [{"role": "system", "content": system}, {"role": "user", "content": question}],
        model=model,
    )
    text, spec = extract_chart_spec(reply)
    fig = build_chart_from_spec(spec, data)
    return text, fig


def render_ai(data: dict):
    with st.sidebar:
        model = st.selectbox("Modelo (OpenRouter)", OPENROUTER_MODELS, index=0)

        st.markdown('<div class="refresh-btn">', unsafe_allow_html=True)
        icon_col, btn_col = st.columns([1, 5], vertical_alignment="center")
        with icon_col:
            st.markdown(icon("trash", color=THEME["text_dim"]), unsafe_allow_html=True)
        with btn_col:
            if st.button("Limpar conversa", key="clear_chat", use_container_width=True):
                st.session_state.messages = []
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        st.caption("Exemplos de perguntas:")
        for question in EXAMPLE_QUESTIONS:
            st.caption(f"• {question}")

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;opacity:0.75;font-size:0.9rem;">'
        f'{icon("sparkles", 16, color=THEME["yellow"])}<span>Insights gerados a partir dos indicadores do negócio via OpenRouter</span></div>',
        unsafe_allow_html=True,
    )

    if not OPENROUTER_API_KEY:
        st.warning("Configure a variável de ambiente OPENROUTER_API_KEY para habilitar o assistente.")
        return

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("figure") is not None:
                st.plotly_chart(message["figure"], use_container_width=True)

    if not st.session_state.messages:
        st.write("Experimente uma dessas perguntas:")
        cols = st.columns(len(EXAMPLE_QUESTIONS))
        for col, question in zip(cols, EXAMPLE_QUESTIONS):
            if col.button(question):
                st.session_state.pending_question = question
                st.rerun()

    user_input = st.chat_input("Pergunte sobre o panorama do negócio...")

    if "pending_question" in st.session_state:
        user_input = st.session_state.pop("pending_question")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            answer, fig = "", None
            with st.spinner("Analisando os dados..."):
                try:
                    answer, fig = ask_ai(user_input, data, model)
                except Exception:
                    answer = "Não consegui gerar uma resposta agora. Tente novamente em instantes."

            st.markdown(answer)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)

        st.session_state.messages.append({"role": "assistant", "content": answer, "figure": fig})


# =========================================================
# Configuração da página
# =========================================================

st.set_page_config(
    page_title="Intelligent Site Services Copilot",
    page_icon=None,
    layout="wide",
)

inject_theme_css()

try:
    engine = get_engine()
except Exception:
    st.error("Não foi possível conectar ao sistema agora. Tente novamente em instantes.")
    st.stop()

with st.spinner("Carregando indicadores..."):
    dashboard_data = load_dashboard_data(engine)

if "page" not in st.session_state:
    st.session_state.page = "Home"
if "attention" not in st.session_state:
    st.session_state.attention = None

attention_active = bool(st.session_state.attention)

if not attention_active:
    st.title("Intelligent Site Services Copilot")
render_notification_overlay(compute_alerts(dashboard_data["scalars"]))

NAV_ITEMS = [("Home", "home"), ("Power Bi", "bar_chart"), ("AI", "message_square")]

with st.sidebar:
    st.markdown(
    f'''
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:1.2rem;">
        <img width="27" height="27"
             src="https://img.icons8.com/ios/50/crane.png"
             style="filter: brightness(0) saturate(100%) invert(85%) sepia(77%) saturate(679%) hue-rotate(358deg) brightness(103%) contrast(96%);"
             alt="crane"/>
        <span  style="font-weight:600; padding-top:2px; font-size:1.08rem; color:{THEME["yellow"]};">Site Services Copilot</span>
    </div>
    ''', 
    unsafe_allow_html=True
)

    st.markdown('<div class="nav-list">', unsafe_allow_html=True)
    for label, icon_name in NAV_ITEMS:
        is_active = st.session_state.page == label
        icon_col, btn_col = st.columns([1, 5], vertical_alignment="center")
        with icon_col:
            st.markdown(
                icon(icon_name, color=THEME["yellow"] if is_active else THEME["text_dim"]),
                unsafe_allow_html=True,
            )
        with btn_col:
            if st.button(
                label, key=f"nav_{label}", use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.page = label
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    render_sidebar_summary(dashboard_data)

selected = st.session_state.page

# =========================================================
# Roteamento
# =========================================================

if st.session_state.attention:
    render_attention_sheet(dashboard_data, st.session_state.attention)
elif selected == "Home":
    render_home(dashboard_data)
elif selected == "Power Bi":
    render_bi(dashboard_data)
else:
    render_ai(dashboard_data)
