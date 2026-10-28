# Plataforma contábil brasileira — contexto para IA

Este repositório é uma fundação de produto, domínio e contratos, com uma aplicação que já roda num piloto hospedado com dados fictícios. Ele não contém regras fiscais suficientes para produção.

## Conceitos principais

- **Escritório:** organização que atende várias empresas e usuários. É o tenant.
- **LegalEntity:** empresa juridicamente responsável, identificada por CNPJ no escopo inicial.
- **Establishment:** estabelecimento, filial ou inscrição que altera regra e obrigação.
- **Ledger:** razão de partidas dobradas com journals e linhas publicadas.
- **Subledger:** módulo de origem, como contas a pagar, receber, banco, estoque ou ativo.
- **Regulatory registry:** catálogo versionado de obrigação, leiaute, XSD, tabela, regra, prazo e órgão.
- **Evidence:** documento original, hash, assinatura, protocolo, recibo, aprovação e evento.
- **Close run:** execução de fechamento com checklist, pendências, aprovações e snapshot.
- **Document request:** pedido de documento numa competência. Aberto ou recebido bloqueia o fechamento.
- **Operational export:** pacote JSON da competência com hash, gerado de forma assíncrona.
- **Cliente da empresa:** login com papel `client`, ligado a uma empresa só, que envia o arquivo do próprio pedido.

## Fronteiras

O ledger não deve conhecer o detalhe de um município. O registry regulatório não deve alterar journals sem workflow. O conector externo não deve decidir a política de tenant. O cliente da empresa não entra na sala do escritório e não confirma o próprio pedido. A IA pode sugerir classificação, correspondência ou explicação, mas a aplicação valida e um usuário autorizado aprova qualquer efeito contábil ou fiscal.

## Incerteza

Quando o contador ainda não decidiu uma regra ou o benchmark não comprova uma capacidade, escreva uma pergunta de decisão ou uma POC. Não converta incerteza em código permanente.

## Operação

Use os schemas como fonte normativa para payloads. Mudança que a tela precisa entender atualiza, no mesmo commit, a SPEC do Rastro, as ADRs, o README, o caderno do contador, o OpenAPI e o README do piloto. Execute todos os validadores antes de concluir. Dados reais de clientes, XML, certificados e credenciais não entram neste repositório.
