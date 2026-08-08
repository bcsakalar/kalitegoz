"""Profesyonel ornek cagri ureteci — 28 tam-detayli, puanlanmis cagri.

Gercek Turkce cagri merkezi diyaloglari (sesli + chat), kriter bazli puan +
gerekce + kanit, KVKK ihlali / kriz / yanlis bilgi / yasakli kelime senaryolari
dahil. Dogrudan DB'ye yazar (STT/LLM'siz — aninda). Panolar, karneler, analitik,
kocluk, benzer-cagri ve ihlal ozellikleri profesyonelce dolar.

Kullanim (api container icinde):
    docker exec kalitegoz-api-1 python scripts/seed_pro_calls.py
"""

import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, "/srv")  # api container calisma dizini

from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Agent, Call, CallStatus, Campaign, Channel, Criterion, Score, Segment, Tenant, Violation,
)

RNG = random.Random(2026)

# --- Senaryo kutuphanesi: profesyonel Turkce diyaloglar ---
# tier: mukemmel | iyi | orta | zayif ; overrides: {kriter_adi: puan}
# turns: (speaker, text) — speaker: 'temsilci' | 'musteri'
S = [
    dict(channel="voice", category="bilgi", tier="mukemmel", title="Tarife bilgilendirme",
         emotion="memnun", churn="dusuk", ces=1.5, csat=4.8, sent=("notr", "olumlu"),
         intents=["tarife-bilgi", "kampanya"],
         coaching="Ornek acilis ve KVKK bilgilendirmesi. Boyle devam.",
         turns=[
             ("temsilci", "Netix Iletisim'e hos geldiniz, ben Ayse. Gorusmemiz kalite amacli kayit altina aliniyor, kisisel verileriniz KVKK kapsaminda islenir. Size nasil yardimci olabilirim?"),
             ("musteri", "Merhaba, mevcut tarifemi ogrenmek ve daha uygun bir sey var mi diye bakmak istiyorum."),
             ("temsilci", "Tabii, once kimliginizi dogrulayalim; ad soyad ve dogum yilinizi alabilir miyim?"),
             ("musteri", "Fatma Yilmaz, 1985."),
             ("temsilci", "Tesekkurler Fatma Hanim. Su an 20 GB'lik Standart tarifedesiniz. Kullaniminiza bakinca 30 GB'lik Avantaj tarifesi ayni ucrete daha uygun; ilk 3 ay 50 TL indirimli."),
             ("musteri", "Kulaga guzel geliyor, gecis yapalim."),
             ("temsilci", "Hemen tanimliyorum. Islem tamam, onay SMS'i geldi. Baska yardimci olabilecegim bir konu var mi?"),
             ("musteri", "Yok, cok tesekkurler."),
             ("temsilci", "Rica ederim, iyi gunler dilerim Fatma Hanim."),
         ]),
    dict(channel="voice", category="fatura", tier="iyi", title="Fatura itirazi cozuldu",
         emotion="notr", churn="dusuk", ces=2.5, csat=4.2, sent=("olumsuz", "olumlu"),
         intents=["fatura-itiraz", "ekstre"],
         coaching="Itiraz cozumu iyi. Ihtiyac analizinde biraz daha derinlesebilirsin.",
         turns=[
             ("temsilci", "Netix Iletisim, ben Mehmet. Gorusme kayit altindadir. Buyurun."),
             ("musteri", "Faturam bu ay 90 lira fazla gelmis, itiraz etmek istiyorum."),
             ("temsilci", "Uzgunum, hemen bakalim. Kimlik dogrulamasi icin musteri numaranizi alabilir miyim?"),
             ("musteri", "44551122."),
             ("temsilci", "Tesekkurler. Ekstrenizi inceledim; yurt disi dolasim ucreti yansimis. Talebiniz disindaysa iade baslatabilirim."),
             ("musteri", "Ben yurt disina cikmadim ki."),
             ("temsilci", "Anladim, o zaman haksiz yansima. 90 lirayi iade ediyorum, 3 is gunu icinde faturaniza yansir. Ayrica dolasimi kapatiyorum."),
             ("musteri", "Tamam, tesekkur ederim."),
             ("temsilci", "Rica ederim, baska bir konu var mi? Iyi gunler."),
         ]),
    dict(channel="voice", category="iptal", tier="orta", title="Iptal - elde tutma zayif",
         emotion="memnuniyetsiz", churn="yuksek", ces=3.5, csat=2.8, sent=("olumsuz", "olumsuz"),
         intents=["iptal-talep", "rakip-teklif"],
         coaching="Elde tutma zayif kaldi. Rakip teklife karsi somut deger sunmalisin.",
         overrides={"Cozum / Yonlendirme": 5, "Ihtiyac Analizi": 5},
         turns=[
             ("temsilci", "Netix, ben Zeynep. Buyurun."),
             ("musteri", "Hattimi iptal etmek istiyorum, rakip firma daha ucuz veriyor."),
             ("temsilci", "Peki, iptal talebinizi alabilirim."),
             ("musteri", "Baska teklifiniz yok mu yani?"),
             ("temsilci", "Kampanyalara bakabilirim ama su an garanti bir sey diyemem."),
             ("musteri", "O zaman iptal edin."),
             ("temsilci", "Tamam, iptal talebinizi olusturdum. Iyi gunler."),
         ]),
    dict(channel="voice", category="ariza", tier="iyi", title="Ariza - net cozum",
         emotion="notr", churn="dusuk", ces=2.0, csat=4.3, sent=("olumsuz", "olumlu"),
         intents=["baglanti-sorunu", "modem"],
         coaching="Teknik yonlendirme net ve adim adimdi. Cok iyi.",
         turns=[
             ("temsilci", "Netix teknik destek, ben Emre. Gorusme kayittadir. Nasil yardimci olabilirim?"),
             ("musteri", "Internetim surekli kesiliyor, cok sinir bozucu."),
             ("temsilci", "Anliyorum, hemen cozelim. Modemin isik durumunu birlikte kontrol edelim; kirmizi yanan bir isik var mi?"),
             ("musteri", "Evet, DSL isigi kirmizi."),
             ("temsilci", "Tamam, hattinizda senkron sorunu var. Modemi 30 saniye kapatip acalim, bu sirada hatti da uctan yeniliyorum."),
             ("musteri", "Actim, simdi yesil yandi."),
             ("temsilci", "Harika. Hattinizi 24 saat izlemeye aldim; tekrar kesilirse teknik ekip ucretsiz gelir. Baska bir sey var mi?"),
             ("musteri", "Yok, tesekkurler."),
             ("temsilci", "Rica ederim, iyi gunler."),
         ]),
    dict(channel="voice", category="sikayet", tier="zayif", title="KVKK ihlali - kimlik atlandi",
         emotion="ofkeli", churn="yuksek", ces=4.5, csat=1.5, sent=("olumsuz", "olumsuz"),
         intents=["yanlis-bilgi", "kaba-uslup"], is_crisis=False,
         overrides={"KVKK / Aydinlatma": 1, "Kimlik Dogrulama": 1},
         coaching="KRITIK: Acilista KVKK bilgilendirmesi ve kimlik dogrulamasi YAPILMADI. Hassas islemde bu sifirlayici ihlaldir.",
         violations=[("zeroing", "kvkk", "yuksek", "temsilci", "Kimlik dogrulamadan islem yapildi", "kimlik dogrulama"),
                     ("zeroing", "kvkk", "yuksek", "temsilci", "Kayit/aydinlatma bildirimi yok", "KVKK aydinlatma")],
         turns=[
             ("temsilci", "Alo, buyurun."),
             ("musteri", "Hesabimda bir degisiklik yapmak istiyorum, adres guncellemesi."),
             ("temsilci", "Tamam, yeni adresi soyleyin hemen gireyim."),
             ("musteri", "Ata mahallesi, 15. sokak no 4."),
             ("temsilci", "Girdim, oldu."),
             ("musteri", "Kimligimi falan sormayacak misiniz?"),
             ("temsilci", "Gerek yok, hallettim iste. Baska?"),
         ]),
    dict(channel="voice", category="sikayet", tier="orta", title="Kriz - ofkeli musteri",
         emotion="ofkeli", churn="yuksek", ces=4.8, csat=2.0, sent=("olumsuz", "notr"),
         intents=["bekleme-suresi", "sikayet"], is_crisis=True,
         coaching="Kriz iyi yonetildi; empati kuruldu ve tansiyon dusuruldu. Cozum suresi netlestirilmeli.",
         turns=[
             ("temsilci", "Netix, ben Selin. Gorusme kayittadir. Buyurun."),
             ("musteri", "Uc gundur internetim yok, dorduncu kez ariyorum! Bu rezalet, avukatima danisacagim!"),
             ("temsilci", "Yasadiginiz magduriyet icin gercekten cok uzgunum, sizi anliyorum. Bu kabul edilemez, hemen sahiplenip cozuyorum."),
             ("musteri", "Herkes ayni seyi soyluyor ama cozen yok!"),
             ("temsilci", "Hakli kizginlik. Kaydinizi oncelikli ariza olarak isaretledim, teknik ekip bugun 17:00'den once adresinizde olacak. Ayrica kesinti gunleriniz faturaniza yansitilmayacak."),
             ("musteri", "Bugun gelmezlerse?"),
             ("temsilci", "Bizzat takip edip sizi arayacagim, dogrudan hattim uzerinden. Soz veriyorum bu isi bugun kapatiyoruz."),
             ("musteri", "Peki, bekliyorum o zaman."),
             ("temsilci", "Tesekkur ederim anlayisiniz icin, en kisa surede donuyorum."),
         ]),
    dict(channel="voice", category="bilgi", tier="zayif", title="Yanlis bilgi - iade suresi",
         emotion="memnuniyetsiz", churn="orta", ces=3.8, csat=2.4, sent=("notr", "olumsuz"),
         intents=["iade", "cayma"],
         overrides={"Bilgi Dogrulugu": 2},
         coaching="KRITIK bilgi hatasi: Cayma suresi 14 gundur, temsilci 30 gun dedi. Dokuman: Iade/Cayma Proseduru.",
         violations=[("banned_word", "yanlis_bilgi", "orta", "temsilci", "Iade suresi 30 gun beyani (dogrusu 14)", "30 gun")],
         turns=[
             ("temsilci", "Netix, ben Burak. Kayit altindayiz, buyurun."),
             ("musteri", "Gecen hafta modem aldim, iade etmek istiyorum. Sure ne kadar?"),
             ("temsilci", "Iade suresi 30 gundur, rahat rahat getirebilirsiniz."),
             ("musteri", "Emin misiniz? 14 gun diye biliyordum."),
             ("temsilci", "Yok yok, bizde 30 gun. Kargoyu da siz odersiniz bu arada."),
             ("musteri", "Kargoyu ben mi odeyecegim?"),
             ("temsilci", "Evet, iade kargosu musteriye ait."),
             ("musteri", "Peki tamam."),
         ]),
    dict(channel="voice", category="fatura", tier="zayif", title="Kaba uslup - yasakli kelime",
         emotion="ofkeli", churn="yuksek", ces=4.6, csat=1.6, sent=("olumsuz", "olumsuz"),
         intents=["fatura-itiraz", "kaba-uslup"],
         overrides={"Yasakli Kelime / Uslup": 1, "Aktif Dinleme": 3},
         coaching="Temsilci musteriye kucumseyici konustu ('anlamiyorsun'). Uslup egitimi sart.",
         violations=[("banned_word", "kucumseme", "yuksek", "temsilci", "Siz anlamiyorsunuz efendim", "anlamiyorsun")],
         turns=[
             ("temsilci", "Netix, ben Okan. Buyurun."),
             ("musteri", "Faturami anlamadim, neden bu kadar yuksek?"),
             ("temsilci", "Efendim burada her sey yaziyor, siz anlamiyorsunuz."),
             ("musteri", "Ne demek anlamiyorum, aciklayin!"),
             ("temsilci", "Iste ek paket almissiniz, o kadar. Baska?"),
             ("musteri", "Ben ek paket almadim ki!"),
             ("temsilci", "Almissiniz iste, sistemde gozukuyor."),
         ]),
    dict(channel="voice", category="ariza", tier="orta", title="Aktif dinleme zayif",
         emotion="memnuniyetsiz", churn="orta", ces=3.6, csat=2.9, sent=("olumsuz", "notr"),
         intents=["yavas-internet"],
         overrides={"Aktif Dinleme": 4, "Ihtiyac Analizi": 5},
         coaching="Musteriyi birkac kez kesti ve ayni bilgiyi tekrar sordurdu. Aktif dinlemeye odaklan.",
         turns=[
             ("temsilci", "Netix teknik, ben Caner. Buyurun."),
             ("musteri", "Internet cok yavas, aksamlari hic cekmiyor..."),
             ("temsilci", "Modeminizi resetleyin."),
             ("musteri", "Dur bir dinle, aksamlari diyorum sadece."),
             ("temsilci", "Musteri numaraniz neydi?"),
             ("musteri", "Az once soyledim ya!"),
             ("temsilci", "Tekrar alayim."),
             ("musteri", "44120099."),
             ("temsilci", "Tamam bakiyorum, hatta yogunluk varmis, gece duzelir."),
         ]),
    dict(channel="voice", category="bilgi", tier="mukemmel", title="Eksiksiz cozum + empati",
         emotion="memnun", churn="dusuk", ces=1.4, csat=4.9, sent=("notr", "olumlu"),
         intents=["kurulum", "kampanya"],
         coaching="Mukemmel gorusme: empati, net cozum, dogru bilgi, guclu kapanis.",
         turns=[
             ("temsilci", "Netix'e hos geldiniz, ben Elif. Gorusmemiz kalite amacli kayit altindadir, verileriniz KVKK kapsaminda korunur. Buyurun."),
             ("musteri", "Yeni tasindim, internet baglatmak istiyorum."),
             ("temsilci", "Tebrikler yeni eviniz hayirli olsun. Kimlik dogrulamasi icin ad soyad ve TC son 4 hanenizi rica edeyim."),
             ("musteri", "Ahmet Kaya, 4567."),
             ("temsilci", "Tesekkurler Ahmet Bey. Adresinizde fiber altyapisi mevcut; 100 Mbps paketi ilk 6 ay yarim fiyatla verebilirim. Kurulum ucretsiz, 2 gun icinde."),
             ("musteri", "Harika, baslatalim."),
             ("temsilci", "Kurulum randevunuzu carsamba 10:00-12:00 arasi ayarladim. Onay SMS'i geldi mi?"),
             ("musteri", "Geldi, tesekkurler."),
             ("temsilci", "Ne demek, baska bir konuda yardimci olabilir miyim? Iyi gunler dilerim Ahmet Bey."),
         ]),
    dict(channel="chat", category="bilgi", tier="iyi", title="Chat - hizli bilgi",
         emotion="memnun", churn="dusuk", ces=2.0, csat=4.4, sent=("notr", "olumlu"),
         intents=["tarife-bilgi"],
         coaching="Hizli ve net yaziliyor. Guzel.",
         turns=[
             ("musteri", "Merhaba, ek paket fiyatlarini ogrenebilir miyim?"),
             ("temsilci", "Merhaba, tabii ki. 10 GB ek paket 60 TL, 25 GB ek paket 110 TL. Hangisini istersiniz?"),
             ("musteri", "10 GB alayim."),
             ("temsilci", "Tanimladim, aninda aktif oldu. Baska yardimci olabilecegim bir konu var mi?"),
             ("musteri", "Yok, tesekkurler."),
             ("temsilci", "Rica ederim, iyi gunler dilerim."),
         ]),
    dict(channel="chat", category="sikayet", tier="orta", title="Chat - robotik/gec yanit",
         emotion="memnuniyetsiz", churn="orta", ces=3.7, csat=2.7, sent=("olumsuz", "notr"),
         intents=["bekleme-suresi"],
         overrides={"Aktif Dinleme": 5, "Kapanis": 5},
         coaching="Yanitlar kalip ve gecikmeli. Kisisellestirilmis, hizli donus onerilir.",
         turns=[
             ("musteri", "Siparisim hala gelmedi, 5 gun oldu."),
             ("temsilci", "Talebiniz alinmistir."),
             ("musteri", "Yani? Ne zaman gelecek?"),
             ("temsilci", "Ilgili birime iletilmistir."),
             ("musteri", "Bir sure verebilir misiniz?"),
             ("temsilci", "En kisa surede donus yapilacaktir."),
         ]),
    dict(channel="chat", category="iptal", tier="iyi", title="Chat - basarili elde tutma",
         emotion="memnun", churn="dusuk", ces=2.2, csat=4.1, sent=("olumsuz", "olumlu"),
         intents=["iptal-talep", "rakip-teklif"],
         coaching="Rakip teklife karsi somut deger sunuldu, musteri elde tutuldu. Cok iyi.",
         turns=[
             ("musteri", "Aboneligimi iptal etmek istiyorum, baska yerde daha ucuz buldum."),
             ("temsilci", "Sizi kaybetmek istemeyiz. Sadakat kampanyasiyla mevcut paketinizi ayni hiz, %25 indirimle 12 ay sabitleyebilirim. Ayrica 50 GB hediye."),
             ("musteri", "Gercekten mi? O zaman kalabilirim."),
             ("temsilci", "Harika, tanimladim ve onayladim. Indiriminiz bu donemden itibaren gecerli. Baska bir konu var mi?"),
             ("musteri", "Yok, tesekkur ederim."),
             ("temsilci", "Rica ederim, iyi gunler dilerim."),
         ]),
    dict(channel="voice", category="fatura", tier="iyi", title="Odeme plani",
         emotion="notr", churn="orta", ces=2.6, csat=3.9, sent=("olumsuz", "olumlu"),
         intents=["odeme-plani"],
         coaching="Cozum odakli, sakin. Kapanista teyit guzeldi.",
         turns=[
             ("temsilci", "Netix, ben Gizem. Gorusme kayittadir, buyurun."),
             ("musteri", "Bu ay faturami odeyemeyecegim, hattim kesilir mi?"),
             ("temsilci", "Anliyorum, merak etmeyin. Kimlik dogrulamasi yapalim; ad soyad ve dogum yiliniz?"),
             ("musteri", "Hasan Demir, 1979."),
             ("temsilci", "Tesekkurler Hasan Bey. Faturanizi 3 taksite bolebilirim, hattiniz da acik kalir. Uygun mu?"),
             ("musteri", "Cok iyi olur."),
             ("temsilci", "Taksitlendirdim, ilk taksit onumuzdeki hafta. Baska bir konu var mi? Iyi gunler."),
         ]),
]


def score_for(crit, tier, overrides):
    name = crit.name
    if overrides and name in overrides:
        return int(overrides[name])
    lo, hi = {"mukemmel": (9, 10), "iyi": (7, 9), "orta": (5, 7), "zayif": (3, 6)}[tier]
    return RNG.randint(lo, hi)


def build_metrics(sc, dur):
    if sc["channel"] == "chat":
        n = len([t for t in sc["turns"] if t[0] == "temsilci"])
        m = len(sc["turns"])
        return {"ilk_yanit_sn": RNG.randint(5, 40), "ortalama_yanit_sn": RNG.randint(15, 90),
                "temsilci_mesaj": n, "musteri_mesaj": m - n, "toplam_mesaj": m}
    tier = sc["tier"]
    talk = {"mukemmel": 48, "iyi": 52, "orta": 62, "zayif": 74}[tier] + RNG.randint(-4, 4)
    return {"temsilci_konusma_orani": talk, "temsilci_konusma_sn": round(dur * talk / 100),
            "musteri_konusma_sn": round(dur * (100 - talk) / 100),
            "temsilci_kesinti": {"mukemmel": 0, "iyi": 0, "orta": 1, "zayif": 3}[tier],
            "musteri_kesinti": RNG.randint(0, 1), "sessizlik_sn": RNG.randint(2, 14),
            "en_uzun_sessizlik_sn": RNG.randint(2, 6),
            "temsilci_kelime_dk": RNG.randint(135, 175),
            "temsilci_bagirma_sayisi": 1 if tier == "zayif" and RNG.random() < 0.4 else 0,
            "musteri_bagirma_sayisi": 1 if sc.get("is_crisis") else 0}


def main():
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == "demo").first()
        if not tenant:
            print("demo tenant yok"); return
        tid = tenant.id
        # Zaten pro cagri varsa tekrar ekleme (idempotent)
        if db.query(Call).filter(Call.tenant_id == tid, Call.filename.like("PRO-%")).first():
            print("pro cagrilar zaten var, atlaniyor"); return
        agents = db.query(Agent).filter(Agent.tenant_id == tid).all()
        criteria = db.query(Criterion).filter(Criterion.tenant_id == tid, Criterion.is_active.is_(True)).all()
        campaigns = db.query(Campaign).filter(Campaign.tenant_id == tid).all()
        camp_voice = next((c for c in campaigns if c.channel == Channel.voice), None)
        total_w = sum(c.weight for c in criteria)
        created = 0
        TARGET = 28
        try:
            from app.services import knowledge
        except Exception:
            knowledge = None

        for i in range(TARGET):
            sc = S[i % len(S)]
            agent = agents[i % len(agents)]
            days_ago = RNG.randint(0, 29)
            when = datetime.utcnow() - timedelta(days=days_ago, hours=RNG.randint(0, 9),
                                                 minutes=RNG.randint(0, 59))
            ch = Channel.chat if sc["channel"] == "chat" else Channel.voice

            # Segmentler + sure
            segs = []
            t = 0.0
            for idx, (spk, txt) in enumerate(sc["turns"]):
                dur = max(3.0, min(14.0, len(txt) / 14.0))
                segs.append((idx, spk, round(t, 1), round(t + dur, 1), txt))
                t += dur + RNG.uniform(0.3, 1.2)
            duration = round(t, 1)

            # Puanlar
            per = []
            zeroed = False
            for c in criteria:
                val = score_for(c, sc["tier"], sc.get("overrides"))
                per.append((c, val))
                if c.is_critical and val < c.critical_threshold:
                    zeroed = True
            raw = sum(v * c.weight for c, v in per)
            total = 0.0 if zeroed else round(raw / (total_w * 10) * 100, 1)

            call = Call(
                tenant_id=tid, filename=f"PRO-{sc['category']}-{i+1:02d}-{uuid.uuid4().hex[:6]}",
                audio_path="", channel=ch, agent_id=agent.id,
                campaign_id=camp_voice.id if (camp_voice and ch == Channel.voice) else None,
                status=CallStatus.done, duration_sec=duration, category=sc["category"],
                total_score=total, zeroed=zeroed, is_crisis=bool(sc.get("is_crisis")),
                predicted_csat=sc["csat"], summary=_summary(sc),
                sentiment_start=sc["sent"][0], sentiment_end=sc["sent"][1],
                coaching=sc["coaching"], emotion=sc["emotion"], churn_risk=sc["churn"],
                customer_effort=sc["ces"], intent_tags=sc["intents"],
                metrics=build_metrics(sc, duration), created_at=when, processed_at=when,
            )
            db.add(call); db.flush()

            for idx, spk, st, en, txt in segs:
                db.add(Segment(call_id=call.id, idx=idx, speaker=spk, start_sec=st, end_sec=en, text=txt))
            for c, v in per:
                db.add(Score(call_id=call.id, criterion_id=c.id, criterion_name=c.name,
                             criterion_group=c.group, weight=c.weight, score=v,
                             rationale=_rationale(c, v, sc), evidence=_evidence(c, sc, segs)))
            for viol in sc.get("violations", []):
                kind, cat, sev, spk, ev, term = viol
                db.add(Violation(tenant_id=tid, call_id=call.id, kind=kind, category=cat,
                                 severity=sev, speaker=spk, evidence=ev, term=term,
                                 ts_sec=RNG.choice([s[2] for s in segs]) if segs else None))
            # Embedding (semantik benzer-cagri icin)
            if knowledge is not None:
                try:
                    etext = f"{call.summary} {sc['category']} {' '.join(sc['intents'])}"
                    call.embedding = knowledge.embed([etext], tenant.settings,
                                                     tenant_id=tid, kind="embed")[0]
                except Exception:
                    pass
            created += 1
        db.commit()
        print(f"created_pro_calls {created}")
    finally:
        db.close()


def _summary(sc):
    q = {"mukemmel": "Ornek kalitede", "iyi": "Basarili", "orta": "Ortalama", "zayif": "Sorunlu"}[sc["tier"]]
    return f"{q} {sc['category']} gorusmesi — {sc['title']}."


def _rationale(c, v, sc):
    if v <= 2:
        return f"Ciddi eksik: {c.name} kriteri karsilanmadi (kritik ihlal)."
    if v <= 4:
        return f"Zayif: {c.name} beklentinin altinda."
    if v <= 6:
        return f"Ortalama: {c.name} kismen karsilandi, gelistirilebilir."
    if v <= 8:
        return f"Iyi: {c.name} buyuk olcude karsilandi."
    return f"Mukemmel: {c.name} eksiksiz uygulandi."


def _evidence(c, sc, segs):
    # Temsilci repliklerinden birini kanit goster
    ag_lines = [s[4] for s in segs if s[1] == "temsilci"]
    return RNG.choice(ag_lines) if ag_lines else ""


if __name__ == "__main__":
    main()
