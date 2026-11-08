"""CPF fictício para amostras: os 9 primeiros dígitos são escolhidos e os 2 verificadores são calculados."""

from __future__ import annotations


def cpf_digits(base9: str) -> str:
    if len(base9) != 9 or not base9.isdigit():
        raise ValueError("base do CPF deve ter 9 dígitos")
    digits = base9
    for size in (9, 10):
        total = sum(int(digits[i]) * (size + 1 - i) for i in range(size))
        digits += str((total * 10) % 11 % 10)
    return digits
