from typing import List, Dict, Any
from datetime import datetime
import pandas as pd


def _snapshots_para_df(snapshots: List[Any]) -> pd.DataFrame:
    linhas = []
    for s in snapshots:
        for c in s.payload:
            m = c.get("metricas") or {}
            linhas.append({
                "timestamp": s.timestamp,
                "app": s.app,
                "origem": s.origem,
                "destino": s.destino,
                "categoria": c.get("categoria", ""),
                "preco": c.get("preco", 0),
                "estimativa_min": c.get("estimativa_min", 0),
                "preco_base": m.get("preco_base"),
                "preco_minimo": m.get("preco_minimo"),
                "adicional_por_minuto": m.get("adicional_por_minuto"),
                "adicional_por_km": m.get("adicional_por_km"),
                "custo_fixo": m.get("custo_fixo"),
            })
    return pd.DataFrame(linhas)


def resumo_geral(snapshots: List[Any]) -> Dict[str, Any]:
    if not snapshots:
        return {}

    df = _snapshots_para_df(snapshots)

    timestamps = [s.timestamp for s in snapshots]
    min_ts = min(timestamps)
    max_ts = max(timestamps)

    return {
        "total_snapshots": len(snapshots),
        "total_corridas": len(df),
        "periodo_inicio": min_ts,
        "periodo_fim": max_ts,
        "rotas_monitoradas": df[["origem", "destino"]].drop_duplicates().shape[0],
        "categorias": sorted(df["categoria"].unique().tolist()),
        "preco_medio_geral": round(df["preco"].mean(), 2) if len(df) > 0 else 0,
        "apps": sorted(df["app"].unique().tolist()),
    }


def analise_precos_por_categoria(snapshots: List[Any]) -> pd.DataFrame:
    df = _snapshots_para_df(snapshots)
    if df.empty:
        return pd.DataFrame()

    df["data"] = df["timestamp"].dt.date

    agg = (
        df.groupby(["data", "categoria", "app"])
        .agg(
            preco_medio=("preco", "mean"),
            preco_mediana=("preco", "median"),
            preco_min=("preco", "min"),
            preco_max=("preco", "max"),
            desvio_padrao=("preco", "std"),
            total_observacoes=("preco", "count"),
        )
        .reset_index()
    )

    agg["preco_medio"] = agg["preco_medio"].round(2)
    agg["preco_mediana"] = agg["preco_mediana"].round(2)
    agg["desvio_padrao"] = agg["desvio_padrao"].round(2)

    return agg.sort_values(["data", "categoria"])


def analise_por_rota(snapshots: List[Any]) -> pd.DataFrame:
    df = _snapshots_para_df(snapshots)
    if df.empty:
        return pd.DataFrame()

    agg = (
        df.groupby(["origem", "destino", "categoria", "app"])
        .agg(
            preco_medio=("preco", "mean"),
            preco_min=("preco", "min"),
            preco_max=("preco", "max"),
            total_snapshots=("preco", "count"),
        )
        .reset_index()
    )

    agg["preco_medio"] = agg["preco_medio"].round(2)
    agg["variacao_pct"] = (
        ((agg["preco_max"] - agg["preco_min"]) / agg["preco_min"] * 100)
        .round(2)
        .fillna(0)
    )

    return agg.sort_values("preco_medio", ascending=False)
