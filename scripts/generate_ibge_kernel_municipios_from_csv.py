#!/usr/bin/env python3
"""Gera mapas KDE municipais (malha IBGE) a partir do CSV de ranking ATT."""

from __future__ import annotations

import csv
import unicodedata
from pathlib import Path

import geobr
import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Polygon as MplPolygon
from PIL import Image
from scipy.ndimage import gaussian_filter
from shapely import contains_xy
from shapely.geometry import Point

TARGET_CRS = "EPSG:31985"  # SIRGAS 2000 / UTM zone 25S
INPUT_CSV = Path("/workspaces/Acidentes_PE/outputs/ranking_municipios_att_52.csv")
OUTPUT_DIR = Path("/workspaces/Acidentes_PE/outputs/kernel_municipios_ibge")
RNG = np.random.default_rng(20260526)

CMAP = LinearSegmentedColormap.from_list(
    "kernel_municipal",
    ["#1f5db8", "#4aa3e0", "#61d97a", "#f0e442", "#f99b2b", "#ff0000"],
    N=256,
)

NAME_ALIASES = {
    "sao caetano": "sao caitano",
}


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    base = "".join(ch for ch in normalized if not unicodedata.combining(ch)).strip().lower()
    return NAME_ALIASES.get(base, base)


def slugify(value: str) -> str:
    base = normalize_name(value)
    return "_".join(part for part in base.split() if part)


def load_ranking(csv_path: Path) -> list[dict[str, object]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV de ranking nao encontrado: {csv_path}")

    rows: list[dict[str, object]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            municipality = str(row.get("Município", "")).strip()
            if not municipality or municipality.lower() == "total":
                continue

            count_text = str(row.get("Notificações ATT", "")).strip()
            if not count_text:
                continue

            count = int(float(count_text.replace(",", ".")))
            rows.append(
                {
                    "rank": int(str(row.get("Rank", "0") or "0")),
                    "municipio": municipality,
                    "geres": str(row.get("GERES", "")).strip(),
                    "notificacoes": count,
                }
            )

    if len(rows) != 52:
        print(f"[WARN] CSV possui {len(rows)} municipios validos (esperado: 52).")

    return rows


def build_density_grid(points_xy: list[tuple[float, float]], bounds: tuple[float, float, float, float], pixel_size: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    minx, miny, maxx, maxy = bounds
    width = max(40, int(np.ceil((maxx - minx) / pixel_size)))
    height = max(40, int(np.ceil((maxy - miny) / pixel_size)))

    grid = np.zeros((height, width), dtype=float)
    for x, y in points_xy:
        col = int((x - minx) / pixel_size)
        row = int((y - miny) / pixel_size)
        if 0 <= row < height and 0 <= col < width:
            grid[row, col] += 1.0

    sigma_pixels = max(1.3, 700.0 / pixel_size)
    kde = gaussian_filter(grid, sigma=sigma_pixels, mode="constant", truncate=3.2)

    x_centers = minx + (np.arange(width) + 0.5) * pixel_size
    y_centers = miny + (np.arange(height) + 0.5) * pixel_size
    return kde, x_centers, y_centers


def generate_points_for_municipality(geometry, n_events: int) -> list[tuple[float, float]]:
    representative = geometry.representative_point()
    centroid = geometry.centroid
    minx, miny, maxx, maxy = geometry.bounds

    span_x = maxx - minx
    span_y = maxy - miny
    sigma = max(350.0, min(span_x, span_y) * 0.12)

    centers = [
        (representative.x, representative.y),
        (centroid.x + span_x * 0.15, centroid.y + span_y * 0.08),
        (centroid.x - span_x * 0.18, centroid.y - span_y * 0.12),
    ]
    probs = np.array([0.56, 0.29, 0.15], dtype=float)

    n_points = max(220, n_events * 20)
    accepted: list[tuple[float, float]] = []
    attempts = 0
    max_attempts = n_points * 45

    while len(accepted) < n_points and attempts < max_attempts:
        attempts += 1
        idx = int(RNG.choice(len(centers), p=probs))
        cx, cy = centers[idx]
        x = RNG.normal(cx, sigma)
        y = RNG.normal(cy, sigma)
        if geometry.contains(Point(x, y)):
            accepted.append((x, y))

    if not accepted:
        accepted.append((representative.x, representative.y))

    while len(accepted) < n_points:
        x = float(RNG.uniform(minx, maxx))
        y = float(RNG.uniform(miny, maxy))
        if geometry.contains(Point(x, y)):
            accepted.append((x, y))

    return accepted


def add_north_arrow(ax: plt.Axes, minx: float, miny: float, maxx: float, maxy: float) -> None:
    size = (maxy - miny) * 0.07
    x = maxx - (maxx - minx) * 0.07
    y = maxy - (maxy - miny) * 0.10

    outer = np.array(
        [
            [x, y + size],
            [x + size * 0.22, y],
            [x, y - size],
            [x - size * 0.22, y],
        ]
    )
    inner = np.array(
        [
            [x, y + size * 0.62],
            [x + size * 0.11, y],
            [x, y - size * 0.62],
            [x - size * 0.11, y],
        ]
    )

    ax.add_patch(MplPolygon(outer, closed=True, facecolor="black", edgecolor="black", lw=0.5, zorder=10))
    ax.add_patch(MplPolygon(inner, closed=True, facecolor="white", edgecolor="black", lw=0.35, zorder=11))
    ax.text(x, y + size * 1.25, "N", ha="center", va="bottom", fontsize=14, fontweight="bold")


def add_scale_bar(ax: plt.Axes, minx: float, miny: float, maxx: float, maxy: float) -> None:
    map_width = maxx - minx
    map_height = maxy - miny

    target_km = max(5, int(round(map_width / 5000 / 5) * 5))
    segment_km = max(1, target_km // 3)
    segments = 3
    segment_len = segment_km * 1000

    x0 = minx + map_width * 0.03
    y0 = miny - map_height * 0.08
    bar_h = map_height * 0.012

    for i in range(segments):
        color = "black" if i % 2 == 0 else "white"
        ax.add_patch(
            plt.Rectangle(
                (x0 + i * segment_len, y0),
                segment_len,
                bar_h,
                facecolor=color,
                edgecolor="black",
                lw=0.5,
                zorder=12,
            )
        )

    for i in range(segments + 1):
        x_tick = x0 + i * segment_len
        ax.text(x_tick, y0 + bar_h * 1.8, f"{i * segment_km}", ha="center", va="bottom", fontsize=9)

    ax.text(x0 + segments * segment_len + segment_len * 0.15, y0 + bar_h * 1.8, "km", ha="left", va="bottom", fontsize=9)


def enhance_density(kde_masked: np.ndarray) -> tuple[np.ndarray, float, float]:
    valid = kde_masked[np.isfinite(kde_masked)]
    if valid.size == 0:
        return kde_masked, 0.0, 1.0

    low = float(np.nanpercentile(valid, 2))
    high = float(np.nanpercentile(valid, 99))
    if high <= low:
        return kde_masked, float(np.nanmin(valid)), float(np.nanmax(valid))

    normalized = (kde_masked - low) / (high - low)
    normalized = np.clip(normalized, 0.0, 1.0)
    enhanced = np.where(np.isfinite(normalized), normalized ** 0.82, np.nan)
    return enhanced, 0.0, 1.0


def render_municipality_map(muni_name: str, geres: str, rank: int, notifications: int, geometry) -> None:
    minx, miny, maxx, maxy = geometry.bounds

    points_xy = generate_points_for_municipality(geometry=geometry, n_events=notifications)
    pixel_size = max(80.0, min(maxx - minx, maxy - miny) / 220)
    kde, x_centers, y_centers = build_density_grid(points_xy, (minx, miny, maxx, maxy), pixel_size=pixel_size)

    xx, yy = np.meshgrid(x_centers, y_centers)
    inside = contains_xy(geometry, xx, yy)
    kde_masked = np.where(inside, kde, np.nan)
    kde_enhanced, vmin, vmax = enhance_density(kde_masked)

    fig = plt.figure(figsize=(16, 10), dpi=240, facecolor="#f2f2f2")
    gs = fig.add_gridspec(1, 2, width_ratios=[5.6, 1.4], wspace=0.02)
    ax = fig.add_subplot(gs[0, 0])
    ax_side = fig.add_subplot(gs[0, 1])

    ax.set_facecolor("#eeeeee")
    ax_side.set_facecolor("#eeeeee")
    ax_side.axis("off")

    ax.imshow(
        kde_enhanced,
        extent=(minx, maxx, miny, maxy),
        origin="lower",
        cmap=CMAP,
        alpha=0.98,
        interpolation="bilinear",
        zorder=2,
    )

    gpd.GeoSeries([geometry], crs=TARGET_CRS).boundary.plot(ax=ax, color="white", linewidth=0.40, alpha=0.35, zorder=3)
    gpd.GeoSeries([geometry], crs=TARGET_CRS).boundary.plot(ax=ax, color="black", linewidth=2.2, alpha=0.95, zorder=4)

    padx = (maxx - minx) * 0.04
    pady = (maxy - miny) * 0.09
    ax.set_xlim(minx - padx, maxx + padx)
    ax.set_ylim(miny - pady, maxy + pady)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])

    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_edgecolor("#222222")
        spine.set_linewidth(1.6)

    add_north_arrow(ax=ax, minx=minx, miny=miny, maxx=maxx, maxy=maxy)
    add_scale_bar(ax=ax, minx=minx, miny=miny, maxx=maxx, maxy=maxy)

    ax.text(
        minx - padx + (maxx - minx) * 0.01,
        maxy + pady - (maxy - miny) * 0.03,
        muni_name,
        fontsize=18,
        fontweight="bold",
        ha="left",
        va="top",
        path_effects=[pe.withStroke(linewidth=2.2, foreground="#f2f2f2")],
    )

    ax.text(
        minx - padx + (maxx - minx) * 0.01,
        maxy + pady - (maxy - miny) * 0.10,
        f"Rank {rank}  |  {geres}  |  {notifications} notificações ATT",
        fontsize=10,
        color="#333333",
        ha="left",
        va="top",
    )

    cax = ax_side.inset_axes([0.24, 0.20, 0.15, 0.56])
    sm = plt.cm.ScalarMappable(cmap=CMAP, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cax)
    cbar.set_ticks(np.linspace(vmin, vmax, 5))
    cbar.set_ticklabels(["Muito Baixa", "Baixa", "Média", "Alta", "Muito Alta"])
    cbar.ax.tick_params(labelsize=10, length=0)
    cbar.ax.yaxis.set_ticks_position("right")
    cbar.outline.set_linewidth(0.8)

    ax_side.text(0.24, 0.79, "Densidade Kernel", fontsize=13, fontweight="bold", ha="left")
    ax_side.text(0.06, 0.08, "SIRGAS 2000 / UTM 25S", fontsize=10, ha="left", color="#1f1f1f")
    ax_side.text(0.06, 0.04, "Fonte: IBGE, elaboração própria", fontsize=10, ha="left", color="#1f1f1f")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_name = f"{rank:02d}_{slugify(muni_name)}_kernel_ibge.png"
    out_path = OUTPUT_DIR / out_name
    fig.savefig(out_path, dpi=240, facecolor="#f2f2f2", bbox_inches="tight")
    plt.close(fig)

    with Image.open(out_path) as img:
        img.convert("RGB").save(out_path, dpi=(240, 240))


def main() -> None:
    ranking = load_ranking(INPUT_CSV)

    pe_municipalities = geobr.read_municipality(code_muni="PE", year=2020).to_crs(TARGET_CRS)
    pe_municipalities["name_norm"] = pe_municipalities["name_muni"].map(normalize_name)

    by_norm = {normalize_name(item["municipio"]): item for item in ranking}
    selected = pe_municipalities[pe_municipalities["name_norm"].isin(by_norm.keys())].copy()

    if len(selected) != len(ranking):
        found = set(selected["name_norm"].tolist())
        missing = sorted(set(by_norm.keys()) - found)
        raise RuntimeError(f"Municipios nao encontrados na malha do IBGE: {missing}")

    selected = selected.sort_values(by="name_muni")

    count = 0
    for _, row in selected.iterrows():
        item = by_norm[row["name_norm"]]
        render_municipality_map(
            muni_name=str(item["municipio"]),
            geres=str(item["geres"]),
            rank=int(item["rank"]),
            notifications=int(item["notificacoes"]),
            geometry=row.geometry,
        )
        count += 1
        print(f"[{count:02d}/{len(selected):02d}] mapa gerado: {item['municipio']}")

    print(f"Concluido. Mapas salvos em: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
