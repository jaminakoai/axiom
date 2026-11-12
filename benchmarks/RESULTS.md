## String Sahiplik Modeli (P2-17b) — 2026-11-10

`benchmarks/str_ownership_bench.c` ile olculdu (clang -O2, tek thread).
Once: global hash tablosu (ptr -> refs, 40 bayt/kayit).
Sonra: intrusive header (refcount verinin hemen onunde, 32 bayt).

| Senaryo | Once | Sonra | Degisim |
|---|---:|---:|---:|
| `int_to_str` 300k (uret+birak) | 31.4 ms | **26.8 ms** | −15% |
| Kisa omurlu ham wrap 300k | 30.7 ms | 30.7 ms | ~0 |
| 150k canli string olustur | 31.9 ms | **16.5 ms** | **−48%** |
| 150k canli string birak | 9.9 ms | **4.0 ms** | **−60%** |
| Takip tablosu bellegi (150k) | 10.0 MB | **0 MB** | **−10 MB** |

Ek kazanc: `axiom run` ciktisi ASan altinda **21/21 temiz**
(once 18/21; 10_packet1'deki 89 B sizinti ve redteam'deki SEGV kapandi).


# Axiom Benchmark Sonuçları

- **Tarih:** 2026-11-06 18:05 UTC
- **Platform:** Linux-7.0.12+kali-amd64-x86_64-with-glibc2.42
- **CPU:** Intel(R) Core(TM) i3-8100 CPU @ 3.60GHz
- **Derleyici:** Debian clang version 21.1.8 (7+b3)
- **Python:** 3.13.14
- **Yöntem:** her dil için en iyi 3 koşu (wall-clock); Axiom ve C `-O3`

| İş | Axiom (s) | C -O3 (s) | Python (s) | Axiom/C | Python/Axiom |
|---|---:|---:|---:|---:|---:|
| Özyinelemeli Fibonacci (n=30) | 0.0050 | 0.0033 | 0.1476 | 1.51× | 29.7× |
| String birleştirme (20,000 adım) | 0.0031 | 0.0007 | 0.0201 | 4.58× | 6.6× |
| Dizi büyütme (100,000 eleman) | 0.0018 | 0.0011 | 0.0228 | 1.67× | 12.4× |
| Base64 encode (20,000 çağrı) | 0.0041 | 0.0007 | 0.0277 | 6.34× | 6.7× |
| Matris çarpımı (64×64) | 0.0015 | 0.0007 | 0.0441 | 2.18× | 29.4× |

**Notlar**
- Axiom/C oranı 1'e yaklaştıkça C ile eşdeğer; >2 ise runtime ek yükü var.
- String benchmark'ında Axiom'un sahiplik/refcount yolu, C'nin ham `realloc` yoluna göre ek maliyet içerir.
- Python/Axiom oranı, Axiom'un Python'a göre hız kazancını gösterir.

> Ölçümler tek makinede, tek oturumda alınmıştır; mutlak değil göreli karşılaştırma içindir.
