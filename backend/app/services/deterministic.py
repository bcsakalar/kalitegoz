"""KATMAN A — Deterministik ön kontrol. LLM'e sorulmadan, kodla çözülen kriterler.

## Neden bu katman var

FAZ 1 taban çizgisi ölçtü: en kötü üç kriter, deterministik olarak çözülebilecek
olanlardı (`docs/v2/FAZ-1-RAPOR.md`):

    KVKK / Aydinlatma      MAE 3.43   kappa 0.32
    Kimlik Dogrulama       MAE 3.06   kappa 0.36
    Acilis                 MAE 2.04   tam isabet %6.1

Üçü de "şu ifade geçti mi?" sorusudur — bir dize aramasıdır. LLM'e sorulduğu için
sistem, kendi doğru kanıtını gösterip tam tersi kararı verebiliyordu (B1).

## İki kural

1. **Katman A, LLM'in kararını EZER.** LLM "kurum adı söylenmedi" dese bile
   Katman A "söylendi, işte alıntısı" diyorsa sonuç Katman A'nındır.
2. **Kanıt yoksa ceza yok.** Konuşmacı bilinmiyorsa (mono kayıt, diarizasyon yok)
   kontrol `insufficient_evidence` döner — asla `not_met` demez (B29).
   Sessizce "ihlal var" demek, sistemin en pahalı hatasıdır.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from .text_tr import PhraseHit, find_any, find_phrase, normalize_tr

Decision = Literal["met", "partially_met", "not_met", "not_applicable", "insufficient_evidence"]

# Açılış ve KVKK anonsu çağrının BAŞINDA yapılır. Bu pencerenin dışında
# söylenmesi kriteri karşılamaz (KVKK: "arama başında veya veri alınmadan hemen
# önce" — Aydınlatma Tebliği m.5/1).
OPENING_WINDOW_SEC = 75.0
# Kapanış son bu kadar saniyede aranır.
CLOSING_WINDOW_SEC = 60.0


@dataclass
class Finding:
    """Bir deterministik kontrolün sonucu.

    `score` None ise karar `insufficient_evidence` demektir ve kriter puanı
    aritmetiğe KATILMAZ; insan kuyruğuna düşer.
    """

    check_key: str
    decision: Decision
    score: int | None
    rationale_tr: str
    evidence_quote: str = ""
    evidence_ts: float | None = None
    evidence_speaker: str = ""
    confidence: float = 1.0
    details: dict = field(default_factory=dict)

    @property
    def is_conclusive(self) -> bool:
        return self.decision != "insufficient_evidence"


# ---------------------------------------------------------------------------
# Segment yardımcıları
# ---------------------------------------------------------------------------

def _agent_segments(segments: list) -> list:
    return [s for s in segments if s.speaker == "temsilci"]


def _speakers_known(segments: list) -> bool:
    """Diarizasyon çalıştı mı? Hepsi 'bilinmeyen' ise konuşmacı bilgisi YOK."""
    return any(s.speaker in ("temsilci", "musteri") for s in segments)


def _window(segments: list, *, first_sec: float | None = None,
            last_sec: float | None = None, total: float = 0.0) -> list:
    if first_sec is not None:
        return [s for s in segments if s.start_sec <= first_sec]
    if last_sec is not None:
        return [s for s in segments if s.end_sec >= max(0.0, total - last_sec)]
    return segments


def _joined(segments: list) -> str:
    return " ".join(s.text for s in segments)


def _locate(segments: list, hit: PhraseHit, blob_offsets: list[tuple[int, object]]) -> tuple[str, float | None, str]:
    """Bir eşleşmenin hangi segmentte geçtiğini bul → (alıntı, saniye, konuşmacı)."""
    for offset, seg in reversed(blob_offsets):
        if hit.start >= offset:
            return seg.text.strip(), seg.start_sec, seg.speaker
    return hit.quote, None, ""


def _blob_with_offsets(segments: list) -> tuple[str, list[tuple[int, object]]]:
    parts, offsets, pos = [], [], 0
    for s in segments:
        offsets.append((pos, s))
        parts.append(s.text)
        pos += len(s.text) + 1
    return " ".join(parts), offsets


def _absence_proof(agent_segments: list, aranan: str) -> str:
    """"Yokluk" kanıtı — bir şeyin OLMADIĞINI göstermenin kanıtı.

    Sıfırlama kanıtsız yapılamaz (B5), ama "kimlik hiç doğrulanmadı" gibi bir
    tespitte gösterilecek bir alıntı YOKTUR — kanıt, aramanın kendisidir.
    Bu yüzden ne arandığı ve nerede arandığı kayda geçer; kaliteci ekranında
    "şu 12 replikte şu ifade aranmış, bulunamamış" olarak gösterilebilir.
    """
    n = len(agent_segments)
    ilk = agent_segments[0].text.strip()[:60] if agent_segments else ""
    return (
        f"Temsilcinin {n} repliğinin tamamı tarandı, {aranan} bulunamadı. "
        f"İlk replik: \"{ilk}…\""
    )


def _no_speaker_finding(check_key: str, name: str) -> Finding:
    return Finding(
        check_key=check_key, decision="insufficient_evidence", score=None,
        rationale_tr=(
            f"{name} değerlendirilemedi: kayıtta konuşmacı ayrımı yapılamadı, "
            "hangi cümleyi temsilcinin söylediği bilinmiyor."
        ),
        confidence=0.0,
    )


# ---------------------------------------------------------------------------
# 1) AÇILIŞ — kurum adı + temsilci adı
# ---------------------------------------------------------------------------

_SELF_INTRO_RE = re.compile(r"\bben\s+([A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,})", re.UNICODE)


def check_acilis(segments: list, *, brand_names: tuple[str, ...],
                 window_sec: float = OPENING_WINDOW_SEC) -> Finding:
    """Temsilci açılışta kurum adını VE kendi adını söyledi mi?

    B1'in birebir karşılığı. Kurum adının cümlenin BAŞINDA olması aranmaz —
    varlığı aranır ("İyi günler, ben Mert; Netik İletişim müşteri
    hizmetlerinden..." tam puan almalı).
    """
    if not _speakers_known(segments):
        return _no_speaker_finding("acilis", "Açılış")

    opening = _window(_agent_segments(segments), first_sec=window_sec)
    if not opening:
        return Finding("acilis", "not_met", 0,
                       "Çağrının açılışında temsilciye ait replik bulunamadı.")

    blob, offsets = _blob_with_offsets(opening)

    brand_hit = find_any(blob, brand_names) if brand_names else None
    name_match = _SELF_INTRO_RE.search(blob)

    if brand_hit and name_match:
        quote, ts, spk = _locate(opening, brand_hit, offsets)
        return Finding(
            "acilis", "met", 10,
            f"Temsilci kurum adını ve kendi adını ({name_match.group(1)}) açılışta bildirdi.",
            evidence_quote=quote, evidence_ts=ts, evidence_speaker=spk,
            details={"kurum": brand_hit.quote, "isim": name_match.group(1)},
        )
    if brand_hit and not name_match:
        quote, ts, spk = _locate(opening, brand_hit, offsets)
        return Finding(
            "acilis", "partially_met", 6,
            "Kurum adı bildirildi ancak temsilci kendi adını söylemedi.",
            evidence_quote=quote, evidence_ts=ts, evidence_speaker=spk,
            details={"kurum": brand_hit.quote, "isim": None},
        )
    if name_match and not brand_hit:
        seg0 = opening[0]
        return Finding(
            "acilis", "partially_met", 5,
            f"Temsilci adını ({name_match.group(1)}) söyledi ancak kurum adını bildirmedi.",
            evidence_quote=seg0.text.strip(), evidence_ts=seg0.start_sec,
            evidence_speaker=seg0.speaker, details={"kurum": None, "isim": name_match.group(1)},
        )

    seg0 = opening[0]
    return Finding(
        "acilis", "not_met", 1,
        "Açılışta ne kurum adı ne de temsilcinin adı bildirildi.",
        evidence_quote=seg0.text.strip(), evidence_ts=seg0.start_sec,
        evidence_speaker=seg0.speaker, details={"kurum": None, "isim": None},
    )


# ---------------------------------------------------------------------------
# 2) KVKK — iki AYRI kontrol, iki AYRI kanıt
# ---------------------------------------------------------------------------

# Aydınlatma Tebliği m.5/1: anonsun birebir aynı cümleyle yapılması beklenmez;
# ANLAM KÜMESİ eşleşmesi aranır.
KAYIT_BILDIRIMI = (
    "kayıt altına", "kayıt alt", "kayıt edil", "kaydedilmekte", "kaydediliyor",
    "kayda alın", "ses kaydı alın", "görüşme kaydedil",
)
AYDINLATMA = (
    "kvkk", "kişisel veri", "kişisel verilerin korunması", "aydınlatma metni",
    "verileriniz işlen", "veri sorumlusu",
)


def check_kvkk(segments: list, *, window_sec: float = OPENING_WINDOW_SEC) -> Finding:
    """Kayıt bildirimi VE kişisel veri aydınlatması ayrı ayrı yapıldı mı?

    Prompt dosyası §584: iki ayrı kontrol, iki ayrı kanıt. Anonsun iki farklı
    repliğe bölünmüş olması sorun değildir (tuzak-04).
    """
    if not _speakers_known(segments):
        return _no_speaker_finding("kvkk_anons", "KVKK aydınlatması")

    opening = _window(_agent_segments(segments), first_sec=window_sec)
    if not opening:
        return Finding("kvkk_anons", "not_met", 0,
                       "Çağrının açılışında temsilciye ait replik bulunamadı.")

    blob, offsets = _blob_with_offsets(opening)
    kayit = find_any(blob, KAYIT_BILDIRIMI)
    aydin = find_any(blob, AYDINLATMA)

    if kayit and aydin:
        quote, ts, spk = _locate(opening, kayit, offsets)
        return Finding(
            "kvkk_anons", "met", 10,
            "Görüşmenin kayıt altına alındığı ve kişisel verilerin işlendiği bildirildi.",
            evidence_quote=quote, evidence_ts=ts, evidence_speaker=spk,
            details={"kayit_bildirimi": kayit.quote, "aydinlatma": aydin.quote},
        )
    if kayit and not aydin:
        quote, ts, spk = _locate(opening, kayit, offsets)
        return Finding(
            "kvkk_anons", "partially_met", 5,
            "Kayıt bildirimi yapıldı ancak kişisel verilerin işlenmesine dair aydınlatma yapılmadı.",
            evidence_quote=quote, evidence_ts=ts, evidence_speaker=spk,
            details={"kayit_bildirimi": kayit.quote, "aydinlatma": None},
        )
    if aydin and not kayit:
        quote, ts, spk = _locate(opening, aydin, offsets)
        return Finding(
            "kvkk_anons", "partially_met", 4,
            "Kişisel veri aydınlatması yapıldı ancak görüşmenin kaydedildiği bildirilmedi.",
            evidence_quote=quote, evidence_ts=ts, evidence_speaker=spk,
            details={"kayit_bildirimi": None, "aydinlatma": aydin.quote},
        )

    return Finding(
        "kvkk_anons", "not_met", 0,
        "Zorunlu KVKK aydınlatması yapılmadı: ne kayıt bildirimi ne de "
        "kişisel veri işleme bilgisi verildi.",
        evidence_quote=_absence_proof(opening, "kayıt bildirimi veya KVKK aydınlatması"),
        evidence_ts=opening[0].start_sec, evidence_speaker="temsilci",
        details={"kayit_bildirimi": None, "aydinlatma": None},
    )


# ---------------------------------------------------------------------------
# 3) KİMLİK DOĞRULAMA
# ---------------------------------------------------------------------------

KIMLIK_TALEP = (
    "adınızı ve müşteri numaranızı", "adınızı ve hizmet numaranızı",
    "ad soyad ve müşteri numara", "müşteri numaranızı alabilir",
    "hizmet numaranızı alabilir", "adınızı alabilir", "ad soyadınızı alabilir",
    "kimlik numaranızı alabilir", "müşteri numaranızı öğrenebilir",
    "adınızı öğrenebilir", "sizi doğrulayabilmem",
    "müşteri numaranızı söyler", "adınızı söyler",
    # Kisa/emir kipli sorma bicimleri — cagri merkezinde yaygin.
    # "Adiniz?" tek basina zayif bir dogrulamadir ama YAPILMAMIS sayilamaz;
    # aksi halde cagri haksiz yere sifirlanir.
    "adınız", "müşteri numaranız", "hizmet numaranız",
)


def check_kimlik(segments: list) -> Finding:
    """Temsilci işlem yapmadan önce kimlik/müşteri doğrulaması istedi mi?"""
    if not _speakers_known(segments):
        return _no_speaker_finding("kimlik_dogrulama", "Kimlik doğrulama")

    agent = _agent_segments(segments)
    if not agent:
        return Finding("kimlik_dogrulama", "not_met", 0,
                       "Kayıtta temsilciye ait replik bulunamadı.")

    blob, offsets = _blob_with_offsets(agent)
    hit = find_any(blob, KIMLIK_TALEP)
    if not hit:
        return Finding(
            "kimlik_dogrulama", "not_met", 0,
            "Temsilci müşteri kimliğini/müşteri numarasını hiç doğrulamadı.",
            evidence_quote=_absence_proof(agent, "kimlik doğrulama talebi"),
        )

    quote, ts, spk = _locate(agent, hit, offsets)
    # Doğrulama işlemden ÖNCE mi yapıldı? Çağrının ilk üçte birinde bekleriz.
    total = max((s.end_sec for s in segments), default=0.0)
    if ts is not None and total > 0 and ts > total / 3:
        return Finding(
            "kimlik_dogrulama", "partially_met", 4,
            "Kimlik doğrulaması yapıldı ancak işlemin başında değil, geç aşamada istendi.",
            evidence_quote=quote, evidence_ts=ts, evidence_speaker=spk,
            details={"gecikmis": True},
        )
    return Finding(
        "kimlik_dogrulama", "met", 10,
        "Temsilci işlem öncesinde müşteri kimliğini doğruladı.",
        evidence_quote=quote, evidence_ts=ts, evidence_speaker=spk,
    )


# ---------------------------------------------------------------------------
# 4) KAPANIŞ
# ---------------------------------------------------------------------------

EK_YARDIM = (
    "başka yardımcı olabileceğim", "başka bir konuda yardımcı",
    "başka bir sorunuz", "başka bir talebiniz", "yardımcı olabileceğim başka",
    "başka bir şey var", "başka bir isteğiniz", "başka bir husus",
)
VEDA = (
    "iyi günler", "iyi akşamlar", "iyi çalışmalar", "sağlıcakla kalın",
    "aradığınız için teşekkür", "hoşça kalın", "iyi geceler",
)


def check_kapanis(segments: list, *, window_sec: float = CLOSING_WINDOW_SEC) -> Finding:
    if not _speakers_known(segments):
        return _no_speaker_finding("kapanis", "Kapanış")

    total = max((s.end_sec for s in segments), default=0.0)
    tail = _window(_agent_segments(segments), last_sec=window_sec, total=total)
    if not tail:
        return Finding("kapanis", "not_met", 0,
                       "Çağrının kapanışında temsilciye ait replik bulunamadı.")

    blob, offsets = _blob_with_offsets(tail)
    ek = find_any(blob, EK_YARDIM)
    veda = find_any(blob, VEDA)

    if ek and veda:
        quote, ts, spk = _locate(tail, ek, offsets)
        return Finding("kapanis", "met", 10,
                       "Temsilci başka bir yardım gerekip gerekmediğini sordu ve veda etti.",
                       evidence_quote=quote, evidence_ts=ts, evidence_speaker=spk)
    if veda and not ek:
        quote, ts, spk = _locate(tail, veda, offsets)
        return Finding("kapanis", "partially_met", 5,
                       "Temsilci veda etti ancak başka bir konuda yardım gerekip "
                       "gerekmediğini sormadı.",
                       evidence_quote=quote, evidence_ts=ts, evidence_speaker=spk)
    if ek and not veda:
        quote, ts, spk = _locate(tail, ek, offsets)
        return Finding("kapanis", "partially_met", 6,
                       "Başka yardım gerekip gerekmediği soruldu ancak veda kalıbı kullanılmadı.",
                       evidence_quote=quote, evidence_ts=ts, evidence_speaker=spk)

    last = tail[-1]
    return Finding("kapanis", "not_met", 1,
                   "Çağrı kapanış kalıbı kullanılmadan sonlandırıldı.",
                   evidence_quote=last.text.strip(), evidence_ts=last.start_sec,
                   evidence_speaker=last.speaker)


# ---------------------------------------------------------------------------
# 5) YASAKLI KELİME / ÜSLUP
# ---------------------------------------------------------------------------

@dataclass
class BannedHit:
    term: str
    category: str
    severity: str
    quote: str
    ts_sec: float | None
    speaker: str


def find_banned(segments: list, banned: list) -> list[BannedHit]:
    """Yasaklı kelimeleri kelime sınırına saygılı biçimde ara.

    Eski `compliance._match_in()` `stem = term[:5]` + `partial_ratio >= 60`
    kısayolunu kullanıyordu; "Kesinlikle haklısınız efendim" cümlesini
    "kesin çözülür" yasak vaadi sanıp **çağrıyı sıfırlıyordu** (B4).
    Artık `text_tr.find_phrase` kullanılıyor: kelime sınırı korunur, Türkçe ek
    toleransı yalnızca güvenli olduğu yerde açılır.
    """
    hits: list[BannedHit] = []
    for seg in segments:
        for bw in banned:
            if not bw.is_active or not (bw.term or "").strip():
                continue
            if bw.match_type == "regex":
                try:
                    m = re.search(bw.term, normalize_tr(seg.text), re.IGNORECASE)
                except re.error:
                    continue
                if not m:
                    continue
                quote = seg.text.strip()
            else:
                hit = find_phrase(seg.text, bw.term)
                if not hit:
                    continue
                quote = seg.text.strip()
            hits.append(BannedHit(
                term=bw.term, category=bw.category, severity=bw.severity,
                quote=quote, ts_sec=seg.start_sec, speaker=seg.speaker,
            ))
    return hits


def check_uslup(segments: list, banned: list) -> Finding:
    """Temsilcinin üslubu. MÜŞTERİNİN küfrü temsilciyi cezalandırmaz."""
    if not _speakers_known(segments):
        return _no_speaker_finding("yasakli_kelime", "Yasaklı kelime / üslup")

    hits = find_banned(segments, banned)
    agent_hits = [h for h in hits if h.speaker == "temsilci"]
    if not agent_hits:
        return Finding("yasakli_kelime", "met", 10,
                       "Temsilci çağrı boyunca profesyonel bir üslup kullandı; "
                       "yasaklı ifade tespit edilmedi.",
                       details={"musteri_ihlali": len([h for h in hits if h.speaker == "musteri"])})

    severe = [h for h in agent_hits if h.severity == "yuksek"]
    worst = severe[0] if severe else agent_hits[0]
    score = 0 if severe else 3
    return Finding(
        "yasakli_kelime", "not_met", score,
        f"Temsilci yasaklı ifade kullandı ({worst.category}): \"{worst.term}\".",
        evidence_quote=worst.quote, evidence_ts=worst.ts_sec, evidence_speaker="temsilci",
        details={"ihlaller": [h.term for h in agent_hits], "agir": bool(severe)},
    )


# ---------------------------------------------------------------------------
# Kayıt: check_key -> fonksiyon
# ---------------------------------------------------------------------------

def check_script(findings: dict[str, Finding]) -> Finding:
    """Zorunlu akış adımlarının tamamı uygulandı mı?

    "Script Uyumu" önceden LLM'e soruluyordu ve muğlaktı: 50 senaryonun 15'inde
    model kanıt bulamayıp `insufficient_evidence` döndü (ölçüldü). Muğlaklığın
    sebebi kriterin kendisiydi — "script" tanımı hiçbir yerde yazılı değildi.

    Burada somut bir tanım verilir: zorunlu akış = açılış + KVKK anonsu +
    kimlik doğrulama + kapanış. Dördü de zaten deterministik olarak ölçülüyor;
    bu kriter onların bileşimidir. Böylece hem muğlaklık biter hem de aynı
    olgu iki kez LLM'e sorulmaz.
    """
    parts = ("acilis", "kvkk_anons", "kimlik_dogrulama", "kapanis")
    available = [findings[k] for k in parts if k in findings]
    conclusive = [f for f in available if f.is_conclusive and f.score is not None]
    if not conclusive:
        return Finding(
            "script_uyumu", "insufficient_evidence", None,
            "Zorunlu akış adımları değerlendirilemedi (konuşmacı ayrımı yok).",
            confidence=0.0,
        )

    tamam = [f for f in conclusive if f.decision == "met"]
    eksik = [f for f in conclusive if f.decision == "not_met"]
    score = round(sum(f.score for f in conclusive) / len(conclusive))

    if not eksik and len(tamam) == len(conclusive):
        return Finding(
            "script_uyumu", "met", score,
            f"Zorunlu akışın {len(conclusive)} adımının tamamı uygulandı.",
            evidence_quote=conclusive[0].evidence_quote,
            evidence_ts=conclusive[0].evidence_ts, evidence_speaker="temsilci",
            details={"tamamlanan": len(tamam), "toplam": len(conclusive)},
        )
    worst = min(conclusive, key=lambda f: f.score)
    decision = "not_met" if len(eksik) >= 2 else "partially_met"
    return Finding(
        "script_uyumu", decision, score,
        f"Zorunlu akışın {len(conclusive)} adımından {len(eksik)} tanesi atlandı.",
        evidence_quote=worst.evidence_quote, evidence_ts=worst.evidence_ts,
        evidence_speaker="temsilci",
        details={"eksik": [f.check_key for f in eksik], "toplam": len(conclusive)},
    )


# Temsilcinin söz kesme sayısı → Aktif Dinleme için ÜST SINIR.
# Ölçülmüş bir olgunun puanı sınırlaması, LLM'in "ikna olması"na bırakılamaz:
# FAZ 2 ölçümünde model, prompt'ta kendisine verilen kesin söz kesme sayılarına
# rağmen ortalama +0.86 cömert puanladı (kappa 0.06). Sayı zaten elimizdeyse
# tavanı kodla koymak doğrudur; LLM tavanın ALTINDA serbestçe karar verir
# (empati, teyit etme, özetleme gibi ölçülemeyen kısım hâlâ ona ait).
INTERRUPTION_CEILING = ((0, 10), (2, 7), (4, 4), (99, 2))


def listening_ceiling(metrics: dict | None) -> tuple[int | None, str]:
    """Söz kesme sayısından Aktif Dinleme tavanı → (tavan, gerekçe)."""
    if not metrics or "temsilci_kesinti" not in metrics:
        return None, ""
    kes = int(metrics.get("temsilci_kesinti") or 0)
    for esik, tavan in INTERRUPTION_CEILING:
        if kes <= esik:
            if tavan >= 10:
                return None, ""  # sınır yok
            return tavan, (
                f"Temsilci müşterinin sözünü {kes} kez kesti; bu kriterin puanı "
                f"{tavan}/10 ile sınırlandı."
            )
    return None, ""


def run_all(segments: list, *, brand_names: tuple[str, ...], banned: list) -> dict[str, Finding]:
    """Tüm deterministik kontrolleri koştur → {check_key: Finding}."""
    out = {
        "acilis": check_acilis(segments, brand_names=brand_names),
        "kvkk_anons": check_kvkk(segments),
        "kimlik_dogrulama": check_kimlik(segments),
        "kapanis": check_kapanis(segments),
        "yasakli_kelime": check_uslup(segments, banned),
    }
    out["script_uyumu"] = check_script(out)  # digerlerinin bileşimi
    return out


CHECK_KEYS = ("acilis", "kvkk_anons", "kimlik_dogrulama", "kapanis",
              "yasakli_kelime", "script_uyumu")

# Rubrikteki kriter adı -> deterministik kontrol. Kriter tablosuna `check_key`
# kolonu eklenene kadar (ve eski kiracılar için) ad bazlı eşleme yedeği.
NAME_TO_CHECK = {
    "acilis": "acilis",
    "kvkk / aydinlatma": "kvkk_anons",
    "kvkk / aydınlatma": "kvkk_anons",
    "kimlik dogrulama": "kimlik_dogrulama",
    "kimlik doğrulama": "kimlik_dogrulama",
    "kapanis": "kapanis",
    "kapanış": "kapanis",
    "yasakli kelime / uslup": "yasakli_kelime",
    "yasaklı kelime / üslup": "yasakli_kelime",
    "script uyumu": "script_uyumu",
}


def check_key_for(criterion) -> str | None:
    """Bir kriter deterministik olarak çözülüyor mu? Çözülüyorsa hangi kontrolle?"""
    explicit = getattr(criterion, "check_key", None)
    if explicit:
        return explicit if explicit in CHECK_KEYS else None
    return NAME_TO_CHECK.get((criterion.name or "").strip().lower())
