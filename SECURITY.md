# Güvenlik Politikası

## Desteklenen sürümler

Axiom **alfa** aşamasındadır. Yalnızca en son `0.5.x-alpha` sürümü güvenlik düzeltmeleri alır.

| Sürüm | Destek |
|---|---|
| `0.5.x-alpha` | ✅ |
| `0.4.x` ve öncesi | ❌ |

## Güvenlik açığı bildirme

**Lütfen herkese açık issue açmayın.**

1. E-posta: `security@axiom-lang.org` (PGP anahtarı talep üzerine)
2. Konu başlığı: `[SECURITY] <kısa açıklama>`
3. Şunları ekleyin:
   - Etkilenen sürüm / commit
   - En küçük yeniden üretim (`.ax` dosyası veya komut)
   - Beklenen ve gerçek davranış
   - Etki değerlendirmesi (RCE, bellek bozulması, DoS, bilgi sızıntısı…)

**Yanıt süresi:** 72 saat içinde ilk yanıt, 14 gün içinde düzeltme planı hedeflenir.

## Kapsam

Güvenlik açığı sayılanlar:

- Derleyici veya runtime'da bellek bozulması (OOB, UAF, double-free)
- Komut/shell enjeksiyonu (derleyici araç zinciri dahil)
- Sözleşme doğrulamasının atlatılması (seslilik ihlali)
- TLS/JWT/AES gibi kriptografik yollarda zayıflık
- Paket yöneticisinde tedarik zinciri sorunları (checksum atlatma)
- `--features offensive` izolasyonunun atlatılması

Kapsam dışı:

- Ofansif modüllerin **kendisinin** kötüye kullanımı (bkz. `std/security/*` uyarıları)
- Harici `sysroot`/toolchain gerektiren deneysel hedeflerin çalışmaması
- Belgelenmiş bilinen sınırlamalar (README → “Bilinen Sınırlamalar”)

## Ofansif modüller

`std/security/shellcode.ax`, `std/net/c2.ax`, `std/security/evasion.ax`,
`std/security/memdump.ax`, `std/net/packet_crafter.ax` **yalnızca** `--features offensive`
(veya `AXIOM_FEATURES=offensive`) ile derlenir.

> **YASAL UYARI:** Bu modüller yalnızca yasal izinli ve etik test ortamlarında kullanılmalıdır.
> Yetkisiz sistemlerde kullanımı yasalara aykırıdır. Sorumluluk kullanıcıya aittir.

## Bilinen riskler (alfa)

- İfade içi geçici string'ler sahiplik tablosunda kalabilir (sızıntı, RCE değil).
- `AXIOM_TLS_INSECURE=1` sertifika doğrulamasını kapatır; üretimde kullanılmamalı.
- `os_exec()` kabuk üzerinden çalıştırır; güvenilmeyen girdi için `os_exec_argv` kullanın.
