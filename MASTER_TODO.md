# Axiom (λx) — Master Yol Haritası (Red/Blue Team, AI ve Self-Hosted Compiler)

> **Misyon:** Red Team (ofansif siber güvenlik), Blue Team (savunma/DFIR), Yapay Zeka (AI/ML tensör hesaplama) ve modern Web/Sistem geliştirmede Python'ın kolaylığı ile C/Rust'ın çıplak metal performansını sunan 1 numaralı tercih edilen sistem programlama dili olmak.

---

## 📌 FAZ 1: Self-Hosted Derleyici (ÖNCELİKLİ AŞAMA — %100 TAMAMLANDI)
*Axiom derleyicisinin Python bağımlılığını tamamen ortadan kaldırarak Axiom dilinin kendisiyle yazılması ve bağımsız yerel binary (`bin/axiomc`) olarak derlenmesi.*
- [x] **1.1. `compiler/tokens.ax`**: Token veri modeli, anahtar kelime ve sembol sabitleri.
- [x] **1.2. `compiler/lexer.ax`**: Axiom ile yazılmış, UTF-8 uyumlu, satır/sütun koordinatlı sözcüksel analiz motoru.
- [x] **1.3. `compiler/ast.ax`**: Düğüm tipleri, struct/array, sözleşmeler (`requires`/`ensures`) ve fonksiyon AST yapıları.
- [x] **1.4. `compiler/parser.ax`**: Recursive Descent ayrıştırıcı, operatör öncelik hiyerarşisi ve sözdizim hata raporlayıcı.
- [x] **1.5. `compiler/codegen.ax`**: Axiom AST'den doğrudan ultra-optimize C99 / LLVM makine kodu üreten motor.
- [x] **1.6. `compiler/main.ax`**: Derleyici CLI sürücüsü (`axiomc build`, `axiomc run`, `axiomc emit-c`).
- [x] **1.7. Bağımsız Binary Derlemesi**: `axiom build compiler/main.ax -o bin/axiomc` ile saf ELF 64-bit ikili derleyicinin üretilmesi ve Python gerektirmeden `.ax` dosyalarını derlediğinin kanıtlanması (Tüm 335 test %100 geçti!).

---

## 📌 FAZ 2: Red Team & Ofansif Siber Güvenlik Altyapısı (%100 TAMAMLANDI)
*Sızma testi uzmanları ve exploit geliştiricileri için sıfır ek yüklü, tespit edilmesi zor ofansif araçlar.*
- [x] **2.1. `std:security:shellcode`**: Bellekte kabuk kodu çalıştırma, RWX bellek tahsisi (`mprotect`/`mmap`), thread hijacking ve process injection yardımcıları.
- [x] **2.2. `std:net:packet_crafter`**: Ham IP/TCP/UDP/ICMP başlıkları oluşturma, SYN Flood / Port Knocking, sahte kaynak IP (IP spoofing).
- [x] **2.3. `std:security:evasion`**: Anti-debugging (ptrace denetimi), sanal makine / sandbox tespiti ve dinamik API hashing (IAT gizleme).
- [x] **2.4. `std:net:c2`**: Şifreli C2 (Command & Control) ajan protokolü (AES-256-GCM + HTTPS + WebSocket beaconing).
- [x] **2.5. `std:security:memdump`**: Süreç bellek alanı tarama (Procfs /proc/pid/mem), string ayıklama ve parola/token arama.

---

## 📌 FAZ 3: Blue Team & Defansif Güvenlik / DFIR Altyapısı (%100 TAMAMLANDI)
*SOC analistleri, olay müdahale (IR) ve tehdit avcıları için yüksek hızlı gerçek zamanlı analiz motorları.*
- [x] **3.1. `std:security:yara`**: Bellek ve dosya desen tarayıcısı (Hex, ASCII, Regex ve Boolean kuralları).
- [x] **3.2. `std:net:pcap`**: Canlı ağ dinleme (Promiscuous mode sniffer) ve PCAP dosya ayrıştırma / derin paket inceleme (DPI).
- [x] **3.3. `std:security:sigma`**: Log ve telemetri kural motoru (Syslog, Auth.log, Nginx/Apache log analizi).
- [x] **3.4. `std:os:forensics`**: Linux adli bilişim araçları (Açık soketler `lsof`, loaded kernel modules, cron & persistence avcısı).
- [x] **3.5. `std:security:integrity`**: Dosya ve bellek bütünlük denetleyicisi (FIM - File Integrity Monitoring, hash diffing).

---

## 📌 FAZ 4: Yapay Zeka (AI / ML) & Heterojen Hesaplama Çekirdeği (%100 TAMAMLANDI)
*Python'ın NumPy/PyTorch hantallığını kaldıran, sıfır ek yüklü tensör ve derin öğrenme altyapısı.*
- [x] **4.1. `std:ai:tensor`**: Çok boyutlu tensör (ND-Array) veri yapısı, bellek stride ve şekil (shape) manipülasyonu.
- [x] **4.2. `std:ai:linalg`**: AVX2 SIMD hızlandırmalı matris çarpımı (GEMM), konvolüsyon ve vektör nokta çarpımı.
- [x] **4.3. `std:ai:autograd`**: Ters yönlü otomatik türev alma motoru (Computational graph & backpropagation).
- [x] **4.4. `std:ai:nn`**: Temel sinir ağı katmanları (Dense/Linear, ReLU, Sigmoid, Softmax, Cross-Entropy Loss).
- [x] **4.5. `std:ai:inference`**: ONNX / saf ağırlık dosya formatı okuyucu ve ultra-hızlı CPU/SIMD model koşturucu.

---

## 📌 FAZ 5: Modern Web & Asenkron API Motoru (%100 TAMAMLANDI)
*Go/Node.js performansını aşan yüksek eşzamanlılıklı web mimarisi.*
- [x] **5.1. `std:web:router`**: Yüksek hızlı Radix-Tree / Trie tabanlı HTTP yönlendirici (URL pattern parametreleri `/api/:id`).
- [x] **5.2. `std:web:app`**: Middleware destekli web framework (CORS, Rate-Limiting, Auth Guard, JSON Binding).
- [x] **5.3. `std:web:template`**: Güvenli, XSS korumalı HTML şablon motoru.
- [x] **5.4. `std:target:wasm`**: WebAssembly (WASM) doğrudan derleme desteği (Tarayıcıda Axiom koşturma).
