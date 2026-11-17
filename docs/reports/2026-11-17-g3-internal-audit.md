# G3 — Maintainer yönlendirmeli iç teknik denetim

**Tarih:** 17 Kasım 2026  
**Denetlenen commit:** `d44278a6ebb879647f803b227e69c3b42bc820d2`  
**Sonuç:** Denetim kapsamındaki testler geçti; bu rapor bağımsız kullanıcı deneyimi iddiası değildir.

## Kapsam

Kullanıcı, bağımsız denetçi/kullanıcı beklemek yerine Axiom içinden teknik
denetim yapılmasını istedi. Bu nedenle G3'ün iç teknik kabul kapısı şu başlıklarla
değerlendirildi: temiz klondan kurulum ve CLI akışı, YARA tarayıcı davranışı,
desteklenen/ret edilen gerçek kural corpus'u, YARA differential sonuçları,
C/LLVM parity'si, PCAP hata sınırları ve dış deneme rehberinin gizlilik kuralları.

## Temiz klon ve CLI kanıtı

GitHub `master`, temiz `/tmp` dizinine klonlandı. Python 3.13.14 venv, editable
kurulum, `axiom --version` ve `examples/21_axiom_scan.ax` derlemesi başarılı
oldu. Zararsız, meta/fullword içeren sentinel kuralı `rules` ile kabul edildi;
hedef taraması tek doğru eşleşmeyi döndürdü.

```text
commit: d44278a6ebb879647f803b227e69c3b42bc820d2
python: 3.13.14
axiom --version: Axiom (λx) v0.5.0-alpha
scanner: axiom-scan 0.2.0
rules: ok=true, rules=1
scan: ok=true, match_count=1, scanned_bytes=74
match: Axiom_Internal_Audit_Sentinel, offset=36, length=37
target_sha256: 1672850fcdc2a61c372188931ea164f8df197a0f87df96e0dd211a4ff02ed405
```

## Test kanıtı

Üç hedefli test grubu, tam olarak denetlenen `d44278a` worktree'sinde çalıştırıldı:

```text
python -m pytest -q --tb=short tests/test_axiom_scan.py tests/test_yara_corpus_compat.py tests/test_yara_condition_differential.py
198 passed in 29.43s

python -m pytest -q --tb=short tests/test_real_yara_engine.py tests/test_real_sigma_engine.py tests/test_yara_sigma_coverage.py
27 passed in 65.65s

python -m pytest -q --tb=short tests/test_external_validation_docs.py tests/test_negative_security.py tests/test_security_audit_fixes.py
33 passed in 25.67s
```

**Toplam: 258 geçti, 0 başarısız, 0 atlandı.** Bu gruplar sentinel/CLI, YARA
gerçek kural örneklemi ve differential koşulları, Sigma regresyonu, scanner
PCAP sınırları, C/LLVM parity'si, hatalı girdi retleri ve dış deneme rehberi/
issue formu gizlilik kurallarını kapsıyor.

En son ürün kodu `2b73fea` için tam CI ayrıca Python 3.10–3.13'te her biri
1587 geçti/27 ortam testi atlandı ve Linux/Windows/macOS platform smoke'u 3/3
başarılı oldu: [CI run 44026041380](https://github.com/jaminakoai/axiom/actions/runs/44026041380),
[platform run 44026041510](https://github.com/jaminakoai/axiom/actions/runs/44026041510).
`d44278a`, bu CI'dan sonra gelen dokümantasyon-only commit'tir; bu raporun
hedefli testleri tam d44278a üzerinde çalıştı.

## Bulgular

Denetlenen yollar için yeni bir kod hatası veya sessiz yanlış karar bulunmadı.
Rapor dizini denetiminde indeks sayacının gerçek dosya sayısından bir eksik
olduğu fark edildi; sayaç 66 rapor / README dahil 67 dosya olarak düzeltildi.
Kabul edilmiş sınırlar devam ediyor: desteklenen YARA alt kümesi tam YARA
uyumluluğu değildir; pcapng desteklenmez; PCAP frame'leri tek tek ham bayt olarak
tarandığından protokol çözümleme ve TCP stream reassembly yoktur.

## Kapsam dışı

Gerçek kullanıcı dosyası/PCAP'i veya bağımsız kullanıcının çalışma biçimi
denetlenmedi. Bu nedenle bu sonuç teknik iç kabulü kapatır; bağımsız usability,
market fit veya kullanıcı kabulü kanıtı değildir. Dış deneme rehberi ve formu
isteğe bağlı geri bildirim için tutulur.

## Kabul kararı

Maintainer'ın isteğiyle G3'te bağımsız kullanıcı denemesi yerine yukarıdaki iç
teknik denetim kabul edildi. G3 teknik iç denetim kapısı kapandı. G4 resmi
registry yayını ve operasyon kararları açık kalır.
