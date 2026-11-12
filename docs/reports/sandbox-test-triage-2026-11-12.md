# Sandbox Test Raporu — Sınıflandırma ve Düzeltmeler

**Tarih:** 12 Kasım 2026
**Kaynak:** Kullanıcının kısıtlı sandbox koşusu (951 passed / 57 failed / 2 errors)
**Durum:** ✅ Her madde ele alındı; ürün hatası olmayanların **hiçbiri skip ile gizlenmedi**, gerekçeleri açıkça raporlanıyor.

---

## 0. Sonsuz döngü olayı (12 Kasım, ayrıca)

### Belirti

`/tmp` altında üç test ikilisi **2 gün boyunca %97,8 CPU** ile döndü:

```
PID 2911614  %97.8  2-00:52:37  /tmp/tmp75ctni4l.bin
PID 2961465  %97.8  2-00:05:43  /tmp/tmpj1xov8ba.bin
PID 3071189  %97.7  1-22:24:21  /tmp/tmptb_xejyw.bin
```

Üçü de `std/io/file` testlerinden üretilmişti (P2-08 + P2-17b günü: 10 Kasım).

### Kök neden (ÜRÜN HATASI)

```axiom
fn lines_of(p: str) -> Result<int, str> {
    let l = read_lines(p)?        // <-- burada
    return result_ok<int>(len(l))
}
```

`?` operatörü hata yolunda `_capture_cleanup()` üretir. Bu temizlik **henüz
atanmamış** `l` değişkenini de serbest bırakıyordu:

```c
ax_array_str l = ({ ... if (!_ok) { axiom_array_str_free(&l); ... } ... });
```

`l` başlatılmadığı için `.length` alanı **çöp değer**. Dizi serbest bırakma
döngüsü bu çöp uzunluk kadar döner:

```c
for (ax_int i = 0; i < arr->length; i++) ...   // çöp length = milyonlar
```

Küçük çöp değer → sessiz geçiş; büyük çöp değer → pratikte sonsuz döngü.
Bu yüzden hata **aralıklı** görünüyordu ve tek koşuda yakalanamıyordu.

### Düzeltme

`pending_init` koruması daha önce yalnız *string* kapsamlarına uygulanmıştı.
**Dizi kapsamlarına da** uygulandı — üç noktada:

| Fonksiyon | Ne yapar |
|---|---|
| `_emit_all_owned_releases` | `?` hata yolu temizliği |
| `_capture_loop_cleanup` | `break` / `continue` temizliği |
| `generate_block_contents` | kapsam sonu temizliği |

### Testin kırmızı olduğu kanıtlandı

Düzeltme geçici kaldırıldığında:

```
FAILED test_generated_c_does_not_free_variable_in_its_own_initializer
  'axiom_array_str_free(&l)' is contained here:
    is_ok)) { axiom_array_str_free(&l);
```

Geri konunca 5/5 yeşil.

> Not: aynı geri alma sırasında **çalışma anı** testi (300 kez hata yolu)
> geçti — çünkü çöp uzunluk o koşuda küçük çıktı. Bu tam olarak hatanın
> neden aralıklı olduğunu kanıtlıyor ve neden C düzeyi bir iddia gerektiğini
> gösteriyor.

### Regresyon testi

`tests/test_uninit_array_release.py` — 5 test:
1. Üretilen C'de `X = ({ ... free(&X) ... })` deseni **yok**
2. 300 kez hata yolu 60 s içinde biter (`errors: 300`)
3. Aynı davranış **C ve LLVM** arka uçlarında
4. Zaman aşımı altyapısı çalışıyor

### İkinci kök neden: kaçak neden 2 gün yaşadı?

Testlerin **168** `subprocess.run(...)` çağrısında `timeout` yoktu. Takılan
ikili hiç durdurulmadı.

**Düzeltme:** `conftest.py` — `subprocess.run` merkezî olarak sarılır, açık
`timeout` verilmemişse varsayılan 900 s uygulanır (`AXIOM_TEST_TIMEOUT` ile
ayarlanır). Açık timeout veren çağrılar etkilenmez.

Ek olarak wine prefix sızıntısı kapatıldı:
- Oturum başına **tek** prefix (önce her çağrıda ~600 MB oluşuyordu)
- `conftest.pytest_sessionfinish` ile oturum sonunda silme
  (hook bir test modülünde tanımlıydı, pytest onu **yok sayıyordu** — taşındı)
- Oturum başında 1 saatten eski bayat prefix'leri temizleme

Kanıt: tam paket sonrası `/tmp` %32 → temizlik sonrası %16,
`/tmp/axiom-wine-*` kalıntısı **0**, yüksek CPU'lu süreç **0**.

### Doğrulama

| Koşu | Sonuç |
|---|---|
| Tam paket (düzeltme sonrası) | `1017 passed` (15:31) |
| Tekrarlı parite (`11`, `22`) | kararlı |
| `/tmp` kullanımı | 606 MB / 3.9 GB |
| Kaçak süreç | yok |


---

## 1. Özet

Senin koşun: `951 passed, 57 failed, 2 errors`
Benim ortamım (yazılabilir `$HOME`, çalışan wine, ağ):
`1017 passed, 0 failed, 0 skipped` — tam paket, 15:31.

Sonra **senin kısıtlarını taklit ettim** (ağsız namespace):
`961 passed, 51 skipped, 0 failed` — 14:01.

Anahtar nokta: **kısıtlı ortamda artık "failed" yok, "skipped + açık gerekçe" var.**
Hiçbir test sessizce yeşil sayılmıyor.

---

## 2. Madde madde

### 2.1 DFIR parite testi deterministik değildi ✅ düzeltildi

**Senin bulgun doğruydu.** Testi 6 kez üst üste koşturduğumda geçti, ama
kırılganlığı kanıtlanabilir: normalizer yalnız `"count"` alanını etkisizleştiriyordu,
**süreç adlarını değil**. Python sürücüsünün ikilisi ile self-hosted ikilinin
kendi süreç adları (`python3` vs `axiomc`) ilk 50'ye girdiğinde çıktı ayrışır.

**Düzeltme:** `tests/test_selfhosted_parity.py` içine JSON-farkında normalizasyon:

```python
def _normalize_dfir_json(text):
    d = json.loads(text)          # yalnız tool == "axiom-dfir-triage" için
    d["processes"] = {"count": "N", "top": "<live process inventory>"}
    d["network"]["listening"] = "<live listening sockets>"
    d["timestamp_ms"] = "N"
    # integrity / log / detections / risk DOKUNULMAZ
```

**Senin uyarını ciddiye aldım:** "tüm DFIR çıktısını karşılaştırma dışı bırakma."
Bunu engelleyen iki test eklendi:

| Test | Ne kanıtlar |
|---|---|
| `test_dfir_normalization_ignores_live_process_inventory` | Farklı PID/isim/port → normalize sonuç **aynı** |
| `test_dfir_normalization_keeps_integrity_detections_and_risk` | Hash / tespit / risk / log kaynağı farkı **hâlâ yakalanıyor** |

Yani normalizasyon dar tutuldu; gerçek regresyonlar görünür kalıyor.

### 2.2 YARA fuzz testleri ✅ ortam hatasıydı, burada geçiyor

`tests/test_fuzzing_suite.py` → **8 passed** burada. ASan ortamında ayrıca
koşturulabilir; benim ortamımda ASan/LSan gerçekten çalışıyor (aşağıda kanıt).

### 2.3 ICMP loopback ✅ ortam-farkında yapıldı

Senin ortamında `UNREACHABLE` dönüyordu; benim ortamımda geçiyor. Test artık
**ürünün kendi kodunu** kullanarak ön koşulu ölçüyor:

```
network_probe → loopback çalışıyor mu?
     ↓ evet
axiom_icmp_ping("127.0.0.1") gerçekten ulaşıyor mu?   # ürün kodu
     ↓ evet
test koşar
```

İlk denemem yalnız `SOCK_RAW` açılışına bakıyordu — **yanlıştı**, çünkü ürün önce
yetkisiz ICMP (`SOCK_DGRAM`) deniyor. İkinci denemem yalnız soket açılışına
bakıyordu — `lo` kapalıyken de "var" diyordu, o da yanlıştı. Üçüncü (mevcut)
sürüm gerçek paket gidiş-dönüşünü ölçüyor.

Kısıt varsa sonuç: `SKIPPED ... Ham soket kullanılamıyor: loopback yok, ICMP de olamaz: [Errno 101] Network is unreachable`

### 2.4 Wine testleri ✅ **iki gerçek hata** bulundu ve düzeltildi

Bu madde en değerlisiydi: "wine başlayamadığı için değerlendirilemedi" demiştin.
Benim ortamımda wine çalışıyor ve testler **açık verdi**.

**Hata A — Wine prefix sızıntısı (benim yazdığım test altyapısı):**
`_wine_run` her çağrıda yeni `WINEPREFIX` oluşturup silmiyordu. 34 test × ~600 MB
→ `/tmp` doldu ve **tüm çeviri derlemeleri** "No space left on device" ile düştü.
Bu, ürün değil test altyapısı hatasıydı ama tam paketi kırıyordu.
Düzeltme: oturum başına **tek** prefix + `pytest_sessionfinish` ile temizlik.

**Hata B — `WSAStartup` hiç çağrılmıyordu (GERÇEK ÜRÜN HATASI):**
Windows'ta `WSAStartup` olmadan **hiçbir soket çalışmaz**. Derleme geçiyordu,
çalışma anında ağ tamamen ölüydü. Yalnız-derleme doğrulamasıyla görünmezdi.
Düzeltme: `platform.h`'ye `__attribute__((constructor))` + tembel başlatma;
tüm soket oluşturmaları `ax_os_socket()` üzerinden.

**Hata C — Regex Windows'ta tamamen devre dışıydı (GERÇEK ÜRÜN HATASI):**
POSIX regex yok → tüm regex çağrıları `false` dönüyordu. Sigma/YARA/CVE tespiti
**sessizce kaçırıyordu** (güvenlikte en tehlikeli hata sınıfı).
Düzeltme: `axiom/regex_portable.h` — geri izlemeli ama **adım bütçeli** (ReDoS
kapalı); `\1` geri referans ve `(?=)` **açık derleme hatası** veriyor.

**Hata D — Örnek 11'de thread çıktı yarışı:**
UDP alıcı thread'i ile ana thread'in `print`'i yarışıyordu; çıktı koşudan koşuya
değişiyordu. `thread_join` sonrasına alındı → 5/5 koşu birebir aynı.

**Wine stderr artık hata mesajında** (senin 4. maddendeki istek):

```
Wine kullanılamıyor: Wine başlatılamadı (çıkış 1) — wine: chdir to .../pfx : No such file or directory
```

`_wine_run` artık `(rc, stdout, stderr)` döndürüyor; `_wine_fail()` son 25 satırı
stdout ve stderr'den assertion mesajına ekliyor.

### 2.5 Regex ve ağ Wine testleri ✅ gerçekten koşturuldu

`test_windows_regex_engine_works` ve `test_windows_networking_works_under_wine`
benim ortamımda **geçti** (skip değil). Doğrulanan çıktı:

```
cve: true
digits: 123
icase: true
alt: true
anchor_bad: false
replace: a#b#c
nested_rejected: 2
bad_pattern: true
```

Ağ testi: `closed_port_fd_negative: true`, `socket_layer_alive: true` — yani
`WSAStartup` düzeltmesi gerçekten çalışıyor.

> Senin ortamında bu testler skip olurlar ve raporda **"skipped"** görünür —
> "passed" olarak sayılmaz.

### 2.6 Registry önbelleği ✅ izole edildi ve kanıtlandı

Testler artık `AXIOM_CACHE_DIR` ile her testin kendi `tmp_path`'ine yazıyor
(`tests/test_registry.py::_isolated_env`). Ayrıca kullanıcı ortam değişkenleri
(`AXIOM_REGISTRY`, `AXIOM_REGISTRY_KEY`, `AXIOM_ALLOW_UNSIGNED`) temizleniyor.

**Kanıt:** salt-okunur `HOME` ile:

```bash
$ HOME=/tmp/ro-home  # chmod 555
$ python3 -m pytest -q tests/test_registry.py
43 passed in 1.50s
```

İmza doğrulama, kurcalanmış tarball reddi, cache onarımı ve path-traversal
testleri bu koşuda gerçekten çalıştı (atlanmadı).

### 2.7 ASan/LSan ✅ ortam denetimi eklendi + burada gerçekten koşuyor

`tests/support_env.py::asan_probe()` bilinen **temiz** bir programı ASan ile
derleyip çalıştırıyor. `LeakSanitizer does not work under ptrace` görürse
ortam kısıtlı demektir ve testler açık gerekçeyle skip olur.

Benim ortamımda probe `(True, '')` döndü ve ASan testleri **PASSED** (skip değil):

```
test_str_replace_loop_has_no_leak_under_asan              PASSED
test_file_read_loop_has_no_leak_under_asan                PASSED
test_str_split_loop_has_no_leak_under_asan                PASSED
test_array_push_loop_has_no_leak_under_asan               PASSED
test_str_sub_and_trim_loop_has_no_leak_under_asan         PASSED
```

Yani "free(): invalid size", tarih/saat ve Packet 4 self-hosted sorunlarının
gerçekten kapandığı **bu ortamda** doğrulandı.

### 2.8 Ağ testleri ✅ 36 test geçide bağlandı

`require_network` modül düzeyinde uygulandı:

| Dosya | Test sayısı |
|---|---|
| `tests/test_packet2_libs.py` | 28 |
| `tests/test_async_epoll.py` | 6 |
| `tests/test_http_client.py` | 1 |
| `tests/test_stdlib.py::test_http_get_with_live_mock_server` | 1 |

Ağ yoksa: `SKIPPED ... Ağ kullanılamıyor: loopback soketi çalışmıyor: [Errno 101] Network is unreachable`

Ağ gerektiren self-hosted örnekleri (`11_packet2_advanced_network.ax`) de
geçide bağlandı (2 test).

---

## 3. Sınıflandırma — senin 7. madden

| Kategori | Testler | Kanıt |
|---|---|---|
| **Gerçek ürün hatası (düzeltildi)** | `WSAStartup` yokluğu, regex yokluğu, örnek 11 thread yarışı | wine altında 21/21 çalışıyor |
| **Test altyapısı hatası (düzeltildi)** | Wine prefix sızıntısı (`/tmp` dolması) | 34/34 geçti, `/tmp` boş |
| **Test tasarımı (düzeltildi)** | DFIR canlı envanter normalizasyonu | 2 koruma testi |
| **Ortam kısıtı → açık skip** | Ağ 36, ICMP 1, ASan 5, Wine 11 | gerekçeler `-rs` çıktısında |

Hiçbiri "sessizce skip edilip başarılı sayıldı" kategorisinde değil.

---

## 4. Ölçülmüş sonuçlar

| Ortam | Sonuç | Süre |
|---|---|---|
| **Benim (tam)** | `1012 passed, 0 failed, 0 skipped` | 18:19 |
| **Ağsız namespace (sandbox taklidi)** | `961 passed, 51 skipped, 0 failed` | 14:01 |
| Salt-okunur `HOME` (registry) | `43 passed` | 1.50 s |
| Wine prefix salt-okunur | `17 passed, 11 skipped` (açık gerekçe) | 55 s |

### Ağsız ortamdaki 51 skip'in dağılımı

Ağ (packet2 28 + epoll 6 + http_client 1 + stdlib 1 + selfhosted 2) ≈ 38,
ICMP 1, Wine 11, diğer ortam denetimleri 1.

> Her skip `-rs` ile görülebilir; hiçbiri gerekçesiz değil.

---

## 5. Değişen dosyalar

| Dosya | Değişiklik |
|---|---|
| `axiom/platform.h` | `WSAStartup` constructor + tembel başlatma, `ax_os_socket()` |
| `axiom/regex_portable.h` | **yeni** — taşınabilir regex motoru |
| `tests/support_env.py` | **yeni** — `require_asan/network/wine/raw_socket` probları |
| `tests/test_selfhosted_parity.py` | DFIR JSON normalizasyonu + 2 koruma testi |
| `tests/test_portability.py` | tek wine prefix + temizlik; stderr hata mesajında |
| `tests/test_packet2_libs.py`, `test_async_epoll.py`, `test_http_client.py`, `test_stdlib.py`, `test_packet5_libs.py` | ağ/ICMP geçitleri |
| `tests/test_registry.py` | `_isolated_env` (izole cache) |
| `tests/test_memory_leak_deep.py`, `test_memory_sanitizer.py` | `@require_asan` |
| `examples/11_packet2_advanced_network.ax` | deterministik çıktı sırası |

---

## 6. Dürüst sınırlar

- **Senin sandbox'ında hâlâ göremeyeceğim şeyler var:** oradaki 57 hatanın
  tamamını tek tek göremedim; yalnız senin verdiğin 7 maddeyi ele aldım.
- **macOS** derleme doğrulaması yok (runner yok).
- **WASI** harici sysroot istiyor.
- Skip'ler ortam kısıtıdır; **CI'da ağ + wine + yazılabilir HOME olduğunda
  bunlar koşmalı**. Bu raporun 4. bölümündeki "benim ortamım" satırı o kanıttır.

---

## 7. Sıradaki

| # | İş |
|---|---|
| 1 | CI matrisine ağ + wine + yazılabilir `HOME` ekle (skip'ler orada kapanır) |
| 2 | macOS runner |
| 3 | WASI SDK ile `wasm32-wasi` |
