#!/usr/bin/env python3
"""Gera mapa temático KDE de acidentes para Pernambuco no padrão cartográfico institucional."""

from __future__ import annotations

import csv
import unicodedata
from pathlib import Path

import geobr
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Polygon as MplPolygon
import matplotlib.patheffects as pe
from PIL import Image
from scipy.ndimage import gaussian_filter
from shapely import contains_xy


# Configuração solicitada
TARGET_CRS = "EPSG:31985"  # SIRGAS 2000 / UTM zone 25S
PIXEL_SIZE = 1000  # metros
INFLUENCE_RADIUS_METERS = 68_000
GAUSSIAN_SIGMA_METERS = INFLUENCE_RADIUS_METERS / 2.8
OUTPUT_PATH = Path("/workspaces/Acidentes_PE/outputs/kernel_pernambuco_ibge.png")
OUTPUT_PATH_CLIPPED = Path("/workspaces/Acidentes_PE/outputs/kernel_pernambuco_ibge_municipios_recortados.png")
CSV_NOTIFICATIONS_PATH = Path("/workspaces/Acidentes_PE/outputs/ranking_municipios_att_52.csv")

NAME_ALIASES = {
    "sao caetano": "sao caitano",
}


def normalize_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    base = "".join(char for char in normalized if not unicodedata.combining(char)).strip().lower()
    return NAME_ALIASES.get(base, base)


def load_notifications_from_csv(csv_path: Path) -> dict[str, int]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV de ranking nao encontrado: {csv_path}")

    notifications: dict[str, int] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            municipality = str(row.get("Município", "")).strip()
            if not municipality or municipality.lower() == "total":
                continue

            count_text = str(row.get("Notificações ATT", "")).strip()
            if not count_text:
                continue

            try:
                notifications[municipality] = int(float(count_text.replace(",", ".")))
            except ValueError as exc:
                raise ValueError(
                    f"Valor invalido de notificacoes para {municipality}: {count_text}"
                ) from exc

    if not notifications:
        raise RuntimeError(f"Nenhuma notificacao valida encontrada em {csv_path}")

    return notifications


def build_density_grid(point_xy_weight: list[tuple[float, float, float]], bounds: tuple[float, float, float, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    minx, miny, maxx, maxy = bounds
    width = int(np.ceil((maxx - minx) / PIXEL_SIZE))
    height = int(np.ceil((maxy - miny) / PIXEL_SIZE))

    grid = np.zeros((height, width), dtype=float)

    for x, y, weight in point_xy_weight:
        col = int((x - minx) / PIXEL_SIZE)
        row = int((y - miny) / PIXEL_SIZE)
        if 0 <= row < height and 0 <= col < width:
            grid[row, col] += weight

    sigma_pixels = GAUSSIAN_SIGMA_METERS / PIXEL_SIZE
    kde = gaussian_filter(grid, sigma=sigma_pixels, mode="constant", truncate=3.0)

    x_centers = minx + (np.arange(width) + 0.5) * PIXEL_SIZE
    y_centers = miny + (np.arange(height) + 0.5) * PIXEL_SIZE
    return kde, x_centers, y_centers


def add_north_arrow(ax: plt.Axes, x: float, y: float, size: float) -> None:
    # Rosa dos ventos discreta em estilo institucional
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
            [x, y + size * 0.65],
            [x + size * 0.12, y],
            [x, y - size * 0.65],
            [x - size * 0.12, y],
        ]
    )
    ax.add_patch(MplPolygon(outer, closed=True, facecolor="black", edgecolor="black", lw=0.4, zorder=6))
    ax.add_patch(MplPolygon(inner, closed=True, facecolor="white", edgecolor="black", lw=0.3, zorder=7))
    ax.text(x, y + size * 1.2, "N", ha="center", va="bottom", fontsize=7.5, fontweight="bold")


def add_scale_bar(ax: plt.Axes, bounds: tuple[float, float, float, float]) -> None:
    minx, miny, maxx, maxy = bounds
    map_width = maxx - minx
    map_height = maxy - miny

    segment_km = 50
    segments = 4
    segment_len = segment_km * 1000
    total_len = segments * segment_len

    x0 = minx + map_width * 0.055
    # Escala em faixa branca abaixo do estado, sem sobrepor o poligono.
    y0 = miny - map_height * 0.11
    bar_h = map_height * 0.006

    for i in range(segments):
        color = "black" if i % 2 == 0 else "white"
        ax.add_patch(
            plt.Rectangle(
                (x0 + i * segment_len, y0),
                segment_len,
                bar_h,
                facecolor=color,
                edgecolor="black",
                lw=0.4,
                zorder=10,
            )
        )

    for i in range(segments + 1):
        x_tick = x0 + i * segment_len
        ax.plot([x_tick, x_tick], [y0, y0 + bar_h * 1.5], color="black", lw=0.4, zorder=10)
        ax.text(
            x_tick,
            y0 + bar_h * 2.3,
            f"{i * segment_km}",
            ha="center",
            va="bottom",
            fontsize=6,
        )

    ax.text(x0 + total_len + segment_len * 0.18, y0 + bar_h * 2.3, "km", fontsize=6, va="bottom")


def enhance_kde_contrast(density: np.ndarray) -> tuple[np.ndarray, float, float]:
    valid = density[np.isfinite(density)]
    if valid.size == 0:
        return density, 0.0, 1.0

    low = float(np.nanpercentile(valid, 2))
    high = float(np.nanpercentile(valid, 99.2))
    if high <= low:
        return density, float(np.nanmin(valid)), float(np.nanmax(valid))

    normalized = (density - low) / (high - low)
    normalized = np.clip(normalized, 0.0, 1.0)
    # Realça hotspots sem quebrar continuidade da superfície.
    enhanced = np.where(np.isfinite(normalized), normalized ** 0.85, np.nan)
    return enhanced, 0.0, 1.0


def main() -> None:
    notifications = load_notifications_from_csv(CSV_NOTIFICATIONS_PATH)

    # Base oficial IBGE via geobr
    pe_state = geobr.read_state(code_state="PE", year=2020).to_crs(TARGET_CRS)
    pe_municipalities = geobr.read_municipality(code_muni="PE", year=2020).to_crs(TARGET_CRS)

    pe_geometry = pe_state.geometry.iloc[0]
    if pe_geometry.geom_type == "MultiPolygon":
        mainland_geometry = max(pe_geometry.geoms, key=lambda poly: poly.area)
    else:
        mainland_geometry = pe_geometry

    # Seleciona municípios de interesse (por nome normalizado)
    target_by_norm = {normalize_name(name): value for name, value in notifications.items()}
    pe_municipalities["name_norm"] = pe_municipalities["name_muni"].map(normalize_name)
    selected = pe_municipalities[pe_municipalities["name_norm"].isin(target_by_norm.keys())].copy()

    if len(selected) != len(notifications):
        found = set(selected["name_norm"].tolist())
        missing = sorted(set(target_by_norm.keys()) - found)
        raise RuntimeError(f"Municipios nao encontrados na base IBGE: {missing}")

    selected["notificacoes"] = selected["name_norm"].map(target_by_norm)
    selected["label_name"] = selected["name_muni"]

    # Pontos representativos dentro do municipio para alimentar KDE
    points = selected.representative_point()
    xyw = [(pt.x, pt.y, float(w)) for pt, w in zip(points, selected["notificacoes"], strict=True)]

    # KDE em grade de 1 km com suavização gaussiana equivalente a raio de influencia de 60 km
    bounds = mainland_geometry.bounds
    kde, x_centers, y_centers = build_density_grid(xyw, tuple(bounds))

    xx, yy = np.meshgrid(x_centers, y_centers)
    inside_mask = contains_xy(mainland_geometry, xx, yy)
    kde_masked = np.where(inside_mask, kde, np.nan)

    # Colormap contínuo solicitado: azul -> verde -> amarelo -> vermelho.
    ibge_cmap = LinearSegmentedColormap.from_list(
        "ibge_kernel",
        ["#08306B", "#2171B5", "#2CA25F", "#FEE08B", "#F46D43", "#D73027"],
        N=256,
    )

    kde_enhanced, vmin, vmax = enhance_kde_contrast(kde_masked)
    selected_union = selected.geometry.union_all()

    def render_layout(
        output_path: Path,
        density: np.ndarray,
        title: str,
        title_fontsize: float,
        municipality_layer,
        municipality_linewidth: float,
        clip_to_marked: bool,
    ) -> None:
        # Layout horizontal com faixa lateral dedicada para legenda e metadados.
        fig = plt.figure(figsize=(13.2, 8.0), dpi=300, facecolor="#f7f7f7")
        gs = fig.add_gridspec(1, 2, width_ratios=[4.9, 1.45], wspace=0.03)
        ax = fig.add_subplot(gs[0, 0])
        ax_side = fig.add_subplot(gs[0, 1])
        ax.set_facecolor("#f8f8f8")
        ax_side.set_facecolor("#f1f1f1")
        ax_side.axis("off")

        minx, miny, maxx, maxy = bounds
        density_to_plot = density
        if clip_to_marked:
            clip_mask = contains_xy(selected_union, xx, yy)
            density_to_plot = np.where(clip_mask, density, np.nan)

        density_to_plot, _, _ = enhance_kde_contrast(density_to_plot)

        ax.imshow(
            density_to_plot,
            extent=(minx, maxx, miny, maxy),
            origin="lower",
            cmap=ibge_cmap,
            alpha=0.97,
            interpolation="bilinear",
            zorder=1,
        )

        municipality_layer.boundary.plot(ax=ax, color="#c8c8c8", linewidth=municipality_linewidth, zorder=3)
        pe_state.boundary.plot(ax=ax, color="black", linewidth=0.85, zorder=4)

        # Rotulos discretos dos municipios
        label_offsets = {
            "Recife": (7_000, 4_000),
            "Jaboatão Dos Guararapes": (8_000, -8_000),
            "Garanhuns": (6_000, 6_000),
            "Canhotinho": (15_000, 12_000),
            "Bom Conselho": (5_000, -14_000),
        }

        for _, row in selected.iterrows():
            p = row.geometry.representative_point()
            name = row["label_name"]
            dx, dy = label_offsets.get(name, (6_000, 4_000))
            ax.text(
                p.x + dx,
                p.y + dy,
                name,
                fontsize=6.4,
                color="#1a1a1a",
                zorder=8,
                path_effects=[pe.withStroke(linewidth=1.5, foreground="white")],
            )

        ax.set_xlim(minx, maxx)
        ax.set_ylim(miny - (maxy - miny) * 0.14, maxy)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_frame_on(False)

        # Barra de cores e elementos cartograficos na faixa lateral.
        cax = ax_side.inset_axes([0.50, 0.30, 0.20, 0.48])
        sm = plt.cm.ScalarMappable(cmap=ibge_cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
        sm.set_array([])
        cbar = fig.colorbar(sm, cax=cax)
        class_vals = np.linspace(vmin, vmax, 5)
        cbar.set_ticks(class_vals)
        cbar.set_ticklabels(["Muito Baixa", "Baixa", "Média", "Alta", "Muito Alta"])
        cbar.ax.tick_params(labelsize=7)
        cbar.outline.set_linewidth(0.5)

        # Elementos cartográficos
        fig.text(0.045, 0.95, title, fontsize=title_fontsize, fontweight="bold")
        ax_side.text(0.50, 0.82, "Densidade Kernel", fontsize=9.5, fontweight="bold", ha="left")
        ax_side.text(0.50, 0.20, "SIRGAS 2000 / UTM 25S", fontsize=7.2, ha="left")
        ax_side.text(0.50, 0.15, "Fonte: IBGE, elaboração própria", fontsize=7.0, ha="left")

        add_north_arrow(ax, x=maxx - (maxx - minx) * 0.10, y=miny + (maxy - miny) * 0.15, size=(maxy - miny) * 0.05)
        add_scale_bar(ax, tuple(bounds))

        # Inset discreto para indicar o arquipelado fora do quadro principal
        inset = ax_side.inset_axes([0.80, 0.78, 0.18, 0.18])
        pe_state.boundary.plot(ax=inset, color="black", linewidth=0.35)
        inset.set_facecolor("#f1f1f1")
        inset.set_xticks([])
        inset.set_yticks([])
        inset.set_frame_on(False)
        inset.set_title("PE", fontsize=5.2, pad=1.5)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=300, facecolor="white", transparent=False)
        plt.close(fig)

        # Exporta em RGB para evitar camada alpha/transparencia no arquivo final
        with Image.open(output_path) as img:
            img.convert("RGB").save(output_path, dpi=(300, 300))

    render_layout(
        output_path=OUTPUT_PATH,
        density=kde_masked,
        title="Mapa de Densidade Kernel de Acidentes em Pernambuco",
        title_fontsize=10.5,
        municipality_layer=pe_municipalities,
        municipality_linewidth=0.15,
        clip_to_marked=False,
    )

    render_layout(
        output_path=OUTPUT_PATH_CLIPPED,
        density=kde_masked,
        title="Mapa de Densidade Kernel de Acidentes em Pernambuco - Municípios Marcados",
        title_fontsize=9.8,
        municipality_layer=selected,
        municipality_linewidth=0.45,
        clip_to_marked=True,
    )

    print(f"Mapa gerado com sucesso em: {OUTPUT_PATH}")
    print(f"Mapa recortado gerado com sucesso em: {OUTPUT_PATH_CLIPPED}")


if __name__ == "__main__":
    main()
