import streamlit as st
import pandas as pd
import sqlite3
import os
import hashlib
import base64
import uuid
from datetime import datetime

# --- CONFIGURAÇÕES DE DIRETÓRIO ---
DB_PATH = "condominio_final_v10.db"
UPLOAD_DIR = "evidencias"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# --- FUNÇÕES DE SEGURANÇA E CÁLCULO ---
def hash_password(plain: str) -> str:
    salt = b'salt_condo_pro_2026_final' 
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, 100_000)
    return base64.b64encode(dk).decode()

def verify_password(plain: str, stored: str) -> bool:
    return hash_password(plain) == stored

def calcular_tempo_finalizacao(data_inicio_str, data_fim_str):
    try:
        fmt = "%d/%m/%Y %H:%M"
        inicio = datetime.strptime(data_inicio_str, fmt)
        fim = datetime.strptime(data_fim_str, fmt)
        diferenca = fim - inicio
        dias, segundos = diferenca.days, diferenca.seconds
        horas = segundos // 3600
        minutos = (segundos // 60) % 60
        res = []
        if dias > 0: res.append(f"{dias}d")
        if horas > 0: res.append(f"{horas}h")
        if minutos > 0 or not res: res.append(f"{minutos}min")
        return " ".join(res)
    except: return "N/A"

# --- BANCO DE DADOS ---
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, role TEXT NOT NULL)")
    cur.execute("""CREATE TABLE IF NOT EXISTS ocorrencias (
                    id TEXT PRIMARY KEY, tipo_registro TEXT, categoria TEXT NOT NULL, 
                    local_detalhado TEXT, descricao TEXT NOT NULL, foto_path TEXT, 
                    status TEXT DEFAULT 'Pendente', data_envio TEXT, data_conclusao TEXT)""")
    if not cur.execute("SELECT * FROM usuarios WHERE username = 'admin'").fetchone():
        cur.execute("INSERT INTO usuarios VALUES (?, ?, ?)", ("admin", hash_password("admin123"), "admin"))
    conn.commit()
    conn.close()

init_db()

# --- INTERFACE ---
st.set_page_config(page_title="Condomínio Pro", layout="centered", page_icon="🏢")

# Ajuste no CSS: Removida altura fixa (height) para evitar corte de texto nos widgets
st.markdown("""
    <style>
    .status-pendente { color: #FFD700; font-weight: bold; font-size: 1.1em; }
    .status-manutencao { color: #FF4B4B; font-weight: bold; font-size: 1.1em; }
    .status-concluido { color: #28A745; font-weight: bold; font-size: 1.1em; }
    .stButton>button { width: 100%; border-radius: 12px; font-weight: bold; margin-top: 10px; }
    [data-testid="stExpander"] { border-radius: 10px; border: 1px solid #eee; }
    /* Garante que o selectbox tenha espaço para o texto */
    .stSelectbox div[data-baseweb="select"] { min-height: 45px; }
    </style>
    """, unsafe_allow_html=True)

if "auth_adm" not in st.session_state:
    st.session_state.auth_adm = False

st.sidebar.title("🏢 Gestão Pro")
menu = st.sidebar.radio("Navegação", ["📝 Abrir Registro", "🔍 Consultar Protocolo", "📊 Painel Administrativo"])

# --- 1. ABRIR REGISTRO ---
if menu == "📝 Abrir Registro":
    st.header("Novo Registro")
    with st.container(border=True):
        tipo_reg = st.radio("O que deseja realizar?", ["Abertura de Chamado", "Denúncia"], horizontal=True)
        if tipo_reg == "Denúncia":
            st.info("🔒 **Sua denúncia é 100% anônima.** O síndico verá apenas o relato e o local.")
        
        cat_sel = st.selectbox("Área:", ["Corredor", "Garagem", "Jardim", "Academia", "Elevador", "Piscina", "Outros"])
        detalhe = st.text_input("Localização específica (ex: Bloco A, Vaga 15):")
        desc = st.text_area("Relato da Ocorrência:", placeholder="Descreva os detalhes aqui...")
        foto = st.file_uploader("📸 Anexar Foto (Opcional)", type=["jpg", "png", "jpeg"])
        
        if st.button("ENVIAR REGISTRO", type="primary"):
            if desc:
                prot = str(uuid.uuid4())[:8].upper()
                path = None
                if foto:
                    path = os.path.join(UPLOAD_DIR, f"{prot}_{foto.name}")
                    with open(path, "wb") as f: f.write(foto.getbuffer())
                
                with get_conn() as conn:
                    conn.execute("INSERT INTO ocorrencias (id, tipo_registro, categoria, local_detalhado, descricao, foto_path, data_envio) VALUES (?,?,?,?,?,?,?)",
                                (prot, tipo_reg, cat_sel, detalhe, desc, path, datetime.now().strftime("%d/%m/%Y %H:%M")))
                st.success(f"✅ Enviado! Seu Protocolo: **{prot}**")
            else: st.error("Por favor, preencha o relato da ocorrência.")

# --- 2. CONSULTAR PROTOCOLO ---
elif menu == "🔍 Consultar Protocolo":
    st.header("Acompanhar Status")
    busca = st.text_input("Digite o seu Protocolo:").upper().strip()
    if busca:
        with get_conn() as conn:
            res = conn.execute("SELECT * FROM ocorrencias WHERE id = ?", (busca,)).fetchone()
        if res:
            with st.container(border=True):
                status = res[6]
                if status == "Pendente": st.warning(f"Status Atual: {status} 🟡")
                elif status == "Em Manutenção": st.error(f"Status Atual: {status} 🔴")
                else: st.success(f"Status Atual: {status} 🟢")
                
                st.write(f"**Relato:** {res[4]}")
                st.caption(f"Aberto em: {res[7]}")
                if res[8]:
                    tempo = calcular_tempo_finalizacao(res[7], res[8])
                    st.write(f"⏱️ **Tempo total de resolução:** {tempo}")
                if res[5]: st.image(res[5])
        else: st.error("Protocolo não localizado.")

# --- 3. PAINEL ADM ---
elif menu == "📊 Painel Administrativo":
    if not st.session_state.auth_adm:
        st.header("Acesso Restrito")
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            with get_conn() as conn:
                db_res = conn.execute("SELECT password_hash FROM usuarios WHERE username = ?", (u,)).fetchone()
            if db_res and verify_password(p, db_res[0]):
                st.session_state.auth_adm = True
                st.rerun()
            else: st.error("Acesso negado.")
    else:
        st.header("Painel Administrativo")
        tab1, tab2, tab3 = st.tabs(["⚡ Atendimentos", "📋 Relatórios", "👤 Novo ADM"])
        
        with tab1:
            df = pd.read_sql("SELECT * FROM ocorrencias WHERE status != 'Concluído' ORDER BY data_envio DESC", get_conn())
            if df.empty: st.info("Não há chamados pendentes.")
            for _, row in df.iterrows():
                cor_emoji = "🟡" if row['status'] == "Pendente" else "🔴"
                with st.expander(f"{cor_emoji} {row['id']} - {row['tipo_registro']}"):
                    if row['status'] == "Pendente":
                        st.markdown('<p class="status-pendente">Aguardando Início</p>', unsafe_allow_html=True)
                    else:
                        st.markdown('<p class="status-manutencao">Em Execução</p>', unsafe_allow_html=True)
                    
                    st.write(f"**Local:** {row['categoria']} ({row['local_detalhado']})")
                    st.write(f"**Relato:** {row['descricao']}")
                    if row['foto_path']: st.image(row['foto_path'])
                    
                    # --- CORREÇÃO DO SELECTBOX ---
                    opcoes_status = ["Pendente", "Em Manutenção", "Concluído"]
                    idx_status = opcoes_status.index(row['status']) if row['status'] in opcoes_status else 0
                    
                    novo_st = st.selectbox(
                        "Mudar Status:", 
                        opcoes_status, 
                        index=idx_status,
                        key=f"status_{row['id']}"
                    )
                    
                    if st.button("Salvar Alteração", key=f"btn_{row['id']}", type="primary"):
                        data_fim = datetime.now().strftime("%d/%m/%Y %H:%M") if novo_st == "Concluído" else None
                        with get_conn() as conn:
                            conn.execute("UPDATE ocorrencias SET status = ?, data_conclusao = ? WHERE id = ?", (novo_st, data_fim, row['id']))
                        st.rerun()

        with tab2:
            st.subheader("Eficiência de Resolução 🟢")
            df_concluidos = pd.read_sql("SELECT * FROM ocorrencias WHERE status = 'Concluído'", get_conn())
            if not df_concluidos.empty:
                df_concluidos['Tempo Total'] = df_concluidos.apply(lambda r: calcular_tempo_finalizacao(r['data_envio'], r['data_conclusao']), axis=1)
                st.dataframe(df_concluidos[['id', 'tipo_registro', 'data_envio', 'data_conclusao', 'Tempo Total']], use_container_width=True, hide_index=True)
            else: st.info("Ainda não há chamados concluídos.")

        with tab3:
            st.subheader("Cadastrar Novo ADM")
            nu = st.text_input("Login")
            np = st.text_input("Senha", type="password")
            if st.button("Criar Acesso"):
                if nu and np:
                    try:
                        with get_conn() as conn:
                            conn.execute("INSERT INTO usuarios VALUES (?, ?, ?)", (nu, hash_password(np), "admin"))
                        st.success("Administrador cadastrado!")
                    except: st.error("Erro: Usuário já existe.")

        if st.sidebar.button("Sair do Painel"):
            st.session_state.auth_adm = False
            st.rerun()