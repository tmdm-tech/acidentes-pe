create table if not exists public.acidentes (
  id text primary key,
  municipio_notificacao text not null,
  nome_notificante text not null,
  endereco text not null,
  veiculo_usuario text not null,
  registro_no_local_sinistro text,
  registro_fora_local_descricao text,
  sinistro_com_vitimas text not null,
  quantidade_vitimas text,
  sinistro_vitimas text,
  equipamentos_seguranca text not null,
  latitude text not null,
  longitude text not null,
  descricao text,
  fotos jsonb not null default '[]'::jsonb,
  tempo_registro_segundos integer not null default 0,
  data_hora text not null,
  photo_count integer not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists idx_acidentes_created_at
  on public.acidentes (created_at desc);