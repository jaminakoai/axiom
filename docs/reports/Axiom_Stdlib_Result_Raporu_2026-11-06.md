# Axiom (λx) — Stdlib `Result` Katmanı Raporu

**Tarih:** 6 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Kapsam:** `~/Desktop/axiom`
**Önceki rapor:** `Axiom_Hata_Modeli_Raporu_2026-11-06.md`

---

## 0. Özet

Önceki turda `Result` + `?` **altyapısı** hazırdı ama stdlib hâlâ `""` / `-1` / `false` dönüyordu — yani kullanıcı yeni modeli ancak kendi fonksiyonlarında kullanabiliyordu. Bu turda model **stdlib'e taşındı**.

| İş | Durum |
|---|---|
| `std/io/file` — `read_file`, `write_file`, `append_file`, `read_lines` | ✅ Yeni modül |
| `std/encoding/json` — `json_get_{str,int,bool}_result` | ✅ |
| `std/net/http` — `http_get_result`, `http_status`, `http_body` | ✅ |
| `std/crypto/tls` — `https_get_result` | ✅ |
| `std/os/process` — `exec_output_result` | ✅ |
| `main -> Result<int, str>` giriş noktası | ✅ Yeni |
| `result_err_with<T>` + tipli kurucular | ✅ |
| **3 codegen/checker hatası** | ✅ Düzeltildi |
| `examples/20_stdlib_result.ax` | ✅ |
| 13 yeni test | ✅ |

**Test durumu:** `602 passed` (önceki 589; +13).

---

## 1. Tasarım kararı: sözleşme vs veri hatası

`Result` API'sinin tüm amacı "veri hatasında program durmasın". Bu yüzden net bir kural koydum ve dokümante ettim:

| Katman | Örnek | Hata davranışı |
|---|---|---|
| **Sessiz (eski)** | `file_read`, `json_get_str`, `http_get` | `""` / `-1` / `false` — neden bilinmez |
| **Result (yeni)** | `read_file`, `json_get_str_result`, `http_get_result` | `Err("anlamlı mesaj")` — **asla abort etmez** |
| **Sözleşmeli** | `requires`/`ensures`/`verify` | Program durur (exit 101) — *programlama hatası* |

> **Kural:** `Result` döndüren fonksiyonlar `requires` ile abort etmez. Boş yol, eksik anahtar, geçersiz port → hepsi `Err`.
> Sözleşmeler yalnızca "bu asla olmamalı" durumları içindir.

Bu yüzden `http_get_result` içinde port aralığı `requires` değil, `Err("gecersiz port: 99999")` olarak ele alınıyor — eski `http_get` ise sözleşme ihlaliyle çöküyordu. Fark testle gösterildi.

---

## 2. Yeni API

### `std/io/file`

```axiom
import "std/core/error"
import "std/io/file"

fn yukle(yol: str) -> Result<str, str> {
    let icerik = read_file(yol)?
    return result_ok<str>(icerik)
}
```

| Fonksiyon | Dönüş | Hata mesajı örneği |
|---|---|---|
| `read_file(path)` | `Result<str, str>` | `dosya bulunamadi: /x.json` |
| `write_file(path, content)` | `Result<bool, str>` | `dosya yazilamadi: /x.json` |
| `append_file(path, content)` | `Result<bool, str>` | (yukarıdaki) |
| `read_lines(path)` | `Result<str[], str>` | `?` ile `read_file`'dan taşınır |
| `file_present(path)` | `bool` | — |

**Bilinen sınır (dokümante):** boş dosya ile okuma hatası ayırt edilemez (yerleşik `file_read` ikisinde de `""` döner). Boş dosya meşru sonuç kabul edilir.

### `std/encoding/json`

```axiom
let name = json_get_str_result(raw, "name")?
let port = json_get_int_result(raw, "port")?
let dbg  = json_get_bool_result(raw, "debug")?
```

Mesajlar: `bos json`, `bos anahtar`, `anahtar bulunamadi: <key>`.

### `std/net/http`

```axiom
let resp = http_get_result(host, port, "/")?
let status = http_status(resp)?      // 200, 404, ...
let body = http_body(resp)?
```

Hata ayrımı: `bos host` · `gecersiz port: <p>` · `baglanti kurulamadi: <h>:<p>` · `istek gonderilemedi: <h>` · `bos yanit: <h>`.

### `std/crypto/tls`, `std/os/process`

- `https_get_result(host, port, path) -> Result<str, str>`
- `exec_output_result(cmd) -> Result<str, str>`

### `main -> Result<int, str>`

Artık `main` de `Result` dönebilir; `?` doğrudan kullanılabilir:

```axiom
fn main() -> Result<int, str> {
    let cfg = load_config("app.json")?
    print(cfg.name)
    return result_ok<int>(0)
}
```

| Durum | Davranış |
|---|---|
| `Ok` | exit **0** |
| `Err(msg)` | `[AXIOM HATA] msg` → stderr, exit **1** |

Özel çıkış kodu gerekiyorsa `main() -> int` kullanılır.

---

## 3. Yol boyunca bulunan 3 gerçek hata

### 3.1 Generic argümanda dizi → geçersiz C tanımlayıcısı

```text
ax_array_Result_str[]_str_clone(...)   // C hatası
```

`Result<str[], str>` mangle edilirken tip argümanı `str[]` **olduğu gibi** birleştiriliyordu.

**Düzeltme:** `mangle_type_arg()` — dizi ekini `_array`'ye çevirir:

```python
'str[]' -> 'str_array'   =>  Result_str_array_str
```

`mangle_type_name` (tip ifadesi için) doğruydu; sorun yalnızca **ad** üretimindeydi.

### 3.2 Struct tanım sırası — C'de tam tip gerekli

`Result<Config, str>` struct'ı `Config`'den önce tanımlanınca:

```text
error: field has incomplete type 'ax_Config'
```

Forward `typedef` yetmiyor; C alan için **tam tanım** ister.

**Düzeltme:** `_order_structs()` topolojik sıralama — bir struct, alanı olarak kullandığı struct'lardan sonra tanımlanır (döngü güvenli).

Bu, yalnızca `Result<Config,...>` için değil, **her iç içe struct** için geçerliydi; muhtemelen daha önce kimse denememişti.

### 3.3 `?` erken dönüşünde yanlış `value` tipi

`Result<str[], str>` döndüren fonksiyonda `?` ile `Result<str, str>` açılırken, hata dalı **kaynağın** değer tipini (`str`) kullanıyordu:

```c
return ((ax_Result_str_array_str){ .is_ok=false, .value = "", ... });  // ✗
```

**Düzeltme:** checker `try_target_value_type` alanını da kaydediyor; codegen hedefin tipini kullanıyor, ve struct/dizi tipleri için evrensel sıfır başlatıcı `(t){0}` üretiyor.

---

## 4. Doğrulama

### Uçtan uca örnek

```bash
$ axiom run examples/20_stdlib_result.ax
[1] yapilandirma yazildi
[2] yuklendi: axiom-demo 8080
[3] beklenen hata: dosya bulunamadi: /tmp/axiom_olmayan_yapilandirma.json
[4] satir sayisi: 1
[5] eksik anahtar: anahtar bulunamadi: yok
```

### Testler (`tests/test_stdlib_result.py`, 13 test)

| Test | Ne doğrular |
|---|---|
| `test_file_result_read_write_roundtrip` | yaz → oku → içerik |
| `test_file_result_missing_file_returns_err_not_abort` | **Err döner, exit 0** (kritik) |
| `test_file_result_empty_path_is_err` | boş yol abort etmez |
| `test_file_result_append_and_lines` | `?` zinciri, `str[]` dönüşü |
| `test_json_result_success_and_missing_key` | Ok/Err ayrımı, boş json |
| `test_http_result_rejects_bad_port_without_abort` | **sözleşme yerine Err** |
| `test_http_status_and_body_parsing` | HTTP ayrıştırma |
| `test_https_result_rejects_bad_port` | TLS katmanı |
| `test_exec_output_result_handles_empty_command` | süreç katmanı |
| `test_result_err_with_custom_struct_type` | kullanıcı struct'ı `Result` içinde |
| `test_result_stdlib_example_runs_clean_under_asan` | sıfır sızıntı |
| `test_main_returning_result_maps_err_to_exit_1` | giriş noktası Err |
| `test_main_returning_result_maps_ok_to_exit_0` | giriş noktası Ok |

### Tam paket

```bash
$ python3 -m pytest -q --no-header
602 passed in 341.28s (0:05:41)
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **602** (+13) |
| LLVM örnekleri | 17/17 (`?` kullanan 2 örnek hariç, açık hata) |
| `bin/axiomc` bootstrap | ✅ |
| `make fmt-check` | ✅ |

---

## 5. Değiştirilen / Eklenen Dosyalar

| Dosya | Değişiklik |
|---|---|
| `std/io/file.ax` | **Yeni** — Result tabanlı dosya G/Ç |
| `std/core/error.ax` | `result_err_with<T>` + `result_err_int/str/bool/strs` |
| `std/encoding/json.ax` | `json_get_*_result`, `_json_precheck` |
| `std/net/http.ax` | `http_get_result`, `http_status`, `http_body` |
| `std/crypto/tls.ax` | `https_get_result` |
| `std/os/process.ax` | `exec_output_result` |
| `axiom/checker.py` | `mangle_type_arg`, `try_target_value_type` |
| `axiom/codegen_c.py` | `main -> Result` köprüsü, `_order_structs`, `_result_shape_of`, dizi/struct sıfır başlatıcı |
| `examples/20_stdlib_result.ax` | **Yeni** |
| `tests/test_stdlib_result.py` | **Yeni** — 13 test |
| `README.md`, `CHANGELOG.md`, `.github/workflows/ci.yml` | Senkron |

---

## 6. "Python gibi olmaya" katkısı

| Boyut | Önce | Sonra |
|---|---|---|
| Hata modeli | ✅ `Result` + `?` (yalnız kullanıcı kodu) | ✅ **stdlib dahil** |
| Günlük kullanım ergonomisi | Orta | **Orta-yüksek** |
| Stdlib pratikliği | ~%10–15 | ~%25 (I/O, JSON, HTTP artık güvenli) |

Artık şu gerçekçi:

```axiom
fn main() -> Result<int, str> {
    let raw = read_file("config.json")?
    let port = json_get_int_result(raw, "port")?
    let resp = http_get_result("127.0.0.1", port, "/health")?
    if http_status(resp)? != 200 {
        return result_err_int("saglik kontrolu basarisiz")
    }
    print("OK")
    return result_ok<int>(0)
}
```

Bu, önceki turlarda **mümkün değildi**.

---

## 7. Sıradaki İşler

| # | İş | Gerekçe |
|---|---|---|
| 1 | `?` için LLVM desteği | İki arka uç eşitliği; 2 örnek şu an C'ye mahkûm |
| 2 | Intrusive header + `String`/`str` | Kalan sızıntı sınıfı + string performansı |
| 3 | Gerçek JSON parser (iç içe nesne/dizi, kaçışlar) | Bugün anahtar arama; `Result` katmanı hazır ama parser sığ |
| 4 | HTTP/1.1: chunked, Content-Length, yönlendirme | `http_body` ham; gerçek istemci değil |
| 5 | Tutorial + SPEC v0.5 | Öğrenme eşiği |
| 6 | Registry politikası | Paket ekosistemi |

**Öneri:** 1 ve 2 birlikte. `?` LLVM'de olmadan LLVM arka ucu ikinci sınıf kalıyor; intrusive header ise string yolundaki son büyük teknik borç ve `Result`'ın `value` alanındaki string'ler de ondan etkileniyor.
