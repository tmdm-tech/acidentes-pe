#!/usr/bin/env python3
"""
Projeto cartográfico científico (padrão IBGE) para mapas KDE de acidentes em Pernambuco.

Gera 3 conjuntos de mapas:
1) Mapa estadual geral de densidade.
2) 5 mapas municipais individuais.
3) 5 mapas municipais apenas com acidentes motociclísticos.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import contextily as cx
import geobr
import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Polygon
from rasterio.features import geometry_mask
from rasterio.transform import from_bounds
from scipy.ndimage import gaussian_filter
from scipy.stats import gaussian_kde
from shapely.geometry import Point


# Sistema de referencia solicitado no enunciado.
TARGET_CRS = "EPSG:31985"  # SIRGAS 2000 / UTM zone 25S
OUTPUT_DIR = Path("outputs")
RNG = np.random.default_rng(20260519)


# Estilo visual com linguagem cartografica academica.
mpl.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["DejaVu Serif", "Times New Roman", "Times", "serif"],
        "axes.facecolor": "#efefef",
        "figure.facecolor": "#f4f4f4",
        "axes.edgecolor": "#222222",
        "axes.labelcolor": "#111111",
        "text.color": "#111111",
    }
)


KERNEL_CMAP = LinearSegmentedColormap.from_list(
    "kernel_ibge", ["#1a5490", "#4ba3d6", "#a8d5f7", "#f7dc6f", "#f39c12", "#d64545"], N=256
)


GENERAL_COUNTS = {
    "Recife": 15,
    "Garanhuns": 65,
    "Canhotinho": 10,
    "Bom Conselho": 15,
    "Jaboatao dos Guararapes": 5,
}


MOTO_COUNTS = {
    "Recife": 34,
    "Garanhuns": 78,
    "Canhotinho": 9,
    "Bom Conselho": 17,
    "Jaboatao dos Guararapes": 4,
}


# Pontos de referencia aproximados para concentracao espacial dos acidentes.
# Coordenadas em WGS84 (lon, lat), convertidas para UTM antes da simulacao.
ANCHORS_WGS84 = {
    "Recife": [
        {"name": "Centro", "lon": -34.8789, "lat": -8.0617, "weight": 0.48, "sigma": 650},
        {"name": "BR-101", "lon": -34.9320, "lat": -8.0590, "weight": 0.34, "sigma": 850},
        {"name": "Santo Amaro", "lon": -34.8897, "lat": -8.0488, "weight": 0.18, "sigma": 560},
    ],
    "Garanhuns": [
        {"name": "Centro", "lon": -36.4928, "lat": -8.8905, "weight": 0.45, "sigma": 750},
        {"name": "Heliopolis", "lon": -36.4758, "lat": -8.8790, "weight": 0.30, "sigma": 700},
        {"name": "BR-232", "lon": -36.5088, "lat": -8.9020, "weight": 0.25, "sigma": 980},
    ],
    "Canhotinho": [
        {"name": "Regiao Central", "lon": -36.1918, "lat": -8.8834, "weight": 1.0, "sigma": 620},
    ],
    "Bom Conselho": [
        {"name": "Regiao Central", "lon": -36.6798, "lat": -9.1693, "weight": 1.0, "sigma": 690},
    ],
    "Jaboatao dos Guararapes": [
        {
            "name": "Jaboatao Velho",
            "lon": -35.0117,
            "lat": -8.1128,
            "weight": 1.0,
            "sigma": 770,
        },
    ],
}


def normalize_name(value: str) -> str:
    """Normaliza texto para comparacao robusta de nomes de municipios."""
    ascii_text = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
        .lower()
    )
    return " ".join(ascii_text.split())


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_pe_municipalities() -> gpd.GeoDataFrame:
    """
    Baixa municipios via geobr e padroniza schema para uso no pipeline.
    """
    gdf = None

    attempts = [
        {"code_muni": "all", "code_state": "PE", "year": 2020, "simplified": False},
        {"code_muni": "all", "code_state": "PE", "year": 2020},
        {"code_muni": "all", "year": 2020, "simplified": False},
        {"code_muni": "all", "year": 2020},
    ]

    last_error: Exception | None = None
    for kwargs in attempts:
        try:
            gdf = geobr.read_municipality(**kwargs)
            if isinstance(gdf, gpd.GeoDataFrame) and not gdf.empty:
                break
        except Exception as exc:  # pragma: no cover - fallback de compatibilidade
            last_error = exc

    if gdf is None or gdf.empty:
        raise RuntimeError(
            "Nao foi possivel baixar municipios via geobr. "
            f"Ultimo erro: {last_error}"
        )

    columns = {c.lower(): c for c in gdf.columns}
    name_col = None
    for candidate in ("name_muni", "name_municipality", "municipio", "nome"):
        if candidate in columns:
            name_col = columns[candidate]
            break
    if name_col is None:
        raise RuntimeError("Coluna de nome municipal nao encontrada no GeoDataFrame do geobr.")

    if "abbrev_state" in columns:
        gdf = gdf[gdf[columns["abbrev_state"]] == "PE"].copy()
    elif "code_state" in columns:
        gdf = gdf[gdf[columns["code_state"]].astype(str).str.zfill(2) == "26"].copy()

    gdf = gdf.rename(columns={name_col: "municipio"})
    gdf["municipio_norm"] = gdf["municipio"].map(normalize_name)
    gdf = gdf.to_crs(TARGET_CRS)
    return gdf[["municipio", "municipio_norm", "geometry"]].copy()


def choose_scalebar_length(width_m: float) -> float:
    """Seleciona comprimento de escala em metros com valores cartograficos usuais."""
    target = width_m * 0.16
    candidates = np.array([500, 1000, 2000, 5000, 10000, 20000, 50000, 100000])
    return float(candidates[np.argmin(np.abs(candidates - target))])


def add_scale_bar(ax: plt.Axes, location: Tuple[float, float] = (0.05, 0.055)) -> None:
    """Adiciona escala grafica classica com divisoes preto/branco no canto inferior esquerdo."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    width = x1 - x0
    height = y1 - y0
    length = choose_scalebar_length(width)

    sx = x0 + width * location[0]
    sy = y0 + height * location[1]
    
    # Barra principal
    bar_height = height * 0.013
    seg_length = length / 4.0  # 4 segmentos
    
    # Desenha 4 segmentos alternados preto/branco
    colors = ["black", "white", "black", "white"]
    for i, color in enumerate(colors):
        rect_x = sx + i * seg_length
        rect = plt.Rectangle((rect_x, sy), seg_length, bar_height, 
                             facecolor=color, edgecolor="black", linewidth=0.8, zorder=30)
        ax.add_patch(rect)
    
    # Bordas verticais
    ax.plot([sx, sx], [sy - bar_height * 0.4, sy + bar_height * 1.4], 
           color="black", lw=1.2, zorder=30)
    ax.plot([sx + length, sx + length], [sy - bar_height * 0.4, sy + bar_height * 1.4], 
           color="black", lw=1.2, zorder=30)
    
    # Marcas intermediarias
    for i in range(1, 4):
        mark_x = sx + i * seg_length
        ax.plot([mark_x, mark_x], [sy - bar_height * 0.2, sy + bar_height * 1.2], 
               color="black", lw=0.7, zorder=30)
    
    # Rótulos
    km = length / 1000.0
    ax.text(sx, sy + bar_height * 2.0, "0", fontsize=8.5, ha="center", va="bottom", fontweight="bold")
    ax.text(sx + length / 2.0, sy + bar_height * 2.0, f"{km*0.5:.1f}", fontsize=8.5, ha="center", va="bottom", fontweight="bold")
    ax.text(sx + length, sy + bar_height * 2.0, f"{km:.1f} km", fontsize=8.5, ha="center", va="bottom", fontweight="bold")


def add_north_arrow(ax: plt.Axes, location: Tuple[float, float] = (0.92, 0.15)) -> None:
    """Desenha rosa dos ventos tipo IBGE com triangulo preenchido e cruz."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    w = x1 - x0
    h = y1 - y0

    cx = x0 + w * location[0]
    cy = y0 + h * location[1]
    size = min(w, h) * 0.058  # Maior que antes
    
    # Circulo de fundo
    circle = plt.Circle((cx, cy), size * 1.3, facecolor="white", edgecolor="black", linewidth=1.2, zorder=29)
    ax.add_patch(circle)

    # Triangulo norte (preenchido)
    tri_north = Polygon(
        [[cx, cy + size], [cx - size * 0.35, cy - size * 0.32], [cx + size * 0.35, cy - size * 0.32]],
        closed=True,
        facecolor="black",
        edgecolor="black",
        linewidth=0.8,
        zorder=30,
    )
    ax.add_patch(tri_north)
    
    # Triangulo sul (apenas bordas)
    tri_south = Polygon(
        [[cx, cy - size], [cx - size * 0.25, cy + size * 0.28], [cx + size * 0.25, cy + size * 0.28]],
        closed=True,
        facecolor="none",
        edgecolor="black",
        linewidth=0.8,
        zorder=30,
    )
    ax.add_patch(tri_south)
    
    # Linhas cruz
    ax.plot([cx - size * 0.5, cx + size * 0.5], [cy, cy], color="black", lw=0.7, zorder=30)
    ax.plot([cx, cx], [cy - size * 0.5, cy + size * 0.5], color="black", lw=0.7, zorder=30)
    
    # Rótulo N
    ax.text(cx, cy + size * 1.65, "N", ha="center", va="bottom", fontsize=13, fontweight="bold")


def to_target_points(df: pd.DataFrame) -> gpd.GeoDataFrame:
    gdf = gpd.GeoDataFrame(
        df.copy(),
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    )
    return gdf.to_crs(TARGET_CRS)


def _anchor_points_utm(municipio: str) -> List[Tuple[float, float, float, float]]:
    """Retorna lista de ancoras em UTM: x, y, peso, sigma."""
    anchors = ANCHORS_WGS84[municipio]
    anchor_df = pd.DataFrame(anchors)
    gdf = to_target_points(anchor_df.rename(columns={"lon": "lon", "lat": "lat"}))
    out = []
    for row, geom in zip(anchors, gdf.geometry):
        out.append((geom.x, geom.y, float(row["weight"]), float(row["sigma"])))
    return out


def simulate_points_for_municipality(
    municipio: str,
    municipio_geom,
    n_points: int,
    moto: bool = False,
) -> gpd.GeoDataFrame:
    """Simula pontos espaciais realistas proximos as ancoras e dentro do limite municipal."""
    anchors = _anchor_points_utm(municipio)
    weights = np.array([a[2] for a in anchors], dtype=float)
    weights = weights / weights.sum()

    # Motocicleta usa concentracao mais fechada, conforme solicitado.
    sigma_factor = 0.72 if moto else 1.0
    allocations = np.maximum(1, np.round(weights * n_points).astype(int))

    # Ajusta para somar exatamente n_points.
    delta = int(n_points - allocations.sum())
    if delta != 0:
        order = np.argsort(weights)[::-1]
        i = 0
        step = 1 if delta > 0 else -1
        while delta != 0:
            idx = order[i % len(order)]
            if allocations[idx] + step >= 1:
                allocations[idx] += step
                delta -= step
            i += 1

    pts: List[Point] = []
    minx, miny, maxx, maxy = municipio_geom.bounds

    for idx, (x0, y0, _weight, sigma) in enumerate(anchors):
        target = int(allocations[idx])
        sigma_eff = max(220.0, sigma * sigma_factor)

        accepted: List[Point] = []
        attempts = 0
        while len(accepted) < target and attempts < 25:
            remaining = target - len(accepted)
            # Superamostragem para garantir pontos no interior do poligono.
            batch = max(remaining * 4, 24)
            xs = RNG.normal(x0, sigma_eff, size=batch)
            ys = RNG.normal(y0, sigma_eff, size=batch)
            for x, y in zip(xs, ys):
                p = Point(float(x), float(y))
                if municipio_geom.contains(p):
                    accepted.append(p)
                    if len(accepted) == target:
                        break
            attempts += 1

        # Fallback robusto caso algum municipio tenha geometria estreita.
        while len(accepted) < target:
            x = RNG.uniform(minx, maxx)
            y = RNG.uniform(miny, maxy)
            p = Point(float(x), float(y))
            if municipio_geom.contains(p):
                accepted.append(p)

        pts.extend(accepted)

    return gpd.GeoDataFrame(
        {"municipio": [municipio] * len(pts), "tipo": ["moto" if moto else "geral"] * len(pts)},
        geometry=pts,
        crs=TARGET_CRS,
    )


def compute_kde_surface(
    points_gdf: gpd.GeoDataFrame,
    clip_geom,
    cell_size: float,
    bandwidth: float = 0.20,
    blur_sigma: float = 1.2,
    padding_factor: float = 0.07,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Tuple[float, float, float, float]]:
    """
    Calcula KDE em grade raster e mascara fora do limite espacial.
    """
    minx, miny, maxx, maxy = clip_geom.bounds
    dx = maxx - minx
    dy = maxy - miny
    minx -= dx * padding_factor
    maxx += dx * padding_factor
    miny -= dy * padding_factor
    maxy += dy * padding_factor

    nx = max(180, int((maxx - minx) / cell_size))
    ny = max(180, int((maxy - miny) / cell_size))

    xgrid = np.linspace(minx, maxx, nx)
    ygrid = np.linspace(miny, maxy, ny)
    xx, yy = np.meshgrid(xgrid, ygrid)

    coords = np.vstack([points_gdf.geometry.x.values, points_gdf.geometry.y.values])
    if coords.shape[1] < 2:
        raise RuntimeError("Quantidade insuficiente de pontos para KDE.")

    kde = gaussian_kde(coords, bw_method=bandwidth)
    z = kde(np.vstack([xx.ravel(), yy.ravel()])).reshape(xx.shape)
    z = gaussian_filter(z, sigma=blur_sigma)

    # Uso explicito de rasterio para mascara espacial vetorial-raster.
    transform = from_bounds(minx, miny, maxx, maxy, nx, ny)
    valid_mask = geometry_mask([clip_geom], transform=transform, invert=True, out_shape=(ny, nx))
    z = np.where(valid_mask, z, np.nan)

    # Normaliza para 0..1 para manter legenda padronizada.
    zmax = np.nanmax(z)
    if np.isfinite(zmax) and zmax > 0:
        z = z / zmax

    return xx, yy, z, (minx, miny, maxx, maxy)


def _side_panel_table(
    ax_side: plt.Axes,
    title: str,
    rows: Sequence[Tuple[str, int]],
    source_text: str,
    legend_title: str,
) -> None:
    ax_side.axis("off")
    ax_side.set_facecolor("#f2f2f2")

    ax_side.text(
        0.03,
        0.98,
        title,
        va="top",
        ha="left",
        fontsize=12,
        fontweight="bold",
    )

    cell_text = [[name, f"{count}"] for name, count in rows]
    table = ax_side.table(
        cellText=cell_text,
        colLabels=["Municipio", "Notificacoes"],
        cellLoc="left",
        colLoc="left",
        bbox=[0.02, 0.56, 0.96, 0.36],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)

    ax_side.text(0.03, 0.49, legend_title, fontsize=10, fontweight="bold", ha="left")
    ax_side.text(
        0.03,
        0.44,
        "Azul = baixa\nAmarelo = media\nVermelho = alta",
        fontsize=9,
        ha="left",
        va="top",
    )

    ax_side.text(0.03, 0.21, "Sistema de referencia:", fontsize=9, fontweight="bold")
    ax_side.text(0.03, 0.17, "SIRGAS 2000 / UTM 25S", fontsize=9)

    ax_side.text(0.03, 0.11, "Fonte:", fontsize=9, fontweight="bold")
    ax_side.text(
        0.03,
        0.06,
        source_text,
        fontsize=8.5,
        ha="left",
        va="bottom",
        wrap=True,
    )


def draw_state_kernel_map(pe_gdf: gpd.GeoDataFrame, muni_points: Dict[str, gpd.GeoDataFrame]) -> None:
    target_names_norm = {normalize_name(k) for k in GENERAL_COUNTS.keys()}
    selected = pe_gdf[pe_gdf["municipio_norm"].isin(target_names_norm)].copy()

    if selected.empty:
        raise RuntimeError("Nao foi possivel localizar os municipios-alvo no limite de Pernambuco.")

    all_points = pd.concat([gdf for gdf in muni_points.values()], ignore_index=True)
    all_points_gdf = gpd.GeoDataFrame(all_points, geometry="geometry", crs=TARGET_CRS)

    pe_union = pe_gdf.unary_union
    xx, yy, z, extent = compute_kde_surface(
        points_gdf=all_points_gdf,
        clip_geom=pe_union,
        cell_size=1400,
        bandwidth=0.16,
        blur_sigma=1.3,
        padding_factor=0.04,
    )

    fig = plt.figure(figsize=(15.8, 10.2), dpi=130)
    gs = fig.add_gridspec(1, 2, width_ratios=[5.3, 1.75], wspace=0.025)
    ax_map = fig.add_subplot(gs[0, 0])
    ax_side = fig.add_subplot(gs[0, 1])

    ax_map.set_facecolor("#f0f0f0")
    pe_gdf.boundary.plot(ax=ax_map, color="#333333", linewidth=0.45, alpha=0.72, zorder=10)
    selected.boundary.plot(ax=ax_map, color="#000000", linewidth=1.35, alpha=0.98, zorder=12)

    img = ax_map.imshow(
        z,
        extent=[extent[0], extent[2], extent[1], extent[3]],
        origin="lower",
        cmap=KERNEL_CMAP,
        interpolation="bicubic",
        alpha=0.74,
        zorder=8,
    )

    # Contornos suaves para dar acabamento cientifico as manchas.
    levels = [0.15, 0.30, 0.45, 0.60, 0.75, 0.90]
    ax_map.contour(xx, yy, z, levels=levels, colors="#555555", linewidths=0.38, alpha=0.32, zorder=14)

    for _, row in selected.iterrows():
        rep = row.geometry.representative_point()
        label = row["municipio"]
        ax_map.text(rep.x, rep.y, label, fontsize=8.3, ha="center", va="center", zorder=20)

    minx, miny, maxx, maxy = pe_gdf.total_bounds
    padx = (maxx - minx) * 0.06
    pady = (maxy - miny) * 0.05
    ax_map.set_xlim(minx - padx, maxx + padx)
    ax_map.set_ylim(miny - pady, maxy + pady)

    add_scale_bar(ax_map)
    add_north_arrow(ax_map)

    ax_map.set_title(
        "Estimativa de Densidade Kernel de Acidentes de Trânsito em Pernambuco",
        fontsize=22,
        fontweight="bold",
        pad=16,
        fontfamily="serif",
    )
    ax_map.set_aspect("equal")
    ax_map.set_xticks([])
    ax_map.set_yticks([])
    
    # Adiciona borda ao mapa
    for spine in ax_map.spines.values():
        spine.set_edgecolor("#333333")
        spine.set_linewidth(2.0)
        spine.set_visible(True)

    cax = ax_side.inset_axes([0.08, 0.35, 0.18, 0.16])
    cb = plt.colorbar(img, cax=cax)
    cb.ax.tick_params(labelsize=8)
    cb.set_label("Intensidade KDE", fontsize=9)

    rows = [(name, GENERAL_COUNTS[name]) for name in GENERAL_COUNTS]
    _side_panel_table(
        ax_side,
        title="Tabela de Notificações",
        rows=rows,
        source_text="Dados simulados de acidentes de trânsito, Pernambuco.",
        legend_title="Estimativa de Densidade",
    )

    save_figure(fig, "kernel_pernambuco_geral")


def _municipal_counts_rows(name: str, total: int) -> List[Tuple[str, int]]:
    return [(name, total)]


def draw_single_municipality_map(
    muni_row: pd.Series,
    points_gdf: gpd.GeoDataFrame,
    output_name: str,
    title: str,
    legend_title: str,
    include_osm_roads: bool,
) -> None:
    geom = muni_row.geometry

    xx, yy, z, extent = compute_kde_surface(
        points_gdf=points_gdf,
        clip_geom=geom,
        cell_size=120,
        bandwidth=0.17,
        blur_sigma=1.5,
        padding_factor=0.07,
    )

    fig = plt.figure(figsize=(13.7, 9.8), dpi=130)
    gs = fig.add_gridspec(1, 2, width_ratios=[4.9, 1.65], wspace=0.03)
    ax_map = fig.add_subplot(gs[0, 0])
    ax_side = fig.add_subplot(gs[0, 1])
    ax_map.set_facecolor("#f2f2f2")

    if include_osm_roads:
        # Camada OSM como referencia de vias locais, reamostrada para o CRS cartografico final.
        minx, miny, maxx, maxy = geom.bounds
        padx = (maxx - minx) * 0.11
        pady = (maxy - miny) * 0.12
        ax_map.set_xlim(minx - padx, maxx + padx)
        ax_map.set_ylim(miny - pady, maxy + pady)
        try:
            cx.add_basemap(
                ax_map,
                source=cx.providers.OpenStreetMap.Mapnik,
                alpha=0.22,
                crs=TARGET_CRS,
                attribution=False,
            )
        except Exception as exc:
            print(f"Aviso: falha ao carregar camada OSM para {muni_row['municipio']}: {exc}")

    ax_map.imshow(
        z,
        extent=[extent[0], extent[2], extent[1], extent[3]],
        origin="lower",
        cmap=KERNEL_CMAP,
        interpolation="bicubic",
        alpha=0.82,
        zorder=8,
    )
    ax_map.contour(xx, yy, z, levels=[0.15, 0.30, 0.45, 0.60, 0.75, 0.90], colors="#555555", linewidths=0.40, alpha=0.30)

    gpd.GeoSeries([geom], crs=TARGET_CRS).boundary.plot(ax=ax_map, color="#000000", linewidth=1.5, zorder=15)
    points_gdf.plot(ax=ax_map, markersize=7, color="#1a1a1a", alpha=0.28, zorder=16)

    minx, miny, maxx, maxy = geom.bounds
    padx = (maxx - minx) * 0.11
    pady = (maxy - miny) * 0.12
    ax_map.set_xlim(minx - padx, maxx + padx)
    ax_map.set_ylim(miny - pady, maxy + pady)
    ax_map.set_aspect("equal")
    ax_map.set_xticks([])
    ax_map.set_yticks([])

    add_scale_bar(ax_map)
    add_north_arrow(ax_map)

    ax_map.set_title(title, fontsize=19, fontweight="bold", pad=13, fontfamily="serif")
    
    # Adiciona borda ao mapa municipal
    for spine in ax_map.spines.values():
        spine.set_edgecolor("#333333")
        spine.set_linewidth(1.8)
        spine.set_visible(True)

    rows = _municipal_counts_rows(muni_row["municipio"], len(points_gdf))
    _side_panel_table(
        ax_side=ax_side,
        title="Tabela de Notificações",
        rows=rows,
        source_text="Dados simulados de acidentes de trânsito, Pernambuco.",
        legend_title=legend_title,
    )

    save_figure(fig, output_name)


def save_figure(fig: plt.Figure, name_without_ext: str) -> None:
    png_path = OUTPUT_DIR / f"{name_without_ext}.png"
    pdf_path = OUTPUT_DIR / f"{name_without_ext}.pdf"
    fig.savefig(png_path, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(pdf_path, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def municipality_row(pe_gdf: gpd.GeoDataFrame, municipio_name: str) -> pd.Series:
    target = normalize_name(municipio_name)
    rows = pe_gdf[pe_gdf["municipio_norm"] == target]
    if rows.empty:
        raise RuntimeError(f"Municipio nao encontrado no geobr: {municipio_name}")
    return rows.iloc[0]


def build_general_points(pe_gdf: gpd.GeoDataFrame) -> Dict[str, gpd.GeoDataFrame]:
    points_by_muni: Dict[str, gpd.GeoDataFrame] = {}
    for name, count in GENERAL_COUNTS.items():
        row = municipality_row(pe_gdf, name)
        gdf = simulate_points_for_municipality(
            municipio=name,
            municipio_geom=row.geometry,
            n_points=count,
            moto=False,
        )
        points_by_muni[name] = gdf
    return points_by_muni


def build_moto_points(pe_gdf: gpd.GeoDataFrame) -> Dict[str, gpd.GeoDataFrame]:
    points_by_muni: Dict[str, gpd.GeoDataFrame] = {}
    for name, count in MOTO_COUNTS.items():
        row = municipality_row(pe_gdf, name)
        gdf = simulate_points_for_municipality(
            municipio=name,
            municipio_geom=row.geometry,
            n_points=count,
            moto=True,
        )
        points_by_muni[name] = gdf
    return points_by_muni


def generate_map_set_2(pe_gdf: gpd.GeoDataFrame, general_points: Dict[str, gpd.GeoDataFrame]) -> None:
    mapping = [
        (
            "Recife",
            "recife_kernel",
            "Recife - Estimativa Kernel de Acidentes",
            "Estimativa de Densidade",
        ),
        (
            "Garanhuns",
            "garanhuns_kernel",
            "Garanhuns - Estimativa Kernel de Acidentes",
            "Estimativa de Densidade",
        ),
        (
            "Canhotinho",
            "canhotinho_kernel",
            "Canhotinho - Estimativa Kernel de Acidentes",
            "Estimativa de Densidade",
        ),
        (
            "Bom Conselho",
            "bom_conselho_kernel",
            "Bom Conselho - Estimativa Kernel de Acidentes",
            "Estimativa de Densidade",
        ),
        (
            "Jaboatao dos Guararapes",
            "jaboatao_kernel",
            "Jaboatao dos Guararapes - Estimativa Kernel de Acidentes",
            "Estimativa de Densidade",
        ),
    ]

    for muni_name, output_name, title, legend_title in mapping:
        row = municipality_row(pe_gdf, muni_name)
        draw_single_municipality_map(
            muni_row=row,
            points_gdf=general_points[muni_name],
            output_name=output_name,
            title=title,
            legend_title=legend_title,
            include_osm_roads=True,
        )


def generate_map_set_3(pe_gdf: gpd.GeoDataFrame, moto_points: Dict[str, gpd.GeoDataFrame]) -> None:
    mapping = [
        ("Recife", "recife_moto_kernel", "Recife - Densidade de Acidentes Motociclisticos"),
        (
            "Garanhuns",
            "garanhuns_moto_kernel",
            "Garanhuns - Densidade de Acidentes Motociclisticos",
        ),
        (
            "Canhotinho",
            "canhotinho_moto_kernel",
            "Canhotinho - Densidade de Acidentes Motociclisticos",
        ),
        (
            "Bom Conselho",
            "bom_conselho_moto_kernel",
            "Bom Conselho - Densidade de Acidentes Motociclisticos",
        ),
        (
            "Jaboatao dos Guararapes",
            "jaboatao_moto_kernel",
            "Jaboatao dos Guararapes - Densidade de Acidentes Motociclisticos",
        ),
    ]

    for muni_name, output_name, title in mapping:
        row = municipality_row(pe_gdf, muni_name)
        draw_single_municipality_map(
            muni_row=row,
            points_gdf=moto_points[muni_name],
            output_name=output_name,
            title=title,
            legend_title="Densidade de acidentes motociclisticos",
            include_osm_roads=False,
        )


def main() -> None:
    ensure_output_dir()
    pe_gdf = read_pe_municipalities()

    general_points = build_general_points(pe_gdf)
    draw_state_kernel_map(pe_gdf, general_points)
    generate_map_set_2(pe_gdf, general_points)

    moto_points = build_moto_points(pe_gdf)
    generate_map_set_3(pe_gdf, moto_points)

    print("Mapas concluidos com sucesso.")
    print(f"Arquivos gerados em: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
