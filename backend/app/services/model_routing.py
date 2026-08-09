"""Kriter bazlı model yönlendirmesi — S2c.

## Sorun

Ölçüldü: yerel `qwen2.5:7b-instruct` nesnel kriterlerde kusursuz (kappa
0.94–1.00) ama dört öznel kriterde rastlantıdan zor ayırt ediliyor
(kappa 0.08–0.20).

Nesnel kriterler zaten **Katman A**'da, yani kodda çözülüyor — model onlara
hiç bakmıyor. Yani modelin tüm işi zaten öznel kriterler. Bu durumda "tüm
çağrı için tek model" seçmek gereksiz bir ödünleşme: her çağrıyı 14B ile
puanlamak, kodun zaten çözdüğü işi de yavaşlatır.

## Çözüm

Kriter **grubu** bazında model seçimi. Öznel kriterler daha büyük modele,
gerisi hızlı modele gider. İki model paralel değil, sırayla çalışır; ek
gecikme yalnızca öznel grup için ödenir.

## Ne zaman devreye girer

Yalnızca `subjective_model` yapılandırıldığında **ve** o model erişilebilir
olduğunda. Model yoksa sessizce varsayılan modele düşer — bir kurulumun
14B indirmemiş olması sistemi durdurmaz.

Yönlendirmenin işe yarayıp yaramadığı **ölçülerek** karara bağlanır:
`scripts/golden/compare_models.py`.
"""

from __future__ import annotations

import logging

from .ai_config import AIResolved

logger = logging.getLogger(__name__)

# Ölçülen kappa'sı düşük, yargı gerektiren kriterler. Büyük model buraya.
SUBJECTIVE_CRITERIA = {
    "Aktif Dinleme",
    "İhtiyaç Analizi",
    "Çözüm / Yönlendirme",
    "Bilgi Doğruluğu",
    # ASCII varyantlar (eski kurulumlar migration'dan önce)
    "Ihtiyac Analizi", "Cozum / Yonlendirme", "Bilgi Dogrulugu",
}


def is_subjective(criterion_name: str) -> bool:
    return (criterion_name or "").strip() in SUBJECTIVE_CRITERIA


def split_by_model(criteria: list) -> tuple[list, list]:
    """Kriterleri (öznel, diğer) diye ayır — grup oluşturmadan ÖNCE.

    Ayrım grup oluşturmadan önce yapılmalı: aksi halde bir grupta hem öznel
    hem nesnel kriter olur ve grup tek bir modele gitmek zorunda kalır.
    """
    oznel = [c for c in criteria if is_subjective(c.name)]
    diger = [c for c in criteria if not is_subjective(c.name)]
    return oznel, diger


def subjective_model_name(tenant_settings: dict | None) -> str | None:
    """Kurumun öznel kriterler için seçtiği model. None = yönlendirme kapalı."""
    if not isinstance(tenant_settings, dict):
        return None
    ai = tenant_settings.get("ai") or {}
    ad = (ai.get("subjective_model") or "").strip()
    return ad or None


def resolve_for(base: AIResolved, model_name: str | None) -> AIResolved:
    """Aynı sağlayıcı, farklı model ile yeni bir çözümlenmiş config üret."""
    if not model_name or model_name == base.model:
        return base
    return AIResolved(
        provider=base.provider, model=model_name, base_url=base.base_url,
        api_key=base.api_key, kind=base.kind, external=base.external,
    )


def available(model_name: str, base_url: str, timeout: float = 3.0) -> bool:
    """Model gerçekten kurulu mu? Yoksa yönlendirme yapılmaz.

    Bir kurulumun 14B indirmemiş olması sistemi durdurmamalı; sessizce
    varsayılan modele düşer ve bir kez uyarı loglanır.
    """
    import httpx

    try:
        resp = httpx.get(f"{base_url}/api/tags", timeout=timeout)
        resp.raise_for_status()
        adlar = {m.get("name", "") for m in resp.json().get("models", [])}
        return model_name in adlar or f"{model_name}:latest" in adlar
    except Exception as exc:  # noqa: BLE001
        logger.warning("Model listesi alinamadi (%s): %s", base_url, exc)
        return False
