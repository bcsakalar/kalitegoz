/** Kök yükleme durumu: rota geçişlerinde boş ekran yerine iskelet/spinner. */
export default function Loading() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center" role="status" aria-live="polite">
      <span className="inline-block h-8 w-8 animate-spin border-2 border-hairline border-t-series" aria-hidden />
      <span className="sr-only">Yükleniyor…</span>
    </div>
  );
}
