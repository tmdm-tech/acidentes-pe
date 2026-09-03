DROP TABLE IF EXISTS "acidentes_observatrafego_snapshot";
CREATE TABLE "acidentes_observatrafego_snapshot" (
  "id" TEXT, "municipio_notificacao" TEXT, "nome_notificante" TEXT,
  "endereco" TEXT, "veiculo_usuario" TEXT, "sinistro_com_vitimas" TEXT,
  "quantidade_vitimas" TEXT, "sinistro_vitimas" TEXT, "equipamentos_seguranca" TEXT,
  "latitude" TEXT, "longitude" TEXT, "descricao" TEXT,
  "registro_no_local_sinistro" TEXT, "registro_fora_local_descricao" TEXT,
  "tempo_registro_segundos" INTEGER, "data_hora" TEXT, "photo_count" INTEGER
);

INSERT INTO "acidentes_observatrafego_snapshot" ("id", "municipio_notificacao", "nome_notificante", "endereco", "veiculo_usuario", "sinistro_com_vitimas", "quantidade_vitimas", "sinistro_vitimas", "equipamentos_seguranca", "latitude", "longitude", "descricao", "registro_no_local_sinistro", "registro_fora_local_descricao", "tempo_registro_segundos", "data_hora", "photo_count") VALUES ('1788475097302', 'Bom Conselho', 'CBMPE', 'Rua Vidal de Negreiro', 'Motocicleta', 'Sim', '2 vítimas ou mais sem gravidade', '2 vítimas ou mais sem gravidade', 'Nenhum equipamento em uso', '-9.161722', '-36.688434', 'As vítimas transitavam de motocicleta quando um cachorro atravessou a rua e provocou o acidente. Vítimas conscientes orientadas.', 'Não', 'As vítimas transitavam de motocicleta quando um cachorro atravessou a rua e provocou o acidente. Vítimas conscientes orientadas.', '391', '03/09/2026 19:38:17', '2');
COMMIT;
