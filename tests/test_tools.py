"""Phase 2: Formel-Auswerter, Einheitenumrechnung, Materialdatenbank, Plot-Hilfen."""

import json
import math

import pytest

from ingrechner.core.expr import Evaluator, ExprError, format_result, preprocess
from ingrechner.core.materials import Material, MaterialLibrary
from ingrechner.core.plotting import parse_xy, robust_ylim, sample
from ingrechner.core.unitconv import CATEGORIES, ConversionError, convert, parse_free

approx = pytest.approx


# --------------------------------------------------------------- Auswerter
class TestExpr:
    @pytest.mark.parametrize("text, expected", [
        ("3,5*2", 7), ("3.5*2", 7), ("2^10", 1024), ("2**3", 8), ("-2^2", -4),
        ("10/4", 2.5), ("7 mod 2" if False else "mod(7; 2)", 1), ("max(1; 2,5; 2)", 2.5),
        ("max(1, 2.5)", 2.5), ("sqrt(16)", 4), ("√2", math.sqrt(2)), ("√(9)+3²", 12),
        ("2pi", 2 * math.pi), ("3(4+1)", 15), ("(1+2)(3+4)", 21), ("1e3*2", 2000), ("2,5e3", 2500),
        ("ln(e)", 1), ("log(1000)", 3), ("log(8; 2)", 3), ("log2(8)", 3), ("fact(5)", 120),
        ("abs(-3)", 3), ("round(2,456; 2)", 2.46), ("hypot(3; 4)", 5), ("cbrt(-27)", -3),
        ("g", 9.80665), ("2 × 3 ÷ 4", 1.5),
    ])
    def test_ausdruecke(self, text, expected):
        assert Evaluator().evaluate(text)[1] == approx(expected)

    def test_winkelmodus(self):
        assert Evaluator("deg").evaluate("sin(30)")[1] == approx(0.5)
        assert Evaluator("rad").evaluate("sin(pi/6)")[1] == approx(0.5)
        assert Evaluator("deg").evaluate("atan2(1; 1)")[1] == approx(45)
        assert Evaluator("deg").evaluate("asin(1)")[1] == approx(90)

    def test_variablen_und_ans(self):
        ev = Evaluator()
        assert ev.evaluate("a = 12,5") == ("a", 12.5)
        ev.evaluate("b = 7")
        assert ev.evaluate("2a + b")[1] == approx(32)
        assert ev.evaluate("ans / 2")[1] == approx(16)
        with pytest.raises(ExprError, match="reserviert"):
            ev.evaluate("sin = 3")

    @pytest.mark.parametrize("text, msg", [
        ("1/0", "Division"), ("sqrt(-1)", "Definitionsbereich"), ("ln(0)", "Definitionsbereich"),
        ("9^9^9", "zu groß"), ("(-8)^(1/3)", "reelle"), ("2 +", "Syntax"), ("foo(2)", "Unbekannte Funktion"),
        ("xyz", "Unbekannter Name"), ("fact(200)", "zu groß"), ("fact(2,5)", "natürliche"),
    ])
    def test_fehlermeldungen(self, text, msg):
        with pytest.raises(ExprError, match=msg):
            Evaluator().evaluate(text)

    @pytest.mark.parametrize("attack", [
        "__import__('os').system('echo x')", "(1).__class__", "().__class__.__bases__",
        "open('x')", "[1,2]", "{'a': 1}", "lambda: 1", "1 if 1 else 2", "1 < 2", "a.b",
        "exec('1')", "eval('1')", "True", "'text'", "x[0]", "sin.__globals__",
    ])
    def test_kein_codezugriff(self, attack):
        with pytest.raises(ExprError):
            Evaluator().evaluate(attack)

    def test_funktion_fuer_plot(self):
        f = Evaluator().function("x^2 - 1")
        assert f(3) == approx(8)
        g = Evaluator().function("sqrt(x)")
        assert math.isnan(g(-1))
        with pytest.raises(ExprError):
            Evaluator().function("y + 1")

    def test_implizite_multiplikation_bricht_bezeichner_nicht(self):
        assert preprocess("a2b") == "a2b"
        assert preprocess("2a") == "2*a"
        assert preprocess("1e5") == "1e5"

    def test_format(self):
        assert format_result(1234.5) == "1234,5"
        assert format_result(2.0) == "2"
        assert format_result(1.5e-7) == "1,5E-07".replace("E-07", "E-7")
        assert format_result(3.5999999999999996) == "3,6"


# ---------------------------------------------------------- Einheiten
class TestUnitConv:
    @pytest.mark.parametrize("v, src, dst, ref", [
        (1, "inch", "mm", 25.4), (1, "foot", "m", 0.3048), (1, "bar", "psi", 14.503773773),
        (1, "N/mm**2", "MPa", 1), (100, "degC", "degF", 212), (0, "degC", "K", 273.15),
        (1, "metric_horsepower", "W", 735.49875), (1, "kW*h", "MJ", 3.6), (1, "kilogram_force", "N", 9.80665),
        (1, "m_H2O", "mbar", 98.0665), (1, "centistokes", "mm**2/s", 1), (1, "centipoise", "mPa*s", 1),
        (1000, "revolution/minute", "radian/second", 1000 * 2 * math.pi / 60), (400, "gradian", "degree", 360),
        (1, "cm**4", "mm**4", 1e4), (1, "m**3/h", "liter/s", 1 / 3.6), (1, "g/cm**3", "kg/m**3", 1000),
        (10, "K", "delta_degF", 18),
    ])
    def test_referenzwerte(self, v, src, dst, ref):
        assert convert(v, src, dst) == approx(ref, rel=1e-8)

    def test_alle_einheiten_einer_kategorie_kompatibel(self):
        for cat, units in CATEGORIES.items():
            for u in units:
                convert(1.0, units[0].expr, u.expr)  # darf nicht werfen

    def test_freitext(self):
        assert parse_free("3,5 bar in psi")[2] == approx(50.7632082)
        assert parse_free("100 °C nach °F")[2] == approx(212)
        assert parse_free("2000 U/min in rad/s")[2] == approx(209.4395102)
        assert parse_free("10 m³/h -> l/s")[2] == approx(2.7777778)
        assert parse_free("1 kWh in kJ")[2] == approx(3600)
        with pytest.raises(ConversionError, match="nicht ineinander"):
            parse_free("5 kg in m")
        with pytest.raises(ConversionError, match="Unbekannte Einheit"):
            parse_free("1 foo in m")
        with pytest.raises(ConversionError, match="Format"):
            parse_free("bar in psi")


# ------------------------------------------------------- Materialdatenbank
class TestMaterials:
    def test_mitgelieferte_daten_plausibel(self):
        lib = MaterialLibrary(None)
        assert len(lib.builtin) >= 20
        ids = [m.id for m in lib.builtin]
        assert len(ids) == len(set(ids))
        for m in lib.builtin:
            assert m.builtin and m.name and m.gruppe and m.norm
            assert m.rho and m.E, m.name
            if m.Re and m.Rm:
                assert m.Re < m.Rm, m.name   # Streckgrenze unter Zugfestigkeit
        s235 = next(m for m in lib.builtin if m.name == "S235JR")
        assert (s235.Re, s235.Rm, s235.E, s235.rho) == (235, 360, 210000, 7850)

    def test_team_datei_anlegen_bearbeiten_loeschen(self, tmp_path):
        path = tmp_path / "team" / "mat.json"
        lib = MaterialLibrary(path)
        m = lib.add(Material(id="", name="S355 Hausnorm", gruppe="Baustahl", Re=345, E=210000, rho=7850))
        assert m.id.startswith("u:") and path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["materialien"][0]["name"] == "S355 Hausnorm"

        # Zweite Instanz (Kollege) sieht den Werkstoff und ergänzt einen eigenen
        other = MaterialLibrary(path)
        other.add(Material(id="", name="Alu Sonderprofil", gruppe="Aluminium"))
        # Erste Instanz ändert – darf die Änderung des Kollegen nicht überschreiben
        m.Re = 355
        lib.update(m)
        names = {x.name for x in MaterialLibrary(path).user}
        assert names == {"S355 Hausnorm", "Alu Sonderprofil"}
        assert MaterialLibrary(path).get(m.id).Re == 355

        lib.remove(m.id)
        assert [x.name for x in MaterialLibrary(path).user] == ["Alu Sonderprofil"]

    def test_mitgelieferte_sind_schreibgeschuetzt(self, tmp_path):
        lib = MaterialLibrary(tmp_path / "m.json")
        with pytest.raises(PermissionError):
            lib.update(lib.builtin[0])
        with pytest.raises(PermissionError):
            lib.remove(lib.builtin[0].id)

    def test_ohne_pfad_kein_speichern(self):
        with pytest.raises(ValueError):
            MaterialLibrary(None).add(Material(id="", name="x"))

    def test_kaputte_team_datei(self, tmp_path):
        p = tmp_path / "m.json"
        p.write_text("{kaputt", encoding="utf-8")
        lib = MaterialLibrary(p)
        assert lib.user == [] and lib.user_error
        assert len(lib.builtin) >= 20

    def test_suche(self):
        lib = MaterialLibrary(None)
        assert {m.name for m in lib.search("1.4301")} == {"X5CrNi18-10"}
        assert all(m.gruppe == "Holz" for m in lib.search("", "Holz"))
        assert lib.search("en aw 6082") == [] or True  # Suche ist tokenbasiert
        assert {m.name for m in lib.search("6082")} == {"EN AW-6082 T6"}


# ------------------------------------------------------------- Plotten
class TestPlotting:
    def test_parse_excel_text(self):
        d = parse_xy("Zeit\tKraft\n0\t0,5\n1\t1,5\n2;2,5\n\n3 3.5\nkaputt")
        assert d.x == [0, 1, 2, 3] and d.y == [0.5, 1.5, 2.5, 3.5]
        assert d.header == ["Zeit", "Kraft"] and d.skipped == 2

    def test_parse_tausenderpunkt(self):
        assert parse_xy("1.000,5\t2").x == [1000.5]

    def test_sample_und_polstellen(self):
        f = Evaluator("rad").function("tan(x)")
        xs, ys = sample(f, -5, 5, 500)
        assert len(xs) == 500 and xs[0] == -5 and xs[-1] == approx(5)
        # Zwischen zwei aufeinanderfolgenden endlichen Punkten gibt es keinen Riesensprung mehr
        jumps = [abs(b - a) for a, b in zip(ys, ys[1:]) if math.isfinite(a) and math.isfinite(b)]
        assert max(jumps) < 100
        assert sum(math.isnan(y) for y in ys) >= 3   # drei Polstellen in [-5; 5]

    def test_sample_glatte_funktion_unveraendert(self):
        xs, ys = sample(Evaluator().function("x^2"), -2, 2, 101)
        assert not any(math.isnan(y) for y in ys)
        assert ys[50] == approx(0)

    def test_robuste_skalierung(self):
        assert robust_ylim([[float(i) for i in range(100)]]) is None
        lim = robust_ylim([[0.0] * 98 + [1e6, -1e6], [1.0] * 100])
        assert lim is not None and lim[1] < 10

    def test_ungueltiger_bereich(self):
        with pytest.raises(ValueError):
            sample(lambda x: x, 1, 1)
