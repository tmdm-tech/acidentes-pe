alter table if exists public.acidentes
  add column if not exists registro_no_local_sinistro text;

alter table if exists public.acidentes
  add column if not exists registro_fora_local_descricao text;

comment on column public.acidentes.registro_no_local_sinistro is
  'Indica se o registro foi feito no local do sinistro: Sim ou Não.';

comment on column public.acidentes.registro_fora_local_descricao is
  'Breve descricao quando o registro nao for feito no local do sinistro.';