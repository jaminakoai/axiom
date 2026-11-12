# Axiom (λx) — Detaylı İnceleme Raporu (Sürüm 2)

**Tarih:** 4 Kasım 2026, 20:45  
**İnceleme kapsamı:** `~/Desktop/axiom` deposunun tamamı  
**Yöntem:** Kaynak kodu okuma + gerçek derleme/çalıştırma testleri + test paketi + güvenlik odaklı denemeler  
**Not:** İnceleme sırasında depoya hiçbir kalıcı değişiklik yapılmadı; tüm denemeler `/tmp/opencode/` altında çalıştırıldı.

> **Bu sürümdeki güncelleme:** Önceki rapordan sonra depoya Faz 3 (Blue Team/DFIR), Faz 4 (AI/ML tensör) ve Faz 5 (Web/WASM) eklendi. Test sayısı 341’den 358’e çıktı; üç yeni örnek (`16`, `17`, `18`) ve 17 yeni test geldi. `runtime.h` 4.351 satırdan 4.769 satıra, `bin/axiomc` 60.344 bayttan 64.664 bayta çıktı. Bu rapor, yeni durumu ve önceki kritik bulguların hâlâ geçerli olup olmadığını birlikte değerlendirir.

---

## 0. Bu Güncellemede Ne Değişti?

### Eklenenler

- **Faz 3 — Blue Team / DFIR:** `std/security/yara.ax`, `std/net/pcap.ax`, `std/security/sigma.ax`, `std/os/forensics.ax`, `std/security/integrity.ax`
- **Faz 4 — AI/ML:** `std/ai/tensor.ax`, `linalg.ax`, `autograd.ax`, `nn.ax`, `inference.ax`
- **Faz 5 — Web/WASM:** `std/web/router.ax`, `app.ax`, `template.ax`, `std/target/wasm.ax`
- **Örnekler:** `examples/16_blueteam_defensive_suite.ax`, `17_ai_tensor_neural_net.ax`, `18_web_api_framework.ax`
- **Testler:** `tests/test_blueteam_libs.py` (6), `tests/test_ai_tensor_libs.py` (6), `tests/test_web_framework.py` (5)

### Doğrulanan iyileşmeler

- Test paketi: **358 passed in 83.60s**
- `examples/16`, `17`, `18` `bin/axiom` ile çalışıyor.
- `bin/axiomc`, `17` ve `18` örneklerini artık derleyip çalıştırabiliyor.
- `bin/axiomc` hâlâ yeniden üretilebilir: aynı BuildID (`1b710519b6b8e51ab164ce9983c6e84b0607308c`), aynı boyut (64.664 bayt).
- PCAP dosya yazıcı/okuyucu, SHA-256 FIM, 2D tensör işlemleri ve XSS kaçış demoları gerçekten çalışıyor.

### Değişmeyen kritik sorunlar

- Dizi sınır denetimi yok; `arr[99]` hâlâ çöp değer basıp `0` ile çıkıyor.
- `array_push` hâlâ stack belleğine `realloc` uyguluyor ve çöküyor.
- `len("ğüşiöç")` hâlâ **11** döndürüyor.
- `1 < "abc"` hâlâ kabul ediliyor ve `true` üretiyor.
- Eksik dönüşlü fonksiyon hâlâ çöp değer döndürüyor.
- Döngülü `ensures` hâlâ “Kesin İspat” ilan edilip çalışma zamanında ihlal ediliyor.
- İç içe `return`’lerde `ensures` hâlâ uygulanmıyor.
- `axiom check` hâlâ prover çalıştırmıyor.
- TLS’te hâlâ sertifika doğrulaması yok; JWT hâlâ `strcmp` kullanıyor; C2 hâlâ AES-256-CBC + sabit IV.
- “Statik ikili” hâlâ dinamik; `libz`, `libssl`, `libcrypto`, `libm`, `libc` bağımlılığı var.
- README hâlâ 161 test gösteriyor; `MASTER_TODO.md` hâlâ 335 test diyor.

**Özet:** Proje **genişledi**, ancak **derinleşmedi**. Yeni alanlar demo seviyesinde; temel güvenlik garantileri aynı.

---

## 1. Yönetici Özeti

Axiom, “Python kadar kolay, C kadar hızlı, Rust kadar güvenli” iddiasıyla geliştirilen, sözleşme tabanlı (`requires` / `ensures` / `verify`) bir sistem programlama dili prototipidir. Gerçekten çalışan bir lexer → parser → tip denetleyici → sembolik ispatlayıcı → C/LLVM kod üretimi hattına sahip. Bu inceleme sırasında **358 test** başarıyla geçti; `16`, `17`, `18` numaralı yeni örnekler uçtan uca çalışıyor; kendi kendini derleyen `bin/axiomc` yeniden üretilebiliyor.

Ancak projenin **temel güvenlik garantileri hâlâ yok**:

- Dizi sınır denetimi yok; `arr[99]` hatalı bellek okumasına rağmen program `0` ile çıkıyor.
- `array_push` stack üzerindeki diziye `realloc` uyguladığı için çöküyor.
- Üretilen C kodunda hiç `free` yok; “Zero-GC + RAII” iddiası pratikte geçersiz.
- `len("ğüşiöç")` 6 değil **11** döndürüyor; stringler bayt tabanlı.
- `1 < "abc"` tip denetiminden geçiyor ve C’de `true` üretiyor.
- Dönüşü olmayan fonksiyon kabul ediliyor ve çöp değer dönüyor.
- Döngülü bir fonksiyonda `ensures return >= 0` sözleşmesi hem `axiom prove` hem `axiom prove --smt` tarafından “Kesin İspat” ilan ediliyor; program çalışınca sözleşme ihlaliyle `101` ile duruyor.
- TLS’te sertifika doğrulaması yok; JWT’de `exp`/`nbf` kontrolü yok; C2 “AES-256-GCM” diye belgelenmiş ama uygulama AES-256-CBC + sabit IV.
- “Statik tek dosya ikili” iddiası yanlış: üretilen `hello` ikilisi `libz`, `libssl`, `libcrypto`, `libm` ve `libc`’ye dinamik bağlı.

**Yeni alanlarla ilgili kritik gözlem:** Faz 3, 4 ve 5 “%100 tamamlandı” olarak işaretlenmiş; ancak uygulamaların çoğu gerçek motor değil, **demo düzeyinde iskelet**:

- “YARA motoru” aslında `str_contains` + regex sarmalayıcısı.
- “Sigma kural motoru” dört sabit desen kontrolü.
- “Canlı PCAP / DPI” yok; yalnızca dosyaya pcap yazma/okuma var.
- “AVX2 SIMD GEMM” yorumu var, kodda skaler üçlü döngü var.
- “Autograd / backprop” gerçek grafik değil, birkaç yardımcı fonksiyon.
- “ONNX inference” yok; sadece küçük bir `model_predict`.
- “Radix-Tree router / async web framework” yok; doğrusal arama ve `Context` struct’ları var.
- “WASM hedefi” yok; yalnızca sihirli bayt dizisi ve export sayacı üretiliyor.

**Genel hüküm:** Axiom, etkileyici bir **araştırma/prototip** projesi; üretim ortamı için hazır değil. En büyük risk teknik eksiklerden çok, **pazarlama iddiaları ile gerçek davranış arasındaki fark**. Özellikle “Kesin İspat”, “güvenli sistem dili” ve “%100 tamamlandı” söylemleri, mevcut haliyle kullanıcıyı yanlış güvene sürükleyebilir.

**Olgunluk puanı (10 üzerinden): 3,5 / 10 — Alpha prototip.**  
Genişlik arttığı için puanı yükseltmedim; çünkü derinlik ve güvenlik aynı seviyede kaldı.

---

## 2. Axiom Nedir ve Ne İşe Yarar?

### 2.1 Kısa tanım

Axiom (λx), Python benzeri bir sözdizimiyle yazılan, C veya LLVM üzerinden yerel makine koduna derlenen, statik tipli ve sözleşme tabanlı doğrulama iddiası taşıyan bir dildir.

Temel bileşenler:

- Python’a benzeyen blok sözdizimi (`fn`, `let`, `if`, `while`, `struct`)
- `requires`, `ensures`, `verify` sözleşmeleri
- C ve LLVM olmak üzere iki kod üretim arka ucu
- Z3 tabanlı SMT ispatlayıcı
- `runtime.h` içinde toplanmış geniş bir C çalışma zamanı
- `std:` altında 45 Axiom kaynak dosyası ve 16 kategori
- REPL, formatter, modül çözümleyici, proje iskeleti oluşturma
- Kendi kendini derleyen `bin/axiomc` denemesi
- Faz 2/3/4/5 ile gelen ofansif güvenlik, DFIR, AI ve web demo kütüphaneleri

### 2.2 Hedeflenen kullanım

README ve `MASTER_TODO.md`’ye göre proje şunları hedefliyor:

- Sistem programlama
- Red Team / Blue Team güvenlik araçları
- Yapay zekâ ve tensör hesaplama
- Modern web/asenkron API’ler
- “Python’ın ergonomisi + C/Rust’ın performansı”
- “1 numaralı tercih edilen sistem programlama dili” olmak

Bu hedef seti son derece geniş. Projenin mevcut olgunluğu bu hedeflerin yalnızca küçük bir kısmını karşılıyor.

### 2.3 Bugün gerçekte ne yapabilir?

| Kullanım senaryosu | Uygunluk | Açıklama |
|---|---|---|
| Derleyici / programlama dili eğitimi | ✅ Uygun | Lexer, parser, AST, kod üretimi gerçekten var. |
| Sözleşmeli programlama araştırması | ⚠️ Kısmen | Fikir güzel, ispatlayıcı sesli değil. |
| Küçük, güvenilmeyen girdi almayan yerel CLI araçları | ⚠️ Dikkatli | Basit programlar çalışıyor; bellek güvenliği yok. |
| Güvenlik laboratuvarı deneyleri | ⚠️ Sadece izole VM | Kütüphaneler güvenli değil; yasal/etik risk var. |
| Blue Team / DFIR demoları | ⚠️ Demo | PCAP dosya I/O ve FIM gerçek; YARA/Sigma değil. |
| AI/ML tensör demoları | ⚠️ Demo | 2D skaler tensörler; AVX2/autograd/ONNX iddiaları yok. |
| Web API demoları | ⚠️ Demo | Router/middleware struct’ları var; HTTP sunucusu/asenkron yok. |
| WASM hedefi | ❌ Uygun değil | Sadece sihirli bayt ve export sayacı; kod üretimi yok. |
| Üretim servisi / genel ağ servisi | ❌ Uygun değil | TLS, bellek, tip ve doğrulama garantileri yok. |
| Kripto / kimlik doğrulama | ❌ Uygun değil | TLS ve JWT uygulamaları güvensiz. |
| Türkçe/Unicode yoğun uygulamalar | ❌ Uygun değil | Stringler bayt tabanlı; `len` yanlış. |
| C/Rust alternatifi olarak ciddi sistem yazılımı | ❌ Henüz değil | Ekosistem, araçlar ve garantiler eksik. |
| Python alternatifi | ❌ Henüz değil | Paket yöneticisi, kütüphane ekosistemi ve olgunluk yok. |

**Kısacası:** Axiom şu an bir “ürün” değil, **çalışan bir dil/derleyici araştırma prototipi**. En gerçekçi kullanımı eğitim, araştırma ve kontrollü deneylerdir.

---

## 3. Mimari ve Bileşenler

### 3.1 Derleme hattı

```text
.ax kaynak
   │
   ▼
Lexer (axiom/lexer.py)
   │
   ▼
Parser (axiom/parser.py) → AST
   │
   ▼
Checker (axiom/checker.py)  ← tip + sözleşme denetimi
   │
   ├──► Prover (axiom/prover.py)      ← aralık tabanlı sembolik ispat
   └──► Z3 Prover (axiom/z3_prover.py) ← SMT-LIB / Z3
   │
   ▼
C Codegen (axiom/codegen_c.py) ──► clang/gcc ──► ELF
LLVM Codegen (axiom/codegen_llvm.py) ──► LLVM IR ──► clang ──► ELF
```

### 3.2 Bileşen tablosu

| Bileşen | Dosya | Değerlendirme |
|---|---|---|
| Lexer | `axiom/lexer.py` | Sağlam; Unicode’u bayt düzeyinde işliyor. |
| Parser | `axiom/parser.py` | Recursive descent; çoğu dil özelliğini kapsıyor. |
| AST | `axiom/ast_nodes.py` | Makul kapsam. |
| Checker | `axiom/checker.py` | Yüzeysel; kritik boşluklar var. |
| Sembolik prover | `axiom/prover.py` | Basit doğrusal aritmetikte iyi; döngülerde ses değil. |
| Z3 prover | `axiom/z3_prover.py` | Entegrasyon gerçek; döngüleri yok sayıyor. |
| C backend | `axiom/codegen_c.py` | Çalışıyor; `ensures`’ı tüm dönüş yollarına uygulamıyor. |
| LLVM backend | `axiom/codegen_llvm.py` | Var ama C backend ile semantik olarak eşdeğer değil. |
| Çalışma zamanı | `axiom/runtime.h` | 4.769 satır; neredeyse tüm stdlib’in gerçek implementasyonu. |
| Standart kütüphane | `std/` | 45 `.ax` dosyası; çoğu ince sarmalayıcı veya demo. |
| Faz 3 modülleri | `std/security`, `std/net`, `std/os` | PCAP/FIM gerçek; YARA/Sigma yüzeysel. |
| Faz 4 modülleri | `std/ai` | 2D tensör gerçek; SIMD/autograd/ONNX iddiaları yok. |
| Faz 5 modülleri | `std/web`, `std/target` | Router/middleware demo; HTTP/WASM motoru yok. |
| Self-hosted derleyici | `compiler/` + `bin/axiomc` | Gerçekten derleniyor; ama dilin yalnızca alt kümesini destekliyor. |
| CLI | `axiom/cli.py` | 11 komut; kullanışlı ama bazı komutlar yanıltıcı. |

### 3.3 Önemli mimari gözlem

`runtime.h`, projenin kalbi. Axiom’un “standart kütüphanesi” denilen şeyin büyük kısmı aslında C ile yazılmış ve `std/*.ax` dosyaları yalnızca bu C fonksiyonlarını sarmalıyor. Bu kötü bir şey değil; ama “self-hosted stdlib” izlenimi veren tanıtımla çelişiyor. Örneğin `std/security/jwt.ax` 22 satır ve tamamen `rt_jwt_*` C fonksiyonlarına delege ediyor.

Yeni Faz 4/5 modülleri ise ters yönde: Axiom’da yazılmışlar, ama gerçek motorlar değil, demo iskeletleri. Örneğin `std/web/router.ax` doğrusal arama yapıyor; `std/target/wasm.ax` gerçek bir WASM ikilisi üretmiyor.

---

## 4. Doğrulanan Güçlü Yönler

Aşağıdakiler yalnızca README iddiası değil, gerçekten test edilerek doğrulandı.

### 4.1 Gerçek bir derleyici hattı var

Bu proje bir yorumlayıcı veya oyuncak değil. Lexer, parser, AST, tip denetleyici, sembolik ispatlayıcı ve iki farklı kod üretim arka ucu gerçekten mevcut. `axiom emit-c`, `axiom emit-llvm`, `axiom emit-smt` gibi komutlar çalışıyor.

### 4.2 Test paketi ciddi genişlikte

Bu inceleme sırasında:

```text
358 passed in 83.60s
```

Test dosyaları; lexer, parser, checker, codegen, LLVM, prover, Z3, modüller, stdlib, I/O, eşzamanlılık, REPL, CLI, self-hosted derleyici, red-team, blue-team, AI ve web kütüphanelerini kapsıyor. 23 test dosyası ve 358 test, tek kişilik bir proje için etkileyici bir kapsam.

### 4.3 Runtime sözleşme denetimi gerçekten çalışıyor

`requires` ihlali çalışma zamanında yakalanıyor:

```text
[AXIOM GUVENLIK IHLALI] REQUIRES Basarisiz Oldu!
  Fonksiyon   : safe_divide
  Sözleşme    : (b != 0)
```

Program `101` ile duruyor. `ensures` da üst düzey `return` yollarında çalışıyor. Bu, hata ayıklama için gerçekten faydalı bir özellik.

### 4.4 Z3 entegrasyonu var ve basit durumlarda çalışıyor

`axiom prove --smt` basit doğrusal aritmetik sözleşmelerini Z3’e aktarıp `UNSAT` sonucu üretebiliyor. `axiom emit-smt` ile SMT-LIB2 çıktısı alınabiliyor. Bu, projenin en iddialı ve en ilginç parçalarından biri.

### 4.5 Self-hosted derleyici gerçekten yeniden üretilebilir

`compiler/main.ax` kaynağından `bin/axiomc` derlendiğinde aynı BuildID elde edildi:

```text
BuildID: 1b710519b6b8e51ab164ce9983c6e84b0607308c
Boyut:   64.664 bayt
```

Ayrıca `bin/axiomc`, yeni `17` ve `18` örneklerini derleyip çalıştırabiliyor. Bu, önceki sürüme göre gerçek bir ilerleme.

### 4.6 Standart kütüphane genişliği arttı

`std/` altında artık 16 kategori ve 45 `.ax` dosyası var. Faz 3/4/5 ile birlikte PCAP, FIM, tensör, matmul, middleware, router, şablon ve WASM sihirli baytları gibi yeni alanlar eklendi. Genişlik kayda değer.

### 4.7 Gerçekçi örnekler

`examples/` altında 17 örnek var: port tarayıcı, çok iş parçacıklı tarayıcı, SIMD risk skorlama, red-team suiti, blue-team suiti, AI tensör/neural net ve web API framework. Bunlar “hello world”ün ötesinde, dilin hedeflediği alanı göstermesi açısından değerli.

### 4.8 Yeni demolar gerçekten çalışıyor

`examples/16`, `17` ve `18` `bin/axiom` ile `0` çıkış koduyla çalıştı. Özellikle:

- `16` blue-team: PCAP yazma/okuma, FIM hash, modül listesi.
- `17` AI: 2D tensör, matmul, ReLU/sigmoid, MSE, argmax.
- `18` web: router eşleşmesi, CORS/auth middleware, XSS kaçışı, WASM magic.

Bu demolar, dilin ifade gücünü göstermesi açısından olumlu.

### 4.9 Türkçe hata mesajları

Hata mesajları Türkçe ve genel olarak okunabilir. Bu, Türkçe konuşan geliştiriciler için gerçek bir avantaj.

### 4.10 CLI ergonomisi fena değil

`run`, `build`, `check`, `prove`, `emit-c`, `emit-smt`, `emit-llvm`, `repl`, `test`, `init`, `fmt` komutları var. Tek komutla derleme/çalıştırma deneyimi akıcı.

### 4.11 Borç denetleyicisi yok

Rust’taki borrow checker karmaşıklığını ortadan kaldırma fikri, öğrenme eğrisi açısından çekici. Ancak bunun bedeli şu anda **bellek güvenliğinin tamamen terk edilmesi** olmuş.

---

## 5. Kritik Zayıflıklar

Aşağıdaki bulguların her biri gerçek komutlarla doğrulandı. Önem sırasına göre verilmiştir.

### 5.0 Önem tablosu

| ID | Sorun | Önem |
|---|---|---|
| C1 | Bellek güvenliği yok (OOB, realloc, leak) | Kritik |
| C2 | Doğrulama sesli değil (“Kesin İspat” yanıltıcı) | Kritik |
| C3 | TLS/JWT/C2/shellcode güvensiz | Kritik |
| H1 | Tip sistemi delikleri | Yüksek |
| H2 | Unicode/string yanlış | Yüksek |
| H3 | C/LLVM semantik farkı | Yüksek |
| H4 | Faz 3-5 iddiaları şişirilmiş | Yüksek |
| M1 | Araç zinciri/ekosistem eksik | Orta |
| M2 | Test altyapısı yetersiz | Orta |

---

### 5.1 [KRİTİK] Bellek güvenliği yok

Axiom’un en büyük teknik sorunu bu. Dil, “güvenli sistem programlama” iddiasında ama diziler, stringler ve bellek yönetimi C seviyesinde çıplak.

#### Dizi sınır denetimi yok

```axiom
fn main() {
    let arr = [1, 2, 3];
    print(arr[99]);
}
```

Sonuç:

```text
11
EXIT=0
```

Sınır dışı okuma hatalı bellek okumasıdır. Program çökmüyor, çöp değer basıyor ve başarıyla çıkıyor. Bu, güvenilmeyen girdiyle çalışan her programda bilgi sızıntısı veya çökme riski demek.

#### `array_push` stack belleğine `realloc` uyguluyor

```axiom
fn main() {
    let mut arr = [1, 2];
    arr = array_push(arr, 3);
    print(len(arr));
}
```

Sonuç:

```text
realloc(): invalid pointer
EXIT=250
```

Dizi literali stack üzerinde oluşturuluyor; `array_push` ise `realloc` çağırıyor. Bu tanımsız davranış. Aynı hata, `let mut` ile kullanılan her dizi literali için geçerli.

#### Üretilen C kodunda `free` yok

`axiom/codegen_c.py` içinde tek bir `free(` çağrısı yok. Stringler `malloc`/`strdup` ile ayrılıyor; `runtime.h` içinde 87 `free` var ama bunlar yalnızca iç yardımcı fonksiyonlarda. Kullanıcı programlarının ayırdığı stringler/diziler scope sonunda serbest bırakılmıyor.

Kısa ömürlü CLI araçlarında işletim sistemi süreç çıkışında belleği geri alır; ama uzun süre çalışan bir servis veya REPL oturumunda bu **memory leak** demektir.

#### “Zero-GC + RAII” iddiası yanlış

- “Zero-GC” kısmı doğru: çöp toplayıcı yok.
- “RAII” kısmı yanlış: kaynaklar scope sonunda otomatik serbest bırakılmıyor.
- SPECIFICATION’ta “derleyicinin enjekte ettiği serbest bırakma çağrıları” deniyor; üretilen kodda böyle bir şey yok.

#### Diğer bellek sorunları

- `ax_str` aslında `const char*`; uzunluk başlığı yok. “Uzunluk başlıklı metin” iddiası yanlış.
- `realloc` dönüşü NULL kontrolü yapılmıyor; bellek biterse çökme.
- Paylaşılan runtime global’leri (TLS slotları, SSL fonksiyon pointer’ları, tensor handle tablosu, pcap handle tablosu) thread-safe değil.
- Tensor motoru en fazla 128 tensör tutuyor; global tablo ve `malloc` hataları kontrol edilmiyor.
- Null pointer kontrolü API’den API’ye değişiyor.
- Integer overflow’lar C’de tanımsız davranış; Axiom tarafında kontrol yok.

**Etki:** Bellek güvenliği gerektiren her senaryoda kullanılamaz. Bu, dilin ana satış argümanını doğrudan baltalıyor.

---

### 5.2 [KRİTİK] Doğrulama sesli (sound) değil — “Kesin İspat” yanıltıcı

Bu, projenin en tehlikeli sorunu. Çünkü kullanıcıya “kanıtlandı” diyor, ama program çalışınca sözleşme ihlal ediliyor.

#### Döngülerde yanlış ispat

```axiom
fn countdown(n: int) -> int
    requires n >= 0
    ensures return >= 0
{
    let mut total = 0;
    let mut i = 0;
    while i < n {
        total = total - 1;
        i = i + 1;
    }
    return total;
}
```

`axiom prove` çıktısı:

```text
• Doğrulanan Fonksiyon Sayısı  : 2
• İspatlanan Sözleşme Sayısı   : 2
• Sözleşme İhlali veya Hata    : YOK (0 Hata - Kesin İspat)
```

`axiom prove --smt` çıktısı:

```text
• Z3 SMT Çözücü Durumu : UNSAT (Tüm Karşıt-Örnekler Çürütüldü)
• Sözleşme İhlali veya Hata : YOK (0 Hata - Kesin İspat)
```

Gerçek çalışma:

```text
[AXIOM GUVENLIK IHLALI] ENSURES Basarisiz Oldu!
  Fonksiyon : countdown
  Sözleşme  : (__ax_ret >= 0)
EXIT=101
```

Yani `countdown(3)` çağrısı `-3` döndürüyor ve `ensures` ihlal ediliyor; buna rağmen ispatlayıcı “kesin ispat” diyor. Sebep: prover döngüyü modellemiyor; döngü gövdesini atlıyor ve `total = 0` başlangıç durumunu esas alıyor.

#### İç içe `return`’lerde `ensures` denetlenmiyor

```axiom
fn id(x: int) -> int { return x; }

fn pick(x: int) -> int
    ensures return >= 0
{
    if x < 0 {
        return id(x);
    } else {
        return 1;
    }
}

fn main() { print(pick(-1)); }
```

Sonuç:

```text
-1
EXIT=0
```

`ensures` ihlali yok sayılıyor. Üretilen C kodunda yalnızca üst düzey `return` yolları sarmalanıyor; `if` içindeki dönüşler sarmalanmıyor. Bu, sözleşmenin yarısının hiç uygulanmadığı anlamına gelir.

#### `axiom check` ispatlayıcıyı çalıştırmıyor

```axiom
fn safe_divide(a: int, b: int) -> int
    requires b != 0
{
    return a / b;
}

fn main() {
    let x = safe_divide(10, 0);
    print(x);
}
```

`axiom check`:

```text
✓ Doğrulama Başarılı: 'check.ax' sözdizimsel, tip ve sözleşme denetimlerinden geçti.
```

`axiom build` bu durumda hatayı yakalıyor; ama `print(...)` içindeki çağrıyı prover atlıyor. `let x = safe_divide(10, 0)` biçiminde yazıldığında yakalıyor. Yani kapsam tutarsız ve kullanıcı `check`’in “her şeyi kontrol ettiğini” sanıyor.

#### LLVM arka ucunda `ensures` hiç yok

`axiom/codegen_llvm.py` içinde `ensures` desteği yok. Ayrıca eksik dönüşlerde varsayılan `ret 0` üretiliyor. Bu, C backend ile LLVM backend’in **farklı semantik** üretmesi demek. Aynı program, seçilen arka uca göre farklı davranabilir.

#### “Kesin İspat” ifadesi kaldırılmalı

Prover tam değilken “0 Hata - Kesin İspat” demek, en hafif tabirle yanıltıcı. Doğru ifade “kısmi doğrulama” veya “bilinen karşı örnek yok” olmalı. Ayrıca `prove` komutu, ispatlayamadığı durumlarda **sıfırdan farklı çıkış kodu** döndürmeli.

**Etki:** Kullanıcı, sözleşmesi “kanıtlanmış” bir programa güvenip üretime alabilir; program çalışma zamanında durabilir. Bu, güvenlik açısından “hiç doğrulama olmamasından” daha kötüdür.

---

### 5.3 [KRİTİK] Güvenlik kütüphaneleri güvenli değil

Proje “güvenlik araçları için sistem dili” diyor; ancak güvenlik kütüphanelerinin kendisi ciddi açıklar içeriyor.

#### TLS: sertifika doğrulaması yok

`runtime.h` içinde `SSL_CTX_set_verify` çağrısı **hiç yok**. `TLS_client_method` ile bağlantı kuruluyor, ancak:

- Sunucu sertifikası doğrulanmıyor.
- Sertifika zinciri kontrol edilmiyor.
- Hostname doğrulaması yapılmıyor.

Sonuç: **MITM (ortadaki adam) saldırısına açık**. Herhangi bir sertifika kabul edilir. “HTTPS” kullanan bir Axiom programı, aslında şifreli ama kimliği doğrulanmamış bir kanal kullanır.

#### WebSocket: sabit anahtar, doğrulama yok

`runtime.h` içinde:

```text
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
```

Sabit anahtar kullanılıyor; sunucunun `Sec-WebSocket-Accept` yanıtı doğrulanmıyor. Varsayılan olarak düz TCP kullanılıyor. Bu, protokol düzeyinde zayıf bir uygulama.

#### JWT: süre ve algoritma doğrulaması yok

`axiom_jwt_verify_hs256`:

- İmza karşılaştırmasını `strcmp` ile yapıyor → **zamanlama saldırısı**.
- `exp` (son kullanma) kontrolü yok.
- `nbf` (geçerlilik başlangıcı) kontrolü yok.
- Header’daki `alg` doğrulanmıyor.
- `alg: none` gibi durumlar için koruma yok.

Yani süresi geçmiş veya yanlış algoritmalı token’lar kabul edilebilir.

#### C2: belgelenen ile uygulanan farklı

`MASTER_TODO.md`:

> “AES-256-GCM + HTTPS + WebSocket beaconing”

Gerçek `std/net/c2.ax`:

- `aes256_cbc_encrypt` kullanıyor (GCM değil).
- Sabit IV: `000102030405060708090a0b0c0d0e0f`.
- HMAC yerine `hash_sha256(agent_id + ":" + enc_data + ":" + secret_key)`.
- HTTPS/WebSocket yok; yalnızca string kodlama/şifreleme var.

Sabit IV, aynı düz metin için her zaman aynı şifreli metni üretir; bu da desen analizine açık demektir. SHA256(concat) ise HMAC değildir; uzunluk uzatma ve yapısal zayıflıklar barındırır.

#### Komut enjeksiyonu API tasarımında var

`runtime.h` içinde `system`, `popen` ve `execl("/bin/sh", "sh", "-c", cmd, ...)` kullanılıyor. `os_exec` gibi fonksiyonlar kullanıcı girdisini doğrudan shell’e verirse **RCE** kaçınılmazdır. Bu, “güvenli API” değil, “kullanıcıya silah veren API” tasarımıdır.

#### Shellcode çalıştırma varsayılan olarak açık

`axiom_exec_mem_run`:

- `mmap(..., PROT_READ | PROT_WRITE | PROT_EXEC, ...)` ile RWX bellek ayırıyor.
- Hex string’i makine kodu olarak çalıştırıyor.

Bu, W^X ilkesini ihlal eder ve keyfi kod çalıştırmaya kapı açar. `std/security/shellcode.ax` varsayılan `std` içinde. Aynı şekilde C2, evasion, memdump, packet crafter gibi ofansif modüller de varsayılan kütüphanede.

**Etki:** Bu modüller yalnızca izole laboratuvarlarda, açık izinle ve ayrı bir pakette kullanılmalı. Varsayılan kurulumda olmaları hem güvenlik hem yasal/etik risk oluşturur.

---

### 5.4 [YÜKSEK] Tip sistemi delikleri

#### Geçersiz karşılaştırma kabul ediliyor

```axiom
let x = 1 < "abc";
print(x);
```

Sonuç:

```text
true
EXIT=0
```

Checker, `int` ile `str` karşılaştırmasını reddetmiyor. C’de bu, tamsayı ile pointer karşılaştırmasına dönüşüyor; sonuç tanımsız/rastgele olabilir. Bu, tip güvenliğinin temel bir ihlali.

#### Eksik dönüş kabul ediliyor

```axiom
fn maybe_positive(x: int) -> int {
    if x > 0 {
        return 1;
    }
}
```

`maybe_positive(-5)` çağrısı:

```text
1
EXIT=0
```

Fonksiyon `x <= 0` için hiçbir değer döndürmüyor; C’de tanımsız davranış. Checker’da “definite return” analizi yok.

#### Tip adları normalleştirilmiyor

`checker.py` küçük harfli `int`, `str`, `bool` kullanıyor; ancak kullanıcı `Int` yazarsa:

```axiom
fn f() -> Int { return 0; }
```

Hata:

```text
Fonksiyon 'Int' dondurmeli ancak 'int' donduruldu.
```

README örnekleri küçük harf kullandığı için bu durum dokümantasyonla çelişmiyor; ama hata mesajı kafa karıştırıcı ve tip sistemi tutarsız. `Int`/`int` ayrımı yapay bir tuzak.

#### Diğer tip sorunları

- Null güvenliği yok.
- Generic/tip parametreleri yok (en azından kullanıcı düzeyinde).
- Koleksiyonlar tipli ama invariant/covariance kuralları yok.
- `void main` ile `int main` arasında tutarsızlık var; bazı örnekler `(int)ax_main()` gibi cast’lere başvuruyor.
- Aşırı yükleme, operatör tanımlama, pattern matching gibi modern özellikler yok.

**Etki:** Tip sistemi, vaat edilen “derleme zamanında hata yakalama” garantisini vermiyor. Basit hatalar üretime kaçabiliyor.

---

### 5.5 [YÜKSEK] Unicode ve stringler yanlış

README/SPEC “UTF-8 uyumlu, uzunluk başlıklı metin” diyor. Gerçek:

```axiom
print(len("ğüşiöç"));
```

Sonuç:

```text
11
```

“ğüşiöç” 6 karakterdir; UTF-8’de 11 bayttır. Axiom `len` bayt sayısı döndürüyor.

Ayrıca:

- `s[0]` ilk **baytı** döndürüyor; çok baytlı karakterin ortasını kesebiliyor.
- `str_sub`, `str_char_at`, `str_index_of` gibi fonksiyonlar bayt indeksleriyle çalışıyor.
- Unicode normalizasyonu yok.
- Türkçe büyük/küçük harf dönüşümleri yok.

Bu, özellikle Türkçe metin işleyen uygulamalar için ciddi bir sorun. “UTF-8 uyumlu” ifadesi teknik olarak yanlış; “UTF-8 bayt dizisi” demek daha doğru olur.

---

### 5.6 [YÜKSEK] Derleyici tutarsızlıkları ve self-hosting iddiası

#### C ve LLVM backend’leri aynı dili konuşmuyor

- LLVM’de `ensures` yok.
- LLVM’de eksik dönüşlerde `ret 0` üretiliyor; C’de tanımsız davranış.
- SIMD/thread gibi bazı özellikler yalnızca C backend’de çalışıyor.
- Aynı program, arka uca göre farklı sonuç verebilir.

Bu, “iki backend” iddiasını zayıflatıyor. Ortak bir semantik test paketi yok.

#### `bin/axiomc` dilin tamamını desteklemiyor

Self-hosted derleyici gerçekten derleniyor ve son sürümde `17`/`18` örneklerini destekliyor; ancak:

- `examples/05_real_scanner.ax` → hâlâ C derleme hatası (14 hata).
- `examples/08_multithreaded_scanner.ax` → `ax_thread_create`, `ax_mutex_init`, `ax_atomic_get` eşlemeleri yok (12 hata).
- `examples/09_simd_vector_scan.ax` → SIMD builtin’leri ve `void main` cast’i yok (13 hata).
- `examples/16_blueteam_defensive_suite.ax` → 20 hata; çok satırlı string/verify mesajı/import yolları sorunlu.

Ayrıca:

- Tip denetleyici yok.
- Modül çözümleyici yok.
- `ensures` yok.
- `@simd`, thread, SIMD builtin’leri yok.
- Fonksiyon gövdelerini ham string olarak saklıyor.
- `~/Desktop/axiom/axiom/runtime.h` yolu sabit kodlanmış.
- `/tmp/axiom_build_tmp.c` ve `/tmp/axiom_run_tmp.c` sabit; paralel derlemeler çakışıyor (`Text file busy`).
- `verify ... , "mesaj"` hâlâ mesajı düşürüyor; üretilen C’de kullanılmayan bir string ifadesi kalıyor.

Yani “self-hosted derleyici %100 tamamlandı” ifadesi, **dilin tamamı** için değil, **basit bir alt küme** için doğru.

#### Sürüm ve dokümantasyon tutarsızlıkları

- README: `v0.5.0-alpha`
- REPL: `v0.3.0`
- `axiomc`: `1.0.0`
- SPECIFICATION: `v0.1`
- README test sayısı: `161`
- `MASTER_TODO.md`: `335`
- Gerçek: `358`
- `axiom --version` çalışmıyor; argparse alt komut istiyor.
- MIT lisans rozeti var; `LICENSE` dosyası yok.
- Git deposu yok; CI yok; `pyproject.toml`/`requirements.txt` yok; changelog yok.

Bunlar tek tek küçük, toplamda güven kaybı yaratan sorunlar.

---

### 5.7 [ORTA] Araç zinciri ve ekosistem eksikleri

- **Paket yöneticisi yok.** `axiom init` bir `axiom.toml` üretiyor ama CLI bu dosyayı hiç okumuyor. Yani proje tanımı dekoratif.
- **Kayıt defteri (registry) yok.** Üçüncü taraf kütüphane ekosistemi kurulamaz.
- **Bağımlılık bildirimi yok.** `z3-solver`, OpenSSL ve zlib geliştirme başlıkları README’de eksik. `runtime.h` koşulsuz `<zlib.h>` ve `<openssl/evp.h>` içeriyor.
- **Statik ikili yok.** `hello` ikilisi dinamik bağlı: `libz`, `libssl`, `libcrypto`, `libm`, `libc`.
- **ARM64 desteği inandırıcı değil.** `runtime.h` içinde `<cpuid.h>`, x86’ya özel `vector_size(32)` AVX2 ve LLVM’de sabit `x86_64-pc-linux-gnu` triple var.
- **REPL yavaş.** Her girdi için yeni bir C ikilisi derliyor; etkileşimli kullanım için pratik değil.
- **Hata ayıklayıcı yok.** GDB/LLDB entegrasyonu, breakpoint, değişken inceleme yok.
- **LSP/IDE desteği yok.** Otomatik tamamlama, go-to-definition, inline hata yok.
- **Biçimlendirici var ama yapılandırılabilir değil.**
- **Dokümantasyon yalnızca README ve kısa SPEC.** API referansı, dil kılavuzu, öğreticiler yok.
- **Topluluk yok.** Katkı rehberi, davranış kuralları, issue şablonları yok.

---

### 5.8 [ORTA] Test altyapısı yetersiz

358 test iyi bir başlangıç; ama:

- **ASan/UBSan yok.** Bellek hataları testlerden kaçıyor.
- **Valgrind/leak testi yok.** Sızıntılar tespit edilmiyor.
- **Fuzz testi yok.** Lexer/parser için rastgele girdi testleri yok.
- **Property-based test yok.** Dizi/string operasyonları için matematiksel özellik testleri yok.
- **CI yok.** Her değişiklikte testler otomatik çalışmıyor.
- **Kapsam (coverage) ölçümü yok.**
- **Platform matrisi yok.** Yalnızca x86_64 Linux.
- **Performans regresyon testi yok.** “C hızı” iddiası ölçülmüyor.
- **Negatif güvenlik testleri yok.** OOB, double-free, TLS MITM gibi senaryolar test edilmiyor.
- **Yeni testler iddiaları değil demoları doğruluyor.** Örneğin WASM testi yalnızca magic baytlarını ve `byte_count`’u kontrol ediyor; gerçek bir WASM ikilisi üretildiğini doğrulamıyor.

Testlerin geçmesi, dilin güvenli olduğu anlamına gelmiyor; sadece test edilen davranışların bozulmadığını gösteriyor.

---

### 5.9 [YÜKSEK] Faz 3-5: “%100 tamamlandı” iddiası şişirilmiş

`MASTER_TODO.md` üç yeni fazı da “%100 TAMAMLANDI” olarak işaretliyor. Gerçek uygulamalar ise demo seviyesinde.

#### YARA: gerçek bir kural motoru değil

`std/security/yara.ax` 26 satır ve üç fonksiyon içeriyor:

- `yara_scan_buffer` → `str_contains`.
- `yara_scan_regex` → `regex_is_match` sarmalayıcısı.
- `yara_scan_hex` → hex string’ler üzerinde `str_contains`.

Rule parser, boolean kural mantığı, hex pattern ayrıştırma, string/hex/regex birleştirme, offset/condition desteği yok. “Hex, ASCII, Regex ve Boolean kuralları” iddiası karşılanmıyor.

#### Sigma: sabit desen listesi

`std/security/sigma.ax` 40 satır ve `sigma_detect_attack` içinde dört sabit kontrol var:

- `"Failed password"` → SSH_BRUTE_FORCE
- `UNION SELECT` / `union select` → SQL_INJECTION
- `<script>` / `alert(` → XSS_ATTACK
- `../..` / `/etc/passwd` → PATH_TRAVERSAL

Sigma kural dosyası (YAML) ayrıştırma, alan eşleme, log source, aggregation, false positive yönetimi yok. “Sigma kural motoru” değil, “birkaç desen kontrolü”.

#### PCAP: canlı yakalama ve DPI yok

`std/net/pcap.ax`, `runtime.h` içindeki `axiom_pcap_*` fonksiyonlarını sarmalıyor. Bunlar:

- Standart PCAP global header yazıyor.
- Hex paketleri dosyaya kaydediyor.
- Dosyadan paket okuyor.

Ancak:

- Canlı ağ dinleme (AF_PACKET/sniffer) yok.
- Paket ayrıştırma (Ethernet/IP/TCP/UDP) yok.
- DPI (deep packet inspection) yok.
- Filtreleme, promiscuous mode, ring buffer yok.

“Canlı PCAP yakalama ve DPI” iddiası yanlış; bu bir **pcap dosya I/O** kütüphanesi.

#### Forensics: /proc okuma, lsof/cron değil

`std/os/forensics.ax` yalnızca:

- `/proc/net/tcp` üzerinden TCP LISTEN portlarını okuyor.
- `/proc/modules` üzerinden yüklü modülleri okuyor.

UDP, process listesi, açık dosyalar, cron/persistence, kernel module analizi, timeline, artefakt toplama yok. “Linux adli bilişim araçları (lsof, cron & persistence avcısı)” iddiası karşılanmıyor.

#### AI: AVX2 yok, autograd yok, ONNX yok

- `axiom_tensor_matmul` yorumu “AVX2 / SIMD Optimize Matris Çarpımı” diyor; kod **skaler üçlü döngü**. AVX2 intrinsic, blocking, cache optimizasyonu yok.
- `std/ai/autograd.ax` gerçek bir hesaplama grafiği tutmuyor; `GradNode` yalnızca `id`, `grad`, `requires_grad` içeriyor. Backprop düğümleri/edges yok; sadece ReLU/sigmoid türev yardımcıları var.
- `std/ai/inference.ax` ONNX veya ağırlık dosyası okumuyor; sadece `model_predict` ve `model_classify` var.
- Tensorlar yalnızca 2D; ND-array, stride, shape manipulation, broadcasting yok. “Çok boyutlu tensör (ND-Array)” iddiası yanlış.
- Global tensor tablosu 128 ile sınırlı ve thread-safe değil.

#### Web: async framework ve Radix router yok

- `std/web/router.ax` route’ları **doğrusal** tarıyor; Radix/Trie yok.
- `std/web/app.ax` yalnızca `Context` struct’ı ve middleware fonksiyonları; HTTP sunucusu, request parsing, response writer, async runtime, connection pool yok.
- `std/web/template.ax` basit `str_replace` zinciri; template parser, expression evaluation, context-aware escaping (attribute/JS/CSS), partials, loops, conditionals yok.
- “Go/Node.js performansını aşan yüksek eşzamanlılıklı web mimarisi” iddiası tamamen desteksiz.

#### WASM: hedef değil, sihirli bayt

- `std/target/wasm.ax` yalnızca `"0061736d01000000"` magic string’ini döndürüyor.
- `wasm_add_export` bir struct dizisine eleman ekliyor ve `byte_count` sayacını artırıyor.
- Gerçek WASM binary encoding, section’lar, type/function/code/export tables, memory, instruction encoding yok.
- `axiom build --target=wasm` gibi bir CLI yolu yok.

“WASM doğrudan derleme desteği” iddiası yanlış.

**Etki:** Bu modüller, güvenlik/AI/web alanında “hazır” izlenimi veriyor; ama gerçek kullanımda beklentiyi karşılamaz. Bu, dilin güvenilirliğini daha da zedeliyor.

---

### 5.10 [ORTA] Yeni testler de iddiaları değil, demoları doğruluyor

Yeni test dosyalarındaki 17 test, yalnızca temel demo çıktılarını kontrol ediyor:

- `test_yara_scanner`: `str_contains` ile bulunan bir string.
- `test_sigma_rules`: dört sabit desen.
- `test_pcap_io`: bir paket yazıp aynı hex’i geri okuyor.
- `test_forensics`: `len(mods) > 0`.
- `test_tensor_create_and_indexing`: 2x3 tensörde iki değer.
- `test_linalg_matmul_and_transpose`: 2x2 matmul.
- `test_autograd_graph_and_backprop`: üç yardımcı fonksiyon.
- `test_wasm_target_module_builder`: magic string ve `byte_count > 8`.
- `test_web_app_middleware_and_context`: struct alanları.

Bunlar faydalı regresyon testleri; ancak “YARA motoru”, “AVX2 GEMM”, “autograd”, “ONNX”, “async web”, “WASM target” iddialarını **doğrulamıyor**. Test sayısının artması, iddiaların doğru olduğu anlamına gelmiyor.

---

## 6. İddia vs Gerçek

| İddia | Gerçek | Kanıt |
|---|---|---|
| “Tek dosya statik ikili” | Dinamik ELF; `libz`, `libssl`, `libcrypto`, `libm`, `libc` bağımlılığı | `file hello`, `ldd hello` |
| “Zero-GC + RAII” | GC yok; RAII yok; üretilen C’de `free` yok | `grep free axiom/codegen_c.py` boş |
| “UTF-8 uyumlu, uzunluk başlıklı str” | Bayt tabanlı; `len` 11 döndürüyor | `len("ğüşiöç")` → 11 |
| “ARM64 hedefi” | x86’ya özel `cpuid.h`, AVX2, sabit triple | `runtime.h:39`, `:808`; `codegen_llvm.py:140` |
| “Sözleşmeler derleme anında kesin ispat” | Döngülerde ses değil; iç içe return’lerde `ensures` yok; `check` prover çalıştırmıyor | `loop3.ax`, `nested2.ax`, `check2.ax` |
| “161 test” | 358 test | `pytest -q` |
| “MIT lisans” | `LICENSE` dosyası yok | `ls LICENSE` |
| “AES-256-GCM + HTTPS + WebSocket C2” | AES-256-CBC + sabit IV; SHA256(concat); TLS/WS yok | `std/net/c2.ax`, `runtime.h:3527` |
| “YARA-style kural motoru” | `str_contains` + regex sarmalayıcı | `std/security/yara.ax` |
| “Sigma kural motoru” | Dört sabit desen | `std/security/sigma.ax` |
| “Canlı PCAP / DPI” | Dosya yazma/okuma; canlı yakalama ve ayrıştırma yok | `std/net/pcap.ax` |
| “AVX2 SIMD GEMM” | Skaler üçlü döngü | `runtime.h:4654` |
| “Autograd / backprop” | Yardımcı türev fonksiyonları; grafik yok | `std/ai/autograd.ax` |
| “ONNX inference” | ONNX okuyucu yok | `std/ai/inference.ax` |
| “Radix router / async web” | Doğrusal arama + `Context` struct’ları | `std/web/router.ax`, `app.ax` |
| “WASM hedefi” | Sadece magic bayt ve export sayacı | `std/target/wasm.ax` |
| “Self-hosted derleyici tamamlandı” | 17/18 çalışıyor; 05/08/09/16 çalışmıyor | `bin/axiomc build ...` |
| “Güvenli sistem dili” | Bellek ve tip güvenliği yok | OOB, `1 < "abc"`, eksik return |

---

## 7. Olgunluk Değerlendirmesi

| Alan | Puan (10) | Gerekçe |
|---|---:|---|
| Dil çekirdeği | 5 | Lexer/parser/AST/kod üretimi gerçek; dil yüzeyi makul. |
| Tip güvenliği | 3 | Karşılaştırma, dönüş analizi, tip normalizasyonu eksik. |
| Bellek güvenliği | 1 | Sınır denetimi yok, `realloc` hatası, sızıntılar. |
| Sözleşme/doğrulama | 3 | Runtime tarafta iyi; statik tarafta ses değil. |
| Standart kütüphane genişliği | 8 | 45 dosya, 16 kategori; yeni alanlar eklendi. |
| Standart kütüphane derinliği/güvenliği | 3 | Çoğu ince wrapper/demo; TLS/JWT/C2 güvensiz. |
| Faz 3-5 demo kalitesi | 4 | Demolar çalışıyor; motorlar gerçek değil. |
| Araç zinciri | 4 | CLI/REPL/fmt var; debugger, LSP, paket yöneticisi yok. |
| Dokümantasyon | 3 | README iyi yazılmış ama yanıltıcı; SPEC kısa; test sayısı eski. |
| Test altyapısı | 5 | 358 test; sanitizer/fuzz/CI yok. |
| Güvenlik | 2 | TLS, JWT, C2, shellcode, komut enjeksiyonu. |
| Taşınabilirlik | 2 | x86_64 Linux’a bağlı; ARM64 iddiası desteksiz. |
| Ekosistem | 1 | Paket yöneticisi, registry, topluluk, lisans yok. |
| **Genel** | **3,5** | **Alpha prototip; üretim için hazır değil.** |

### Üretim hazırlığı hükmü

**Hayır.** Axiom şu haliyle üretimde kullanılmamalı. Özellikle:

- Genel ağa açık servisler
- Kimlik doğrulama / kripto
- Güvenilmeyen girdi işleyen araçlar
- Uzun süre çalışan süreçler
- Çok iş parçacıklı kritik sistemler
- Türkçe/Unicode metin işleme
- Gerçek YARA/Sigma/PCAP/DFIR/AI/Web/WASM iş yükleri

için uygun değil.

Ancak **eğitim, araştırma ve kontrollü prototipleme** için değerli bir proje. Derleyici hattı, sözleşme fikri ve self-hosting denemesi takdire değer.

---

## 8. Önceliklendirilmiş İyileştirme Yol Haritası

Aşağıdaki sıralama, “en yüksek riski en erken azalt” ilkesine göre yapılmıştır.

### P0 — Acil (0–2 hafta): Özellik dondurma, güvenlik ve dürüstlük

1. **Yeni faz eklemeyi durdur.**
   - Faz 6/7 eklemek yerine mevcut fazları gerçek yap.
   - “%100 tamamlandı” işaretlerini “demo” olarak değiştir.
   - README’deki “YARA motoru”, “AVX2”, “autograd”, “ONNX”, “async web”, “WASM target” ifadelerini düzelt.

2. **“Kesin İspat” ifadesini kaldır.**
   - `prove` ve `prove --smt` çıktısı “kısmi doğrulama” olarak değiştirilmeli.
   - İspatlanamayan durumlarda çıkış kodu `0` olmamalı.
   - Döngü içeren fonksiyonlar için “bilinmiyor” sonucu verilmeli.

3. **Tüm `return` yollarını `ensures` ile sarmala.**
   - C codegen’de `if`/`else`, `while`, `for` içindeki dönüşler dahil.
   - LLVM backend’e de `ensures` ekle veya LLVM’i deneysel olarak işaretle.

4. **`axiom check` ya prover’ı çalıştırsın ya da adı değişsin.**
   - “check” denince kullanıcı sözleşmelerin de kontrol edildiğini sanıyor.
   - En azından `--no-prove` seçeneği ve net çıktı.

5. **Dizi sınır denetimi ekle.**
   - `arr[i]` için çalışma zamanı kontrolü (debug) + statik analiz (mümkünse).
   - `array_push` stack literaline `realloc` uygulamasın; kopyalama yapsın.

6. **TLS’i düzelt.**
   - `SSL_CTX_set_verify(ctx, SSL_VERIFY_PEER, NULL)`.
   - Sistem CA deposunu yükle.
   - Hostname doğrulaması ekle.
   - Doğrulama başarısızsa bağlantıyı kapat.

7. **JWT’yi düzelt.**
   - Sabit zamanlı karşılaştırma.
   - `exp`, `nbf`, `iat` kontrolü.
   - `alg` doğrulaması; `none` reddi.

8. **WebSocket’i düzelt.**
   - Rastgele `Sec-WebSocket-Key`.
   - `Sec-WebSocket-Accept` doğrulaması.
   - Varsayılan TLS.

9. **Ofansif modülleri ayrı pakete taşı.**
   - `shellcode`, `c2`, `evasion`, `memdump`, `packet_crafter` varsayılan `std`’den çıkarılmalı.
   - Açık uyarı, lisans/etik metni ve izinli kullanım şartı.

10. **`os_exec`/`popen` API’lerini argv tabanlı yap.**
    - Shell’siz `execve`/`posix_spawn` tercih edilmeli.
    - Shell gerekiyorsa adı `os_exec_shell` olmalı ve dokümante edilmeli.

### P1 — Kısa vade (2–6 hafta): Dil güvenliği ve yeni modüllerin derinleştirilmesi

1. **Tip denetleyiciyi sıkılaştır.**
   - `int < str` gibi karşılaştırmaları reddet.
   - “Definite return” analizi ekle.
   - `Int`/`int` normalizasyonu yap veya yalnızca tek biçime izin ver.
   - Sayısal dönüşümleri açık hale getir.

2. **UTF-8 string türü.**
   - Uzunluk, indeksleme ve substring karakter tabanlı olsun.
   - `len` karakter sayısı döndürsün; `byte_len` ayrı fonksiyon olsun.
   - Geçersiz UTF-8 için hata veya replacement politikası belirle.

3. **Bellek yönetimi stratejisi.**
   - En azından “arena per scope” veya “ownership + explicit free” modeli.
   - Üretilen C’de `free` enjeksiyonu.
   - Sızıntı testleri (valgrind/ASan).

4. **C/LLVM semantik parity.**
   - Ortak test paketi: aynı program iki backend’de aynı çıktıyı vermeli.
   - LLVM’de eksik dönüşte `ret 0` yerine derleme hatası.

5. **Yeni modülleri ya derinleştir ya yeniden adlandır.**
   - **YARA:** Gerçek kural parser’ı yaz veya `pattern_match` olarak adlandır.
   - **Sigma:** YAML kural motoru yaz veya `log_pattern_match` olarak adlandır.
   - **PCAP:** Canlı yakalama + paket ayrıştırma ekle veya `pcap_file_io` olarak adlandır.
   - **Forensics:** `lsof`, cron, process, UDP ekle veya kapsamı daralt.
   - **AI:** AVX2 intrinsiclerini gerçekten kullan veya “AVX2” iddiasını kaldır.
   - **Autograd:** Gerçek grafik/backprop yaz veya adını `grad_helpers` yap.
   - **Inference:** ONNX parser yaz veya “ONNX” iddiasını kaldır.
   - **Web:** HTTP sunucusuyla entegre et; Radix router yaz veya “Radix” iddiasını kaldır.
   - **WASM:** Gerçek binary encoder yaz veya “hedef” iddiasını kaldır.

6. **Test altyapısını güçlendir.**
   - ASan/UBSan ile test koşusu.
   - Valgrind/leak kontrolü.
   - Lexer/parser için fuzz.
   - Dizi/string için property-based test.
   - GitHub Actions/CI.

7. **Dokümantasyonu dürüstleştir.**
   - README’deki “statik”, “RAII”, “UTF-8”, “ARM64”, “kesin ispat”, “AVX2”, “ONNX”, “WASM” ifadelerini düzelt.
   - Test sayısını otomatik güncelle.
   - `LICENSE` ekle.
   - `requirements.txt`/`pyproject.toml` ekle.
   - Sürümü tek kaynaktan yönet.

### P2 — Orta vade (2–4 ay): Araçlar ve taşınabilirlik

1. **Paket yöneticisi.**
   - `axiom.toml`’u gerçekten oku.
   - Bağımlılık çözümleme, lockfile, yerel/uzak paket.
   - Registry olmasa bile path/git bağımlılığı destekle.

2. **Self-hosted derleyici parity.**
   - Ya dilin tamamını destekle ya da “bootstrap alt kümesi” olarak etiketle.
   - Sabit `/tmp` yollarını kaldır; `mkdtemp` kullan.
   - Runtime header yolunu yapılandırılabilir yap.
   - Tip denetleyici ve modül çözümleyici ekle.

3. **ARM64.**
   - Ya gerçekten destekle (cpuid/AVX2 soyutlama, triple seçimi) ya da iddiayı kaldır.
   - CI’da x86_64 + ARM64 matrisi.

4. **REPL’i hızlandır.**
   - Her girdi için yeni binary derlemek yerine kalıcı bir JIT/interpreted mod.
   - En azından incremental derleme.

5. **Debugger/LSP.**
   - DWARF debug info.
   - GDB/LLDB entegrasyonu.
   - LSP sunucusu (tamamlama, tanıma git, hata).

6. **Performans ölçümü.**
   - C/Rust/Go/Python karşılaştırmalı benchmark’lar.
   - “C hızı”, “AVX2”, “async web” iddialarını sayılarla destekle.

### P3 — Uzun vade (6–12 ay): Üretim sertleştirmesi

1. **Güvenlik denetimi.**
   - Bağımsız kod incelemesi.
   - Tehdit modeli.
   - Kripto ve ağ kütüphaneleri için ayrı audit.

2. **Spesifikasyon uyum testleri.**
   - SPEC’teki her madde için test.
   - Sürüm uyumluluğu politikası.

3. **Ekosistem.**
   - Dokümantasyon sitesi.
   - Örnek projeler.
   - Topluluk yönetişimi.
   - Kararlı sürüm ve semver.

4. **Üretim sertleştirmesi.**
   - Sandbox, kaynak limitleri, hata izolasyonu.
   - Fuzz sürekli entegrasyonu.
   - SBOM ve tedarik zinciri güvenliği.

---

## 9. Sonuç

Axiom’un fikri tutarlı ve çekici: Python benzeri sözdizimi, sözleşmeli doğrulama, yerel derleme, geniş güvenlik kütüphanesi. Tek kişilik bir proje için ortaya konan mühendislik hacmi gerçekten etkileyici. Derleyici hattı çalışıyor, testler geçiyor, self-hosted ikili üretilebiliyor; son sürümde `17` ve `18` örnekleri self-hosted derleyiciyle de çalışıyor.

Ancak proje, **“güvenli” ve “kanıtlanmış” kelimelerini hak etmiyor**:

- Bellek güvenliği yok.
- Tip güvenliği delik.
- Statik ispat sesli değil.
- TLS/JWT/C2 güvensiz.
- “Statik binary”, “UTF-8”, “RAII”, “ARM64” gibi iddialar yanlış.
- Faz 3-5’in “YARA”, “Sigma”, “AVX2”, “autograd”, “ONNX”, “async web”, “WASM” iddiaları demo seviyesinde.
- Ekosistem ve üretim altyapısı yok.

Bu haliyle Axiom, **ciddi bir araştırma prototipi**; üretim dili değil. Son eklenen üç faz, projenin **genişleme hızının derinleşme hızını geçtiğini** gösteriyor. Eğer hedef “C/Rust alternatifi olmak” ise önümüzdeki 6–12 ayın önceliği yeni özellik eklemek değil, **temel garantileri gerçekten sağlamak ve iddiaları gerçekle hizalamak** olmalı.

En kritik tek cümle: **“Kesin İspat” yazan bir araç, ispatlayamadığında bunu söylemeli; aksi halde hiç doğrulama olmamasından daha tehlikelidir.**

---

## Ek A: İnceleme Kanıtları

| Deney | Komut / dosya | Sonuç |
|---|---|---|
| Test paketi | `python3 -m pytest -q` | `358 passed in 83.60s` |
| Dizi taşması | `print(arr[99])` | Çöp değer `11`, `EXIT=0` |
| `array_push` | `let mut arr = [1,2]; arr = array_push(arr,3)` | `realloc(): invalid pointer`, `EXIT=250` |
| Unicode | `len("ğüşiöç")` | `11` |
| Tip hatası | `let x = 1 < "abc"` | `true`, `EXIT=0` |
| Eksik dönüş | `maybe_positive(-5)` | `1`, `EXIT=0` |
| `check` sözleşme | `axiom check check2.ax` | “Doğrulama Başarılı” |
| Prover döngü | `axiom prove loop3.ax` | “0 Hata - Kesin İspat” |
| Aynı program çalışma | `axiom run loop3.ax` | `ENSURES` ihlali, `EXIT=101` |
| İç içe return | `pick(-1)` | `-1`, `EXIT=0` |
| Statik binary | `file hello` / `ldd hello` | Dinamik; `libz`, `libssl`, `libcrypto`, `libm`, `libc` |
| Yeni örnek 16 | `axiom run examples/16...` | `EXIT=0` |
| Yeni örnek 17 | `axiom run examples/17...` | `EXIT=0` |
| Yeni örnek 18 | `axiom run examples/18...` | `EXIT=0` |
| Self-hosted 17 | `axiomc build examples/17...` | Derlendi ve çalıştı |
| Self-hosted 18 | `axiomc build examples/18...` | Derlendi ve çalıştı |
| Self-hosted 05 | `axiomc build examples/05...` | 14 C derleme hatası |
| Self-hosted 08 | `axiomc build examples/08...` | 12 C derleme hatası |
| Self-hosted 09 | `axiomc build examples/09...` | 13 C derleme hatası |
| Self-hosted 16 | `axiomc build examples/16...` | 20 C derleme hatası |
| axiomc reproducible | `axiom build compiler/main.ax` | Aynı BuildID `1b7105...`, 64.664 bayt |
| README test sayısı | `README.md` | 161 (güncel değil) |
| MASTER_TODO test sayısı | `MASTER_TODO.md` | 335 (güncel değil) |
| Sürüm | `axiom --version` | Argparse hatası |
| REPL | `repl` | `v0.3.0` |
| Lisans | `ls LICENSE` | Yok |
| Git/CI | `ls -a` | `.git`, `.github`, `pyproject.toml`, `requirements.txt` yok |

## Ek B: İncelemenin Sınırlamaları

- Bu bir **güvenlik denetimi değil**, mühendislik incelemesidir. Kripto ve ağ kütüphaneleri için ayrıca uzman audit gerekir.
- İnceleme sırasında depo değişti: Faz 3/4/5 dosyaları 19:42–20:27 arasında eklendi. Rapor, 20:45 itibarıyla durumu yansıtır.
- Testler yalnızca x86_64 Linux üzerinde koşuldu; ARM64 iddiası doğrulanamadı.
- Performans iddiaları ölçülmedi; benchmark altyapısı olmadığı için “C hızı”, “AVX2”, “async web” doğrulanamıyor.
- Bazı bulgular örnek programlarla sınırlı; tüm dil yüzeyi taranmadı.
- Yeni Faz 3-5 modüllerinin tamamı tek tek güvenlik auditinden geçirilmedi; öne çıkan tasarım ve kapsam sorunları incelendi.

---

**Rapor sonu.**
