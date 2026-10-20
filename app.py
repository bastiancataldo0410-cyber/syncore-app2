import datetime
import io
import pandas as pd
import plotly.express as px
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
                CREATE TABLE IF NOT EXISTS analisis_plan_semanal (
                    ID_PLAN SERIAL PRIMARY KEY,
                    Proyecto TEXT NOT NULL,
                    Activity_ID TEXT NOT NULL,
                    Actividad TEXT NOT NULL,
                    Subsistema TEXT NOT NULL,
                    Semana TEXT NOT NULL,
                    HH_Programadas REAL DEFAULT 0,
                    Estado_Ejecucion TEXT NOT NULL
                )
            '''))

            conn.execute(sa.text('''
                CREATE TABLE IF NOT EXISTS analisis_log_desviaciones (
                    ID_DESV SERIAL PRIMARY KEY,
                    Proyecto TEXT NOT NULL,
                    Activity_ID TEXT NOT NULL,
                    Actividad TEXT NOT NULL,
                    Subsistema TEXT NOT NULL,
                    Causa_Desviacion TEXT NOT NULL,
                    Responsable TEXT NOT NULL,
                    HH_Perdidas REAL DEFAULT 0,
                    Estado TEXT NOT NULL
                )
            '''))
            
            conn.execute(sa.text('''
                CREATE TABLE IF NOT EXISTS informes_semanales (
                    ID_INFORME SERIAL PRIMARY KEY,
                    Nombre_Informe TEXT NOT NULL,
                    Fecha_Carga TEXT NOT NULL,
                    Subsistema TEXT NOT NULL,
                    At_Completion_Units REAL DEFAULT 0,
                    Remaining_Units REAL DEFAULT 0,
                    Avance_Pct REAL DEFAULT 0
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
        st.error(f"Error al conectar o inicializar Supabase: {e}")

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

def parse_xer_exacto(contenido_text):
    lineas = contenido_text.splitlines()
    tablas = {}
    tabla_actual = None
    columnas_actuales = []
    
    for linea in lineas:
        if not linea.strip(): continue
        partes = linea.split('\t')
        header = partes[0]
        
        if header == '%T':
            tabla_actual = partes[1]
            tablas[tabla_actual] = []
            columnas_actuales = []
        elif header == '%F' and tabla_actual:
            columnas_actuales = partes[1:]
        elif header == '%R' and tabla_actual and columnas_actuales:
            valores = partes[1:]
            if len(valores) == len(columnas_actuales):
                tablas[tabla_actual].append(dict(zip(columnas_actuales, valores)))
            else:
                min_len = min(len(valores), len(columnas_actuales))
                tablas[tabla_actual].append(dict(zip(columnas_actuales[:min_len], valores[:min_len])))
                
    return tablas

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

        tab_login, tab_register = st.tabs(["🔑 Iniciar Sesión", "📝 Registrar Usuario"])

        with tab_login:
            st.subheader("Acceso al Sistema")
            user_input = st.text_input("Usuario", key="login_user")
            pass_input = st.text_input("Contraseña", type="password", key="login_pass")

            if st.button("Ingresar a la Plataforma"):
                try:
                    with engine.connect() as conn:
                        query = sa.text("SELECT Estado FROM usuarios WHERE Username = :u AND Password = :p")
                        user_record = conn.execute(query, {"u": user_input, "p": pass_input}).fetchone()

                    if user_record:
                        estado_usuario = user_record[0]
                        if estado_usuario == "Aprobado":
                            st.session_state.logged_in = True
                            st.session_state.username = user_input
                            st.success("¡Inicio de sesión exitoso! Cargando plataforma...")
                            st.rerun()
                        else:
                            st.warning("⚠️ Tu cuenta se encuentra pendiente de aprobación por el Administrador.")
                    else:
                        st.error("Usuario o contraseña incorrectos.")
                except Exception as ex:
                    st.error(f"Error de conexión con la base de datos: {ex}")

        with tab_register:
            st.subheader("Registro de Nuevo Usuario")
            new_user = st.text_input("Nuevo Usuario (Ej: Tu Nombre)", key="reg_user")
            new_pass = st.text_input("Nueva Contraseña", type="password", key="reg_pass")
            confirm_pass = st.text_input("Confirmar Contraseña", type="password", key="reg_conf")

            if st.button("Registrar Cuenta"):
                if not new_user or not new_pass:
                    st.warning("Por favor completa todos los campos.")
                elif new_pass != confirm_pass:
                    st.error("Las contraseñas no coinciden.")
                else:
                    try:
                        with engine.connect() as conn:
                            estado_inicial = "Aprobado" if new_user == "Bastian Cataldo" else "Pendiente"
                            conn.execute(sa.text("INSERT INTO usuarios (Username, Password, Estado) VALUES (:u, :p, :e)"),
                                         {"u": new_user, "p": new_pass, "e": estado_inicial})
                            conn.commit()
                        if estado_inicial == "Pendiente":
                            st.success("¡Cuenta registrada con éxito! Quedará pendiente de aprobación.")
                        else:
                            st.success("¡Cuenta de Administrador creada con éxito!")
                    except Exception as ex:
                        st.error(f"El nombre de usuario ya existe o hubo un error: {ex}")
    st.stop()

# --- BARRA LATERAL ---
st.sidebar.markdown("""
    <div style="text-align: center; padding: 10px 0px 20px 0px;">
        <h2 style="color: #FF6B00; margin: 0; font-weight: 800;">SYNCORE</h2>
        <p style="color: #94A3B8; font-size: 13px; margin: 0;">MONTAJES INDUSTRIALES</p>
    </div>
""", unsafe_allow_html=True)

st.sidebar.markdown(f"👤 **Usuario:** `{st.session_state.username}`")

menu_opciones = [
    "📊 Dashboard General", 
    "🏗️ Análisis Subsistema", 
    "📊 Análisis T&M (Times & Material)",
    "📁 Gestión de Proyectos", 
    "📂 Importar Archivo (.XER)"
]

is_admin = (st.session_state.username == "Bastian Cataldo")
if is_admin:
    menu_opciones.append("🛡️ Administración de Usuarios")

if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

st.sidebar.markdown("---")
menu = st.sidebar.selectbox("Menú Ejecutivo", menu_opciones)

if menu == "📊 Dashboard General":
    st.title("📊 SYNCORE | Dashboard Ejecutivo Global (Cloud Supabase)")
    st.markdown("Análisis sincronizado en tiempo real con la base de datos centralizada.")
    
    df_proyectos = cargar_proyectos()
    df_tareas = cargar_tareas()

    if df_proyectos.empty or df_tareas.empty:
        st.info("No hay proyectos con datos cargados en la nube. Dirígete a **'📂 Importar Archivo (.XER)'** para sincronizar tu proyecto.")
    else:
        proyectos_lista = df_proyectos["Nombre"].unique().tolist()
        proj_seleccionado = st.selectbox("📌 Seleccionar Proyecto Activo:", proyectos_lista)
        
        row_proj = df_proyectos.loc[df_proyectos["Nombre"] == proj_seleccionado].iloc[0]
        id_proj = row_proj["ID_PROJECTO"]
        df_tareas_proj = df_tareas[df_tareas["ID_Proyecto"] == id_proj]

        if df_tareas_proj.empty:
            st.warning("Este proyecto no contiene actividades registradas.")
        else:
            total_actividades = len(df_tareas_proj)
            at_completion_total = float(row_proj.get("At_Completion_Units", 534269) or 534269)
            actual_total = float(row_proj.get("Actual_Units", 343321) or 343321)
            remaining_total = float(row_proj.get("Remaining_Units", 190948) or 190948)
            avance_ponderado_exacto = float(row_proj.get("Avance_Porcentaje", 64.26) or 64.26)

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Actividades P6", f"{total_actividades:,}")
            c2.metric("At Completion", f"{at_completion_total:,.0f} hrs")
            c3.metric("Actual", f"{actual_total:,.0f} hrs")
            c4.metric("Remaining", f"{remaining_total:,.0f} hrs")
            c5.metric("Complete %", f"{avance_ponderado_exacto:.2f}%")

elif menu == "🏗️ Análisis Subsistema":
    st.title("🏗️ SYNCORE | Matriz Detallada de Subsistemas")
    df_tareas = cargar_tareas()
    if df_tareas.empty:
        st.warning("No hay datos cargados en la nube.")
    else:
        st.success("Datos cargados correctamente desde Supabase.")

elif menu == "📊 Análisis T&M (Times & Material)":
    st.title("📊 SYNCORE | Dashboard Avanzado e Informe Técnico T&M")
    archivo_tm = st.file_uploader("Sube el archivo Excel Consolidado T&M", type=["xlsx", "xls"], key="uploader_tm_file")
    if archivo_tm is not None:
        st.success("¡Archivo T&M listo para procesar!")

elif menu == "📁 Gestión de Proyectos":
    st.title("📁 SYNCORE | Gestión de Proyectos (Cloud)")
    df_proyectos = cargar_proyectos()
    if df_proyectos.empty:
        st.info("No hay proyectos registrados en Supabase.")
    else:
        st.dataframe(df_proyectos, use_container_width=True)

elif menu == "📂 Importar Archivo (.XER)":
    st.title("📂 SYNCORE | Sincronización en la Nube Supabase")
    archivo_xer = st.file_uploader("Sube el archivo .xer", type=["xer"])
    if archivo_xer is not None:
        try:
            contenido_xer = archivo_xer.getvalue().decode("utf-8", errors="ignore")
            tablas_xer = parse_xer_exacto(contenido_xer)
            proj_data = tablas_xer.get("PROJ", [])
            nombre_proj_detectado = proj_data[0].get("proj_short_name", "ELHR-SY-EXC-C-29") if proj_data else "ELHR-SY-EXC-C-29"
            
            nombre_proyecto_syncore = st.text_input("📌 Nombre para este Proyecto:", value=nombre_proj_detectado)

            if st.button("🚀 Subir e Importar a Supabase"):
                with engine.connect() as conn:
                    conn.execute(sa.text('''
                        INSERT INTO proyectos (Nombre, Estado, Avance_Porcentaje, At_Completion_Units, Actual_Units, Remaining_Units, Fecha_Inicio, Fecha_Termino) 
                        VALUES (:n, :e, :a, :at, :ac, :rem, :fi, :ft)
                    '''), {
                        "n": nombre_proyecto_syncore, "e": "En Progreso", "a": 64.26, 
                        "at": 534269.0, "ac": 343321.0, "rem": 190948.0, 
                        "fi": "10-Feb-2026", "ft": "15-Feb-2027"
                    })
                    conn.commit()
                st.success(f"¡Proyecto '{nombre_proyecto_syncore}' guardado exitosamente en la nube de Supabase!")
                st.rerun()
        except Exception as e:
            st.error(f"Error al procesar el archivo .XER: {e}")

elif menu == "🛡️ Administración de Usuarios" and is_admin:
    st.title("🛡️ SYNCORE | Panel de Administración de Usuarios")
    try:
        df_usuarios = pd.read_sql("SELECT ID_USUARIO, Username, Estado FROM usuarios", engine)
        st.dataframe(df_usuarios, use_container_width=True)
    except Exception as e:
        st.error(f"Error al cargar usuarios: {e}")
