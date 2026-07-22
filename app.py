import json
import os
import re

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

INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME", "")
KPI_CACHE_TTL = int(os.environ.get("KPI_CACHE_TTL_SECONDS", "300"))

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_MODELS = [
    OPENROUTER_DEFAULT_MODEL,
    "anthropic/claude-3.5-sonnet",
    "google/gemini-flash-1.5",
    "meta-llama/llama-3.1-70b-instruct",
]
OPENROUTER_MODELS = list(dict.fromkeys(OPENROUTER_MODELS))

EXAMPLE_QUESTIONS = {
    "en": [
        "Give me a business overview.",
        "Which equipment needs attention?",
        "Show revenue by service category.",
    ],
    "pt": [
        "Qual o panorama geral do negócio?",
        "Quais equipamentos precisam de atenção?",
        "Mostre a receita por categoria.",
    ],
}

# =========================================================
# Paleta "canteiro de obras"
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
# TRANSLATIONS
# =========================================================

if "language" not in st.session_state:
    st.session_state.language = "en"

TRANSLATIONS = {
    "pt": {
        "Home": "Home",
        "Power BI": "Power BI",
        "AI": "IA",
        "Refresh": "Atualizar",
        "Summary": "Resumo",
        "Equipment Available": "Equipamentos Disponíveis",
        "Equipment Under Maintenance": "Equipamentos em Manutenção",
        "Active Projects": "Projetos Ativos",
        "Overdue Projects": "Projetos Atrasados",
        "Pending Permits": "Permits Pendentes",
        "Low Stock Items": "Itens com Estoque Baixo",
        "Aggregate Revenue": "Receita de Agregados",
        "Average Revenue per Project": "Receita Média por Projeto",
        "Operations": "Operações",
        "Projects": "Projetos",
        "Finance": "Financeiro",
        "Inventory": "Estoque",
        "Clients": "Clientes",
        "Notifications": "Notificações",
        "Open Notifications": "Abrir Notificações",
        "No active alerts": "Nenhum alerta ativo.",
        "View Spreadsheet": "Ver Planilha",
        "Return Home": "Voltar para Home",
        "Detailed Analysis": "Análise Detalhada",
        "Operations, Projects & Permits": "Operações, Projetos e Permits",
        "Finance & Inventory": "Financeiro e Estoque",
        "Equipment Status": "Status dos Equipamentos",
        "Project Status": "Status dos Projetos",
        "Permit Status": "Status dos Permits",
        "Monthly Revenue": "Receita Mensal",
        "Top Clients": "Melhores Clientes",
        "Stock Levels": "Níveis de Estoque",
        "Service Categories": "Categorias de Serviços",
        "Revenue": "Receita",
        "Question Examples": "Exemplos de Perguntas",
        "Clear Conversation": "Limpar Conversa",
        "Ask about your business...": "Pergunte sobre o negócio...",
    },
    "en": {
        "Home": "Home",
        "Power BI": "Power BI",
        "AI": "AI",
        "Refresh": "Refresh",
        "Summary": "Summary",
        "Equipment Available": "Equipment Available",
        "Equipment Under Maintenance": "Equipment Under Maintenance",
        "Active Projects": "Active Projects",
        "Overdue Projects": "Overdue Projects",
        "Pending Permits": "Pending Permits",
        "Low Stock Items": "Low Stock Items",
        "Aggregate Revenue": "Aggregate Revenue",
        "Average Revenue per Project": "Average Revenue per Project",
        "Operations": "Operations",
        "Projects": "Projects",
        "Finance": "Finance",
        "Inventory": "Inventory",
        "Clients": "Clients",
        "Notifications": "Notifications",
        "Open Notifications": "Open Notifications",
        "No active alerts": "No active alerts.",
        "View Spreadsheet": "View Spreadsheet",
        "Return Home": "Return Home",
        "Detailed Analysis": "Detailed Analysis",
        "Operations, Projects & Permits": "Operations, Projects & Permits",
        "Finance & Inventory": "Finance & Inventory",
        "Equipment Status": "Equipment Status",
        "Project Status": "Project Status",
        "Permit Status": "Permit Status",
        "Monthly Revenue": "Monthly Revenue",
        "Top Clients": "Top Clients",
        "Stock Levels": "Inventory Levels",
        "Service Categories": "Service Categories",
        "Revenue": "Revenue",
        "Question Examples": "Question Examples",
        "Clear Conversation": "Clear Conversation",
        "Ask about your business...": "Ask about your business...",
    },
}

def tr(text):
    lang = st.session_state.get("language", "en")
    return TRANSLATIONS.get(lang, {}).get(text, text)

# =========================================================
# Ícones
# =========================================================

_LUCIDE = {
    "home": '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "bar_chart": '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "message_square": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "refresh": '<path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
    "package": '<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    "clipboard_list": '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2"/><path d="M9 12h6"/><path d="M9 16h6"/><path d="M9 8h.01"/><path d="M9 20h.01"/>',
    "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94z"/>',
    "file_clock": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v6h6"/><circle cx="12" cy="16" r="3"/><path d="M12 14.5v1.7l1.1.7"/>',
    "dollar": '<line x1="12" x2="12" y1="2" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
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
# CSS global — Posicionamento e ajuste anti-quebra de texto
# =========================================================

def inject_theme_css():
    st.markdown(
        f"""
        <style>
        .stApp {{ background-color: {THEME['dark_bg']}; }}
        section[data-testid="stSidebar"] {{
            background-color: {THEME['dark_panel']};
            border-right: 1px solid {THEME['border']};
        }}
        h1, h2, h3 {{ color: {THEME['text']}; }}
        hr, div[data-testid="stDivider"] {{ border-color: {THEME['border']} !important; }}

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

        section[data-testid="stSidebar"] .refresh-btn button {{
            background: transparent !important;
            border: 1px solid {THEME['border']} !important;
            color: {THEME['text_dim']} !important;
        }}
        section[data-testid="stSidebar"] .refresh-btn button:hover {{
            border-color: {THEME['yellow']} !important;
            color: {THEME['yellow']} !important;
        }}

        div[data-testid="stMetric"] {{
            background-color: {THEME['dark_panel']};
            border: 1px solid {THEME['border']};
            border-radius: 8px;
            padding: 12px 14px;
        }}
        div[data-testid="stMetricValue"] {{ color: {THEME['yellow']} !important; }}

        /* --- BARRA FIXA NO CANTO SUPERIOR DIREITO --- */
        .top-right-marker, .notification-panel-marker {{ display: none; }}
        
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .top-right-marker) {{
            position: fixed !important;
            top: 55px !important;
            right: 20px !important;
            z-index: 1000000 !important;
            background: {THEME['dark_panel']};
            border: 1px solid {THEME['border']};
            border-radius: 20px;
            padding: 4px 12px !important;
            box-shadow: 0 4px 14px rgba(0,0,0,0.4);
            width: fit-content !important;
        }}

        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .top-right-marker) [data-testid="stHorizontalBlock"] {{
            gap: 6px !important;
            align-items: center !important;
            flex-wrap: nowrap !important;
            width: fit-content !important;
        }}

        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .top-right-marker) [data-testid="column"] {{
            width: auto !important;
            min-width: auto !important;
            flex: 0 0 auto !important;
            padding: 0 !important;
        }}

        /* PREVENÇÃO DE QUEBRA DE LINHA DOS BOTÕES (EN/PT/SINO) */
        .lang-switch-btn button, .notification-btn button {{
            background: transparent !important;
            border: none !important;
            padding: 2px 8px !important;
            font-size: 0.82rem !important;
            font-weight: 600 !important;
            min-height: unset !important;
            height: 28px !important;
            min-width: 38px !important; /* CORRIGIDO: Garante largura suficiente para "EN" */
            width: auto !important;
            box-shadow: none !important;
            white-space: nowrap !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
        }}
        
        .lang-switch-btn button p, .notification-btn button p {{
            white-space: nowrap !important;
            word-break: keep-all !important;
            margin: 0 !important;
            font-size: 0.82rem !important;
            line-height: 1 !important;
        }}

        .lang-active button {{ color: {THEME['yellow']} !important; }}
        .lang-inactive button {{ color: {THEME['text_dim']} !important; }}
        .lang-inactive button:hover {{ color: {THEME['text']} !important; }}
        
        .lang-divider {{
            color: {THEME['text_dim']};
            font-size: 0.8rem;
            opacity: 0.4;
            padding: 0 2px;
            user-select: none;
            display: inline-block;
            line-height: 24px;
        }}

        .notification-btn button {{
            color: {THEME['yellow']} !important;
            font-weight: 700 !important;
            min-width: 48px !important;
        }}
        .notification-btn button:hover {{ opacity: 0.85; }}

        /* Painel suspenso Notificações */
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .notification-panel-marker) {{
            position: fixed !important; 
            top: 95px !important; 
            right: 20px !important; 
            z-index: 99999 !important;
            width: min(380px, calc(100vw - 32px)) !important; /* CORRIGIDO: Mais espaço para texto longo */
            max-height: calc(100vh - 120px);
            overflow-y: auto; 
            background: {THEME['dark_panel_2']};
            border: 1px solid {THEME['border']}; 
            border-radius: 12px;
            box-shadow: 0 14px 32px rgba(0,0,0,.5); 
            padding: 16px !important;
        }}

        /* Estilização dos botões dentro do painel de notificações */
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .notification-panel-marker) button {{
            text-align: left !important;
            justify-content: flex-start !important;
            padding: 10px 12px !important;
            height: auto !important;
            min-height: 44px !important;
            white-space: normal !important;
            word-break: normal !important;
            line-height: 1.35 !important;
            border: 1px solid {THEME['border']} !important;
            background: {THEME['dark_panel']} !important;
            border-radius: 8px !important;
            transition: all 0.2s ease;
        }}

        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .notification-panel-marker) button:hover {{
            border-color: {THEME['yellow']} !important;
            background: {THEME['yellow_soft']} !important;
        }}

        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .notification-panel-marker) button p {{
            text-align: left !important;
            white-space: normal !important;
            font-size: 0.83rem !important;
            font-weight: 500 !important;
            color: {THEME['text']} !important;
            margin: 0 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

# =========================================================
# Banco de Dados & Cache
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

def _build_cloud_sql_engine():
    from google.cloud.sql.connector import Connector
    connector = Connector()
    def getconn():
        return connector.connect(
            INSTANCE_CONNECTION_NAME, "pg8000",
            user=DB_USER, password=DB_PASSWORD, db=DB_NAME,
        )
    return sqlalchemy.create_engine("postgresql+pg8000://", creator=getconn)

@st.cache_resource(show_spinner="Conectando ao banco de dados...")
def get_engine():
    if INSTANCE_CONNECTION_NAME:
        return _build_cloud_sql_engine()
    db_uri = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return sqlalchemy.create_engine(db_uri)

@st.cache_data(show_spinner=False, ttl=KPI_CACHE_TTL)
def load_dashboard_data(_engine):
    queries = {
        "equipment_status": "SELECT status, COUNT(*) AS total FROM equipment GROUP BY status ORDER BY total DESC",
        "equipment_by_type": "SELECT type, COUNT(*) AS total, ROUND(AVG(hourly_rate), 2) AS avg_rate FROM equipment GROUP BY type ORDER BY total DESC",
        "projects_status": "SELECT status, COUNT(*) AS total FROM projects GROUP BY status ORDER BY total DESC",
        "projects_by_type": "SELECT project_type, COUNT(*) AS total FROM projects GROUP BY project_type ORDER BY total DESC",
        "permits_status": "SELECT status, COUNT(*) AS total FROM permits GROUP BY status ORDER BY total DESC",
        "service_requests_by_category": """
            SELECT sc.group_name, sc.name AS category, COUNT(sr.id) AS total_requests,
                   COALESCE(SUM(sr.final_cost), 0) AS revenue
            FROM service_requests sr
            JOIN service_categories sc ON sc.id = sr.service_category_id
            GROUP BY sc.group_name, sc.name ORDER BY revenue DESC
        """,
        "monthly_aggregate_revenue": "SELECT DATE_TRUNC('month', delivery_date)::date AS month, SUM(total_price) AS revenue FROM aggregate_orders WHERE delivery_date IS NOT NULL GROUP BY 1 ORDER BY 1",
        "revenue_by_aggregate": "SELECT a.name, SUM(ao.total_price) AS revenue, SUM(ao.quantity) AS qty FROM aggregate_orders ao JOIN aggregates a ON a.id = ao.aggregate_id GROUP BY a.name ORDER BY revenue DESC",
        "aggregate_stock": "SELECT name, stock_qty, reorder_point FROM aggregates ORDER BY stock_qty ASC",
        "attention_low_stock": "SELECT sku, name, unit, stock_qty, reorder_point, last_updated FROM aggregates WHERE stock_qty <= reorder_point ORDER BY stock_qty ASC",
        "attention_equipment_available": "SELECT id, name, type, hourly_rate, last_service_date FROM equipment WHERE status = 'available' ORDER BY name",
        "attention_projects_active": "SELECT p.id, c.name AS client, p.site_address, p.project_type, p.status, p.start_date, p.est_completion FROM projects p LEFT JOIN clients c ON c.id = p.client_id WHERE p.status IN ('scheduled', 'in_progress') ORDER BY p.est_completion ASC NULLS LAST",
        "attention_projects_overdue": "SELECT p.id, c.name AS client, p.site_address, p.project_type, p.status, p.est_completion FROM projects p LEFT JOIN clients c ON c.id = p.client_id WHERE p.est_completion < CURRENT_DATE AND p.status NOT IN ('completed') ORDER BY p.est_completion ASC",
        "attention_services_overdue": "SELECT sr.id, p.site_address, sc.name AS service, sr.crew_name, sr.scheduled_date, sr.status FROM service_requests sr LEFT JOIN projects p ON p.id = sr.project_id LEFT JOIN service_categories sc ON sc.id = sr.service_category_id WHERE sr.scheduled_date < CURRENT_DATE AND sr.status = 'scheduled' ORDER BY sr.scheduled_date ASC",
        "attention_equipment_maintenance": "SELECT id, name, type, last_service_date, hourly_rate FROM equipment WHERE status = 'maintenance' ORDER BY last_service_date ASC NULLS LAST",
        "attention_permits_pending": "SELECT pe.id, p.site_address, pe.permit_type, pe.status, pe.submitted_date, pe.notes FROM permits pe LEFT JOIN projects p ON p.id = pe.project_id WHERE pe.status IN ('pending', 'submitted') ORDER BY pe.submitted_date ASC NULLS LAST",
        "attention_aggregate_revenue": "SELECT ao.id, a.name AS aggregate, c.name AS client, ao.quantity, ao.total_price, ao.delivery_date FROM aggregate_orders ao LEFT JOIN aggregates a ON a.id = ao.aggregate_id LEFT JOIN clients c ON c.id = ao.client_id ORDER BY ao.delivery_date DESC NULLS LAST",
        "attention_project_revenue": "SELECT p.id, p.site_address, p.project_type, p.status, COALESCE(SUM(ao.total_price), 0) AS aggregate_revenue FROM projects p LEFT JOIN aggregate_orders ao ON ao.project_id = p.id GROUP BY p.id, p.site_address, p.project_type, p.status ORDER BY aggregate_revenue DESC",
        "top_clients": "SELECT c.name, COALESCE(SUM(ao.total_price), 0) AS revenue FROM clients c LEFT JOIN aggregate_orders ao ON ao.client_id = c.id GROUP BY c.name ORDER BY revenue DESC LIMIT 10",
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

# =========================================================
# Alertas e Notificações
# =========================================================

def compute_alerts(s: dict) -> list[dict]:
    en = st.session_state.language == "en"
    alerts = []
    if s.get("low_stock_count", 0) > 0:
        alerts.append({
            "severity": "high" if s["low_stock_count"] >= 3 else "medium",
            "title": "Low Inventory" if en else "Estoque baixo",
            "text": f"{s['low_stock_count']} inventory item(s) below reorder point." if en else f"{s['low_stock_count']} agregado(s) abaixo do ponto de reposição."
        })
    if s.get("projects_overdue", 0) > 0:
        alerts.append({
            "severity": "high",
            "title": "Overdue Projects" if en else "Projetos atrasados",
            "text": f"{s['projects_overdue']} project(s) overdue." if en else f"{s['projects_overdue']} projeto(s) com prazo vencido."
        })
    if s.get("service_requests_overdue", 0) > 0:
        alerts.append({
            "severity": "high",
            "title": "Overdue Services" if en else "Serviços atrasados",
            "text": f"{s['service_requests_overdue']} service request(s) overdue." if en else f"{s['service_requests_overdue']} solicitação(ões) atrasada(s)."
        })
    if s.get("equipment_maintenance", 0) > 0:
        alerts.append({
            "severity": "medium",
            "title": "Equipment Maintenance" if en else "Equipamentos em manutenção",
            "text": f"{s['equipment_maintenance']} equipment under maintenance." if en else f"{s['equipment_maintenance']} equipamento(s) em manutenção."
        })
    if s.get("permits_pending", 0) > 5:
        alerts.append({
            "severity": "medium",
            "title": "Pending Permits" if en else "Permits pendentes",
            "text": f"{s['permits_pending']} permits awaiting approval." if en else f"{s['permits_pending']} permits aguardando aprovação."
        })
    return alerts

ALERT_DESTINATIONS = {
    "Estoque baixo": ("low_stock", "Estoque com necessidade de reposição"),
    "Low Inventory": ("low_stock", "Estoque com necessidade de reposição"),
    "Projetos atrasados": ("projects_overdue", "Projetos com prazo vencido"),
    "Overdue Projects": ("projects_overdue", "Projetos com prazo vencido"),
    "Serviços atrasados": ("services_overdue", "Solicitações de serviço atrasadas"),
    "Overdue Services": ("services_overdue", "Solicitações de serviço atrasadas"),
    "Equipamentos em manutenção": ("equipment_maintenance", "Equipamentos em manutenção"),
    "Equipment Maintenance": ("equipment_maintenance", "Equipamentos em manutenção"),
    "Permits pendentes": ("permits_pending", "Permits aguardando aprovação"),
    "Pending Permits": ("permits_pending", "Permits aguardando aprovação"),
}

ATTENTION_SHEETS = {
    "equipment_available": ("Available Equipment", "wrench"),
    "projects_active": ("Active Projects", "clipboard_list"),
    "low_stock": ("Low Inventory", "package"),
    "projects_overdue": ("Overdue Projects", "clipboard_list"),
    "services_overdue": ("Overdue Services", "clipboard_list"),
    "equipment_maintenance": ("Equipment Maintenance", "wrench"),
    "permits_pending": ("Pending Permits", "file_clock"),
    "aggregate_revenue": ("Aggregate Revenue", "dollar"),
    "project_revenue": ("Project Revenue", "dollar")
}

def render_top_right_overlay(alerts: list[dict]):
    """Renderiza a barra sobreposta no canto superior direito: EN | PT • 🔔 N"""
    with st.container():
        st.markdown('<div class="top-right-marker"></div>', unsafe_allow_html=True)
        
        # Proporções ajustadas para evitar sobreposição ou quebra de linha dos botões
        c_en, c_div, c_pt, c_dot, c_bell = st.columns([1.5, 0.2, 1.5, 0.2, 2.0])
        
        is_en = st.session_state.language == "en"
        
        with c_en:
            st.markdown(f'<div class="lang-switch-btn {"lang-active" if is_en else "lang-inactive"}">', unsafe_allow_html=True)
            if st.button("EN", key="lang_btn_en"):
                st.session_state.language = "en"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        with c_div:
            st.markdown('<span class="lang-divider">|</span>', unsafe_allow_html=True)

        with c_pt:
            st.markdown(f'<div class="lang-switch-btn {"lang-inactive" if is_en else "lang-active"}">', unsafe_allow_html=True)
            if st.button("PT", key="lang_btn_pt"):
                st.session_state.language = "pt"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        with c_dot:
            st.markdown('<span class="lang-divider">•</span>', unsafe_allow_html=True)

        with c_bell:
            count = len(alerts)
            bell_label = f"🔔 {count}" if count > 0 else "🔔"
            st.markdown('<div class="notification-btn">', unsafe_allow_html=True)
            if st.button(bell_label, key="notification_trigger", help=f"{count} notificações"):
                st.session_state.notifications_open = not st.session_state.get("notifications_open", False)
            st.markdown('</div>', unsafe_allow_html=True)

    # Painel Suspenso de Notificações
    if st.session_state.get("notifications_open", False):
        with st.container():
            st.markdown('<div class="notification-panel-marker"></div>', unsafe_allow_html=True)
            st.markdown(f"#### {tr('Notifications')}")
            if not alerts:
                st.caption(tr("No active alerts"))
            else:
                for alert in alerts:
                    target, _ = ALERT_DESTINATIONS.get(alert["title"], ("low_stock", ""))
                    color = ALERT_COLORS.get(alert["severity"], "#64748b")
                    _, alert_icon = ATTENTION_SHEETS.get(target, ("", "bell"))
                    
                    row_icon, row_button = st.columns([1, 9], vertical_alignment="center")
                    with row_icon:
                        st.markdown(icon(alert_icon, 18, color), unsafe_allow_html=True)
                    with row_button:
                        if st.button(f"{alert['title']} — {alert['text']}", key=f"notification_{target}", use_container_width=True):
                            st.session_state.attention = target
                            st.session_state.page = tr("Home")
                            st.session_state.notifications_open = False
                            st.rerun()

def render_attention_sheet(data: dict, target: str):
    sheet_name, _ = ATTENTION_SHEETS.get(target, ("Detalhamento", "clipboard_list"))
    if st.session_state.language == "pt":
        translate = {
            "Available Equipment": "Equipamentos Disponíveis",
            "Active Projects": "Projetos Ativos",
            "Low Inventory": "Estoque Baixo",
            "Overdue Projects": "Projetos Atrasados",
            "Overdue Services": "Serviços Atrasados",
            "Equipment Maintenance": "Equipamentos em Manutenção",
            "Pending Permits": "Permits Pendentes",
            "Aggregate Revenue": "Receita de Agregados",
            "Project Revenue": "Receita por Projeto",
        }
        sheet_name = translate.get(sheet_name, sheet_name)

    col1, col2 = st.columns([6, 1])
    with col1:
        st.subheader(f"{sheet_name}")
    with col2:
        if st.button(tr("Return Home"), key="close_attention"):
            st.session_state.attention = None
            st.rerun()

    df_key = f"attention_{target}"
    df = data.get(df_key, pd.DataFrame())
    display_table(df)

def render_card_link(container, target: str, key: str):
    with container:
        if st.button("View Details" if st.session_state.language == "en" else "Ver planilha", key=key, use_container_width=True):
            st.session_state.attention = target
            st.session_state.page = tr("Home")

def render_sidebar_summary(data: dict):
    s = data["scalars"]
    st.caption(tr("Summary"))
    rows = [
        ("Equip. disponíveis", f"{s['equipment_available']}/{s['equipment_total']}"),
        ("Projetos ativos", f"{s['projects_active']}/{s['projects_total']}"),
        ("Permits pendentes", s["permits_pending"]),
        ("Clientes", s["clients_total"]),
        ("Receita agregados", f"$ {s['aggregate_revenue_total']:,.0f}"),
    ]
    for label, value in rows:
        st.markdown(
            f'<div style="display:flex;justify-space-between;font-size:0.82rem;'
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
        clicked = st.button(tr("Refresh"), key=key, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    if clicked:
        load_dashboard_data.clear()
        st.rerun()

# =========================================================
# Páginas do App
# =========================================================

def render_home(data: dict):
    with st.sidebar:
        sidebar_refresh_button("refresh_home")

    s = data["scalars"]

    header_title = "Operations Control Center" if st.session_state.language == "en" else "Central de Controle Operacional"
    st.markdown(
        f'''
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:1.2rem;">
            <img width="27" height="27" src="https://img.icons8.com/ios/50/crane.png"
                 style="filter: brightness(0) saturate(100%) invert(85%) sepia(77%) saturate(679%) hue-rotate(358deg) brightness(103%) contrast(96%);"
                 alt="crane"/>
            <span style="font-weight:600; padding-top:2px; font-size:1.08rem; color:{THEME["yellow"]};">{header_title}</span>
        </div>
        ''', unsafe_allow_html=True
    )

    if st.session_state.language == "en":
        st.markdown(
            """
            Welcome to the **Integrated Operations Portal**.
            This dashboard provides a real-time overview of your business.
            • **Equipment Fleet** — Availability and maintenance status.
            • **Projects & Permits** — Active projects, schedules and permits.
            • **Inventory** — Aggregate stock levels and reorder points.
            • **Financial Performance** — Revenue, clients and project profitability.
            """
        )
    else:
        st.markdown(
            """
            Bem-vindo ao **Portal de Gestão Integrada**.
            Este painel consolida os principais indicadores da operação.
            • **Frota de Equipamentos** — Disponibilidade e manutenção.
            • **Projetos e Licenças** — Acompanhamento de projetos e permits.
            • **Estoque** — Níveis de agregados e reposição.
            • **Financeiro** — Receita, clientes e desempenho dos projetos.
            """
        )

    st.divider()

    attention = st.session_state.get("attention")
    if attention:
        render_attention_sheet(data, attention)
        st.divider()

    st.subheader("Key Performance Indicators" if st.session_state.language == "en" else "Indicadores Principais")

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Equipment Available" if st.session_state.language == "en" else "Equipamentos Disponíveis", f"{s['equipment_available']}/{s['equipment_total']}")
    kpi2.metric("Equipment Under Maintenance" if st.session_state.language == "en" else "Equipamentos em Manutenção", s["equipment_maintenance"], delta="Atention" if s["equipment_maintenance"] > 0 else "Ideal", delta_color="inverse" if s["equipment_maintenance"] > 0 else "normal")
    kpi3.metric("Active Projects" if st.session_state.language == "en" else "Projetos Ativos", f"{s['projects_active']}/{s['projects_total']}")
    kpi4.metric("Overdue Projects" if st.session_state.language == "en" else "Projetos Atrasados", s["projects_overdue"], delta="Critical" if s["projects_overdue"] > 0 else "No prazo", delta_color="inverse" if s["projects_overdue"] > 0 else "normal")

    kpi5, kpi6, kpi7, kpi8 = st.columns(4)
    kpi5.metric("Pending Permits" if st.session_state.language == "en" else "Permits Pendentes", s["permits_pending"])
    kpi6.metric("Low Inventory Items" if st.session_state.language == "en" else "Itens em Estoque Baixo", s["low_stock_count"], delta="Repor estoque" if s["low_stock_count"] > 0 else "OK", delta_color="inverse" if s["low_stock_count"] > 0 else "normal")

    receita_media = (s["aggregate_revenue_total"] / s["projects_total"]) if s["projects_total"] else 0
    kpi7.metric("Total Aggregate Revenue" if st.session_state.language == "en" else "Receita Agregados (Total)", f"${s['aggregate_revenue_total']:,.2f}")
    kpi8.metric("Average Revenue per Project" if st.session_state.language == "en" else "Receita Média / Projeto", f"${receita_media:,.2f}")

    render_card_link(kpi1, "equipment_available", "card_equipment_available")
    render_card_link(kpi2, "equipment_maintenance", "card_equipment_maintenance")
    render_card_link(kpi3, "projects_active", "card_projects_active")
    render_card_link(kpi4, "projects_overdue", "card_projects_overdue")
    render_card_link(kpi5, "permits_pending", "card_permits_pending")
    render_card_link(kpi6, "low_stock", "card_low_stock")
    render_card_link(kpi7, "aggregate_revenue", "card_aggregate_revenue")
    render_card_link(kpi8, "project_revenue", "card_project_revenue")

    st.divider()
    st.subheader("Detailed Analysis" if st.session_state.language == "en" else "Análise Detalhada")

    tab_operacoes, tab_financeiro = st.tabs([
        "Operations, Projects & Permits" if st.session_state.language == "en" else "Operações, Projetos & Permits",
        "Finance & Inventory" if st.session_state.language == "en" else "Financeiro & Estoque"
    ])

    with tab_operacoes:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Equipment Fleet Status" if st.session_state.language == "en" else "#### Status da Frota de Equipamentos")
            df = data["equipment_status"]
            if not df.empty:
                fig = px.pie(df, names="status", values="total", hole=0.45, color_discrete_sequence=[THEME["yellow"], "#7A7D84", "#4A4D54", "#B8860B"])
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color=THEME["text"])
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("#### Status dos Projetos" if st.session_state.language == "pt" else "#### Project Status")
            df = data["projects_status"]
            if not df.empty:
                fig = px.bar(df, x="status", y="total", text="total", color_discrete_sequence=[THEME["yellow"]])
                fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color=THEME["text"])
                st.plotly_chart(fig, use_container_width=True)

    with tab_financeiro:
        col5, col6 = st.columns(2)
        with col5:
            st.markdown("#### Evolução Mensal da Receita" if st.session_state.language == "pt" else "#### Monthly Revenue Evolution")
            df = data["monthly_aggregate_revenue"]
            if not df.empty:
                fig = px.line(df, x="month", y="revenue", markers=True, color_discrete_sequence=[THEME["yellow"]])
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color=THEME["text"])
                st.plotly_chart(fig, use_container_width=True)
        with col6:
            st.markdown("#### Top 5 Clientes" if st.session_state.language == "pt" else "#### Top 5 Clients")
            df = data["top_clients"].head(5)
            if not df.empty:
                fig = px.bar(df.sort_values("revenue"), x="revenue", y="name", orientation="h", color_discrete_sequence=[THEME["yellow"]])
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color=THEME["text"])
                st.plotly_chart(fig, use_container_width=True)

def render_bi(data: dict):
    with st.sidebar:
        sidebar_refresh_button("refresh_bi")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Services & Revenue" if st.session_state.language == "en" else "Serviços & Receita",
        "Clients" if st.session_state.language == "en" else "Clientes",
        "Equipment & Crews" if st.session_state.language == "en" else "Equipamentos & Equipes",
        "Aggregates" if st.session_state.language == "en" else "Agregados",
    ])

    with tab1:
        st.subheader("Revenue by Service Category" if st.session_state.language == "en" else "Receita por categoria de serviço")
        df = data["service_requests_by_category"]
        if not df.empty:
            fig = px.bar(df, x="category", y="revenue", color="group_name", color_discrete_sequence=[THEME["yellow"], "#7A7D84", "#4A4D54", "#B8860B"])
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color=THEME["text"])
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Top 10 Clients by Revenue" if st.session_state.language == "en" else "Top 10 clientes por receita")
        df = data["top_clients"]
        if not df.empty:
            fig = px.bar(df.sort_values("revenue"), x="revenue", y="name", orientation="h", color_discrete_sequence=[THEME["yellow"]])
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color=THEME["text"])
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("Equipment by Type" if st.session_state.language == "en" else "Equipamentos por tipo")
        df = data["equipment_by_type"]
        if not df.empty:
            fig = px.bar(df, x="type", y="total", color_discrete_sequence=[THEME["yellow"]])
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color=THEME["text"])
            st.plotly_chart(fig, use_container_width=True)

    with tab4:
        st.subheader("Revenue by Aggregate Type" if st.session_state.language == "en" else "Receita por tipo de agregado")
        df = data["revenue_by_aggregate"]
        if not df.empty:
            fig = px.bar(df.sort_values("revenue"), x="revenue", y="name", orientation="h", color_discrete_sequence=[THEME["yellow"]])
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color=THEME["text"])
            st.plotly_chart(fig, use_container_width=True)

# =========================================================
# Assistente AI
# =========================================================

def call_openrouter(messages: list[dict], model: str, temperature: float = 0.3, max_tokens: int = 900) -> str:
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
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
        parts.append(f"{key} (columns: {list(df.columns)}): {json.dumps(sample, default=str)}")
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
        chart_type = spec.get("type", "bar")
        title = spec.get("title", "")
        if chart_type == "line":
            fig = px.line(df, x=x, y=y, title=title, markers=True, color_discrete_sequence=[THEME["yellow"]])
        elif chart_type == "pie":
            fig = px.pie(df, names=x, values=y, title=title, color_discrete_sequence=[THEME["yellow"], "#7A7D84", "#4A4D54"])
        else:
            fig = px.bar(df, x=x, y=y, title=title, color_discrete_sequence=[THEME["yellow"]])
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color=THEME["text"])
        return fig
    except Exception:
        return None

def ask_ai(question: str, data: dict, model: str):
    context = build_dashboard_context(data)
    lang = st.session_state.get("language", "en")
    
    if lang == "pt":
        system = (
            "Você é um analista especialista em BI. "
            "Responda ao usuário SEMPRE em Português, com base estritamente nos dados fornecidos abaixo:\n"
            + context
        )
    else:
        system = (
            "You are an expert BI analyst. "
            "ALWAYS reply to the user in English, based strictly on the provided data context below:\n"
            + context
        )

    reply = call_openrouter([{"role": "system", "content": system}, {"role": "user", "content": question}], model=model)
    text, spec = extract_chart_spec(reply)
    fig = build_chart_from_spec(spec, data)
    return text, fig

def render_ai(data: dict):
    with st.sidebar:
        model = st.selectbox("Model" if st.session_state.language == "en" else "Modelo", OPENROUTER_MODELS, index=0)
        if st.button(tr("Clear Conversation"), use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    st.markdown(f'<div>{icon("sparkles", 16, color=THEME["yellow"])} AI Insights</div>', unsafe_allow_html=True)

    if not OPENROUTER_API_KEY:
        st.warning("Configure OPENROUTER_API_KEY.")
        return

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("figure") is not None:
                st.plotly_chart(message["figure"], use_container_width=True)

    examples = EXAMPLE_QUESTIONS[st.session_state.language]
    cols = st.columns(len(examples))
    for col, q in zip(cols, examples):
        if col.button(q):
            st.session_state.pending_question = q
            st.rerun()

    user_input = st.chat_input(tr("Ask about your business..."))
    if "pending_question" in st.session_state:
        user_input = st.session_state.pop("pending_question")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            spinner_text = "Analyzing..." if st.session_state.language == "en" else "Analisando..."
            with st.spinner(spinner_text):
                try:
                    answer, fig = ask_ai(user_input, data, model)
                except Exception:
                    answer = "Unable to generate answer." if st.session_state.language == "en" else "Não foi possível gerar a resposta."
                    fig = None
            st.markdown(answer)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

        st.session_state.messages.append({"role": "assistant", "content": answer, "figure": fig})

# =========================================================
# Configuração da página e Roteamento
# =========================================================

st.set_page_config(page_title="Intelligent Site Services Copilot", layout="wide")
inject_theme_css()

try:
    engine = get_engine()
except Exception:
    st.error("Não foi possível conectar ao sistema agora.")
    st.stop()

dashboard_data = load_dashboard_data(engine)

if "page" not in st.session_state:
    st.session_state.page = "Home"
if "attention" not in st.session_state:
    st.session_state.attention = None

# Renderiza barra superior (EN | PT • 🔔 N)
render_top_right_overlay(compute_alerts(dashboard_data["scalars"]))

NAV_ITEMS = [
    ("Home", "home"),
    ("Power BI", "bar_chart"),
    ("AI", "message_square"),
]

with st.sidebar:
    st.markdown(
        f'''
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:1.2rem;">
            <img width="27" height="27" src="https://img.icons8.com/ios/50/crane.png"
                 style="filter: brightness(0) saturate(100%) invert(85%) sepia(77%) saturate(679%) hue-rotate(358deg) brightness(103%) contrast(96%);"
                 alt="crane"/>
            <span style="font-weight:600; padding-top:2px; font-size:1.08rem; color:{THEME["yellow"]};">Site Services Copilot</span>
        </div>
        ''', unsafe_allow_html=True
    )

    st.markdown('<div class="nav-list">', unsafe_allow_html=True)
    for raw_label, icon_name in NAV_ITEMS:
        label = tr(raw_label)
        is_active = st.session_state.page in [raw_label, label]
        icon_col, btn_col = st.columns([1, 5], vertical_alignment="center")
        with icon_col:
            st.markdown(icon(icon_name, color=THEME["yellow"] if is_active else THEME["text_dim"]), unsafe_allow_html=True)
        with btn_col:
            if st.button(label, key=f"nav_{raw_label}", use_container_width=True, type="primary" if is_active else "secondary"):
                st.session_state.page = label
                st.session_state.attention = None
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.divider()
    render_sidebar_summary(dashboard_data)

selected = st.session_state.page

if st.session_state.attention:
    render_attention_sheet(dashboard_data, st.session_state.attention)
elif selected in ["Home", tr("Home")]:
    render_home(dashboard_data)
elif selected in ["Power BI", "Power Bi", tr("Power BI")]:
    render_bi(dashboard_data)
else:
    render_ai(dashboard_data)