import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for mod_name in list(sys.modules):
    if mod_name.startswith('modelos') or mod_name.startswith('persistencia') or mod_name.startswith('analises'):
        del sys.modules[mod_name]

from persistencia.repositorio_banco import RepositorioBanco
from analises.insights import (
    resumo_geral,
    analise_precos_por_categoria,
    analise_por_rota,
)

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
    st.stop()

# ── Filtros ──────────────────────────────────────────────────────────────────
linhas = []
for s in snapshots:
    for c in s.payload:
        m = c.get("metricas") or {}
        linhas.append({
            "ID": s.id,
            "Timestamp": s.timestamp,
            "Categoria": c.get("categoria", ""),
            "Preco": c.get("preco", 0),
            "Estimativa": c.get("estimativa_min", 0),
            "Origem": s.origem,
            "Destino": s.destino,
            "App": s.app,
            "Pr. Base": m.get("preco_base"),
            "Pr. Minimo": m.get("preco_minimo"),
            "R$/min": m.get("adicional_por_minuto"),
            "R$/km": m.get("adicional_por_km"),
            "Custo Fixo": m.get("custo_fixo"),
        })

df = pd.DataFrame(linhas)

apps_unicos = sorted(df["App"].unique())
categorias_unicas = sorted(df["Categoria"].unique())

col1, col2 = st.columns(2)
with col1:
    filtro_categoria = st.multiselect("Categoria", options=categorias_unicas, default=[])
with col2:
    filtro_app = st.multiselect("App", options=apps_unicos, default=[])

df_filtrado = df.copy()
if filtro_categoria:
    df_filtrado = df_filtrado[df_filtrado["Categoria"].isin(filtro_categoria)]
if filtro_app:
    df_filtrado = df_filtrado[df_filtrado["App"].isin(filtro_app)]
df_filtrado = df_filtrado.sort_values("ID")

# ── Abas ─────────────────────────────────────────────────────────────────────
aba_geral, aba_categoria, aba_rota, aba_dados = st.tabs([
    "Visao Geral", "Por Categoria", "Por Rota", "Dados"
])

# ── Visao Geral ──────────────────────────────────────────────────────────────
with aba_geral:
    resumo = resumo_geral(snapshots)

    if resumo:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Snapshots", resumo["total_snapshots"])
        c2.metric("Corridas", resumo["total_corridas"])
        c3.metric("Rotas", resumo["rotas_monitoradas"])
        c4.metric("Preco Medio", f"R$ {resumo['preco_medio_geral']:.2f}".replace(".", ","))

        st.caption(f"Periodo: {resumo['periodo_inicio'].strftime('%d/%m/%Y %H:%M')} a {resumo['periodo_fim'].strftime('%d/%m/%Y %H:%M')}")
        st.caption(f"Categorias: {', '.join(resumo['categorias'])}")

    # Grafico de evolucao temporal
    st.subheader("Evolucao do Preco Medio por Categoria")
    df_tempo = df_filtrado.copy()
    df_tempo["Data"] = df_tempo["Timestamp"].dt.date
    evolucao = (
        df_tempo.groupby(["Data", "Categoria"])["Preco"]
        .mean()
        .reset_index()
        .sort_values("Data")
    )
    if not evolucao.empty:
        st.line_chart(
            evolucao.pivot(index="Data", columns="Categoria", values="Preco"),
            use_container_width=True,
        )

# ── Por Categoria ────────────────────────────────────────────────────────────
with aba_categoria:
    st.subheader("Analise de Precos por Categoria")
    df_cat = analise_precos_por_categoria(snapshots)

    if df_cat.empty:
        st.info("Sem dados suficientes para analise por categoria.")
    else:
        if filtro_categoria:
            df_cat = df_cat[df_cat["categoria"].isin(filtro_categoria)]
        if filtro_app:
            df_cat = df_cat[df_cat["app"].isin(filtro_app)]

        st.dataframe(
            df_cat.rename(columns={
                "data": "Data",
                "categoria": "Categoria",
                "app": "App",
                "preco_medio": "Preco Medio",
                "preco_mediana": "Mediana",
                "preco_min": "Minimo",
                "preco_max": "Maximo",
                "desvio_padrao": "Desvio Padrao",
                "total_observacoes": "Obs.",
            }),
            use_container_width=True,
            hide_index=True,
        )

        # Grafico de barras comparativo
        st.subheader("Preco Medio por Categoria")
        resumo_cat = (
            df_cat.groupby("categoria")["preco_medio"]
            .mean()
            .sort_values(ascending=False)
            .reset_index()
        )
        if not resumo_cat.empty:
            st.bar_chart(
                resumo_cat.rename(columns={"categoria": "Categoria", "preco_medio": "Preco Medio"})
                .set_index("Categoria"),
                use_container_width=True,
            )

# ── Por Rota ─────────────────────────────────────────────────────────────────
with aba_rota:
    st.subheader("Analise por Rota (Origem -> Destino)")
    df_rota = analise_por_rota(snapshots)

    if df_rota.empty:
        st.info("Sem dados suficientes para analise por rota.")
    else:
        if filtro_categoria:
            df_rota = df_rota[df_rota["categoria"].isin(filtro_categoria)]
        if filtro_app:
            df_rota = df_rota[df_rota["app"].isin(filtro_app)]

        st.dataframe(
            df_rota.rename(columns={
                "origem": "Origem",
                "destino": "Destino",
                "categoria": "Categoria",
                "app": "App",
                "preco_medio": "Preco Medio",
                "preco_min": "Minimo",
                "preco_max": "Maximo",
                "total_snapshots": "Snapshots",
                "variacao_pct": "Variacao %",
            }),
            use_container_width=True,
            hide_index=True,
        )

        # Ranking de rotas mais caras
        st.subheader("Top 10 Rotas Mais Caras")
        top_rotas = df_rota.head(10)[["origem", "destino", "categoria", "preco_medio"]].copy()
        top_rotas["Rota"] = top_rotas["origem"] + " → " + top_rotas["destino"]
        top_rotas = top_rotas.rename(columns={
            "categoria": "Categoria",
            "preco_medio": "Preco Medio",
        })
        if not top_rotas.empty:
            st.bar_chart(
                top_rotas[["Rota", "Preco Medio"]].set_index("Rota"),
                use_container_width=True,
            )

# ── Dados ────────────────────────────────────────────────────────────────────
with aba_dados:
    st.subheader("Dados Filtrados")

    df_exibicao = df_filtrado[[
        "ID", "Timestamp", "Categoria", "Preco", "Estimativa",
        "Origem", "Destino", "App", "Pr. Base", "Pr. Minimo",
        "R$/min", "R$/km", "Custo Fixo",
    ]].copy()
    df_exibicao["Preco"] = df_exibicao["Preco"].apply(lambda x: f"R$ {x:.2f}".replace(".", ","))
    df_exibicao["Estimativa"] = df_exibicao["Estimativa"].apply(lambda x: f"{x} min" if x else "")
    df_exibicao["Pr. Base"] = df_exibicao["Pr. Base"].apply(
        lambda x: f"R$ {x:.2f}".replace(".", ",") if pd.notna(x) else ""
    )
    df_exibicao["Pr. Minimo"] = df_exibicao["Pr. Minimo"].apply(
        lambda x: f"R$ {x:.2f}".replace(".", ",") if pd.notna(x) else ""
    )
    df_exibicao["R$/min"] = df_exibicao["R$/min"].apply(
        lambda x: f"R$ {x:.2f}".replace(".", ",") if pd.notna(x) else ""
    )
    df_exibicao["R$/km"] = df_exibicao["R$/km"].apply(
        lambda x: f"R$ {x:.2f}".replace(".", ",") if pd.notna(x) else ""
    )
    df_exibicao["Custo Fixo"] = df_exibicao["Custo Fixo"].apply(
        lambda x: f"R$ {x:.2f}".replace(".", ",") if pd.notna(x) else ""
    )

    st.dataframe(df_exibicao, use_container_width=True, hide_index=True)

    # Download JSON
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
