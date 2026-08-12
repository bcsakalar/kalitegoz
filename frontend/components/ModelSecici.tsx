"use client";

/**
 * Canlı model seçici — sağlayıcının kendi API'sinden gelen liste.
 *
 * ## Neden `<datalist>` yerine bu
 *
 * Önceki sürüm bir `<input list=…>` + `<datalist>` idi. İki sorunu vardı:
 *
 * 1. **Liste sabitti** — elle yazılmış 4 model. OpenRouter'da 410 model var;
 *    kullanıcı listede olmayanı ancak tam adını ezbere yazarak seçebiliyordu.
 * 2. **`<datalist>` aramada zayıf** — tarayıcıya göre davranışı değişir,
 *    açıklama (bağlam, fiyat) gösteremez, kaç seçenek olduğunu söylemez.
 *
 * Bu bileşen listeyi canlı çeker, aranabilir gösterir ve her modelin
 * bağlam/fiyat bilgisini yanına yazar.
 *
 * ## Serbest metin neden hâlâ mümkün
 *
 * Sağlayıcı yeni bir model çıkardığında liste güncellenene kadar
 * kullanıcının eli bağlanmasın. Listede olmayan bir ad yazılabilir; bu
 * durumda "listede yok — yine de kullanılacak" uyarısı gösterilir.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useT } from "@/components/I18nProvider";
import type { ModelListesi, ModelBilgi } from "@/lib/types";

const KAYNAK_ANAHTAR: Record<string, string> = {
  canli: "model.sourceLive",
  onbellek: "model.sourceCache",
  yedek: "model.sourceFallback",
};

export default function ModelSecici({
  saglayici, tur, deger, onChange, etkinModel,
}: {
  saglayici: string;
  tur: "llm" | "embed" | "vision";
  deger: string;
  onChange: (v: string) => void;
  /** Seçim yapılmamışsa sistemin fiilen kullandığı model */
  etkinModel?: string;
}) {
  const t = useT();
  const [liste, setListe] = useState<ModelListesi | null>(null);
  const [yukleniyor, setYukleniyor] = useState(false);
  const [arama, setArama] = useState("");
  const [acik, setAcik] = useState(false);
  const kapsayici = useRef<HTMLDivElement>(null);

  const yukle = useCallback(async (tazele = false) => {
    setYukleniyor(true);
    try {
      setListe(await api.aiModels(saglayici, tur, tazele));
    } catch {
      setListe({ saglayici, tur, kaynak: "yedek", hata: t("model.fetchFailed"), modeller: [] });
    } finally {
      setYukleniyor(false);
    }
  }, [saglayici, tur, t]);

  useEffect(() => { void yukle(); }, [yukle]);

  // Dışarı tıklayınca kapat
  useEffect(() => {
    function disari(e: MouseEvent) {
      if (kapsayici.current && !kapsayici.current.contains(e.target as Node)) setAcik(false);
    }
    document.addEventListener("mousedown", disari);
    return () => document.removeEventListener("mousedown", disari);
  }, []);

  const modeller = liste?.modeller ?? [];
  const suzulmus = useMemo(() => {
    const q = arama.trim().toLowerCase();
    if (!q) return modeller.slice(0, 60);
    return modeller.filter((m) =>
      m.id.toLowerCase().includes(q) || m.ad.toLowerCase().includes(q)).slice(0, 60);
  }, [modeller, arama]);

  const listedeVar = !deger || modeller.some((m) => m.id === deger);

  /** Sayisal alanlari okunur tek satira cevirir; birim ve kelime i18n'den. */
  function bilgi(m: ModelBilgi): string {
    const p: string[] = [];
    if (m.boyut_gb) p.push(`${m.boyut_gb} GB`);
    // Asagi yuvarlama bilincli: 32768 baglam alanda "32K" diye bilinir,
    // yuvarlayinca "33K" cikiyor ve modeli taniyan kullaniciya yanlis geliyor.
    if (m.baglam) p.push(`${Math.floor(m.baglam / 1000)}K ${t("model.context")}`);
    if (m.ucretsiz) p.push(t("model.free"));
    else if (m.fiyat_m) p.push(`$${m.fiyat_m}/M`);
    return p.join(" · ");
  }

  function sec(m: ModelBilgi) {
    onChange(m.id);
    setAcik(false);
    setArama("");
  }

  return (
    <div className="relative" ref={kapsayici}>
      <div className="flex gap-1">
        <input
          className="input w-full"
          value={deger}
          placeholder={etkinModel ? `${etkinModel} (${t("model.active")})` : t("model.placeholder")}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setAcik(true)}
          spellCheck={false}
          autoComplete="off"
        />
        <button type="button" className="btn shrink-0 !px-2" onClick={() => setAcik((a) => !a)}
          aria-label={t("model.openList")} title={t("model.openList")}>
          {yukleniyor ? "…" : "▾"}
        </button>
      </div>

      {/* Durum satırı — kullanıcı hangi listeye baktığını bilmeli */}
      <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted">
        {liste && (
          <span>
            {modeller.length} {t("model.countWord")} · {t(KAYNAK_ANAHTAR[liste.kaynak] ?? "")}
          </span>
        )}
        <button type="button" className="underline hover:text-ink2"
          onClick={() => void yukle(true)} disabled={yukleniyor}>
          {t("model.refresh")}
        </button>
        {!deger && etkinModel && (
          <span>· {t("model.inUse")}: <strong className="text-ink2">{etkinModel}</strong></span>
        )}
        {deger && !listedeVar && (
          <span style={{ color: "var(--status-warning)" }}>
            · {t("model.notInList")}
          </span>
        )}
      </div>

      {liste?.hata && (
        <p className="mt-1 text-[11px]" style={{ color: "var(--status-warning)" }}>
          {liste.hata}
        </p>
      )}

      {acik && (
        <div className="absolute z-30 mt-1 w-full border border-hairline-strong bg-surface shadow-[var(--shadow)]">
          <div className="border-b border-hairline p-2">
            <input className="input w-full text-sm" placeholder={t("model.search")} value={arama}
              onChange={(e) => setArama(e.target.value)} autoFocus spellCheck={false} />
          </div>
          <div className="max-h-64 overflow-y-auto">
            {suzulmus.length === 0 ? (
              <p className="p-3 text-sm text-muted">
                {modeller.length > 0
                  ? t("model.noMatch")
                  : liste?.hata || t("model.empty")}
              </p>
            ) : (
              suzulmus.map((m) => (
                <button key={m.id} type="button" onClick={() => sec(m)}
                  className={`flex w-full items-baseline gap-2 border-b border-hairline px-3 py-2 text-left text-sm hover:bg-surface2 ${
                    m.id === deger ? "bg-series/10" : ""}`}>
                  <span className="min-w-0 flex-1 truncate font-mono text-xs">{m.id}</span>
                  {m.kurulu && (
                    <span className="shrink-0 text-[10px]" style={{ color: "var(--status-good)" }}>
                      {t("model.installed")}
                    </span>
                  )}
                  {bilgi(m) && (
                    <span className="shrink-0 text-[10px] text-muted">{bilgi(m)}</span>
                  )}
                </button>
              ))
            )}
            {modeller.length > suzulmus.length && !arama && (
              <p className="px-3 py-2 text-[11px] text-muted">
                {t("model.more").replace("{n}", String(modeller.length - suzulmus.length))}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
