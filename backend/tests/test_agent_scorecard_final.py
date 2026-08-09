"""B33 — Temsilci karnesi yalnizca KESINLESMIS puanlari sayar.

## Neden bu test var

Urunun vaadi "AI onerir, kalite uzmani onaylar". Ama temsilci karnesi
(`/api/v1/agents`) yalnizca `status == done` filtreliyordu; `qa_state`
hic bakilmiyordu. Sonuc: inceleme kuyrugunda BEKLEYEN bir cagrinin AI
puani, kaliteci daha onaylamamisken temsilcinin ortalamasina giriyordu.

Bu, olculen gercekle celisir: oznel kriterlerde kappa 0.08-0.20 (bkz.
docs/KALITE-METODOLOJISI.md §4.1). Tam da bu yuzden o cagrilar kuyruga
dusuyor. Onlari karneye yazmak, "guvenilir olmadigini bildigimiz puani
temsilcinin karnesine yazdik" demektir.

Model `Call.score_is_final` ozelligiyle bu niyeti zaten belgeliyordu
("Puan liderlik tablosuna ve karneye girebilir mi?") ama API'de
uygulanmiyordu — yazili ama uygulanmayan bir kural.

## Kapsam kaybi neden yok

Risk kurali tetiklemeyen cagri puanlandigi anda `final` olur
(`qa_workflow.route_after_scoring`). Filtre yalnizca su an kuyrukta
bekleyenleri disarida birakir.
"""

from app.models import Call, CallStatus, Channel, QAState
from tests.conftest import TestingSession, token_for


def _cagri_ekle(tenant_id, agent_id, *, puan, durum):
    db = TestingSession()
    try:
        c = Call(tenant_id=tenant_id, filename=f"{durum.value}.wav", audio_path="",
                 channel=Channel.voice, agent_id=agent_id,
                 status=CallStatus.done, total_score=puan, qa_state=durum)
        db.add(c)
        db.commit()
        return c.id
    finally:
        db.close()


def _karne(client, seeded):
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    r = client.get("/api/v1/agents", headers=hdr)
    assert r.status_code == 200
    return {a["id"]: a for a in r.json()}[seeded["agent_a"]]


def test_kuyrukta_bekleyen_cagri_karneye_GIRMEZ(seeded, client):
    """Insan kuyrugundaki cagri temsilcinin ortalamasini degistirmemeli."""
    once = _karne(client, seeded)

    # Kaliteci onayi beklemede olan, cok dusuk puanli bir cagri
    _cagri_ekle(seeded["tenant_a"], seeded["agent_a"],
                puan=10.0, durum=QAState.human_queue)

    sonra = _karne(client, seeded)

    assert sonra["call_count"] == once["call_count"], (
        "Kuyrukta bekleyen cagri karneye girdi — kaliteci henuz onaylamadi")
    assert sonra["avg_score"] == once["avg_score"], (
        "Onaylanmamis AI puani temsilcinin ortalamasini dusurdu")


def test_kesinlesen_cagri_karneye_GIRER(seeded, client):
    """Onaylanan puan normal sekilde sayilmali — filtre fazla genis olmasin."""
    once = _karne(client, seeded)

    _cagri_ekle(seeded["tenant_a"], seeded["agent_a"],
                puan=40.0, durum=QAState.final)

    sonra = _karne(client, seeded)

    assert sonra["call_count"] == once["call_count"] + 1
    assert sonra["avg_score"] < once["avg_score"], "Kesinlesen dusuk puan ortalamayi dusurmeliydi"


def test_itiraz_incelemedeki_cagri_karneye_GIRMEZ(seeded, client):
    """Itiraz acilan puan yeniden tartisiliyor demektir; karnede sayilmaz."""
    once = _karne(client, seeded)

    _cagri_ekle(seeded["tenant_a"], seeded["agent_a"],
                puan=5.0, durum=QAState.appeal_review)

    sonra = _karne(client, seeded)

    assert sonra["call_count"] == once["call_count"]
