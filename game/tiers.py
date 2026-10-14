"""Тиры юнитов и предметов: число 0..30 в данных, на экране — ступень I, II или III.

Число нужно для тонкого баланса (предмет 14 чуть лучше предмета 11, оба — второй ступени);
ступень — по 10 на каждую: 0..9 — I, 10..19 — II, 20..30 — III.
"""
TIER_MAX = 30
TIER_STEP = 10
RANKS = 3


def rank_of(tier: int) -> int:
    """Ступень (1..3) по числу тира."""
    return max(1, min(RANKS, tier // TIER_STEP + 1))


def check_tier(tier: int, where: str) -> int:
    if not 0 <= tier <= TIER_MAX:
        raise ValueError(f"{where}: tier must be 0..{TIER_MAX}, got {tier}")
    return tier
