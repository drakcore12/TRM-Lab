"""TRM Lab — Dashboard de cajas USD/COP.

Aplicación Python con servidor HTTP de biblioteca estándar. Datos oficiales de la
Superintendencia Financiera de Colombia, vía Datos Abiertos (Socrata).
Arrancar con: python app.py (o PORT=10000 python app.py en Render).
"""
from __future__ import annotations

import csv
import io
import json
import logging
import math
import os
import threading
import time
from datetime import datetime, date, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import requests
import seaborn as sns

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
CACHE = ROOT / "trm_snapshot.csv"
SOURCE_API = "https://www.datos.gov.co/resource/32sa-8pi3.json"
SOURCE_PAGE = "https://www.datos.gov.co/Econom-a-y-Finanzas/Tasa-de-Cambio-Representativa-del-Mercado-TRM/32sa-8pi3"
BOGOTA = ZoneInfo("America/Bogota")
CACHE_TTL = 20 * 60  # segundos
MIN_DATE = date(1991, 12, 2)
LOG = logging.getLogger("trm")

_state_lock = threading.RLock()
_graph_lock = threading.Lock()
_state = {"df": None, "fetched": 0.0, "updated": None, "source": None, "warning": None}


def load_remote() -> pd.DataFrame:
    """No inventa datos: descarga registros oficiales de TRM desde 2020."""
    params = {
        "$select": "valor,unidad,vigenciadesde,vigenciahasta",
        "$where": "vigenciadesde >= '2020-01-01T00:00:00'",
        "$order": "vigenciadesde ASC",
        "$limit": "10000",
    }
    result = requests.get(SOURCE_API, params=params, timeout=(8, 24), headers={
        "Accept": "application/json", "User-Agent": "TRMLab-Educativo/1.0"
    })
    result.raise_for_status()
    rows = result.json()
    if not isinstance(rows, list) or not rows:
        raise ValueError("La API no devolvió registros.")
    frame = pd.DataFrame.from_records(rows)
    return clean_frame(frame)


def clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Una observación por comienzo de vigencia; no rellena fines de semana."""
    if not {"valor", "vigenciadesde"}.issubset(frame.columns):
        raise ValueError("Faltan los campos oficiales 'valor' o 'vigenciadesde'.")
    df = frame.copy()
    df["fecha"] = pd.to_datetime(df["vigenciadesde"], errors="coerce").dt.normalize()
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    today = datetime.now(BOGOTA).date()
    df = df.dropna(subset=["fecha", "valor"])
    df = df[(df["valor"] > 0) & (df["fecha"].dt.date <= today)]
    df = df.drop_duplicates(subset=["fecha"], keep="last").sort_values("fecha")
    if df.empty:
        raise ValueError("No quedaron valores de TRM válidos.")
    return df[["fecha", "valor"]].reset_index(drop=True)


def read_snapshot() -> pd.DataFrame | None:
    if not CACHE.exists():
        return None
    try:
        df = pd.read_csv(CACHE)
        if {"fecha", "valor"}.issubset(df.columns):
            df["vigenciadesde"] = df["fecha"]
            return clean_frame(df)
    except Exception as exc:
        LOG.warning("No pudo leerse el respaldo: %s", exc)
    return None


def snapshot(df: pd.DataFrame) -> None:
    try:
        temp = CACHE.with_suffix(".tmp")
        df.to_csv(temp, index=False, date_format="%Y-%m-%d")
        temp.replace(CACHE)
    except OSError as exc:
        LOG.warning("Respaldo no persistente (esperable en Render): %s", exc)


def get_data(force=False) -> tuple[pd.DataFrame, dict]:
    now = time.time()
    with _state_lock:
        if not force and _state["df"] is not None and now - _state["fetched"] < CACHE_TTL:
            return _state["df"].copy(), {k: _state[k] for k in ("source", "updated", "warning")}
        try:
            df = load_remote()
            _state.update(df=df, fetched=now, source="api", updated=datetime.now(BOGOTA).isoformat(), warning=None)
            snapshot(df)
        except (requests.RequestException, ValueError, KeyError) as exc:
            LOG.error("No se pudo cargar TRM: %s", exc)
            if _state["df"] is None:
                stored = read_snapshot()
                if stored is not None:
                    _state.update(df=stored, source="respaldo", updated=None)
            if _state["df"] is None:
                raise DataUnavailable("La fuente oficial no está disponible y aún no hay respaldo. Vuelve a intentar en unos minutos.") from exc
            _state.update(fetched=now, warning="No se pudo actualizar la fuente. Se muestran los últimos datos guardados.")
        return _state["df"].copy(), {k: _state[k] for k in ("source", "updated", "warning")}


class DataUnavailable(Exception):
    pass


def parse_filters(query: dict, df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    maxdate = df["fecha"].max().date()
    earliest = df["fecha"].min().date()
    default_from = max(earliest, maxdate - timedelta(days=730))

    def parse_date(key, fallback):
        val = query.get(key, [""])[0]
        if not val:
            return fallback
        try:
            return date.fromisoformat(val)
        except ValueError as err:
            raise ValueError(f"La fecha '{key}' debe tener formato AAAA-MM-DD.") from err

    start = parse_date("start", default_from)
    end = parse_date("end", maxdate)
    if start > end:
        raise ValueError("La fecha inicial no puede superar la fecha final.")
    if (end - start).days > 365 * 10:
        raise ValueError("Selecciona un intervalo de diez años como máximo.")
    group = query.get("group", ["month"])[0]
    if group not in ("month", "quarter", "year"):
        raise ValueError("Agrupación no válida.")
    result = df[(df["fecha"].dt.date >= start) & (df["fecha"].dt.date <= end)].copy()
    if result.empty:
        raise ValueError("No hay observaciones oficiales en el periodo elegido.")
    month_names = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    result["anio"] = result["fecha"].dt.year.astype(int)
    result["mes"] = result["fecha"].dt.month.astype(int)
    if group == "month":
        result["grupo"] = result.apply(lambda x: f"{month_names[x['mes']-1]} {x['anio']}", axis=1)
    elif group == "quarter":
        result["grupo"] = result.apply(lambda x: f"T{(x['mes'] - 1)//3 + 1} {x['anio']}", axis=1)
    else:
        result["grupo"] = result["anio"].astype(str)
    return result, {"start": start.isoformat(), "end": end.isoformat(), "group": group}


def number(value: float | None, digits=2):
    return round(float(value), digits) if value is not None and math.isfinite(float(value)) else None


def build_payload(df: pd.DataFrame, filtered: pd.DataFrame, filt: dict, meta: dict) -> dict:
    values = filtered["valor"]
    latest = df.iloc[-1]
    prior = df.iloc[-2] if len(df) > 1 else latest
    groups = []
    for name, part in filtered.groupby("grupo", sort=False):
        vals = part["valor"]
        groups.append({
            "name": name, "count": int(len(part)), "values": [number(v) for v in vals],
            "min": number(vals.min()), "q1": number(vals.quantile(.25)),
            "median": number(vals.median()), "q3": number(vals.quantile(.75)), "max": number(vals.max()),
        })
    q1 = float(values.quantile(.25)); q3 = float(values.quantile(.75))
    low = q1 - 1.5*(q3-q1); high = q3 + 1.5*(q3-q1)
    outliers = int(((values < low) | (values > high)).sum())
    # Promedio mensual por mes de calendario y año: una matriz de calor.
    heat = filtered.pivot_table(index="anio", columns="mes", values="valor", aggfunc="mean")
    heatmap = []
    for year, row in heat.iterrows():
        heatmap.append({"year": int(year), "months": [number(row.get(i)) for i in range(1, 13)]})
    series = [{"date": f.strftime("%Y-%m-%d"), "value": number(v)} for f, v in zip(filtered["fecha"], filtered["valor"])]
    return {
        "status": "ok", "meta": {
            "source": SOURCE_PAGE, "source_mode": meta["source"], "warning": meta["warning"],
            "consulted_at": meta["updated"], "latest_date": latest["fecha"].date().isoformat(),
            "coverage_start": df["fecha"].min().date().isoformat(), "coverage_end": df["fecha"].max().date().isoformat(),
            "refresh_minutes": CACHE_TTL // 60, "official": True, "filters": filt,
        },
        "stats": {
            "latest": number(latest["valor"]), "previous": number(prior["valor"]),
            "change": number(latest["valor"]-prior["valor"]),
            "change_pct": number(100*(latest["valor"]/prior["valor"]-1)),
            "mean": number(values.mean()), "median": number(values.median()),
            "std": number(values.std(ddof=1)) if len(values)>1 else 0,
            "min": number(values.min()), "max": number(values.max()),
            "q1": number(q1), "q3": number(q3), "iqr": number(q3-q1),
            "outliers": outliers, "observations": int(len(values)),
            "first": number(values.iloc[0]), "last": number(values.iloc[-1]),
            "range_change_pct": number(100*(values.iloc[-1]/values.iloc[0]-1)),
        },
        "groups": groups, "series": series, "heatmap": heatmap,
    }


def seaborn_png(frame: pd.DataFrame) -> bytes:
    """Seaborn nativo: el servidor regenera una imagen según los filtros."""
    with _graph_lock:
        sns.set_theme(style="darkgrid", context="notebook", font_scale=1.02)
        fig, ax = plt.subplots(figsize=(11.2, 4.2), dpi=150)
        fig.patch.set_facecolor("#111114")
        ax.set_facecolor("#111114")
        order = list(dict.fromkeys(frame["grupo"].to_list()))
        sns.boxplot(data=frame, x="grupo", y="valor", order=order, ax=ax,
                    color="#f5474f", saturation=0.75, fliersize=3, linewidth=1.15,
                    medianprops={"color":"#ffe1b9", "linewidth":2.4},
                    boxprops={"edgecolor":"#fbb0a9"}, whiskerprops={"color":"#c58d8f"},
                    capprops={"color":"#c58d8f"})
        ax.set_title("Distribución de la TRM · Análisis Seaborn", loc="left", fontsize=14, weight="bold", color="#fff2e5", pad=20)
        ax.set_ylabel("COP por USD", color="#e1c7ba", labelpad=14)
        ax.set_xlabel("")
        ax.tick_params(axis="x", colors="#e1c7ba", rotation=45, labelsize=8)
        ax.tick_params(axis="y", colors="#e1c7ba", labelsize=9)
        ax.grid(axis="y", color="#3a262b", alpha=.75)
        ax.grid(axis="x", visible=False)
        for edge in ax.spines.values(): edge.set_visible(False)
        if len(order) > 28:
            step = math.ceil(len(order)/22)
            for i, lab in enumerate(ax.get_xticklabels()):
                lab.set_visible(i % step == 0)
        fig.subplots_adjust(left=.095,right=.985,top=.82,bottom=.24)
        output = io.BytesIO()
        fig.savefig(output, format="png", facecolor=fig.get_facecolor())
        plt.close(fig)
        return output.getvalue()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def reply(self, data: bytes, code=200, content_type="application/json; charset=utf-8", cache=False):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400" if cache else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try: self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError): pass

    def do_GET(self):
        path = urlparse(self.path)
        try:
            if path.path == "/api/health":
                return self.reply(b'{"status":"ok"}')
            if path.path in ("/api/trm", "/api/seaborn.png", "/api/export.csv"):
                q = parse_qs(path.query)
                force = q.get("refresh", ["0"])[0] == "1"
                df, meta = get_data(force=force)
                selected, filt = parse_filters(q, df)
                if path.path == "/api/trm":
                    payload = build_payload(df, selected, filt, meta)
                    return self.reply(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"))
                if path.path == "/api/seaborn.png":
                    return self.reply(seaborn_png(selected), content_type="image/png")
                content = io.StringIO()
                writer = csv.writer(content)
                writer.writerow(["fecha", "trm_cop_por_usd", "fuente"])
                writer.writerows((dt.strftime("%Y-%m-%d"), f"{value:.2f}", "Superfinanciera / datos.gov.co") for dt, value in zip(selected["fecha"], selected["valor"]))
                self.send_response(200)
                data = ('\ufeff' + content.getvalue()).encode('utf-8')
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="TRM_Colombia.csv"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                return self.wfile.write(data)
            if path.path == "/":
                self.path = "/index.html"
            return super().do_GET()
        except ValueError as exc:
            return self.reply(json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"), 400)
        except DataUnavailable as exc:
            return self.reply(json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"), 503)
        except Exception:
            LOG.exception("Error inesperado en la petición")
            return self.reply(json.dumps({"error": "Error interno. Reintenta la operación."}).encode("utf-8"), 500)

    def log_message(self, fmt, *args):
        LOG.info("%s - %s", self.address_string(), fmt % args)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    port = int(os.environ.get("PORT", 10000))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    LOG.info("TRM Lab listo en http://localhost:%s", port)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == "__main__":
    main()