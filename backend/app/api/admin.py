"""Admin yonetimi: kampanya (kuyruk), yasakli kelime, kullanici, takim."""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

import logging
import secrets

from ..config import settings
from ..db import get_db
from ..deps import CurrentUser, require_admin, require_staff
from ..services import audit, onboarding
from ..models import (
    Agent, AuditLog, BannedWord, Call, CallStatus, Campaign, Channel, Criterion,
    KnowledgeDoc, Role, Team, Tenant, User,
)
from ..schemas import (
    AgentAdminCreate,
    AgentAdminOut,
    AuditLogOut,
    AuditLogPage,
    BannedWordCreate,
    BannedWordOut,
    BannedWordUpdate,
    BrandingOut,
    BrandingUpdate,
    CampaignCreate,
    CampaignOut,
    InviteResultOut,
    InviteUserRequest,
    OnboardingStatusOut,
    ProcessingStatus,
    SystemInfoOut,
    TeamCreate,
    TeamOut,
    TenantSettingsOut,
    TenantSettingsUpdate,
    UserCreate,
    UserOut,
)
from ..security import hash_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# --- Kampanyalar (kuyruklar) ---
@router.get("/campaigns", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    return (
        db.query(Campaign)
        .filter(Campaign.tenant_id == user.tenant_id)
        .order_by(Campaign.name).all()
    )


@router.post("/campaigns", response_model=CampaignOut, status_code=201)
def create_campaign(body: CampaignCreate, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_admin)):
    channel = Channel(body.channel) if body.channel in (c.value for c in Channel) else Channel.voice
    camp = Campaign(tenant_id=user.tenant_id, name=body.name, channel=channel,
                    description=body.description)
    db.add(camp)
    db.commit()
    db.refresh(camp)
    return camp


@router.delete("/campaigns/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: int, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_admin)):
    camp = db.query(Campaign).filter(
        Campaign.id == campaign_id, Campaign.tenant_id == user.tenant_id).first()
    if camp is None:
        raise HTTPException(404, "Kampanya bulunamadi")
    db.delete(camp)
    db.commit()


# --- Yasakli kelimeler ---
@router.get("/banned-words", response_model=list[BannedWordOut])
def list_banned(db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    return (
        db.query(BannedWord)
        .filter(BannedWord.tenant_id == user.tenant_id)
        .order_by(BannedWord.category, BannedWord.term).all()
    )


@router.post("/banned-words", response_model=BannedWordOut, status_code=201)
def create_banned(body: BannedWordCreate, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require_admin)):
    bw = BannedWord(tenant_id=user.tenant_id, **body.model_dump())
    db.add(bw)
    db.commit()
    db.refresh(bw)
    return bw


@router.patch("/banned-words/{bw_id}", response_model=BannedWordOut)
def update_banned(bw_id: int, body: BannedWordUpdate, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require_admin)):
    bw = db.query(BannedWord).filter(
        BannedWord.id == bw_id, BannedWord.tenant_id == user.tenant_id).first()
    if bw is None:
        raise HTTPException(404, "Yasakli kelime bulunamadi")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(bw, field, value)
    db.commit()
    db.refresh(bw)
    return bw


@router.delete("/banned-words/{bw_id}", status_code=204)
def delete_banned(bw_id: int, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require_admin)):
    bw = db.query(BannedWord).filter(
        BannedWord.id == bw_id, BannedWord.tenant_id == user.tenant_id).first()
    if bw is None:
        raise HTTPException(404, "Yasakli kelime bulunamadi")
    db.delete(bw)
    db.commit()


# --- Takimlar / kullanicilar ---
@router.get("/teams", response_model=list[TeamOut])
def list_teams(db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    return db.query(Team).filter(Team.tenant_id == user.tenant_id).order_by(Team.name).all()


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    return (
        db.query(User)
        .filter(User.tenant_id == user.tenant_id)
        .order_by(User.role, User.name).all()
    )


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_admin)):
    try:
        role = Role(body.role)
    except ValueError:
        raise HTTPException(400, f"Gecersiz rol: {body.role}")
    email = body.email.lower().strip()
    exists = db.query(User).filter(
        User.tenant_id == user.tenant_id, User.email == email).first()
    if exists:
        raise HTTPException(409, "Bu e-posta zaten kayitli")
    new_user = User(
        tenant_id=user.tenant_id, email=email, name=body.name,
        password_hash=hash_password(body.password), role=role,
        team_id=body.team_id, agent_id=body.agent_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/users/invite", response_model=InviteResultOut, status_code=201)
def invite_user(body: InviteUserRequest, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_admin)):
    """Kullaniciyi davet et: parolasiz olusturulur, davet linki (SMTP varsa e-posta)
    ile paylasilir; kullanici linkten parolasini belirler."""
    try:
        role = Role(body.role)
    except ValueError:
        raise HTTPException(400, f"Gecersiz rol: {body.role}")
    email = body.email.lower().strip()
    if db.query(User).filter(User.tenant_id == user.tenant_id, User.email == email).first():
        raise HTTPException(409, "Bu e-posta zaten kayitli")
    new_user = User(
        tenant_id=user.tenant_id, email=email, name=body.name, role=role,
        team_id=body.team_id, agent_id=body.agent_id,
        password_hash=hash_password(secrets.token_urlsafe(24)),  # gecici, kullanilamaz
        is_active=True, password_set=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    token = onboarding.issue_token(db, new_user, "invite", hours=72)
    url = onboarding.link_for(token, "invite")
    tenant = db.get(Tenant, user.tenant_id)
    org = tenant.name if tenant else "KaliteGoz"
    emailed = onboarding.send_auth_email(
        email, f"{org} — hesap davetiniz",
        f"Merhaba {body.name},\n\n{org} kalite platformuna davet edildiniz.\n"
        f"Parolanizi belirleyip giris yapmak icin:\n{url}\n\nBaglanti 72 saat gecerlidir.")
    audit.log(db, action="invite_user", tenant_id=user.tenant_id, user_id=user.id,
              entity_type="user", entity_id=new_user.id, detail={"email": email})
    return InviteResultOut(user=new_user, invite_url=url, emailed=emailed)


@router.post("/users/{user_id}/invite-link", response_model=InviteResultOut)
def regenerate_link(user_id: int, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_admin)):
    """Bir kullanici icin yeni davet/sifirlama linki uret (SMTP yoksa admin paylasir)."""
    u = db.query(User).filter(User.id == user_id, User.tenant_id == user.tenant_id).first()
    if u is None:
        raise HTTPException(404, "Kullanici bulunamadi")
    purpose = "invite" if not u.password_set else "reset"
    token = onboarding.issue_token(db, u, purpose, hours=72)
    url = onboarding.link_for(token, purpose)
    emailed = onboarding.send_auth_email(
        u.email, "KaliteGoz erisim baglantisi",
        f"Hesabiniza erismek icin:\n{url}\n\nBaglanti 72 saat gecerlidir.")
    return InviteResultOut(user=u, invite_url=url, emailed=emailed)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_admin)):
    if user_id == user.id:
        raise HTTPException(400, "Kendi hesabinizi silemezsiniz")
    u = db.query(User).filter(User.id == user_id, User.tenant_id == user.tenant_id).first()
    if u is None:
        raise HTTPException(404, "Kullanici bulunamadi")
    db.delete(u)
    db.commit()


# --- Ekip CRUD ---
@router.post("/teams", response_model=TeamOut, status_code=201)
def create_team(body: TeamCreate, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_admin)):
    name = body.name.strip()
    if db.query(Team).filter(Team.tenant_id == user.tenant_id, Team.name == name).first():
        raise HTTPException(409, "Bu isimde ekip zaten var")
    team = Team(tenant_id=user.tenant_id, name=name, supervisor_id=body.supervisor_id)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.delete("/teams/{team_id}", status_code=204)
def delete_team(team_id: int, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_admin)):
    team = db.query(Team).filter(Team.id == team_id, Team.tenant_id == user.tenant_id).first()
    if team is None:
        raise HTTPException(404, "Ekip bulunamadi")
    db.delete(team)
    db.commit()


# --- Temsilci CRUD ---
@router.get("/agents", response_model=list[AgentAdminOut])
def list_agents_admin(db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    return db.query(Agent).filter(Agent.tenant_id == user.tenant_id).order_by(Agent.name).all()


@router.post("/agents", response_model=AgentAdminOut, status_code=201)
def create_agent(body: AgentAdminCreate, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(require_admin)):
    name = body.name.strip().lower()
    if db.query(Agent).filter(Agent.tenant_id == user.tenant_id, Agent.name == name).first():
        raise HTTPException(409, "Bu isimde temsilci zaten var")
    agent = Agent(tenant_id=user.tenant_id, name=name, team_id=body.team_id)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.patch("/agents/{agent_id}", response_model=AgentAdminOut)
def update_agent(agent_id: int, body: AgentAdminCreate, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(require_admin)):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.tenant_id == user.tenant_id).first()
    if agent is None:
        raise HTTPException(404, "Temsilci bulunamadi")
    agent.name = body.name.strip().lower()
    agent.team_id = body.team_id
    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: int, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(require_admin)):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.tenant_id == user.tenant_id).first()
    if agent is None:
        raise HTTPException(404, "Temsilci bulunamadi")
    db.delete(agent)
    db.commit()


# --- Kurum ayarlari + sistem bilgisi + onboarding durumu ---
def _settings_out(tenant: Tenant) -> TenantSettingsOut:
    s = tenant.settings or {}
    return TenantSettingsOut(
        org_name=tenant.name, retention_days=tenant.retention_days,
        auto_process=not tenant.processing_paused,
        notify_events=s.get("notify_events") or ["zeroing", "crisis"],
        brand_name=tenant.brand_name, brand_color=tenant.brand_color,
    )


@router.get("/settings", response_model=TenantSettingsOut)
def get_settings(db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    return _settings_out(db.get(Tenant, user.tenant_id))


@router.put("/settings", response_model=TenantSettingsOut)
def update_settings(body: TenantSettingsUpdate, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_admin)):
    tenant = db.get(Tenant, user.tenant_id)
    s = dict(tenant.settings or {})
    if body.retention_days is not None:
        tenant.retention_days = body.retention_days
    if body.auto_process is not None:
        tenant.processing_paused = not body.auto_process
    if body.notify_events is not None:
        s["notify_events"] = body.notify_events
    tenant.settings = s
    db.commit()
    db.refresh(tenant)
    audit.log(db, action="update_settings", tenant_id=tenant.id, user_id=user.id)
    return _settings_out(tenant)


@router.get("/system-info", response_model=SystemInfoOut)
def system_info(user: CurrentUser = Depends(require_admin)):
    return SystemInfoOut(
        llm_provider=settings.llm_provider,
        llm_model=(settings.ollama_model if settings.llm_provider == "ollama" else settings.gemini_model),
        whisper_model=settings.whisper_model, whisper_device=settings.whisper_device,
        vision_enabled=settings.vision_enabled, rag_enabled=settings.rag_enabled,
        sso_enabled=settings.sso_enabled, demo_mode=settings.demo_mode,
        pii_masking=settings.pii_masking_enabled, smtp_configured=bool(settings.smtp_host),
    )


@router.get("/onboarding-status", response_model=OnboardingStatusOut)
def onboarding_status(db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    tid = user.tenant_id
    tenant = db.get(Tenant, tid)

    def has(model) -> bool:
        return db.query(model.id).filter(model.tenant_id == tid).first() is not None

    has_users = db.query(User.id).filter(
        User.tenant_id == tid, User.role != Role.admin).first() is not None
    complete = has(Team) and has(Agent) and has(Criterion) and (has(Call) or has(KnowledgeDoc))
    return OnboardingStatusOut(
        brand_set=bool(tenant and tenant.brand_name), has_teams=has(Team),
        has_agents=has(Agent), has_users=has_users, has_rubric=has(Criterion),
        has_calls=has(Call), has_knowledge=has(KnowledgeDoc), complete=complete,
    )


# =====================================================================
# Isleme kontrolu — agir STT/LLM isini ELLE baslatma
# =====================================================================
# Sesli cagri islemek CPU/RAM yogundur (Whisper + 7B LLM). Duraklatilmis
# moddayken cagrilar "pending" olarak birikir; makine musaitken buradan
# baslatilir.


def _sesli_worker_canli() -> tuple[bool, str]:
    """`voice` kuyrugunu dinleyen bir worker var mi?

    Celery'nin `inspect` cagrisi broker uzerinden canli worker'lara sorar.
    Yanit vermeyen ya da hic worker olmayan durumda bos doner.

    Neden onemli: sesli cagrilar `voice` kuyruguna gider ve o kuyrugu
    yalnizca HOST'ta calisan native worker tuketir (Whisper konteynerin
    bellek tavanina sigmiyor, exit 137). Worker yoksa "Islemeyi baslat"
    gorevleri kuyruga atar, Celery basariyla doner, ve cagrilar sonsuza
    kadar bekler — HICBIR HATA GORUNMEDEN.

    Genis except bilincli: inspect ag/broker hatasi verirse panel yine
    acilmali, yalnizca "bilinmiyor" demeli.
    """
    try:
        from ..tasks.celery_app import celery_app

        kuyruklar = celery_app.control.inspect(timeout=2.0).active_queues() or {}
        for adlar in kuyruklar.values():
            if any(q.get("name") == "voice" for q in adlar or []):
                return True, ""
        if kuyruklar:
            return False, (
                "Sesli çağrı işçisi çalışmıyor. Ses dosyaları çözümlenemez. "
                "PowerShell'de başlatın: ./scripts/run-host-worker.ps1"
            )
        return False, (
            "Hiçbir arka plan işçisine ulaşılamadı. Servisler ayakta mı? "
            "Sesli çağrılar için ayrıca: ./scripts/run-host-worker.ps1"
        )
    except Exception as exc:  # noqa: BLE001 — panel calismaya devam etmeli
        logger.warning("Worker durumu sorgulanamadi: %s", exc)
        return False, "İşçi durumu sorgulanamadı (broker yanıt vermiyor)."


def _processing_status(db: Session, tenant_id: int, queued_now: int = 0) -> ProcessingStatus:
    def count(*statuses):
        return db.query(func.count(Call.id)).filter(
            Call.tenant_id == tenant_id, Call.status.in_(statuses)
        ).scalar() or 0

    tenant = db.get(Tenant, tenant_id)
    canli, ipucu = _sesli_worker_canli()
    return ProcessingStatus(
        paused=bool(tenant and tenant.processing_paused),
        pending_calls=count(CallStatus.pending),
        failed_calls=count(CallStatus.failed),
        running_calls=count(CallStatus.transcribing, CallStatus.scoring),
        done_calls=count(CallStatus.done),
        queued_now=queued_now,
        voice_worker_active=canli,
        voice_worker_hint=ipucu,
    )


@router.get("/processing", response_model=ProcessingStatus)
def processing_status(db: Session = Depends(get_db),
                      user: CurrentUser = Depends(require_staff)):
    return _processing_status(db, user.tenant_id)


@router.post("/processing/pause", response_model=ProcessingStatus)
def pause_processing(db: Session = Depends(get_db),
                     user: CurrentUser = Depends(require_admin)):
    """Yeni cagrilar islenmesin (pending birikir). Calisan isler tamamlanir."""
    tenant = db.get(Tenant, user.tenant_id)
    tenant.processing_paused = True
    db.commit()
    return _processing_status(db, user.tenant_id)


@router.post("/processing/resume", response_model=ProcessingStatus)
def resume_processing(db: Session = Depends(get_db),
                      user: CurrentUser = Depends(require_admin)):
    """Duraklatmayi kaldir — bundan SONRA gelen cagrilar otomatik islenir.

    Birikmis pending cagrilari islemez; onun icin /processing/start kullanin.
    """
    tenant = db.get(Tenant, user.tenant_id)
    tenant.processing_paused = False
    db.commit()
    return _processing_status(db, user.tenant_id)


@router.post("/processing/start", response_model=ProcessingStatus)
def start_processing(include_failed: bool = True, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(require_admin)):
    """Bekleyen (ve istege bagli hatali) cagrilari kuyruga atar — agir is BURADA baslar.

    Sesli cagrilar 'voice', chat'ler 'fast' kuyruguna gider.
    """
    from ..tasks.pipeline import process_call, process_chat

    statuses = [CallStatus.pending]
    if include_failed:
        statuses.append(CallStatus.failed)
    calls = db.query(Call).filter(
        Call.tenant_id == user.tenant_id, Call.status.in_(statuses)
    ).all()

    queued = 0
    for call in calls:
        call.status = CallStatus.pending
        call.error = None
        if call.channel == Channel.chat:
            process_chat.delay(call.id)
        else:
            process_call.delay(call.id)
        queued += 1
    db.commit()
    return _processing_status(db, user.tenant_id, queued_now=queued)


@router.post("/import-metadata")
async def import_metadata(file: UploadFile = File(...), request: Request = None,
                          db: Session = Depends(get_db),
                          user: CurrentUser = Depends(require_admin)):
    """CSV ile toplu metadata esleştirme (santral export'u -> cagrilar).

    Bicim: `dosya;temsilci;kampanya;musteri_ref` (dosya zorunlu, digerleri opsiyonel).
    Watch-folder ile toplu aktarilan cagrilarda kampanya/musteri bilgisini sonradan
    baglamak icin.
    """
    from ..services import metadata_import

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "CSV dosyasi bekleniyor (.csv)")
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "CSV cok buyuk (limit 5 MB)")
    try:
        result = metadata_import.apply_metadata(db, user.tenant_id, raw)
    except metadata_import.MetadataError as exc:
        raise HTTPException(400, str(exc))

    audit.log(db, action="import_metadata", tenant_id=user.tenant_id, user_id=user.id,
              detail={"matched": result.matched, "updated": result.updated},
              ip=request.client.host if request and request.client else "")
    return {
        "matched": result.matched,
        "updated": result.updated,
        "not_found": result.not_found[:20],
        "not_found_count": len(result.not_found),
        "unknown_campaign": result.unknown_campaign,
        "message": (
            f"{result.matched} cagri eslesti, {result.updated} guncellendi. "
            f"{len(result.not_found)} dosya bulunamadi."
        ),
    }


# =====================================================================
# Denetim gunlugu (audit log) goruntuleme — KVKK/kurumsal izlenebilirlik
# =====================================================================
@router.get("/audit", response_model=AuditLogPage)
def list_audit(
    action: str | None = None,
    user_id: int | None = None,
    entity_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    """Append-only denetim kayitlari (kim, ne zaman, neyi). Yalnizca admin gorur.

    'reveal_pii', 'override', 'download_audio', 'export' gibi hassas erisimler
    burada izlenir — kurumsal RFP ve KVKK denetimlerinin temel gereksinimi.
    """
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    q = db.query(AuditLog).filter(AuditLog.tenant_id == user.tenant_id)
    if action:
        q = q.filter(AuditLog.action == action)
    if user_id is not None:
        q = q.filter(AuditLog.user_id == user_id)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    total = q.with_entities(func.count(AuditLog.id)).scalar() or 0
    rows = (
        q.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size).all()
    )
    # Kullanici adlarini tek sorguda cek (id -> ad)
    names = dict(
        db.query(User.id, User.name).filter(User.tenant_id == user.tenant_id).all()
    )
    items = [
        AuditLogOut(
            id=r.id, user_id=r.user_id, user_name=names.get(r.user_id),
            action=r.action, entity_type=r.entity_type, entity_id=r.entity_id,
            detail=r.detail, ip=r.ip, created_at=r.created_at,
        )
        for r in rows
    ]
    return AuditLogPage(items=items, total=total, page=page, page_size=page_size)


# =====================================================================
# Beyaz etiket (white-label) — tenant marka adi/renk/logo
# =====================================================================
def _branding(tenant: Tenant) -> BrandingOut:
    return BrandingOut(
        brand_name=tenant.brand_name or settings.brand_name,
        brand_color=tenant.brand_color or settings.brand_color,
        logo_data_url=tenant.logo_data_url,
    )


@router.get("/branding", response_model=BrandingOut)
def get_branding(db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    return _branding(db.get(Tenant, user.tenant_id))


@router.put("/branding", response_model=BrandingOut)
def update_branding(body: BrandingUpdate, request: Request = None,
                    db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_admin)):
    tenant = db.get(Tenant, user.tenant_id)
    if body.logo_data_url is not None and len(body.logo_data_url) > 300_000:
        raise HTTPException(413, "Logo cok buyuk (~200 KB sinir); daha kucuk bir gorsel yukleyin")
    if body.brand_name is not None:
        tenant.brand_name = body.brand_name
    if body.brand_color is not None:
        tenant.brand_color = body.brand_color
    if body.logo_data_url is not None:
        tenant.logo_data_url = body.logo_data_url or None
    db.commit()
    audit.log(db, action="update_branding", tenant_id=user.tenant_id, user_id=user.id,
              ip=request.client.host if request and request.client else "")
    return _branding(tenant)


# --- Demo: 8 haftalik sentetik gecmis (dashboard doldurma) ---
@router.post("/seed-demo-history")
def seed_demo_history_endpoint(db: Session = Depends(get_db),
                               user: CurrentUser = Depends(require_admin)):
    if not settings.demo_mode:
        raise HTTPException(403, "Demo modu kapali")
    from ..seed import seed_demo_history

    created = seed_demo_history(db, user.tenant_id)
    return {"created": created, "message": f"{created} sentetik gecmis cagri eklendi"}
