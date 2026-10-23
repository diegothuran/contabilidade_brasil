# Plataforma contábil brasileira — contexto para IA

Este repositório é uma fundação de produto, domínio e contratos. Ele não é ainda uma aplicação pronta e não contém regras fiscais suficientes para produção.

## Conceitos principais

- **Escritório:** organização que atende várias empresas e usuários.
- **LegalEntity:** empresa juridicamente responsável, identificada por CNPJ no escopo inicial.
- **Establishment:** estabelecimento, filial ou inscrição que altera regra e obrigação.
- **Ledger:** razão de partidas dobradas com journals e linhas publicadas.
- **Subledger:** módulo de origem, como contas a pagar, receber, banco, estoque ou ativo.
- **Regulatory registry:** catálogo versionado de obrigação, leiaute, XSD, tabela, regra, prazo e órgão.
- **Evidence:** documento original, hash, assinatura, protocolo, recibo, aprovação e evento.
- **Close run:** execução de fechamento com checklist, pendências, aprovações e snapshot.

## Fronteiras

O ledger não deve conhecer o detalhe de um município. O registry regulatório não deve alterar journals sem workflow. O conector externo não deve decidir a política de tenant. A IA pode sugerir classificação, correspondência ou explicação, mas a aplicação valida e um usuário autorizado aprova qualquer efeito contábil ou fiscal.

## Incerteza

Quando o contador ainda não decidiu uma regra ou o benchmark não comprova uma capacidade, escreva uma pergunta de decisão ou uma POC. Não converta incerteza em código permanente.

## Operação

Use os schemas como fonte normativa para payloads. Execute todos os validadores antes de concluir. Dados reais de clientes, XML, certificados e credenciais não entram neste repositório.
