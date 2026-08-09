"use client";

/**
 * Kurumsal Kimlik (OIDC/SSO) + Şifreleme Anahtarı — S12.
 *
 * ## Neden bu ekran var
 *
 * Önceden OIDC yalnızca ortam değişkeniyle açılabiliyordu: yönetici `.env`
 * düzenleyip konteyneri yeniden başlatmak zorundaydı. Kurumsal ihalelerde SSO
 * bir blocker maddedir ve "sunucuya SSH ile girip dosya düzenleyin" cevabı
 * satışı bitirir.
 *
 * ## İki karar burada görünür
 *
 * 1. **İstemci sırrı asla ekrana geri gelmez.** Sunucu yalnızca "girilmiş mi"
 *    bilgisini döndürür. Alan boş bırakılırsa mevcut sır korunur — böylece
 *    "issuer'ı düzeltmek için sırrı yeniden yapıştır" zorunluluğu ortadan
 *    kalkar. O zorunluluk, sırların panolarda dolaşmasının baş sebebidir.
 *
 * 2. **Kaydetmeden önce sağlayıcı denenir.** Yanlış yazılmış bir issuer
 *    kaydedilip "SSO açık" denmez; yönetici hatayı günler sonra ilk giriş
 *    denemesinde değil, o anda görür.
 *
 * Şifreleme anahtarı bu ekranda **salt okunur** gösterilir: anahtarın kendisi
 * hiçbir uçtan dönmez ve panelden girilmez. Anahtarı panele girdirmek, onu
 * tarayıcıya ve sunucu loglarına taşımak demektir. Anahtar dosyadan okunur;
 * rotasyon prosedürü `docs/KVKK-UYUM.md` §3.1'de.
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EncryptionStatus, SSOConfig } from "@/lib/types";

const KAYNAK_ETIKET: Record<string, string> = {
  yonetim_ekrani: "Yönetim ekranı",
  ortam_degiskeni: "Ortam değişkeni",
  dosya: "Anahtar dosyası",
  ortam: "Ortam değişkeni",
  yok: "Tanımlı değil",
};

export default function SSOTab() {
  const [cfg, setCfg] = useState<SSOConfig | null>(null);
  const [enc, setEnc] = useState<EncryptionStatus | null>(null);
  const [issuer, setIssuer] = useState("");
  const [clientId, setClientId] = useState("");
  const [secret, setSecret] = useState("");
  const [redirect, setRedirect] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [hata, setHata] = useState("");

  const yukle = useCallback(async () => {
    try {
      const [c, e] = await Promise.all([api.ssoConfig(), api.encryptionStatus()]);
      setCfg(c);
      setEnc(e);
      setIssuer(c.issuer);
      setClientId(c.client_id);
      setRedirect(c.redirect_uri);
      setSecret("");
      setHata("");
    } catch (err) {
      setHata(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => { yukle(); }, [yukle]);

  async function kaydet() {
    setBusy(true); setMsg(""); setHata("");
    try {
      const r = await api.ssoConfigSave({
        issuer, client_id: clientId, client_secret: secret, redirect_uri: redirect,
      });
      setMsg(r.mesaj);
      await yukle();
    } catch (err) {
      setHata(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const acik = cfg?.durum === "acik";

  return (
    <div className="space-y-5">
      {hata && (
        <p className="card border-l-4 p-3 text-sm" style={{ borderLeftColor: "var(--status-critical)" }}>
          {hata}
        </p>
      )}

      {/* ---------------- OIDC / SSO ---------------- */}
      <section className="card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">🔐 Kurumsal Kimlik (OIDC / SSO)</h2>
          {cfg && (
            <span className={`badge ${acik ? "badge-good" : "badge-neutral"}`}>
              <span className="dot" />
              {acik ? "Açık" : "Kapalı"}
              <span className="ml-1 text-xs opacity-70">
                · {KAYNAK_ETIKET[cfg.kaynak] ?? cfg.kaynak}
              </span>
            </span>
          )}
        </div>

        {cfg && <p className="mt-1 text-sm text-ink2">{cfg.mesaj}</p>}

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-ink2">
            Issuer (discovery adresi)
            <input className="input mt-1 block w-full" value={issuer}
              onChange={(e) => setIssuer(e.target.value)}
              placeholder="https://keycloak.kurum.local/realms/kurum" />
          </label>
          <label className="text-xs text-ink2">
            İstemci kimliği (client_id)
            <input className="input mt-1 block w-full" value={clientId}
              onChange={(e) => setClientId(e.target.value)} placeholder="kalitegoz" />
          </label>
          <label className="text-xs text-ink2">
            İstemci sırrı (client_secret)
            <input className="input mt-1 block w-full" type="password" value={secret}
              onChange={(e) => setSecret(e.target.value)}
              placeholder={cfg?.client_secret_girildi ? "•••••••• (kayıtlı — değiştirmek için yazın)" : "girilmedi"} />
            <span className="mt-1 block text-[11px] text-muted">
              Boş bırakırsanız kayıtlı sır korunur. Sır hiçbir zaman geri gösterilmez.
            </span>
          </label>
          <label className="text-xs text-ink2">
            Yönlendirme adresi (redirect_uri)
            <input className="input mt-1 block w-full" value={redirect}
              onChange={(e) => setRedirect(e.target.value)} />
            <span className="mt-1 block text-[11px] text-muted">
              Bu adresi sağlayıcıdaki istemci tanımına da eklemeniz gerekir.
            </span>
          </label>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <button className="btn btn-primary" disabled={busy} onClick={kaydet}>
            {busy ? "Doğrulanıyor…" : "Kaydet ve doğrula"}
          </button>
          <button className="btn" disabled={busy} onClick={yukle}>Yenile</button>
          {msg && <span className="text-sm text-ink2">{msg}</span>}
        </div>

        <p className="mt-3 text-[11px] text-muted">
          Kaydetmeden önce sağlayıcının discovery adresi denenir. Erişilemezse
          ayar yine kaydedilir ama durum &quot;uyarı&quot; döner — yanlış yazım
          ilk giriş denemesinde değil, burada fark edilir.
        </p>
      </section>

      {/* ---------------- Şifreleme anahtarı (salt okunur) ---------------- */}
      <section className="card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">🔑 Diskte Şifreleme Anahtarı</h2>
          {enc && (
            <span className={`badge ${enc.aktif ? "badge-good" : "badge-neutral"}`}>
              <span className="dot" />{enc.aktif ? "Açık" : "Kapalı"}
            </span>
          )}
        </div>

        {enc && (
          <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
            <div className="flex justify-between gap-3 border-b border-hairline py-1">
              <dt className="text-ink2">Anahtar kaynağı</dt>
              <dd className="font-medium">{KAYNAK_ETIKET[enc.kaynak] ?? enc.kaynak}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-hairline py-1">
              <dt className="text-ink2">Anahtar kimliği</dt>
              <dd className="font-medium">{enc.anahtar_kimligi || "—"}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-hairline py-1">
              <dt className="text-ink2">Rotasyon penceresi</dt>
              <dd className="font-medium">
                {enc.eski_anahtar_sayisi > 0
                  ? `${enc.eski_anahtar_sayisi} eski anahtar okunabiliyor`
                  : "Eski anahtar tanımlı değil"}
              </dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-hairline py-1">
              <dt className="text-ink2">Anahtar uzunluğu</dt>
              <dd className="font-medium">{enc.uzunluk_yeterli ? "Yeterli" : "Yetersiz / yok"}</dd>
            </div>
          </dl>
        )}

        {enc && <p className="mt-3 text-sm text-ink2">{enc.mesaj}</p>}

        <p className="mt-3 text-[11px] text-muted">
          Anahtar <strong>panelden girilmez</strong> — girilseydi tarayıcıya ve
          sunucu günlüklerine taşınırdı. Anahtar bir dosyadan okunur
          (<code>KG_MASTER_KEY_FILE</code>); kesintisiz rotasyon prosedürü ve
          KMS/Vault entegrasyonu için <code>docs/KVKK-UYUM.md</code> §3.1–3.2.
        </p>
      </section>
    </div>
  );
}
