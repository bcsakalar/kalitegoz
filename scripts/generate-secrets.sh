#!/usr/bin/env bash
# =====================================================================
# KaliteGöz — sır üretici
# =====================================================================
#
# Depoyu klonlayan biri TEK KOMUTLA çalışır hale gelsin diye var.
#
#     ./scripts/generate-secrets.sh
#
# Ne yapar:
#   1. .env.example'ı şablon alır
#   2. Her sırrı kriptografik olarak güvenli şekilde üretir
#   3. Şifreleme ana anahtarını AYRI BİR DOSYAYA yazar (.env'e değil)
#   4. .env'i 0600 izniyle oluşturur
#
# Neden ana anahtar .env'de değil dosyada:
#   Ortam değişkenleri `docker inspect`, `/proc/<pid>/environ` ve çöken
#   süreçlerin log'larında görünür. Dosya, dosya sistemi izinleriyle
#   korunur. Ayrıntı: docs/KVKK-UYUM.md §3.1
#
# Mevcut .env'i ASLA sessizce ezmez — üzerine yazmak için --force gerekir.

set -euo pipefail

KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DOSYA="$KOK/.env"
ORNEK="$KOK/.env.example"
SECRET_DIZIN="$KOK/secrets"
ANAHTAR_DOSYA="$SECRET_DIZIN/kg_master_key"

ZORLA=0
[[ "${1:-}" == "--force" ]] && ZORLA=1

# ---------------------------------------------------------------- yardımcılar

hata() { printf '\n  HATA: %s\n\n' "$1" >&2; exit 1; }
bilgi() { printf '  %s\n' "$1"; }

# Rastgele, URL-güvenli sır. openssl yoksa Python'a düşer — ikisi de yoksa durur.
uret() {
  local uzunluk="${1:-48}"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 "$uzunluk" | tr -d '\n=' | tr '+/' '-_'
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c "import secrets;print(secrets.token_urlsafe($uzunluk))"
  elif command -v python >/dev/null 2>&1; then
    python -c "import secrets;print(secrets.token_urlsafe($uzunluk))"
  else
    hata "openssl veya python bulunamadı — sır üretilemiyor."
  fi
}

# .env içinde bir anahtarın değerini değiştirir (yoksa ekler).
ayarla() {
  local anahtar="$1" deger="$2" dosya="$3"
  if grep -qE "^${anahtar}=" "$dosya"; then
    # | ayracı: değerler / ve + içerebilir
    sed -i.bak "s|^${anahtar}=.*|${anahtar}=${deger}|" "$dosya" && rm -f "${dosya}.bak"
  else
    printf '%s=%s\n' "$anahtar" "$deger" >> "$dosya"
  fi
}

# ---------------------------------------------------------------- ön kontrol

printf '\n=== KaliteGöz — sır üretimi ===\n\n'

[[ -f "$ORNEK" ]] || hata ".env.example bulunamadı: $ORNEK"

if [[ -f "$ENV_DOSYA" && $ZORLA -eq 0 ]]; then
  printf '  .env zaten var: %s\n\n' "$ENV_DOSYA"
  printf '  Üzerine yazmak için:  ./scripts/generate-secrets.sh --force\n'
  printf '  (mevcut dosya .env.yedek olarak saklanır)\n\n'
  exit 0
fi

if [[ -f "$ENV_DOSYA" ]]; then
  cp "$ENV_DOSYA" "$KOK/.env.yedek"
  bilgi "Mevcut .env → .env.yedek olarak saklandı"
fi

# ---------------------------------------------------------------- üret

cp "$ORNEK" "$ENV_DOSYA"

DB_PAROLA="$(uret 24)"
JWT="$(uret 48)"
SESSION="$(uret 48)"
ADMIN_PAROLA="$(uret 12)"
ANA_ANAHTAR="$(uret 48)"
INGEST="$(uret 24)"

ayarla "POSTGRES_PASSWORD" "$DB_PAROLA" "$ENV_DOSYA"
ayarla "DATABASE_URL" "postgresql+psycopg://kalitegoz:${DB_PAROLA}@postgres:5432/kalitegoz" "$ENV_DOSYA"
ayarla "JWT_SECRET" "$JWT" "$ENV_DOSYA"
ayarla "SESSION_SECRET" "$SESSION" "$ENV_DOSYA"
ayarla "ADMIN_PASSWORD" "$ADMIN_PAROLA" "$ENV_DOSYA"
ayarla "INGEST_API_KEY" "$INGEST" "$ENV_DOSYA"

# Ana anahtar dosyaya — .env'e DEĞİL.
mkdir -p "$SECRET_DIZIN"
printf '%s' "$ANA_ANAHTAR" > "$ANAHTAR_DOSYA"
chmod 600 "$ANAHTAR_DOSYA" 2>/dev/null || true
ayarla "KG_MASTER_KEY_FILE" "/run/secrets/kg_master_key" "$ENV_DOSYA"
ayarla "KG_MASTER_KEY_ID" "$(date +%Y-%m)" "$ENV_DOSYA"
ayarla "ENCRYPTION_AT_REST" "true" "$ENV_DOSYA"

chmod 600 "$ENV_DOSYA" 2>/dev/null || true

# ---------------------------------------------------------------- özet

cat <<BILGI

  Üretilen sırlar
  ---------------
  POSTGRES_PASSWORD   .env         (24 bayt)
  JWT_SECRET          .env         (48 bayt)
  SESSION_SECRET      .env         (48 bayt)
  INGEST_API_KEY      .env         (24 bayt)
  Ana şifreleme anahtarı  secrets/kg_master_key  (48 bayt, 0600)

  GİRİŞ BİLGİSİ — bir kez gösteriliyor
  ------------------------------------
  E-posta : admin@kalitegoz.local
  Parola  : ${ADMIN_PAROLA}

  Bu parola .env içinde ADMIN_PASSWORD olarak da duruyor.
  Tüm başlangıç kullanıcıları (yönetici, süpervizör, kalite uzmanı,
  temsilci) aynı parolayı kullanır.

  Sıradaki adımlar
  ----------------
    ollama pull qwen2.5:7b-instruct
    ollama pull nomic-embed-text
    docker compose up -d --build

  .env ve secrets/ dizini .gitignore'da — commit EDİLMEZ.

BILGI
