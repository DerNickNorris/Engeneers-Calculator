"""Phase 4: weitere Fachrechner – geprüft gegen Normtabellen und Handrechnungen."""

import math

import pytest

from ingrechner.calculators.elektro.abschaltbedingung import Abschaltbedingung
from ingrechner.calculators.elektro.kompensation import Kompensation
from ingrechner.calculators.fluid.u_wert import UWert
from ingrechner.calculators.fluid.waermeleistung_rohr import WaermeleistungRohr, dn_vorschlag
from ingrechner.calculators.maschinenbau.kesselformel import Kesselformel
from ingrechner.calculators.maschinenbau.schraube_vdi2230 import Schraube, gewinde_geometrie
from ingrechner.calculators.maschinenbau.welle_torsion import WelleTorsion
from ingrechner.calculators.statik.knicken_en1993 import KnickenEN1993, chi
from ingrechner.calculators.statik.kragtraeger import Kragtraeger
from ingrechner.core.model import Level

approx = pytest.approx


def warned(result, text):
    return any(m.level is Level.WARNUNG and text in m.text for m in result.messages)


# ------------------------------------------------------------- Schraube
class TestSchraube:
    @pytest.mark.parametrize("g, d2, d3, As", [
        ("M6", 5.350, 4.773, 20.1), ("M10", 9.026, 8.160, 58.0), ("M16", 14.701, 13.546, 157),
        ("M24", 22.051, 20.319, 353),
    ])
    def test_gewinde_din13(self, g, d2, d3, As):
        from ingrechner.calculators.maschinenbau.schraube_vdi2230 import GEWINDE

        d, P, *_ = GEWINDE[g]
        r = gewinde_geometrie(d, P)
        assert r[0] == approx(d2, abs=0.002) and r[1] == approx(d3, abs=0.002)
        assert r[2] == approx(As, rel=0.005)

    # VDI 2230 Blatt 1, Tabelle A1 (Schaftschrauben, μ_G = μ_K = 0,12, ν = 0,9)
    @pytest.mark.parametrize("g, kl, fm, ma", [
        ("M8", "8.8", 18.6, 24.6), ("M10", "8.8", 29.6, 48), ("M12", "8.8", 43.0, 84),
        ("M16", "8.8", 81.3, 206), ("M10", "10.9", 43.6, 71), ("M12", "12.9", 74.3, 144),
    ])
    def test_vdi_tabelle(self, g, kl, fm, ma):
        r = Schraube().run({"gewinde": g, "klasse": kl})
        assert r.value("FM") == approx(fm, rel=0.015)
        assert r.value("MA") == approx(ma, rel=0.03)

    def test_reibung_erhoeht_moment(self):
        lo = Schraube().run({"mu_g": 0.08, "mu_k": 0.08})
        hi = Schraube().run({"mu_g": 0.16, "mu_k": 0.16})
        assert hi.value("MA") > lo.value("MA") and hi.value("FM") < lo.value("FM")

    def test_streckgrenze_ueber_m16(self):
        assert Schraube().run({"gewinde": "M16"}).value("Rp") == 640
        assert Schraube().run({"gewinde": "M20"}).value("Rp") == 660


# ---------------------------------------------------------------- Welle
class TestWelle:
    def test_vollwelle(self):
        r = WelleTorsion().run({})
        T = 10_000 / (2 * math.pi * 1450 / 60)
        assert r.value("T") == approx(T)
        assert r.value("tau") == approx(T * 1000 / (math.pi * 25**3 / 16))
        assert r.value("d_erf") == approx((16 * T * 1000 / (math.pi * 30)) ** (1 / 3))
        phi = T * 1000 * 500 / (81000 * math.pi * 25**4 / 32)
        assert r.value("phi") == approx(math.degrees(phi))

    def test_hohlwelle(self):
        r = WelleTorsion().run({"querschnitt": "hohl", "d": 40, "di": 30})
        T = r.value("T")
        assert r.value("tau") == approx(T * 1000 * 16 * 40 / (math.pi * (40**4 - 30**4)))
        assert not WelleTorsion().run({"querschnitt": "hohl", "d": 30, "di": 30}).ok


# --------------------------------------------------------- Kesselformel
class TestKessel:
    def test_ad2000_b1(self):
        r = Kesselformel().run({"p": 10, "Da": 168.3, "s": 4.5, "K": 235, "S": 1.5, "v": 1, "c": 1})
        s0 = 168.3 * 10 / (20 * 235 / 1.5 * 1 + 10)
        assert r.value("s_erf") == approx(s0 + 1)
        assert r.value("sig_t") == approx(1.0 * (168.3 - 3.5) / (2 * 3.5))
        assert r.value("sig_a") == approx(r.value("sig_t") / 2)

    def test_p_zul_konsistent(self):
        """Mit p = p_zul muss die Ausnutzung genau 100 % sein."""
        p_zul = Kesselformel().run({}).value("p_zul")
        assert Kesselformel().run({"p": p_zul}).value("eta") == approx(100)

    def test_zu_duenn(self):
        assert warned(Kesselformel().run({"p": 200, "s": 3}), "zu gering")


# -------------------------------------------------------------- Knicken
class TestKnicken:
    # EN 1993-1-1, Tabelle der Abminderungsbeiwerte χ (bzw. Gl. 6.49)
    @pytest.mark.parametrize("lam, kl, ref", [
        (0.2, 0.34, 1.0), (0.5, 0.21, 0.9243), (1.0, 0.34, 0.5970), (1.0, 0.49, 0.5399),
        (1.5, 0.13, 0.3954), (2.0, 0.49, 0.1962), (1.2, 0.76, 0.3762),
    ])
    def test_chi(self, lam, kl, ref):
        assert chi(lam, kl) == approx(ref, abs=1e-4)

    def test_ipe200_z_achse(self):
        r = KnickenEN1993().run({"N": 100, "L": 3000, "fall": "2", "A": 28.5, "I": 142, "kl": "b",
                                 "fy": 235, "gM1": 1.1})
        Ncr = math.pi**2 * 210000 * 142e4 / 3000**2 / 1000
        assert r.value("Ncr") == approx(Ncr)
        lb = math.sqrt(28.5e2 * 235 / 1000 / Ncr)
        assert r.value("lam_bar") == approx(lb)
        assert r.value("Nb") == approx(chi(lb, 0.34) * 28.5e2 * 235 / 1000 / 1.1)

    def test_eulerfaelle(self):
        n2 = KnickenEN1993().run({"fall": "2"}).value("Ncr")
        assert KnickenEN1993().run({"fall": "1"}).value("Ncr") == approx(n2 / 4)
        assert KnickenEN1993().run({"fall": "4"}).value("Ncr") == approx(n2 * 4)

    def test_warnung(self):
        assert warned(KnickenEN1993().run({"N": 1000}), "NICHT erfüllt")


# ----------------------------------------------------------- Kragträger
class TestKragtraeger:
    def test_superposition(self):
        r = Kragtraeger().run({"L": 2000, "F": 4, "q": 3, "I": 1000, "W": 100, "E": 210000})
        assert r.value("M") == approx(4 * 2 + 3 * 2**2 / 2)
        assert r.value("V") == approx(4 + 3 * 2)
        EI = 210000 * 1000e4
        w = 4000 * 2000**3 / (3 * EI) + 3 * 2000**4 / (8 * EI)
        assert r.value("w") == approx(w)
        assert r.value("sigma") == approx(14e6 / 100e3)

    def test_ohne_last(self):
        assert not Kragtraeger().run({"F": 0, "q": 0}).ok


# --------------------------------------------------------- Kompensation
class TestKompensation:
    def test_drehstrom_dreieck(self):
        r = Kompensation().run({"P": 100, "cos1": 0.7, "cos2": 0.95, "U": 400, "f": 50})
        qc = 100 * (math.tan(math.acos(0.7)) - math.tan(math.acos(0.95)))
        assert r.value("Qc") == approx(qc)          # 69,15 kvar
        assert r.value("C") == approx(qc * 1e3 / (3 * 2 * math.pi * 50 * 400**2) * 1e6)
        assert r.value("I1") == approx(100e3 / 0.7 / (math.sqrt(3) * 400))

    def test_stern_dreifache_kapazitaet(self):
        d = Kompensation().run({"schaltung": "dreieck"}).value("C")
        s = Kompensation().run({"schaltung": "stern"}).value("C")
        assert s == approx(3 * d)

    def test_ziel_kleiner_als_ist(self):
        assert not Kompensation().run({"cos1": 0.9, "cos2": 0.8}).ok


# ------------------------------------------------------ Abschaltbedingung
class TestAbschaltung:
    def test_b16(self):
        r = Abschaltbedingung().run({})
        rho = 0.017241 * (1 + 0.00393 * 60)
        zs = 0.3 + 2 * rho * 30 / 1.5
        assert r.value("Zs") == approx(zs)
        assert r.value("Ik") == approx(0.95 * 230 / zs)
        assert r.value("Ia") == 80
        assert r.value("Lmax") == approx((0.95 * 230 / 80 - 0.3) * 1.5 / (2 * rho))

    def test_l_max_ist_grenze(self):
        lmax = Abschaltbedingung().run({"char": "C"}).value("Lmax")
        assert Abschaltbedingung().run({"char": "C", "L": lmax}).value("reserve") == approx(1.0)
        assert warned(Abschaltbedingung().run({"char": "C", "L": lmax * 1.05}), "NICHT erfüllt")


# --------------------------------------------------------------- U-Wert
class TestUWert:
    def test_wand(self):
        r = UWert().run({})
        rt = 0.13 + 0.015 / 0.70 + 0.175 / 0.99 + 0.14 / 0.035 + 0.010 / 0.87 + 0.04
        assert r.value("U") == approx(1 / rt)
        assert r.value("phi") == approx(1 / rt * 10 * 32)

    def test_richtung_und_erdreich(self):
        base = {"d1": 200, "l1": 1.0, "d2": 0, "d3": 0, "d4": 0}
        assert UWert().run({**base, "richtung": "aufwaerts"}).value("RT") == approx(0.10 + 0.2 + 0.04)
        assert UWert().run({**base, "richtung": "abwaerts", "aussen": "erdreich"}).value("RT") == approx(0.17 + 0.2)
        assert UWert().run({**base, "aussen": "unbeheizt"}).value("RT") == approx(0.13 + 0.2 + 0.13)

    def test_schimmelkriterium(self):
        r = UWert().run({"d1": 240, "l1": 0.99, "d2": 0, "d3": 0, "d4": 0})   # ungedämmte KS-Wand
        assert r.value("frsi") < 0.70 and warned(r, "Schimmel")

    def test_keine_schicht(self):
        assert not UWert().run({f"d{i}": 0 for i in range(1, 7)}).ok


# ------------------------------------------------------- Wärmeleistung
class TestWaerme:
    def test_massenstrom(self):
        r = WaermeleistungRohr().run({"Q": 25, "dt": 20})
        m = 25 / (4.18 * 20) * 3600
        assert r.value("m") == approx(m)
        assert r.value("V") == approx(m / 992.2)
        assert r.value("dmin") == approx(math.sqrt(4 * m / 992.2 / 3600 / (math.pi * 0.8)) * 1000)

    def test_dn_vorschlag(self):
        assert dn_vorschlag(21.9) == "DN 25"
        assert dn_vorschlag(16.1) == "DN 15"
        assert dn_vorschlag(200) is None

    def test_gewaehlte_nennweite(self):
        r = WaermeleistungRohr().run({"dn": "DN 15"})
        assert r.value("v_ist") > 1.4 and warned(r, "Pa/m")
