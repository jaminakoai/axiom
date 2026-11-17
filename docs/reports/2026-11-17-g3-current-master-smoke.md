# G3 — Güncel master onboarding smoke doğrulaması

**Tarih:** 17 Kasım 2026  
**Commit:** `0de28cef21064284683d05c5462a8cd00a284f66`  
**Durum:** Temiz kurulum ve sentetik başlangıç akışı doğrulandı; bağımsız gerçek kullanıcı denemesi hâlâ bekliyor.

## Yapılan doğrulama

GitHub `master` yeni, derinliği 1 olan geçici bir klona alındı. Python venv
oluşturuldu, editable kurulum yapıldı, `axiom --version` çalıştırıldı ve
`examples/21_axiom_scan.ax` derlenip bağımsız tarayıcı üretildi. Ardından
`docs/EXTERNAL_VALIDATION.md` içindeki zararsız YARA sentinel kuralı
doğrulandı ve sentinel dosyası tarandı.

```text
git rev-parse HEAD: 0de28cef21064284683d05c5462a8cd00a284f66
python: 3.13 (yerel ortam)
axiom --version: Axiom (λx) v0.5.0-alpha
build: examples/21_axiom_scan.ax başarılı
rules: ok=true, rules=1
scan: ok=true, match_count=1
match: Axiom_External_Validation, offset=36, length=37
target_sha256: 1672850fcdc2a61c372188931ea164f8df197a0f87df96e0dd211a4ff02ed405
```

Çalıştırılan temel komutlar:

```bash
git clone --depth 1 https://github.com/jaminakoai/axiom.git
python3 -m venv .venv
python -m pip install -e .
axiom --version
axiom build examples/21_axiom_scan.ax -o /tmp/axiom-scan
/tmp/axiom-scan rules /tmp/axiom-external.yar
/tmp/axiom-scan scan /tmp/axiom-external.txt --rules /tmp/axiom-external.yar
```

## Bulgular ve sınırlar

Bu çalıştırmada onboarding akışını bozan hata görülmedi. Çıktı beklenen tek
sentinel eşleşmesi, ofseti, uzunluğu ve SHA-256 değerini verdi. Bu yalnızca
Linux x86_64 üzerindeki sentetik kurulum/build/smoke akışının güncel commit'te
tekrarlandığını kanıtlar; gerçek dosya/PCAP taramasını, Windows/macOS tam
kurulumunu veya bağımsız kullanıcı deneyimini kanıtlamaz. G3 kullanıcı kapısı
bu nedenle açık kalır.

## Sıradaki iş

Bağımsız bir testçinin kendi yetkili dosya veya PCAP'iyle deneme yapıp
gizlilik gözeten, temizlenmiş geri bildirim paylaşmasını bekle. G4 yayın
kararları ve Pages/anahtar işletimi ayrıca maintainer girdisi gerektirir.
