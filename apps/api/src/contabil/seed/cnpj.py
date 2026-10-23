from __future__ import annotations


def cnpj_digits(base12: str) -> str:
    if len(base12) != 12 or not base12.isdigit():
        raise ValueError("base do CNPJ deve ter 12 dígitos")

    def digit(numbers: str) -> str:
        weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] if len(numbers) == 12 else [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        total = sum(int(number) * weight for number, weight in zip(numbers, weights, strict=True))
        remainder = total % 11
        return "0" if remainder < 2 else str(11 - remainder)

    first = digit(base12)
    second = digit(base12 + first)
    return base12 + first + second
