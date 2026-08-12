"use client";

/**
 * Güvenlik & Uyum — B25.
 *
 * Eski sayfa `security-posture` uçundan **bayrak** okuyordu ve her satırı
 * yeşil/kırmızı bir nokta olarak çiziyordu. İki sorunu vardı:
 *
 *  1. Bayrak, şifrelemenin gerçekten çalıştığını kanıtlamaz.
 *  2. "Kapalı" gören kullanıcı ne yapacağını bilmiyordu — kurumsal satışta
 *     bu doğrudan blocker.
 *
 * Yeni sayfa `security-checks` uçunu kullanır: her satır **çalıştırılmış bir
 * kontrolün** sonucudur, kanıtını gösterir ve kapalıysa **nasıl açılacağını**
 * yazar.
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { ErrorState, LoadingRegion } from "@/components/EmptyState";
import type { SecurityCheck, SecurityChecks } from "@/lib/types";

const DURUM_RENK: Record<string, string> = {
  ok: "var(--status-good)",
  uyari: "var(--status-warning)",
  kapali: "var(--status-critical)",
};

const DURUM_ETIKET: Record<string, string> = {
  ok: "Açık",
  uyari: "Dikkat",
  kapali: "Kapalı",
};

function KontrolSatiri({ k }: { k: SecurityCheck }) {
  const renk = DURUM_RENK[k.durum] ?? "var(--muted)";
  return (
    <li className="border-b border-[var(--border)] py-3 last:border-0">
      <div className="flex items-start gap-3">
        <span
          className="mt-1.5 h-2.5 w-2.5 shrink-0"
          style={{ background: renk }}
          aria-hidden="true"
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-2">
            <h3 className="text-sm font-semibold">{k.baslik}</h3>
            <span className="text-[11px] font-medium" style={{ color: renk }}>
              {DURUM_ETIKET[k.durum] ?? k.durum}
            </span>
            {k.kritik && k.durum !== "ok" && (
              <span className="bg-[var(--surface-2)] px-1.5 text-[10px] font-medium text-[var(--ink-2)]">
                kurumsal satışta zorunlu
              </span>
            )}
          </div>

          {/* KANIT — kontrolün ne bulduğu. Bayrak değil, ölçüm. */}
          <p className="mt-1 text-[13px] leading-relaxed text-[var(--ink-2)]">{k.kanit}</p>

          {/* NASIL AÇILIR — kapalıysa kullanıcı ne yapacağını bilir */}
          {k.nasil_acilir && (
            <div className="mt-2 border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">
                Nasıl açılır
              </p>
              <p className="mt-0.5 text-[13px] leading-relaxed text-[var(--ink-2)]">
                {k.nasil_acilir}
              </p>
            </div>
          )}
        </div>
      </div>
    </li>
  );
}

export default function SecurityPage() {
  const [veri, setVeri] = useState<SecurityChecks | null>(null);
  const [hata, setHata] = useState(false);
  const [yukleniyor, setYukleniyor] = useState(true);

  const yukle = useCallback(async () => {
    setYukleniyor(true);
    setHata(false);
    try {
      setVeri(await api.securityChecks());
    } catch {
      setHata(true);
    } finally {
      setYukleniyor(false);
    }
  }, []);

  useEffect(() => { void yukle(); }, [yukle]);

  if (yukleniyor) {
    return (
      <div className="space-y-4">
        <PageHeader title="Güvenlik & Uyum" />
        <LoadingRegion label="Güvenlik kontrolleri çalıştırılıyor…" rows={6} />
      </div>
    );
  }

  if (hata || !veri) {
    return (
      <div className="space-y-4">
        <PageHeader title="Güvenlik & Uyum" />
        <ErrorState
          what="Güvenlik kontrolleri çalıştırılamadı."
          next="Sunucuya erişilemiyor olabilir. Tekrar deneyin; sorun sürerse API servisinin çalıştığını kontrol edin."
          onRetry={() => void yukle()}
        />
      </div>
    );
  }

  const kritikAcik = veri.kritik_acik.length;

  return (
    <div className="space-y-4">
      <PageHeader title="Güvenlik & Uyum" />

      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <p className="text-2xl font-bold tabular-nums">
              {veri.gecen}<span className="text-[var(--muted)]">/{veri.toplam}</span>
            </p>
            <p className="text-xs text-[var(--ink-2)]">kontrol geçti</p>
          </div>
          {kritikAcik > 0 && (
            <div className="border border-[var(--status-critical)] px-3 py-2">
              <p className="text-sm font-semibold text-[var(--status-critical)]">
                {kritikAcik} kritik madde kapalı
              </p>
              <p className="text-[12px] text-[var(--ink-2)]">
                Kurumsal kurulum öncesi açılması gerekir.
              </p>
            </div>
          )}
          <button type="button" onClick={() => void yukle()} className="btn btn-secondary ml-auto">
            Yeniden çalıştır
          </button>
        </div>
        <p className="mt-3 text-[11px] text-[var(--muted)]">
          Her satır, sayfa açıldığında <strong>çalıştırılan</strong> bir kontrolün sonucudur —
          ayar dosyasındaki bir bayrak değil. Ölçüm zamanı:{" "}
          <span className="tabular-nums">{veri.olculme_zamani.replace("T", " ")}</span>
        </p>
      </div>

      <div className="card p-4">
        <ul>
          {veri.kontroller.map((k) => (
            <KontrolSatiri key={k.anahtar} k={k} />
          ))}
        </ul>
      </div>
    </div>
  );
}
