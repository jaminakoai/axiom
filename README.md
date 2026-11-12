# Axiom Programming Language (λx)

[![Axiom Version](https://img.shields.io/badge/Axiom-v0.5.0--alpha-blue.svg)](#)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#)
[![Tests](https://img.shields.io/badge/Tests-1022%20Passed-brightgreen.svg)](#)
[![Benchmarks](https://img.shields.io/badge/Benchmarks-sonuclar-blue.svg)](benchmarks/RESULTS.md)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-success.svg)](.github/workflows/ci.yml)
[![Target](https://img.shields.io/badge/Target-Native%20x86__64%20%7C%20ARM64%20deneysel-orange.svg)](#)

> **"Python kadar zarif ve hızlı yazılan, C/Rust kadar hızlı koşan ve matematiksel sözleşmelerle mantık hatalarını derleme anında durduran yeni nesil sistem programlama dili."**

> 🌍 **English:** [README.en.md](README.en.md)

---

## 🔎 Axiom bugün ne işe yarar? — Çevrimdışı DFIR ve güvenlik kanıtı triyajı

Axiom bir dil ve derleyicidir. Bu dilin üzerine yazılmış iki araç bugün
**çevrimdışı** (canlı servise/ağa ihtiyaç duymayan) güvenlik triyajı için
kullanılabilir:

| Araç | Girdi | Yaptığı analiz | Çıktı |
|---|---|---|---|
| **`axiom-scan`** (`examples/21_axiom_scan.ax`) | YARA alt kümesi kural dosyası + bir dosya **veya** PCAP | metin, hex-wildcard ve basit regex desenleri; `any of them` / `all of them` koşulları | Şema sürümlü JSON: `schema_version`, `tool_version`, `rules_count`, `target_sha256`, `scanned_bytes`, `match_count`, eşleşmeler |
| **DFIR triyajı** (`examples/22_dfir_triage.ax`) | Çalışan sistem (`/proc`) ve isteğe bağlı log dosyası (`AXIOM_DFIR_LOG`) | süreç listesi, dinlenen TCP portları, kritik dosya SHA-256 bütünlüğü, Sigma kuralıyla log taraması | Tek JSON rapor: `processes`, `network`, `integrity`, `log`, `detections`, `risk` |

**Hangi somut işi kolaylaştırır?**

- Bir olay müdahalesinde "bu dosya/PCAP bilinen bir deseni içeriyor mu?" sorusunu
  **tek bağımsız ikiliyle**, Python/venv/pip kurmadan yanıtlar.
- Rapor, taranan hedefin **SHA-256'sını** taşır; böylece "hangi baytlar tarandı"
  sorusu kanıt zincirine bağlanabilir.
- `--fail-on-match` ile bulgu varken **exit 10** döner; CI veya kabuk betiği
  taramayı kapı olarak kullanabilir (bayraksız davranış değişmez, exit 0).
- Hatalar da şemalı JSON olarak (`"ok":false`) ve **exit 1** ile döner; çıktıyı
  ayrıştıran araç tek biçim görür.

**Hedef kullanıcı:** SOC/DFIR analisti, olay müdahalecisi, malware triyajı yapan
güvenlik mühendisi ve çevrimdışı/air-gapped ortamda kanıt toplayan ekip.
Ayrıca güvenlik aracını kendi dilinde yazmak isteyen sistem programcısı.

**Dürüst sınırlar (v0.2):**

- `axiom-scan` **YARA'nın tamamı değildir**: alt küme desenler ve basit koşullar
  desteklenir; gelişmiş YARA modülleri/koşulları yoktur.
- `scan` metin tabanlıdır: NUL baytı içeren dosya **ilk NUL'da kesilir**.
  `target_sha256` yine tüm dosyayı kapsar; `scanned_bytes` yalnız okunabilen
  öneki gösterir.
- PCAP'te her paket ayrı taranır; **akış yeniden birleştirme (TCP reassembly) yoktur**.
- DFIR aracı Linux `/proc` tabanlıdır; Windows/macOS'ta süreç ve port toplama
  yoktur. Bir tespit/politika motoru değildir: risk skoru üretir, exit kodunu
  değiştirmez.
- Araçlar henüz "üretimde kanıtlanmış" değildir; testler ve örneklerle
  doğrulanmış alfa prototiplerdir.

Ayrıntılı kullanım: [axiom-scan v0.2](#13-axiom-scan-v02--güvenlik-kanıtı-taramasi)
ve [DFIR triyajı](#11-dfir-triyajı-tek-json-rapor-faz-1-kapanış-aracı).

---

## ⚡ Neden Axiom?

Günümüz dillerinde iki aşırı uç vardır:
* **Python:** Öğrenmesi ve geliştirmesi inanılmaz ergonomik; ancak çalışma zamanında yavaş, devasa bellek tüketimine sahip ve tip/mantık hatalarını ancak üretimde fırlatır.
* **Rust:** Muazzam bellek güvenliği ve çıplak metal hızı; fakat borrow checker kuralları, `'a` ömür muhasebesi ve uzun derleme süreleri nedeniyle yüksek bilişsel yük getirir.

**Axiom bu iki kutup arasındaki boşluğu kapatır:**
1. **Sıfır Bilişsel Yük:** Borrow checker savaşı yok. `defer` tabanlı kapsam temizliği, sahiplik takipli string birleştirme ve sınır denetimli diziler.
2. **Çöp Toplayıcısız (Zero-GC):** Duraksama yok. Gerçek zamanlı sistemler ve güvenlik araçları için öngörülebilir mikro-saniye gecikme.
3. **Sözleşmeli Doğrulama (Contract-Driven Logic Safety):** `requires`, `ensures` ve `verify` blokları ile mantık hataları ve sınır taşmaları daha derleme anında tespit edilir.
4. **Beklenen Hatalar İçin `Result<T, E>` + `?`:** Dosya yok, port kapalı, ağ hatası gibi *beklenen* durumlar `Result` ile akar; `?` operatörü hatayı üst katmana iletir, `defer` temizliği çalışır. `main` de `Result<int, str>` dönebilir (Err → stderr + exit 1). Stdlib'in `Result` katmanı hazırdır: `std/io/file`, `std/encoding/json`, `std/net/http`, `std/crypto/tls`, `std/os/process`. Sözleşme ihlalleri (`requires`/`ensures`/`verify`) ise *programlama hatası* sayılır ve programı durdurur.
5. **Bağımsız ELF İkili Dosyası (Standalone Binary):** Python gibi bağımlılık cehennemi yok; tek bir komutla bağımsız ELF ikili dosyası üretir (Sistem OpenSSL ve glibc kütüphanelerine dinamik bağlıdır).

---

## 🚀 Hızlı Başlangıç

### Gereksinimler
* Linux (x86_64 / ARM64)
* Python 3.10+ (Axiom Bootstrap Derleyicisi için)
* `clang` veya `gcc` (Yerel ikili derleme için)

### Kurulum ve CLI Erişimi
```bash
cd /path/to/axiom
export PATH="$PWD/bin:$PATH"

# (İsteğe bağlı) Axiom ile yazılmış self-hosted derleyiciyi üret:
# depoda ELF ikili tutulmaz, bu yüzden `bin/axiomc` yerelde derlenir.
axiom build compiler/main.ax -o bin/axiomc
```

### Etkileşimli REPL (Interactive Shell)
```bash
axiom repl
```
```
Axiom (λx) v0.5.0-alpha - İnteraktif REPL
Yardım için 'help', çıkış için 'exit' veya 'quit' yazın.

axiom> let x = 40
axiom> x + 2
42
axiom> file_write("test.txt", "Axiom Native IO")
true
axiom> file_read("test.txt")
Axiom Native IO
axiom> quit
```

### 🎯 Yol Haritası

Projenin tek geçerli planı: **[TODO.md](TODO.md)** — nerede olduğumuz, nereye gittiğimiz,
faz kapıları, ölçüm panosu ve AI ajanları için çalışma kuralları.

### 📘 Başlangıç Rehberi ve Şartname

- **[docs/TUTORIAL.md](docs/TUTORIAL.md)** — sıfırdan başlayanlar için: kurulum,
  temel sözdizimi, struct/diziler, sözleşmeler, `Result` + `?` hata modeli,
  stdlib, eşzamanlılık, araçlar, yaygın hatalar.
- **[SPECIFICATION.md](SPECIFICATION.md)** — v0.5 dil şartnamesi: sözcüksel yapı,
  tipler, ifadeler, hata modeli, bellek modeli, ABI, çıkış kodları, EBNF özeti.
- **[docs/reports/](docs/reports/README.md)** — tüm geliştirme turlarının raporları
  (43 rapor, tarihsel dizin; her biri bulunan gerçek hataları ve doğrulama
  komutlarını içerir).

Her iki belgedeki kod blokları CI'da derlenerek doğrulanır.

### İlk Axiom Programını Çalıştırma
```bash
axiom run examples/01_hello.ax
```

### Bağımsız Yerel İkili Dosya Derleme (Native Build)
```bash
axiom build examples/01_hello.ax -o hello
./hello

# Çapraz Derleme (Harici toolchain ve sysroot gerektirir / Deneysel):
axiom build examples/01_hello.ax --target aarch64-linux-gnu -o hello_arm
axiom build examples/01_hello.ax --target wasm32-wasi --sysroot /path/to/wasi-sysroot -o hello.wasm
```

---

## 📖 Kod Örnekleri

### 1. Merhaba Dünya & Temel Mantık
```axiom
# examples/01_hello.ax
fn main() -> int {
    let msg = "Axiom sistemine hos geldiniz!"
    print(msg)
    
    let mut sum: int = 0
    for i in 1..11 {
        sum = sum + i
    }
    
    print("1'den 10'a kadar toplam:")
    print(sum)
    return 0
}
```

### 2. Güvenlik Sözleşmeleri (Formal Verification)
```axiom
# examples/03_contracts.ax
fn port_scan(target_ip: str, port: int) -> bool
    requires port > 0 and port <= 65535      # Gecersiz portlar derleme/calisma aninda engellenir
{
    print("Hedef taranıyor...")
    print(target_ip)
    print(port)
    return true
}

fn main() -> int {
    port_scan("192.168.1.1", 80)
    # port_scan("192.168.1.1", 70000)  <-- Bu satir hata firlatir!
    return 0
}
```

### 3. Veri Yapıları (Struct), Dinamik Diziler ve Yerel POSIX Ağ Soketleri
```axiom
# examples/05_real_scanner.ax
struct TargetHost {
    ip: str,
    port: int
}

fn scan_target(target: TargetHost) -> int {
    let fd = tcp_connect(target.ip, target.port)
    if fd >= 0 {
        print("[ACIK PORT BULUNDU]", target.ip, target.port)
        socket_close(fd)
        return 1
    }
    return 0
}

fn main() -> int {
    let ports = [22, 80, 443, 8080]
    let t_start = time_now_ms()

    for i in 0..len(ports) {
        let t = TargetHost { ip: "127.0.0.1", port: ports[i] }
        scan_target(t)
    }

    let elapsed = time_now_ms() - t_start
    print("Toplam tarama suresi (ms):", elapsed)
    return 0
}
```

### 4. Çoklu Modül, Dosya I/O ve Sistem Çağrıları
```axiom
# examples/06_modules/main.ax
import "utils.ax"

fn main() -> int {
    let report = create_report("Sistem Yapılandırması", 3)
    let ok = file_write("/tmp/log.txt", "Axiom v0.5.0-alpha I/O")
    if ok and file_exists("/tmp/log.txt") {
        let content = file_read("/tmp/log.txt")
        print("Okunan:", content)
    }
    let user = os_getenv("USER")
    print("Kullanıcı:", user)
    return 0
}
```

### 5. Standart Kütüphane (std:net/http.ax) & Güvenlik Banner Grabber
```axiom
# examples/07_http_banner_grabber.ax
import "std:net/http.ax"

struct BannerReport {
    target: str,
    port: int,
    is_http: bool,
    server_nginx: bool
}

fn scan_target(host: str, port: int) -> void {
    let response = http_get(host, port, "/")
    let is_nginx = str_contains(response, "nginx")
    print("Hedef:", host, "Nginx mi:", is_nginx)
}
```

### 6. Çok İş Parçacıklı Eşzamanlı Tarayıcı & Statik İspat Motoru
```axiom
# examples/08_multithreaded_scanner.ax
fn worker(port: int) -> int
    requires port >= 1 and port <= 65535
{
    let fd = tcp_connect("127.0.0.1", port)
    if fd >= 0 { socket_close(fd); return 1; }
    return 0;
}

fn main() -> int {
    let t1 = thread_create(worker, 80)
    let t2 = thread_create(worker, 443)
    let r1 = thread_join(t1)
    let r2 = thread_join(t2)
    return 0
}
```

Matematiksel ispat motorunu çalıştırmak:
```bash
axiom prove examples/08_multithreaded_scanner.ax
```

### 6. Heterojen SIMD Vektör Hızlandırma ve Z3 SMT Teorem İspatı
```axiom
# examples/09_simd_vector_scan.ax
@simd
fn parallel_signature_score(weights: int[], base_risk: int[]) -> int
    requires len(weights) > 0 and len(base_risk) > 0
    ensures return >= 0
{
    let multiplied = simd_mul_i64(weights, base_risk)
    return simd_sum_i64(multiplied)
}
```

Z3 SMT Solver ile tam teorem ispatı ve LLVM IR derleme:
```bash
# Z3 SMT Motoru ile formal teorem kanıtlama:
axiom prove examples/09_simd_vector_scan.ax --smt

# Standart SMT-LIB2 formatı dışa aktarma:
axiom emit-smt examples/09_simd_vector_scan.ax

# Doğrudan LLVM IR üretme ve Clang ile derleme:
axiom emit-llvm examples/09_simd_vector_scan.ax
axiom build examples/09_simd_vector_scan.ax --backend=llvm -o simd_scan
```

### 7. Red Team & Ofansif Siber Güvenlik Suiti (Faz 2)
```axiom
# examples/15_redteam_offensive_suite.ax
import "std/security/shellcode.ax"
import "std/net/packet_crafter.ax"
import "std/security/evasion.ax"
import "std/net/c2.ax"
import "std/security/memdump.ax"

// Anti-debugging, dinamik API hashing, bellek kabuk kodu çalıştırma, ham IP paket sentezi
```

> **Not:** Ofansif modüller varsayılan derlemede reddedilir. Derlemek için `--features offensive` (veya `AXIOM_FEATURES=offensive`) kullanın.

### 8. Blue Team & DFIR Defansif Güvenlik Suiti (Faz 3)
```axiom
# examples/16_blueteam_defensive_suite.ax
import "std/security/yara.ax"
import "std/net/pcap.ax"
import "std/security/sigma.ax"
import "std/os/forensics.ax"
import "std/security/integrity.ax"

// Canlı PCAP yakalama, Sigma kural motoru, YARA desen tarama, FIM bütünlük denetimi
```

### 9. Yapay Zeka (AI/ML) Tensör & Derin Öğrenme Motoru (Faz 4)
```axiom
# examples/17_ai_tensor_neural_net.ax
import "std/ai/tensor.ax"
import "std/ai/linalg.ax"
import "std/ai/autograd.ax"
import "std/ai/nn.ax"
import "std/ai/inference.ax"

// AVX2 SIMD GEMM matris çarpımı, ReLU & Sigmoid forward pass, Argmax sınıflandırma, Autograd geriye yayılım
```

### 10. Modern Web Framework & WASM Hedefi (Faz 5)
```axiom
# examples/18_web_api_framework.ax
import "std/web/router.ax"
import "std/web/app.ax"
import "std/web/template.ax"
import "std/target/wasm.ax"

// Radix pattern yönlendirici, CORS & Auth Guard middleware, XSS korumalı şablonlama, WebAssembly ikili modülü
```

### 11. DFIR Triyajı: Tek JSON Rapor (Faz 1 kapanış aracı)
```axiom
# examples/22_dfir_triage.ax
import "std/os/forensics"
import "std/security/integrity"
import "std/security/sigma"
import "std/encoding/json"

// /proc süreç listesi + dinlenen portlar + SHA-256 bütünlük + Sigma eşleşmesi
// -> tek JSON rapor (risk skoru ve verdict dahil)
```
```bash
axiom run examples/22_dfir_triage.ax
AXIOM_DFIR_LOG=/var/log/auth.log axiom run examples/22_dfir_triage.ax
```

### 13. `axiom-scan` v0.2 — Güvenlik kanıtı taraması

```bash
# Tek bağımsız ikili üret (çalışma zamanı bağımlılığı yok)
axiom build examples/21_axiom_scan.ax -o axiom-scan

# Kural dosyasını doğrula
./axiom-scan rules kurallar.yar

# Dosya tara (JSON stdout)
./axiom-scan scan ornek.bin --rules kurallar.yar

# Bulgu varsa exit 10 (CI kapısı); bulgu yoksa exit 0
./axiom-scan scan ornek.bin --rules kurallar.yar --fail-on-match

# PCAP tara (her paket ayrı; akış birleştirme yok)
./axiom-scan pcap trafik.pcap --rules kurallar.yar --fail-on-match
```

Gerçek çıktı (bulgu var, `--fail-on-match` yok → `exit 0`):

```json
{"schema_version":"1","tool":"axiom-scan","tool_version":"0.2.0","rules_count":1,
 "ok":true,"target":"dirty.txt",
 "target_sha256":"21f10114c2932724770202eff83c9109322c2d605efd0e9e6c2a157dd0866551",
 "scanned_bytes":18,"match_count":1,
 "matches":[{"rule":"R1","pattern":"$a","offset":5,"length":7}]}
```

Çıkış kodları: `0` rapor üretildi (bulgu yok veya bayrak verilmedi) · `10`
`--fail-on-match` verildi ve bulgu var · `1` hata (dosya/kural/kullanım).

### 12. Hata Modeli: `Result<T, E>` ve `?` Operatörü

```axiom
# examples/19_error_handling.ax
import "std/core/error"

fn parse_port(s: str) -> Result<int, str> {
    let v = str_to_int(s)
    if v <= 0 or v > 65535 {
        return result_err<int>("gecersiz port: " + s)
    }
    return result_ok<int>(v)
}

fn resolve_port(host: str, port_str: str) -> Result<int, str> {
    defer { print("[temizlik] resolve_port cikisi") }
    let port = parse_port(port_str)?      # Err ise hata yukari iletilir
    return result_ok<int>(port)
}

fn main() -> int {
    let r = resolve_port("127.0.0.1", "99999")
    print("HATA:", r.error)
    print("YEDEK:", result_unwrap_or<int>(r, -1))
    return 0
}
```

> `?` yalnızca `Result` döndüren fonksiyonlarda kullanılabilir; erken dönüşte
> `defer` blokları ve sahiplik temizliği çalışır. Sözleşme ihlalleri (`requires`,
> `ensures`, `verify`) bu yoldan geçmez — onlar programlama hatasıdır ve durdurur.

---

## 🛠️ Mimari Genel Bakış

Axiom derleyicisi modüler mimari bileşenlerinden oluşur:

```
axiom/
├── lexer.py        # Tokenizer: Temiz blok ve sözdizim ayrıştırma (@simd desteği)
├── ast_nodes.py    # Soyut Sözdizim Ağacı (AST) düğüm tanımları
├── parser.py       # Recursive Descent Parser
├── resolver.py     # Bağımlılık ve Stdlib Import Çözümleyici ('std:...')
├── checker.py      # Tip çıkarımı, kapsam ve sözleşme (contract) analizi
├── prover.py       # Sembolik Yürütme ve Statik Matematiksel İspat Motoru ('axiom prove')
├── z3_prover.py    # Z3 SMT Solver Teorem İspat Motoru ('axiom prove --smt', 'emit-smt')
├── formatter.py    # Kanonik kaynak kod biçimlendirici (canonical formatter)
├── codegen_c.py    # Yüksek başarımlı C99 / Native kod üreteci
├── codegen_llvm.py # Doğrudan LLVM Intermediate Representation (.ll) kod üreteci
├── runtime.h       # AVX2/SSE SIMD, POSIX pthread, OpenSSL 3 TLS/AES, tensör motoru ve ağ soketleri
└── cli.py          # 'axiom' CLI sürücüsü (run, build, check, prove, emit-c, emit-smt, emit-llvm, doc, init, fmt, repl, test)
compiler/           # Axiom ile yazılmış Self-Hosted Derleyici (λx)
├── tokens.ax       # Token sabitleri
├── lexer.ax        # Sözcüksel analizci
├── ast.ax          # AST tanımları
├── parser.ax       # Sözdizim ayrıştırıcı
├── codegen.ax      # Bağımsız C99 kod üreticisi
└── main.ax         # 'bin/axiomc' CLI ikili yürütücüsü (Python gerektirmez!)
std/                # 52 Standart Kütüphane Modülü / 385 fonksiyon
├── ai/             # tensor, linalg, autograd, nn, inference
├── web/            # router, app, template
├── target/         # wasm
├── security/       # shellcode, evasion, memdump, yara, sigma, integrity
├── net/            # packet_crafter, c2, pcap, http_server, tls, websocket, udp, dns
├── os/             # forensics, process
├── crypto/         # aes, jwt, hash
└── encoding/       # json, base64, hex, html, csv, zlib
```

---

## 📊 Karşılaştırma Tablosu

| Özellik | Python | Rust | Axiom (λx) |
| :--- | :---: | :---: | :---: |
| **Yazım Hızı & Ergonomi** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Saf Makine Hızı** | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐☆ (C'nin 1,5–6× yavaşı; bkz. benchmarks/RESULTS.md) |
| **Çöp Toplayıcısız (No GC)** | ❌ | ✅ | ✅ |
| **Borrow Checker Zorluğu** | Yok | Yüksek | **Yok (Otomatik)** |
| **Mantık Doğrulama (`requires`/`ensures`)** | ❌ | Kısmi/Harici | **Yerleşik (Built-in)** |
| **Dağıtım** | Hantal (venv/pip) | Statik Binary | **Bağımsız ELF İkili Dosyası (OpenSSL/glibc dinamik bağlı)** |

---

## 🧪 Testleri çalıştırma

```bash
# Bagimliliklar: python3 + pytest, clang/gcc
python3 -m pytest -q --no-header -p no:cacheprovider
```

Tek bir örnek/alanı hedeflemek için:

```bash
python3 -m pytest -q tests/test_axiom_scan.py -p no:cacheprovider
python3 -m pytest -q tests/test_self_hosted.py -p no:cacheprovider
```

Test altyapısı notları:

- Testlerdeki `subprocess` çağrılarına varsayılan **900 s** zaman aşımı uygulanır
  (`AXIOM_TEST_TIMEOUT` ile değiştirilebilir); takılan bir ikili günlerce
  çalışmaz.
- Windows hedefi testleri `wine` üzerinde gerçek çalıştırma yapar; wine yoksa
  ilgili testler ortam nedeniyle atlanır. Oturum sonunda wine prefix'leri silinir.
- Son doğrulanmış tam koşu: **1022 passed, 0 failed, 0 skipped**
  (12 Kasım 2026, Linux x86_64).

---

## 🧭 Proje durumu ve yol haritası

> Bu bölüm **ürün görünümüdür**; teknik doğruluk kaynağı [TODO.md](TODO.md)'dir.
> İşaretler: ✅ tamamlandı ve testle doğrulandı · 🟡 kısmi · ⬜ başlanmadı.
> Yüzdeler kesin ölçüm değil; özellik/test/doküman durumuna dayalı tahmindir.

### ✅ Tamamlanan (testle doğrulanmış)

- Derleyici hattı: lexer → parser → resolver → checker → prover → C99/LLVM kod üretimi.
- İki arka uç paritesi: `defer`, `?`, string/dizi kapsam temizliği, DWARF.
- `requires` / `ensures` / `verify` sözleşmeleri ve Z3 SMT ile statik ispat.
- `Result<T,E>` + `?` hata modeli; `main` için `int` veya `Result<int,str>`.
- 21 örnek program: C **21/21**, LLVM **21/21**, self-hosted `bin/axiomc` **21/21**,
  Windows hedefi wine altında **21/21**.
- 52 stdlib modülü / 385 fonksiyon; güvenlik, ağ, kodlama, dosya, zaman, regex.
- `axiom-scan` v0.2: şema sürümlü JSON, `target_sha256`, `--fail-on-match`.
- DFIR triyaj aracı (`examples/22_dfir_triage.ax`): süreç/port/bütünlük/Sigma → tek JSON.
- HTTP istemcisi, gerçek JSON parser, YARA/Sigma motorları, PCAP okuyucu.
- Paket yöneticisi + registry v1 (ed25519 imza, semver, transitive, yanked).
- LSP (10 metod), `axiom doc`, TR+EN rehber ve şartname, 43 geliştirme raporu.
- Linux ve Windows hedefi; NFC/NFD normalizasyonu; epoll tabanlı olay döngüsü.

### 🟡 Üzerinde çalışılan / kısmi

- **Windows:** çapraz derleme + `wine` ile çalıştırma doğrulandı; gerçek Windows
  makinede CI koşusu yok.
- **macOS:** runner/doğrulama yok.
- **WASI:** `--sysroot` olmadan derlenmez; WASM encoder deneysel.
- **Statik bağlama:** ikililer glibc/OpenSSL/zlib'e dinamik bağlı; tam statik
  musl desteği yok.
- **Registry:** altyapı hazır, yayınlanmış paket yok.
- **Saat dilimi:** sabit ofset; IANA/DST veritabanı yok.
- **Unicode:** NFC/NFD var; NFKC/NFKD yok.
- **Regex:** POSIX ERE + ReDoS adım bütçesi; PCRE2/RE2 yok.
- **YARA:** alt küme; tam YARA değil. PCAP'te akış birleştirme yok.

### ⬜ Planlanan

- `v1.0` API kararlılığı ve 2 sürüm geriye uyum taahhüdü.
- Gerçek Windows ve macOS CI runner'ları; WASI sysroot ile uçtan uca test.
- Statik (musl) ikili üretimi.
- Yayınlanmış paket ekosistemi (hedef: 200+ paket) ve ilk kurumsal kullanıcı.
- `axiom prove` çıktısından IEC 62304 / ISO 26262 denetim kanıt paketi.
- DFIR aracı için: Windows/macOS toplama, PCAP akış birleştirme, imzalı rapor.

**Bu bölüm nasıl güncellenir?** Bir iş `TODO.md`'de `[x]` olduğunda, kabul
maddeleri çalıştırılıp tam test paketi yeşil kaldığında satır ✅'ya taşınır;
aynı değişiklikte `CHANGELOG.md` ve README'deki test sayısı güncellenir.
Kod + test kanıtı olmadan hiçbir madde ✅ yapılmaz; tahminler "planlanan" kalır.

---

## 🤝 Katkı

Katkı kuralları [CONTRIBUTING.md](CONTRIBUTING.md)'dedir. Kısaca: küçük ve geri
alınabilir değişiklikler, önce test, gerçek çıktıyla raporlama, iki arka uç için
parite testi. Güvenlik bildirimi için [SECURITY.md](SECURITY.md).

---

## 📌 Proje Statüsü ve Bilinen Sınırlamalar

> **Mevcut Sürüm:** `v0.5.0-alpha` (Geliştirme / Araştırma Prototipi)  
> Axiom, aktif geliştirme ve araştırma aşamasında olan deneysel bir sistem programlama dilidir.

### Bilinen Sınırlamalar ve Teknik Kapsam:
1. **Çapraz Derleme ve WASM Hedefleri:** `--target wasm32-wasi` ve `--target aarch64-linux-gnu` gibi hedefler harici sysroot ve çapraz derleme toolchain'i (örn. WASI SDK, gcc-aarch64) gerektirir. Sistemde kurulu sysroot bulunmadığında derleyici açık ve yönlendirici bir hata mesajı ile güvenli şekilde durur; bu hedefler deneysel statüdedir.
2. **Dinamik Sistem Kütüphane Bağımlılıkları:** Üretilen ELF ikili dosyaları bağımsız çalıştırılabilir olmakla birlikte host sistemin `glibc`, `libssl`, `libcrypto`, `libz` ve `libpthread` kütüphanelerine dinamik olarak bağlanır (tam statik musl desteği yol haritasındadır).
3. **Self-Hosted Derleyici Durumu:** `bin/axiomc` (`compiler/main.ax`) Axiom ile yazılmış derleyicidir ve **21/21 örneği** derleyip Python sürücüsüyle aynı çıktıyı üretir (`tests/test_self_hosted.py`). Yine de alfa prototipidir: tanılama mesajları ve kapsamlı sözleşme/Z3 doğrulaması için Python bootstrap sürücüsü (`bin/axiom`) önerilir.
4. **Paket Yöneticisi (`axpm`):** `init/add/install/update/verify/tree/search/remove/build/run/test` komutlarını destekler. Yerel (`--path`) ve Git (`--git`, `--rev`) bağımlılıkları gerçekten klonlanır ve içerik tabanlı SHA-256 ile kilitlenir; `axpm verify` kurcalamayı tespit eder. **Registry v1 uygulandı:** içerik-adresli depo, ed25519 imza, semver, geçişli (transitive) çözümleme, yanked sürümler ve path-traversal koruması ([docs/REGISTRY.md](docs/REGISTRY.md)). İmzasız paketler varsayılan olarak reddedilir; `@kapsam/paket` ad alanı desteklenir.
5. **Bellek Modeli:** String'ler refcount tabanlı sahiplik tablosuyla izlenir. `let`/atama/`return` yollarında, ayrıca **`print(f(x))` ve sonucu atılan ifade deyimlerinde** iç içe üretilen geçici string'ler ifade sonunda bırakılır; `continue`/`break` de döngü gövdesine ait kapsamları temizler. `file_read`, `str_split`, `str_replace`, `str_sub`, `str_trim`, base64/hex/hash gibi üreticiler ve `array_push` sonuçları kapsam çıkışında temizlenir. `str_owned_count()` ile izlenen string sayısı ölçülebilir (C arka ucu).
6. **LLVM Arka Ucu:** 21 örnek programın tamamı `--backend=llvm` ile derlenir (ofansif `15_redteam_offensive_suite.ax` için `--features offensive` gerekir). `defer`, `?` ve **string kapsam temizliği** de LLVM'de desteklenir (döngü gövdesi, if/else dalları, erken dönüş; kaçış analizi ile struct alanı/cağrı argümanı korunur). `-g` ile LLVM IR'e DWARF metadata (`DICompileUnit`, `DISubprogram`, `DILocation`, `DILocalVariable`) üretilir; üretilen ikili `readelf --debug-dump=line` ile kaynak satırlarını, `--debug-dump=info` ile yerel değişkenleri (`DW_TAG_variable`) içerir.
7. **Ofansif Güvenlik Modülleri:** `shellcode`, `c2`, `evasion`, `memdump`, `packet_crafter` modülleri varsayılan olarak reddedilir; yalnızca `--features offensive` (veya `AXIOM_FEATURES=offensive`) ile derlenebilir.


---

## 📄 Lisans
Bu proje MIT lisansı ile korunmaktadır.
