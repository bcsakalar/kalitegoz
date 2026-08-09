"""Diskte şifreleme — zarf şifreleme (envelope encryption).

## Neden uygulama seviyesinde?

Şifreli disk/volume, sunucuya erişen birine karşı korumaz: disk mount edilmişse
dosyalar düz görünür. Çağrı kayıtları TC kimlik, telefon ve IBAN içerir; KVKK
açısından bunların **uygulama katmanında** şifrelenmesi beklenir.

## Anahtar nerede?

`KG_MASTER_KEY` ortam değişkeninde — **`.env` dosyasında DEĞİL.** `.env`
depoya yakın durur ve yedeklere sızar; ana anahtar ayrı yönetilmelidir
(systemd `EnvironmentFile`, Docker secret, KMS/Vault).

Anahtar yoksa şifreleme **kapalıdır** ve güvenlik sayfası bunu açıkça
"kapalı" olarak gösterir. Sessizce düz metin yazıp "şifreli" demek, güvenlik
sayfasını yalancı yapardı — B25'in kökeni tam olarak buydu.

## Biçim

    KGENC1:<base64(nonce)>:<base64(ciphertext)>

Önek sayesinde şifreli ve düz veriler bir arada yaşayabilir; mevcut kurulumlar
kademeli olarak şifrelemeye geçebilir (okuma her ikisini de anlar).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
from pathlib import Path

logger = logging.getLogger(__name__)

PREFIX = "KGENC1"
ENV_KEY = "KG_MASTER_KEY"
_NONCE_LEN = 16


class CryptoError(RuntimeError):
    pass


# S12: anahtar kaynagi onceligi.
#
#   1. KG_MASTER_KEY_FILE  -> dosya yolu (Docker secret / K8s secret mount)
#   2. KG_MASTER_KEY       -> dogrudan ortam degiskeni (kucuk kurulumlar)
#
# `.env` DOSYASI BIR ANAHTAR KAYNAGI DEGILDIR ve olmamalidir: `.env` depoya
# yakin durur, yedeklere ve imajlara sizar. Docker secret varsayilan olarak
# /run/secrets/ altina mount edilir ve imaja girmez.
KEY_FILE_ENV = "KG_MASTER_KEY_FILE"
# Anahtar kimligi: rotasyonda hangi anahtarla sifrelendigini bilmek icin.
KEY_ID_ENV = "KG_MASTER_KEY_ID"
# Eski anahtarlar (rotasyon sirasinda okuma icin): virgulle ayrilmis dosya yollari
OLD_KEYS_ENV = "KG_MASTER_KEY_OLD_FILES"


def _oku_dosya(yol: str) -> str:
    try:
        return Path(yol).read_text(encoding="utf-8").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Anahtar dosyasi okunamadi (%s): %s", yol, exc)
        return ""


def _ham_anahtar() -> tuple[str, str]:
    """(anahtar, kaynak) — kaynak: dosya | ortam | yok."""
    yol = os.environ.get(KEY_FILE_ENV, "").strip()
    if yol:
        ham = _oku_dosya(yol)
        if ham:
            return ham, "dosya"
    ham = os.environ.get(ENV_KEY, "").strip()
    if ham:
        return ham, "ortam"
    return "", "yok"


def _turet(ham: str) -> bytes | None:
    if len(ham) < 32:
        logger.warning("Ana anahtar cok kisa (>=32 karakter olmali) — sifreleme KAPALI")
        return None
    return hashlib.sha256(ham.encode("utf-8")).digest()


def _master_key() -> bytes | None:
    ham, _ = _ham_anahtar()
    return _turet(ham) if ham else None


def _eski_anahtarlar() -> list[bytes]:
    """Rotasyon sirasinda ESKI anahtarla sifrelenmis veriyi okuyabilmek icin.

    Rotasyon tek seferde tamamlanmaz: yeni anahtar devreye girer, veri
    kademeli olarak yeniden sifrelenir. Bu arada eski anahtarla yazilmis
    kayitlar hala okunabilmelidir.
    """
    yollar = [y.strip() for y in os.environ.get(OLD_KEYS_ENV, "").split(",") if y.strip()]
    out = []
    for y in yollar:
        ham = _oku_dosya(y)
        k = _turet(ham) if ham else None
        if k:
            out.append(k)
    return out


def key_status() -> dict:
    """Anahtar durumu — yonetim ekrani ve guvenlik sayfasi icin."""
    ham, kaynak = _ham_anahtar()
    ok, mesaj = (False, "Anahtar tanimli degil")
    if ham:
        ok, mesaj = self_test()
    return {
        "aktif": ok,
        "kaynak": kaynak,
        "kaynak_aciklama": {
            "dosya": f"{KEY_FILE_ENV} ile dosyadan okunuyor (onerilen)",
            "ortam": f"{ENV_KEY} ortam degiskeninden okunuyor",
            "yok": "Anahtar tanimli degil; sifreleme kapali",
        }[kaynak],
        "anahtar_kimligi": os.environ.get(KEY_ID_ENV, "").strip() or None,
        "eski_anahtar_sayisi": len(_eski_anahtarlar()),
        "mesaj": mesaj,
        "uzunluk_yeterli": len(ham) >= 32 if ham else False,
    }


def is_enabled() -> bool:
    """Şifreleme fiilen açık mı? Bayrak değil, **anahtarın varlığı** belirler."""
    return _master_key() is not None


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """HMAC-SHA256 tabanlı sayaç modu anahtar akışı.

    Harici bağımlılık istemeden (cryptography paketi kurulu olmayabilir)
    kimliği doğrulanmış şifreleme sağlar. Anahtar akışı nonce+sayaçtan türetilir;
    aynı nonce iki kez kullanılmadığı sürece güvenlidir (nonce rastgeledir).
    """
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _mac(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    return hmac.new(key, b"mac" + nonce + ciphertext, hashlib.sha256).digest()[:16]


def encrypt_bytes(data: bytes) -> bytes:
    key = _master_key()
    if key is None:
        return data
    nonce = secrets.token_bytes(_NONCE_LEN)
    ct = bytes(a ^ b for a, b in zip(data, _keystream(key, nonce, len(data))))
    return b"%s:%s:%s:%s" % (
        PREFIX.encode(), base64.b64encode(nonce),
        base64.b64encode(_mac(key, nonce, ct)), base64.b64encode(ct),
    )


def decrypt_bytes(blob: bytes) -> bytes:
    if not blob.startswith(PREFIX.encode() + b":"):
        return blob  # sifrelenmemis eski veri — kademeli gecise izin ver
    key = _master_key()
    if key is None:
        raise CryptoError(
            f"Sifreli veri var ama {ENV_KEY} tanimli degil; veri okunamaz."
        )
    try:
        _, b_nonce, b_mac, b_ct = blob.split(b":", 3)
        nonce, mac, ct = (base64.b64decode(b_nonce), base64.b64decode(b_mac),
                          base64.b64decode(b_ct))
    except Exception as exc:  # noqa: BLE001
        raise CryptoError(f"Sifreli veri bozuk: {exc}") from exc

    # Once aktif anahtar, sonra ESKI anahtarlar denenir (rotasyon penceresi).
    for aday in [key, *_eski_anahtarlar()]:
        if hmac.compare_digest(mac, _mac(aday, nonce, ct)):
            return bytes(a ^ b for a, b in zip(ct, _keystream(aday, nonce, len(ct))))
    raise CryptoError(
        "Butunluk dogrulamasi basarisiz — veri degistirilmis ya da anahtar yanlis. "
        f"Rotasyon yapildiysa eski anahtari {OLD_KEYS_ENV} ile tanimlayin."
    )


def encrypt_text(text: str) -> str:
    if not is_enabled():
        return text
    return encrypt_bytes(text.encode("utf-8")).decode("ascii")


def decrypt_text(value: str) -> str:
    if not value or not value.startswith(PREFIX + ":"):
        return value
    return decrypt_bytes(value.encode("ascii")).decode("utf-8")


def encrypt_file(path: str | Path) -> bool:
    """Bir dosyayı yerinde şifrele. Doner: işlem yapıldı mı."""
    p = Path(path)
    if not is_enabled() or not p.exists():
        return False
    raw = p.read_bytes()
    if raw.startswith(PREFIX.encode() + b":"):
        return False  # zaten sifreli
    p.write_bytes(encrypt_bytes(raw))
    return True


def read_file(path: str | Path) -> bytes:
    """Şifreli ya da düz dosyayı oku — çağıran tarafın ayrım yapması gerekmez."""
    return decrypt_bytes(Path(path).read_bytes())


def self_test() -> tuple[bool, str]:
    """GERÇEK kontrol: şifrele → çöz → doğrula.

    Güvenlik sayfası bunu çağırır. Bir bayrak okumak yerine sistemin
    şifrelemeyi gerçekten yapabildiği **kanıtlanır**.
    """
    if not is_enabled():
        return False, (
            f"{ENV_KEY} tanimli degil. Sifreleme kapali; ses ve transkriptler "
            "diskte duz metin olarak duruyor."
        )
    try:
        ornek = "TCKN 12345678901 · IBAN TR33 0006 1005 1978 6457 8413 26"
        sifreli = encrypt_text(ornek)
        if sifreli == ornek or not sifreli.startswith(PREFIX):
            return False, "Sifreleme uygulanmadi (cikti duz metin)."
        if decrypt_text(sifreli) != ornek:
            return False, "Cozme dogrulamasi basarisiz."
        # Butunluk kontrolu gercekten calisiyor mu?
        bozuk = sifreli[:-4] + "AAAA"
        try:
            decrypt_text(bozuk)
        except CryptoError:
            pass
        else:
            return False, "Butunluk dogrulamasi degisiklige tepki vermiyor."
        return True, "Sifrele/coz/butunluk dogrulamasi basarili."
    except Exception as exc:  # noqa: BLE001
        return False, f"Sifreleme kendini test edemedi: {exc}"
