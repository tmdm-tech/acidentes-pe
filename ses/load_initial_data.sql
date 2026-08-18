-- Execute com psql a partir da raiz do repositório:
-- psql "$DATABASE_URL" -f ses/load_initial_data.sql
-- ou defina PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD.

\set ON_ERROR_STOP on

BEGIN;

-- Estruturas
\i ses/migrate_postgresql_ses.sql

-- Carga do ranking consolidado versionado no repositório.
-- O dump já contém os 52 registros e usa TRUNCATE intencionalmente para
-- reconstruir esta tabela de referência.
\i planilha_att.dump.sql

-- Carga do snapshot de resgate dos registros operacionais.
-- A tabela staging permite adaptar o CSV antigo ao schema PostgreSQL atual.
CREATE TEMP TABLE _acidentes_import (
  id text,
  periodo text,
  data_hora_registro text,
  municipio_notificacao text,
  nome_notificante text,
  endereco text,
  veiculo_usuario text,
  registro_no_local_sinistro text,
  registro_fora_local_descricao text,
  sinistro_com_vitimas text,
  quantidade_vitimas text,
  sinistro_vitimas text,
  equipamentos_seguranca text,
  latitude text,
  longitude text,
  quantidade_fotos integer,
  tempo_registro_segundos integer,
  tempo_registro_formatado text
);

\copy _acidentes_import FROM 'resgate_temporario/2026-05-05/exports_snapshot/acidentes_diario_latest.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8', NULL 'None');

INSERT INTO public.acidentes (
  id,
  municipio_notificacao,
  nome_notificante,
  endereco,
  veiculo_usuario,
  registro_no_local_sinistro,
  registro_fora_local_descricao,
  sinistro_com_vitimas,
  quantidade_vitimas,
  sinistro_vitimas,
  equipamentos_seguranca,
  latitude,
  longitude,
  descricao,
  fotos,
  tempo_registro_segundos,
  data_hora,
  photo_count,
  created_at
)
SELECT
  id,
  municipio_notificacao,
  nome_notificante,
  endereco,
  veiculo_usuario,
  NULLIF(registro_no_local_sinistro, ''),
  NULLIF(registro_fora_local_descricao, ''),
  sinistro_com_vitimas,
  NULLIF(quantidade_vitimas, ''),
  NULLIF(sinistro_vitimas, ''),
  equipamentos_seguranca,
  latitude,
  longitude,
  NULL,
  '[]'::jsonb,
  COALESCE(tempo_registro_segundos, 0),
  data_hora_registro,
  COALESCE(quantidade_fotos, 0),
  to_timestamp(
    regexp_replace(data_hora_registro, '(\d{2})/(\d{2})/(\d{4}) (.*)', '\3-\2-\1 \4')
  )
FROM _acidentes_import
ON CONFLICT (id) DO UPDATE SET
  municipio_notificacao = EXCLUDED.municipio_notificacao,
  nome_notificante = EXCLUDED.nome_notificante,
  endereco = EXCLUDED.endereco,
  veiculo_usuario = EXCLUDED.veiculo_usuario,
  registro_no_local_sinistro = EXCLUDED.registro_no_local_sinistro,
  registro_fora_local_descricao = EXCLUDED.registro_fora_local_descricao,
  sinistro_com_vitimas = EXCLUDED.sinistro_com_vitimas,
  quantidade_vitimas = EXCLUDED.quantidade_vitimas,
  sinistro_vitimas = EXCLUDED.sinistro_vitimas,
  equipamentos_seguranca = EXCLUDED.equipamentos_seguranca,
  latitude = EXCLUDED.latitude,
  longitude = EXCLUDED.longitude,
  tempo_registro_segundos = EXCLUDED.tempo_registro_segundos,
  data_hora = EXCLUDED.data_hora,
  photo_count = EXCLUDED.photo_count;

COMMIT;

-- Conferência final
SELECT 'public.acidentes' AS tabela, COUNT(*) AS registros FROM public.acidentes
UNION ALL
SELECT 'public.planilha_att' AS tabela, COUNT(*) AS registros FROM public.planilha_att;
