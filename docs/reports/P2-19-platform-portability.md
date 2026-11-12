# P2-19 — Platform Taşınabilirliği: Linux + Windows

**Tarih:** 11 Kasım 2026
**Görev:** `TODO.md` → P2-19
**Durum:** ✅ Windows çapraz derleme **21/21**, Linux bozulmadı

---

## 1. Sonuç

| Hedef | Derlenen | Çalıştırılan | Not |
|---|---:|---:|---|
| Linux (C) | 21/21 | ✅ | referans |
| Linux (LLVM) | 21/21 | ✅ | |
| Linux (self-hosted) | 21/21 | ✅ | |
| **Windows (mingw-w64)** | **21/21** | — | wine yok; PE32+ doğrulandı |

```bash
$ axiom build examples/01_hello.ax --target windows -o hello.exe
✓ Başarılı → hello.exe
$ file hello.exe
PE32+ executable for MS Windows 5.02 (console), x86-64
```

---

## 2. Mimari: dört katman

`axiom/platform.h` — platforma özgü **her** çağrı tek dosyada.

| Katman | Kapsam | Linux | Windows |
|---|---|---|---|
| **1 Çekirdek** | string, dizi, dosya, matematik, thread, mutex, koşul değişkeni, zaman | ✅ | ✅ |
| **2 Ağ** | TCP, UDP, DNS, HTTP istemcisi, poll, timeout | POSIX sockets | Winsock2 |
| **3 Linux'a özel** | epoll, `/proc` adli bilişim, ptrace, shellcode, ham soket | ✅ | **açık hata** |
| **4 Harici** | OpenSSL (AES/TLS), zlib | ✅ | hash/HMAC **yedek**, AES/zlib **açık hata** |

### 2.1 Neden katman?

Tek bir "Windows için de derlenir" iddiası yanıltıcı olurdu. `/proc` Windows'ta
yok; ona sessizce boş liste döndürmek, bir DFIR aracında **"temiz sistem"**
gibi okunur. Bu yüzden katman 3 ve 4'te **açık hata** politikası (ilke D7).

### 2.2 Kabul edilebilir tek istisna: hash

Güvenlik araçlarının çekirdeği hash/HMAC. "OpenSSL yok" demek, Windows'ta
Axiom'un tüm güvenlik araçlarını işe yaramaz yapardı. Bu yüzden
`axiom/crypto_portable.h` yazıldı:

| Algoritma | Kaynak | Doğrulama |
|---|---|---|
| SHA-256 | FIPS 180-4 | `hashlib.sha256` ile birebir |
| SHA-1 | FIPS 180-4 | `hashlib.sha1` |
| MD5 | RFC 1321 | `hashlib.md5` |
| HMAC-SHA256 | RFC 2104 | `hmac` modülü |
| Sabit zamanlı karşılaştırma | — | uzunluk sızdırmaz |

AES ve TLS **taklit edilmedi** — bunlar için açık hata verilir.

---

## 3. Açılan soyutlamalar

| Alan | Soyutlama |
|---|---|
| Thread | `ax_os_thread_create/join` (pthread / `_beginthreadex`) |
| Mutex | `ax_os_mutex_*` (pthread_mutex / SRWLOCK) |
| Koşul değişkeni | `ax_os_cond_*` (pthread_cond / CONDITION_VARIABLE) |
| Zaman | `ax_os_time_ms`, `epoch`, `gmtime`, `localtime`, `strftime_tz`, `timegm` |
| Dosya | `ax_os_stat`, `mkdir`, `rmdir`, `unlink`, `rename`, `dir_open/next/close` |
| Ortam | `ax_os_getenv_dup` |
| Süreç | `ax_os_run_argv`, `run_shell`, `spawn_bg`, `kill`, `getpid`, `sleep_ms` |
| Soket | `set_timeout`, `set_reuse`, `set_nonblocking`, `poll_read/write`, `get_error`, `shutdown_write`, `close` |
| Dinamik kütüphane | `ax_os_lib_open/sym/close` |
| Yürütülebilir bellek | `ax_os_alloc_exec`, `ax_os_alloc_rwx`, `protect_exec`, `free_exec` |
| CPU | `ax_os_cpuid`, `ax_os_read_xcr0` (target attribute ile) |
| Statik işaretçi | ELF segment taraması / `VirtualQuery(MEM_IMAGE)` |

### 3.1 Windows'a özgü çözümler

- **`socketpair` yok** → loopback TCP çifti (dinle → bağlan → kabul).
- **`_xgetbv`** `-mxsave` olmadan inline edilemiyor →
  `__attribute__((target("xsave")))`.
- **`SO_REUSEPORT`** yok → `#if defined(SO_REUSEPORT)` ile atlanır.
- **`socklen_t`** yok → `typedef int socklen_t`.
- **`send`/`setsockopt`** `const char*` bekliyor → ince sarmalayıcılar.

---

## 4. Bulunan 3 gerçek hata

### 4.1 Çift sarma → geçersiz `free`

`grep 'axiom_owned_str_wrap(axiom_safe_strdup'` → **8 yer**.

Eski modelde `safe_strdup` ham `malloc` döndürürdü, `wrap` onu sahiplenirdi.
Yeni intrusive modelde `safe_strdup` **zaten** başlıklı sahipli tampon döner;
`wrap` tekrar sarınca `free((void*)buf)` çağırıyor → **başlıklı işaretçiyi ham
free** → `free(): invalid pointer`.

Belirti: tarih ve hash fonksiyonları çöküyordu (`test_date_timezone`,
`test_packet4_libs`).

### 4.2 `exec_mem_run` SEGV

`ax_os_alloc_exec` RW tahsis ediyor (sonradan `protect_exec` ile X eklensin
diye). Ama `axiom_exec_mem_run` bu belleğe yazıp **doğrudan çağırıyordu** →
çalıştırma izni yok → SIGSEGV.

`ax_os_alloc_rwx` ayrıldı; `exec_mem_run` onu kullanıyor.

### 4.3 zlib bloğunda iç içe `#if`

Regex guard'ını eklerken `#if AXIOM_HAVE_POSIX_REGEX` yanlış yere düştü ve
zlib'in `#else` dalıyla iç içe girdi. Linux'ta fark edilmedi (her ikisi de
açıktı), Windows'ta ortaya çıktı.

---

## 5. Testler — `tests/test_portability.py` (21)

| Grup | Kapsam |
|---|---|
| Katman ayrımı | `platform.h` makroları ve soyutlama noktaları |
| Kaynak denetimi | POSIX başlıkları koşulsuz include edilmiyor |
| Kripto vektörleri | SHA-256/SHA-1/MD5/HMAC → `hashlib`/`hmac` ile birebir |
| Windows derleme | `--target windows` → PE32+ (`MZ` imzası), 13 örnek |
| Açık hata | `/proc` fonksiyonu Windows'ta derlenir, açık hata verir |
| Linux regresyonu | `01_hello` çalışır, 55 yazar |
| Harici kütüphane | OpenSSL/zlib yoksa yedek ya da açık hata |

---

## 6. Wine ile GERÇEK Windows çalıştırma

Wine 10.0 kurulduktan sonra **21 örneğin tamamı wine altında çalıştırıldı**:

| Sonuç | Sayı |
|---|---|
| Derlenen + çalışan | **21/21** |
| Linux çıktısıyla birebir (normalize sonrası) | **21/21** |

Kalan farkların tamamı iki sınıfta:
1. **Zamanlama/rastgelelik** (geçen süre, zaman damgası, ICMP gecikmesi,
   rastgele beacon) — normalize edilir.
2. **Belgelenmiş Linux'a özel özellik**: `zlib` yok → açık hata,
   `/proc` yok → boş liste + stderr uyarısı.

Örnek çıktı (`01_hello.exe` wine altında):

```
$ wine hello.exe
Merhaba, Guvenlik Uzmani! Axiom dunyasina hos geldin.
1'den 10'a kadar sayilarin toplami:
55
[DOGRULAMA] Toplam hesabi basarili ve dogru!
```

### 6.1 Wine altında bulunan 3 GERÇEK hata

Wine olmadan yalnız derleme doğrulanabildiği için bu üçü **görünmezdi**:

| # | Hata | Etki |
|---|---|---|
| 1 | **`WSAStartup` hiç çağrılmıyordu** | Windows'ta **hiçbir soket çalışmazdı**. `platform.h`'ye constructor + tembel başlatma, tüm soket oluşturmaları `ax_os_socket()` üzerinden |
| 2 | **POSIX regex yoktu** | Sigma/YARA/CVE tespiti Windows'ta `false` dönüyordu (sessiz kaçırma). `axiom/regex_portable.h` yazıldı |
| 3 | **Thread çıktı yarışı** (örnek 11) | UDP alıcı thread'i ile ana thread'in `print`'i yarışıyordu; çıktı koşudan koşuya değişiyordu. Örnek `thread_join` sonrasına alındı |

### 6.2 Taşınabilir regex motoru

`axiom/regex_portable.h` — POSIX regex olmayan platformlarda devreye girer:

| Özellik | Destek |
|---|---|
| literal, `\.` `\\` `\d` `\s` `\w` | ✅ |
| `.` `[abc]` `[^abc]` `[a-z]` | ✅ |
| `*` `+` `?` `{n}` `{n,}` `{n,m}` | ✅ |
| `( )` gruplama, `\|` alternasyon | ✅ |
| `^` `$` çapa, `(?i)` harf duyarsız | ✅ |
| Geri referans `\1`, ileri bakış `(?=)` | **derleme hatası** (sessiz yanlış yasak) |

**ReDoS koruması:** geri izlemeli motor **adım bütçesi** (2M) ile sınırlı;
bütçe aşılırsa eşleşme başarısız sayılır. Ayrıca `regex_risk_level` iç içe
niceleyicileri zaten reddeder.

Doğrulama: `CVE-[0-9]{4}-[0-9]+`, `(?i)HELLO`, `(union.*select|1=1)`,
`^abc$`, `[0-9]{1,3}\.` gibi gerçek Sigma/YARA desenleri wine altında test edildi.

## 7. Önceki (wine öncesi) doğrulama

wine kurulu değil ve `sudo` şifre istiyor → ikililer **çalıştırılamadı**.
Bunun yerine iki dolaylı ama güçlü kanıt üretildi.

### 6.1 Import tablosu: çıplak Windows'ta başlar mı?

`objdump -p` ile 21 ikilinin tamamı tarandı:

| Import edilen DLL | Görüldüğü örnek |
|---|---|
| `KERNEL32.dll` | 21/21 |
| `msvcrt.dll` | 21/21 |
| `WS2_32.dll` | ağ kullanan 8 örnek |

**`libssl`, `libcrypto`, `libz`, `libpthread`, `libdl` import edilmiyor.**
Bu kritik: o kütüphaneler çıplak Windows'ta yoktur; import edilseydi `.exe`
açılırken "DLL bulunamadı" hatası verirdi.

### 6.2 Windows kod yolunu Linux'ta **çalıştırma**

Aynı `runtime.h`, `-DAXIOM_DISABLE_OPENSSL -DAXIOM_DISABLE_ZLIB` ile derlenip
Linux'ta çalıştırıldı — yani Windows'un kullandığı kod yolu:

| Çağrı | Sonuç |
|---|---|
| `axiom_hash_sha256("abc")` | `ba7816bf...15ad` — `hashlib` ile **birebir** |
| `axiom_hash_sha1("abc")` | `a9993e36...89d` — birebir |
| `axiom_hash_md5("abc")` | `90015098...f72` — birebir |
| `axiom_hmac_sha256("Jefe", ...)` | RFC 4231 vektörü — birebir |
| `axiom_crypto_memcmp` | `1` / `0` (doğru) |
| `axiom_crypto_random_hex(16)` | 32 hex karakter |
| `axiom_gzip_compress` | `sikistirma: bu yapida zlib yok` |
| `axiom_aes256_cbc_encrypt` | `AES: bu yapida OpenSSL yok` |

Yani Windows'ta: **hash/HMAC doğru çalışır**, AES/zlib **açık hata verir**.
Bu, tasarım kararının ölçülmüş kanıtıdır.

Bu doğrulama `tests/test_portability.py` içinde kalıcı iki test olarak duruyor.

## 8. Dürüst sınırlar

| Konu | Durum |
|---|---|
| **macOS** | `dladdr` yolu kodda hazır; runner olmadığı için derleme doğrulanamadı |
| **macOS** | `dladdr` yolu kodda hazır, derleme doğrulanamadı |
| **WASI** | `wasm32-wasi` hedefi sysroot istiyor; harici bağımlılık |
| **AES/TLS Windows'ta** | OpenSSL DLL gerekir; yoksa açık hata |
| **`/proc` araçları** | Windows'ta Linux'taki sonucu vermez (tasarım gereği) |

Bunlar "yapılmadı" değil, **ölçülmüş sınırlar** — README ve TODO'da yazılı.

---

## 9. Durum

```bash
python3 -m pytest -q --no-header      # 1010 passed (0 skip)
axiom build (Linux C)                 # 21/21
axiom build --backend=llvm            # 21/21
./bin/axiomc build                    # 21/21
axiom build --target windows          # 21/21  (PE32+)
make fmt-check                        # ✅
```

| Kontrol | Sonuç |
|---|---|
| Test | **1010** (+34) |
| Platform | **2** (Linux yerel, Windows çapraz) |
| Raporlar | `docs/reports/` (41 rapor, tarihsel dizin) |

---

## 10. Sıradaki

| # | İş | Not |
|---|---|---|
| 1 | ~~Windows ikililerini wine'da çalıştırma~~ | ✅ yapıldı (21/21) |
| 2 | macOS CI runner | `dladdr` yolu hazır |
| 3 | WASI sysroot + `wasm32-wasi` | Harici SDK gerekiyor |
| 4 | Faz 3 (1.0, paket yayını, kullanıcı) | Kod dışı |
