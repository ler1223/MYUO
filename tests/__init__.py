"""Общие заготовки для тестов."""
import os

# Листы анимаций assets/uo_anim собираются локально и в git не лежат: тесты не должны от них зависеть.
os.environ.setdefault("MYUO_UO_ANIM", "0")
