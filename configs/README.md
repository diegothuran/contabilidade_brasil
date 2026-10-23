# Configurações

`product.yaml` contém defaults seguros e decisões pendentes. Não contém credenciais, chaves, dados de cliente nem regras fiscais de produção. Valores regulatórios devem vir do registry versionado e aprovado.

A fundação local fixa `relational_database: postgresql` e `object_storage: s3_compatible`. Fila, identidade de produção e certificados continuam pendentes.
