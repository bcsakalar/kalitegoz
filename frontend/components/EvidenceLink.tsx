"use client";

/**
 * İMZA ÖĞESİ — kanıt-transkript bağı.
 *
 * Ürünün tüm iddiası: **her puanın kanıtı var.** Bu bileşen o iddiayı
 * tıklanabilir hâle getirir: kriter kartındaki alıntıya basınca ses o saniyeye
 * atlar, transkriptte ilgili satır vurgulanır ve odak oraya gider.
 *
 * Tasarım planı §5. Cesaret tek yere harcanıyor; çevresindeki her şey sakin.
 *
 * Erişilebilirlik (web-design-guidelines):
 *   - Eylem olduğu için `<button>` — `<div onClick>` değil
 *   - `aria-label` saniyeyi sözle söyler ("Kanıta git: 5. saniye")
 *   - Hedef satır `scroll-margin-top` ile başlığın altında kalmaz
 *   - `prefers-reduced-motion` açıksa kaydırma anında yapılır
 */

import { useCallback } from "react";

export function seekToSecond(sec: number) {
  // Ses oynatıcı sayfada tek; id ile bulunur.
  const audio = document.getElementById("kg-audio") as HTMLAudioElement | null;
  if (audio) {
    audio.currentTime = Math.max(0, sec);
    void audio.play().catch(() => {
      /* otomatik oynatma engellenebilir — konum yine de ayarlandı */
    });
  }

  const line = document.querySelector<HTMLElement>(`[data-transcript-sec="${Math.round(sec)}"]`);
  if (!line) return;

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  line.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "center" });

  // Vurgu: tüm satırlardan kaldır, hedefe koy. `aria-current` ekran okuyucuya
  // "şu an burasi" der.
  document.querySelectorAll("[data-transcript-sec]").forEach((el) => {
    el.removeAttribute("data-active");
    el.removeAttribute("aria-current");
  });
  line.setAttribute("data-active", "true");
  line.setAttribute("aria-current", "true");
  line.focus({ preventScroll: true });
}

function fmt(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function EvidenceLink({
  quote, second, verified = true,
}: {
  quote: string;
  second?: number | null;
  /** Katman C alıntıyı transkriptte doğruladı mı? */
  verified?: boolean;
}) {
  const onClick = useCallback(() => {
    if (second != null) seekToSecond(second);
  }, [second]);

  if (!quote) return null;

  const clickable = second != null;
  const Tag = clickable ? "button" : "div";

  return (
    <Tag
      {...(clickable
        ? {
            type: "button" as const,
            onClick,
            "aria-label": `Kanıta git: ${fmt(second!)}`,
          }
        : {})}
      className={[
        "group flex w-full items-start gap-2 rounded-md border border-[var(--border)]",
        "bg-[var(--surface-2)] px-2.5 py-2 text-left text-[13px] leading-relaxed",
        "text-[var(--ink-2)] transition-colors",
        clickable
          ? "cursor-pointer hover:border-[var(--series-1)] hover:bg-[var(--series-1-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--series-1)]"
          : "",
      ].join(" ")}
    >
      <span
        className="mt-[3px] shrink-0 text-[var(--muted)] group-hover:text-[var(--series-1)]"
        aria-hidden="true"
      >
        ▸
      </span>
      <span className="min-w-0 flex-1">
        <span className="italic">“{quote}”</span>
        {!verified && (
          <span className="ml-1 text-[11px] font-medium not-italic text-[var(--status-serious)]">
            (doğrulanamadı)
          </span>
        )}
      </span>
      {clickable && (
        <span className="shrink-0 tabular-nums text-[11px] font-medium text-[var(--muted)] group-hover:text-[var(--series-1)]">
          {fmt(second!)}
        </span>
      )}
    </Tag>
  );
}
