"""LLM rubrik puanlama.

- Kriterler DB'den okunur, prompt dinamik kurulur (rubrik editorunden eklenen
  yeni kriter otomatik olarak prompta girer).
- Kisa cagrilar tek atista puanlanir.
- Uzun cagrilar (> CHUNK_THRESHOLD_SEC) chunk'lanip map-reduce ile puanlanir:
  map: her chunk icin kriter gozlemleri, reduce: gozlemlerden nihai puanlar.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AlertType, BannedWord, Call, Channel, Criterion, Score, Segment, Tenant, Violation
from ..schemas import LLMChunkAnaliz, LLMDegerlendirme, LLMPuan
from . import acoustics, ai_config, compliance, compliance_packs, etiquette, knowledge
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
    alerts: list[tuple[AlertType, str, str]]  # (tip, siddet, mesaj)

SPEAKER_LABELS = {"musteri": "MUSTERI", "temsilci": "TEMSILCI", "bilinmeyen": "KONUSMACI"}

SYSTEM_PROMPT = (
    "Sen kidemli bir cagri merkezi kalite guvence (QA) uzmanisin. Yillardir cagri "
    "dinleyip puanliyorsun; degerlendirmelerin adil, tutarli, KANITA DAYALI ve "
    "profesyoneldir. Sana zaman damgali, konusmaci etiketli Turkce transkript verilir; "
    "yalnizca TEMSILCININ performansini rubrik kriterlerine gore degerlendirirsin.\n"
    "Uzman ilkelerin:\n"
    "1) TUTARLILIK: Her puan kendi gerekcesiyle uyumlu olmali. Gerekcede bir eksik/"
    "hata/'ancak' belirtiyorsan puan bunu YANSITMALI; ovup dusuk ya da elestirip yuksek "
    "puan VERME.\n"
    "2) KANIT: Her puan transkriptten BIREBIR alintiya dayanir. Kanit yoksa tahmin "
    "yurutme, puani buna gore ver.\n"
    "3) ADALET: Musterinin davranisi (bagirma, kufur, sabirsizlik) temsilciyi "
    "CEZALANDIRMAZ; yalnizca temsilcinin buna verdigi tepkiyi degerlendirirsin.\n"
    "4) DIL: Turkce'yi dogru, akici ve profesyonel yaz; klise ve bosluk doldurma cumleler kurma.\n"
    "Yanitin HER ZAMAN sadece gecerli JSON olur; JSON disinda hicbir metin yazmazsin."
)

MAP_SYSTEM_PROMPT = (
    "Sen bir cagri merkezi kalite degerlendirme uzmanisin. Sana uzun bir cagrinin "
    "BIR BOLUMU verilir. Bu bolumde her kritere dair gordugun kanitlari ve riskli "
    "anlari toplarsin; PUAN VERMEZSIN, sadece gozlem yazarsin. Bir kritere dair bu "
    "bolumde kanit yoksa o kriteri atlarsin. Yanitin HER ZAMAN sadece gecerli JSON olur."
)


def _fmt_ts(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    return f"{m:02d}:{s:02d}"


def format_transcript(segments: list[Segment]) -> str:
    lines = []
    for seg in segments:
        label = SPEAKER_LABELS.get(seg.speaker, "KONUSMACI")
        lines.append(f"[{_fmt_ts(seg.start_sec)} | {seg.start_sec:.0f}sn] {label}: {seg.text}")
    return "\n".join(lines)


def _criteria_block(criteria: list[Criterion]) -> str:
    lines = []
    for c in criteria:
        flag = " [KRITIK/SIFIRLAYICI]" if c.is_critical else ""
        lines.append(
            f"- kriter_id={c.id} | [{c.group}] {c.name} (agirlik: {c.weight}){flag}\n  {c.description}"
        )
    return "\n".join(lines)


def _eval_prompt(criteria: list[Criterion], transcript: str, extra: str = "") -> str:
    ids = [c.id for c in criteria]
    return f"""## DEGERLENDIRME KRITERLERI
{_criteria_block(criteria)}

## CAGRI TRANSKRIPTI
Format: [dakika:saniye | saniye] KONUSMACI: metin
{transcript}
{extra}
## PUANLAMA OLCEGI (0-10) — HER kriteri bu capalara gore puanla
9-10: Kusursuz/ornek — kriterin tum unsurlari eksiksiz karsilandi.
7-8 : Iyi — kucuk bir eksik var ama kriter buyuk olcude karsilandi.
5-6 : Orta — onemli bir unsur eksik veya kismen yanlis yapildi.
3-4 : Zayif — kriterin buyuk kismi karsilanmadi.
0-2 : Basarisiz — kriter hic karsilanmadi veya agir ihlal var.
KURAL: Gerekce ile puan TUTARLI olacak. Gerekcede "yapmadi / eksik / yanlis / ancak"
gecen bir kriter 8-9 ALAMAZ; eksigi puana yansit (orn. zorunlu "baska yardim?" sorusu
sorulmadiysa Kapanis 6 veya alti).

## GOREV
1. Her kriteri yukaridaki olcege gore 0-10 puanla.
2. Her puan icin puanla TUTARLI, spesifik (klise olmayan) Turkce gerekce yaz.
3. Her puan icin transkriptten BIREBIR kanit cumlesi ve kanitin saniye cinsinden
   zamanini ver (kanit yoksa bos birak).
4. Cagriyi su kategorilerden birine ata: fatura, iptal, ariza, sikayet, bilgi, diger.
5. OZET: Cagriyi 1-2 NESNEL cumlede ozetle — musterinin talebi + temsilcinin ne yaptigi
   + SONUC (cozuldu / yonlendirildi / cozulmedi). Yorum veya duygu katma.
6. Riskli anlari listele (kaba uslup, yasakli ifade, KVKK ihlali, musteri magduriyeti,
   yanlis bilgi vb.) — her biri icin saniye, aciklama ve onem (dusuk/orta/yuksek).
7. Musterinin duygu durumunu cagrinin BASINDA ve SONUNDA etiketle
   (olumlu/notr/olumsuz) — iyi bir cagri duyguyu yukseltir veya korur.
8. KOCLUK: Temsilciye SPESIFIK, davranissal ve uygulanabilir 1-2 cumlelik oneri yaz;
   transkriptteki GERCEK bir eksige dayandir ("su noktada sunu yapmaliydi"). Klise ogut
   ("daha iyi iletisim kur") ve ANLAMSIZ oneri (orn. "daha uzun sessizlik birak") VERME.
   Cagri gercekten iyiyse tek cumleyle en guclu yonunu belirt.
9. Musteri memnuniyetini (CSAT) 1-5 arasi tahmin et (1=cok kotu, 5=cok iyi).
10. Musterinin BASKIN duygusunu tek kelimeyle etiketle: ofke, hayal_kirikligi,
    endise, memnuniyet, notr, saskinlik, minnettarlik, uzuntu.
11. Duygu YORUNGESI: cagri boyunca musterinin tonu nasil seyretti?
    yukselen (kotu basladi iyi bitti), dusen (iyi basladi kotu bitti), sabit.
12. SONRAKI EN IYI AKSIYON: cagri sonrasi atilacak SOMUT adim (orn. "iade talebini
    sisteme gir", "teknik ekibe is emri ac", "48 saat icinde takip aramasi yap",
    "ust birime aktar"). Cagri tam cozulduyse "takip gerekmiyor" yaz — BOS BIRAKMA.
13. CHURN (musteri kaybi) riski: musteri iptal/tehdit/asiri memnuniyetsizlik
    isareti veriyor mu? dusuk | orta | yuksek.
14. MUSTERI EFOR skoru (CES) 1-5: musteri sorununu cozdurmek icin ne kadar
    ugrasmak zorunda kaldi? (1=cok kolay/tek temas, 5=cok zor/tekrar tekrar).
15. NIYET ETIKETLERI: cagriyi tanimlayan 1-4 ince etiket (orn. "iptal-tehdidi",
    "fatura-itiraz", "teknik-ariza", "gecikme-sikayeti", "bilgi-talebi").

"puanlar" listesinde su kriter id'lerinin TAMAMI bulunmali: {ids}

SADECE su semada gecerli JSON dondur:
{{
  "kategori": "fatura|iptal|ariza|sikayet|bilgi|diger",
  "ozet": "...",
  "musteri_duygu_baslangic": "olumlu|notr|olumsuz",
  "musteri_duygu_bitis": "olumlu|notr|olumsuz",
  "gelisim_onerisi": "...",
  "tahmini_csat": 3.5,
  "baskin_duygu": "ofke|hayal_kirikligi|endise|memnuniyet|notr|saskinlik|minnettarlik|uzuntu",
  "duygu_yorungesi": "yukselen|dusen|sabit",
  "sonraki_aksiyon": "...",
  "churn_riski": "dusuk|orta|yuksek",
  "musteri_efor": 3.0,
  "niyet_etiketleri": ["...", "..."],
  "puanlar": [
    {{"kriter_id": {ids[0]}, "puan": 0, "gerekce": "...", "kanit": "...", "kanit_zaman": 12.5}}
  ],
  "riskli_anlar": [
    {{"zaman": 45.0, "aciklama": "...", "onem": "dusuk|orta|yuksek"}}
  ]
}}"""


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

    lines.append(
        "\nBu olcumleri kullan: soz kesme/sessizlik -> 'Aktif Dinleme'; temsilcinin "
        "bagirmasi -> 'Yasakli Kelime / Uslup' ve varsa 'Kriz Yonetimi' (sakin kalmali); "
        "monotonluk -> 'Iletisim Kalitesi'. Musterinin bagirmasi temsilciyi CEZALANDIRMAZ, "
        "ancak temsilcinin buna nasil tepki verdigini degerlendir.\n"
    )
    return "\n".join(lines)


def _map_prompt(criteria: list[Criterion], chunk_no: int, total: int, transcript: str) -> str:
    return f"""## DEGERLENDIRME KRITERLERI
{_criteria_block(criteria)}

## CAGRI BOLUMU ({chunk_no}/{total})
Format: [dakika:saniye | saniye] KONUSMACI: metin
{transcript}

## GOREV
Bu bolumde her kritere dair gordugun kanitlari topla (puan verme). Bir kritere dair
kanit yoksa listeye ekleme. Riskli anlari da listele.

SADECE su semada gecerli JSON dondur:
{{
  "gozlemler": [
    {{"kriter_id": 1, "gozlem": "...", "kanit": "...", "kanit_zaman": 12.5}}
  ],
  "riskli_anlar": [
    {{"zaman": 45.0, "aciklama": "...", "onem": "dusuk|orta|yuksek"}}
  ]
}}"""


def _chunk_segments(segments: list[Segment], chunk_sec: int) -> list[list[Segment]]:
    chunks: list[list[Segment]] = []
    current: list[Segment] = []
    chunk_start = 0.0
    for seg in segments:
        if current and seg.start_sec >= chunk_start + chunk_sec:
            chunks.append(current)
            current = []
            chunk_start = seg.start_sec
        if not current:
            chunk_start = seg.start_sec
        current.append(seg)
    if current:
        chunks.append(current)
    return chunks


def _evaluate_single(
    criteria: list[Criterion], segments: list[Segment], extra: str = ""
) -> LLMDegerlendirme:
    prompt = _eval_prompt(criteria, format_transcript(segments), extra)
    result = generate_json(LLMDegerlendirme, SYSTEM_PROMPT, prompt)
    return _ensure_coverage(result, criteria, format_transcript(segments))


def _evaluate_map_reduce(
    criteria: list[Criterion], segments: list[Segment], extra_hint: str = ""
) -> LLMDegerlendirme:
    chunks = _chunk_segments(segments, settings.chunk_size_sec)
    logger.info("Uzun cagri: %d chunk ile map-reduce puanlama", len(chunks))

    observations: list[str] = []
    risky: list = []
    for i, chunk in enumerate(chunks, start=1):
        analysis = generate_json(
            LLMChunkAnaliz,
            MAP_SYSTEM_PROMPT,
            _map_prompt(criteria, i, len(chunks), format_transcript(chunk)),
        )
        span = f"{_fmt_ts(chunk[0].start_sec)}-{_fmt_ts(chunk[-1].end_sec)}"
        for g in analysis.gozlemler:
            ts = f", zaman: {g.kanit_zaman:.0f}sn" if g.kanit_zaman is not None else ""
            observations.append(
                f"- [bolum {i}, {span}] kriter_id={g.kriter_id}: {g.gozlem}"
                + (f' | kanit: "{g.kanit}"{ts}' if g.kanit else "")
            )
        risky.extend(analysis.riskli_anlar)

    obs_text = "\n".join(observations) if observations else "(gozlem toplanamadi)"
    extra = (
        "\n## NOT\nBu cagri uzun oldugu icin bolum bolum incelendi. Asagida tum "
        "bolumlerden toplanan kriter gozlemleri var; nihai puanlari BU GOZLEMLERE "
        f"gore ver:\n{obs_text}\n{extra_hint}"
    )
    # Reduce asamasina ham transkript yerine ozet akis + gozlemler verilir
    outline = _transcript_outline(segments)
    prompt = _eval_prompt(criteria, outline, extra)
    result = generate_json(LLMDegerlendirme, SYSTEM_PROMPT, prompt)
    result = _ensure_coverage(result, criteria, outline)
    # Map asamasindan gelen riskli anlar reduce ciktisiyla birlestirilir
    seen = {(round(r.zaman), r.aciklama[:40]) for r in result.riskli_anlar}
    for r in risky:
        key = (round(r.zaman), r.aciklama[:40])
        if key not in seen:
            result.riskli_anlar.append(r)
            seen.add(key)
    result.riskli_anlar.sort(key=lambda r: r.zaman)
    return result


def _transcript_outline(segments: list[Segment], head: int = 25, tail: int = 25) -> str:
    """Uzun cagrida reduce prompt'u sismesin diye bas + son bolumu ver."""
    if len(segments) <= head + tail:
        return format_transcript(segments)
    skipped = len(segments) - head - tail
    return (
        format_transcript(segments[:head])
        + f"\n... ({skipped} satir atlandi, gozlemler bolumune bakin) ...\n"
        + format_transcript(segments[-tail:])
    )


def _ensure_coverage(
    result: LLMDegerlendirme, criteria: list[Criterion], transcript: str
) -> LLMDegerlendirme:
    """Tum aktif kriterlerin puanlandigini garanti et; eksikse 1 kez tamamlat."""
    expected = {c.id for c in criteria}
    got = {p.kriter_id for p in result.puanlar}
    missing = expected - got
    # Rubrikte olmayan id'ler atilir (LLM halusinasyonu)
    result.puanlar = [p for p in result.puanlar if p.kriter_id in expected]

    if missing:
        logger.warning("LLM su kriterleri atladi, tamamlatiliyor: %s", missing)
        missing_criteria = [c for c in criteria if c.id in missing]
        try:
            fix = generate_json(
                LLMDegerlendirme,
                SYSTEM_PROMPT,
                _eval_prompt(missing_criteria, transcript),
            )
            by_id = {p.kriter_id: p for p in fix.puanlar}
            for cid in list(missing):
                if cid in by_id:
                    result.puanlar.append(by_id[cid])
                    missing.discard(cid)
        except Exception as exc:
            logger.warning("Eksik kriter tamamlama basarisiz: %s", exc)

    # Hala eksikse notr puanla isaretle — pipeline'i dusurmek yerine gorunur birak
    for cid in missing:
        crit = next(c for c in criteria if c.id == cid)
        result.puanlar.append(
            LLMPuan(
                kriter_id=cid,
                puan=5,
                gerekce=f"'{crit.name}' kriteri LLM tarafindan degerlendirilemedi (otomatik notr puan).",
            )
        )
    return result


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


def compute_total(puanlar: list[LLMPuan], criteria: list[Criterion]) -> float:
    """Agirlikli toplam: 0-100 olcegi."""
    weights = {c.id: c.weight for c in criteria}
    total_w = sum(weights.get(p.kriter_id, 1.0) for p in puanlar)
    if total_w <= 0:
        return 0.0
    raw = sum(p.puan * weights.get(p.kriter_id, 1.0) for p in puanlar)
    return round(raw / (total_w * 10) * 100, 1)


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


def _run_scoring_inner(db: Session, call: Call) -> ScoringOutcome:
    """Cagriyi puanla, uyum kontrolu yap ve sonuclari DB'ye yaz.

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

    hint = _metrics_hint(call.metrics if isinstance(call.metrics, dict) else None)

    # Hitap & nezaket kural motoru (Turkce'ye ozgu, deterministik)
    etiquette_result = etiquette.analyze(segments)
    hint += etiquette.hint(etiquette_result)

    # RAG: sirket bilgi bankasindan ilgili pasajlari prompt'a ekle (bilgi dogrulugu).
    # Bilgi bankasi bossa veya embedding alinamazsa bos doner; puanlama RAG'siz surer.
    if settings.rag_enabled:
        try:
            hint += knowledge.build_context(db, call.tenant_id, format_transcript(segments))
        except Exception as exc:  # RAG asla puanlamayi dusurmez
            logger.warning("RAG baglami olusturulamadi: %s", exc)

    duration = call.duration_sec or (segments[-1].end_sec if segments else 0)
    if duration > settings.chunk_threshold_sec:
        result = _evaluate_map_reduce(criteria, segments, hint)
    else:
        result = _evaluate_single(criteria, segments, hint)

    crit_by_id = {c.id: c for c in criteria}
    db.query(Score).filter(Score.call_id == call.id).delete()
    for p in result.puanlar:
        crit = crit_by_id[p.kriter_id]
        db.add(
            Score(
                call_id=call.id,
                criterion_id=crit.id,
                criterion_name=crit.name,
                criterion_group=crit.group,
                weight=crit.weight,
                score=p.puan,
                rationale=p.gerekce,
                evidence=p.kanit,
                evidence_ts=p.kanit_zaman,
            )
        )

    # --- Uyum motoru: yasakli kelime + kriz + sifirlayici ihlal ---
    db.query(Violation).filter(Violation.call_id == call.id).delete()
    alerts: list[tuple[AlertType, str, str]] = []

    banned = db.query(BannedWord).filter(BannedWord.tenant_id == call.tenant_id).all()
    detected = compliance.detect_banned_words(segments, banned)
    agent_hits = compliance.agent_violations(detected)
    for v in detected:
        db.add(
            Violation(
                tenant_id=call.tenant_id,
                call_id=call.id,
                kind=v.kind,
                category=v.category,
                severity=v.severity,
                term=v.term,
                speaker=v.speaker,
                evidence=v.evidence,
                ts_sec=v.ts_sec,
            )
        )
    for v in agent_hits:
        alerts.append(
            (AlertType.banned_word, v.severity, f"Yasakli kelime ({v.category}): '{v.term}' — {v.evidence[:80]}")
        )

    # Hitap/nezaket ihlalleri (kural motorundan) — ihlal listesine yazilir
    for f in etiquette_result.get("bulgular", []):
        db.add(
            Violation(
                tenant_id=call.tenant_id, call_id=call.id, kind="etiquette",
                category="hitap", severity=f["onem"], term=f["tur"],
                speaker="temsilci", evidence=f["kanit"], ts_sec=f["zaman"],
            )
        )
    if etiquette_result.get("sen_kullanimi"):
        alerts.append((
            AlertType.banned_word, "yuksek",
            f"Hitap ihlali: temsilci musteriye {etiquette_result['sen_kullanimi']} kez "
            f"'sen' diye hitap etti",
        ))

    # Uyum paketleri: temsilci repliklerinde zorunlu aciklama eksik / yasak ifade var mi?
    # (KVKK aydinlatma, PCI kart-no vb.) Aktif paketler tenant ayarindan gelmeli;
    # su an built-in DEFAULT_ACTIVE (kvkk) kullanilir.
    agent_text = " ".join(s.text for s in segments if s.speaker == "temsilci")
    for pv in compliance_packs.evaluate(agent_text):
        db.add(
            Violation(
                tenant_id=call.tenant_id, call_id=call.id, kind="compliance",
                category=pv["pack"], severity=pv["severity"],
                term=pv["rule"], speaker="temsilci",
                evidence=pv["description"], ts_sec=None,
            )
        )
        if pv["severity"] == "yuksek":
            label = "eksik zorunlu aciklama" if pv["type"] == "missing_required" else "yasak ifade"
            alerts.append((
                AlertType.banned_word, "yuksek",
                f"Uyum ihlali ({pv['pack'].upper()} — {label}): {pv['description']}",
            ))

    is_crisis, crisis_ev, crisis_ts = compliance.detect_crisis(segments)
    if is_crisis:
        db.add(
            Violation(
                tenant_id=call.tenant_id, call_id=call.id, kind="crisis",
                category="eskalasyon", severity="yuksek", term="", speaker="musteri",
                evidence=crisis_ev or "", ts_sec=crisis_ts,
            )
        )
        alerts.append((AlertType.crisis, "yuksek", f"Kriz sinyali: {(crisis_ev or '')[:100]}"))

    # Sifirlayici ihlal: kritik kriter esik altinda VEYA temsilci yuksek siddet yasakli kelime
    zeroing_reason = None
    score_by_crit = {p.kriter_id: p.puan for p in result.puanlar}
    for c in criteria:
        if c.is_critical and score_by_crit.get(c.id, 10) < c.critical_threshold:
            zeroing_reason = f"Kritik kriter esik alti: {c.name} ({score_by_crit.get(c.id)}/{c.critical_threshold})"
            break
    if not zeroing_reason:
        severe = [v for v in agent_hits if v.severity == "yuksek"]
        if severe:
            zeroing_reason = f"Temsilci agir yasakli ifade kullandi: '{severe[0].term}'"

    base_total = compute_total(result.puanlar, criteria)
    if zeroing_reason:
        call.total_score = 0.0
        call.zeroed = True
        alerts.append((AlertType.zeroing, "yuksek", zeroing_reason))
    else:
        call.total_score = base_total
        call.zeroed = False
        if base_total < 60:
            alerts.append((AlertType.low_score, "orta", f"Dusuk kalite puani: {base_total}"))

    call.category = result.kategori
    call.summary = result.ozet
    # LLM'in bulduklari + akustik tespitler (bagirma anlari) birlikte
    risky = [r.model_dump() for r in result.riskli_anlar]
    if isinstance(call.metrics, dict):
        seen_ts = {round(r["zaman"]) for r in risky}
        for extra in acoustics.acoustic_risky_moments(call.metrics):
            if round(extra["zaman"]) not in seen_ts:
                risky.append(extra)
                seen_ts.add(round(extra["zaman"]))
        risky.sort(key=lambda r: r["zaman"])
    call.risky_moments = risky
    call.sentiment_start = result.musteri_duygu_baslangic
    call.sentiment_end = result.musteri_duygu_bitis
    call.coaching = result.gelisim_onerisi
    call.predicted_csat = round(result.tahmini_csat, 1)
    call.is_crisis = is_crisis

    # --- LLM analitik paketi (Dalga 1) ---
    call.emotion = result.baskin_duygu
    call.sentiment_trajectory = result.duygu_yorungesi
    call.next_action = result.sonraki_aksiyon.strip() or None
    call.churn_risk = result.churn_riski
    call.customer_effort = round(result.musteri_efor, 1)
    call.intent_tags = result.niyet_etiketleri

    # Semantik "benzer cagri" aramasi icin embedding uret (best-effort; hata puanlamayi bozmaz)
    try:
        from ..models import Tenant
        # NOT: `knowledge` modul duzeyinde import edili (bkz. ustteki import).
        # Burada tekrar import etmek onu fonksiyon-yerel degiskene cevirip
        # yukaridaki RAG baglami cagrisini UnboundLocalError ile patlatiyordu.
        etext = " ".join(p for p in [call.summary or "", call.category or "",
                                     " ".join(call.intent_tags or [])] if p).strip()
        if etext:
            _tenant = db.get(Tenant, call.tenant_id)
            call.embedding = knowledge.embed(
                [etext], _tenant.settings if _tenant else None,
                tenant_id=call.tenant_id, kind="embed")[0]
    except Exception as _exc:  # noqa: BLE001
        logger.warning("Cagri embedding uretilemedi (call %s): %s", call.id, _exc)
    call.emotion_mismatch = _detect_emotion_mismatch(
        result.musteri_duygu_bitis, result.baskin_duygu, result.tahmini_csat
    )
    if call.emotion_mismatch:
        # Insan gozden gecirmesi icin alarm — AI kendi icinde celisiyor olabilir
        alerts.append((
            AlertType.low_score, "dusuk",
            "Duygu-sonuc uyumsuzlugu: musteri duygusu ile tahmini CSAT celisiyor, "
            "gozden gecirilmeli.",
        ))

    return ScoringOutcome(
        zeroed=bool(zeroing_reason),
        zeroing_reason=zeroing_reason,
        is_crisis=is_crisis,
        banned_word_hits=len(agent_hits),
        total_score=call.total_score,
        alerts=alerts,
    )
