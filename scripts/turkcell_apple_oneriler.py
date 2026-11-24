#!/usr/bin/env python3
"""Turkcell Pasaj Apple feed'inden app popup'i icin oneri JSON'u uretir.

Kullanim:
  python3 scripts/turkcell_apple_oneriler.py <feed_url_veya_dosya> <cikti.json>

Kurallar (popup ile ayni):
  - Sadece stokta olanlar (availability = in stock, stock_amount > 0)
  - Ayni modelin renkleri tek urune iner (baslik - renk = model anahtari),
    modelin en yuksek indirimli rengi kalir
  - Indirim = g:price - g:sale_price (TL); buyukten kucuge siralanir
  - Kategori basina en fazla KATEGORI_SINIRI urun (cesitlilik icin)
  - En fazla MAKS_URUN urun
Cikti ASCII-guvenli JSON'dur (ensure_ascii); GitHub Pages CORS'a aciktir.
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

MAKS_URUN = 10
KATEGORI_SINIRI = 3
G = "{https://base.google.com/ns/1.0}"


def oku(kaynak):
    if re.match(r"^https?://", kaynak):
        istek = urllib.request.Request(kaynak, headers={
            "User-Agent": "Mozilla/5.0 (BoostUp feed bot; +https://boost-up.co)",
            "Accept": "application/xml,text/xml,*/*"})
        with urllib.request.urlopen(istek, timeout=60) as yanit:
            return yanit.read()
    with open(kaynak, "rb") as f:
        return f.read()


def sayi(metin):
    m = re.search(r"[\d.]+", (metin or "").replace(",", "."))
    try:
        return float(m.group(0)) if m else 0.0
    except ValueError:
        return 0.0


def alan(item, ad):
    e = item.find(ad)
    return (e.text or "").strip() if e is not None and e.text else ""


def normal(metin):
    return re.sub(r"\s+", " ", metin.replace("I", "ı").replace("İ", "i").lower()).strip()


def uret(xml_bytes):
    kok = ET.fromstring(xml_bytes)
    kanal = kok.find("channel")
    build = alan(kanal, "lastBuildDate") if kanal is not None else ""
    enIyi = {}
    for it in kok.iter("item"):
        if alan(it, G + "availability") != "in stock":
            continue
        stok_metin = alan(it, G + "stock_amount")
        stok = int(sayi(stok_metin)) if stok_metin else 1
        if stok <= 0:
            continue
        fiyat = sayi(alan(it, G + "price"))
        if fiyat <= 0:
            continue
        satis = sayi(alan(it, G + "sale_price")) or fiyat
        baslik = alan(it, "title")
        renk = alan(it, G + "color")
        anahtar = normal(baslik)
        if renk:
            anahtar = re.sub(r"\s+", " ", anahtar.replace(normal(renk), " ")).strip()
        tip = alan(it, G + "product_type").split(">")
        urun = {
            "id": alan(it, G + "id"),
            "name": baslik,
            "img": alan(it, G + "image_link"),
            "url": alan(it, G + "link"),
            "price": round(fiyat, 2),
            "sale": round(satis, 2),
            "disc": round(fiyat - satis, 2),
            "pct": int(round((fiyat - satis) / fiyat * 100)),
            "cat": tip[1].strip() if len(tip) > 1 else "",
            "_stok": stok,
        }
        if not (urun["img"].startswith("https://") and urun["url"].startswith("https://")):
            continue
        onceki = enIyi.get(anahtar)
        if onceki is None or urun["disc"] > onceki["disc"] or (
                urun["disc"] == onceki["disc"] and stok > onceki["_stok"]):
            enIyi[anahtar] = urun
    liste = sorted(enIyi.values(), key=lambda u: (-u["disc"], -u["_stok"]))
    secim, kat = [], {}
    for u in liste:
        if len(secim) >= MAKS_URUN:
            break
        if kat.get(u["cat"], 0) >= KATEGORI_SINIRI:
            continue
        kat[u["cat"]] = kat.get(u["cat"], 0) + 1
        secim.append({k: v for k, v in u.items() if not k.startswith("_")})
    return {
        "source": "https://www.turkcell.com.tr/datafeed/CUSTOMFEED/appletemmuzfeed.xml",
        "feedBuildDate": build,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(secim),
        "products": secim,
    }


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    veri = uret(oku(sys.argv[1]))
    if veri["count"] == 0:
        print("HATA: secilecek urun bulunamadi; mevcut JSON korunuyor")
        sys.exit(1)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=True, separators=(",", ":"))
    print(f"{veri['count']} urun yazildi -> {sys.argv[2]}")


if __name__ == "__main__":
    main()
