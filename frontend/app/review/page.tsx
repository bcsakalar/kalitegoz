"use client";

/**
 * İnceleme Kuyruğum — FAZ 3.3'ün arayüzü.
 *
 * Hedef: **bir çağrı incelemesi 8-10 dakikadan 2 dakikaya insin.** Bu ürünün
 * ROI vaadi. Tasarım kararları bu hedeften çıkıyor:
 *
 *  - Kart yığını değil, **tek çağrı odaklı akış**: aç → incele → kaydet →
 *    otomatik sıradaki. Backend `submit` yanıtında sıradaki çağrıyı döner,
 *    yani kaydetme ile sıradakinin gelmesi arasında ikinci istek yok.
 *  - **Klavye birinci sınıf**: J/K kriterler arası, A onayla, D düzelt,
 *    Space oynat/durdur, Enter kaydet. Fareye dokunmadan tamamlanabilir.
 *  - Solda ses + transkript sabit, sağda kriter kartları — kanıta tıklayınca
 *    ses o saniyeye atlar (imza öğesi).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import EvidenceLink, { seekToSecond } from "@/components/EvidenceLink";
import { EmptyState, ErrorState, LoadingRegion } from "@/components/EmptyState";

interface KriterKarti {
  score_id: number;
  criterion_id: number | null;
  ad: string;
  grup: string;
  agirlik: number;
  ai_puani: number | null;
  karar: string;
  guven: number;
  gerekce: string;
  kanit: string;
  kanit_saniye: number | null;
  kanit_dogrulandi: boolean;
  katman: string;
  duzeltilmis_puan: number | null;
  incelendi: boolean;
}

interface Cagri {
  call_id: number;
  ref: string;
  dosya: string;
  temsilci: string | null;
  toplam_puan: number | null;
  sifirlandi: boolean;
  sifirlama_gerekcesi: string | null;
  sifirlama_kaniti: string | null;
  qa_durumu: string;
  kuyruk_sebepleri: string[];
  sure_sn: number | null;
  ozet: string | null;
  kriterler: KriterKarti[];
  transkript: { idx: number; konusmaci: string; saniye: number; metin: string }[];
  kalan_kuyruk: number;
}

const SEBEP_ETIKET: Record<string, string> = {
  critical: "Sıfırlayıcı ihlal",
  crisis: "Kriz sinyali",
  low_confidence: "Düşük güven / yetersiz kanıt",
  low_score: "Alt %10 dilim",
  emotion_mismatch: "Duygu–puan uyumsuzluğu",
  random: "Rastgele örneklem",
  new_agent: "Yeni temsilci",
  manual: "Elle seçildi",
};

const GEREKCE_KODLARI = [
  { kod: "kanit_yanlis", etiket: "Gösterilen kanıt hatalı" },
  { kod: "baglam_kacirildi", etiket: "Çağrının bağlamı kaçırıldı" },
  { kod: "kriter_yanlis_yorumlandi", etiket: "Kriter yanlış yorumlandı" },
  { kod: "stt_hatasi", etiket: "Transkript hatası" },
  { kod: "rubrik_mugak", etiket: "Kriter tanımı net değil" },
  { kod: "diger", etiket: "Diğer" },
];

type Karar = { yeni_puan: number | null; gerekce_kodu: string | null; not: string };

export default function ReviewQueuePage() {
  const [cagri, setCagri] = useState<Cagri | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<string | null>(null);
  const [kararlar, setKararlar] = useState<Record<number, Karar>>({});
  const [aktifIdx, setAktifIdx] = useState(0);
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const [duyuru, setDuyuru] = useState("");
  const kartRefs = useRef<(HTMLDivElement | null)[]>([]);

  const yukle = useCallback(async () => {
    setYukleniyor(true);
    setHata(null);
    try {
      const d = await api.reviewNext();
      setCagri(d);
      setKararlar({});
      setAktifIdx(0);
    } catch {
      setHata("kuyruk");
    } finally {
      setYukleniyor(false);
    }
  }, []);

  useEffect(() => { void yukle(); }, [yukle]);

  const kriterler = cagri?.kriterler ?? [];
  const tamamlanan = useMemo(
    () => kriterler.filter((k) => kararlar[k.score_id] !== undefined).length,
    [kriterler, kararlar],
  );
  const hepsiKarara_baglandi = kriterler.length > 0 && tamamlanan === kriterler.length;

  const onayla = useCallback((idx: number) => {
    const k = kriterler[idx];
    if (!k) return;
    setKararlar((p) => ({ ...p, [k.score_id]: { yeni_puan: null, gerekce_kodu: null, not: "" } }));
    setDuyuru(`${k.ad} onaylandı`);
    setAktifIdx((i) => Math.min(i + 1, kriterler.length - 1));
  }, [kriterler]);

  const duzelt = useCallback((idx: number, puan: number, kod: string, not = "") => {
    const k = kriterler[idx];
    if (!k) return;
    setKararlar((p) => ({ ...p, [k.score_id]: { yeni_puan: puan, gerekce_kodu: kod, not } }));
    setDuyuru(`${k.ad} ${puan} olarak düzeltildi`);
  }, [kriterler]);

  const kaydet = useCallback(async () => {
    if (!cagri || !hepsiKarara_baglandi || kaydediliyor) return;
    setKaydediliyor(true);
    try {
      const govde = {
        kararlar: kriterler.map((k) => ({
          score_id: k.score_id,
          yeni_puan: kararlar[k.score_id]?.yeni_puan ?? null,
          gerekce_kodu: kararlar[k.score_id]?.gerekce_kodu ?? null,
          not: kararlar[k.score_id]?.not ?? "",
        })),
        kapanis_notu: "",
      };
      const sonraki = await api.reviewSubmit(cagri.call_id, govde);
      setCagri(sonraki);
      setKararlar({});
      setAktifIdx(0);
      setDuyuru(sonraki ? "Kaydedildi, sıradaki çağrı açıldı" : "Kaydedildi, kuyruk boşaldı");
    } catch {
      setHata("kaydet");
    } finally {
      setKaydediliyor(false);
    }
  }, [cagri, hepsiKarara_baglandi, kaydediliyor, kriterler, kararlar]);

  // --- Klavye akisi: fareye dokunmadan tamamlanabilir ---
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const hedef = e.target as HTMLElement;
      if (hedef.tagName === "INPUT" || hedef.tagName === "TEXTAREA" || hedef.tagName === "SELECT") return;

      if (e.key === "j" || e.key === "J" || e.key === "ArrowDown") {
        e.preventDefault();
        setAktifIdx((i) => Math.min(i + 1, kriterler.length - 1));
      } else if (e.key === "k" || e.key === "K" || e.key === "ArrowUp") {
        e.preventDefault();
        setAktifIdx((i) => Math.max(i - 1, 0));
      } else if (e.key === "a" || e.key === "A") {
        e.preventDefault();
        onayla(aktifIdx);
      } else if (e.key === " ") {
        e.preventDefault();
        const a = document.getElementById("kg-audio") as HTMLAudioElement | null;
        if (a) a.paused ? void a.play() : a.pause();
      } else if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        void kaydet();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [aktifIdx, kriterler.length, onayla, kaydet]);

  useEffect(() => {
    kartRefs.current[aktifIdx]?.scrollIntoView({ block: "nearest" });
  }, [aktifIdx]);

  if (yukleniyor) {
    return (
      <div className="p-4">
        <PageHeader title="İnceleme Kuyruğum" />
        <LoadingRegion label="Kuyruk yükleniyor…" rows={6} />
      </div>
    );
  }

  if (hata === "kuyruk") {
    return (
      <div className="p-4">
        <PageHeader title="İnceleme Kuyruğum" />
        <ErrorState
          what="İnceleme kuyruğu yüklenemedi."
          next="Bağlantınızı kontrol edip tekrar deneyin. Sorun sürerse sistem yöneticisine bildirin."
          onRetry={() => void yukle()}
        />
      </div>
    );
  }

  if (!cagri) {
    return (
      <div className="p-4">
        <PageHeader title="İnceleme Kuyruğum" />
        <EmptyState
          title="Onay bekleyen çağrı yok."
          reason="Yapay zekâ puanladığı çağrılarda risk kuralı tetiklendiğinde bu kuyruk dolar: sıfırlayıcı ihlal, kriz sinyali, düşük güvenli kriter ya da rastgele örneklem."
        />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col">
      {/* Ekran okuyucu duyurusu — async guncellemeler aria-live ister */}
      <p className="sr-only" aria-live="polite">{duyuru}</p>

      {/* Karar seridi: tek satirda ozet + birincil eylem */}
      <div className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] bg-[var(--surface)] px-4 py-2.5">
        <span className="font-mono text-sm font-semibold tabular-nums">{cagri.ref}</span>
        <span className="text-sm text-[var(--ink-2)]">{cagri.temsilci ?? "—"}</span>
        {cagri.sifirlandi ? (
          <span
            className="rounded px-2 py-0.5 text-xs font-semibold text-white"
            style={{ background: "var(--status-critical)" }}
            title={cagri.sifirlama_gerekcesi ?? undefined}
          >
            0 — sıfırlayıcı ihlal
          </span>
        ) : (
          <span className="text-sm font-semibold tabular-nums">
            {cagri.toplam_puan?.toFixed(1) ?? "—"}
          </span>
        )}
        <div className="flex flex-wrap gap-1">
          {cagri.kuyruk_sebepleri.map((s) => (
            <span key={s} className="rounded bg-[var(--surface-2)] px-1.5 py-0.5 text-[11px] text-[var(--ink-2)]">
              {SEBEP_ETIKET[s] ?? s}
            </span>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs tabular-nums text-[var(--muted)]">
            {tamamlanan}/{kriterler.length} kriter · kuyrukta {cagri.kalan_kuyruk}
          </span>
          <button
            type="button"
            onClick={() => void kaydet()}
            disabled={!hepsiKarara_baglandi || kaydediliyor}
            className="btn btn-primary disabled:opacity-50"
          >
            {kaydediliyor ? "Kaydediliyor…" : "Kaydet ve sıradaki"}
          </button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        {/* SOL: ses + transkript */}
        <section className="flex min-h-0 flex-col border-r border-[var(--border)]" aria-label="Ses ve transkript">
          <div className="border-b border-[var(--border)] p-3">
            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <audio
              id="kg-audio"
              controls
              className="w-full"
              src={`/api/v1/calls/${cagri.call_id}/audio`}
            />
            {cagri.ozet && <p className="mt-2 text-[13px] text-[var(--ink-2)]">{cagri.ozet}</p>}
          </div>
          <ol className="min-h-0 flex-1 overflow-y-auto p-3 text-[13px]">
            {cagri.transkript.map((g) => (
              <li
                key={g.idx}
                data-transcript-sec={Math.round(g.saniye)}
                tabIndex={-1}
                onClick={() => seekToSecond(g.saniye)}
                className="mb-1 scroll-mt-16 rounded px-2 py-1 transition-colors data-[active=true]:bg-[var(--series-1-soft)] data-[active=true]:ring-1 data-[active=true]:ring-[var(--series-1)]"
              >
                <span className="mr-2 tabular-nums text-[11px] text-[var(--muted)]">
                  {String(Math.floor(g.saniye / 60)).padStart(2, "0")}:
                  {String(Math.floor(g.saniye % 60)).padStart(2, "0")}
                </span>
                <span className={`mr-1.5 text-[11px] font-semibold uppercase ${
                  g.konusmaci === "temsilci" ? "text-[var(--series-1)]" : "text-[var(--muted)]"
                }`}>
                  {g.konusmaci === "temsilci" ? "Temsilci" : g.konusmaci === "musteri" ? "Müşteri" : "Konuşmacı"}
                </span>
                <span className="text-[var(--ink-2)]">{g.metin}</span>
              </li>
            ))}
          </ol>
        </section>

        {/* SAG: kriter kartlari */}
        <section className="min-h-0 overflow-y-auto p-3" aria-label="Kriter kartları">
          {cagri.sifirlandi && cagri.sifirlama_gerekcesi && (
            <div className="mb-3 rounded-md border border-[var(--status-critical)] bg-[var(--surface-2)] p-3">
              <p className="text-sm font-semibold text-[var(--status-critical)]">
                Sıfırlayıcı ihlal
              </p>
              <p className="mt-1 text-[13px] text-[var(--ink-2)]">{cagri.sifirlama_gerekcesi}</p>
              {cagri.sifirlama_kaniti && (
                <p className="mt-1.5 text-[12px] italic text-[var(--ink-2)]">
                  “{cagri.sifirlama_kaniti}”
                </p>
              )}
            </div>
          )}

          <ul className="space-y-2">
            {kriterler.map((k, i) => (
              <li key={k.score_id}>
                <KriterKartiGorunum
                  ref={(el) => { kartRefs.current[i] = el; }}
                  kriter={k}
                  aktif={i === aktifIdx}
                  karar={kararlar[k.score_id]}
                  onSec={() => setAktifIdx(i)}
                  onOnayla={() => onayla(i)}
                  onDuzelt={(p, kod, not) => duzelt(i, p, kod, not)}
                />
              </li>
            ))}
          </ul>

          <p className="mt-4 text-[11px] text-[var(--muted)]">
            Klavye: <kbd>J</kbd>/<kbd>K</kbd> kriterler arası · <kbd>A</kbd> onayla ·
            {" "}<kbd>Space</kbd> oynat/durdur · <kbd>Ctrl</kbd>+<kbd>Enter</kbd> kaydet
          </p>
        </section>
      </div>
    </div>
  );
}

import { forwardRef } from "react";

const KriterKartiGorunum = forwardRef<HTMLDivElement, {
  kriter: KriterKarti;
  aktif: boolean;
  karar?: Karar;
  onSec: () => void;
  onOnayla: () => void;
  onDuzelt: (puan: number, kod: string, not: string) => void;
}>(function KriterKartiGorunum({ kriter, aktif, karar, onSec, onOnayla, onDuzelt }, ref) {
  const [acik, setAcik] = useState(false);
  const [puan, setPuan] = useState(kriter.ai_puani ?? 5);
  const [kod, setKod] = useState(GEREKCE_KODLARI[0].kod);
  const [not, setNot] = useState("");

  const yetersiz = kriter.karar === "insufficient_evidence";
  const renk = yetersiz
    ? "var(--status-serious)"
    : (kriter.ai_puani ?? 0) >= 8 ? "var(--status-good)"
    : (kriter.ai_puani ?? 0) >= 5 ? "var(--status-warning)"
    : "var(--status-critical)";

  return (
    <div
      ref={ref}
      onClick={onSec}
      /* Odaklanabilir: klavye kullanicisi Tab ile karta gelince o kart aktif
         olur. J/K zaten calisiyor; bu, Tab ile gezinmeyi de tutarli kilar. */
      tabIndex={0}
      onFocus={onSec}
      data-active={aktif}
      className="rounded-md border border-[var(--border)] bg-[var(--surface)] p-3 transition-colors duration-150 motion-reduce:transition-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--series-1)] data-[active=true]:border-[var(--series-1)] data-[active=true]:ring-1 data-[active=true]:ring-[var(--series-1)]"
    >
      <div className="flex items-start gap-2">
        <span className="h-2 w-2 shrink-0 translate-y-1.5 rounded-full" style={{ background: renk }} aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <h3 className="text-sm font-semibold">{kriter.ad}</h3>
            <span className="text-[11px] text-[var(--muted)]">ağırlık {kriter.agirlik}</span>
            {kriter.katman === "A" && (
              <span className="rounded bg-[var(--surface-2)] px-1 text-[10px] text-[var(--muted)]" title="Kod tarafından belirlendi">
                deterministik
              </span>
            )}
          </div>
          <p className="mt-0.5 text-[13px] text-[var(--ink-2)]">{kriter.gerekce}</p>
        </div>
        <span className="shrink-0 text-lg font-bold tabular-nums" style={{ color: renk }}>
          {yetersiz ? "—" : (karar?.yeni_puan ?? kriter.ai_puani)}
        </span>
      </div>

      {kriter.kanit && (
        <div className="mt-2">
          <EvidenceLink quote={kriter.kanit} second={kriter.kanit_saniye} verified={kriter.kanit_dogrulandi} />
        </div>
      )}

      {yetersiz && (
        <p className="mt-2 text-[12px] text-[var(--status-serious)]">
          Yeterli kanıt bulunamadı — bu kriterin puanını siz vermelisiniz.
        </p>
      )}

      <div className="mt-2 flex items-center gap-2">
        {karar === undefined ? (
          <>
            <button type="button" onClick={(e) => { e.stopPropagation(); onOnayla(); }} className="btn btn-secondary text-xs">
              Onayla
            </button>
            <button type="button" onClick={(e) => { e.stopPropagation(); setAcik((v) => !v); }} className="btn btn-secondary text-xs">
              Düzelt
            </button>
          </>
        ) : (
          <span className="text-xs font-medium text-[var(--status-good)]">
            {karar.yeni_puan === null ? "Onaylandı" : `Düzeltildi: ${karar.yeni_puan}`}
          </span>
        )}
      </div>

      {acik && karar === undefined && (
        <div className="mt-2 space-y-2 rounded-md bg-[var(--surface-2)] p-2" onClick={(e) => e.stopPropagation()}>
          <label className="block text-xs">
            <span className="mb-1 block font-medium">Yeni puan</span>
            <input
              type="number" min={0} max={10} value={puan}
              onChange={(e) => setPuan(Number(e.target.value))}
              className="input w-20 tabular-nums"
            />
          </label>
          <label className="block text-xs">
            <span className="mb-1 block font-medium">Gerekçe</span>
            <select value={kod} onChange={(e) => setKod(e.target.value)} className="input w-full">
              {GEREKCE_KODLARI.map((g) => <option key={g.kod} value={g.kod}>{g.etiket}</option>)}
            </select>
          </label>
          <label className="block text-xs">
            <span className="mb-1 block font-medium">Not (opsiyonel)</span>
            <input
              value={not} onChange={(e) => setNot(e.target.value)}
              placeholder="Örn. müşteri kesmişti…" className="input w-full"
            />
          </label>
          <button
            type="button"
            onClick={() => { onDuzelt(puan, kod, not); setAcik(false); }}
            className="btn btn-primary w-full text-xs"
          >
            Düzeltmeyi uygula
          </button>
        </div>
      )}
    </div>
  );
});
