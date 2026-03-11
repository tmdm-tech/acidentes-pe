# Acidentes_PE

## Instalação

Para instalar as dependências do projeto:

```bash
pip install -r requirements.txt
```

## Execução (Gunicorn)

Inicie o servidor com:

```bash
gunicorn server:app --bind 0.0.0.0:$PORT
```

> Nota: Este projeto expõe a aplicação WSGI `app` no módulo `server`.
