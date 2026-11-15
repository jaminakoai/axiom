# G2 — Sabitlenmiş gerçek YARA corpus doğrulaması

**Tarih:** 16 Kasım 2026
**Durum:** Kod, test, README ve CI değişiklikleri hazır; yerel doğrulama tamamlandı.

## Kapsam

`advanced-threat-research/Yara-Rules` kaynağından beş küçük kural dosyası
`1919562a59f190bda60c982424f6a24c542ee3e0` commit'ine sabitlendi. Lisans
Apache-2.0'dır. Kaynak dosyalar değiştirilmeden
`tests/fixtures/yara_corpus/trellix-atr-2025-03-18/` altına alındı; manifestte
her kaynak ve lisans için SHA-256 kaydı bulunur. Test hedefleri sentetik ve
zararsızdır; gerçek malware örneği indirilmedi veya depoya eklenmedi.

Karşılaştırma motoru `yara-python==4.5.4`'tür. Manifest testi kaynak hash'lerini,
lisans hash'ini, tüm kaynaklardaki her rule adının tam bir kez sınıflandırılmasını
ve sınıflandırma değerlerini doğrular.

## Sonuç

Altı kuralın tamamı sınıflandırılmıştır:

| Kural | Sınıf | Gerekçe |
|---|---|---|
| `malw_eicar` | `supported` | `fullword ascii` ve `any of them`; sentetik pozitif ve negatif hedefler iki motorla karşılaştırıldı. |
| `BackdoorFCKG` | `supported` | `3 of them`; sentetik pozitif ve negatif hedefler iki motorla karşılaştırıldı. |
| `malw_browser_fox_adware` | `explicitly unsupported` | `uint16(0)` tamsayı okuması desteklenmiyor; Axiom kural dosyasını açık hatayla reddediyor. |
| `clop_ransom_note` | `explicitly unsupported` | `uint16(0)` tamsayı okuması desteklenmiyor; Axiom kural dosyasını açık hatayla reddediyor. |
| `ransomware_sodinokibi` | `explicitly unsupported` | Dosya `import "pe"`, `pe.imphash()` ve `uint16(0)` kullanıyor; dosya düzeyindeki PE import açık hatayla reddediliyor. |
| `Sodinokobi` | `explicitly unsupported` | Kendi koşulu daha basit olsa da aynı dosyanın üst düzey PE import'u nedeniyle kural dosyasının tamamı reddediliyor. |

Corpus içinde `mismatch` yoktur. Test, destek dışı her kaynağın YARA tarafından
derlenebildiğini ve Axiom tarafından sessiz sonuç yerine hata ile reddedildiğini
doğrular. Bu küçük corpus genel YARA uyumluluğu veya tespit başarısı iddiası
oluşturmaz.

## Uygulama notları

- Gerçek kurallar, koşul ifadesini fiziksel satırlar boyunca toplama ihtiyacını
  ortaya çıkardı. Parser artık geçerli çok satırlı koşulları topluyor.
- Bu değişikliğin ilk testi, tek satırlı koşulu string birleştirmeyle yeniden
  oluşturmanın birden çok kural taramasını bozduğunu gösterdi; koşul birimi ve
  birim yazım biçimi de oracle ile sınır testlerine alındı. Yaygın tek satırlı
  yolda ilk koşul satırı doğrudan korunuyor; birleştirme yalnız gerçek devam
  satırlarında yapılıyor. Çoklu kural regresyonu mevcut scanner testleriyle
  kontrol edildi.
- Browser ve Clop kurallarındaki `filesize` kullanımları için onluk `KB` ve `MB`
  birimleri YARA semantiğiyle eklendi. `1KB` = 1024 bayt ve `1MB` = 1.048.576
  bayttır; hexadecimal değerlerin veya boşlukla ayrılmış sayı/birimlerin kullanımı oracle ile uyumlu biçimde reddedilir.
- README Türkçe/İngilizce sürümlere aynı pinned corpus durum matrisi eklendi.
- GitHub Actions test işine corpus + YARA condition diferansiyel testleri için
  açık adımlı bir koşum eklendi. `yara-python==4.5.4` zaten `.[dev]`
  bağımlılıklarında sabittir.

## Doğrulama

Komut:

```text
python -m pytest -q --tb=short tests/test_yara_condition_differential.py tests/test_yara_corpus_compat.py tests/test_axiom_scan.py
```

Sonuç: **185 passed, 0 failed** (26,38 saniye). Bu koşu oracle differential
testlerini, corpus manifest/hash/sınıflandırma kapısını, desteklenen kuralların
pozitif-negatif sentetik hedeflerini, destek dışı kuralların açık reddini ve
mevcut `axiom-scan` regresyon paketini içerir.

Tam proje doğrulaması:

```text
python -m pytest -q --no-header
1500 passed in 1347.90s (0:22:27)
```

Dokümantasyon testleri ayrıca `tests/test_docs_en.py tests/test_docgen.py` ile
**25 passed** verdi. Son `make fmt-check` sonucu `Biçimlendirme geçerli`, son
`git diff --check` ise hatasız tamamlandı.

Bu rapor yazılırken yeni commit için GitHub Actions sonucu henüz alınmamıştı;
önceki commit'lerin CI sonucu bu G2 değişikliğinin kanıtı sayılmaz.
