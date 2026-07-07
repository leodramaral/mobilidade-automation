import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from persistencia.repositorio_banco import RepositorioBanco

st.set_page_config(page_title="Mobilidade", layout="wide")

with open("config.json") as f:
    config = json.load(f)

caminho_db = config["persistencia"]["caminho"]

repo = RepositorioBanco(caminho_db)
repo.inicializar()
snapshots = repo.listar_todos()
repo.fechar()

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
