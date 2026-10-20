import datetime
import io
import pandas as pd
import plotly.express as py
import streamlit as st
import sqlalchemy as sa
import os

# Importaciones para generación de PDF nativo con ReportLab
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(
    page_title="SYNCORE | Control Ejecutivo P6, 6WLA & T&M", 
    page_icon="🟧", 
    layout="wide"
)

# --- CADENA DE CONEXIÓN SUPABASE (POOLER IPv4) ---
DATABASE_URL = "postgresql+psycopg2://postgres.wlxdxdjmyaamcoozvego:SyncoreMontajes@aws-0-us-east-2.pooler.supabase.com:6543/postgres"
engine = sa.create_engine(DATABASE_URL)

# --- ESTILOS CSS EJECUTIVOS Y CORPORATIVOS SYNCORE ---
st.markdown("""
    <style>
        .stApp {
            background-color: #F4F6F9;
        }
        [data-testid="stSidebar"] {
            background-color: #0F172A;
            color: #FFFFFF;
        }
        [data-testid="stSidebar"] label, [data-testid="stSidebar"] .stSelectbox div {
            color: #FFFFFF !important;
        }
        .stButton>button {
            background-color: #FF6B00;
            color: white;
            font-weight: 600;
            border-radius: 6px;
            border: none;
            padding: 0.6rem 1.2rem;
            box-shadow: 0 4px 6px rgba(255, 107, 0, 0.2);
        }
        .stButton>button:hover {
            background-color: #E05D00;
            color: white;
        }
        h1, h2, h3 {
            color: #0F172A;
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        }
        [data-testid="metric-container"] {
            background-color: #FFFFFF;
            border-top: 4px solid #FF6B00;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
        }
        .block-container {
            padding-top: 2rem;
        }
    </style>
""", unsafe_allow_html=True)

def init_db():
    try:
        with engine.connect() as conn:
            conn.execute(sa.text('''
                CREATE TABLE IF NOT EXISTS proyectos (
                    ID_PROJECTO SERIAL PRIMARY KEY,
                    Nombre TEXT NOT NULL,
                    Estado TEXT NOT NULL,
                    Avance_Porcentaje REAL NOT NULL,
                    At_Completion_Units REAL DEFAULT 0,
                    Actual_Units REAL DEFAULT 0,
                    Remaining_Units REAL DEFAULT 0,
                    Fecha_Inicio TEXT NOT NULL,
                    Fecha_Termino TEXT NOT NULL
                )
            '''))
            
            conn.execute(sa.text('''
                CREATE TABLE IF NOT EXISTS tareas (
                    ID_TAREA SERIAL PRIMARY KEY,
                    ID_Proyecto INTEGER,
                    Tarea TEXT NOT NULL,
                    Subsistema TEXT NOT NULL,
                    Labor_Units REAL NOT NULL,
                    Remaining_Labor_Units REAL NOT NULL,
                    Labor_Units_Complete_Pct REAL NOT NULL,
                    Estado TEXT NOT NULL,
                    Responsable TEXT
                )
            '''))
            
            conn.execute(sa.text('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    ID_USUARIO SERIAL PRIMARY KEY,
                    Username TEXT UNIQUE NOT NULL,
                    Password TEXT NOT NULL,
                    Estado TEXT DEFAULT 'Aprobado'
                )
            '''))
            conn.commit()
            
            result = conn.execute(sa.text("SELECT * FROM usuarios WHERE Username = 'Bastian Cataldo'")).fetchone()
            if not result:
                conn.execute(sa.text("INSERT INTO usuarios (Username, Password, Estado) VALUES (:user, :passw, :est)"),
                             {"user": "Bastian Cataldo", "passw": "admin123", "est": "Aprobado"})
                conn.commit()
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")

init_db()

def cargar_proyectos():
    try:
        return pd.read_sql("SELECT * FROM proyectos", engine).fillna("")
    except Exception:
        return pd.DataFrame()

def cargar_tareas():
    try:
        return pd.read_sql("SELECT * FROM tareas", engine).fillna("")
    except Exception:
        return pd.DataFrame()

# --- GESTIÓN DE SESIÓN ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #FF6B00;'>SYNCORE</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #0F172A;'>Control Ejecutivo P6 (Cloud Supabase)</h3>", unsafe_allow_html=True)
        st.markdown("---")

        user_input = st.text_input("Usuario", key="login_user")
        pass_input = st.text_input("Contraseña", type="password", key="login_pass")

        if st.button("Ingresar a la Plataforma"):
            try:
                with engine.connect() as conn:
                    query = sa.text("SELECT Estado FROM usuarios WHERE Username = :u AND Password = :p")
                    user_record = conn.execute(query, {"u": user_input, "p": pass_input}).fetchone()

                if user_record:
                    st.session_state.logged_in = True
                    st.session_state.username = user_input
                    st.success("¡Inicio de sesión exitoso!")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")
            except Exception as ex:
                st.error(f"Error en la base de datos: {ex}")
    st.stop()

# --- BARRA LATERAL Y MENÚ ---
st.sidebar.markdown("""
    <div style="text-align: center; padding: 10px 0px 20px 0px;">
        <h2 style="color: #FF6B00; margin: 0; font-weight: 800;">SYNCORE</h2>
        <p style="color: #94A3B8; font-size: 13px; margin: 0;">MONTAJES INDUSTRIALES</p>
    </div>
""", unsafe_allow_html=True)

st.sidebar.markdown(f"👤 **Usuario:** `{st.session_state.username}`")

menu = st.sidebar.selectbox("Menú Ejecutivo", [
    "📊 Dashboard General", 
    "📁 Gestión de Proyectos"
])

if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

if menu == "📊 Dashboard General":
    st.title("📊 SYNCORE | Dashboard Ejecutivo Global")
    df_proyectos = cargar_proyectos()
    df_tareas = cargar_tareas()

    if df_proyectos.empty:
        st.info("No hay proyectos cargados en Supabase.")
    else:
        st.dataframe(df_proyectos, use_container_width=True)
        
        # Ejemplo de gráfico con plotly para verificar que funciona
        fig = px.bar(df_proyectos, x="Nombre", y="Avance_Porcentaje", title="Avance por Proyecto")
        st.plotly_chart(fig, use_container_width=True)

elif menu == "📁 Gestión de Proyectos":
    st.title("📁 Gestión de Proyectos en la Nube")
    df_proyectos = cargar_proyectos()
    st.dataframe(df_proyectos, use_container_width=True)
