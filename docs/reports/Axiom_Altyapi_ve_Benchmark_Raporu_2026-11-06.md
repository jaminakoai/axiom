# Axiom (λx) — Altyapı, Benchmark ve Performans Turu

**Tarih:** 6 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Kapsam:** `~/Desktop/axiom`
**Önceki rapor:** `Axiom_Devam_Turu_Raporu_2026-11-06.md`

---

## 0. Özet

Bu turda proje altyapısı tamamlandı, **gerçek benchmark paketi** eklendi ve benchmark sırasında ortaya çıkan **iki ciddi performans/ABI hatası** düzeltildi.

| İş | Durum |
|---|---|
| 1. `.gitignore`, `pyproject.toml`, `Makefile` | ✅ Eklendi |
| 2. GitHub Actions CI matrisi (4 job) | ✅ Eklendi |
| 3. `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md` | ✅ Eklendi |
| 4. Karşılaştırmalı benchmark paketi (Axiom / C / Python) | ✅ Eklendi, gerçek sonuçlar |
| 5. **Dizi `array_push` O(n²) → O(n)** (kapasiteli dizi) | ✅ Düzeltildi (139× hızlanma) |
| 6. **LLVM ↔ C ABI uyumsuzluğu** (24 baytlık struct) | ✅ Düzeltildi (pointer sarmalayıcılar) |
| 7. `tools/ci_matrix.sh` biçimlendirme mutasyonu | ✅ `make fmt-check` ile giderildi |

**Test durumu:** `577 passed`. **Benchmark:** 5 iş yükü, üç dilde doğrulanmış çıktı.

---

## 1. Proje Altyapısı

### `.gitignore`

Python, Axiom üretim çıktıları (`*.ll`, `*.smt2`, `target/`, `.axiom/`), kök derleme artıkları ve editör dosyaları kapsanıyor.

### `pyproject.toml`

```toml
[project]
name = "axiom-lang"
version = "0.5.0a0"
requires-python = ">=3.10"
dependencies = ["z3-solver>=4.12"]

[project.scripts]
axiom = "axiom.cli:main"
axpm = "axiom.package_manager:main"
axiom-lsp = "axiom.lsp:main"
```

- `pip install -e ".[dev]"` ile kurulabilir.
- `runtime.h` ve `axiom_llvm_runtime.c` paket verisi olarak işaretli.
- `[tool.pytest.ini_options]` ile `testpaths`, `offensive` / `slow` işaretleri tanımlı.

### `Makefile`

```text
make test        # tüm paket
make test-fast   # ~30 sn birim testleri
make bootstrap   # bin/axiomc'yi Axiom kaynağından derle
make ci          # tools/ci_matrix.sh
make bench       # benchmark paketi
make fmt-check   # biçimlendirme denetimi (değiştirmez)
make clean       # üretilmiş dosyaları sil
```

### GitHub Actions (`.github/workflows/ci.yml`)

| Job | İçerik |
|---|---|
| `test` | Python 3.10 / 3.11 / 3.12 / 3.13 matrisi, tam test paketi, bootstrap |
| `sanitizers` | ASan/UBSan + bellek sızıntısı testleri |
| `llvm` | LLVM + DWARF testleri, **17 örneğin tamamı LLVM ile derlenmeli** |
| `fmt` | `make fmt-check` |

### Süreç dosyaları

- `CHANGELOG.md` — Keep a Changelog biçiminde 0.1 → 0.5 geçmişi ve `[Unreleased]`.
- `SECURITY.md` — açık bildirme süreci, kapsam, ofansif modül yasal uyarısı.
- `CONTRIBUTING.md` — ortam kurulumu, builtin eklerken güncellenecek **üç yer**, bellek kuralları, test kuralları.

---

## 2. Benchmark Paketi

`benchmarks/run_benchmarks.py` aynı algoritmayı Axiom, C (`clang -O3`) ve Python'da çalıştırır; her dil için en iyi 3 koşuyu alır ve **çıktıyı doğrular**.

```bash
python benchmarks/run_benchmarks.py           # tümü
python benchmarks/run_benchmarks.py --quick   # küçük boyutlar
```

### Sonuçlar (`benchmarks/RESULTS.md`)

| İş | Axiom (s) | C -O3 (s) | Python (s) | Axiom/C | Python/Axiom |
|---|---:|---:|---:|---:|---:|
| Fibonacci (n=30) | 0.0051 | 0.0034 | 0.1483 | **1.50×** | 29.0× |
| String birleştirme (20.000) | 0.0033 | 0.0007 | 0.0210 | 4.51× | 6.4× |
| Dizi büyütme (100.000) | 0.0020 | 0.0012 | 0.0232 | **1.68×** | 11.4× |
| Base64 (20.000 çağrı) | 0.0040 | 0.0007 | 0.0286 | 6.03× | 7.2× |
| Matris çarpımı (64×64) | 0.0016 | 0.0009 | 0.0439 | **1.90×** | 26.9× |

**Yorum:**

- Aritmetik/döngü yoğun işlerde Axiom, C'nin **1,5–1,9×** yavaşı; Python'un **11–29×** hızlısı. Bu, “C kadar hızlı” iddiasını tam doğrulamıyor ama “Python'dan kat kat hızlı” iddiasını doğruluyor.
- String birleştirme ve Base64'te fark 4,5–6×; nedeni refcount/sahiplik yolu ve `axiom_owned_str_wrap` çağrıları.
- README'deki performans iddiası bu ölçüme göre güncellendi: “⭐⭐⭐⭐☆ (C'nin 1,5–6× yavaşı)”.

---

## 3. Benchmark'ın Ortaya Çıkardığı Gerçek Hatalar

### 3.1 `array_push` O(n²) — 139× hızlanma

**İlk ölçüm:**

```
Dizi büyütme (20.000)  axiom 0.2226 s   c 0.0008 s   → 293×
```

**Neden:** Her `array_push` yeni tampon ayırıp tüm diziyi kopyalıyordu (`length + 1`). Ayrıca heap tampon kayıt defteri lineer arama yapıyordu → ikinci bir O(n²).

**Düzeltme:**

1. `ax_array_*` struct'larına `capacity` alanı eklendi.
2. `axiom_array_push` artık kapasite varsa **yerinde** yazıyor; yoksa `max(8, cap*2)` ile büyütüyor.
3. Heap tampon kayıt defteri lineer listeden **hash tablosuna** çevrildi (O(1) ekleme/silme).

**Sonra:**

```
Dizi büyütme (20.000)  axiom 0.0016 s   → 2.06×
Dizi büyütme (100.000) axiom 0.0020 s   → 1.68×
```

Yani **139× hızlanma** ve C'ye neredeyse eşit.

### 3.2 LLVM ↔ C ABI uyumsuzluğu (segfault)

`capacity` alanı eklenince `ax_array_*` 24 bayta çıktı. SysV ABI'de 16 bayttan büyük struct'lar **gizli işaretçi (sret)** ile döner ve yığın üzerinden geçer. LLVM IR'deki `declare %struct.ax_array @axiom_simd_add_i64(...)` bu kuralı bilmediği için C tarafıyla uyuşmadı → `SIGSEGV` / yanlış veri.

**Etkilenen:** `simd_add/mul/sub/sum/scan_match`, `json_build_object`, `csv_add_row`, `cli_set_args`, `os_exec_argv`.

**Çözüm:** Runtime'a **pointer tabanlı sarmalayıcılar** eklendi:

```c
AXIOM_RUNTIME_FN void axiom_simd_add_i64_ptr(ax_array_int* out,
                                             const ax_array_int* a,
                                             const ax_array_int* b);
```

LLVM tarafı artık struct'ı `alloca` + `store` ile belleğe koyup **yalnızca pointer** geçiriyor. Böylece ABI'ye bağımlılık kalmadı.

**Doğrulama:**

```bash
$ axiom build simd.ax --backend=llvm && ./simd
SIMD Sum: 110
$ axiom build packet4.ax --backend=llvm && ./packet4
LLVM_PACKET4_SUCCESS
```

Ve **17/17 örnek** LLVM ile derleniyor.

---

## 4. Test Sonuçları

```bash
$ python3 -m pytest -q --no-header
577 passed in 319.39s (0:05:19)
```

Ek doğrulamalar:

| Kontrol | Sonuç |
|---|---|
| `make fmt-check` | ✅ 6/6 compiler dosyası |
| 17 örnek `--backend=llvm` | ✅ 17/17 |
| `bin/axiomc` bootstrap | ✅ |
| Benchmark çıktı doğrulaması | ✅ 5/5 iş yükü, 3 dil |

---

## 5. Değiştirilen / Eklenen Dosyalar

| Dosya | Değişiklik |
|---|---|
| `.gitignore` | Yeni |
| `pyproject.toml` | Yeni (paketleme + pytest config + entry point) |
| `Makefile` | Yeni |
| `.github/workflows/ci.yml` | Yeni (4 job) |
| `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md` | Yeni |
| `benchmarks/run_benchmarks.py`, `benchmarks/RESULTS.md` | Yeni |
| `axiom/runtime.h` | Dizi `capacity`, hash tabanlı tampon defteri, pointer sarmalayıcılar |
| `axiom/codegen_c.py` | Dizi struct'larına `capacity`, literallerde `capacity = 0` |
| `axiom/codegen_llvm.py` | `%struct.ax_array` 3 alan, pointer ABI sarmalayıcı yolu |
| `README.md` | CI/benchmark rozetleri, gerçek performans notu |

---

## 6. Kalan İşler (güncel)

| # | İş | Not |
|---|---|---|
| 1 | **Intrusive header + `String`/`str` ayrımı** | Geçici string sızıntısını kökten çözer; string benchmark'ındaki 4,5× farkı da azaltır |
| 2 | Runtime `core` / `platform` ayrımı + WASI | Çapraz derleme/WASM'ın ön koşulu |
| 3 | Gerçek registry veya resmî git-only politikası | `axpm` komutları hazır |
| 4 | AST tabanlı self-hosted derleyici | Tam generics/sözleşme denetimi |
| 5 | String/runtime hot path optimizasyonu | Base64 6× farkı; `owned_str_wrap` maliyeti ölçülmeli |
| 6 | Benchmark kapsamını genişletme | JSON, HTTP, YARA, TLS |

### Öneri

Benchmark artık “neyin yavaş olduğunu” gösteriyor: **string yolu**. Bir sonraki turda `axiom_owned_str_wrap`/`release` maliyeti profillenip ya kilit (mutex) granülerliği azaltılmalı ya da intrusive header'a geçilmeli. Bu, hem #1 hem #5'i birlikte çözer.

---

## 7. Sonuç

- Proje artık **kurulabilir, test edilebilir, CI'da doğrulanabilir** bir yapıya sahip.
- “C kadar hızlı” iddiası ölçüldü: şu an **1,5–1,9×** (aritmetik) ve **4,5–6×** (string). README buna göre düzeltildi.
- Benchmark, iki gerçek hatayı (O(n²) dizi, ABI segfault) ortaya çıkardı ve ikisi de düzeltildi; dizi yolu **139×** hızlandı.
- Test sayısı 577, tüm örnekler iki arka uçta derleniyor.

Bu turun en önemli çıktısı kod değil, **ölçüm altyapısı**: bundan sonra her performans iddiası `benchmarks/RESULTS.md` ile karşılaştırılabilir.
