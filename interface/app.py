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

    st.dataframe(df, width="stretch", hide_index=True)

    dados = [
        {"id": s.id, "timestamp": s.timestamp.isoformat(), "resultados": s.payload}
        for s in snapshots
    ]
    json_str = json.dumps(dados, ensure_ascii=False, indent=2)

    st.download_button(
        label="Baixar JSON",
        data=json_str,
        file_name="mobilidade_resultado.json",
        mime="application/json",
    )
