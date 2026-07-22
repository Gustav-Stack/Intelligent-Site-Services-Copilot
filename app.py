import os
import pandas as pd
import sqlalchemy
import streamlit as st
import plotly.express as px
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_google_vertexai import ChatVertexAI


DB_USER = os.environ.get("DB_USER", "agent_readonly")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "troque_esta_senha")
DB_NAME = os.environ.get("DB_NAME", "site_services")

# Dev local (Docker na sua máquina): conecta via TCP normal
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")

# Produção (Cloud SQL): se esta variável existir, o app conecta via
# Cloud SQL Python Connector em vez de TCP direto. Formato esperado:
# "projeto:regiao:nome-da-instancia"
INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME", "")

# Google Cloud Vertex AI
PROJECT_ID = os.environ.get("PROJECT_ID", "intelligent-site-copilot")
LOCATION = os.environ.get("LOCATION", "us-central1")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Quanto tempo (segundos) os indicadores/gráficos ficam em cache antes de
# reconsultar o banco. Ajuste conforme a frequência de atualização dos dados.
KPI_CACHE_TTL = int(os.environ.get("KPI_CACHE_TTL_SECONDS", "300"))

# =========================================================
# Camada extra de proteção (defesa em profundidade) — usada pela aba AI
# =========================================================
_BLOCKED_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter",
    "truncate", "create", "grant", "revoke",
)


def is_safe_select(command: str) -> bool:
    normalized = command.strip().lower()
    if not normalized.startswith("select"):
        return False
    if any(f" {kw} " in f" {normalized} " for kw in _BLOCKED_KEYWORDS):
        return False
    return True


class ReadOnlySQLDatabase(SQLDatabase):
    def run(self, command: str, *args, **kwargs):
        if not is_safe_select(command):
            return (
                "Query bloqueada: este agente só tem permissão para executar "
                "consultas SELECT (somente leitura)."
            )
        return super().run(command, *args, **kwargs)


EXAMPLE_QUESTIONS = [
    "Quantas escavadeiras estão disponíveis agora?",
    "Qual o custo total de aluguel de equipamentos em uso?",
    "Liste os projetos com permits pendentes.",
]

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
    "building": '<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/>',
}


def icon(name: str, size: int = 18) -> str:
    body = _LUCIDE.get(name, "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle">{body}</svg>'
    )

# =========================================================
# Helpers de saída do Gemini / LangChain
# =========================================================


def extract_text(output) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        parts = []
        for block in output:
            if isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    parts.append(block["text"])
                elif "text" in block:
                    parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts).strip()
    return str(output)


def extract_sql_queries(intermediate_steps) -> list[str]:
    queries = []
    for action, _observation in intermediate_steps or []:
        tool_name = getattr(action, "tool", "")
        if "sql_db_query" not in tool_name:
            continue
        tool_input = getattr(action, "tool_input", "")
        if isinstance(tool_input, dict):
            sql = tool_input.get("query") or tool_input.get("sql") or ""
        else:
            sql = str(tool_input)
        sql = sql.strip()
        if sql and sql not in queries:
            queries.append(sql)
    return queries


@st.cache_data(show_spinner=False, ttl=60)
def run_query_as_dataframe(_db, sql: str) -> pd.DataFrame | None:
    if not is_safe_select(sql):
        return None
    try:
        with _db._engine.connect() as conn:
            return pd.read_sql(sql, conn)
    except Exception:
        return None


def display_table(df: pd.DataFrame, rename: dict | None = None):
    """Mostra uma tabela limpa para o usuário final: nomes de coluna
    amigáveis, valores monetários formatados e sem índice técnico."""
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


def render_chart_if_useful(df: pd.DataFrame):
    if df is None or df.empty or len(df) < 2:
        return
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if not numeric_cols:
        return
    non_numeric_cols = [c for c in df.columns if c not in numeric_cols]
    label_col = non_numeric_cols[0] if non_numeric_cols else None
    if label_col:
        fig = px.bar(df, x=label_col, y=numeric_cols[0])
    else:
        fig = px.bar(df, y=numeric_cols[0])
    fig.update_layout(margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)


# =========================================================
# Conexão com o banco e agente (cacheados por sessão)
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
def get_database():
    if INSTANCE_CONNECTION_NAME:
        engine = _build_cloud_sql_engine()
        return ReadOnlySQLDatabase(engine)
    db_uri = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return ReadOnlySQLDatabase.from_uri(db_uri)


@st.cache_resource(show_spinner="Inicializando o modelo Gemini (Vertex AI)...")
def get_agent(_db):
    llm = ChatVertexAI(
        project=PROJECT_ID,
        model_name=GEMINI_MODEL,
        location=LOCATION,
        temperature=0,
    )
    return create_sql_agent(
        llm=llm,
        db=_db,
        agent_type="tool-calling",
        verbose=True,
        return_intermediate_steps=True,
    )


# =========================================================
# Camada de indicadores (KPIs) — cacheada para não bater no
# banco a cada rerender do Streamlit
# =========================================================


@st.cache_data(show_spinner=False, ttl=KPI_CACHE_TTL)
def load_dashboard_data(_engine):
    """Executa todas as queries de indicadores/gráficos de uma vez e
    devolve um dicionário de DataFrames. Cacheado por KPI_CACHE_TTL
    segundos — controla a frequência de idas ao banco."""
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
            "projects_active": "SELECT COUNT(*) FROM projects WHERE status IN ('scheduled', 'in_progress')",
            "projects_total": "SELECT COUNT(*) FROM projects",
            "permits_pending": "SELECT COUNT(*) FROM permits WHERE status IN ('pending', 'submitted')",
            "aggregate_revenue_total": "SELECT COALESCE(SUM(total_price), 0) FROM aggregate_orders",
            "low_stock_count": "SELECT COUNT(*) FROM aggregates WHERE stock_qty <= reorder_point",
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
# Configuração da página
# =========================================================

st.set_page_config(
    page_title="Intelligent Site Services Copilot",
    page_icon=None,
    layout="wide",
)

# =========================================================
# Conexão (feita uma vez, compartilhada por todas as abas)
# =========================================================

try:
    db = get_database()
    engine = db._engine
except Exception:
    st.error("Não foi possível conectar ao sistema agora. Tente novamente em instantes.")
    st.stop()

# =========================================================
# Barra de menu (Home / BI's / AI)
# =========================================================

st.title("Intelligent Site Services Copilot")

if "page" not in st.session_state:
    st.session_state.page = "Home"

NAV_ITEMS = [("Home", "home"), ("BI's", "bar_chart"), ("AI", "message_square")]

with st.sidebar:
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:1rem;">'
        f'{icon("building", 20)}<span style="font-weight:600;">Site Services Copilot</span></div>',
        unsafe_allow_html=True,
    )
    for label, icon_name in NAV_ITEMS:
        icon_col, btn_col = st.columns([1, 5], vertical_alignment="center")
        with icon_col:
            st.markdown(icon(icon_name), unsafe_allow_html=True)
        with btn_col:
            is_active = st.session_state.page == label
            if st.button(
                label, key=f"nav_{label}", use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.page = label
                st.rerun()
    st.divider()

selected = st.session_state.page


# =========================================================
# Página: HOME — indicadores principais + gráficos (Plotly)
# =========================================================


def render_home():
    with st.sidebar:
        icon_col, btn_col = st.columns([1, 5], vertical_alignment="center")
        with icon_col:
            st.markdown(icon("refresh"), unsafe_allow_html=True)
        with btn_col:
            if st.button("Atualizar", key="refresh_home", use_container_width=True):
                load_dashboard_data.clear()
                st.rerun()

    with st.spinner("Carregando indicadores..."):
        data = load_dashboard_data(engine)

    s = data["scalars"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Equipamentos disponíveis", f"{s['equipment_available']}/{s['equipment_total']}")
    c2.metric("Projetos ativos", f"{s['projects_active']}/{s['projects_total']}")
    c3.metric("Permits pendentes", s["permits_pending"])
    c4.metric("Receita agregados (total)", f"${s['aggregate_revenue_total']:,.2f}")
    c5.metric("Itens com estoque baixo", s["low_stock_count"],
              delta=None if s["low_stock_count"] == 0 else "atenção", delta_color="inverse")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Status da frota de equipamentos")
        df = data["equipment_status"]
        if not df.empty:
            fig = px.pie(df, names="status", values="total", hole=0.45)
            fig.update_traces(textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados de equipamentos.")

    with col2:
        st.subheader("Projetos por status")
        df = data["projects_status"]
        if not df.empty:
            fig = px.bar(df, x="status", y="total", color="status", text="total")
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados de projetos.")

    col3, col4 = st.columns(2)

    with col3:
        st.subheader("Receita de agregados por mês")
        df = data["monthly_aggregate_revenue"]
        if not df.empty:
            fig = px.line(df, x="month", y="revenue", markers=True)
            fig.update_yaxes(tickprefix="$")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados de receita.")

    with col4:
        st.subheader("Estoque de agregados vs. ponto de reposição")
        df = data["aggregate_stock"]
        if not df.empty:
            fig = px.bar(
                df, x="name", y=["stock_qty", "reorder_point"],
                barmode="group", labels={"value": "quantidade", "name": "agregado"},
            )
            fig.update_layout(xaxis_tickangle=-30)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados de estoque.")


# =========================================================
# Página: BI's — dashboards mais detalhados
# =========================================================


def render_bi():
    with st.sidebar:
        icon_col, btn_col = st.columns([1, 5], vertical_alignment="center")
        with icon_col:
            st.markdown(icon("refresh"), unsafe_allow_html=True)
        with btn_col:
            if st.button("Atualizar", key="refresh_bi", use_container_width=True):
                load_dashboard_data.clear()
                st.rerun()

    with st.spinner("Carregando dados de BI..."):
        data = load_dashboard_data(engine)

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
            )
            fig.update_layout(xaxis_tickangle=-30, yaxis_tickprefix="$")
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
            fig = px.bar(df, x="project_type", y="total", text="total")
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Permits por status")
        df = data["permits_status"]
        if not df.empty:
            fig = px.pie(df, names="status", values="total", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Top 10 clientes por receita")
        df = data["top_clients"]
        if not df.empty:
            fig = px.bar(df.sort_values("revenue"), x="revenue", y="name", orientation="h")
            fig.update_layout(xaxis_tickprefix="$")
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
                fig = px.bar(df, x="type", y="total", hover_data=["avg_rate"], text="total")
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("Produtividade das equipes")
            df = data["crew_workload"]
            if not df.empty:
                fig = px.bar(
                    df, x="crew_name", y=["total_jobs", "completed"], barmode="group",
                )
                st.plotly_chart(fig, use_container_width=True)

    with tab4:
        st.subheader("Receita por tipo de agregado")
        df = data["revenue_by_aggregate"]
        if not df.empty:
            fig = px.bar(df.sort_values("revenue"), x="revenue", y="name", orientation="h")
            fig.update_layout(xaxis_tickprefix="$")
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Histórico de preços por agregado")
        df = data["price_history"]
        if not df.empty:
            options = sorted(df["name"].unique().tolist())
            selected_agg = st.multiselect("Selecione agregados", options, default=options[:3])
            filtered = df[df["name"].isin(selected_agg)] if selected_agg else df
            fig = px.line(filtered, x="recorded_at", y="price", color="name", markers=True)
            fig.update_yaxes(tickprefix="$")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem histórico de preços.")


# =========================================================
# Página: AI — chat com o SQL Agent (LangChain + Gemini)
# =========================================================


def render_ai():
    try:
        agent_executor = get_agent(db)
    except Exception:
        st.error("O assistente não está disponível no momento. Tente novamente mais tarde.")
        st.stop()

    with st.sidebar:
        icon_col, btn_col = st.columns([1, 5], vertical_alignment="center")
        with icon_col:
            st.markdown(icon("trash"), unsafe_allow_html=True)
        with btn_col:
            if st.button("Limpar conversa", key="clear_chat", use_container_width=True):
                st.session_state.messages = []
                st.rerun()

        st.divider()
        st.caption("Exemplos de perguntas:")
        for question in EXAMPLE_QUESTIONS:
            st.caption(f"• {question}")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            df = message.get("dataframe")
            if df is not None:
                display_table(df)
                render_chart_if_useful(df)

    if not st.session_state.messages:
        st.write("Experimente uma dessas perguntas:")
        cols = st.columns(len(EXAMPLE_QUESTIONS))
        for col, question in zip(cols, EXAMPLE_QUESTIONS):
            if col.button(question):
                st.session_state.pending_question = question
                st.rerun()

    user_input = st.chat_input("Digite sua pergunta sobre o negócio...")

    if "pending_question" in st.session_state:
        user_input = st.session_state.pop("pending_question")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            sql_queries: list[str] = []
            result_df = None
            answer = ""

            with st.spinner("Consultando o banco de dados..."):
                try:
                    response = agent_executor.invoke({"input": user_input})
                    answer = extract_text(response.get("output", ""))
                    sql_queries = extract_sql_queries(response.get("intermediate_steps"))
                    if sql_queries:
                        result_df = run_query_as_dataframe(db, sql_queries[-1])
                except Exception:
                    answer = "Não consegui responder essa pergunta agora. Tente reformular ou pergunte novamente."

            st.markdown(answer)

            if result_df is not None and not result_df.empty:
                display_table(result_df)
                render_chart_if_useful(result_df)

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "sql_queries": sql_queries,
            "dataframe": result_df,
        })


# =========================================================
# Roteamento
# =========================================================

if selected == "Home":
    render_home()
elif selected == "BI's":
    render_bi()
else:
    render_ai()