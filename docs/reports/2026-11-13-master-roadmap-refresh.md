# Master roadmap yenileme ve YARA pattern tasarım notu

**Tarih:** 13 Kasım 2026  
**Durum:** G0 doğrulaması tamamlandı; G1 tasarım/semantik incelemesi sürüyor  
**Kod değişikliği:** yok

## Amaç ve sonuç

`TODO.md` ana ve tek yürütme planı olarak güncellendi. Eski test sayıları,
eski CI koşusu ve tamamlanmış işi sıradaki iş gibi gösteren maddeler düzeltildi.
Sıra artık açık kabul kapılarından oluşuyor: G0 doğrulama, G1 pattern modeli,
G2 gerçek kurallar, G3 dış kullanıcı, G4 platform/dağıtım, G5 sürüm/ekosistem.

G0 tamamlandı. Sıradaki iş G1'dir. Bu not G1'in ilk mimari incelemesidir; pattern
modeli için bir uygulama başlatmaz. YARA sözdizimi veya runtime kodu değiştirilmedi.

## G0 doğrulama kanıtı

| Kanıt | Sonuç |
|---|---|
| Commit | `a5a0018d3fdf3ee43f843a4cc65239a553786fb8` |
| Yerel tam test | `python -m pytest -q -rs` — **1297 passed, 0 failed, 0 skipped** |
| Süre | 1205.72 s |
| Önceki hedefli doğrulama | 304 YARA/runtime/self-hosted + 58 LLVM/codegen test geçti |
| GitHub Actions | run `43419634279` — **7/7 jobs success** |

CI matrisi Python 3.10–3.13, ASan/UBSan, LLVM/DWARF ve biçimlendirme işlerini
kapsıyor. Bu kanıt yalnız belirtilen SHA ve Linux yerel ortamı için geçerlidir;
macOS veya gerçek Windows runner sonucu değildir.

## YARA pattern modeli — G1 tasarım notu

### Bugünkü yapı

- `YaraRule.patterns` ve `pattern_names`, aynı indeksle eşlenen iki paralel
  `str[]` dizisidir. `yara_rule_add_pattern` bu public builder biçimini kullanır.
- `yara_rules.ax` kaynak sözdizimini özel `hexrange:`, `hexalt:` ve `hexnot:`
  metin etiketlerine kodlar.
- `yara.ax` bu etiketleri ayrı ayrı tanır ve üç farklı runtime çağrısına
  yönlendirir. `axiom/runtime.h` içinde üç ayrı doğrulayıcı/tarama yolu vardır.
- `yara_condition.ax` da bazı etiketleri ayrıca tanımak zorundadır; örneğin
  `#` sayımının destek dışı olup olmadığını pattern türünden çıkarır.
- Sonuç modeli `YaraMatch` başına tek `offset` ve `matched_len` taşır. Bazı
  türlerde occurrence sayımı açık hata ile reddedilir.

Bu düzen yeni pattern biçimlerinde parser, evaluator, condition kontrolü ve
runtime dispatch'inin birlikte güncellenmesini gerektiriyor. Paralel diziler de
isim/değer indekslerinin eş kalmasına bağlı.

### Önerilen hedef model

1. **Tek bir tipli pattern modeli:** kimlik, pattern türü/flags ve içerik aynı
   kayıtta taşınmalı. YARA hex içeriği sıralı AST olarak temsil edilmeli:
   `Sequence` içinde `Byte(mask/value)`, `Jump(min,max)`, `Alternation(branches)`
   ve `NotByte(mask/value)` atomları. Mevcut wildcard bayt `Byte` atomunun tam
   maskesiz hali olur. Sabit/bounded jump mevcut sınırları korur.
2. **Tek hex parser ve doğrulayıcı:** kaynak konumuyla parse; boş dallar, bozuk
   aralık, sınır taşması, desteklenmeyen iç içe yapı ve resource limit aşımı
   açık hata üretmeli. Kısmi parse veya sessiz düzleştirme yok.
3. **Tek runtime yürütücüsü:** C runtime bir sürümlü, uzunluğu açıkça taşınan
   pattern programını okur. Tür başına ayrı dispatch/tag yerine sequence
   atomlarını yürütür. C99 ve LLVM aynı public/runtime helper'ı kullanmalı.
4. **Uyumluluk geçişi:** `yara_rule_new` ve `yara_rule_add_pattern` imzaları
   korunmalı. Eski düz metin pattern girdileri aynı parser'a girer. Yeni typed
   model önce internal/compiled representation olarak eklenir; doğrudan
   `YaraRule` struct literal kullanan istemciler ve ABI/source compatibility
   etkisi ayrıca ölçülmeden struct değiştirilmez.
5. **Tek doğruluk tablosu:** parser, condition evaluator ve raporlama aynı
   `PatternKind` bilgisini tüketmeli. `#`, `@`, `!`, `at`, `in` davranışları
   tür bazında test edilene kadar sessizce yaklaşık sonuç vermemeli; destek
   dışı ise kaynak konumuyla reddedilmeli.

### Henüz karara bağlanmamış semantik

Tasarım tek başına YARA referans davranışını kanıtlamaz. Aşağıdakiler YARA
4.5.4 ile diferansiyel testlerden önce sabitlenmemeli:

- En erken başlangıçta birden çok match varsa hangi uzunluk/ofset raporlanır?
- Alternation dalları aynı konumda ya da farklı uzunlukta eşleştiğinde seçim
  kuralı nedir?
- Overlap eden occurrence'lar `#`, `@` ve `!` için nasıl sayılır/sıralanır?
- `$a at N` ve `$a in (N..M)` değişken uzunluklu pattern'larda hangi aralık
  sınırlarını uygular?
- `Jump`, `Alternation` ve `NotByte` hangi birleşimlerde ve hangi iç içe
  derinlikte desteklenir?

### Uygulama öncesi kabul ölçütleri

- En az birim/runtime ve parser testleri, her AST atomunu ve sınır hatalarını
  kapsar.
- Lisansı ve sürümü sabit YARA 4.5.4 ile benign sentetik hedeflerde sonuç,
  offset, length ve occurrence sayısı karşılaştırılır.
- Her test ya tam eşleşme üretir ya da açık unsupported/parse hatası verir;
  sessiz mismatch sıfır olmalıdır.
- Aralık, toplam pattern uzunluğu, dallanma ve çalışma maliyetine test edilmiş
  sert limitler konur. Taşan boyutlarda integer overflow ve sınırsız tarama
  olmamalıdır.
- C backend ve LLVM aynı test örneklerinde aynı raporu üretir.
- Önceki `hexrange`, `hexalt`, `hexnot`, `??` ve nibble wildcard örnekleri
  geriye dönük regresyon kümesinde kalır.

## Değişen dosyalar

- `TODO.md`: tek aktif plan, G0 kapandı, G1 tasarımı sırada.
- `README.md`, `README.en.md`: güncel tam test sayısı, commit ve CI run bilgisi.
- `docs/reports/README.md`: bu rapor eklendi.

Kaynak kodu değiştirilmedi. CHANGELOG'a ürün özelliği eklenmedi.

## Sıradaki iş

G1'in kalan ilk işi açık semantik kararlarını YARA 4.5.4 diferansiyel testleri
ile kapatmak; ondan sonra tek typed modelin geriye uyumlu API tasarımını
kesinleştirmek. Bu kapılar geçmeden runtime/grammar implementasyonuna geçilmez.
