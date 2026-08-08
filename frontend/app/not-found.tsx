import Link from "next/link";

/** 404 — bulunamayan rota. Kullanıcıyı boş ekranda bırakmaz. */
export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center gap-4 px-4 text-center">
      <div className="text-6xl font-black text-series" aria-hidden>404</div>
      <h1 className="text-xl font-bold">Sayfa bulunamadı</h1>
      <p className="text-sm text-ink2">
        Aradığınız sayfa taşınmış veya hiç var olmamış olabilir.
      </p>
      <Link href="/" className="btn btn-primary">Ana sayfaya dön</Link>
    </div>
  );
}
