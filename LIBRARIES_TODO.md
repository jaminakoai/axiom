# Axiom (λx) — Standart Kütüphane Yol Haritası (5'erli Paketler)

> Bu belge, Axiom sistem programlama ve güvenlik dilini Python ve Rust ekosistem seviyesine taşımak için geliştirilecek tüm kütüphanelerin 5'erli aşamalar halindeki planını içerir.

---

## 📦 PAKET 1: Ağ, Veri ve Güvenlik Çekirdeği (TAMAMLANDI)
- [x] **1. `std:encoding:base64`**: Standart ve URL-safe Base64 encode / decode (Web exploitleri, token ve HTTP auth başlıkları).
- [x] **2. `std:encoding:hex`**: Hexadecimal encode/decode ve güvenlik uzmanları için renkli hex dump aracı.
- [x] **3. `std:crypto:hash`**: SHA-256, SHA-1, MD5 ve HMAC imzalama motoru (Veri bütünlüğü, parola ve token hashleme).
- [x] **4. `std:net:url`**: RFC 3986 uyumlu URL ayrıştırıcı (scheme, user, host, port, path, query, fragment).
- [x] **5. `std:encoding:json`**: JSON ayrıştırıcı (parser) ve üreteci (serializer) — REST API ve güvenlik yapılandırmaları.

---

## 📦 PAKET 2: İleri Ağ ve İletişim Protokolleri (TAMAMLANDI)
- [x] **6. `std:net:dns`**: Yerel DNS çözümleyici (A, AAAA, CNAME sorguları, PTR ters sorgu ve hedef keşfi).
- [x] **7. `std:net:udp`**: UDP soket API'si (`udp_bind`, `udp_send`, `udp_recv`, `udp_close` — DNS, SNMP, NTP tarama).
- [x] **8. `std:net:http_server`**: Hafif yerel HTTP sunucusu (Webhook dinleyici, SSRF / OOB callback ve PoC sunucusu).
- [x] **9. `std:crypto:tls`**: OpenSSL / TLS güvenli soket istemcisi (HTTPS bağlantıları ve sertifika analizi).
- [x] **10. `std:net:websocket`**: RFC 6455 WebSocket istemcisi (Gerçek zamanlı web protokolleri ve socket enjeksiyonları).

---

## 📦 PAKET 3: Sistem, İkili Veri ve Dosya İşleme (TAMAMLANDI)
- [x] **11. `std:io:binary`**: İkili veri (Byte Buffer) okuma/yazma, Big/Little Endian pack/unpack (Binary exploit payloadları).
- [x] **12. `std:os:process`**: Gelişmiş alt süreç yönetimi (`exec_pipe`, `stdin/stdout/stderr` yakalama, PID, sinyal yönetimi).
- [x] **13. `std:compress:zlib`**: Gzip ve Deflate sıkıştırma/açma motoru (HTTP gzip yanıtları ve arşivler).
- [x] **14. `std:text:regex`**: Düzenli ifadeler motoru (Regex desen arama, regex replace ve log analitiği).
- [x] **15. `std:collections:map`**: Yüksek hızlı Hash Map / Sözlük veri yapısı (`Map[K, V]`).

---

## 📦 PAKET 4: Güvenlik, Fuzzing ve Veri Yapıları (TAMAMLANDI)
- [x] **16. `std:collections:queue`**: İş parçacığı güvenli (thread-safe) kuyruk (Worker pool ve paralel tarayıcılar için).
- [x] **17. `std:security:fuzzer`**: Wordlist okuyucu, payload permütasyon motoru ve fuzzing kuralları.
- [x] **18. `std:time:date`**: Tarih, saat, ISO 8601 biçimlendirici ve mikrosaniyelik epoch dönüştürücü.
- [x] **19. `std:io:csv`**: CSV ve TSV okuyucu / yazıcı (Güvenlik tarama sonuçlarını raporlama).
- [x] **20. `std:cli:args`**: Gelişmiş CLI argüman ve bayrak ayrıştırıcısı (`--target`, `-p`, `--verbose`).

---

## 📦 PAKET 5: İleri Kriptografi ve Raporlama (TAMAMLANDI)
- [x] **21. `std:crypto:aes`**: AES-128/256 (CBC/GCM) simetrik şifreleme ve deşifreleme.
- [x] **22. `std:security:jwt`**: JSON Web Token ayrıştırma, imza denetimi ve payload okuma.
- [x] **23. `std:encoding:html`**: HTML Entity encode/decode ve XSS filtreleme yardımcıları.
- [x] **24. `std:log:logger`**: Renkli ve seviyeli loglama motoru (`DEBUG`, `INFO`, `WARN`, `ERROR`).
- [x] **25. `std:net:raw_socket`**: Ham IP/ICMP paketleri (ICMP Echo Ping sweep, SYN taraması).
