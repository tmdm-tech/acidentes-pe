-- Observa ATT / SES
-- Migração inicial para PostgreSQL da SES
-- Alvo esperado: SR-SECLXBDP6047 (10.16.56.47:5432)
-- Execute conectado ao banco definido em DB_NAME.
-- Este script NÃO cria banco/usuário do sistema operacional e NÃO contém credenciais.

BEGIN;

CREATE SCHEMA IF NOT EXISTS public;

-- Tabela operacional principal
CREATE TABLE IF NOT EXISTS public.acidentes (
  id text PRIMARY KEY,
  municipio_notificacao text NOT NULL,
  nome_notificante text NOT NULL,
  endereco text NOT NULL,
  veiculo_usuario text NOT NULL,
  registro_no_local_sinistro text,
  registro_fora_local_descricao text,
  sinistro_com_vitimas text NOT NULL,
  quantidade_vitimas text,
  sinistro_vitimas text,
  equipamentos_seguranca text NOT NULL,
  latitude text NOT NULL,
  longitude text NOT NULL,
  descricao text,
  fotos jsonb NOT NULL DEFAULT '[]'::jsonb,
  tempo_registro_segundos integer NOT NULL DEFAULT 0,
  data_hora text NOT NULL,
  photo_count integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_acidentes_created_at
  ON public.acidentes (created_at DESC);

-- Base/ranking consolidado do piloto
CREATE TABLE IF NOT EXISTS public.planilha_att (
  rank integer,
  municipio text,
  geres text,
  notificacoes_att integer
);

-- O dump de dados versionado do projeto é a fonte para a carga inicial desta tabela.
-- Não fazemos TRUNCATE automaticamente aqui para evitar apagar dados já existentes na SES.

COMMIT;

-- Verificações pós-migração
SELECT current_database() AS database_name,
       current_user AS database_user,
       inet_server_addr() AS server_address,
       inet_server_port() AS server_port;

SELECT 'public.acidentes' AS tabela, COUNT(*) AS registros
FROM public.acidentes
UNION ALL
SELECT 'public.planilha_att' AS tabela, COUNT(*) AS registros
FROM public.planilha_att;
