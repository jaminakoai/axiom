# G1 — YARA alt kümesi doğrulama kapanışı

**Tarih:** 15 Kasım 2026  
**Durum:** G1 kapandı; GitHub Actions run `43758677082` (`53839c3`) **7/7 başarılı**.  
**Kapsam:** TODO.md içindeki G1 — YARA hex pattern modeli, occurrence semantiği,
differential kanıtı, C/LLVM eşitliği ve doğrudan runtime sınırları.

## Sonuç

G1'in açık kalan iki kanıtı tamamlandı: YARA 4.5.4 differential/condition
matrisi tekrar çalıştırıldı ve 64 MiB typed-executor near-match fixture'ına
ölçülen çalışma süresi eşiği eklendi. Ürün hâlâ tam YARA uyumluluğu iddia etmez;
belgelenmiş alt küme dışındaki kullanımlar açıkça reddedilir.

## Doğrulama

| Komut | Sonuç |
|---|---|
| `python -m pytest -q -rs tests/test_yara_*.py tests/test_axiom_scan.py tests/test_real_yara_engine.py` | **490 geçti, 0 skip**, 224,36 sn; YARA oracle sürümü 4.5.4 |
| `python -m pytest -q -s tests/test_yara_typed_executor_stress.py` | **1 geçti**, 2,81 sn; 64 MiB hedef, 999-byte suffix, 16 near-match ve 17 instance; ölçülen runtime 15 sn altında |
| `python -m pytest -q tests/test_docs_en.py tests/test_docgen.py` | **25 geçti**, 11,47 sn |
| `make fmt-check && git diff --check` | biçim ve whitespace kontrolü temiz |
| GitHub Actions [run 43758677082](https://github.com/jaminakoai/axiom/actions/runs/43758677082) | **7/7 başarılı**; Python 3.10–3.13 her biri 1457 geçti/27 genel ortam testi atlandı; her sürümde doküman blokları 55 geçti; ASan/UBSan 40 geçti; LLVM testleri 20 geçti; biçim kontrolü başarılı |

Hedefli YARA paketi; metin ve typed hex occurrence'ları, `$a at/in`, `#/@/!`,
condition precedence/parantezleri, selector overlap, filesize birleşimleri,
NUL içeren hedefler, malformed/unsupported yapıların reddi ve C/LLVM parity
regresyonlarını kapsar. Doğrudan C harness'i 8 KiB encoding sınırı, hatalı AST
opcode/operand/jump/alternation, signed integer uçları, aşırı hedef uzunluğu ve
occurrence index sınırlarını fail-closed doğrular.

Stress testi `seconds=` değerini artık **15,0 saniyelik** bir regression eşiğiyle
karşılaştırır; 30 saniyelik subprocess timeout son emniyet sınırı olarak kalır.
Bu eşik yalnız testteki sabit adversarial fixture için geçerlidir, her kural veya
hedef boyutu için genel performans garantisi değildir. Önceki ölçümde aynı sınıf
fixture 64 MiB'de 1,455 saniyede çalışmıştı.

## Sınırlar ve riskler

- YARA'nın tamamı desteklenmiyor; destek matrisi geçerlidir.
- Geçerli tek satır inline YARA kuralı, satır tabanlı parser sınırında açıkça
  reddedilir.
- NUL içeren hedefte regex, byte-span regex desteği olmadığı için açık hatayla
  reddedilir.
- Gerçek kural dosyası corpus'u G2'nin işidir; bu rapor G2 uyumluluğu iddia etmez.
- CI'daki 27 skip, YARA hedefli oracle koşusunda görülmedi; yerel G1 hedefli
  koşu `-rs` ile **490 geçti, 0 skip** verdi.

## Sonraki iş

G1 kapandı. `TODO.md` yürütme sırası G2'ye ilerledi: lisansı ve sürümü
sabitlenmiş, zararsız sentetik hedefli küçük gerçek-kural corpus'u.
