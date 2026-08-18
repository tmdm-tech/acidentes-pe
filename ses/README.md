# Migração PostgreSQL — SES

Destino previsto: `SR-SECLXBDP6047` (`10.16.56.47:5432`).

## Arquivos

- `migrate_postgresql_ses.sql`: cria a estrutura PostgreSQL.
- `load_initial_data.sql`: cria a estrutura e carrega os dados iniciais versionados.
- `../planilha_att.dump.sql`: carga da `public.planilha_att`.
- `../resgate_temporario/2026-05-05/exports_snapshot/acidentes_diario_latest.csv`: snapshot operacional mais recente encontrado no repositório para carga da `public.acidentes`.

## Execução

Na máquina com acesso ao PostgreSQL da SES, a partir da raiz do repositório:

```bash
export PGHOST=10.16.56.47
export PGPORT=5432
export PGDATABASE=SEU_BANCO
export PGUSER=SEU_USUARIO
export PGPASSWORD='SUA_SENHA'
psql -f ses/load_initial_data.sql
```

Para uma carga apenas da estrutura:

```bash
psql -f ses/migrate_postgresql_ses.sql
```

## Verificação

O carregador termina exibindo a quantidade de registros em `public.acidentes` e `public.planilha_att`.

O snapshot operacional versionado no repositório é usado como fonte de recuperação inicial; arquivos diário/mensal/semanal derivados não devem ser importados como novos acidentes para evitar duplicidade.

## Aplicação

Configure o `.env` do servidor com os valores reais de `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` e `POSTGRES_TABLE`. Não versione credenciais.

O Supabase não é mais dependência de instalação em `requirements.txt`. O PostgreSQL da SES é a fonte de dados prevista para a implantação.
