# P2-18c — Tip Çözücü Operatörler ve `?` Desteği

**Tarih:** 9 Kasım 2026
**Görev:** `TODO.md` → P2-18c
**Durum:** ✅ self-hosted **8/21 → 11/21**, hepsi Python sürücüsüyle aynı çıktı

---

## 1. Özet

Bu turda eklenen üç örnek (`12`, `14`, `19`) sadece **derlenmiyor**, aynı
zamanda **doğru çalışıyor**. Bunu kanıtlayan parite testi de yazıldı.

> Önemli ders: ilk denemede `12` ve `14` **derlendi ama yanlış sonuç verdi**
> (`verify` düşüyordu). "Derlendi" ile "doğru" arasındaki farkı ancak çıktı
> karşılaştırması gösterdi.

---

## 2. Bulunan ve düzeltilen 5 gerçek hata

### 2.1 `==` iki değişkende **pointer** karşılaştırması yapıyordu

```axiom
verify secilen == "gzip-ok", "Gzip acilan veri orjinali ile birebir ayni olmali!"
```

```c
/* önce */  if (!((secilen == "gzip-ok"))) { ... }      // adres karşılaştırması
/* sonra */ if (!(axiom_eq_auto(secilen, "gzip-ok"))) { ... }
```

Self-hosted parser tipleri izlemediği için `is_str_expr` sezgiseli yalnızca
*literal* ve bilinen üreticilerde çalışıyor; iki **değişken** karşılaştırıldığında
`(a == b)` üretiliyordu. Bu, C'de pointer karşılaştırmasıdır — sessizce yanlış.

Çözüm: `axiom_eq_auto` / `axiom_neq_auto` (`_Generic`):

```c
#define axiom_eq_auto(a, b) _Generic((a), \
    char*: axiom_str_eq, const char*: axiom_str_eq, \
    float: axiom_eq_float_, double: axiom_eq_float_, \
    default: axiom_eq_int_)(a, b)
```

### 2.2 `+` operatöründe tip bilinmiyordu

```c
out = (out + c);   // error: invalid operands to binary expression ('ax_str' and 'ax_str')
```

`axiom_add_auto` eklendi: sol operand metinse `axiom_str_concat`, sayıysa
toplama. Karar `_Generic` ile derleme anında veriliyor.

### 2.3 `?` operatörü hiç desteklenmiyordu

Lexer `?` karakterini "bilinmeyen karakter" olarak **sessizce atlıyordu**.
Sonuç:

```axiom
let port = parse_port(port_str)?     # Result açılmıyor
```

üretilen C: `__auto_type port = ax_parse_port(...);` — `port` bir `Result`
struct'ı, `print(port)` derlenmiyor. Hata mesajı kaynaktan çok uzakta çıkıyordu.

Düzeltme (lexer + parser):

```c
__auto_type port_ax_try_684 = ax_parse_port(port_str);
if (!((port_ax_try_684).is_ok)) {
    <kapsam defer'leri>
    return port_ax_try_684;
}
__auto_type port = (port_ax_try_684).value;
```

### 2.4 `return` + `defer` yolunda `ax_typeof(...)`

```c
/* önce */  ax_typeof( axiom_result_ok_int(port) ) ret_val = ...;
/* sonra */ __auto_type ret_val = axiom_result_ok_int(port);
```

`ax_typeof` bir **makro çağrısının** tipini çıkaramıyor (makro genişlemesi
sonrası tipi görüyor ama bizim durumumuzda yanlış sonuç veriyordu).
`__auto_type` her iki durumda da doğru.

### 2.5 Bilinmeyen `ax_X(...)` çağrıları

Stdlib bazı yerleşikleri `rt_` öneki olmadan çağırıyor:

```
error: call to undeclared function 'ax_json_parse'
error: call to undeclared function 'ax_tcp_ping'
error: call to undeclared function 'ax_cli_set_args'
```

Codegen'e genel çözüm eklendi: gövdedeki her `ax_<ad>(` çağrısı için, `<ad>`
kullanıcı fonksiyonu **değilse** `axiom_<ad>` üretilir. Bir kural, tüm sınıf.

---

## 3. Parite testi — asıl kazanç

`tests/test_selfhosted_parity.py` (14 test):

| Test | Ne yapar |
|---|---|
| `test_selfhosted_matches_python_driver` | Listedeki her örnek için `bin/axiomc` çıktısını `bin/axiom` çıktısıyla karşılaştırır |
| `test_supported_list_is_accurate` | Liste şişirilemez — her örnek gerçekten derlenmeli |
| `test_compiling_but_wrong_is_not_counted` | `12`/`14` çalışma anında patlarsa yakalar (P2-18c regresyonu) |
| `test_utf8_source_not_truncated` | Çok baytlı kaynak kesilmesi (P2-18 regresyonu) |

Normalizasyon (kaçınılmaz farklar): PID, ISO zaman damgası, geçen süre (ms),
`timestamp_ms`, bellek adresleri, ANSI renk kodları.

Bu olmadan `08_multithreaded_scanner` süre farkıyla, `12` PID farkıyla
"başarısız" görünürdü; normalize edilince gerçek içerik farkı kalıyor.

---

## 4. Sonuç

| | P2-18 | P2-18b | **P2-18c** |
|---|---|---|---|
| Self-hosted derlenen+**doğru** çalışan | 8/21 | 8/21 | **11/21** |
| Yeni | 05, 08, 09, 17 | — | **12, 14, 19** |

```bash
python3 -m pytest -q --no-header     # 940 passed, 2 skipped
./bin/axiomc  → 11/21 örnek
axiom build --backend=llvm → 21/21
axiom build (C)            → 21/21
```

---

## 5. Kalan 10 örnek ve nedenleri

| Örnek | Engel |
|---|---|
| `07_http_banner_grabber` | `ensures return.field >= 0` — alan erişimli ensures |
| `10`, `21` | `str[]` alan erişimi + generic fonksiyon örnekleme |
| `11` | `tls_id` (struct alanı olarak kullanılan değişken) |
| `13` | `str[]` dizi literali tipi (`(ax_int[]){"a","b"}` üretiliyor) |
| `15` | Tip listesi parametrelerinde (`craft_ipv4_header(src_ip, str, ...)`) |
| `16`, `22` | `Result`/struct dizi alan erişimi |
| `18` | `ax_array_Route` alan erişimi (`.capacity`) |
| `20` | Generic fonksiyon çağrı yerine göre örnekleme |

### 5.1 P2-18d (ertelenen)

`Result<T,E>`/`Box<T>` generic **fonksiyon gövdesinin** çağrı yerine göre ayrı
örneklenmesi. Şu an gövde `T → int` ikamesiyle **tek kez** üretiliyor; `result_*`
yardımcıları tipli makrolara yönlendirildiği için pratikte çalışıyor, ama
`Box<T>` gibi kullanıcı tiplerinde yanlış olur.

Doğru çözüm: çağrı yerlerinden `(fonksiyon, tip argümanları)` kümesi topla,
her biri için ayrı C fonksiyonu üret (`ax_wrap_int`, `ax_wrap_str`). Struct
monomorfizasyonunun fonksiyonlara uygulanmış hâli.

---

## 6. Sıradaki

| # | İş | Beklenti |
|---|---|---|
| 1 | **P2-18d** generic fonksiyon örnekleme | 3–4 örnek daha |
| 2 | `str[]` dizi literali tipi | `13` + birkaç yer |
| 3 | P2-17b intrusive header | Performans/ABI |
| 4 | Faz 3 hazırlığı | Paket yayını + kullanıcı |
