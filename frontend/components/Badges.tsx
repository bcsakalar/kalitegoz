import { CATEGORY_LABELS, CHANNEL_LABELS, STATUS_LABELS, scoreStatus } from "@/lib/api";

/** Skor rozeti: renk + sayı birlikte (renk tek başına anlam taşımaz). */
export function ScoreBadge({ score, zeroed }: { score: number | null; zeroed?: boolean }) {
  if (score == null) return <span className="text-muted">—</span>;
  const status = zeroed ? "critical" : scoreStatus(score);
  return (
    <span className={`badge badge-${status}`}>
      <span className="dot" aria-hidden />
      {score.toFixed(1)}
      {zeroed && <span className="text-xs">✕</span>}
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

export function ChannelChip({ channel }: { channel: string }) {
  return (
    <span className="badge badge-neutral">
      {channel === "chat" ? "💬" : "📞"} {CHANNEL_LABELS[channel] ?? channel}
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
