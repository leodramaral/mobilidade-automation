import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for mod_name in list(sys.modules):
    if mod_name.startswith('modelos') or mod_name.startswith('persistencia'):
        del sys.modules[mod_name]

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

caminho_db = config["persistencia"]["caminho"]
snapshots = carregar_dados(caminho_db)

if not snapshots:
    st.warning("Nenhum dado encontrado no banco.")
else:
    st.success(f"{len(snapshots)} snapshots encontrados")

    linhas = []
    for s in snapshots:
        for c in s.payload:
            m = c.get("metricas") or {}
            linhas.append({
                "ID": s.id,
                "Timestamp": s.timestamp,
                "Categoria": c.get("categoria", ""),
                "Preço": f"R$ {c.get('preco', 0):.2f}".replace(".", ","),
                "Estimativa": f"{c.get('estimativa_min', 0)} min" if c.get("estimativa_min") else "",
                "Origem": s.origem,
                "Destino": s.destino,
                "Pr. Base": f"R$ {m['preco_base']:.2f}".replace(".", ",") if m.get("preco_base") is not None else "",
                "Pr. Mínimo": f"R$ {m['preco_minimo']:.2f}".replace(".", ",") if m.get("preco_minimo") is not None else "",
                "R$/min": f"R$ {m['adicional_por_minuto']:.2f}".replace(".", ",") if m.get("adicional_por_minuto") is not None else "",
                "R$/km": f"R$ {m['adicional_por_km']:.2f}".replace(".", ",") if m.get("adicional_por_km") is not None else "",
                "Custo Fixo": f"R$ {m['custo_fixo']:.2f}".replace(".", ",") if m.get("custo_fixo") is not None else "",
                "Temp (°C)": getattr(s, 'temperatura', None),
                "Cond. Tempo": getattr(s, 'condicao_tempo', ""),
                "Device": s.device_model,
                "App": s.app,
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
            app_ok = not filtro_app or s.app in filtro_app
            cat_ok = not filtro_categoria or c.get("categoria", "") in filtro_categoria
            if app_ok and cat_ok:
                itens_filtrados.append(c)
        if itens_filtrados:
            dados_filtrados.append({
                "id": s.id,
                "timestamp": s.timestamp.isoformat(),
                "app": s.app,
                "origem": s.origem,
                "destino": s.destino,
                "temperatura": getattr(s, 'temperatura', None),
                "condicao_tempo": getattr(s, 'condicao_tempo', ""),
                "resultados": itens_filtrados
            })

    json_str = json.dumps(dados_filtrados, ensure_ascii=False, indent=2)
    st.download_button(
        label="Baixar JSON",
        data=json_str,
        file_name="mobilidade_resultado.json",
        mime="application/json",
    )
