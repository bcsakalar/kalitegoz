"use client";

/** Kök seviye hata sınırı: layout dahil her şey patlarsa devreye girer.
 *  Kendi <html>/<body>'sini render etmek ZORUNDADIR (layout devre dışıdır). */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="tr">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 0 }}>
        <div style={{
          minHeight: "100vh", display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", gap: 16, padding: 24,
          textAlign: "center", background: "#0b0f17", color: "#e5e7eb",
        }}>
          <div style={{ fontSize: 48 }} aria-hidden>⚠️</div>
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Uygulama hatası</h1>
          <p style={{ fontSize: 14, color: "#9ca3af", maxWidth: 420 }}>
            Beklenmeyen bir hata oluştu. Sayfayı yenileyin; sorun sürerse yöneticinizle iletişime geçin.
          </p>
          <button onClick={() => reset()} style={{
            padding: "8px 16px", borderRadius: 8, border: "1px solid #374151",
            background: "#2563eb", color: "#fff", cursor: "pointer", fontSize: 14,
          }}>Tekrar dene</button>
        </div>
      </body>
    </html>
  );
}
