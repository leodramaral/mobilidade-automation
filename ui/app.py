import json
import sys
import threading
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coletor import Coletor
from persistencia.repositorio_banco import RepositorioBanco

st.set_page_config(page_title="Mobilidade", layout="wide")


def carregar_config():
    caminho_config = Path(__file__).resolve().parent.parent / "config.json"
    with open(caminho_config, encoding="utf-8") as f:
        return json.load(f)


def carregar_dados(caminho_db):
    repo = RepositorioBanco(caminho_db)
    repo.inicializar()
    snapshots = repo.listar_todos()
    repo.fechar()
    return snapshots


config = carregar_config()

with st.sidebar:
    st.header("Configuração da Coleta")

    coletando = st.session_state.get("coletando", False)

    destino = st.text_input("Destino", value=config.get("destino", ""), disabled=coletando)
    origem = st.text_input(
        "Origem",
        value=config.get("origem", ""),
        placeholder="Deixe vazio para usar a atual",
        disabled=coletando,
    )
    limite_consultas = st.number_input(
        "Limite de consultas",
        min_value=1,
        value=config.get("limite_consultas", 2),
        disabled=coletando,
    )
    intervalo_segundos = st.number_input(
        "Intervalo (segundos)",
        min_value=5,
        value=config.get("intervalo_segundos", 20),
        disabled=coletando,
    )

    st.divider()

    if not coletando:
        if st.button("Iniciar Coleta", use_container_width=True):
            config_coleta = {
                "origem": origem,
                "destino": destino,
                "limite_consultas": int(limite_consultas),
                "intervalo_segundos": int(intervalo_segundos),
                "appium": config["appium"],
                "persistencia": config["persistencia"],
            }
            coletor = Coletor(config_coleta, status_callback=print)
            thread = threading.Thread(target=coletor.executar, daemon=True)
            thread.start()
            st.session_state["coletor"] = coletor
            st.session_state["coletando"] = True
            st.session_state["thread_coleta"] = thread
            st.rerun()
    else:
        if st.button("Parar Coleta", use_container_width=True, type="primary"):
            st.session_state["coletor"].parar()
            st.session_state["coletando"] = False
            st.rerun()

    st.divider()

    if coletando:
        st.success("Coletando...")
    else:
        st.info("Parado")

if st.session_state.get("coletando", False):
    thread = st.session_state.get("thread_coleta")
    if thread and not thread.is_alive():
        st.session_state["coletando"] = False
        st.rerun()
    else:
        st.iframe(
            "<script>setTimeout(function(){window.parent.location.reload()}, 10000)</script>",
            height=1,
        )

caminho_db = config["persistencia"]["caminho"]
snapshots = carregar_dados(caminho_db)

if not snapshots:
    st.warning("Nenhum dado encontrado no banco.")
else:
    st.success(f"{len(snapshots)} snapshots encontrados")

    linhas = []
    for s in snapshots:
        for c in s.payload:
            linhas.append({
                "ID": s.id,
                "Timestamp": s.timestamp,
                "Device": s.device_model,
                "App": c.get("app", ""),
                "Categoria": c.get("categoria", ""),
                "Preço": c.get("preco_label", ""),
                "Estimativa": c.get("estimativa_label", ""),
                "Origem": c.get("origem", ""),
                "Destino": c.get("destino", ""),
            })

    df = pd.DataFrame(linhas)

    apps_unicos = sorted(df["App"].unique())
    categorias_unicas = sorted(df["Categoria"].unique())

    col1, col2 = st.columns(2)
    with col1:
        filtro_categoria = st.multiselect(
            "Categoria",
            options=categorias_unicas,
            default=[]
        )
    with col2:
        filtro_app = st.multiselect(
            "App",
            options=apps_unicos,
            default=[]
        )

    df_filtrado = df.copy()
    if filtro_categoria:
        df_filtrado = df_filtrado[df_filtrado["Categoria"].isin(filtro_categoria)]
    if filtro_app:
        df_filtrado = df_filtrado[df_filtrado["App"].isin(filtro_app)]
    df_filtrado = df_filtrado.sort_values("ID")

    st.dataframe(df_filtrado, width="stretch", hide_index=True)

    dados_filtrados = []
    for s in snapshots:
        itens_filtrados = []
        for c in s.payload:
            app_ok = not filtro_app or c.get("app", "") in filtro_app
            cat_ok = not filtro_categoria or c.get("categoria", "") in filtro_categoria
            if app_ok and cat_ok:
                itens_filtrados.append(c)
        if itens_filtrados:
            dados_filtrados.append({
                "id": s.id,
                "timestamp": s.timestamp.isoformat(),
                "resultados": itens_filtrados
            })

    json_str = json.dumps(dados_filtrados, ensure_ascii=False, indent=2)
    st.download_button(
        label="Baixar JSON",
        data=json_str,
        file_name="mobilidade_resultado.json",
        mime="application/json",
    )
