# ADR 011 — Object storage S3-compatível, MinIO só em localhost

**Status:** proposed · **Data:** 12 de outubro de 2026

## Contexto

A Fase B precisa guardar o arquivo original, o hash e a referência do objeto sem colocar o conteúdo no banco nem no log. O contrato de armazenamento não deve depender do console do MinIO.

## Decisão

A aplicação fala com um adaptador S3 (`put`, `open`, `exists`). A chave é `{tenant_id}/documents/{sha256}` e a referência gravada é `s3://{bucket}/{chave}`. No compose local o serviço é MinIO, com credenciais falsas e buckets `contabil-dev` e `contabil-test`. A imagem `minio/minio` saiu do Docker Hub; o compose usa `cgr.dev/chainguard/minio`, que continua falando S3. Essa imagem não traz `mc` nem `curl`, então um passo curto consulta `/minio/health/live` antes da migração. Um bucket gerenciado no futuro troca o endpoint, não o módulo de documentos.

## Consequências

O mesmo conteúdo no mesmo escritório devolve o documento já existente. O limite local de upload é menor que o teto de produto. Retenção definitiva continua em aberto; o documento nasce com `retention_pending` e sem legal hold.
