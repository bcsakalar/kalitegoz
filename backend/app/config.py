from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Genel ---
    app_name: str = "KaliteGoz"
    # development | production — production'da boot'ta guvensiz ayarlar KRITIK uyarir
    environment: str = "development"
    cors_origins: str = "*"  # virgul ile ayrilmis liste veya *

    # --- Guvenlik / Auth (JWT) ---
    jwt_secret: str = "kalitegoz-dev-secret-CHANGE-IN-PROD"
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 30
    refresh_token_ttl_days: int = 14
    # Demo modunda landing'den tek tikla rol secilebilir (parolasiz demo giris)
    demo_mode: bool = True

    # --- Veritabani / kuyruk ---
    database_url: str = "postgresql+psycopg://kalitegoz:kalitegoz@postgres:5432/kalitegoz"
    redis_url: str = "redis://redis:6379/0"

    # --- Depolama ---
    storage_dir: Path = Path("/data/storage")
    watch_dir: Path = Path("/data/inbox")
    # Docker DISI (native/host) STT worker'i icin yol cevirisi. DB'de ses yolu
    # container-mutlak saklanir (/data/storage/audio/x.wav — api Docker'da yazar).
    # host_data_dir doluysa bu onek host yoluna cevrilir; Docker icinde bos kalir
    # ve ceviri yapilmaz (no-op). Ornek: HOST_DATA_DIR=D:/proj/data
    host_data_dir: str = ""
    container_data_dir: str = "/data"

    # --- STT (faster-whisper) ---
    whisper_model: str = "medium"
    whisper_device: str = "auto"  # auto | cuda | cpu
    whisper_compute_type: str = "int8"
    stt_language: str = "tr"

    # --- Diarization ---
    # Stereo kayitlarda kanal ayrimi kullanilir, pyannote'a hic girilmez.
    # Mono kayitlarda pyannote icin HuggingFace token gerekir (bossa tek konusmaci varsayilir).
    hf_token: str = ""
    pyannote_model: str = "pyannote/speaker-diarization-3.1"

    # --- LLM ---
    llm_provider: str = "ollama"  # ollama | gemini
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:7b"
    # Baglam penceresi: buyuk deger KV cache'i (RAM) sisirir. 8192, tipik bir
    # cagri transkripti + rubrik + RAG pasajlari icin yeterlidir; daha uzun
    # cagrilar zaten CHUNK_THRESHOLD_SEC ile parcalanip map-reduce edilir.
    ollama_num_ctx: int = 8192
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    # Ollama tek slotla calisir; istekler sunucuda siraya girer. CPU'da 7B model
    # yavas oldugundan timeout comert (yoksa kuyrukta bekleyen istek dusuyor).
    llm_timeout_sec: int = 900
    llm_max_retries: int = 1  # JSON parse hatasi sonrasi repair denemesi

    # --- Bilgi bankasi / RAG (embedding) ---
    embed_model: str = "nomic-embed-text"        # Ollama embedding modeli
    gemini_embed_model: str = "text-embedding-004"
    rag_enabled: bool = True  # bilgi bankasi bosken zaten devre disi kalir

    # --- Vision (gorsel denetim) ---
    vision_enabled: bool = False
    ollama_vision_model: str = "llava:7b"
    gemini_vision_model: str = "gemini-2.0-flash"

    # --- KVKK / maskeleme ---
    # Harici LLM'e (Gemini) giden metin her zaman maskelenir. Ollama yerel oldugu
    # icin varsayilan maskelemez; mask_local_llm=True ile yerelde de maskelenir.
    mask_local_llm: bool = False
    # Saklanan transkript/ozet API'den okunurken PII maskelenir mi? Kurumsal
    # (KVKK/PCI) varsayilan: acik. Yalnizca admin/kalite `reveal=true` ile ham
    # veriyi gorebilir ve bu erisim denetim gunlugune 'reveal_pii' olarak yazilir.
    pii_masking_enabled: bool = True

    # --- SSO / OIDC (kurumsal tek oturum acma) ---
    # Bos ise SSO kapalidir; parola/demo giris calismaya devam eder. Doldurulursa
    # landing'de "Kurumsal giris (SSO)" butonu cikar. Okta/Entra/Keycloak/Google
    # gibi standart OIDC saglayicilariyla calisir (Authorization Code + PKCE'siz).
    sso_enabled: bool = False
    oidc_issuer: str = ""            # orn. https://login.microsoftonline.com/<tenant>/v2.0
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "http://localhost:8000/api/v1/auth/sso/callback"
    # SSO ile gelen kullaniciya atanacak varsayilan rol ve tenant (e-posta domaini
    # eslesmezse). Guvenlik: yeni kullanicilar en dusuk yetkiyle (agent) acilir.
    oidc_default_role: str = "agent"
    oidc_default_tenant: str = "demo"
    # SSO sonrasi tarayicinin yonlendirilecegi frontend adresi
    frontend_url: str = "http://localhost:3000"

    # --- Beyaz etiket (white-label) varsayilanlari ---
    # Tenant kendi marka rengini/logosunu ayarlayana kadar kullanilir.
    brand_name: str = "KaliteGoz"
    brand_color: str = "#2563eb"

    # --- Push-ingest (santral/CRM konnektor) ---
    # Bos ise kapali. Doldurulursa X-Ingest-Key basligiyla /api/v1/ingest/call
    # endpoint'ine harici sistemler (santral webhook, CRM) ses/metadata POST eder.
    ingest_api_key: str = ""

    # --- Guvenlik durusu beyani (guvenlik sayfasinda gosterilir) ---
    # Diskte sifreleme isletim sistemi/volume seviyesinde saglanir; bu bayrak
    # yalnizca operatorun bunu etkinlestirdigini BEYAN eder (dogrulamaz).
    encryption_at_rest: bool = False

    # --- Webhook / rapor / bildirim ---
    webhook_urls: str = ""  # virgul ile ayrilmis; ihlal/kriz olaylari POST edilir
    # Slack/Teams incoming webhook URL'leri (bos ise gonderilmez). Ikisi de
    # basit {"text": ...} govdesini kabul eder; kimlik bilgisi URL'in kendisidir.
    slack_webhook_url: str = ""
    teams_webhook_url: str = ""
    # Hangi olaylar Slack/Teams'e dussun (virgulle): zeroing, crisis, banned_word,
    # low_score, score_drop. Bos ise yalnizca kritik olanlar (zeroing, crisis).
    notify_events: str = "zeroing,crisis"

    # --- SMTP zamanlanmis e-posta raporu (Dalga 7) ---
    # Bos ise gonderilmez; sadece log'a yazilir (kimlik bilgisi olmadan da calisir).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "kalitegoz@localhost"
    smtp_use_tls: bool = True
    # Haftalik ekip raporunun gidecegi adresler (virgulle). Bos ise gonderilmez.
    report_recipients: str = ""

    # IP basina dakikalik istek siniri. SPA panolari tek sayfada onlarca istek
    # atabildigi icin comert tutulur; 429 dondugunde CORS basligi yine eklenir
    # (middleware sirasi main.py'de garanti). On-prem/tek kiracili kurulumda daha
    # da yukseltilebilir veya .env RATE_LIMIT_PER_MIN ile ayarlanabilir.
    rate_limit_per_min: int = 1000

    # --- Uzun cagri chunklama (map-reduce) ---
    # Esik, OLLAMA_NUM_CTX ile uyumlu olmali: ~10 dk transkript + rubrik + RAG
    # pasajlari 8192 token baglamina sigar. Esik yukseltilirse num_ctx de artmali,
    # yoksa prompt sessizce kirpilir ve puanlama bozulur.
    chunk_threshold_sec: int = 600  # 10 dk uzeri cagrilar chunklanir
    chunk_size_sec: int = 480       # her chunk ~8 dk

    @property
    def audio_dir(self) -> Path:
        return self.storage_dir / "audio"

    @property
    def transcript_dir(self) -> Path:
        return self.storage_dir / "transcripts"

    def resolve_path(self, p: str) -> str:
        """Container-mutlak veri yolunu host yoluna cevirir (Docker DISI worker icin).

        host_data_dir bos ise (Docker icinde) yol oldugu gibi doner (no-op).
        Ornek: '/data/storage/audio/x.wav' + host_data_dir='D:/proj/data'
               -> 'D:/proj/data/storage/audio/x.wav'
        """
        if not p or not self.host_data_dir:
            return p
        cd = self.container_data_dir.rstrip("/")
        if p == cd or p.startswith(cd + "/"):
            return self.host_data_dir.rstrip("/\\") + p[len(cd):]
        return p

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def webhook_url_list(self) -> list[str]:
        return [u.strip() for u in self.webhook_urls.split(",") if u.strip()]

    @property
    def notify_event_set(self) -> set[str]:
        return {e.strip() for e in self.notify_events.split(",") if e.strip()}

    @property
    def report_recipient_list(self) -> list[str]:
        return [r.strip() for r in self.report_recipients.split(",") if r.strip()]


settings = Settings()
