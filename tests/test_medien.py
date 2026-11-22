"""Mediendatenbank: Stoffmodelle und Einbindung in die Rechner."""

import pytest

from ingrechner.calculators.fluid.druckverlust_rohr import DruckverlustRohr
from ingrechner.calculators.heizung.waermemenge import Waermemenge
from ingrechner.calculators.pumpen.auslegung import PumpenAuslegung
from ingrechner.calculators.pumpen.npsh import NPSH
from ingrechner.core import medien
from ingrechner.core.model import Level
from ingrechner.core.stoffwerte import dampfdruck, stoffwerte

approx = pytest.approx


def warned(r, text):
    return any(m.level is Level.WARNUNG and text in m.text for m in r.messages)


class TestModelle:
    def test_ids_eindeutig_und_vollstaendig(self):
        ids = [m.id for m in medien.MEDIEN]
        assert len(ids) == len(set(ids))
        for need in ("wasser", "abwasser_zulauf", "klaerwasser", "klaerschlamm_5", "eg30", "pg40", "heizoel",
                     "vg46", "hlp46", "speiseoel", "speisefett", "luft", "stickstoff", "co2", "erdgas_h",
                     "erdgas_l", "klaergas_60", "fett_nlgi2"):
            assert need in ids

    def test_alle_fliessfaehigen_im_bereich(self):
        for m in medien.MEDIEN:
            if not m.fliessfaehig:
                continue
            for t in (m.t_min, (m.t_min + m.t_max) / 2, m.t_max):
                z = m.zustand(t)
                assert z.rho > 0 and z.mu > 0 and z.cp > 0, m.id

    def test_wasser_wie_stoffwerte(self):
        z = medien.medium("wasser").zustand(60)
        sw = stoffwerte("wasser", 60)
        assert z.rho == sw.rho and z.nu * 1e6 == approx(sw.nu) and z.pv == approx(dampfdruck(60) * 1000)

    @pytest.mark.parametrize("mid, rho_n", [("luft", 1.2930), ("co2", 1.977), ("stickstoff", 1.2505),
                                            ("erdgas_h", 0.77), ("erdgas_l", 0.82)])
    def test_normdichte(self, mid, rho_n):
        assert medien.medium(mid).normdichte() == approx(rho_n, rel=0.01)

    def test_gas_druck_und_realgas(self):
        co2 = medien.medium("co2")
        z1, z10 = co2.zustand(20, 1e5), co2.zustand(20, 10e5)
        assert z10.Z == approx(0.95, abs=0.01)                  # Literatur ≈ 0,95
        assert z10.rho / z1.rho == approx(10 * z1.Z / z10.Z)
        assert medien.medium("stickstoff").zustand(20).nu * 1e6 == approx(15.1, rel=0.03)
        assert medien.medium("luft").zustand(20).mu == approx(18.2e-6, rel=0.03)

    def test_walther(self):
        oel = medien.medium("vg46")
        assert oel.nu_mm2(40) == approx(46) and oel.nu_mm2(100) == approx(6.8)
        assert oel.nu_mm2(0) > oel.nu_mm2(20) > oel.nu_mm2(40)
        assert oel.zustand(15).rho == approx(875)

    def test_tabelle(self):
        z = medien.medium("eg30").zustand(20)
        assert z.mu == approx(2.0e-3) and z.rho == 1038 and z.cp == 3.73

    def test_schlamm_und_fett(self):
        s = medien.medium("klaerschlamm_5")
        assert not s.newtonsch and s.zustand(20).nu * 1e6 == approx(45)
        with pytest.raises(ValueError, match="nicht-newtonsch"):
            medien.medium("fett_nlgi2").zustand(20)

    def test_bereich(self):
        with pytest.raises(ValueError, match="45 … 120"):
            medien.medium("speisefett").zustand(20)


class TestRechner:
    def test_druckverlust_alte_auswahl(self):
        alt = DruckverlustRohr().run({"medium": "wasser_60"})
        neu = DruckverlustRohr().run({"medium": "wasser", "theta": 60})
        assert alt.ok and alt.value("dp") == approx(neu.value("dp"))

    def test_druckverlust_gas(self):
        r = DruckverlustRohr().run({"medium": "erdgas_h", "theta": 15, "p": 5, "Q": 100, "d": 50, "L": 200,
                                    "dz": 0})
        z = medien.medium("erdgas_h").zustand(15, 5e5)
        assert r.ok
        dyn = z.rho * r.value("v") ** 2 / 2
        assert r.value("dp_r") == approx(r.value("lam") * 200 / 0.05 * dyn / 1e5)
        r = DruckverlustRohr().run({"medium": "luft", "theta": 20, "p": 1.01325, "Q": 400, "d": 50, "L": 200})
        assert warned(r, "inkompressibler")

    def test_auslegung_glykol(self):
        r = PumpenAuslegung().run({"medium": "eg30", "theta": 0, "quelle": "waerme", "P": 50, "dT": 6})
        z = medien.medium("eg30").zustand(0)
        assert r.value("V") == approx(50 / (z.rho * z.cp * 6) * 3600)
        assert r.value("rho") == approx(z.rho)

    def test_auslegung_schlamm_warnt(self):
        r = PumpenAuslegung().run({"medium": "klaerschlamm_5", "theta": 15, "quelle": "volumen", "V": 30,
                                   "rohr": "st:DN 100"})
        assert r.ok and warned(r, "Nicht-newtonsches")

    def test_npsh_oel_und_glykol(self):
        r = NPSH().run({"medium": "vg46", "theta": 40})
        assert r.ok and "tmax" not in {v.key for v in r.values}
        r = NPSH().run({"medium": "eg30", "theta": 20, "hz": 1})
        assert r.ok and 20 < r.value("tmax") <= 100

    def test_waermemenge_glykol(self):
        r = Waermemenge().run({"medium": "pg30", "modus": "volumenstrom", "Q": 30, "dt": 6, "tvl": 12})
        z = medien.medium("pg30").zustand(9)
        assert r.value("V") == approx(30 / (z.rho * z.cp * 6) * 3600, rel=1e-6)
