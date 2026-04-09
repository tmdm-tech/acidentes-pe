-- Migração: adiciona a coluna photo_count à tabela acidentes
-- Execute este script no SQL Editor do Supabase (projeto: izdubenyjyxhtooaaxzv)
-- Esta coluna já consta no schema canônico (acidentes_schema.sql) mas pode estar
-- ausente em bancos criados antes desta migração.

alter table if exists public.acidentes
  add column if not exists photo_count integer not null default 0;

comment on column public.acidentes.photo_count is
  'Quantidade de fotos anexadas ao registro.';
