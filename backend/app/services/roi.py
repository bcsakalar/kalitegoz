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

    # B14: ekranda "Hesapla"nin altinda GOSTERILECEK somut sonuclar.
    # Onceden hesaplayici sonuc alani uretmiyordu; artik net fayda, geri odeme
    # suresi ve kapsam farki ayri alanlar olarak doner.
    net_monthly = monthly_saving - i.platform_monthly_cost
    payback = None
    if i.platform_monthly_cost > 0 and net_monthly > 0:
        # Kac ayda kendini amorti eder: lisans / aylik net fayda
        payback = round(i.platform_monthly_cost / net_monthly, 1)
    # payback None ise iki durum vardir ve ARAYUZ BUNU AYIRT ETMELI:
    #   - lisans maliyeti girilmedi  -> hesaplanamaz
    #   - net fayda negatif          -> sadece maliyet tasarrufuyla amorti olmaz;
    #                                   deger kapsam artisindadir (%3 -> %100)
    payback_durumu = (
        "hesaplanabilir" if payback is not None
        else ("maliyet_girilmedi" if i.platform_monthly_cost <= 0
              else "maliyet_tasarrufuyla_amorti_olmaz")
    )

    formuller = [
        {"ad": "Aylik toplam cagri",
         "formul": "temsilci x gunluk cagri x calisma gunu",
         "hesap": f"{i.agents} x {i.calls_per_agent_day} x {i.working_days_month} = {total_calls}"},
        {"ad": "Elle denetlenen cagri",
         "formul": "toplam cagri x elle kapsam %",
         "hesap": f"{total_calls} x %{i.manual_coverage_pct:g} = {manual_reviews}"},
        {"ad": "Elle denetim emegi",
         "formul": "denetlenen cagri x inceleme dakikasi / 60",
         "hesap": f"{manual_reviews} x {i.minutes_per_manual_review} dk = {round(manual_hours, 1)} saat"},
        {"ad": "Aylik elle denetim maliyeti",
         "formul": "emek saati x kaliteci saatlik maliyet",
         "hesap": f"{round(manual_hours, 1)} x {i.qa_hourly_cost:g} TL = {round(manual_cost, 2)} TL"},
        {"ad": "Ayni kapsami ELLE yapmanin maliyeti",
         "formul": "toplam cagri x inceleme dakikasi / 60 x saatlik maliyet",
         "hesap": f"{round(ai_equiv_hours, 1)} saat = {round(ai_equiv_cost, 2)} TL"},
        {"ad": "Aylik net fayda",
         "formul": "elle denetim maliyeti - platform maliyeti",
         "hesap": f"{round(monthly_saving, 2)} - {i.platform_monthly_cost:g} = {round(net_monthly, 2)} TL"},
    ]

    return RoiResult(
        payback_months=payback,
        payback_durumu=payback_durumu,
        net_monthly_benefit=round(net_monthly, 2),
        coverage_gain_pct=round(100.0 - i.manual_coverage_pct, 1),
        formuller=formuller,
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
