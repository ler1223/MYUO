"""Бесконечная башня: бои подряд с усиливающимися врагами (окно pygame-ce).

Запуск: python tower.py [язык]
Работает рядом с demo_pygame.py: справочник data/ общий, правки из демо применяются
перед следующим боем (или по F5). Забег сохраняется в saves/tower.json.
"""
import sys

from pygame_tower import main

if __name__ == "__main__":
    main(lang=sys.argv[1] if len(sys.argv) > 1 else None)
