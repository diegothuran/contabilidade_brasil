from __future__ import annotations

from contabil.suggestions.pseudonymize import pseudonymize


def _cpf(base: str) -> str:
    """CPF fictício com dígitos verificadores calculados aqui."""
    digits = [int(char) for char in base]
    for size in (9, 10):
        total = sum(value * weight for value, weight in zip(digits, range(size + 1, 1, -1)))
        rest = (total * 10) % 11
        digits.append(0 if rest == 10 else rest)
    return "".join(str(value) for value in digits)


def _cnpj(base: str) -> str:
    """CNPJ fictício (numérico ou alfanumérico) com dígitos verificadores calculados aqui."""
    values = [ord(char) - 48 for char in base]
    for weights in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        rest = sum(value * weight for value, weight in zip(values, weights)) % 11
        values.append(0 if rest < 2 else 11 - rest)
    return base + "".join(str(value) for value in values[len(base) :])


def _mask_cpf(cpf: str) -> str:
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def _mask_cnpj(cnpj: str) -> str:
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def test_masks_cpf_cnpj_email_phone():
    cpf = _cpf("418273650")
    cnpj = _cnpj("739158420001")
    alpha = _cnpj("12ABC345AB01")
    assert len(cpf) == 11 and len(cnpj) == 14 and len(alpha) == 14
    cases = {
        f"PAGAMENTO CPF {cpf}": "PAGAMENTO CPF [CPF]",
        f"PAGAMENTO CPF {_mask_cpf(cpf)}": "PAGAMENTO CPF [CPF]",
        f"BOLETO CNPJ {cnpj}": "BOLETO CNPJ [CNPJ]",
        f"BOLETO CNPJ {_mask_cnpj(cnpj)}": "BOLETO CNPJ [CNPJ]",
        f"BOLETO CNPJ {alpha}": "BOLETO CNPJ [CNPJ]",
        f"BOLETO CNPJ {_mask_cnpj(alpha)}": "BOLETO CNPJ [CNPJ]",
        "COBRANCA financeiro.teste@exemplo.com.br": "COBRANCA [EMAIL]",
        "CONTATO (11) 98765-4321": "CONTATO [TELEFONE]",
        "CONTATO +55 21 3456-7890": "CONTATO [TELEFONE]",
    }
    for raw, expected in cases.items():
        assert pseudonymize(raw) == expected, raw


def test_masks_long_numbers():
    assert pseudonymize("BOLETO 2026091512345 PARCELA 3") == "BOLETO [NUMERO] PARCELA 3"
    assert pseudonymize("NF123456") == "NF[NUMERO]"
    assert pseudonymize("TARIFA 12345") == "TARIFA 12345"


def test_masks_person_after_pix():
    result = pseudonymize("PIX RECEBIDO JOAO DA SILVA")
    assert "JOAO" not in result and "SILVA" not in result
    assert result == "PIX RECEBIDO [PESSOA]"
    assert pseudonymize("TED ENVIADO PARA Maria Souza Pagamento") == "TED ENVIADO PARA [PESSOA] Pagamento"
    assert pseudonymize("TRANSFERÊNCIA JOSE ALVES LTDA") == "TRANSFERÊNCIA [PESSOA] LTDA"
    assert pseudonymize(f"PIX {_cpf('418273650')} ANA LIMA") == "PIX [CPF] [PESSOA]"


def test_keeps_known_terms():
    assert pseudonymize("PAGAMENTO BOLETO ENERGIA") == "PAGAMENTO BOLETO ENERGIA"
    assert pseudonymize("PIX PAGAMENTO BOLETO") == "PIX PAGAMENTO BOLETO"


def test_heuristic_gap_documented():
    # Lacuna conhecida (ADR 035): nome sem prefixo de PIX, TED, DOC ou transferência passa sem máscara.
    assert pseudonymize("MARIA SOUZA ALUGUEL") == "MARIA SOUZA ALUGUEL"
