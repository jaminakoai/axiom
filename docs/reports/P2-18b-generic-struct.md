# P2-18b — Generic Struct Somutlaştırma + Bulunan HTTP RST Hatası

**Tarih:** 9 Kasım 2026
**Görev:** `TODO.md` → P2-18b (kısmi)
**Durum:** 🟡 altyapı düzeltildi; örnek sayısı 8/21'de sabit

---

## 1. Dürüst özet

Bu turda **8 örneği birden açmak** hedefleniyordu. Açılmadı. Ama hedeflenen
altyapının önündeki **6 gerçek hata** bulundu ve düzeltildi, ayrıca bağımsız
bir **runtime hatası** (HTTP RST) keşfedilip kapatıldı.

En somut ilerleme: `examples/12_packet3_system_exploit.ax` **20 C hatasından
1'e** indi.

---

## 2. Düzeltilen 6 self-hosted derleyici hatası

### 2.1 Uzantısız `import "std/..."` sessizce atlanıyordu

```axiom
import "std/core/error"       // .ax yok
```

`resolve_file`, `std/` öneki için yolu olduğu gibi birleştiriyor, `file_exists`
başarısız olunca **hiçbir uyarı vermeden** modülü atlıyordu. Sonuç: `Result`
struct'ı hiç tanımlanmıyor, hata "unknown type name" olarak çok sonra çıkıyordu.

Düzeltme: `.ax` yoksa ve dosya bulunamıyorsa `.ax` eklenir.
Sessiz atlama, tüm "tanımsız tip" hatalarının gizli kaynağıydı.

### 2.2 `E` tip parametresi hiç tanınmıyordu

```axiom
struct Result<T, E> { is_ok: bool, value: T, error: E }
```

`is_generic_template` yalnız `T/U/V/K` arıyordu. `Result` generic sayılmadığı
için **hiçbir zaman somutlaşmadı** — `ax_Result_int_str` hiç üretilmiyordu.
`E`, `A`, `B` eklendi (alan eşlemesi + `to_c_type`).

### 2.3 Generic argümanda `str[]` reddediliyordu

Monomorfizasyon döngüsü yalnız IDENT/tip token'larını kabul ediyordu; `[` ve
`]` görünce `is_valid_generic = false` yapıyordu. `Result<str[], str>` hiç
üretilmiyordu. Döngü yeniden yazıldı: argümanlar virgülde ayrılır, `[]` tipe
eklenir.

### 2.4 C tanımlayıcısında `[]` geçersiz

`ax_Result_str[]_str` — geçersiz C. Struct adı, struct literal ve tip adı
yollarının üçünde de `[]` → `_array` eşlemesi eklendi. (Üç ayrı yer; biri
atlanınca hata başka satırda görünüyordu.)

### 2.5 `rt_*` yerleşikleri C'ye çıplak geçiyordu

```
error: call to undeclared function 'rt_base64_encode'
error: call to undeclared function 'rt_dns_resolve_ipv4'
error: call to undeclared function 'rt_buf_create'
error: call to undeclared function 'rt_regex_is_match'
error: call to undeclared function 'rt_forensics_get_ports'
```

Tek genel kural eklendi: `rt_X` → `axiom_X`. Bu, yedi örnekteki **20'şer
hatayı** tek seferde kaldırdı.

### 2.6 `result_ok<T>` tip parametresi çözülemiyordu

Tek geçişli derleyici T'yi bilemediği için her çağrı `ax_result_ok` (T=int)
üretiyordu. `Result<str,str>` bekleyen fonksiyona `Result<int,str>` dönüyordu.

Çözüm iki katmanlı:

| Çağrı biçimi | Üretilen C |
|---|---|
| `result_ok<str>(x)` | `axiom_result_ok_str(x)` |
| `result_ok(x)` | `axiom_result_ok_auto(x)` → `_Generic` değerin tipine göre seçer |

`axiom_result_ok_int/str/bool` makroları `runtime.h`'de; struct'lar kullanıcı
kodunda üretildiği için makrolar yalnız kullanım anında genişler.

---

## 3. Bonus: gerçek runtime hatası — HTTP sunucusu RST

`tests/test_packet2_libs.py` tam pakette ara sıra düşüyordu (~%20). Kök neden
test değil, **runtime**'dı:

```c
send(client_fd, full_resp, total_len, 0);
shutdown(client_fd, SHUT_WR);
close(client_fd);            // istek hiç okunmadı
```

Okunmamış veri bulunan bir TCP soketini kapatmak **RST** gönderir; RST,
gönderilmiş ama henüz teslim edilmemiş yanıtı da düşürebilir. İstemci
`HTTP/1.1` sonrasında çöp bayt (`0xbd`) görüyordu.

Düzeltme: `shutdown` sonrası drain döngüsü (recv → 0), sonra `close`.
Sonuç: 10/10 ve 4 ardışık tam paket çalıştırması temiz.

Ayrıca `get_free_port` aynı portu tekrar dağıtabiliyordu; verilen portlar artık
süreç boyunca tekrar kullanılmıyor.

---

## 4. Neden 8/21'de kaldı

Kalan 13 örneğin engeli artık **generic fonksiyon gövdesi üretimi**:

```axiom
fn result_ok<T>(v: T) -> Result<T, str>   // T çağrı yerine göre değişir
```

Doğru çözüm, çağrı yerlerinden toplanan somut tipler için ayrı C fonksiyon
gövdeleri üretmek (struct'larda yapılanın fonksiyonlara uygulanması). Bu,
`ASTFunction`'a tip parametre listesi eklemeyi ve codegen'de örnek başına gövde
üretmeyi gerektirir — ayrı bir tur (P2-18c).

Ayrıca `out = out + c` gibi ifadelerde `+` operatörünün string birleştirme
olduğunu anlamak değişken tip ortamı gerektiriyor (P2-18c).

---

## 5. Durum

```bash
python3 -m pytest -q --no-header     # 923 passed, 2 skipped in 691.96s
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **923** |
| C örnekleri | 21/21 |
| LLVM örnekleri | 21/21 |
| Self-hosted | 8/21 (değişmedi) |
| `test_packet2_libs.py` | **4/4 temiz** (önce ~%20 flaky) |
| `make fmt-check` | ✅ |
| Bootstrap | ✅ |

---

## 6. Sıradaki

| # | İş | Beklenti |
|---|---|---|
| 1 | **P2-18c** generic fonksiyon monomorfizasyonu | 8 örneği açabilir |
| 2 | **P2-18c** `+` operatöründe string birleştirme çıkarımı | 12'yi kapatır |
| 3 | P2-17b intrusive header | Performans/ABI |
| 4 | Faz 3 hazırlığı | Paket yayını + kullanıcı |
