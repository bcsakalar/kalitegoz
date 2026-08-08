"""SMTP zamanlanmis e-posta raporu testleri (Dalga 7).

Gercek SMTP sunucusu GEREKMEZ: yapilandirilmamis halde 'uretildi ama
gonderilmedi' yolu ve rapor Excel'inin gecerli uretildigi test edilir.
"""

from app.services import email_reports
from tests.conftest import TestingSession


class TestBuildReport:
    def test_xlsx_is_valid_workbook(self, seeded):
        db = TestingSession()
        try:
            data = email_reports.build_team_xlsx(db, seeded["tenant_a"])
            # Excel dosyalari 'PK' (zip) ile baslar
            assert data[:2] == b"PK"
            assert len(data) > 500
        finally:
            db.close()


class TestSendReport:
    def test_not_sent_without_smtp(self, seeded, monkeypatch):
        monkeypatch.setattr("app.config.settings.smtp_host", "")
        db = TestingSession()
        try:
            r = email_reports.send_report(db, seeded["tenant_a"], "Test A", ["x@y.com"])
            assert r["generated"] is True
            assert r["sent"] is False
            assert "SMTP" in r["reason"]
        finally:
            db.close()

    def test_not_sent_without_recipients(self, seeded, monkeypatch):
        monkeypatch.setattr("app.config.settings.smtp_host", "smtp.example.com")
        db = TestingSession()
        try:
            r = email_reports.send_report(db, seeded["tenant_a"], "Test A", [])
            assert r["sent"] is False
            assert "Alici" in r["reason"]
        finally:
            db.close()

    def test_smtp_error_does_not_raise(self, seeded, monkeypatch):
        """SMTP baglanti hatasi rapor gorevini dusurmemeli (best-effort)."""
        monkeypatch.setattr("app.config.settings.smtp_host", "nonexistent.invalid")
        monkeypatch.setattr("app.config.settings.smtp_port", 2525)
        db = TestingSession()
        try:
            r = email_reports.send_report(db, seeded["tenant_a"], "Test A", ["x@y.com"])
            assert r["sent"] is False
            assert "SMTP hatasi" in r["reason"]  # istisna yutuldu
        finally:
            db.close()

    def test_send_all_tenants_returns_per_tenant(self, seeded, monkeypatch):
        monkeypatch.setattr("app.config.settings.smtp_host", "")
        db = TestingSession()
        try:
            out = email_reports.send_all_tenants(db)
            assert len(out) >= 1
            assert all("generated" in r for r in out.values())
        finally:
            db.close()


class TestSmtpConfig:
    def test_recipient_list_parsing(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.report_recipients", "a@x.com, b@y.com ,")
        from app.config import settings
        assert settings.report_recipient_list == ["a@x.com", "b@y.com"]
