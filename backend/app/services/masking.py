"""KVKK PII maskeleme.

Transkript/metin icindeki kisisel verileri (TC kimlik, telefon, kart no, IBAN,
e-posta) maskeler. Harici LLM'e (Gemini) giden HER metin bu katmandan gecer;
`mask_text` cagrilmadan harici saglayiciya veri gitmemesi kod seviyesinde
`llm.py` icinde garanti altina alinmistir.

Yaklasim: yuksek kesinlikli regex'ler (TR'ye ozgu bicimler) + Luhn dogrulamali
kart no + TC kimlik algoritma dogrulamasi (yanlis pozitifleri azaltir).
"""

import re

# --- Desenler ---
_IBAN_RE = re.compile(r"\bTR\d{2}[\s]?(?:\d{4}[\s]?){5}\d{2}\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Telefon: 0(5xx) xxx xx xx, +90..., bosluk/tire/parantez toleransli
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?90[\s-]?)?(?:0[\s-]?)?5\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)"
)
# 16 haneli kart adayi (bosluk/tire ile gruplanabilir)
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){15}\d(?!\d)")
# 11 haneli TC kimlik adayi
_TCKN_RE = re.compile(r"(?<!\d)\d{11}(?!\d)")

MASK = "[MASKELI]"


def _luhn_ok(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if len(digits) != 16:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _tckn_ok(number: str) -> bool:
    if len(number) != 11 or not number.isdigit() or number[0] == "0":
        return False
    d = [int(c) for c in number]
    d10 = ((sum(d[0:9:2]) * 7) - sum(d[1:8:2])) % 10
    if d10 != d[9]:
        return False
    d11 = sum(d[0:10]) % 10
    return d11 == d[10]


def _mask_cards(text: str) -> str:
    def repl(m: re.Match) -> str:
        return MASK if _luhn_ok(m.group(0)) else m.group(0)

    return _CARD_RE.sub(repl, text)


def _mask_tckn(text: str) -> str:
    def repl(m: re.Match) -> str:
        return MASK if _tckn_ok(m.group(0)) else m.group(0)

    return _TCKN_RE.sub(repl, text)


def mask_text(text: str) -> str:
    """Metindeki PII'yi maskeler. Sirali uygulanir (IBAN/kart once, sonra TC)."""
    if not text:
        return text
    text = _IBAN_RE.sub(MASK, text)
    text = _EMAIL_RE.sub(MASK, text)
    text = _mask_cards(text)
    text = _PHONE_RE.sub(MASK, text)
    text = _mask_tckn(text)
    return text


def has_pii(text: str) -> bool:
    """Metinde PII olup olmadigini (maskeleme oncesi) tespit eder."""
    return mask_text(text) != text
