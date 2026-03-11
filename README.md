# Acidentes_PE

## Instalação

```bash
pip install -r requirements.txt
```

## Execução

```bash
gunicorn server:app --bind 0.0.0.0:$PORT
```

## Endpoints

- GET `/` : retorna status
- GET `/health` : retorna status

## Render

Arquivos incluídos:
- Procfile
- .render.yaml

Deploy por Render:
1. Crie projeto no Render apontando para este repositório.
2. O comando de build é `pip install -r requirements.txt`.
3. O comando de start é `gunicorn server:app --bind 0.0.0.0:$PORT`.
