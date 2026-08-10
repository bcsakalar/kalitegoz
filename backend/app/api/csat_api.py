"""Gerçek müşteri anketi (CSAT) girişi ve korelasyon raporu.

Piyasa analizi §5.1: ürünün en büyük dış doğrulama boşluğu buydu — kalite
puanının müşterinin gerçekten ne hissettiğiyle ilgisi hiç ölçülmüyordu.

## Giriş yolları

- `POST /api/v1/csat/{call_id}` — tek çağrı (panelden veya entegrasyondan)
- `POST /api/v1/csat/bulk` — toplu (santral/CRM anket dökümü)
- `GET  /api/v1/csat/correlation` — kalite puanı ↔ CSAT ilişkisi
- `GET  /api/v1/csat/distribution` — kalite bandı başına ortalama CSAT

Toplu girişte **kısmi başarı** döner: 100 kaydın 3'ü hatalıysa 97'si yazılır
ve hangi 3'ünün neden reddedildiği tek tek bildirilir. Hepsini birden
reddetmek, entegrasyonu yazan tarafı tek tek deneme yanılmaya mahkûm eder.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_staff
from ..models import Call
from ..services import audit, csat

router = APIRouter(prefix="/api/v1/csat", tags=["csat"])

# NOT — YOL SIRASI ONEMLI: `/bulk` ve `/correlation` gibi sabit yollar,
# `/{call_id}` yakalayicisindan ONCE tanimlanmalidir. Aksi halde FastAPI
# `/csat/bulk` istegini `call_id="bulk"` diye eslestirir, int'e ceviremez ve
# 422 doner. (Bizzat yasandi.)


class CSATIn(BaseModel):
    puan: float = Field(..., description="1-5 arası müşteri memnuniyet puanı")
    kaynak: str = Field("manuel", description="anket | manuel | ice_aktarma")
    yorum: str = ""


class CSATToplu(BaseModel):
    kayitlar: list[dict] = Field(
        ..., description='[{"call_id": 12, "puan": 4, "kaynak": "anket", "yorum": ""}]')


def _cagri(db: Session, call_id: int, tenant_id: int) -> Call:
    c = db.query(Call).filter(Call.id == call_id, Call.tenant_id == tenant_id).first()
    if c is None:
        raise HTTPException(404, "Çağrı bulunamadı")
    return c


@router.post("/bulk")
def csat_toplu(body: CSATToplu, request: Request,
               db: Session = Depends(get_db),
               user: CurrentUser = Depends(require_staff)):
    """Toplu CSAT girişi. Kısmi başarı döner — hatalı satır diğerlerini düşürmez."""
    yazilan, hatalar = 0, []
    for i, kayit in enumerate(body.kayitlar):
        cid = kayit.get("call_id")
        try:
            c = db.query(Call).filter(
                Call.id == cid, Call.tenant_id == user.tenant_id).first()
            if c is None:
                hatalar.append({"satir": i, "call_id": cid, "hata": "Çağrı bulunamadı"})
                continue
            csat.kaydet(db, c, kayit.get("puan"),
                        kaynak=kayit.get("kaynak", "ice_aktarma"),
                        yorum=kayit.get("yorum", ""))
            yazilan += 1
        except csat.CSATHatasi as exc:
            hatalar.append({"satir": i, "call_id": cid, "hata": str(exc)})
        except Exception as exc:  # noqa: BLE001
            hatalar.append({"satir": i, "call_id": cid, "hata": f"beklenmeyen: {exc}"})

    db.commit()
    audit.log(db, action="csat_bulk", tenant_id=user.tenant_id, user_id=user.id,
              detail={"yazilan": yazilan, "hatali": len(hatalar)},
              ip=request.client.host if request.client else "")
    db.commit()
    return {"yazilan": yazilan, "hatali": len(hatalar), "hatalar": hatalar[:50]}


@router.post("/{call_id}")
def csat_yaz(call_id: int, body: CSATIn, request: Request,
             db: Session = Depends(get_db),
             user: CurrentUser = Depends(require_staff)):
    c = _cagri(db, call_id, user.tenant_id)
    try:
        csat.kaydet(db, c, body.puan, kaynak=body.kaynak, yorum=body.yorum)
    except csat.CSATHatasi as exc:
        raise HTTPException(400, str(exc)) from None
    audit.log(db, action="csat_write", tenant_id=user.tenant_id, user_id=user.id,
              detail={"call_id": call_id, "puan": body.puan, "kaynak": body.kaynak},
              ip=request.client.host if request.client else "")
    db.commit()
    return {"call_id": c.id, "actual_csat": c.actual_csat, "kaynak": c.csat_source}


@router.get("/correlation")
def csat_korelasyon(gunler: int | None = None, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_staff)):
    return csat.korelasyon(db, user.tenant_id, gunler=gunler)


@router.get("/distribution")
def csat_dagilim(db: Session = Depends(get_db),
                 user: CurrentUser = Depends(require_staff)):
    return {"bantlar": csat.dagilim(db, user.tenant_id)}
