"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { tokenStore } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { useT } from "@/components/I18nProvider";

/** SSO geri dönüş: backend token'ları URL fragment'ında (#access_token=...) taşır.
 *  Fragment sunucuya/loglara gitmez; burada okuyup güvenli şekilde saklarız. */
export default function SsoCallbackPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const t = useT();
  const [err, setErr] = useState("");

  useEffect(() => {
    const hash = typeof window !== "undefined" ? window.location.hash.replace(/^#/, "") : "";
    const params = new URLSearchParams(hash);
    const access = params.get("access_token");
    const refreshTok = params.get("refresh_token");
    if (!access || !refreshTok) {
      setErr(t("sso.noToken"));
      setTimeout(() => router.replace("/login"), 1500);
      return;
    }
    tokenStore.set(access, refreshTok);
    // URL'den token'ları temizle
    window.history.replaceState(null, "", "/sso");
    refresh().then(() => router.replace("/")).catch(() => router.replace("/login"));
  }, [router, refresh]);

  return (
    <div className="grid min-h-screen place-items-center">
      <p className="text-sm text-ink2">{err || t("sso.processing")}</p>
    </div>
  );
}
