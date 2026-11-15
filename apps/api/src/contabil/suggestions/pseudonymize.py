"""Pseudonimização da descrição bancária antes do envio ao modelo (ADR 035).

Documentos, e-mail, telefone e números longos saem por regra. Nome de pessoa sai por
heurística, só depois de PIX, TED, DOC, transferência, "RECEBIDO DE" ou "ENVIADO PARA":
um nome sem esses prefixos passa (lacuna registrada na ADR e em teste). Nada aqui é logado.
"""
from __future__ import annotations

import re
import unicodedata

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_CNPJ_MASKED = re.compile(r"\b[0-9A-Z]{2}\.[0-9A-Z]{3}\.[0-9A-Z]{3}/[0-9A-Z]{4}-\d{2}\b", re.IGNORECASE)
# Sem máscara: 12 posições alfanuméricas e 2 dígitos, com pelo menos 3 dígitos no total.
_CNPJ_PLAIN = re.compile(r"\b(?=(?:[A-Z]*\d){3})[0-9A-Z]{12}\d{2}\b", re.IGNORECASE)
_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b")
_PHONE = re.compile(
    r"(?:\+?55\s?)?(?:\(\d{2}\)\s?|\b\d{2}\s)9?\d{4}[-\s]?\d{4}\b"
    r"|\b9?\d{4}-\d{4}\b"
)
_LONG_NUMBER = re.compile(r"\d{6,}")

_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (_EMAIL, "[EMAIL]"),
    (_CNPJ_MASKED, "[CNPJ]"),
    (_CNPJ_PLAIN, "[CNPJ]"),
    (_CPF, "[CPF]"),
    (_PHONE, "[TELEFONE]"),
    (_LONG_NUMBER, "[NUMERO]"),
)

PERSON = "[PESSOA]"
_PREFIXES = frozenset({"PIX", "TED", "DOC", "TRANSF", "TRANSFERENCIA"})
_TWO_WORD_PREFIXES = frozenset({("RECEBIDO", "DE"), ("ENVIADO", "PARA")})
# Palavras de ligação logo depois do prefixo ("PIX RECEBIDO DE ...") não iniciam o nome.
_LEADING_LINKS = frozenset({"DE", "PARA", "P", "A", "AO"})

# Termos bancários e comerciais: param a máscara de nome e não viram [PESSOA].
_KNOWN_TERMS = frozenset(
    {
        "LTDA", "ME", "EIRELI", "SA", "EPP", "MEI", "CIA", "COMERCIO", "SERVICOS", "SERVICO", "INDUSTRIA",
        "PAGAMENTO", "PAGTO", "PGTO", "PAG", "BOLETO", "TARIFA", "TAXA", "PACOTE", "ALUGUEL", "ENERGIA",
        "AGUA", "LUZ", "GAS", "TELEFONE", "INTERNET", "CONDOMINIO", "SEGURO", "MENSALIDADE", "PARCELA",
        "RECEBIDO", "RECEBIMENTO", "RECEB", "ENVIADO", "ENVIO", "TRANSFERENCIA", "TRANSF", "PIX", "TED", "DOC",
        "DEPOSITO", "SAQUE", "CHEQUE", "COMPRA", "VENDA", "VENDAS", "CARTAO", "CREDITO", "DEBITO", "JUROS",
        "IOF", "MULTA", "IMPOSTO", "DARF", "GPS", "FGTS", "INSS", "ISS", "ICMS", "SIMPLES", "NACIONAL",
        "SALARIO", "FOLHA", "PROLABORE", "FORNECEDOR", "FORNECEDORES", "CLIENTE", "ESTORNO", "DEVOLUCAO",
        "AGENDADO", "AGENDAMENTO", "CONTA", "CORRENTE", "POUPANCA", "APLICACAO", "RESGATE", "RENDIMENTO",
        "EMPRESTIMO", "FINANCIAMENTO", "BANCO", "BANCARIA", "BANCARIO", "REF", "REFERENTE", "NF", "NFE",
        "NOTA", "FISCAL", "FATURA", "COBRANCA", "CONVENIO", "QR", "CODE", "ONLINE", "INTERNO", "EXTERNO",
        "MESMA", "TITULARIDADE",
    }
)


def _key(word: str) -> str:
    plain = unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode("ascii").upper()
    return re.sub(r"[^A-Z0-9]", "", plain)


def _is_marker(word: str) -> bool:
    return word.startswith("[") and word.endswith("]")


def _mask_people(text: str) -> str:
    words = text.split()
    out: list[str] = []
    state = "idle"
    index = 0
    while index < len(words):
        word = words[index]
        key = _key(word)
        if state == "run":
            if _is_marker(word) or key in _KNOWN_TERMS:
                state = "idle"
                continue  # reprocessa a palavra fora do nome: ela pode ser outro prefixo
            if out[-1] != PERSON:
                out.append(PERSON)
            index += 1
            continue
        if state == "lead":
            if not key or _is_marker(word) or key in _KNOWN_TERMS or key in _LEADING_LINKS:
                out.append(word)
                index += 1
                continue
            state = "run"
            out.append(PERSON)
            index += 1
            continue
        out.append(word)
        index += 1
        if key in _PREFIXES:
            state = "lead"
        elif index < len(words) and (key, _key(words[index])) in _TWO_WORD_PREFIXES:
            out.append(words[index])
            index += 1
            state = "lead"
    return " ".join(out)


def pseudonymize(text: str) -> str:
    result = text or ""
    for pattern, marker in _RULES:
        result = pattern.sub(marker, result)
    return _mask_people(result)
