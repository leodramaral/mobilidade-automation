import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from persistencia.repositorio_banco import RepositorioBanco

st.set_page_config(page_title="Mobilidade", layout="wide")

with open("config.json") as f:
    config = json.load(f)

caminho_db = config["persistencia"]["caminho"]

if st.button("Consultar", type="primary"):
    repo = RepositorioBanco(caminho_db)
    repo.inicializar()

    snapshots = repo.listar_todos()
    repo.fechar()

    if not snapshots:
        st.warning("Nenhum dado encontrado no banco.")
    else:
        st.success(f"{len(snapshots)} snapshots encontrados")

        dados = [
            {"id": s.id, "timestamp": s.timestamp.isoformat(), "resultados": s.payload}
            for s in snapshots
        ]
        json_str = json.dumps(dados, ensure_ascii=False, indent=2)

        st.subheader("Resultado JSON")
        st.code(json_str, language="json")

        st.download_button(
            label="Baixar JSON",
            data=json_str,
            file_name="mobilidade_resultado.json",
            mime="application/json",
        )
