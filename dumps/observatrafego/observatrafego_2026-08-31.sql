DROP TABLE IF EXISTS "acidentes_observatrafego_20260831";
CREATE TABLE "acidentes_observatrafego_20260831" (
  "id" TEXT, "municipio_notificacao" TEXT, "nome_notificante" TEXT,
  "endereco" TEXT, "veiculo_usuario" TEXT, "sinistro_com_vitimas" TEXT,
  "quantidade_vitimas" TEXT, "sinistro_vitimas" TEXT, "equipamentos_seguranca" TEXT,
  "latitude" TEXT, "longitude" TEXT, "descricao" TEXT,
  "registro_no_local_sinistro" TEXT, "registro_fora_local_descricao" TEXT,
  "tempo_registro_segundos" INTEGER, "data_hora" TEXT, "photo_count" INTEGER
);

INSERT INTO "acidentes_observatrafego_20260831" ("id", "municipio_notificacao", "nome_notificante", "endereco", "veiculo_usuario", "sinistro_com_vitimas", "quantidade_vitimas", "sinistro_vitimas", "equipamentos_seguranca", "latitude", "longitude", "descricao", "registro_no_local_sinistro", "registro_fora_local_descricao", "tempo_registro_segundos", "data_hora", "photo_count") VALUES ('1788199906400', 'Bom Conselho', 'CBMPE', 'RUA SÃO VICENTE', 'Motocicleta', 'Sim', '1 vítima sem gravidade', '1 vítima sem gravidade', 'Capacete', '0.000000-9.165459', '-6.675272', 'REGISTRO REALIZADO NA 2ª SEÇÃO DE BOMBEIROS EM BOM CONSELHO.', 'Não', 'REGISTRO REALIZADO NA 2ª SEÇÃO DE BOMBEIROS EM BOM CONSELHO.', '1580', '31/08/2026 15:11:46', '2');
COMMIT;
