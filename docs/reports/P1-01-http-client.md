# P1-01 — HTTP/1.1 İstemcisi (Uygulama Raporu)

**Tarih:** 7 Kasım 2026
**Görev:** `TODO.md` → P1-01
**Durum:** ✅ Tamamlandı

---

## 1. Sorun

`std/net/http.ax` üç yerde yetersizdi:

| Sorun | Etki |
|---|---|
| `tcp_recv` **tek** `recv()` çağrısı | 64 KB'tan büyük yanıtlar sessizce kesiliyordu |
| `Transfer-Encoding: chunked` yok | Çoğu modern sunucu chunked döner → bozuk gövde |
| Yönlendirme takibi yok | 301/302 → boş yanıt |
| Zaman aşımı ayarlanamıyor | Asılı bağlantıda 2 sn sabit (soket düzeyi) |

Ayrıca `Content-Length` dikkate alınmıyor, gövde "geri kalan her şey" sayılıyordu.

---

## 2. Uygulama

### Runtime (C)

| Fonksiyon | Ne yapar |
|---|---|
| `tcp_recv_all(fd, max)` | EOF veya `max`'a kadar **döngüyle** okur, tamponu geometrik büyütür |
| `tcp_set_timeout(fd, ms)` | `SO_RCVTIMEO` + `SO_SNDTIMEO` |
| `http_header_value(resp, name)` | Başlıkları (gövde ayırıcısından önce) **harf duyarsız** arar |
| `http_chunked_decode(body)` | Chunk boyutu (hex), chunk extension (`;ext=1`), son `0\r\n\r\n` |

### stdlib (Axiom)

```axiom
struct HttpResponse { status, location, content_type, body, redirects }
struct FetchResult  { is_ok, value: HttpResponse, error }   // `?` uyumlu
```

| Fonksiyon | Not |
|---|---|
| `_read_response(fd, max)` | Content-Length varsa o kadar; chunked ise decode; yoksa EOF |
| `http_once(host, port, method, path, timeout)` | Tek istek, yönlendirme yok |
| `http_request(...)` | Yönlendirme takibi (max 5), döngü tespiti, yapısal sonuç |
| `http_get` / `http_get_result` | Geriye dönük uyum |

Yönlendirme: göreli `/path` ve mutlak `http://host:port/path` destekli;
`https://` yönlendirmesi açık hata verir (TLS istemcisi ayrı modülde).

---

## 3. Doğrulama

Gerçek TCP sunucusuna karşı (`tests/test_http_client.py`, `socketserver`):

| Senaryo | Sonuç |
|---|---|
| Basit GET | `status: 200`, `body: ok` |
| `Transfer-Encoding: chunked` | `hello chunked world` |
| 302 → `/final` | `final-target`, `redirects: 1` |
| 300 KB yanıt | `big: 300000` (tek recv ile kesilirdi) |
| Kendine yönlendirme | `loop_ok: false` (döngü tespiti) |
| Boş host | `bos host` |
| Port 0 | `gecersiz port: 0` |
| Chunk decoder kenar durumları | `hello`, `abc`, `""`(bozuk), `""`(boş) |
| Başlık arama (harf duyarsız) | `42`, `abc`, `""` |

```
$ python3 -m pytest -q --no-header
710 passed in 467.25s
```

C ve LLVM çıktıları **birebir aynı**.

---

## 4. Değişen dosyalar

| Dosya | Değişiklik |
|---|---|
| `axiom/runtime.h` | `tcp_recv_all`, `tcp_set_timeout`, `http_header_value`, `http_chunked_decode` |
| `axiom/checker.py` | 4 yeni builtin |
| `axiom/codegen_c.py`, `axiom/codegen_llvm.py` | eşlemeler + declare |
| `std/net/http.ax` | yeniden yazıldı (`HttpResponse`, `FetchResult`, redirect, chunked) |
| `tests/test_http_client.py` | **Yeni** — 4 test |
| `TODO.md`, `CHANGELOG.md`, `README.md` | P1-01 kapandı, test 710 |

---

## 5. Sıradaki

**P2-01 — Registry v1** (`[!]` engelleyici). JSON ve HTTP tamam; `axiom-scan`
artık yazılabilir. Ancak ekosistem için registry ön koşul.

Alternatif sıra: **P1-03 `axiom-scan` v0.1** — JSON + HTTP hazır olduğu için
killer app'i şimdi çıkarmak, registry'den daha hızlı somut değer üretir.
