# Projeto KDE Cartografico (Padrao IBGE)

Este projeto gera 3 conjuntos de mapas cientificos de densidade Kernel de acidentes de transito em Pernambuco.

## Arquivos principais

- `main.py`: pipeline completo de simulacao, KDE e exportacao cartografica.
- `requirements.txt`: dependencias Python.
- `outputs/`: pasta de saida com PNG 300 DPI e PDF.

## Requisitos

- Python 3.10+
- Ambiente com acesso a internet para baixar limites municipais via geobr/IBGE e camadas OSM (quando aplicavel).

## Execucao

1. Criar/ativar ambiente virtual (caso necessario):

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Rodar geracao completa:

```bash
python main.py
```

## Saidas esperadas

### Mapa 1 - estadual

- `outputs/kernel_pernambuco_geral.png`
- `outputs/kernel_pernambuco_geral.pdf`

### Mapa 2 - municipais individuais

- `outputs/recife_kernel.png` / `.pdf`
- `outputs/garanhuns_kernel.png` / `.pdf`
- `outputs/canhotinho_kernel.png` / `.pdf`
- `outputs/bom_conselho_kernel.png` / `.pdf`
- `outputs/jaboatao_kernel.png` / `.pdf`

### Mapa 3 - somente acidentes motociclisticos

- `outputs/recife_moto_kernel.png` / `.pdf`
- `outputs/garanhuns_moto_kernel.png` / `.pdf`
- `outputs/canhotinho_moto_kernel.png` / `.pdf`
- `outputs/bom_conselho_moto_kernel.png` / `.pdf`
- `outputs/jaboatao_moto_kernel.png` / `.pdf`

## Notas tecnicas

- CRS padrao: SIRGAS 2000 / UTM Zone 25S (EPSG:31985).
- KDE com `scipy.stats.gaussian_kde` e suavizacao adicional com `scipy.ndimage.gaussian_filter`.
- Mascara raster vetorial com `rasterio.features.geometry_mask`.
- Simulacao de pontos com concentracao espacial orientada por bairros/vias solicitados.
- Estilo visual academico com fundo cinza, limites finos pretos, escala grafica, rosa dos ventos e painel lateral.
