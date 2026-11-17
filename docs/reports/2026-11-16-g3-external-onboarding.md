# G3 — Dış kullanıcı başlangıç akışı hazırlığı

**Tarih:** 16 Kasım 2026
**Durum:** Başlangıç/kurulum maddesi doğrulandı; bağımsız kullanıcının kendi yetkili girdisindeki denemesi bekleniyor.

## Hazırlananlar

- `docs/EXTERNAL_VALIDATION.md`: Debian/Ubuntu sistem gereksinimleri, temiz
  clone + venv kurulumu, `axiom-scan` derleme ve zararsız sentinel smoke testi,
  gerçek dosya/PCAP komutları, destek sınırları ve gizlilik gözeten geri bildirim
  şablonu içerir.
- README Türkçe ve İngilizce hızlı başlangıçlarından rehbere bağlantı eklendi.
- Geri bildirim şablonu veri dosyalarının yüklenmesini istemez. Testçi, kendi
  yetkili girdisi için yalnızca izin verilen OS/komut/sonuç/hash özetini paylaşır.
- G3 TODO başlığı `[~]`: kurulum hazırlığı tamamlandı, fakat dış kullanıcı
  deneyimi ve geri bildirimi henüz alınmadı.

## Temiz kurulum kanıtı

Geçici dizinde GitHub `master` temiz klonlandı; Python 3.13.14 venv oluşturuldu,
`pip install -e .` çalıştırıldı, `axiom --version` ve `examples/21_axiom_scan.ax`
derlemesi tamamlandı. Sentinel kuralı `rules` komutuyla doğrulandı ve sentetik
metin taraması `match_count=1` döndürdü.

Tekrarlanabilir ölçüm komutu (geçici venv/klon ve sentinel hedefi kullandı):

```text
clean clone + setup + build + rules + scan: 14.7 s
commit: 79e27c5
Axiom: v0.5.0-alpha
target_sha256: 1672850fcdc2a61c372188931ea164f8df197a0f87df96e0dd211a4ff02ed405
match: Axiom_External_Validation, offset 36, length 37
```

Ortam Linux x86_64, Kali GNU/Linux 2026.3 ve yerel Python 3.13.14 idi. Pip
önbelleği makinede bulunuyordu; 14.7 saniye ağ hızı için garanti değildir.
Sonuç yalnızca kurulum/build/sentetik smoke testini kanıtlar. Kullanıcı kabul
kapısı sayılmaz.

## Bekleyen dış kanıt

G3'ü kapatmak için en az bir bağımsız testçinin rehberdeki gerçek akışı kendi
yetkili dosyası veya PCAP'i üzerinde denemesi ve sonucu paylaşması gerekir.
Henüz böyle bir kullanıcı raporu/issue yoktur. Hiçbir kullanıcı girdisi projeye
alınmadı. Testçi sonucu geldiğinde girdiyi depolamadan bulgu `TODO.md`'ye
gizlilik gözeten yeniden üretim bilgisi ve önceliğiyle eklenecek.

## `2871874` commit'inde tekrar doğrulama

Önceki `79e27c5` kanıtını güncel kaynakla karıştırmamak için aynı temiz klon,
kurulum, build ve sentetik sentinel akışı doğrulama anında GitHub `master`'ın
güncel `2871874` commit'inde yeniden çalıştırıldı. `git clone --depth 1`, Python venv,
`pip install -e .`, `axiom --version`, örnek derleme, `rules` ve `scan`
adımlarının tamamı başarılı oldu. Toplam süre **15 saniye** idi.

```text
commit: 2871874
environment: Linux x86_64, local Python 3.13
axiom --version: Axiom (λx) v0.5.0-alpha
rules: ok=true, rules=1
scan: ok=true, match_count=1
match: Axiom_External_Validation, offset=36, length=37
target_sha256: 1672850fcdc2a61c372188931ea164f8df197a0f87df96e0dd211a4ff02ed405
elapsed: 15 s
```

Bu güncel doğrulama da yalnızca temiz kurulum/build ve sentetik akışı kanıtlar;
bağımsız kullanıcı deneyimi veya gerçek dosya/PCAP kabulü değildir.

Dokümantasyon doğrulaması: `python -m pytest -q --tb=short
tests/test_docs_en.py tests/test_docgen.py tests/test_tutorial_examples.py` →
**38 passed**; `make fmt-check` ve `git diff --check` başarılı.

## `4097bda` commit'inde temiz klonda tekrar doğrulama

17 Kasım 2026'da GitHub `master`'ın güncel `4097bda` commit'i yeni bir geçici
dizin altında derinliği 1 olan temiz klonda doğrulandı. Python 3.13.14 ile
`pip install -e .`, `axiom --version`, örnek derleme, `rules` ve sentetik
sentinel taraması başarılı oldu.

```text
commit: 4097bdaacff24c047d4f5ae98809b619681b39be
python: 3.13.14
axiom --version: Axiom (λx) v0.5.0-alpha
build: examples/21_axiom_scan.ax succeeded
rules: ok=true, rules=1
scan: ok=true, match_count=1
match: Axiom_External_Validation, offset 36, length 37
target_sha256: 1672850fcdc2a61c372188931ea164f8df197a0f87df96e0dd211a4ff02ed405
```

Bu güncel sentetik doğrulama onboarding komutlarını ve dosya tarama yolunu
kanıtlar; bağımsız kullanıcının yetkili gerçek dosya veya PCAP denemesinin
yerini tutmaz. G3 kullanıcı kabul kapısı bu nedenle açık kalır.

## `f3a6411` commit'inde temiz klonda tekrar doğrulama

17 Kasım 2026'da yerel `master` HEAD'i `f3a6411173ba` yeni bir geçici dizine
temiz klonlandı. Python 3.13.14 venv, editable kurulum, sürüm kontrolü, örnek
derleme, kural doğrulama ve sentetik sentinel taraması başarılı oldu.

```text
commit: f3a6411173ba
python: 3.13.14
axiom --version: Axiom (λx) v0.5.0-alpha
build: examples/21_axiom_scan.ax succeeded
rules: ok=true, rules=1
scan: ok=true, match_count=1
match: Axiom_External_Validation, offset=36, length=37
target_sha256: 1672850fcdc2a61c372188931ea164f8df197a0f87df96e0dd211a4ff02ed405
elapsed: 12.3 s
```

Bu sentetik kontrol güncel master'daki onboarding yolunu doğrular; bağımsız
kullanıcı denemesi veya gerçek dosya/PCAP kabulü değildir. G3 kapısı açık kalır.
