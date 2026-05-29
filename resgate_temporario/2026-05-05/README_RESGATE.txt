Resgate temporario de registros - gerado automaticamente.

Estrutura:
- soltos/: snapshots de arquivos de dados da raiz.
- exports_snapshot/: copia das exportacoes disponiveis.
- incoming_jsonl/: novos registros recebidos pelo app a partir desta atualizacao.

Objetivo: evitar perda de dados antes da migracao definitiva para Supabase.
