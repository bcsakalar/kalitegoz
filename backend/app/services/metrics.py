"""STT ciktisindan deterministik konusma metrikleri.

LLM'e gitmeden, segment zamanlarindan hesaplanir:
- konusma sureleri / temsilci konusma orani
- soz kesme sayilari (bir konusmaci digerinin repligi bitmeden girerse)
- toplam ve en uzun sessizlik
- temsilci konusma hizi (kelime/dk)

Sonuc Call.metrics'e yazilir ve LLM prompt'una ipucu olarak eklenir
(ozellikle 'Aktif Dinleme' kriteri icin nesnel dayanak saglar).
"""

OVERLAP_TOLERANCE_SEC = 0.2  # bu kadarlik bindirme dogal kabul edilir
# Kesilen replik en az bu kadar suredir devam ediyor olmali. Konusmaci
# degisiminde olusan sinir artefaktlari "soz kesme" sayilmasin diye.
MIN_INTERRUPTED_SEC = 1.0


def compute_metrics(segments: list[dict], duration_sec: float) -> dict:
    if not segments:
        return {}

    talk = {"temsilci": 0.0, "musteri": 0.0}
    words = {"temsilci": 0, "musteri": 0}
    for seg in segments:
        spk = seg["speaker"]
        if spk not in talk:
            continue
        talk[spk] += max(0.0, seg["end"] - seg["start"])
        words[spk] += len(seg["text"].split())

    # Soz kesme: farkli konusmaci, onceki replik bitmeden giriyor.
    #
    # Iki ek sart (B3): kesilen replik en az MIN_INTERRUPTED_SEC suredir devam
    # ediyor olmali VE bindirme gercek olmali. Aksi halde segment sinirindaki
    # kucuk artefaktlar "soz kesme" sayiliyor ve temsilci yapmadigi kesmelerle
    # cezalandiriliyordu. Sayac YALNIZ kesen tarafa yazilir — musterinin kesmesi
    # temsilcinin Aktif Dinleme puanini etkileyemez.
    ordered = sorted(segments, key=lambda s: (s["start"], s["end"]))
    interruptions = {"temsilci": 0, "musteri": 0}
    for prev, cur in zip(ordered, ordered[1:]):
        if cur["speaker"] == prev["speaker"] or cur["speaker"] not in interruptions:
            continue
        overlap = prev["end"] - cur["start"]
        already_speaking = cur["start"] - prev["start"]
        if overlap > OVERLAP_TOLERANCE_SEC and already_speaking >= MIN_INTERRUPTED_SEC:
            interruptions[cur["speaker"]] += 1

    # Sessizlik: konusma araliklarinin birlesiminin disinda kalan sure
    merged: list[list[float]] = []
    for seg in ordered:
        if merged and seg["start"] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], seg["end"])
        else:
            merged.append([seg["start"], seg["end"]])
    speech = sum(en - st for st, en in merged)
    total = max(duration_sec, merged[-1][1] if merged else 0.0)
    silence = max(0.0, total - speech)

    longest_gap = merged[0][0] if merged else 0.0
    for (_, prev_end), (next_start, _) in zip(merged, merged[1:]):
        longest_gap = max(longest_gap, next_start - prev_end)
    if merged:
        longest_gap = max(longest_gap, total - merged[-1][1])

    total_talk = talk["temsilci"] + talk["musteri"]
    agent_ratio = round(talk["temsilci"] / total_talk * 100, 1) if total_talk > 0 else 0.0
    agent_wpm = (
        round(words["temsilci"] / (talk["temsilci"] / 60.0)) if talk["temsilci"] > 0 else 0
    )

    return {
        "temsilci_konusma_sn": round(talk["temsilci"], 1),
        "musteri_konusma_sn": round(talk["musteri"], 1),
        "temsilci_konusma_orani": agent_ratio,
        "temsilci_kesinti": interruptions["temsilci"],
        "musteri_kesinti": interruptions["musteri"],
        "sessizlik_sn": round(silence, 1),
        "en_uzun_sessizlik_sn": round(longest_gap, 1),
        "temsilci_kelime_dk": agent_wpm,
    }


def compute_chat_metrics(messages: list[dict]) -> dict:
    """Chat kanali metrikleri: ilk/ortalama yanit suresi, mesaj sayilari.

    messages: [{speaker, ts_sec, text}] (zamana gore sirali).
    """
    if not messages:
        return {}
    ordered = sorted(messages, key=lambda m: m["ts_sec"])
    agent_msgs = sum(1 for m in ordered if m["speaker"] == "temsilci")
    cust_msgs = sum(1 for m in ordered if m["speaker"] == "musteri")

    # Musteri mesajindan sonraki ilk temsilci yanitinin gecikmesi
    response_times: list[float] = []
    pending_customer_ts: float | None = None
    first_response: float | None = None
    for m in ordered:
        if m["speaker"] == "musteri":
            if pending_customer_ts is None:
                pending_customer_ts = m["ts_sec"]
        elif m["speaker"] == "temsilci" and pending_customer_ts is not None:
            delay = max(0.0, m["ts_sec"] - pending_customer_ts)
            response_times.append(delay)
            if first_response is None:
                first_response = delay
            pending_customer_ts = None

    avg_resp = round(sum(response_times) / len(response_times), 1) if response_times else 0.0
    return {
        "temsilci_mesaj": agent_msgs,
        "musteri_mesaj": cust_msgs,
        "ilk_yanit_sn": round(first_response, 1) if first_response is not None else 0.0,
        "ortalama_yanit_sn": avg_resp,
        "toplam_mesaj": len(ordered),
    }
