"""Phase 3: Protokolle, Vorlagen, PDF, Audio und Spracherkennung."""

import json
import math
import os
import wave

import numpy as np
import pytest

from ingrechner.core import speech
from ingrechner.core.audio import SAMPLE_RATE, load_audio, pcm_to_float, resample, save_wav
from ingrechner.core.protocol_report import build_protocol_pdf
from ingrechner.core.protocols import (BLOCK_TYPES, Block, Protocol, Template, TemplateLibrary, continue_from,
                                       next_number)


@pytest.fixture
def lib():
    return TemplateLibrary(None)


def _filled(lib) -> Protocol:
    p = Protocol.new(lib.get("b:baubesprechung"), "BB-07")
    p.values.update(projekt="Werkhalle 3", ort="Container", datum="21.11.2026", protokoll="A. Beispiel")
    p.values["teilnehmer"] = [{"name": "Max Muster", "firma": "Bauleitung", "kuerzel": "MM", "status": "anwesend"},
                              {"name": "Bauherr", "firma": "Immo", "kuerzel": "BH", "status": "Verteiler"},
                              {"name": "Hans", "firma": "Rohbau", "kuerzel": "HB", "status": "entschuldigt"}]
    p.values["top"][2]["text"] = "Betonage am Montag.\nAbnahme am Freitag."
    p.values["aufgaben"] = [
        {"nr": "", "art": "A", "aufgabe": "Pläne freigeben", "verantwortlich": "MM", "termin": "27.11.", "status": "offen"},
        {"nr": "", "art": "B", "aufgabe": "Betonage 30.11.", "verantwortlich": "HB", "termin": "", "status": "offen"},
        {"nr": "", "art": "A", "aufgabe": "Zufahrt räumen", "verantwortlich": "HB", "termin": "", "status": "erledigt"},
        {"nr": "", "art": "F", "aufgabe": "Beton C30/37", "verantwortlich": "", "termin": "", "status": "in Arbeit"},
    ]
    return p


# ------------------------------------------------------------- Vorlagen
class TestTemplates:
    def test_mitgelieferte_vorlagen_gueltig(self, lib):
        assert [t.name for t in lib.builtin][:3] == ["Baubesprechung", "Jour fixe / Teambesprechung",
                                                    "Gesprächs- / Telefonnotiz"]
        for t in lib.builtin:
            assert t.builtin and t.blocks
            assert all(b.typ in BLOCK_TYPES for b in t.blocks)

    def test_doppelte_schluessel_abgelehnt(self):
        with pytest.raises(ValueError, match="doppelte"):
            Template.from_dict({"id": "x", "name": "x", "blocks": [
                {"key": "a", "typ": "feld", "titel": "A"}, {"key": "a", "typ": "text", "titel": "B"}]})

    def test_unbekannter_typ_abgelehnt(self):
        with pytest.raises(ValueError, match="Bausteintyp"):
            Block.from_dict({"key": "a", "typ": "video", "titel": "A"})

    def test_team_vorlagen(self, tmp_path):
        path = tmp_path / "team" / "vorlagen.json"
        a = TemplateLibrary(path)
        src = a.get("b:jourfixe")
        created = a.add(Template.from_dict({**src.to_dict(), "id": "", "name": "Jour fixe Statik"}))
        assert created.id.startswith("u:") and path.exists()
        b = TemplateLibrary(path)               # Kollege
        b.add(Template(id="", name="Abnahme", blocks=[Block("d", "datum", "Datum")]))
        created.blocks.append(Block(created.new_block_key("text"), "text", "Bemerkungen"))
        a.update(created)                        # darf Kollegen-Vorlage nicht überschreiben
        names = {t.name for t in TemplateLibrary(path).user}
        assert names == {"Jour fixe Statik", "Abnahme"}
        assert TemplateLibrary(path).get(created.id).blocks[-1].titel == "Bemerkungen"
        a.remove(created.id)
        assert [t.name for t in TemplateLibrary(path).user] == ["Abnahme"]
        with pytest.raises(PermissionError):
            a.update(a.builtin[0])

    def test_neuer_bausteinschluessel(self, lib):
        t = lib.get("b:gespraechsnotiz")
        assert t.new_block_key("text") == "text1"
        t.blocks.append(Block("text1", "text", "x"))
        assert t.new_block_key("text") == "text2"


# ------------------------------------------------------------ Protokolle
class TestProtocols:
    def test_neu_mit_vorgaben(self, lib):
        p = Protocol.new(lib.get("b:baubesprechung"))
        assert [t["titel"] for t in p.value("top")][0] == "Begrüßung und Feststellung der Teilnehmer"
        assert len(p.value("datum")) == 10 and p.value("teilnehmer") == []

    def test_vorlage_wird_kopiert(self, lib):
        tpl = lib.get("b:baubesprechung")
        p = Protocol.new(tpl)
        p.template.blocks[0].titel = "geändert"
        assert tpl.blocks[0].titel == "Projekt"

    def test_aufgabennummern(self, lib):
        p = _filled(lib)
        p.values["aufgaben"][1]["nr"] = "BB-07.1"   # schon vergeben -> wird übersprungen
        p.renumber_tasks()
        assert [t["nr"] for t in p.values["aufgaben"]] == ["BB-07.2", "BB-07.1", "BB-07.3", "BB-07.4"]

    def test_speichern_laden(self, lib, tmp_path):
        p = _filled(lib)
        path = p.save(tmp_path / "prot")
        assert path.name == "prot.irpk"
        q = Protocol.load(path)
        assert q.title == "Protokoll Baubesprechung Nr. BB-07"
        assert q.value("top")[2]["text"] == "Betonage am Montag.\nAbnahme am Freitag."
        assert q.subject == "Werkhalle 3"
        assert q.suggested_filename() == "2026-11-21 Protokoll Baubesprechung Nr BB-07 Werkhalle 3"

    def test_fremde_datei(self, tmp_path):
        f = tmp_path / "x.irpk"
        f.write_text(json.dumps({"format": "etwas"}), encoding="utf-8")
        with pytest.raises(ValueError):
            Protocol.load(f)

    @pytest.mark.parametrize("nr, nxt", [("1", "2"), ("9", "10"), ("BB-07", "BB-08"), ("2026/09", "2026/10"),
                                         ("BB-7a", "BB-8a"), ("A", "A-2"), ("", "1")])
    def test_naechste_nummer(self, nr, nxt):
        assert next_number(nr) == nxt

    def test_folgeprotokoll(self, lib):
        p = _filled(lib)
        p.renumber_tasks()
        n = continue_from(p)
        assert n.nummer == "BB-08"
        assert n.value("projekt") == "Werkhalle 3" and n.value("protokoll") == "A. Beispiel"
        # Offene Aufgaben/Festlegungen übernommen, Beschlüsse und Erledigtes nicht
        assert [t["aufgabe"] for t in n.value("aufgaben")] == ["Pläne freigeben", "Beton C30/37"]
        assert all(t["herkunft"] == "Prot. BB-07" for t in n.value("aufgaben"))
        # Inhalte der TOPs beginnen leer, Teilnehmer wieder „anwesend“ (Verteiler bleibt)
        assert all(not t["text"] for t in n.value("top"))
        assert [x["status"] for x in n.value("teilnehmer")] == ["anwesend", "Verteiler", "anwesend"]
        # Herkunft bleibt über mehrere Folgeprotokolle erhalten
        assert continue_from(n).value("aufgaben")[0]["herkunft"] == "Prot. BB-07"

    def test_pdf(self, lib, tmp_path):
        for tpl in lib.all():
            p = Protocol.new(tpl, "3")
            if tpl.id == "b:baubesprechung":
                p = _filled(lib)
            data = build_protocol_pdf(tmp_path / f"{tpl.name[:5]}.pdf", p).read_bytes()
            assert data.startswith(b"%PDF") and len(data) > 3000


# ----------------------------------------------------------------- Audio
class TestAudio:
    def test_pcm_und_resampling(self):
        tone = (np.sin(np.linspace(0, 2 * np.pi * 440, 48000)) * 0.5).astype(np.float32)
        stereo = np.repeat((tone * 32767).astype("<i2"), 2)
        mono = pcm_to_float(stereo.tobytes(), 2, 2)
        assert mono.size == 48000 and abs(mono.max() - 0.5) < 1e-3
        r = resample(mono, 48000)
        assert r.size == 16000 and abs(r.max() - 0.5) < 1e-2

    def test_wav_roundtrip(self, tmp_path):
        x = np.linspace(-0.5, 0.5, 8000, dtype=np.float32)
        save_wav(tmp_path / "a.wav", x, 8000)
        y = load_audio(tmp_path / "a.wav")
        assert y.size == 16000 and y.dtype == np.float32
        assert abs(y[0] + 0.5) < 1e-3 and abs(y[-1] - 0.5) < 1e-3

    def test_wav_8bit(self, tmp_path):
        with wave.open(str(tmp_path / "b.wav"), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(1)
            wf.setframerate(16000)
            wf.writeframes(bytes([128, 255, 0]))
        y = load_audio(tmp_path / "b.wav")
        assert y[0] == 0 and y[1] > 0.99 and y[2] == -1

    def test_andere_formate_ueber_pyav(self, tmp_path):
        av = pytest.importorskip("av")
        path = tmp_path / "t.flac"
        tone = (np.sin(np.linspace(0, 2 * np.pi * 300, 44100)) * 0.3).astype(np.float32)
        with av.open(str(path), "w") as out:
            st = out.add_stream("flac", rate=44100, layout="mono")
            pcm = (tone * 32767).astype(np.int16).reshape(1, -1)
            frame = av.AudioFrame.from_ndarray(pcm, format="s16", layout="mono")
            frame.sample_rate = 44100
            for pkt in st.encode(frame):
                out.mux(pkt)
            for pkt in st.encode(None):
                out.mux(pkt)
        y = load_audio(path)
        assert abs(y.size - SAMPLE_RATE) < 2000
        assert 0.2 < np.abs(y).max() < 0.4


# -------------------------------------------------------- Spracherkennung
MODEL = os.environ.get("INGRECHNER_TEST_MODEL", "")


class TestSpeech:
    def test_prompt_aus_fachbegriffen(self):
        assert speech.build_prompt("") is None
        assert speech.build_prompt("Betonage,  Statik\nVDE") == "Besprechungsprotokoll. Fachbegriffe: Betonage, Statik, VDE."

    def test_tidy(self):
        assert speech.tidy("  die  betonage , am montag . ") == "Die betonage, am montag."

    def test_modell_pruefung(self, tmp_path):
        assert not speech.is_model_ready(tmp_path)
        for f in speech.MODEL_FILES:
            (tmp_path / f).write_text("x")
        assert speech.is_model_ready(tmp_path)
        assert speech.model_dir(tmp_path, "small").name == "faster-whisper-small"

    def test_fehlendes_modell_klare_meldung(self, tmp_path):
        if not speech.available():
            pytest.skip("faster-whisper nicht installiert")
        with pytest.raises(speech.SpeechError, match="Kein Sprachmodell"):
            speech.SpeechEngine(tmp_path)

    @pytest.mark.skipif(not MODEL, reason="INGRECHNER_TEST_MODEL (Pfad zu einem Whisper-Modell) nicht gesetzt")
    def test_erkennung_end_to_end(self, tmp_path):
        import shutil
        import subprocess

        if not shutil.which("espeak-ng"):
            pytest.skip("espeak-ng für Testsprache nicht installiert")
        wav = tmp_path / "s.wav"
        subprocess.run(["espeak-ng", "-v", "de", "-s", "140", "-w", str(wav),
                        "Die Betonage der Bodenplatte ist am Montag."], check=True)
        text = speech.SpeechEngine(MODEL).transcribe(wav, glossary="Betonage, Bodenplatte").lower()
        assert "betonage" in text and "montag" in text
        assert math.isclose(len(load_audio(wav)) / SAMPLE_RATE, 3, abs_tol=2.5)
