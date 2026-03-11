# Acidentes_PE

## Instalação

Para instalar as dependências do projeto:

```bash
pip install -r requirements.txt
```

## Execução (Gunicorn)

Inicie o servidor com:

```bash
gunicorn app:app --bind 0.0.0.0:$PORT
```

> Nota: certifique-se que sua aplicação expõe `app` no módulo `app`.
