/** Stat tile: etiket + deger (+ opsiyonel alt bilgi). */
export default function StatTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="card p-4">
      <div className="text-sm text-ink2">{label}</div>
      <div className="mt-1 text-3xl font-semibold">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}
