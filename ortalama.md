# SCImago Quartiles Scraper – Zamanlama Referansı

Bu doküman, tipik bir çalıştırmada gözlemlenen sürelerin ortalamalarını ve bunların aşılması durumunda ne anlama geldiğini belirtir.

## Ortalama Süreler (25 Başarılı + 5 Bulunamayan Dergi, Referans Ortam)

| Aşama | Ortalama Süre | Detay |
|-------|---------------|-------|
| **Chrome başlatma** | ~2–4 sn | `undetected_chromedriver` ilk kurulum/cache süresi |
| **Başarılı dergi (tek)** | ~5–15 sn | Arama → profil → Quartiles tablosu |
| **Bulunamayan dergi (tek)** | ~6–8 sn | Arama → "No results" → fail |
| **30 dergi toplam** | ~5–7 dk | 1.5 sn bekleme süresi (`--delay`) dahil |

## Başarılı Dergi Süre Dağılımı

Tipik bir başarılı dergi şu adımları takip eder:

```
Arama sayfası yükleme          : 1–3 sn
Cloudflare bekleme (varsa)     : 0–5 sn
Profil sayfasına gitme         : 1–2 sn
Quartiles tablosu bekleme      : 1–3 sn
Veriyi parse etme              : <1 sn
--delay bekleme (varsayılan)   : 1.5 sn
───────────────────────────────────────
TOPLAM (tek dergi)             : ~5–15 sn
```

## Eşik Değerler (Alarm Sinyali)

Aşağıdaki süreler **sistematik olarak** aşılıyorsa bir sorun olabilir:

| Süre | Durum | Olası Neden |
|------|-------|-------------|
| **Tek dergi > 60 sn** | ⚠️ Uzun | Cloudflare challenge takılması, IP rate-limit, ağ yavaşlığı |
| **Tek dergi > 90 sn** | 🚨 Kritik | Cloudflare challenge timeout (script otomatik retry yapar) |
| **Chrome başlatma > 15 sn** | ⚠️ Uzun | Disk I/O sorunu, Chrome cache eksikliği, RAM yetersizliği |
| **Chrome başlatma > 30 sn** | 🚨 Kritik | Chrome binary bulunamıyor veya çökmüş driver instance |
| **30 dergi > 15 dk** | ⚠️ Uzun | Çoğunlukla Cloudflare'a takılma, ortalama süre 2x+ artmış |
| **30 dergi > 25 dk** | 🚨 Kritik | Sürekli challenge/timeout, IP bloklanmış olabilir |
| **Bulunamayan dergi > 15 sn** | ⚠️ Uzun | Normalde hızlı fail etmeli; ağ veya site yavaşlığı |

## Ne Yapmalı?

- **⚠️ Seviyesi:** `--delay` değerini artır (örn. `3.0`), birkaç saat sonra tekrar dene.
- **🚨 Seviyesi:**
  1. Farklı bir IP/proxy ile dene.
  2. `--verbose` flag'iyle logları incele.
  3. Site üzerinden manuel kontrol yap: Cloudflare challenge zorlaşmış olabilir.
  4. `script.sh` içindeki `xvfb-run` parametrelerini kontrol et.

## Not

Bu süreler **sunucu ortamında** (4+ CPU, yeterli RAM, stabil bağlantı(1Gbit)) ölçülmüştür. Daha düşük özellikli bir makinede veya yavaş internette süreler 2–3 kat artabilir.
