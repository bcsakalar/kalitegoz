/**
 * Dört durumun üçü: boş, hata, yükleniyor.
 *
 * `web-design-guidelines`:
 *   - "Handle empty states — don't render broken UI for empty arrays"
 *   - "Loading states end with …"
 *   - "Error messages include fix/next step, not just problem statement"
 *
 * Boş durum şablonu (tasarım planı §7): **ne yok + neden + tek eylem.**
 * Beş farklı tonda beş ayrı "Veri yok" metni yerine tek bileşen — B19'un çözümü
 * metin yazmak değil, metnin şeklini zorunlu kılmaktır.
 */

import type { ReactNode } from "react";

export function EmptyState({
  title, reason, action, icon,
}: {
  /** NE yok — "Henüz inceleme yok" */
  title: string;
  /** NEDEN — "Çağrılar puanlandıkça kuyruk dolar." */
  reason: string;
  /** TEK eylem (opsiyonel) */
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
      {icon && <div className="text-[var(--muted)]" aria-hidden="true">{icon}</div>}
      <p className="text-[15px] font-semibold text-[var(--ink)]">{title}</p>
      <p className="max-w-md text-sm leading-relaxed text-[var(--ink-2)]">{reason}</p>
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}

export function ErrorState({
  what, next, onRetry, retryLabel = "Tekrar dene",
}: {
  /** NE OLDU — özür yok, "bir şeyler ters gitti" yok */
  what: string;
  /** NE YAPMALI */
  next: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-3 px-6 py-10 text-center"
    >
      <p className="text-[15px] font-semibold text-[var(--status-critical)]">{what}</p>
      <p className="max-w-md text-sm leading-relaxed text-[var(--ink-2)]">{next}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn btn-secondary mt-1">
          {retryLabel}
        </button>
      )}
    </div>
  );
}

/**
 * İskelet yükleyici. Spinner yalnız 1 sn'den kısa işlemlerde kullanılır
 * (tasarım planı §7); liste/kart yüklemesinde iskelet, düzen kaymasını
 * (CLS) da engeller.
 */
export function Skeleton({ rows = 3, className = "" }: { rows?: number; className?: string }) {
  return (
    <div className={`space-y-2 ${className}`} aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-9 animate-pulse rounded-md bg-[var(--surface-2)]" />
      ))}
    </div>
  );
}

/** Ekran okuyucuya "yükleniyor" bilgisini geçirir; görsel iskeletin eşi. */
export function LoadingRegion({ label = "Yükleniyor…", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div aria-busy="true" aria-live="polite">
      <span className="sr-only">{label}</span>
      <Skeleton rows={rows} />
    </div>
  );
}
