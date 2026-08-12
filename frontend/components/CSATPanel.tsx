"use client";

/**
 * Kalite puanı ↔ gerçek müşteri anketi (CSAT) ilişkisi.
 *
 * ## Bu panel neden var
 *
 * Ürünün bütün doğrulaması bugüne kadar **içeriden**ydi: altın seti sistemi
 * geliştiren taraf yazdı, `predicted_csat`'ı da aynı model üretti. Hiçbiri
 * rubriğin kendisini sorgulayamaz.
 *
 * Müşterinin anket puanı dışarıdan gelir. Bu panel tek bir soruyu cevaplar:
 * **"Bizim 'kaliteli' dediğimiz çağrıda müşteri gerçekten memnun mu?"**
 *
 * ## Neden bazen sayı yerine cümle gösteriyor
 *
 * 20 çağrının altında korelasyon **gösterilmiyor**. Beş çağrıyla hesaplanan
 * r=0.9 gürültüdür; ekrana basıldığı anda birileri onu sunuma koyar. Boş
 * bırakmak, yanlış sayı göstermekten iyidir.
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CSATBand, CSATCorrelation } from "@/lib/types";

function renk(r: number | null): string {
  if (r === null) return "var(--muted)";
  const a = Math.abs(r);
  if (a >= 0.4) return "var(--status-good)";
  if (a >= 0.2) return "var(--status-warning)";
  return "var(--status-critical)";
}

export default function CSATPanel() {
  const [k, setK] = useState<CSATCorrelation | null>(null);
  const [bantlar, setBantlar] = useState<CSATBand[]>([]);
  const [hata, setHata] = useState("");

  useEffect(() => {
    api.csatCorrelation().then(setK).catch((e) => setHata(String(e)));
    api.csatDistribution().then((d) => setBantlar(d.bantlar)).catch(() => {});
  }, []);

  if (hata) return null;
  if (!k) return null;

  const doluBantlar = bantlar.filter((b) => b.n > 0);
  const enBuyukN = Math.max(1, ...doluBantlar.map((b) => b.n));

  return (
    <section className="card p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Kalite puanı ↔ müşteri memnuniyeti</h2>
        <span className="text-xs text-muted">{k.n} kesinleşmiş çağrı</span>
      </div>

      {k.korelasyon === null ? (
        <div className="mt-3 border-l-2 border-hairline pl-3">
          <p className="text-sm text-ink2">{k.mesaj}</p>
          {!k.yeterli_veri && (
            <p className="mt-2 text-xs text-muted">
              Anket sonuçlarını <code>POST /api/v1/csat/bulk</code> ile toplu
              aktarabilir ya da çağrı detayından tek tek girebilirsiniz.
            </p>
          )}
        </div>
      ) : (
        <>
          <div className="mt-3 flex items-baseline gap-3">
            <span className="text-3xl font-bold tabular-nums"
              style={{ color: renk(k.korelasyon) }}>
              {k.korelasyon.toFixed(2)}
            </span>
            <span className="text-sm text-ink2">{k.yorum} ilişki</span>
          </div>
          <p className="mt-1 text-sm text-ink2">{k.mesaj}</p>

          {k.tahmin_mae !== null && (
            <p className="mt-2 text-xs text-muted">
              Yapay zekânın CSAT tahmini ortalama <strong>{k.tahmin_mae}</strong> puan
              sapıyor ({k.tahmin_n} çağrıda, 1–5 ölçeğinde). Bu ayrı bir sorudur:
              rubrik geçerli olup tahmin kötü olabilir.
            </p>
          )}

          {k.uyari && (
            <p className="mt-3 border-l-2 p-2 text-sm"
              style={{ borderLeftColor: "var(--status-critical)" }}>
              {k.uyari}
            </p>
          )}
        </>
      )}

      {doluBantlar.length > 0 && (
        <div className="mt-4 border-t border-hairline pt-3">
          <p className="mb-2 text-xs text-muted">
            Kalite bandı başına ortalama müşteri puanı
          </p>
          <div className="space-y-1.5">
            {doluBantlar.map((b) => (
              <div key={b.bant} className="flex items-center gap-2 text-xs">
                <span className="w-16 shrink-0 text-ink2">{b.bant}</span>
                <div className="h-4 flex-1 bg-grid">
                  <div className="h-full bg-series"
                    style={{ width: `${(b.n / enBuyukN) * 100}%` }} />
                </div>
                <span className="w-20 shrink-0 text-right tabular-nums">
                  {b.ortalama_csat != null ? `${b.ortalama_csat}/5` : "—"}
                </span>
                <span className="w-12 shrink-0 text-right text-muted">n={b.n}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
