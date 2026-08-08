"""Agent assist motoru (6) + vision sema (5) testleri.

Vision'in LLM cagrisi test edilmez (model gerektirir); yalnizca sema
normalize + assist motorunun deterministik mantigi dogrulanir.
"""

from app.services import assist
from app.services.schemas_vision import VisionResult
from tests.conftest import TestingSession


class TestAssistEngine:
    def test_compliance_reminder_when_disclosure_missing(self, seeded):
        db = TestingSession()
        try:
            # KVKK aciklamasi YOK -> hatirlatma cikmali
            out = assist.suggest(db, seeded["tenant_a"], "Merhaba, buyurun nasil yardimci olayim?")
            kinds = {s["kind"] for s in out}
            assert "compliance" in kinds
        finally:
            db.close()

    def test_no_compliance_reminder_when_satisfied(self, seeded):
        db = TestingSession()
        try:
            text = ("Gorusmemiz kayit altina alinmaktadir, kisisel verileriniz KVKK "
                    "kapsaminda islenmektedir. Buyurun.")
            out = assist.suggest(db, seeded["tenant_a"], text)
            assert all(s["kind"] != "compliance" for s in out)
        finally:
            db.close()

    def test_next_action_hint_on_cancellation(self, seeded):
        db = TestingSession()
        try:
            out = assist.suggest(db, seeded["tenant_a"],
                                 "kayit altina KVKK ... musteri hattini iptal etmek istiyorum dedi")
            assert any(s["kind"] == "next_action" for s in out)
        finally:
            db.close()

    def test_critical_sorted_first(self, seeded):
        db = TestingSession()
        try:
            # KVKK eksik (kritik) + iptal (bilgi) birlikte
            out = assist.suggest(db, seeded["tenant_a"], "iptal etmek istiyorum")
            assert out[0]["severity"] == "kritik"
        finally:
            db.close()

    def test_empty_knowledge_does_not_crash(self, seeded):
        db = TestingSession()
        try:
            out = assist.suggest(db, seeded["tenant_a"], "kayit altina KVKK kisisel veri tamam")
            assert isinstance(out, list)  # bilgi bankasi bos olsa da patlamaz
        finally:
            db.close()


class TestVisionSchema:
    def test_normalizes_doc_type(self):
        r = VisionResult(belge_turu="FATURA", kvkk_riski="YUKSEK")
        assert r.belge_turu == "fatura"
        assert r.kvkk_riski == "yuksek"

    def test_unknown_doc_type_falls_back(self):
        assert VisionResult(belge_turu="uçak bileti").belge_turu == "diger"

    def test_invalid_risk_falls_back(self):
        assert VisionResult(kvkk_riski="belirsiz").kvkk_riski == "dusuk"

    def test_sensitive_data_list_normalized(self):
        r = VisionResult(hassas_veri=["Kart_No", "  TCKN ", ""])
        assert r.hassas_veri == ["kart_no", "tckn"]

    def test_missing_fields_defaults(self):
        r = VisionResult()
        assert r.belge_turu == "diger" and r.kvkk_riski == "dusuk" and r.hassas_veri == []
