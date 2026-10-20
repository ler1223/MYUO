"""Экраны редакторов справочника: снаряжение, теги и правила их взаимодействия."""
from __future__ import annotations

import copy
from typing import Optional

import pygame

from game.definitions import CATEGORIES
from game.editing import new_item_data, new_rule_data, new_tag_data
from game.stats import ModOp, Stat
from game.tags import TAG_DAMAGE, TAG_KINDS, TAG_UNIT
from game.tiers import TIER_MAX
from game.unit import wearable
from pygame_data_editors import list_buttons
from pygame_editors import FORM_X, ROW_H, TOP, EditorHost, apply, entity_list, named, plain, tag_options
from pygame_ui import DIM, PANEL, RED, UI, WIDTH

MODIFIER_ROWS = 8
RULE_ROWS = 9
# Подписи операций модификатора: FLAT прибавляет число, PERCENT_ADD долю (0.2 = +20%), PERCENT_MULT умножает.
OP_LABELS = {ModOp.FLAT: "+ value", ModOp.PERCENT_ADD: "+ share (0.2 = +20%)", ModOp.PERCENT_MULT: "x multiplier"}


class ItemEditor:
    """Предмет: слот, модификаторы статов, теги носителю, тип урона оружия, навыки и пассивки."""

    def __init__(self) -> None:
        self.item_id: Optional[str] = None

    def draw(self, ui: UI, app: EditorHost) -> None:
        db = app.db
        if self.item_id not in db.items:
            self.item_id = next(iter(db.items), None)
        if self.item_id is not None:
            self._draw_form(ui, app, self.item_id)
        ui.text(ui.t("Items"), 16, TOP, DIM, "small")
        clicked = entity_list(ui, "items", named(ui, db.items.values()), self.item_id, TOP + 20, 18)
        if clicked is not None:
            self.item_id = clicked
        new, delete = list_buttons(ui, self.item_id is not None)
        if new:
            self.item_id = db.create("items", "New Item", new_item_data(db))
            app.data_changed()
        elif delete:
            db.delete("items", self.item_id)  # с юнитов предмет снимется сам
            app.data_changed()

    def _draw_form(self, ui: UI, app: EditorHost, item_id: str) -> None:
        t, db, x = ui.t, app.db, FORM_X
        data = db.items[item_id].to_dict()
        new = copy.deepcopy(data)
        key = ("item", item_id)

        ui.text(t("Name"), x, TOP + 4, font="small")
        name = ui.text_input((key, "name"), pygame.Rect(x + 110, TOP, 220, 24), data["name"])
        if name:
            new["name"] = name
        ui.text(f"id: {item_id}", x + 344, TOP + 5, DIM, "small", 130)
        for field, label, fx, high in (("tier", "Tier", 486, TIER_MAX), ("price", "Price", 600, 99999)):
            ui.text(t(label), x + fx, TOP + 4, font="small")
            value = ui.number_input((key, field), pygame.Rect(x + fx + 50, TOP, 60, 24), data[field],
                                    0, high)
            if value is not None:
                new[field] = value

        ui.text(t("Slot type"), x, TOP + 34, font="small")
        picked = ui.dropdown((key, "slot"), pygame.Rect(x + 110, TOP + 30, 220, 24), plain(ui, db.slot_types), data["slot"])
        if picked is not None:
            new["slot"] = picked
            new.pop("kind", None)                  # особый вид принадлежит слоту
        # Вид предмета: кто носит — решает класс (виды класса в редакторе классов)
        kinds = [(k, t("main") if k == data["slot"] else t(k)) for k in db.kinds_of_slot(data["slot"])]
        picked = ui.dropdown((key, "kind"), pygame.Rect(x + 344, TOP + 30, 140, 24), kinds,
                             data.get("kind", data["slot"]))
        if picked is not None:
            new.pop("kind", None)
            if picked != data["slot"]:
                new["kind"] = picked
        wearers = [t(u.name) for u in db.units.values()
                   if wearable(db.items[item_id], db.definition_for(u.id, db.lineage(u.id)))]
        ui.text(f"{t('fits')}: {', '.join(wearers) or '-'}", x + 494, TOP + 35, DIM, "small", WIDTH - x - 510)
        # Исключение: только эти классы (именное оружие, особые аксессуары); пусто — все, кто носит вид
        ui.text(t("Only for classes"), x + 580, TOP + 64, DIM, "small")
        picked = ui.multiselect((key, "classes"), pygame.Rect(x + 580, TOP + 90, 180, 24),
                                named(ui, db.units.values()), data.get("classes", []))
        if picked is not None:
            new["classes"] = picked
            if not picked:
                new.pop("classes")

        lists = (
            ("tags", "Wearer tags", tag_options(ui, db, TAG_UNIT)),
            ("damage_tags", "Damage type", tag_options(ui, db, TAG_DAMAGE)),
            ("skills", "Skills", named(ui, db.skills.values())),
            ("passives", "Passives", named(ui, db.passives.values())),
        )
        for row, (field, label, choices) in enumerate(lists):
            ry = TOP + 60 + row * 30
            ui.text(t(label), x, ry + 4, font="small")
            picked = ui.multiselect((key, field), pygame.Rect(x + 110, ry, 460, 24), choices, data[field])
            if picked is not None:
                new[field] = picked

        # Модификаторы статов
        y = TOP + 60 + len(lists) * 30 + 8
        modifiers = data["modifiers"]
        ui.text(t("Stat modifiers: {n}", n=len(modifiers)), x, y + 4, font="small")
        if ui.button(t("+ Add modifier"), pygame.Rect(x + 250, y, 190, 22)):
            new["modifiers"] = modifiers + [{"stat": Stat.PHYS_ATK.value, "op": ModOp.FLAT.value, "value": 1}]
        for label, offset in (("stat", 22), ("operation", 190), ("value", 404)):
            ui.text(t(label), x + offset, y + 26, DIM, "small")
        y += 44
        area = pygame.Rect(x, y - 2, WIDTH - x - 16, MODIFIER_ROWS * ROW_H)
        pygame.draw.rect(ui.screen, PANEL, area)
        offset = ui.scroll((key, "modifiers"), area, len(modifiers), MODIFIER_ROWS)
        stat_choices = plain(ui, (s.value for s in Stat))
        op_choices = [(op.value, t(label)) for op, label in OP_LABELS.items()]
        for row, index in enumerate(range(offset, min(len(modifiers), offset + MODIFIER_ROWS))):
            mod = modifiers[index]
            edited = dict(mod)
            ry, mkey = y + row * ROW_H, (key, "mod", index)
            ui.text(f"{index + 1}.", x + 4, ry + 4, DIM, "small")
            picked = ui.dropdown((mkey, "stat"), pygame.Rect(x + 22, ry, 164, 24), stat_choices, mod["stat"])
            if picked is not None:
                edited["stat"] = picked
            picked = ui.dropdown((mkey, "op"), pygame.Rect(x + 190, ry, 210, 24), op_choices, mod["op"])
            if picked is not None:
                edited["op"] = picked
            value = ui.number_input((mkey, "value"), pygame.Rect(x + 404, ry, 64, 24), mod["value"], -9999, 9999, False)
            if value is not None:
                edited["value"] = value
            if ui.button("x", pygame.Rect(x + 474, ry, 24, 24), color=RED):
                new["modifiers"] = modifiers[:index] + modifiers[index + 1:]
            elif edited != mod:
                new["modifiers"] = modifiers[:index] + [edited] + modifiers[index + 1:]

        if new != data:
            apply(app, "items", item_id, new)


class TagEditor:
    """Теги и таблица правил: какие теги атаки по каким тегам цели меняют урон и точность."""

    def __init__(self) -> None:
        self.tag_id: Optional[str] = None

    def draw(self, ui: UI, app: EditorHost) -> None:
        t, db = ui.t, app.db
        if self.tag_id not in db.tags:
            self.tag_id = next(iter(db.tags), None)
        if self.tag_id is not None:
            self._draw_tag(ui, app, self.tag_id)
        self._draw_rules(ui, app)
        ui.text(t("Tags"), 16, TOP, DIM, "small")
        entries = [(tag.id, f"{t(tag.name)} ({t(tag.kind)})") for tag in db.tags.values()]
        clicked = entity_list(ui, "tags", entries, self.tag_id, TOP + 20, 18)
        if clicked is not None:
            self.tag_id = clicked
        new, delete = list_buttons(ui, self.tag_id is not None)
        if new:
            self.tag_id = db.create("tags", "New Tag", new_tag_data())
            app.data_changed()
        elif delete:
            db.delete("tags", self.tag_id)  # тег уходит из классов, предметов, навыков и правил
            app.data_changed()

    def _draw_tag(self, ui: UI, app: EditorHost, tag_id: str) -> None:
        t, db, x = ui.t, app.db, FORM_X
        data = db.tags[tag_id].to_dict()
        new = dict(data)
        key = ("tag", tag_id)
        ui.text(t("Name"), x, TOP + 4, font="small")
        name = ui.text_input((key, "name"), pygame.Rect(x + 76, TOP, 190, 24), data["name"])
        if name:
            new["name"] = name
        ui.text(t("Kind"), x + 282, TOP + 4, font="small")
        picked = ui.dropdown((key, "kind"), pygame.Rect(x + 330, TOP, 130, 24), plain(ui, TAG_KINDS), data["kind"])
        if picked is not None:
            new["kind"] = picked
        is_damage = data["kind"] == TAG_DAMAGE
        ui.text(t("Ignores guard"), x + 476, TOP + 4, font="small")
        if ui.button(t("yes") if data["unblockable"] else t("no"), pygame.Rect(x + 600, TOP, 60, 24),
                     data["unblockable"], enabled=is_damage):
            new["unblockable"] = not data["unblockable"]
        ui.text(f"id: {tag_id}", x + 676, TOP + 5, DIM, "small")
        ui.text(t("Kinds: unit = trait of a class, item or effect; damage = damage type; skill = kind of skill."),
                x, TOP + 30, DIM, "small")
        if new != data:
            apply(app, "tags", tag_id, new)

    def _draw_rules(self, ui: UI, app: EditorHost) -> None:
        t, db, x = ui.t, app.db, FORM_X
        y = TOP + 56
        rules = [rule.to_dict() for rule in db.rules]
        new_rules = None
        ui.text(t("Tag rules: {n}", n=len(rules)), x, y + 4)
        if ui.button(t("+ Add rule"), pygame.Rect(x + 200, y, 160, 22)):
            new_rules = rules + [new_rule_data()]
        ui.text(t("A rule applies when the attack has every tag of the first list, none of the second,"),
                x, y + 28, DIM, "small")
        ui.text(t("and the target has every tag of the third. Matching rules multiply together."),
                x, y + 44, DIM, "small")
        for label, offset in (("attack has", 22), ("attack lacks", 222), ("target has", 392),
                              ("damage x", 562), ("accuracy x", 640)):
            ui.text(t(label), x + offset, y + 66, DIM, "small")
        y += 84
        area = pygame.Rect(x, y - 2, WIDTH - x - 16, RULE_ROWS * ROW_H)
        pygame.draw.rect(ui.screen, PANEL, area)
        offset = ui.scroll("tag-rules", area, len(rules), RULE_ROWS)
        # Атака несёт теги навыка, типа урона, оружия, эффектов и самого атакующего, плюс категорию урона.
        attack_choices = [*named(ui, db.tags.values()), *plain(ui, CATEGORIES)]
        target_choices = tag_options(ui, db, TAG_UNIT)
        for row, index in enumerate(range(offset, min(len(rules), offset + RULE_ROWS))):
            rule = rules[index]
            edited = copy.deepcopy(rule)
            ry, rkey = y + row * ROW_H, ("tag-rule", index)
            ui.text(f"{index + 1}.", x + 4, ry + 4, DIM, "small")
            for field, fx, width, choices in (("attack", 22, 196, attack_choices),
                                              ("attack_not", 222, 166, attack_choices),
                                              ("target", 392, 166, target_choices)):
                picked = ui.multiselect((rkey, field), pygame.Rect(x + fx, ry, width, 24), choices, rule[field])
                if picked is not None:
                    edited[field] = picked
            for field, fx in (("damage", 562), ("hit", 640)):
                value = ui.number_input((rkey, field), pygame.Rect(x + fx, ry, 60, 24), rule[field], 0, 100, False)
                if value is not None:
                    edited[field] = value
            if ui.button("x", pygame.Rect(x + 716, ry, 24, 24), color=RED):
                new_rules = rules[:index] + rules[index + 1:]
            elif edited != rule:
                new_rules = rules[:index] + [edited] + rules[index + 1:]
        if new_rules is not None:
            try:
                db.set_rules(new_rules)
                app.data_changed()
            except (ValueError, KeyError, TypeError) as error:
                app.message = str(error)
