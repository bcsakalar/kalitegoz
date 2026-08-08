"""Yonetici ROI hesaplayici — satis gorusmesinin sayisal omurgasi.

Klasik QA'da cagrilarin %2-5'i elle dinlenir; kalanlar hic denetlenmez.
KaliteGoz %100 otomatik puanlar. Bu modul "ayni kapsami elle yapmak kac kisi/
kac lira ederdi" karsilastirmasini uretir — CFO diliyle tasarruf hikayesi.
"""

from ..schemas import RoiInputs, RoiResult


def compute(i: RoiInputs) -> RoiResult:
    total_calls = i.agents * i.calls_per_agent_day * i.working_days_month
    manual_reviews = round(total_calls * i.manual_coverage_pct / 100)

    manual_hours = manual_reviews * i.minutes_per_manual_review / 60
    manual_cost = manual_hours * i.qa_hourly_cost

    # KaliteGoz TUM cagrilari puanlar. Ayni %100 kapsami ELLE yapmanin maliyeti:
    ai_equiv_hours = total_calls * i.minutes_per_manual_review / 60
    ai_equiv_cost = ai_equiv_hours * i.qa_hourly_cost

    coverage_mult = round(100 / i.manual_coverage_pct, 1) if i.manual_coverage_pct else 0.0
    # Tasarruf: mevcut elle denetim maliyeti KaliteGoz ile ortadan kalkar; ayrica
    # %100 kapsama elle ulasmak imkansiz maliyetli oldugundan asil deger orada.
    monthly_saving = manual_cost
    annual_saving = monthly_saving * 12

    return RoiResult(
        total_calls_month=total_calls,
        manual_reviews_month=manual_reviews,
        ai_coverage_pct=100.0,
        manual_hours_month=round(manual_hours, 1),
        manual_cost_month=round(manual_cost, 2),
        ai_equiv_hours_saved=round(ai_equiv_hours, 1),
        ai_equiv_cost=round(ai_equiv_cost, 2),
        coverage_multiplier=coverage_mult,
        est_monthly_saving=round(monthly_saving, 2),
        est_annual_saving=round(annual_saving, 2),
        payback_note=(
            f"Bugun cagrilarin yalnizca %{i.manual_coverage_pct:g}'i denetleniyor. "
            f"KaliteGoz ile kapsam {coverage_mult:g}x artarak %100 olur; mevcut "
            f"elle denetim ekibinin ayda ~{round(manual_hours):g} saatlik emegi "
            "otomasyona devredilir."
        ),
    )
