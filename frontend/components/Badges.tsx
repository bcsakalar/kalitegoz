import { CATEGORY_LABELS, CHANNEL_LABELS, STATUS_LABELS, scoreStatus } from "@/lib/api";

/** Skor rozeti: renk + sayı birlikte (renk tek başına anlam taşımaz). */
/**
 * Puan rozeti — eşik renkleri TEK MERKEZDEN (`scoreStatus`).
 *
 * B5: sıfırlanmış çağrıda rozet yalnız "0.0" göstermez; **"0 — sıfırlayıcı
 * ihlal"** der ve tooltip'te gerekçeyi verir. Çağrılar listesinde 0.0 gören
 * kullanıcı neden sıfırlandığını anlayamıyordu.
 */
export function ScoreBadge({
  score, zeroed, zeroingReason,
}: {
  score: number | null;
  zeroed?: boolean;
  zeroingReason?: string | null;
}) {
  if (score == null) return <span className="text-muted">—</span>;
  if (zeroed) {
    return (
      <span
        className="badge badge-critical whitespace-nowrap"
        title={zeroingReason || "Kritik kriter eşiğin altında kaldığı için çağrı puanı sıfırlandı."}
      >
        <span className="dot" aria-hidden />
        <span className="tabular-nums">0</span>
        <span className="text-[10px] font-medium"> — sıfırlayıcı ihlal</span>
      </span>
    );
  }
  return (
    <span className={`badge badge-${scoreStatus(score)}`}>
      <span className="dot" aria-hidden />
      <span className="tabular-nums">{score.toFixed(1)}</span>
    </span>
  );
}

export function StatusChip({ status }: { status: string }) {
  const cls =
    status === "done" ? "badge-good"
      : status === "failed" ? "badge-critical"
        : status === "pending" ? "badge-neutral" : "badge-info";
  return (
    <span className={`badge ${cls}`}>
      <span className="dot" aria-hidden />
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

export function CategoryChip({ category }: { category: string | null }) {
  if (!category) return <span className="text-muted">—</span>;
  return <span className="badge badge-neutral">{CATEGORY_LABELS[category] ?? category}</span>;
}

/**
 * B22: `compact` modda kanal, ROZET değil küçük bir simgedir.
 *
 * 24 satırlık bir listede 24 kez tekrarlanan "📞 Sesli" rozeti hiçbir bilgi
 * taşımaz — hepsi aynıysa ayırt edici değildir, sadece göz yorar. Simge,
 * karışık kanallı listede farkı yine gösterir ama satırı şişirmez.
 */
export function ChannelChip({ channel, compact = false }: { channel: string; compact?: boolean }) {
  const label = CHANNEL_LABELS[channel] ?? channel;
  if (compact) {
    return (
      <span
        className="align-middle text-[11px] text-muted"
        title={label}
        aria-label={label}
        role="img"
      >
        {channel === "chat" ? "💬" : "📞"}
      </span>
    );
  }
  return (
    <span className="badge badge-neutral">
      <span aria-hidden="true">{channel === "chat" ? "💬" : "📞"}</span> {label}
    </span>
  );
}

export function CrisisChip() {
  return (
    <span className="badge badge-critical">
      <span className="dot" aria-hidden /> Kriz
    </span>
  );
}

export function ZeroedChip() {
  return (
    <span className="badge badge-critical">
      <span className="dot" aria-hidden /> Sıfırlayıcı ihlal
    </span>
  );
}
