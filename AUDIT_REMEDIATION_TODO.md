# Axiom (λx) — İnceleme Raporu İyileştirme ve Güvenlik Sertleştirme Master Planı (TODO)

Bu belge, `~/Desktop/Axiom_Inceleme_Raporu.md` teknik denetim raporundaki tüm bulguları gidermek ve Axiom'u gerçek anlamda güvenli, sesli (sound) ve üretime hazır hale getirmek için hazırlanmış eylem planıdır.

---

## 🚨 AŞAMA 1: P0 — Acil Güvenlik ve Doğruluk Düzeltmeleri

### 1.1. Dizi Sınır Denetimi (Bounds Checking) ve Bellek Güvenliği
- [x] **1.1.1. Çalışma Zamanı Dizi Sınır Denetimi (Runtime Bounds Check):**
  - `axiom/codegen_c.py` ve `compiler/parser.ax` içinde dizi indeksleme (`arr[idx]`) işlemlerine `axiom_bounds_check(idx, arr.length, file, line)` kontrolü ekle.
  - Sınır dışı erişimde (`idx < 0` veya `idx >= length`) programın çöp değer okuması yerine `[AXIOM BELLEK IHLALI] Dizi sınır aşımı (Index out of bounds)` hatası vererek güvenli şekilde durmasını sağla.
- [x] **1.1.2. `array_push` Stack Belleği Hatasının Giderilmesi:**
  - `axiom/runtime.h` içindeki `axiom_array_push` makrosunu stack literallerine güvenli kopyalama yapacak şekilde düzelt; `malloc`/`realloc` çökmesini (`invalid pointer`) tamamen engelle.

### 1.2. Doğrulama Motoru (Prover) ve Sözleşmelerin Düzeltilmesi
- [x] **1.2.1. "Kesin İspat" İfadesinin Kaldırılması & Döngü Koruması:**
  - `axiom/prover.py` ve `axiom/z3_prover.py` içinde döngü (`while`, `for`) içeren fonksiyonlar için döngü invariantı verilmedikçe yanıltıcı `Kesin İspat` yerine `Kısmi Doğrulama / Döngü Nedeniyle Kanıtlanamadı (Unknown)` durumunu bildir.
  - Çözülemeyen karşı-örneklerde veya bilinmeyen durumlarda CLI çıkış kodunu `0` yerine uygun hata kodu yap.
- [x] **1.2.2. Tüm `return` Yollarının `ensures` ile Sarmalanması:**
  - `axiom/codegen_c.py` ve `compiler/codegen.ax` içinde `if/else`, `while` ve blok içi tüm erken dönüşleri (`return ...`) `ensures` sözleşmesiyle sarmala; iç içe dönüşlerde sözleşme ihlallerinin atlanmasını önle.
- [x] **1.2.3. `axiom check` ve `axiom prove` Entegrasyonu:**
  - `axiom check` komutunun sözleşmeleri de doğrulaması veya `--no-prove` parametresiyle kapsamının netleştirilmesi.

### 1.3. Kriptografik ve Ağ Protokollerinin Güvenli Hale Getirilmesi
- [x] **1.3.1. TLS Sertifika ve Hostname Doğrulaması (Anti-MITM):**
  - `axiom/runtime.h` içindeki `axiom_tls_connect` fonksiyonuna `SSL_CTX_set_verify(ctx, SSL_VERIFY_PEER, NULL)`, sistem CA sertifika havuzunun yüklenmesi (`SSL_CTX_set_default_verify_paths`) ve SNI / hostname doğrulamasını ekle.
- [x] **1.3.2. Sabit Zamanlı JWT ve Süre Kontrolü (Anti-Timing Attack):**
  - `runtime.h` içindeki `axiom_jwt_verify_hs256` fonksiyonunda `strcmp` yerine sabit zamanlı `CRYPTO_memcmp` kullan.
  - JWT token içindeki `exp` (expiration), `nbf` (not before) ve `iat` zaman kontrollerini ekle; süresi geçmiş token'ları reddet. `alg: none` saldırısını engelle.
- [x] **1.3.3. Güvenli C2 Protokolü:**
  - `std/net/c2.ax` içindeki sabit IV (`00010203...`) yerine her paket için kriptografik rastgele IV üretimini ve AES-256-GCM / HMAC-SHA256 authenticated encryption standartlarını uygula.
- [x] **1.3.4. WebSocket El Sıkışma Güvenliği:**
  - `runtime.h` içindeki sabit `Sec-WebSocket-Key` yerine rastgele 16 baytlık Base64 anahtar üretimi ve sunucu `Sec-WebSocket-Accept` doğrulaması ekle.
- [x] **1.3.5. Güvenli Proses Çalıştırma (Command Injection Koruması):**
  - `runtime.h` içine shell'siz doğrudan argüman dizisi alan `axiom_os_exec_argv` (`execve` / `posix_spawn`) API'si ekle.

### 1.4. Ofansif Modüllerin İzolasyonu ve Lisans
- [x] **1.4.1. Ofansif Siber Güvenlik Modülleri İzolasyonu:**
  - `shellcode`, `c2`, `evasion`, `memdump`, `packet_crafter` modüllerine açık güvenlik/etik uyarı başlıkları ekle ve izole et.
- [x] **1.4.2. `LICENSE` Dosyası:**
  - Kök dizine resmi MIT Lisansı metnini ekle.

---

## 🛠️ AŞAMA 2: P1 — Dil Güvenliği ve Tip Sistemi Sıkılaştırma

### 2.1. Tip Sistemi Deliklerinin Kapatılması
- [x] **2.1.1. Tür Uyuşmazlığı Karşılaştırma Yasağı (`int < str` engeli):**
  - `axiom/checker.py` içinde farklı ve dönüştürülemez türler arasındaki `<`, `>`, `<=`, `>=` karşılaştırmalarını derleme anında reddet (`SemanticError`).
- [x] **2.1.2. Eksik Dönüş (Definite Return) Analizi:**
  - `axiom/checker.py` içinde dönüş tipi `void` olmayan fonksiyonların tüm dallarında (`if/else` vb.) mutlak bir `return` ifadesi olup olmadığını denetle; eksik dönüşleri derleme hatası yap.
- [ ] **2.1.3. Tip Adı Normalizasyonu:**
  - `Int`, `Str`, `Bool` gibi büyük/küçük harf varyasyonlarını tutarlı şekilde normalize et.

### 2.2. Gerçek Karakter Tabanlı UTF-8 Metin Desteği
- [x] **2.2.1. Karakter Sayısı ve UTF-8 Desteği:**
  - `str_len` fonksiyonunu ve `len(str)` ifadesini UTF-8 çok baytlı karakterleri (ör. Türkçe `ğ, ü, ş, i, ö, ç`) sayacak şekilde güncelle (`len("ğüşiöç") == 6`). Bayt uzunluğu için `str_byte_len` fonksiyonu sağla.

### 2.3. C ve LLVM Çift Arka Uç (Backend) Eşitliği
- [ ] **2.3.1. LLVM IR `ensures` Desteği:**
  - `axiom/codegen_llvm.py` içine `ensures` çalışma zamanı sözleşme doğrulaması ekle. Eksik dönüşlerde `ret 0` yerine derleme hatası ver.

### 2.4. Faz 3 - Faz 5 Modüllerinin Derinleştirilmesi
- [ ] **2.4.1. AI / GEMM:** Gerçek AVX2 SIMD intrinsics ile optimize matmul implementasyonu.
- [ ] **2.4.2. Web Router:** Trie / Radix-tree desen eşleme derinleştirmesi.
- [ ] **2.4.3. YARA & Sigma:** Kurallı desen motorunun geliştirilmesi.
- [ ] **2.4.4. WASM:** Gerçek ikili modül encoder ve export yapısı.

---

## 🧪 AŞAMA 3: P2 & P3 — Doğrulama, Test ve Dokümantasyon

- [x] **3.1. Negatif Güvenlik Test Paketi (`tests/test_security_audit_fixes.py`):**
  - Dizi sınır aşımı yakalama testi (OOB).
  - Stack literali `array_push` testi.
  - TLS geçersiz sertifika reddi testi.
  - Sabit zamanlı JWT doğrulama testi.
  - C2 rastgele IV ve güvenli HMAC testi.
  - `os_exec_argv` shell enjeksiyonu önleme testi.
- [x] **3.2. Dokümantasyon ve Test Sayısı Senkronizasyonu:**
  - `README.md` ve `MASTER_TODO.md` belgelerini güncel test sayıları ve gerçek mimari kabiliyetlerle senkronize et.
