# Axiom (λx) Dil Şartnamesi — v0.5

> 🌍 **English:** [docs/en/SPECIFICATION.md](docs/en/SPECIFICATION.md)

**Durum:** Alfa (`v0.5.0-alpha`)
**Bu belge:** Dilin gözlemlenebilir davranışını tanımlar. Uygulama bu şartnameye uymakla yükümlüdür; çelişki varsa **şartname değil, uygulama hatalıdır** — ya uygulama düzeltilir ya da bu belge gerekçesiyle güncellenir.

> **Alfa uyarısı:** Geriye dönük uyumluluk **taahhüt edilmez**. Sözdizimi ve semantik değişebilir; değişiklikler `CHANGELOG.md`'ye yazılır.

---

## 1. Kapsam ve terminoloji

| Terim | Anlam |
|---|---|
| **zorunludur** | Uyumlu her uygulama bunu yapmalıdır. |
| **önerilir** | Yapılmaması hata değildir, ancak beklenmeyen davranışa yol açabilir. |
| **tanımsız** | Davranış garanti edilmez; programcı buna güvenmemelidir. |
| **derleme zamanı** | Kaynak → ikili dönüşümü sırasında. |
| **çalışma zamanı** | Üretilen ikili çalışırken. |

Şartname **C arka ucunu** (varsayılan) referans alır. LLVM arka ucu aynı gözlemlenebilir davranışı sağlamalıdır; sapmalar §13.4'te listelenir.

---

## 2. Tasarım ilkeleri

1. **Sıfır bilişsel yük** — borrow checker yok; `defer` tabanlı kapsam temizliği ve değer anlambilimi.
2. **Çöp toplayıcısız (zero-GC)** — duraklama yok; bellek sahipliği derleyici + runtime işbirliğiyle yönetilir.
3. **Sözleşmeli güvenlik** — `requires` / `ensures` / `verify` ile mantık hataları derleme veya çalışma anında durdurulur.
4. **Yerel derleme** — C99 veya LLVM IR üzerinden bağımsız ELF; yorumlayıcı yoktur.
5. **İki katmanlı hata modeli** — *beklenen* hatalar `Result<T,E>` + `?`; *programlama* hataları sözleşme ihlali → program durur.

---

## 3. Sözcüksel yapı

### 3.1 Kaynak kodlama

Kaynak dosyalar UTF-8'dir. Uzantı `.ax`'tir.

### 3.2 Yorumlar

```axiom
# Tek satır (Python biçimi)
// Tek satır (C biçimi)
```

Blok yorumu (`/* */`) yoktur.

### 3.3 Anahtar kelimeler (tam liste)

```
fn  let  mut  if  else  while  for  in  return  print
verify  requires  ensures  struct  import
break  continue  defer  invariant  as  match
true  false  and  or  not
```

Bu sözcükler tanımlayıcı olarak kullanılamaz.

### 3.4 Tip adları

```
int  float  bool  str  void
```

### 3.5 Tanımlayıcılar

`[A-Za-z_][A-Za-z0-9_]*`. `_` tek başına joker desendir (`match`).

### 3.6 Sayı literalleri

```
42          # int
3.14        # float
```

- Negatif sayı literal değildir; tekli `-` operatörüdür.
- `0x`, `0b`, alt çizgi ayırıcı (`1_000`) **desteklenmez**.
- Bilimsel gösterim (`1e9`) **desteklenmez**.

### 3.7 Metin literalleri

Çift tırnak. Desteklenen kaçış dizileri:

| Kaçış | Anlam |
|---|---|
| `\n` | satır sonu |
| `\r` | satır başı |
| `\t` | sekme |
| `\\` | ters bölü |
| `\"` | çift tırnak |

Diğer `\x` dizileri `x` olarak yorumlanır. Çok satırlı metin bloğu yoktur.

### 3.8 Operatörler ve öncelik (yüksekten düşüğe)

| Öncelik | Operatörler | İlişki |
|---|---|---|
| 1 | `()` `[]` `.` `?` | postfix |
| 2 | `-` `+` `not` | tekli (ön ek) |
| 3 | `as` | tip dönüşümü |
| 4 | `*` `/` `%` | soldan |
| 5 | `+` `-` | soldan |
| 6 | `<` `<=` `>` `>=` | soldan |
| 7 | `==` `!=` | soldan |
| 8 | `and` | soldan |
| 9 | `or` | soldan |
| 10 | `=` | atama (deyim) |

`=` atama dışında ifade üretmez.

---

## 4. Tipler

### 4.1 Yerleşik tipler

| Axiom | C karşılığı | Açıklama |
|---|---|---|
| `int` | `int64_t` | 64-bit işaretli tamsayı |
| `float` | `double` | 64-bit IEEE-754 |
| `bool` | `bool` | `true` / `false` |
| `str` | `const char*` | UTF-8, NUL sonlandırmalı |
| `void` | `void` | değer yok |

### 4.2 Bileşik tipler

- **Dizi:** `T[]` — `{ length: int, capacity: int, data: T* }`.
- **Struct:** `struct Ad { alan: Tip, ... }` — değer tipi.
- **Generic parametre:** `T` (yalnızca generic bildirimlerde).

### 4.3 Tip çıkarımı

`let x = <ifade>` biçiminde tip ifadeden çıkarılır. Çıkarım yalnızca ilk atamada yapılır; sonradan tip değişmez.

### 4.4 Açık dönüşüm (`as`)

```axiom
let a = 3.9 as int      # 3 (kesir atılır)
let b = 7 as float      # 7.0
let c = 1 as bool       # true
```

Desteklenen hedefler: `int`, `float`, `bool`. `as str` **desteklenmez**; metne çevirme için `int_to_str` kullanılır.

### 4.5 Tip uyumu

- Aritmetikte `int` ve `float` karışabilir; sonuç `float` olur.
- Karşılaştırmada (`<`, `<=`, `>`, `>=`) iki taraf da sayısal **veya** iki taraf da `str` olmalıdır. `int < str` **derleme hatasıdır**.
- Eşitlikte (`==`, `!=`) tipler aynı olmalı (sayısal tipler arası geçiş serbest).
- Mantıksal `and`/`or`/`not` yalnızca `bool` alır.

---

## 5. Değişkenler ve kapsam

```axiom
let sabit = 10          # değiştirilemez
let mut sayac = 0       # değiştirilebilir
let port: int = 8080    # açık tip
```

- `let` ile tanımlanan değişkene atama **derleme hatasıdır**.
- Kapsam blok tabanlıdır (`{}`).
- **Aynı blokta** aynı adla ikinci `let` **derleme hatasıdır**.
- **İç blokta** aynı ad yeniden tanımlanabilir (gölgeleme); iç tanım bloğun dışında görünmez.
- İç blokta tanımlanan değişken blok bitince kapsam dışına çıkar (dıştaki değer korunur).
- Tanımsız değişken kullanımı derleme hatasıdır.

---

## 6. İfadeler

### 6.1 Aritmetik

`+ - * / %` — `int` işlemlerinde **taşma denetlenir**: taşma `ARITHMETIC_OVERFLOW` ile programı `exit 101` ile durdurur. `/` ve `%` sıfır böleninde `ARITHMETIC_ZERO_DIV` ile durdurur.

`float` işlemlerinde taşma denetlenmez (IEEE-754 davranışı).

### 6.2 Metin birleştirme

`str + str` yeni bir `str` üretir (heap). `str + int` **geçersizdir**; `int_to_str` kullanılmalıdır.

### 6.3 Karşılaştırma ve mantık

`< <= > >= == !=` → `bool`. `and` / `or` kısa devre yapar. `not` tekli.

### 6.4 İndeksleme

`dizi[i]`, `metin[i]` → eleman / tek karakter `str`.

Sınır denetimi **çalışma zamanında zorunludur**: `i < 0` veya `i >= len` → `exit 102`.

### 6.5 Fonksiyon çağrısı

`ad(arg1, arg2)`. Argüman sayısı ve tipleri derleme anında denetlenir.

### 6.6 Struct oluşturma ve alan erişimi

```axiom
struct Point { x: int, y: int }
let p = Point { x: 1, y: 2 }
let a = p.x
p.x = 3        # yalnızca `let mut p` ise
```

Tüm alanlar verilmelidir; eksik alan derleme hatasıdır.

### 6.7 `match` ifadesi

```axiom
let ad = match x {
    1 => "bir",
    _ => "diger"
}
```

Desen türleri: literal (`1`, `"a"`, `true`), tanımlayıcı (bağlama), joker `_`. Guard desteklenir: `n if n > 10 => ...`.

`bool` ve `int` üzerinde tüketici (exhaustive) olması için joker veya tüm durumlar gerekir; eksik desen derleme hatasıdır.

### 6.8 `?` operatörü

`<ifade>?` — `<ifade>` Result benzeri olmalıdır (§9).

---

## 7. Deyimler

### 7.1 `if` / `else`

```axiom
if kosul {
    ...
} else if diger {
    ...
} else {
    ...
}
```

Koşul `bool` olmalıdır.

### 7.2 `while`

```axiom
while kosul {
    ...
}
```

İsteğe bağlı `invariant <ifade>` (ispatlayıcı için).

### 7.3 `for`

```axiom
for i in 0..10 { ... }     # 0,1,...,9  (üst sınır hariç)
```

Döngü değişkeni `int`'tir ve gövde içinde değiştirilemez. İsteğe bağlı `invariant`.

### 7.4 `break` / `continue`

Yalnızca döngü içinde; döngü dışında derleme hatası. Her ikisi de o anda açık olan en iç bloğun `defer`'larını ve sahipli kaynaklarını bırakır.

### 7.5 `return`

`return` veya `return <ifade>;`. Dönüş tipi `void` değilse **tüm kod yollarında** `return` bulunmalıdır (kesin dönüş analizi); eksikse derleme hatası.

### 7.6 `defer`

```axiom
fn main() -> int {
    defer { print("temizlik") }
    print("govde")
    return 0
}
```

- Kapsam çıkışında **LIFO** (son giren ilk çıkar) çalışır.
- Erken `return`, `break`, `continue` ve `?` ile erken dönüşte de çalışır.
- `defer` içindeki ifade, kaydedildiği andaki değişken değerlerini değil, **çalıştığı andaki** değerleri görür.

### 7.7 `print`

`print(a, b, c)` — argümanları aralarına tek boşluk koyarak ve sonuna satır sonu ekleyerek yazar. Tip otomatik biçimlenir (`int`, `float`, `bool`, `str`).

### 7.8 `verify`

`verify <koşul>, "<mesaj>"` — koşul `bool`. Derleme anında ispatlanabiliyorsa ispatlayıcı reddeder; aksi halde çalışma anında `exit 101`.

---

## 8. Fonksiyonlar ve sözleşmeler

### 8.1 Bildirim

```axiom
fn ad(p1: Tip1, p2: Tip2) -> DonusTipi
    requires <bool ifade>
    ensures <bool ifade>          # 'return' sembolü kullanılabilir
{
    ...
}
```

### 8.2 Sözleşmeler

| Sözleşme | Ne zaman | İhlal davranışı |
|---|---|---|
| `requires` | Fonksiyon girişinde | `exit 101`, `REQUIRES` |
| `ensures` | Her `return` yolunda | `exit 101`, `ENSURES` |
| `verify` | Deyim olarak | `exit 101`, `VERIFY` |

`ensures` içinde `return` sembolü, dönen değeri temsil eder.

**Sözleşmeler programlama hataları içindir.** Kullanıcı girdisi, dosya yokluğu gibi *beklenen* durumlar `Result` ile ele alınmalıdır (§9).

### 8.3 Aşırı yükleme

Aynı ad, farklı parametre tipleriyle birden fazla kez tanımlanabilir. Çözümleme argüman tiplerine göre yapılır. Aynı imza iki kez tanımlanamaz.

### 8.4 Generic fonksiyonlar

```axiom
fn wrap<T>(x: T) -> Box<T> { return Box<T> { val: x } }
```

Tip parametreleri çağrıda açık (`wrap<int>(42)`) veya argümandan çıkarımla belirlenir.

---

## 9. Hata modeli

### 9.1 `Result<T, E>`

```axiom
struct Result<T, E> {
    is_ok: bool,
    value: T,
    error: E
}
```

`?` operatörü **yapısal** çalışır: alanları `is_ok: bool`, `value`, `error` olan **her** struct Result sayılır. Kullanıcı kendi hata tipini tanımlayabilir.

### 9.2 `?` operatörü kuralları

1. İfade Result benzeri olmalıdır; değilse derleme hatası.
2. Yalnızca Result döndüren bir fonksiyon gövdesinde kullanılabilir.
3. İfadenin hata tipi (`E`) ile fonksiyonun dönüşündeki hata tipi **aynı** olmalıdır.
4. `Ok` ise `value` üretilir ve akış sürer.
5. `Err` ise: o ana kadar açık `defer`'lar LIFO çalışır, sahipli kaynaklar bırakılır, hata üst fonksiyona döner.

### 9.3 `main` ve `Result`

```axiom
fn main() -> Result<int, str> { ... }
```

| Dönüş | Davranış |
|---|---|
| `Ok` | `exit 0` |
| `Err(msg)` | `msg` → `stderr` (`[AXIOM HATA] ...`), `exit 1` |

`fn main() -> int` kullanılırsa dönüş değeri çıkış kodudur.

### 9.4 İki katman özeti

| Durum | Mekanizma | Sonuç |
|---|---|---|
| Beklenen hata (dosya yok, port kapalı, parse hatası) | `Result` + `?` | Akar; çağıran karar verir |
| Programlama hatası (geçersiz sabit, yanlış mantık) | `requires` / `ensures` / `verify` | `exit 101` |
| Dizi sınırı | Çalışma zamanı denetimi | `exit 102` |
| Tamsayı taşması / sıfıra bölme | Çalışma zamanı koruması | `exit 101` |

---

## 10. Bellek modeli

### 10.1 Değer anlambilimi

- Primitifler (`int`, `float`, `bool`) ve `str` (işaretçi) kopyalanır.
- **Diziler değer tipidir:** `let b = a` **derin kopya** üretir. `b`'yi değiştirmek `a`'yı etkilemez.
- Struct'lar değer tipidir.

### 10.2 String sahipliği

Axiom'da `str` bir işaretçidir; heap'te ayrılan string'ler runtime'da **referans sayımı** ile izlenir.

- `str` döndüren runtime fonksiyonları sonucu sahiplik tablosuna kaydeder.
- Kapsam çıkışında, `let`/atama/`return` yollarında üretilen geçici string'ler bırakılır.
- Struct alanına, diziye veya çağrı argümanına "kaçan" string'ler kapsam sonunda bırakılmaz (kaçış analizi).
- Literaller ve `os_getenv` gibi dış işaretçiler sahiplik dışıdır; serbest bırakma no-op'tur.

**Bilinen sınır (v0.5):** atama yapılmayan ifadelerde üretilen geçici string'ler (`print(f(x))`) ifade sonunda bırakılmaz. Sıcak döngülerde sonucu değişkene atayın.

### 10.3 Açık serbest bırakma

`str_free(s)` bir string'i hemen bırakır ve işaretçiyi `NULL`'lar (çift serbest bırakma güvenlidir).

### 10.4 `defer` ve kaynak temizliği

`defer`, kapsam çıkışında çalışır; sahipli kaynaklar için birincil araçtır.

---

## 11. Modüller

```axiom
import "std:io:file"
import "std/io/file"
import "std/io/file.ax"
import "utils.ax"          # göreli dosya
```

- `std:` / `std/` öneki standart kütüphaneyi çözer.
- Göreli yollar içe aktaran dosyaya göre çözülür.
- **Döngüsel bağımlılık** derleme hatasıdır.
- **Elmas bağımlılık** (aynı dosyanın iki yoldan gelmesi) bir kez dahil edilir.
- İsim alanı (namespace) yoktur; tüm semboller tek düzlemdedir.

### 11.1 Ofansif modül izolasyonu

Şu modüller varsayılan derlemede **reddedilir**:

`std/security/shellcode.ax`, `std/security/evasion.ax`, `std/security/memdump.ax`,
`std/net/c2.ax`, `std/net/packet_crafter.ax`

Yalnızca `--features offensive` bayrağı veya `AXIOM_FEATURES=offensive` ortam değişkeniyle derlenebilir.

---

## 12. Eşzamanlılık

| Fonksiyon | İmza | Not |
|---|---|---|
| `thread_create` | `(fn, arg: int) -> int` | Thread argümanı **yalnızca `int`** |
| `thread_join` | `(id: int) -> int` | Thread'in dönüş değeri |
| `mutex_init` | `() -> int` | |
| `mutex_lock` / `mutex_unlock` | `(id: int) -> void` | |
| `atomic_init` / `atomic_add` / `atomic_get` | `(int) -> int` | |
| `sleep_ms` | `(ms: int) -> void` | |

Thread'e yalnızca `int` geçirilebilir; karmaşık veri için global/handle yöntemi kullanılır. Veri yarışı denetimi **yoktur**; senkronizasyon programcının sorumluluğundadır.

---

## 13. Yerleşik fonksiyon kataloğu

Toplam **86** kullanıcıya açık yerleşik (dahili `rt_*` takma adları hariç).

### 13.1 Metin

| Fonksiyon | İmza | Açıklama |
|---|---|---|
| `str_len` | `(str) -> int` | UTF-8 karakter sayısı |
| `str_byte_len` | `(str) -> int` | Bayt sayısı |
| `str_char_at` | `(str, int) -> str` | Tek karakter |
| `str_char_code` | `(str, int) -> int` | Kod noktası |
| `char_to_str` | `(int) -> str` | Kod noktasından metin |
| `str_sub` | `(str, int, int) -> str` | Alt metin (başlangıç, uzunluk) |
| `str_index_of` | `(str, str) -> int` | İlk konum, yoksa `-1` |
| `str_contains` | `(str, str) -> bool` | |
| `str_starts_with` | `(str, str) -> bool` | |
| `str_ends_with` | `(str, str) -> bool` | |
| `str_trim` | `(str) -> str` | Baş/son boşluk |
| `str_replace` | `(str, str, str) -> str` | Tümünü değiştir |
| `str_split` | `(str, str) -> str[]` | Ayırıcıya böl |
| `str_join` | `(str[], str) -> str` | Ayırıcıyla birleştir |
| `str_to_int` | `(str) -> int` | Geçersizse `0` |
| `int_to_str` | `(int) -> str` | |
| `str_free` | `(str) -> void` | Hemen bırak |
| `str_owned_count` | `() -> int` | **Tanılama:** izlenen string sayısı |

### 13.2 Matematik

`math_abs(int)->int`, `math_min(int,int)->int`, `math_max(int,int)->int`, `math_pow(int,int)->int`

### 13.3 Dosya ve işletim sistemi

| Fonksiyon | İmza | Hata davranışı |
|---|---|---|
| `file_read` | `(str) -> str` | `""` |
| `file_write` | `(str, str) -> bool` | `false` |
| `file_exists` | `(str) -> bool` | — |
| `os_getenv` | `(str) -> str` | `""` |
| `os_exec` | `(str) -> int` | Kabuk üzerinden |
| `os_exec_argv` | `(str[]) -> int` | Kabuk yok (enjeksiyon güvenli) |
| `time_now_ms` | `() -> int` | — |

### 13.4 Ağ

`tcp_connect(str,int)->int`, `tcp_send(int,str)->int`, `tcp_recv(int,int)->str`, `socket_close(int)->void`

### 13.5 Dizi ve SIMD

| Fonksiyon | İmza |
|---|---|
| `array_push_int` / `array_push_str` | `(T[], T) -> T[]` |
| `simd_add_i64` / `sub` / `mul` | `(int[], int[]) -> int[]` |
| `simd_sum_i64` | `(int[]) -> int` |
| `simd_scan_match` | `(int[], int) -> int` |

### 13.6 Tensör

`tensor_create_2d(int,int)->int`, `tensor_set(int,int,int,float)->void`, `tensor_get(int,int,int)->float`,
`tensor_rows/cols(int)->int`, `tensor_matmul/add/transpose(int,int)->int`, `tensor_to_str(int)->str`, `tensor_free(int)->void`,
`dot_product(int,int)->float`, `nn_relu(float)->float`, `nn_sigmoid(float)->float`, `nn_argmax(int)->int`

### 13.7 Güvenlik / sistem tanılama

`exec_mem_run/alloc/protect`, `packet_craft_ip/tcp/udp`, `diag_is_debugged/is_virtualized/set_dumpable`,
`proc_search_pattern`, `proc_get_maps`, `pcap_*`, `fim_hash_file`, `forensics_get_ports/modules`,
`crypto_memcmp`

> Bu fonksiyonların çoğu ilgili `std/` modülü üzerinden kullanılmalıdır; doğrudan çağrı desteklenir ama taşınabilirlik garanti edilmez.

### 13.8 Modül düzeyi API

`std/` modülleri ek olarak `Result` tabanlı sarmalayıcılar sunar:
`std/io/file` (`read_file`, `write_file`, …), `std/encoding/json` (`json_get_*_result`),
`std/net/http` (`http_get_result`, `http_status`, `http_body`), `std/crypto/tls` (`https_get_result`),
`std/os/process` (`exec_output_result`).

---

## 14. Derleme hattı

```
[ .ax kaynak ]
      │
      ▼
  1. Lexer ──────► token akışı
      │
      ▼
  2. Parser ─────► AST
      │
      ▼
  3. Resolver ───► modül birleştirme (döngü tespiti, elmas tekilleştirme)
      │
      ▼
  4. Checker ────► tip, kapsam, kesin dönüş, sözleşme, monomorflaştırma
      │
      ▼
  5. Prover ─────► sembolik aralık analizi (varsayılan) / Z3 SMT (isteğe bağlı)
      │
      ├──► 6a. C99 codegen ──► clang ──► ELF
      └──► 6b. LLVM IR codegen ──► clang ──► ELF
```

`axiom check` 1–4 (+5 sembolik) çalıştırır. `axiom build` hepsini çalıştırır.

---

## 15. Çalışma zamanı ve ABI

### 15.1 Tip eşlemesi

| Axiom | C |
|---|---|
| `int` | `int64_t` |
| `float` | `double` |
| `bool` | `bool` |
| `str` | `const char*` |
| `T[]` | `struct { int64_t length; int64_t capacity; T* data; }` |

### 15.2 Struct dönüşü

16 bayttan büyük struct'lar SysV ABI gereği **sret** (gizli işaretçi) ile döner. Bu, C ve LLVM arka uçlarında tutarlı uygulanmalıdır.

### 15.3 Çıkış kodları

| Kod | Anlam |
|---|---|
| `0` | Başarı |
| `1` | Genel hata (`main` `Err` döndürdü, CLI kullanım hatası) |
| `101` | Sözleşme veya aritmetik ihlali (`REQUIRES`/`ENSURES`/`VERIFY`/`ARITHMETIC_*`) |
| `102` | Dizi sınırı aşımı |
| `127` | `exec` başarısız |

---

## 16. Tanımlanmış ve tanımsız davranış

### 16.1 Garanti edilen

- `int` taşması → `exit 101` (sessiz sarma **yok**).
- Sıfıra bölme/mod → `exit 101`.
- Dizi sınırı → `exit 102`.
- Eksik `return` → derleme hatası.
- Tip uyumsuzluğu → derleme hatası.
- Dizi ataması → derin kopya.

### 16.2 Garanti edilmeyen (tanımsız)

- `float` taşması/NaN davranışı (IEEE-754'e bırakılır).
- Eşzamanlı erişimde veri yarışı sonucu.
- Dış C kütüphanelerinin hata kodları (`file_read` `""` ile hatayı ayırt edemez).
- `AXIOM_TLS_INSECURE=1` ayarlandığında sertifika doğrulaması.
- Thread'e `int` dışında veri geçirme.

---

## 17. Uyumluluk ve sürümleme

- Sürüm biçimi: `MAJOR.MINOR.PATCH[-etiket]`. Alfa döneminde `0.x.y-alpha`.
- Alfa döneminde **geriye dönük uyumluluk taahhüdü yoktur**.
- Her kullanıcıya görünen değişiklik `CHANGELOG.md`'ye yazılır.
- Dil yüzeyi değişikliği bu şartnamenin sürümünü artırır.

---

## 18. Ek: Sözdizimi özeti (EBNF benzeri)

```ebnf
program        = { declaration } ;
declaration    = struct_decl | function_decl | import_stmt | statement ;

import_stmt    = "import" STRING [ ";" ] ;
struct_decl    = "struct" IDENT [ "<" type_params ">" ] "{"
                     { IDENT ":" type [ "," ] }
                 "}" ;
function_decl  = "fn" IDENT [ "<" type_params ">" ] "(" [ params ] ")"
                 [ "->" type ] { contract } block ;
params         = param { "," param } ;
param          = IDENT ":" type ;
type_params    = IDENT { "," IDENT } ;
contract       = "requires" expr | "ensures" expr ;

type           = base_type { "[]" } ;
base_type      = "int" | "float" | "bool" | "str" | "void"
               | IDENT [ "<" type { "," type } ">" ] ;

block          = "{" { statement } "}" ;
statement      = let_decl | assign | if_stmt | while_stmt | for_stmt
               | return_stmt | break_stmt | continue_stmt | defer_stmt
               | print_stmt | verify_stmt | match_stmt | expr_stmt ;

let_decl       = "let" [ "mut" ] IDENT [ ":" type ] "=" expr ;
assign         = lvalue "=" expr ;
if_stmt        = "if" expr block [ "else" ( if_stmt | block ) ] ;
while_stmt     = "while" expr [ "invariant" expr ] block ;
for_stmt       = "for" IDENT "in" expr ".." expr [ "invariant" expr ] block ;
return_stmt    = "return" [ expr ] ;
break_stmt     = "break" ;
continue_stmt  = "continue" ;
defer_stmt     = "defer" ( block | statement ) ;
print_stmt     = "print" "(" [ expr { "," expr } ] ")" ;
verify_stmt    = "verify" expr [ "," STRING ] ;
match_stmt     = "match" expr "{" { match_arm } "}" ;

expr           = or_expr ;
or_expr        = and_expr { "or" and_expr } ;
and_expr       = cmp_expr { "and" cmp_expr } ;
cmp_expr       = add_expr { ( "<" | "<=" | ">" | ">=" | "==" | "!=" ) add_expr } ;
add_expr       = mul_expr { ( "+" | "-" ) mul_expr } ;
mul_expr       = cast_expr { ( "*" | "/" | "%" ) cast_expr } ;
cast_expr      = unary { "as" base_type } ;
unary          = ( "-" | "+" | "not" ) unary | postfix ;
postfix        = primary { "." IDENT | "[" expr "]" | "?" } ;
primary        = INT | FLOAT | STRING | "true" | "false"
               | IDENT | call | struct_init | array_literal
               | "match" expr "{" { match_arm } "}"
               | "(" expr ")" ;

call           = IDENT [ "<" type { "," type } ">" ] "(" [ args ] ")" ;
args           = expr { "," expr } ;
struct_init    = IDENT [ "<" type { "," type } ">" ] "{"
                     { IDENT ":" expr [ "," ] }
                 "}" ;
array_literal  = "[" [ expr { "," expr } ] "]" ;
match_arm      = pattern [ "if" expr ] "=>" ( expr | block ) ;
pattern        = "_" | IDENT | INT | FLOAT | STRING | "true" | "false" ;
```

> Not: `match` guard'ı `if` anahtar kelimesiyle yazılır: `n if n > 10 => ...`.

---

## 19. Bilinen sınırlamalar (v0.5)

1. **Geçici string'ler:** atama yapılmayan `print(f(x))` benzeri ifadelerde üretilen string'ler bırakılmaz.
2. **Çapraz derleme:** `--target` harici sysroot/WASI SDK gerektirir; deneyseldir.
3. **Registry:** merkezi paket havuzu yok; registry bağımlılığında `install` açık hata verir.
4. **Dinamik bağlantı:** üretilen ELF `glibc`, `libssl`, `libcrypto`, `libz`, `libpthread`'e dinamik bağlıdır.
5. **Self-hosted derleyici:** `bin/axiomc` Python sürücüsünün tam eşi değildir (sözleşme denetimi ve SMT yok).
6. **`enum`, `trait`, closure, `try/except`** dilde yoktur.
7. **`match` guard** sözdizimi `when` değil `if`'tir (`n if n > 0 => ...`).
