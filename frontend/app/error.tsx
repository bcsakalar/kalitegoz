"use client";

import { useEffect } from "react";

/** Rota seviyesi hata sınırı: bir sayfa/komponent patlarsa boş ekran yerine
 *  toparlanabilir bir hata kartı gösterir. Next.js her segment için kullanır. */
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { console.error("Route error:", error); }, [error]);
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center gap-4 px-4 text-center">
      <div className="text-5xl" aria-hidden>⚠️</div>
      <h1 className="text-xl font-bold">Bir şeyler ters gitti</h1>
      <p className="text-sm text-ink2">
        Bu sayfa yüklenirken beklenmeyen bir hata oluştu. Tekrar deneyebilir veya
        ana sayfaya dönebilirsiniz.
      </p>
      {error?.message && (
        <p className="max-w-full truncate rounded-lg bg-grid/50 px-3 py-1.5 text-xs text-muted">
          {error.message}
        </p>
      )}
      <div className="flex gap-2">
        <button className="btn btn-primary" onClick={() => reset()}>Tekrar dene</button>
        <a className="btn" href="/">Ana sayfa</a>
      </div>
    </div>
  );
}
