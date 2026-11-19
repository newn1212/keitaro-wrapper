"""Логика долей (процентов) трафика между офферами потока. Сумма всегда должна быть 100."""


def even_shares(n: int) -> list[int]:
    """Поровну на n офферов; остаток раздаётся первым. 3 -> [34, 33, 33]."""
    if n <= 0:
        return []
    base, rem = divmod(100, n)
    return [base + (1 if i < rem else 0) for i in range(n)]


def validate_shares(shares: dict[int, int], offer_ids: set[int]) -> None:
    if set(shares) != offer_ids:
        raise ValueError("Доли нужно указать для всех офферов потока")
    if any(v < 0 or v > 100 for v in shares.values()):
        raise ValueError("Каждая доля должна быть от 0 до 100")
    total = sum(shares.values())
    if total != 100:
        raise ValueError(f"Сумма долей должна быть 100%, сейчас {total}%")
