# Acidentes_PE

## Instalação

```bash
pip install -r requirements.txt
```

## Execução

```bash
python -m gunicorn server:app --bind 0.0.0.0:$PORT
```

Use `PORT=8000` como padrão local quando a variável não estiver definida.

## Endpoints

- GET `/` : status da API
- GET `/health` : healthcheck para monitoramento
- GET `/version` : versão atual da API

## Render

Arquivos incluídos:
- Procfile
- .render.yaml

Deploy por Render:
1. Crie projeto no Render apontando para este repositório.
2. O comando de build é `pip install -r requirements.txt`.
3. O comando de start é `python -m gunicorn server:app --bind 0.0.0.0:$PORT`.

## Execução local rápida

```bash
PORT=8000 python -m gunicorn server:app --bind 0.0.0.0:$PORT
```
