"""Verknüpfung von Positionen: Eingabefelder übernehmen Ergebnisse oder Eingaben anderer Positionen.

Eine Verknüpfung wird an der Zielposition gespeichert (``Position.links``)::

    {"Va": {"pos": "<Positions-ID>", "art": "ergebnis", "key": "V"}}

``art`` ist ``"ergebnis"`` (Ergebniswert der Quelle) oder ``"eingabe"`` (Eingabefeld der Quelle, z. B.
das Medium). Der zuletzt übernommene Wert steht zusätzlich in ``Position.inputs`` – ältere Programm-
versionen öffnen die Datei daher ohne Verknüpfungen, aber mit den richtigen Zahlen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model import Calculator, CalcResult, ChoiceField, NumberField
from .project import Position, Project
from .units import Q_, fmt_num, pretty_unit, runden

ERGEBNIS, EINGABE = "ergebnis", "eingabe"


@dataclass
class Kandidat:
    link: dict[str, str]
    position: str          # Anzeige „Pos. 1 – …“
    groesse: str           # „Förderstrom V̇_A“
    wert: str              # „3,500 m³/h“


@dataclass
class Aufloesung:
    """Ergebnis einer Auflösung: Eingaben mit übernommenen Werten, Ergebnisse, Fehler je Feld."""

    inputs: dict[str, dict[str, Any]] = field(default_factory=dict)       # pid -> Eingaben
    results: dict[str, CalcResult] = field(default_factory=dict)          # pid -> Ergebnis
    fehler: dict[str, dict[str, str]] = field(default_factory=dict)       # pid -> {feld: Meldung}


# ------------------------------------------------------------------ Graph
def abhaengigkeiten(pos: Position) -> set[str]:
    return {lk["pos"] for lk in pos.links.values()}


def abhaengige(project: Project, pid: str) -> list[str]:
    """Alle Positionen, die direkt oder indirekt von ``pid`` abhängen (Reihenfolge: Abarbeitung)."""
    out: list[str] = []
    frontier = [pid]
    while frontier:
        cur = frontier.pop(0)
        for p in project.positions:
            if cur in abhaengigkeiten(p) and p.id not in out and p.id != pid:
                out.append(p.id)
                frontier.append(p.id)
    return out


def erzeugt_kreis(project: Project, ziel: str, quelle: str) -> bool:
    """True, wenn eine Verknüpfung ``ziel`` ← ``quelle`` einen Kreis bilden würde."""
    return quelle == ziel or quelle in abhaengige(project, ziel)


def reihenfolge(project: Project) -> list[str]:
    """Positionen so sortiert, dass Quellen vor ihren Zielen stehen (Kreise werden ignoriert)."""
    ids = {p.id for p in project.positions}
    done: list[str] = []
    seen: set[str] = set()

    def visit(pid: str, stack: set[str]) -> None:
        if pid in seen or pid in stack or pid not in ids:
            return
        stack.add(pid)
        for dep in abhaengigkeiten(project.get(pid)):
            visit(dep, stack)
        stack.discard(pid)
        seen.add(pid)
        done.append(pid)

    for p in project.positions:
        visit(p.id, set())
    return done


# ------------------------------------------------------------ Werte holen
def _wert(link: dict[str, str], src_calc: Calculator, src_inputs: dict[str, Any], src_result: CalcResult | None,
          ziel) -> Any:
    """Wert der Quelle umgerechnet in die Einheit des Zielfelds; ValueError mit Klartext bei Problemen."""
    if link["art"] == EINGABE:
        try:
            sf = src_calc.field(link["key"])
        except KeyError:
            raise ValueError(f"Eingabe „{link['key']}“ gibt es in der Quelle nicht mehr.") from None
        v = (src_calc.defaults() | src_inputs).get(link["key"])
        if isinstance(ziel, ChoiceField):
            if v not in dict(ziel.options):
                raise ValueError(f"„{v}“ ist hier keine gültige Auswahl.")
            return v
        if isinstance(sf, NumberField) and isinstance(v, (int, float)):
            return _umrechnen(float(v), sf.unit, ziel.unit)
        raise ValueError("Die Quelleingabe ist keine Zahl.")
    if src_result is None or not src_result.ok:
        raise ValueError("Die Quellposition liefert kein gültiges Ergebnis.")
    rv = next((r for r in src_result.values if r.key == link["key"]), None)
    if rv is None:
        raise ValueError(f"Das Ergebnis „{link['key']}“ wird in der Quelle nicht berechnet.")
    if isinstance(ziel, ChoiceField):
        raise ValueError("Auswahlfelder können nur Eingaben übernehmen.")
    return _umrechnen(rv.value, rv.unit, ziel.unit)


def _umrechnen(value: float, von: str, nach: str) -> float:
    try:
        return float(Q_(value, von or "").to(nach or "").magnitude)
    except Exception:  # noqa: BLE001 - pint: DimensionalityError u. a.
        raise ValueError(f"Einheit {pretty_unit(von) or '–'} passt nicht zu {pretty_unit(nach) or '–'}.") from None


def kompatibel(von: str, nach: str) -> bool:
    try:
        Q_(1.0, von or "").to(nach or "")
        return True
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------- Auflösen
def aufloesen(project: Project, calcs: dict[str, type[Calculator]], nur: str | None = None) -> Aufloesung:
    """Rechnet die Positionen in Abhängigkeitsreihenfolge und setzt verknüpfte Werte ein.

    ``nur``: nur diese Position und ihre Quellen (schneller beim Öffnen einer Position).
    """
    out = Aufloesung()
    order = reihenfolge(project)
    if nur is not None:
        need = {nur}
        changed = True
        while changed:
            changed = False
            for pid in list(need):
                for dep in abhaengigkeiten(project.get(pid)):
                    if dep not in need and any(p.id == dep for p in project.positions):
                        need.add(dep)
                        changed = True
        order = [pid for pid in order if pid in need]
    for pid in order:
        pos = project.get(pid)
        cls = calcs.get(pos.calc)
        if cls is None:
            continue
        calc = cls()
        inputs = calc.upgrade(dict(pos.inputs))
        fehler: dict[str, str] = {}
        for key, lk in pos.links.items():
            try:
                ziel = calc.field(key)
            except KeyError:
                continue
            src = next((p for p in project.positions if p.id == lk["pos"]), None)
            if src is None or src.id not in out.inputs:
                fehler[key] = "Quellposition nicht vorhanden."
                continue
            src_cls = calcs[src.calc]
            try:
                v = _wert(lk, src_cls(), out.inputs[src.id], out.results.get(src.id), ziel)
                inputs[key] = runden(v, ziel.decimals) if isinstance(ziel, NumberField) else v
            except ValueError as exc:
                fehler[key] = str(exc)
        out.inputs[pid] = inputs
        out.results[pid] = calc.run(inputs)
        if fehler:
            out.fehler[pid] = fehler
    return out


def uebernehmen(project: Project, calcs: dict[str, type[Calculator]]) -> list[str]:
    """Schreibt verknüpfte Werte in die gespeicherten Eingaben; liefert die geänderten Positionen."""
    res = aufloesen(project, calcs)
    changed = []
    for pos in project.positions:
        if not pos.links or pos.id not in res.inputs:
            continue
        neu = {k: res.inputs[pos.id][k] for k in pos.links if k in res.inputs[pos.id]
               and k not in res.fehler.get(pos.id, {})}
        if any(pos.inputs.get(k) != v for k, v in neu.items()):
            project.update(pos.id, inputs=pos.inputs | neu)
            changed.append(pos.id)
    return changed


# --------------------------------------------------------------- Auswahl
def beschreibung(project: Project, calcs: dict[str, type[Calculator]], link: dict[str, str]) -> str:
    """Kurztext „Pos. 1 · V̇_A“ für Anzeige und Bericht."""
    src = next((p for p in project.positions if p.id == link["pos"]), None)
    if src is None:
        return "Quelle fehlt"
    cls = calcs.get(src.calc)
    pos_txt = f"Pos. {src.nr}" if src.nr else (src.titel or (cls.title if cls else src.calc))
    sym = link["key"]
    if cls is not None:
        if link["art"] == EINGABE:
            try:
                f = cls().field(link["key"])
                sym = getattr(f, "symbol", "") or f.label
            except KeyError:
                pass
        else:
            sym = _symbole(cls).get(link["key"], link["key"])
    return f"{pos_txt} · {sym}"


_SYM_CACHE: dict[str, dict[str, str]] = {}


def _symbole(cls: type[Calculator]) -> dict[str, str]:
    if cls.id not in _SYM_CACHE:
        r = cls().run({})
        _SYM_CACHE[cls.id] = {v.key: v.symbol or v.label for v in r.values}
    return _SYM_CACHE[cls.id]


def kandidaten(project: Project, calcs: dict[str, type[Calculator]], ziel_pid: str, key: str) -> list[Kandidat]:
    """Mögliche Quellen für ein Feld: passende Ergebnisse und Eingaben aller anderen Positionen."""
    ziel_pos = project.get(ziel_pid)
    ziel = calcs[ziel_pos.calc]().field(key)
    res = aufloesen(project, calcs)
    out: list[Kandidat] = []
    for pos in project.positions:
        if pos.id == ziel_pid or erzeugt_kreis(project, ziel_pid, pos.id) or pos.calc not in calcs:
            continue
        cls = calcs[pos.calc]
        calc = cls()
        label = pos.label(cls.title)
        inputs = calc.defaults() | res.inputs.get(pos.id, pos.inputs)
        result = res.results.get(pos.id)
        if isinstance(ziel, NumberField):
            if result is not None and result.ok:
                for rv in result.values:
                    if kompatibel(rv.unit, ziel.unit):
                        out.append(Kandidat({"pos": pos.id, "art": ERGEBNIS, "key": rv.key}, label,
                                            f"{rv.label} ({rv.symbol})" if rv.symbol else rv.label, rv.text))
            for f in calc.fields:
                if isinstance(f, NumberField) and kompatibel(f.unit, ziel.unit) and calc.is_visible(f, inputs):
                    try:
                        txt = f"{fmt_num(float(inputs[f.key]), f.decimals)} {pretty_unit(f.unit)}".strip()
                    except (TypeError, ValueError):
                        continue
                    out.append(Kandidat({"pos": pos.id, "art": EINGABE, "key": f.key}, label,
                                        f"Eingabe: {f.label} ({f.symbol})", txt))
        elif isinstance(ziel, ChoiceField):
            erlaubt = dict(ziel.options)
            for f in calc.fields:
                if isinstance(f, ChoiceField) and inputs.get(f.key) in erlaubt and (
                        f.key == key or set(dict(f.options)) & set(erlaubt) == set(dict(f.options))):
                    out.append(Kandidat({"pos": pos.id, "art": EINGABE, "key": f.key}, label,
                                        f"Eingabe: {f.label}", f.label_for(inputs[f.key])))
    return out


def loesen_fuer_quelle(project: Project, quelle: str) -> list[tuple[str, str]]:
    """Entfernt alle Verknüpfungen auf ``quelle`` (z. B. beim Löschen); liefert (pid, feld)."""
    weg = []
    for pos in project.positions:
        for key in [k for k, lk in pos.links.items() if lk["pos"] == quelle]:
            del pos.links[key]
            weg.append((pos.id, key))
    if weg:
        project.dirty = True
    return weg


# ---------------------------------------------------------------- Ketten
@dataclass
class Kette:
    titel: str
    beschreibung: str
    # (Rechner-ID, Bezeichnung, {Zielfeld: (Index der Quelle in der Kette, Art, Schlüssel)}
    #  [, Starteingaben [, Notiz]])
    glieder: list[tuple]


KETTEN = [
    Kette("Pumpenkette", "Auslegung → Kennlinie & Betriebspunkt → Leistung & Motor → Energiekosten → NPSH", [
        ("pu.auslegung", "Pumpe – Auslegung", {}),
        ("pu.betriebspunkt", "Pumpe – Betriebspunkt", {
            "Va": (0, ERGEBNIS, "V"), "Ha": (0, ERGEBNIS, "H"), "Hs": (0, ERGEBNIS, "Hstat"),
            "rho": (0, ERGEBNIS, "rho")}),
        ("pu.leistung", "Pumpe – Leistung & Motor", {
            "V": (1, ERGEBNIS, "Qb"), "H": (1, ERGEBNIS, "Hb"), "rho": (0, ERGEBNIS, "rho"),
            "etaP": (1, ERGEBNIS, "eta")}),
        ("pu.energie", "Pumpe – Energiekosten", {
            "VN": (1, ERGEBNIS, "Qb"), "HN": (1, ERGEBNIS, "Hb"), "H0": (1, ERGEBNIS, "H0"),
            "Hs": (0, ERGEBNIS, "Hstat"), "eta": (2, ERGEBNIS, "eta"), "rho": (0, ERGEBNIS, "rho")}),
        ("pu.npsh", "Pumpe – NPSH", {
            "medium": (0, EINGABE, "medium"), "theta": (0, EINGABE, "theta"), "V": (1, ERGEBNIS, "Qb"),
            "rho": (0, EINGABE, "rho"), "nu": (0, EINGABE, "nu")}),
    ]),
    Kette("Rohrnetz + Pumpenkette",
          "Rohrnetz-Strang → Kennlinie & Betriebspunkt → Leistung & Motor → Energiekosten → NPSH", [
              ("fl.rohrnetz", "Rohrnetz – ungünstigster Strang", {}),
              ("pu.betriebspunkt", "Pumpe – Betriebspunkt", {
                  "Va": (0, ERGEBNIS, "V"), "Ha": (0, ERGEBNIS, "H"), "rho": (0, ERGEBNIS, "rho")}),
              ("pu.leistung", "Pumpe – Leistung & Motor", {
                  "V": (1, ERGEBNIS, "Qb"), "H": (1, ERGEBNIS, "Hb"), "rho": (0, ERGEBNIS, "rho"),
                  "etaP": (1, ERGEBNIS, "eta")}),
              ("pu.energie", "Pumpe – Energiekosten", {
                  "VN": (1, ERGEBNIS, "Qb"), "HN": (1, ERGEBNIS, "Hb"), "H0": (1, ERGEBNIS, "H0"),
                  "eta": (2, ERGEBNIS, "eta"), "rho": (0, ERGEBNIS, "rho")}),
              ("pu.npsh", "Pumpe – NPSH", {
                  "medium": (0, EINGABE, "medium"), "theta": (0, EINGABE, "theta"), "V": (1, ERGEBNIS, "Qb"),
                  "rho": (0, EINGABE, "rho"), "nu": (0, EINGABE, "nu")}),
          ]),
    Kette("Abwasserpumpwerk",
          "Druckleitung → Kennlinie & Betriebspunkt → Pumpensumpf → Druckstoß → NPSH", [
              ("aw.druckleitung", "Pumpwerk – Druckleitung", {}),
              ("pu.betriebspunkt", "Pumpwerk – Betriebspunkt", {
                  "Va": (0, ERGEBNIS, "V"), "Ha": (0, ERGEBNIS, "H"), "Hs": (0, ERGEBNIS, "Hstat"),
                  "rho": (0, ERGEBNIS, "rho")},
               {"kennlinie": [[0, 34, 0], [20, 33, 30], [40, 31, 50], [60, 28, 62], [80, 24, 64], [100, 19, 58]],
                "nN": 1450},
               "BEISPIELKENNLINIE einer Abwasserpumpe – durch die Datenblattwerte der gewählten Pumpe ersetzen."),
              ("aw.pumpensumpf", "Pumpwerk – Pumpensumpf", {"QP": (1, ERGEBNIS, "Qb")}),
              ("aw.druckstoss", "Pumpwerk – Druckstoß", {
                  "v0": (0, ERGEBNIS, "v"), "L": (0, EINGABE, "L"), "da": (0, ERGEBNIS, "da"),
                  "s": (0, ERGEBNIS, "s"), "rho": (0, ERGEBNIS, "rho"), "p0": (0, ERGEBNIS, "p")}),
              ("pu.npsh", "Pumpwerk – NPSH", {
                  "medium": (0, EINGABE, "medium"), "theta": (0, EINGABE, "theta"), "V": (1, ERGEBNIS, "Qb"),
                  "rho": (0, EINGABE, "rho"), "nu": (0, EINGABE, "nu")},
               {"hz": 1.0, "rohr": "st:DN 150", "L": 3, "zeta": 1.5},
               "Trocken aufgestellte Pumpe mit Zulauf aus dem Sumpf; bei Tauchmotorpumpen Mindestüberdeckung "
               "nach Herstellerangabe statt NPSH-Nachweis."),
          ]),
    Kette("Lüftungsanlage", "Luftvolumenstrom → Kanalnetz-Strang → Ventilator & SFP → Wärmerückgewinnung", [
        ("lu.luftmenge", "RLT – Luftvolumenstrom", {}),
        ("lu.kanalnetz", "RLT – Kanalnetz (ungünstigster Strang)", {}, {},
         "Erste Teilstrecke mit dem Volumenstrom aus Pos. „RLT – Luftvolumenstrom“ (bzw. Gerätevolumenstrom) "
         "beginnen."),
        ("lu.ventilator", "RLT – Ventilator", {
            "V": (1, ERGEBNIS, "V"), "dp_ext": (1, ERGEBNIS, "dpext"), "dp_int": (1, ERGEBNIS, "dpg")}),
        ("lu.wrg", "RLT – Wärmerückgewinnung", {
            "V": (1, ERGEBNIS, "V"), "Vab": (1, ERGEBNIS, "V"), "t": (2, EINGABE, "t"),
            "p_strom": (2, EINGABE, "preis")}),
    ]),
    Kette("Getriebeauslegung",
          "Antriebsauslegung → Übersetzung → Stirnrad (Stufe 1) → Tragfähigkeit → Wälzlager → Passfeder (Abtrieb)", [
              ("mb.antrieb", "Getriebe – Antriebsauslegung", {}),
              ("mb.uebersetzung", "Getriebe – Übersetzung", {
                  "n1": (0, EINGABE, "n1"), "n2": (0, EINGABE, "n2"), "P": (0, ERGEBNIS, "P1")}),
              ("mb.stirnrad", "Getriebe – Stirnrad Stufe 1", {"z1": (1, ERGEBNIS, "z1_1"), "z2": (1, ERGEBNIS, "z2_1")},
               {"mn": 2.5, "b": 30}),
              ("mb.zahnrad_tragfaehigkeit", "Getriebe – Tragfähigkeit Stufe 1", {
                  "mn": (2, EINGABE, "mn"), "z1": (2, EINGABE, "z1"), "z2": (2, EINGABE, "z2"),
                  "beta": (2, EINGABE, "beta"), "alpha": (2, EINGABE, "alpha"), "x1": (2, ERGEBNIS, "x1"),
                  "x2": (2, ERGEBNIS, "x2"), "b": (2, EINGABE, "b"), "M1": (1, ERGEBNIS, "M_0"),
                  "n1": (0, EINGABE, "n1"), "KA": (0, ERGEBNIS, "fB")}),
              ("mb.waelzlager", "Getriebe – Lager Ritzelwelle", {
                  "Ft": (3, ERGEBNIS, "Ft"), "Fr_z": (3, ERGEBNIS, "Fr"), "Fa_z": (3, ERGEBNIS, "Fa"),
                  "dw": (3, ERGEBNIS, "dw1"), "n": (0, EINGABE, "n1")}, {"kraefte": "zahnrad"}),
              ("mb.passfeder", "Getriebe – Passfeder Abtrieb", {"T": (0, ERGEBNIS, "M2"), "KA": (0, ERGEBNIS, "fB")},
               {"d": 60, "L": 90}),
          ]),
]


def kette_anlegen(project: Project, kette: Kette, after: str | None = None) -> list[str]:
    """Legt die Positionen einer Kette mit allen Verknüpfungen an; liefert die neuen Positions-IDs."""
    pids: list[str] = []
    for calc_id, titel, links, *extra in kette.glieder:
        inputs, notiz = (list(extra) + [{}, ""])[:2]
        pos = project.add_position(calc_id, dict(inputs), notiz, titel=titel, after=pids[-1] if pids else after)
        pos.links = {k: {"pos": pids[i], "art": art, "key": key} for k, (i, art, key) in links.items()}
        pids.append(pos.id)
    return pids
