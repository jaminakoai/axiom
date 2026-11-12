# Axiom (λx) — Kapsamlı İyileştirme ve Güvenlik Yol Haritası (5 Kasım 2026)

> **Mühendislik İlkesi:** Sıfır Halüsinasyon, Sıfır Yalan İddia, Tam Bellek ve Aritmetik Güvenlik, Sesli Matematiksel İspat.

---

## 📌 FAZ 0: P0 Kritik Güvenlik ve Doğrulama Blokları (Derhal Çözülecek)

- [x] **P0.1: `bin/axiomc` Komut Enjeksiyonunun Kapatılması**
  - **Dosyalar:** `compiler/main.ax`, `axiom/runtime.h`
  - **Sorun:** `compiler/main.ax` içindeki derleme komutu `let compile_cmd = "clang ... " + tmp_c + " -o " + output_bin` string birleştirmesiyle `os_exec()` (yani `system()`) üzerinden çalıştırılıyor. `-o '/tmp/pwned; touch /tmp/INJECTED'` argümanı keyfi komut çalıştırıyor.
  - **Çözüm:** `compiler/main.ax` içinde `system()` kaldırıldı; doğrudan `compile_c` (`execvp`) API'si kullanıldı ve girdi/çıktı yolları `is_safe_path` katı karakter beyaz listesi filtresinden geçirildi.
  - **Test:** `tests/test_negative_security.py::test_negative_security_p0_1_axiomc_command_injection_prevention` testi başarıyla doğrulandı.

- [x] **P0.2: Aritmetik Güvenlik ve Sıfıra Bölme Koruması**
  - **Dosyalar:** `axiom/codegen_c.py`, `axiom/runtime.h`, `compiler/parser.ax`
  - **Sorun:** Sabit sıfıra bölmede `10 / 0` çöp değer basarak `exit 0` ile sonlanıyor (UB); değişkende SIGFPE çökmesi yaşanıyor; taşmalar sessizce sarıyor.
  - **Çözüm:** `runtime.h` içine `axiom_safe_div` ve `axiom_safe_mod` makroları eklendi, `codegen_c.py` ve `compiler/parser.ax` bölme ve mod işlemlerine güvenli sıfır denetimi entegre etti (`axiom_contract_fail("ARITHMETIC_ZERO_DIV", ...)`).
  - **Test:** `tests/test_negative_security.py::test_negative_security_p0_2_arithmetic_zero_division_protection` ile sabit ve değişken bölme/mod senaryolarının kontrollü 101 hata kodu ile durdurulduğu doğrulandı.

- [x] **P0.3: Doğrulama Motoru Sesliliği (Soundness) & `PrintStmt` Açığı**
  - **Dosyalar:** `axiom/prover.py`, `axiom/z3_prover.py`, `axiom/cli.py`
  - **Sorun:** `print(check_port(99999))` gibi `PrintStmt` içindeki çağrılar sembolik yürütmede gezilmediği için ispatlayıcı yanlış negatif vererek "0 Hata - Kesin İspat" ilan ediyor. Ayrıca `axiom check` sözleşmeleri hiç doğrulamıyor.
  - **Çözüm:** `prover.py` ve `z3_prover.py` içine `PrintStmt` ifadelerini sembolik olarak değerlendiren denetimler eklendi. `axiom check` varsayılan olarak `SymbolicProver` doğrulamasını çalıştıracak şekilde yapılandırıldı (`--no-prove` seçeneği eklendi).
  - **Test:** `tests/test_negative_security.py::test_negative_security_p0_3_print_stmt_prover_soundness` ile ihlallerin hem sembolik prover hem Z3 prover hem de `axiom check` tarafından yakalandığı doğrulandı.

- [x] **P0.4: Bellek Modeli Güvenliği & `str_free` Literal Koruması**
  - **Dosyalar:** `axiom/runtime.h`, `axiom/codegen_c.py`, `compiler/parser.ax`
  - **Sorun:** `str_free("literal")` çağrısı statik literal adresi serbest bırakmaya çalıştığı için `free(): invalid pointer` ile çöküyor.
  - **Çözüm:** `runtime.h` içindeki `axiom_str_free` fonksiyonuna `dladdr` ile ELF salt-okunur segment/rodata denetimi eklendi; literal göstericiler serbest bırakılmayarak güvenli şekilde no-op yapıldı.
  - **Test:** `tests/test_negative_security.py::test_negative_security_p0_4_str_free_literal_protection_under_asan` testi ile AddressSanitizer altında sıfır sızıntı ve sıfır çökme ile doğrulandı.

---

## 📌 FAZ 1: P1 Yüksek Öncelikli Sistem Eşitliği & Derinlik

- [x] **P1.1: Self-Hosted Derleyiciye Tip Denetimi & Generics Desteği**
  - **Dosyalar:** `compiler/tokens.ax`, `compiler/parser.ax`, `compiler/codegen.ax`, `compiler/main.ax`, `tests/test_self_hosted.py`
  - **Sorun:** `bin/axiomc`, `struct Box<T>` generic yapılarını parse edemiyor ve C syntax hatası (`ax_T <; ax_{ >;`) veriyordu; generic alanlar ve tip parametreleri C99 sözdizimine dönüştürülemiyordu; runtime yolu hardcoded idi.
  - **Çözüm:** `compiler/parser.ax` içerisine `parse_type_str` ve `monomorphize_structs_in_program` eklenerek generic struct'ların tam monomorflaştırılması (`Box_int`, `Pair_int_str`) sağlandı; `parse_primary` içinde generic struct ilklendirmeleri (`Box<int> { ... }`) ve fonksiyon çağrıları parse edildi; `compiler/codegen.ax` içinde monomorflaştırılmış C99 struct tanımları üretildi; `compiler/main.ax` içindeki hardcoded yollar `get_axiom_root()` ve `get_runtime_path()` ile dinamik (`AXIOM_HOME`, `PWD`, yerel göreli yol) hale getirildi; `bin/axiomc` yeniden derlendi.
  - **Test:** `tests/test_self_hosted.py::test_self_hosted_generics_box` testi eklendi ve tüm self-hosted testlerin başarıyla geçtiği doğrulandı.

- [x] **P1.2: LLVM Arka Ucu Düzeltmeleri**
  - **Dosyalar:** `axiom/codegen_llvm.py`, `axiom/runtime.h`, `tests/test_llvm.py`
  - **Sorun:** `ensures` blokları LLVM arka ucunda üretilmiyordu; `examples/17_ai_tensor_neural_net.ax` dosyası `fmul double %iop.37, 1.0` tip uyuşmazlığı (`i64` değerin double yerine kullanılması) nedeniyle LLVM ile derlenemiyordu.
  - **Çözüm:** `codegen_llvm.py` içinde BinaryOp kayan nokta işlemlerine ve karşılaştırmalara eksik `sitofp i64 to double` ve `uitofp i1 to double` instruksiyonları eklendi; `LetDecl`, `AssignStmt` ve `ReturnStmt` içinde tip dönüşümleri desteklendi; fonksiyon dönüşlerinde `ensures` sözleşme denetimi döngüsü ve sözleşme ihlali durumunda çıkış kodu 101 ile güvenli durdurma mekanizması enjekte edildi; `runtime.h` içindeki tensör ve aktivasyon fonksiyonlarının dışa aktarımı (`AXIOM_RUNTIME_FN`) LLVM runtime bağlantısı için düzeltildi; `test_llvm.py` içine `-lm` ve ensures testleri eklendi.
  - **Test:** `examples/17_ai_tensor_neural_net.ax` `--backend=llvm` ile başarıyla derlenip çalıştırıldı; `test_llvm_ensures_contract_success` ve `test_llvm_ensures_contract_violation` dahil tüm LLVM testlerinin (16/16) geçtiği doğrulandı.

- [x] **P1.3: Paket Yöneticisi (`axpm`) Gerçek İndirme ve Doğrulama**
  - **Dosyalar:** `axiom/package_manager.py`, `tests/test_package_manager.py`, `axiom/resolver.py`
  - **Sorun:** `axpm install` git clone yapmıyor; checksum dosya içeriğinin değil string'in özeti.
  - **Çözüm:** Git depolarının gerçek klonlanması (`git clone --depth 1`), yerel önbellek ve içerik bazlı SHA-256 doğrulaması (`compute_dir_checksum` ile `.git` atlanarak) sağlandı; `LockFile.verify` ve modül çözümleyici entegre edildi.

- [x] **P1.4: Çapraz Derleme ve WASM Hedeflerinin Gerçekçi Yapılandırılması**
  - **Dosyalar:** `axiom/cli.py`, `axiom/package_manager.py`, `README.md`, `tests/test_dwarf_and_multitarget.py`
  - **Sorun:** `--target wasm32-wasi` ve `--target aarch64` sistemde kurulu sysroot olmadığı için `bits/libc-header-start.h` hatası veriyor.
  - **Çözüm:** `validate_target_toolchain` fonksiyonu ile hedef sysroot/toolchain ön denetimi eklendi; eksik sysroot durumunda yönlendirici kurulum rehberi verildi; `--sysroot` parametresi eklendi ve dokümantasyonda bu hedeflerin "deneysel/harici toolchain gerektirir" olduğu belirtildi.

- [x] **P1.5: Ofansif Güvenlik Modülleri İzolasyonu & Yasal Uyarılar**
  - **Dosyalar:** `std/security/shellcode.ax`, `std/net/c2.ax`, `std/security/evasion.ax`, `std/security/memdump.ax`, `std/net/packet_crafter.ax`, `tests/test_redteam_libs.py`
  - **Sorun:** Yasal uyarı başlıkları yok; varsayılan test suitinde gerçek shellcode koşturuluyor.
  - **Çözüm:** `shellcode.ax`, `c2.ax`, `evasion.ax`, `memdump.ax` ve `packet_crafter.ax` dosyalarının başlıklarına açık "YASAL VE ETİK UYARI / LEGAL & ETHICAL DISCLAIMER: YALNIZCA YASAL İZİNLİ VE ETİK TEST ORTAMLARINDA KULLANIM İÇİNDİR. YETKİSİZ SİSTEMLERDE KULLANIMI YASALARA AYKIRIDIR." başlıkları eklendi; `tests/test_redteam_libs.py` test dosyasına ortam kontrolü (`AXIOM_SKIP_REDTEAM_TESTS`) ve bilgilendirme notu eklendi.
  - **Test:** `pytest tests/test_redteam_libs.py` ile tüm testlerin (6/6) başarıyla geçtiği doğrulandı.

---

## 📌 FAZ 2: P2/P3 Dokümantasyon Senkronizasyonu & Test Güvencesi

- [x] **P2.1: Sürüm Numaraları ve Test Sayısı Senkronizasyonu**
  - `axiom/__init__.py`, `README.md`, `cli.py`, `lsp.py`, `compiler/main.ax` sürümlerinin `v0.5.0-alpha` olarak eşitlenmesi.
  - README rozetinin gerçek durum olan `509+ Passed` olarak güncellenmesi.
  - "Statik ikili" ifadesinin "Bağımsız yürütülebilir yerel ikili (OpenSSL/libc dinamik bağlı)" olarak dürüstçe düzeltilmesi.
  - Proje statüsünün dürüstçe **"v0.5.0-alpha (Geliştirme / Araştırma Prototipi)"** olarak belirtilmesi ve bilinen sınırlamalar bölümünün eklenmesi.

- [x] **P2.2: Negatif Test Paketi ve Sürekli Doğrulama**
  - Tüm P0 ve P1 düzeltmeleri için kapsamlı negatif güvenlik ve entegrasyon testleri eklendi (`test_negative_security_p0_1_axiomc_command_injection_prevention`, `test_negative_security_p0_2_arithmetic_zero_division_protection`, `test_negative_security_p0_3_print_stmt_prover_soundness`, `test_negative_security_p0_4_str_free_literal_protection_under_asan`, `test_self_hosted_generics_box`, `test_llvm_ensures_contract_success`, `test_git_dependency_clone_and_lock_verification`).
  - Toplam test sayısı **520 passed in 273.87s (%100 başarı)** olarak doğrulandı ve CI altyapısı yeşile bağlandı.
