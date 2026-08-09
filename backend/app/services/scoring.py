"""Rubrik puanlama orkestrasyonu — uc katmanli hibrit motor (FAZ 2).

    KATMAN A  deterministik.py    kod, LLM yok. Kesin cevabi olan kriterler
                                  burada biter ve LLM'in karariNI EZER.
    KATMAN B  scoring_layers.py   kanit zorunlu LLM. Kriterler 3'lu gruplara
                                  bolunur, her grup AYRI cagridir.
    KATMAN C  scoring_layers.py   alinti transkriptte gercekten var mi?
                                  Puan aritmetigi KODDA yapilir.

Bu modul katmanlari sirayla kosturur, sonuclari DB'ye yazar ve alarm uretir.

Onceki surum tek dev prompt'ta 10 kriteri birden degerlendiriyordu; FAZ 1 taban
cizgisi olctu: kappa 0.32, kanit dogrulanabilirlik %56, sifirlayici yanlis
pozitif %38.5 (docs/v2/FAZ-1-RAPOR.md). O implementasyon kaldirildi.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AlertType, BannedWord, Call, Channel, Criterion, Score, Segment, Tenant, Violation
from ..schemas import LLMCagriAnalizi
from . import acoustics, ai_config, calibration_scale, compliance, deterministic, etiquette, knowledge
from . import alert_engine
from . import alerts as alerts_svc
from . import review_feedback
from . import scoring_layers
from .llm import generate_json

logger = logging.getLogger(__name__)


@dataclass
class ScoringOutcome:
    """Puanlama sonrasi pipeline'in alarm/webhook uretmesi icin ozet."""

    zeroed: bool
    zeroing_reason: str | None
    is_crisis: bool
    banned_word_hits: int
    total_score: float
    # FAZ 4.2: serbest metin yerine ZORUNLU ALANLI taslak (bkz. alert_engine)
    alerts: list[alert_engine.AlertDraft]

SPEAKER_LABELS = {"musteri": "MUSTERI", "temsilci": "TEMSILCI", "bilinmeyen": "KONUSMACI"}

def _fmt_ts(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    return f"{m:02d}:{s:02d}"


def format_transcript(segments: list[Segment]) -> str:
    lines = []
    for seg in segments:
        label = SPEAKER_LABELS.get(seg.speaker, "KONUSMACI")
        lines.append(f"[{_fmt_ts(seg.start_sec)} | {seg.start_sec:.0f}sn] {label}: {seg.text}")
    return "\n".join(lines)


def _metrics_hint(metrics: dict | None) -> str:
    """Deterministik olcumleri (zamanlama + akustik) LLM'e nesnel dayanak olarak ver."""
    if not metrics:
        return ""
    lines = ["\n## OTOMATIK OLCUMLER (ses analizinden, KESIN degerler)"]

    if "temsilci_konusma_orani" in metrics:
        lines.append(f"- Temsilci konusma orani: %{metrics.get('temsilci_konusma_orani')}")
        lines.append(f"- Temsilcinin musteriyi soz kesme sayisi: {metrics.get('temsilci_kesinti')}")
        lines.append(
            f"- Toplam sessizlik: {metrics.get('sessizlik_sn')} sn "
            f"(en uzun blok: {metrics.get('en_uzun_sessizlik_sn')} sn)"
        )
    if "ilk_yanit_sn" in metrics:  # chat kanali
        lines.append(f"- Ilk yanit suresi: {metrics.get('ilk_yanit_sn')} sn")
        lines.append(f"- Ortalama yanit suresi: {metrics.get('ortalama_yanit_sn')} sn")

    # --- Akustik (nasil soyledi) ---
    ac = []
    if metrics.get("temsilci_bagirma_sayisi"):
        ac.append(
            f"- TEMSILCI {metrics['temsilci_bagirma_sayisi']} kez sesini belirgin sekilde "
            f"yukseltti (bagirma), anlar: {metrics.get('temsilci_bagirma_anlari')} sn"
        )
    if metrics.get("musteri_bagirma_sayisi"):
        ac.append(
            f"- MUSTERI {metrics['musteri_bagirma_sayisi']} kez sesini yukseltti "
            f"(ofke/gerginlik isareti), anlar: {metrics.get('musteri_bagirma_anlari')} sn"
        )
    if metrics.get("temsilci_monoton"):
        ac.append(
            f"- Temsilcinin tonlamasi MONOTON (tonlama sapmasi "
            f"{metrics.get('temsilci_tonlama_sapmasi')} Hz) — robotik/ilgisiz algilanabilir"
        )
    if ac:
        lines.append("\n### Akustik (NASIL soyledi):")
        lines.extend(ac)

    # Somut esikler ver: "soz kesme puani dusurur" gibi mugak bir yonerge,
    # modelin sayilari gormesine ragmen comert puanlamasina yol aciyordu
    # (altin sette Aktif Dinleme ortalama sapma +1.73).
    kes = metrics.get("temsilci_kesinti")
    if kes is not None:
        lines.append(
            "\n### Bu olcumleri NASIL kullanacaksin (Aktif Dinleme):"
            "\n- Temsilcinin soz kesme sayisi 0     -> bu yonden tam puan engeli YOK"
            "\n- 1-2 kesme                          -> en fazla 7"
            "\n- 3-4 kesme                          -> en fazla 4"
            "\n- 5 ve uzeri                         -> en fazla 2"
            f"\n  (bu cagrida temsilci {kes} kez kesti)"
            "\n- MUSTERININ kesmesi temsilcinin puanini ETKILEMEZ."
            f" (musteri {metrics.get('musteri_kesinti', 0)} kez kesti — bu bir ceza sebebi DEGILDIR)"
        )
    lines.append(
        "\nTemsilcinin bagirmasi -> 'Yasakli Kelime / Uslup'; monotonluk -> iletisim "
        "kalitesi. Musterinin bagirmasi temsilciyi CEZALANDIRMAZ, ancak temsilcinin "
        "buna nasil tepki verdigini degerlendir.\n"
    )
    return "\n".join(lines)


NEGATIVE_EMOTIONS = {"ofke", "hayal_kirikligi", "uzuntu"}


def _detect_emotion_mismatch(sentiment_end: str, emotion: str, csat: float) -> bool:
    """Duygu-sonuc tutarsizligini yakala.

    LLM'in duygu etiketi ile CSAT tahmini celisiyorsa (orn. musteri ofkeli
    bitip CSAT 4.5 tahmin edildiyse) bu genellikle modelin bir yerde hata
    yaptiginin isaretidir; insan gozden gecirmesi degerli olur. Iki yon:
      - Kotu duygu + yuksek CSAT  (musteri kizgin ama "memnun" denmis)
      - Iyi bitis  + dusuk CSAT   (musteri mutlu ama "memnuniyetsiz" denmis)
    """
    bad_feeling = sentiment_end == "olumsuz" or emotion in NEGATIVE_EMOTIONS
    good_feeling = sentiment_end == "olumlu" and emotion not in NEGATIVE_EMOTIONS
    if bad_feeling and csat >= 4.0:
        return True
    if good_feeling and csat <= 2.0:
        return True
    return False


def _load_criteria(db: Session, call: Call) -> list[Criterion]:
    """Tenant + kampanya + kanal kapsamina uyan aktif kriterleri getir.

    campaign_id NULL kriterler global'dir (tum kampanyalarda gecerli).
    Kampanyaya ozel kriterler yalnizca o kampanyanin cagrilarinda uygulanir.
    """
    channel = call.channel.value if isinstance(call.channel, Channel) else str(call.channel)
    q = (
        db.query(Criterion)
        .filter(Criterion.tenant_id == call.tenant_id)
        .filter(Criterion.is_active.is_(True))
        .filter(or_(Criterion.channel_scope == "all", Criterion.channel_scope == channel))
    )
    if call.campaign_id is not None:
        q = q.filter(
            or_(Criterion.campaign_id.is_(None), Criterion.campaign_id == call.campaign_id)
        )
    else:
        q = q.filter(Criterion.campaign_id.is_(None))
    return q.order_by(Criterion.id).all()


def run_scoring(db: Session, call: Call) -> ScoringOutcome:
    """Cagriyi puanla. Kurumun AI saglayici config'ini (Ollama/Gemini/OpenAI/
    OpenRouter) aktif eder; tum LLM cagrilari onu kullanir."""
    tenant = db.get(Tenant, call.tenant_id)
    with ai_config.use_llm(tenant.settings if tenant else None, call.tenant_id, "scoring"):
        return _run_scoring_inner(db, call)


# =========================================================================
# UC KATMANLI PUANLAMA (FAZ 2)
#
#   KATMAN A — deterministik on kontrol (kod, LLM yok)
#        v  kesin cevabi olan her sey burada biter ve LLM'i EZER
#   KATMAN B — kanit zorunlu LLM degerlendirme (kriter grubu bazli)
#        v  her kararin yaninda transkriptten birebir alinti
#   KATMAN C — sunucu dogrulamasi + puan aritmetigi
#        v  alinti gercekten transkriptte var mi? toplam KODDA hesaplanir
#
# Gerekce ve olculen taban cizgisi: docs/v2/FAZ-1-RAPOR.md
# =========================================================================

def _brand_names(tenant: Tenant | None) -> tuple[str, ...]:
    """Kurumun acilista soylenmesi beklenen marka adlari.

    Tenant ayarindan `brand_names` listesi okunur; yoksa marka adi ve kiraci
    adindan turetilir.
    """
    names: list[str] = []
    if tenant is not None:
        settings_names = (tenant.settings or {}).get("brand_names")
        if isinstance(settings_names, list):
            names.extend(str(n) for n in settings_names if str(n).strip())
        for candidate in (tenant.brand_name, tenant.name):
            if candidate and candidate not in names:
                names.append(candidate)
    return tuple(n for n in names if n and not n.startswith("__"))


def _windows(segments: list[Segment], window_sec: int) -> list[list[Segment]]:
    """Uzun cagriyi ORTUSEN pencerelere bol; hicbir bolum atlanmaz.

    B30: eski `_transcript_outline` uzun cagrida ilk 25 + son 25 satiri alip
    ORTAYI ATIYORDU. Ortadaki bir hakaret hic gorulmuyordu. Kirpma yerine
    pencereleme yapilir ve pencereler %15 ortusur (sinira denk gelen ihlal kacmasin).
    """
    if not segments:
        return []
    total = segments[-1].end_sec
    if total <= window_sec:
        return [segments]
    overlap = window_sec * 0.15
    out: list[list[Segment]] = []
    start = 0.0
    while start < total:
        end = start + window_sec
        chunk = [s for s in segments if s.end_sec > start and s.start_sec < end]
        if chunk:
            out.append(chunk)
        start = end - overlap
    return out


def _evaluate_llm_criteria(
    criteria: list[Criterion], segments: list[Segment], hint: str, few_shot_for=None
) -> list[scoring_layers.CriterionDecision]:
    """Katman B + C. Uzun cagrida pencereleme, sonra karar birlestirme."""
    blob = " ".join(s.text for s in segments)
    windows = _windows(segments, settings.chunk_size_sec)

    if len(windows) == 1:
        kararlar = scoring_layers.evaluate_all(
            criteria, format_transcript(segments), hint, few_shot_for)
        return [scoring_layers.verify(k, blob) for k in kararlar]

    logger.info("Uzun cagri: %d pencere ile degerlendiriliyor", len(windows))
    best: dict[int, scoring_layers.CriterionDecision] = {}
    for i, win in enumerate(windows, 1):
        note = (
            f"\n## NOT\nBu, cagrinin {i}/{len(windows)} bolumudur. Yalnizca bu "
            "bolumde GORDUGUN kanitlara dayan; gormedigin bir kriter icin "
            "'insufficient_evidence' de.\n"
        )
        kararlar = scoring_layers.evaluate_all(
            criteria, format_transcript(win), hint + note, few_shot_for)
        for k in kararlar:
            d = scoring_layers.verify(k, blob)
            prev = best.get(d.criterion_id)
            if prev is None:
                best[d.criterion_id] = d
                continue
            # Kanitli bir karar, kanitsiz karari her zaman yener.
            if prev.score is None and d.score is not None:
                best[d.criterion_id] = d
            elif d.score is not None and prev.score is not None and d.score < prev.score:
                # En dusuk (en kotu) KANITLI karar gecerli: bir bolumde tespit
                # edilen ihlal, diger bolumlerin temizligiyle silinemez.
                best[d.criterion_id] = d
    return list(best.values())


def _analyze_call(segments: list[Segment], hint: str) -> LLMCagriAnalizi:
    """Cagri geneli analiz (ozet, duygu, koclu, niyet) — puanlamadan AYRI cagri.

    Puanlarla ayni prompt'a sikistirilinca modelin dikkati boluyordu.
    """
    prompt = f"""## CAGRI TRANSKRIPTI
Format: [dakika:saniye | saniye] KONUSMACI: metin
{format_transcript(segments)}
{hint}
## GOREV
1. Kategori: fatura|iptal|ariza|sikayet|bilgi|diger
2. OZET: 1-2 NESNEL cumle — musterinin talebi + temsilcinin ne yaptigi + SONUC.
3. Musteri duygusu cagrinin BASINDA ve SONUNDA (olumlu|notr|olumsuz).
4. BASKIN duygu: ofke|hayal_kirikligi|endise|memnuniyet|notr|saskinlik|minnettarlik|uzuntu
5. Duygu YORUNGESI: yukselen|dusen|sabit
6. KOCLUK: temsilciye SPESIFIK, davranissal, transkriptteki GERCEK bir eksige
   dayali 1-2 cumle. Klise ogut verme. Cagri iyiyse en guclu yonunu belirt.
7. Tahmini CSAT (1-5) ve musteri efor skoru CES (1-5).
8. SONRAKI AKSIYON: somut adim; gerekmiyorsa "takip gerekmiyor".
9. CHURN riski: dusuk|orta|yuksek
10. NIYET ETIKETLERI: 1-4 ince etiket.
11. RISKLI ANLAR: zaman + aciklama + onem (dusuk|orta|yuksek).

Turkce yaz ve Turkce karakterleri DOGRU kullan.

SADECE su semada gecerli JSON dondur:
{{"kategori":"...","ozet":"...","musteri_duygu_baslangic":"notr",
 "musteri_duygu_bitis":"notr","baskin_duygu":"notr","duygu_yorungesi":"sabit",
 "gelisim_onerisi":"...","tahmini_csat":3.5,"musteri_efor":3.0,
 "sonraki_aksiyon":"...","churn_riski":"dusuk","niyet_etiketleri":["..."],
 "riskli_anlar":[{{"zaman":45.0,"aciklama":"...","onem":"orta"}}]}}"""
    try:
        return generate_json(
            LLMCagriAnalizi,
            "Sen bir cagri merkezi kalite analistisin. Yalnizca gecerli JSON "
            "dondurursun. Turkce metinleri dogru Turkce karakterlerle yazarsin.",
            prompt,
        )
    except Exception as exc:  # noqa: BLE001 — analiz puanlamayi dusurmez
        logger.warning("Cagri analizi uretilemedi: %s", exc)
        return LLMCagriAnalizi()
def _run_scoring_inner(db: Session, call: Call) -> ScoringOutcome:
    """Cagriyi uc katmanli motorla puanla ve sonuclari DB'ye yaz.

    Segmentler onceden cikarilmis olmali. Doner: pipeline'in alarm/webhook
    uretmesi icin ScoringOutcome.
    """
    criteria = _load_criteria(db, call)
    if not criteria:
        raise RuntimeError("Aktif kriter yok — rubrik editorunden kriter ekleyin")

    segments = (
        db.query(Segment).filter(Segment.call_id == call.id).order_by(Segment.idx).all()
    )
    if not segments:
        raise RuntimeError("Transkript bos — puanlama yapilamadi")

    tenant = db.get(Tenant, call.tenant_id)
    banned = db.query(BannedWord).filter(BannedWord.tenant_id == call.tenant_id).all()

    # Yeniden puanlamada onceki cikti temizlenir; alarmlar SILINMEZ,
    # gecersizlestirilir (B31 — eski alarm ekranda asili kalmasin).
    db.query(Score).filter(Score.call_id == call.id).delete()
    db.query(Violation).filter(Violation.call_id == call.id).delete()
    alerts_svc.invalidate_for_call(db, call.id)
    db.flush()

    # ---------------- KATMAN A — deterministik on kontrol ----------------
    findings = deterministic.run_all(
        segments, brand_names=_brand_names(tenant), banned=banned
    )

    decisions: list[scoring_layers.CriterionDecision] = []
    llm_criteria: list[Criterion] = []
    for c in criteria:
        mode = getattr(c, "evaluation_mode", "llm_evidence")
        if mode == "human_only":
            decisions.append(scoring_layers.CriterionDecision(
                criterion_id=c.id, decision="insufficient_evidence", score=None,
                rationale="Bu kriter yalnizca kalite uzmani tarafindan puanlanir.",
                evidence_quote="", evidence_ts=None, evidence_speaker="",
                confidence=0.0, evidence_verified=False, source_layer="A",
            ))
            continue
        key = deterministic.check_key_for(c)
        if key and key in findings:
            decisions.append(scoring_layers.from_finding(c.id, findings[key]))
        else:
            llm_criteria.append(c)

    # ---------------- Ipuclari (nesnel dayanak) --------------------------
    hint = _metrics_hint(call.metrics if isinstance(call.metrics, dict) else None)
    etiquette_result = etiquette.analyze(segments)
    hint += etiquette.hint(etiquette_result)
    if settings.rag_enabled:
        try:
            hint += knowledge.build_context(db, call.tenant_id, format_transcript(segments))
        except Exception as exc:  # RAG asla puanlamayi dusurmez
            logger.warning("RAG baglami olusturulamadi: %s", exc)

    # ---------------- KATMAN B + C — kanit zorunlu LLM -------------------
    # Kalite uzmaninin onceki duzeltmeleri few-shot ornek olarak enjekte edilir
    # (FAZ 3.4 geri besleme dongusu). Ornek yoksa blok bos doner, davranis degismez.
    if llm_criteria:
        def _few_shot(group: list[Criterion]) -> str:
            try:
                return review_feedback.build_block(db, call.tenant_id, group)
            except Exception as exc:  # noqa: BLE001 — kalibrasyon puanlamayi dusurmez
                logger.warning("Kalibrasyon ornekleri okunamadi: %s", exc)
                return ""

        decisions.extend(_evaluate_llm_criteria(llm_criteria, segments, hint, _few_shot))

    # ---------------- KATMAN C (devam) — skala kalibrasyonu --------------
    # LLM ile puanlanan kriterlerde olculmus, tek yonlu bir sapma var (altin
    # sette Aktif Dinleme +1.73, Cozum +1.24, Ihtiyac +1.16). Bu, gurultu degil
    # olcek hizasizligidir; kriter bazinda ogrenilmis kaydirmayla duzeltilir.
    # Deterministik (Katman A) kararlar kalibre EDILMEZ — sapmalari sifir.
    # Kaydirma BANT ICINDE kalir: modelin "karsilandi" dedigi bir kriter
    # kalibrasyon yuzunden "kismen" bandina DUSEMEZ. Aksi halde kalibrasyon,
    # modelin dogru kararlarini bozarak yeni hata uretir (olculdu).
    _names = {c.id: c.name for c in criteria}
    for d in decisions:
        d.score = scoring_layers.clamp_to_band(
            d.decision,
            calibration_scale.apply(
                _names.get(d.criterion_id, ""), d.score, source_layer=d.source_layer
            ),
        )

    # Deterministik TAVAN: olculmus soz kesme sayisi Aktif Dinleme puanini
    # sinirlar. LLM tavanin ALTINDA serbest — empati/teyit gibi olculemeyen
    # kisim ona ait. Bkz. deterministic.listening_ceiling.
    # Olculmus guvenilirlik: sistemin guvenilir OLMADIGINI bildigi kriterlerde
    # guven skoru tavanlanir -> kuyruk kurali 3 devreye girer -> cagri insana
    # gider. "AI %100 dogru" demek yerine sinirini bilip yonetmek.
    for d in decisions:
        cap = calibration_scale.confidence_cap(
            _names.get(d.criterion_id, ""), d.source_layer
        )
        if cap is not None and d.confidence > cap:
            d.confidence = cap

    tavan, tavan_gerekce = deterministic.listening_ceiling(
        call.metrics if isinstance(call.metrics, dict) else None
    )
    if tavan is not None:
        for d in decisions:
            ad = _names.get(d.criterion_id, "")
            if "aktif dinleme" not in ad.lower() or d.score is None or d.score <= tavan:
                continue
            d.score = tavan
            d.rationale = f"{d.rationale} {tavan_gerekce}".strip()
            d.decision = "partially_met" if tavan >= 5 else "not_met"
            d.source_layer = "A"  # karari kod verdi

    # ---------------- Puan ve sifirlama — hepsi KODDA --------------------
    base_total = scoring_layers.compute_total(decisions, criteria)
    zeroing = scoring_layers.decide_zeroing(decisions, criteria)

    if zeroing.zeroed and not zeroing.evidence:
        # Kanitsiz sifirlama bir SISTEM HATASIDIR, sessizce gecilemez.
        raise ValueError(
            f"Kanitsiz sifirlama girisimi (call={call.id}): {zeroing.reason}"
        )

    crit_by_id = {c.id: c for c in criteria}
    for d in decisions:
        c = crit_by_id.get(d.criterion_id)
        if c is None:
            continue
        db.add(Score(
            call_id=call.id, criterion_id=c.id, criterion_name=c.name,
            criterion_group=c.group, weight=c.weight,
            score=d.score, rationale=d.rationale,
            evidence=d.evidence_quote, evidence_ts=d.evidence_ts,
            decision=d.decision, confidence=d.confidence,
            evidence_verified=d.evidence_verified, source_layer=d.source_layer,
        ))

    # ---------------- Ihlaller ve alarmlar -------------------------------
    alerts: list[alert_engine.AlertDraft] = []

    banned_hits = deterministic.find_banned(segments, banned)
    agent_hits = [h for h in banned_hits if h.speaker == "temsilci"]
    for h in banned_hits:
        db.add(Violation(
            tenant_id=call.tenant_id, call_id=call.id, kind="banned_word",
            category=h.category, severity=h.severity, term=h.term,
            speaker=h.speaker, evidence=h.quote, ts_sec=h.ts_sec,
        ))
    for h in agent_hits:
        alerts.append(alert_engine.banned_word_alert(
            call.id, h.term, h.category, h.severity, h.quote, h.ts_sec))

    for f in etiquette_result.get("bulgular", []):
        db.add(Violation(
            tenant_id=call.tenant_id, call_id=call.id, kind="etiquette",
            category="hitap", severity=f["onem"], term=f["tur"],
            speaker="temsilci", evidence=f["kanit"], ts_sec=f["zaman"],
        ))
    if etiquette_result.get("sen_kullanimi"):
        alerts.append(alert_engine.AlertDraft(
            type=AlertType.banned_word, severity="yuksek", rule_id="etiquette:sen",
            call_id=call.id, title_tr="Hitap ihlali",
            explanation_tr=(
                f"Temsilci musteriye {etiquette_result['sen_kullanimi']} kez "
                "'sen' diye hitap etti."),
            suggested_action_tr="Temsilciye hitap kurallarini hatirlatin."))

    # Deterministik uyum bulgulari ihlal olarak da kaydedilir (izlenebilirlik).
    # ONEMLI (B32): bu bulgular ARTIK kriter puanini dogrudan belirliyor —
    # Katman A yukarida `decisions` icine yazdi. Yani "KVKK anonsu yok" tespiti
    # hem alarm uretir hem puani sifirlar. Onceden yalniz alarm uretiyordu ve
    # cagri 92 puan alabiliyordu.
    for key in ("kvkk_anons", "kimlik_dogrulama"):
        f = findings.get(key)
        if f is not None and f.decision == "not_met":
            db.add(Violation(
                tenant_id=call.tenant_id, call_id=call.id, kind="compliance",
                category=key, severity="yuksek", term=key, speaker="temsilci",
                evidence=f.rationale_tr, ts_sec=f.evidence_ts,
            ))
            alerts.append(alert_engine.compliance_alert(
                call.id, key, f.rationale_tr, f.evidence_quote, f.evidence_ts))

    is_crisis, crisis_ev, crisis_ts = compliance.detect_crisis(segments)
    if is_crisis:
        db.add(Violation(
            tenant_id=call.tenant_id, call_id=call.id, kind="crisis",
            category="eskalasyon", severity="yuksek", term="", speaker="musteri",
            evidence=crisis_ev or "", ts_sec=crisis_ts,
        ))
        alerts.append(alert_engine.crisis_alert(call.id, crisis_ev or "", crisis_ts))

    # ---------------- Cagri geneli analiz (ayri LLM cagrisi) -------------
    analiz = _analyze_call(segments, hint)

    if zeroing.zeroed:
        call.total_score = 0.0
        call.zeroed = True
        call.zeroing_reason = zeroing.reason
        call.zeroing_evidence = zeroing.evidence
        call.zeroing_evidence_ts = zeroing.evidence_ts
        call.zeroing_criterion_id = zeroing.criterion_id
        alerts.append(alert_engine.zeroing_alert(
            call.id,
            crit_by_id[zeroing.criterion_id].name if zeroing.criterion_id in crit_by_id
            else "Kritik kriter",
            zeroing.reason or "", zeroing.evidence or "", zeroing.evidence_ts))
    else:
        call.total_score = base_total
        call.zeroed = False
        call.zeroing_reason = None
        call.zeroing_evidence = None
        call.zeroing_evidence_ts = None
        call.zeroing_criterion_id = None
        if base_total is not None and base_total < 60:
            alerts.append(alert_engine.low_score_alert(call.id, base_total))

    # Kanitsiz/dusuk guvenli kriterler insan kuyruguna isaret eder
    pending = [d for d in decisions if d.needs_human]
    if pending:
        names = ", ".join(
            crit_by_id[d.criterion_id].name for d in pending[:3] if d.criterion_id in crit_by_id
        )
        alerts.append(alert_engine.review_needed_alert(call.id, names, len(pending)))

    call.category = analiz.kategori
    call.summary = analiz.ozet
    risky = [r.model_dump() for r in analiz.riskli_anlar]
    if isinstance(call.metrics, dict):
        seen_ts = {round(r["zaman"]) for r in risky}
        for extra in acoustics.acoustic_risky_moments(call.metrics):
            if round(extra["zaman"]) not in seen_ts:
                risky.append(extra)
                seen_ts.add(round(extra["zaman"]))
        risky.sort(key=lambda r: r["zaman"])
    call.risky_moments = risky
    call.sentiment_start = analiz.musteri_duygu_baslangic
    call.sentiment_end = analiz.musteri_duygu_bitis
    call.coaching = analiz.gelisim_onerisi
    call.predicted_csat = round(analiz.tahmini_csat, 1)
    call.is_crisis = is_crisis
    call.emotion = analiz.baskin_duygu
    call.sentiment_trajectory = analiz.duygu_yorungesi
    call.next_action = (analiz.sonraki_aksiyon or "").strip() or None
    call.churn_risk = analiz.churn_riski
    call.customer_effort = round(analiz.musteri_efor, 1)
    call.intent_tags = analiz.niyet_etiketleri

    # Semantik "benzer cagri" aramasi icin embedding (best-effort)
    try:
        etext = " ".join(p for p in [call.summary or "", call.category or "",
                                     " ".join(call.intent_tags or [])] if p).strip()
        if etext:
            call.embedding = knowledge.embed(
                [etext], tenant.settings if tenant else None,
                tenant_id=call.tenant_id, kind="embed")[0]
    except Exception as _exc:  # noqa: BLE001
        logger.warning("Cagri embedding uretilemedi (call %s): %s", call.id, _exc)

    call.emotion_mismatch = _detect_emotion_mismatch(
        analiz.musteri_duygu_bitis, analiz.baskin_duygu, analiz.tahmini_csat
    )
    if call.emotion_mismatch:
        alerts.append(alert_engine.emotion_mismatch_alert(call.id))

    return ScoringOutcome(
        zeroed=zeroing.zeroed,
        zeroing_reason=zeroing.reason,
        is_crisis=is_crisis,
        banned_word_hits=len(agent_hits),
        total_score=call.total_score,
        alerts=alerts,
    )
