import type { Metadata } from "next";
import AlertToast from "@/components/AlertToast";
import AuthProvider from "@/components/AuthProvider";
import I18nProvider from "@/components/I18nProvider";
import LiveAlertsProvider from "@/components/LiveAlertsProvider";
import Shell from "@/components/Shell";
import ThemeProvider from "@/components/ThemeProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "KaliteGöz — Kalite Yönetim Platformu",
  description: "Çok kanallı çağrı merkezi kalite analiz ve yönetim platformu",
};

// Tema, React hydrate olmadan ONCE uygulanmali; yoksa koyu temada bir kare
// beyaz "flash" olur. Bu script <head>'de senkron calisir.
const THEME_INIT = `
(function(){
  try {
    var t = localStorage.getItem('kg_theme') || 'system';
    if (t !== 'system') document.documentElement.setAttribute('data-theme', t);
    var l = localStorage.getItem('kg_lang');
    if (l) document.documentElement.lang = l;
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
      </head>
      <body className="min-h-screen">
        <ThemeProvider>
          <I18nProvider>
            <AuthProvider>
              {/* LiveAlerts AuthProvider'in ICINDE olmali: baglanmak icin
                  kullanicinin rolunu ve token'ini bilmesi gerekiyor. */}
              <LiveAlertsProvider>
                <Shell>{children}</Shell>
                <AlertToast />
              </LiveAlertsProvider>
            </AuthProvider>
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
