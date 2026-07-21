import os
import re
import pandas as pd
import sqlalchemy
import streamlit as st
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

# =========================================================
# Camada extra de proteção (defesa em profundidade)
# =========================================================
# Mesmo com o usuário do Postgres sendo read-only, adicionamos uma
# checagem no próprio código: qualquer query que não comece com SELECT
# é bloqueada antes de chegar ao banco.

_BLOCKED_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter",
    "truncate", "create", "grant", "revoke",
)


def is_safe_select(command: str) -> bool:
    """Reaproveita a mesma regra de segurança do ReadOnlySQLDatabase,
    usada aqui para decidir se podemos reexecutar a query e gerar um gráfico."""
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
                "⛔ Query bloqueada: este agente só tem permissão para executar "
                "consultas SELECT (somente leitura)."
            )
        return super().run(command, *args, **kwargs)


EXAMPLE_QUESTIONS = [
    "Quantas escavadeiras estão disponíveis agora?",
    "Qual o custo total de aluguel de equipamentos em uso?",
    "Liste os projetos com permits pendentes.",
]

# =========================================================
# Helpers de saída do Gemini / LangChain
# =========================================================


def extract_text(output) -> str:
    """O Gemini 2.5 às vezes retorna `output` como uma lista de blocos
    (ex: [{'type': 'text', 'text': '...'}, {'type': 'thought_signature', ...}])
    em vez de uma string simples. Esta função normaliza para string limpa."""
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
    """Varre os intermediate_steps do AgentExecutor e retorna as queries SQL
    que o agente efetivamente rodou (tool sql_db_query / sql_db_query_checker)."""
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
    """Reexecuta a query gerada pelo agente para conseguir um DataFrame
    de verdade (o agente só devolve texto). Só roda se passar na mesma
    checagem de segurança usada pelo ReadOnlySQLDatabase."""
    if not is_safe_select(sql):
        return None
    try:
        with _db._engine.connect() as conn:
            return pd.read_sql(sql, conn)
    except Exception:
        return None


def render_chart_if_useful(df: pd.DataFrame):
    """Decide heuristicamente se o resultado merece um gráfico e, se sim,
    qual tipo. Critério simples: precisa de pelo menos 1 coluna numérica
    e mais de 1 linha; usa a primeira coluna não-numérica como eixo X."""
    if df is None or df.empty or len(df) < 2:
        return

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if not numeric_cols:
        return

    non_numeric_cols = [c for c in df.columns if c not in numeric_cols]

    with st.expander("📊 Ver gráfico", expanded=True):
        if non_numeric_cols:
            label_col = non_numeric_cols[0]
            chart_df = df.set_index(label_col)[numeric_cols]
        else:
            chart_df = df[numeric_cols]

        # Poucas categorias -> barra costuma ser mais legível que linha
        if len(chart_df) <= 25:
            st.bar_chart(chart_df)
        else:
            st.line_chart(chart_df)


# =========================================================
# Configuração da página
# =========================================================

st.set_page_config(
    page_title="Intelligent Site Services Copilot",
    page_icon="🏗️",
    layout="centered",
)

st.title("🏗️ Intelligent Site Services Copilot")
st.caption("Converse em linguagem natural com o banco de dados do seu negócio.")

# =========================================================
# Inicialização (cacheada — roda uma vez só por sessão)
# =========================================================


def _build_cloud_sql_engine():
    """Conecta no Cloud SQL via Cloud SQL Python Connector — sem proxy,
    sem IP público exposto. Usado quando INSTANCE_CONNECTION_NAME está setado
    (ou seja, quando rodando no Cloud Run)."""
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
        # Produção: Cloud Run -> Cloud SQL
        engine = _build_cloud_sql_engine()
        return ReadOnlySQLDatabase(engine)

    # Dev local: Docker na sua máquina
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
# Sidebar — status da conexão e info do banco
# =========================================================

with st.sidebar:
    st.header("⚙️ Status")

    try:
        db = get_database()
        mode = "Cloud SQL" if INSTANCE_CONNECTION_NAME else f"TCP local ({DB_HOST}:{DB_PORT})"
        st.success(f"Banco de dados conectado ({mode})")
        with st.expander("Tabelas disponíveis"):
            for table in db.get_usable_table_names():
                st.write(f"- {table}")
    except Exception as e:
        st.error(f"Falha ao conectar ao banco: {e}")
        st.stop()

    try:
        agent_executor = get_agent(db)
        st.success(f"Modelo ativo: {GEMINI_MODEL} (Vertex AI · {PROJECT_ID})")
    except Exception as e:
        st.error(f"Falha ao inicializar o Vertex AI: {e}")
        st.caption(
            "Verifique se você rodou `gcloud auth application-default login` "
            "e se o projeto/modelo estão liberados no Model Garden."
        )
        st.stop()

    st.divider()
    if st.button("🗑️ Limpar conversa"):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption("Exemplos de perguntas:")
    for question in EXAMPLE_QUESTIONS:
        st.caption(f"• {question}")

# =========================================================
# Histórico de conversa
# =========================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        for sql in message.get("sql_queries", []):
            st.code(sql, language="sql")
        df = message.get("dataframe")
        if df is not None:
            st.dataframe(df, use_container_width=True)
            render_chart_if_useful(df)

# Botões de pergunta rápida (só aparecem se a conversa estiver vazia)
if not st.session_state.messages:
    st.write("Experimente uma dessas perguntas:")
    cols = st.columns(len(EXAMPLE_QUESTIONS))
    for col, question in zip(cols, EXAMPLE_QUESTIONS):
        if col.button(question):
            st.session_state.pending_question = question
            st.rerun()

# =========================================================
# Input do usuário
# =========================================================

user_input = st.chat_input("Digite sua pergunta sobre o negócio...")

# Se um botão de exemplo foi clicado, usa essa pergunta
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
                    # usa a última query rodada (geralmente a que gerou a resposta final)
                    result_df = run_query_as_dataframe(db, sql_queries[-1])
            except Exception as e:
                answer = f"⚠️ Erro ao processar a pergunta: {e}"

        st.markdown(answer)

        if sql_queries:
            with st.expander("🔍 Ver SQL gerada pelo agente"):
                for sql in sql_queries:
                    st.code(sql, language="sql")

        if result_df is not None and not result_df.empty:
            st.dataframe(result_df, use_container_width=True)
            render_chart_if_useful(result_df)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "sql_queries": sql_queries,
        "dataframe": result_df,
    })