# P1-04 + P2-02 — Kural Motoru Kapsamı ve Namespace

**Tarih:** 8 Kasım 2026
**Görevler:** `TODO.md` → P1-04, P2-02
**Durum:** ✅ ikisi de tamamlandı

---

## 1. P1-04 — YARA/Sigma kapsamı

Ajan raporu 14 fonksiyonun testsiz olduğunu bildirmişti. Hepsi denendi —
**çoğu doğru çalışıyordu, iki gerçek hata çıktı**.

### 1.1 Gerçek hata — Sigma fail-open

```axiom
sigma_eval_op("a", "contians", "a")   // yazım hatası
```

| Önce | Sonra |
|---|---|
| `true` (contains'e düşüyordu) | **`false`** |

Güvenlik motorunda bilinmeyen operatör sessizce eşleşmeye yol açmamalı.
Artık **fail-closed**.

### 1.2 Gerçek hata — `sigma_parse_syslog` yanlış servis

```
"Jan  1 00:00:00 host sshd[123]: Failed password..."
```

| Önce | Sonra |
|---|---|
| `service = "1 00:00:00 host sshd[123]"` | `"sshd[123]"` |

Neden: `str_index_of(header, " ")` **ilk** boşluğu buluyordu. `_sigma_last_index_of`
eklendi.

### 1.3 Doğrulanan davranış (kilitlendi)

| Alan | Fonksiyonlar |
|---|---|
| YARA kural | `yara_rule_set_offset_bounds`, `set_at_offset` |
| YARA tarama | `yara_scan_single_pattern` (str/hex/regex + ofset kısıtı), `yara_scan_buf` |
| YARA set | `yara_ruleset_has_match`, `count_matches` |
| YARA legacy | `yara_scan_buffer`, `yara_scan_regex`, `yara_scan_hex` |
| Sigma op | `sigma_eval_op` (5 operatör + bilinmeyen) |
| Sigma kural | `sigma_rule_set_condition`, `sigma_rule_eval` |
| Sigma parser | `sigma_parse_syslog`, `sigma_parse_auth_log` |
| Sigma motor | `sigma_engine_eval_raw`, `sigma_engine_has_alert` |
| Sigma legacy | `sigma_match_rule`, `sigma_count_matches` |

`tests/test_yara_sigma_coverage.py` — **13 test**, C + LLVM paritesi.

### 1.4 Belgelenen davranış (hata değil)

`sigma_engine_eval_raw(engine, line, "syslog")` default kurallarla **0** döner:
varsayılan SSH kuralı `log_type = "auth"`. Log türü yalıtımı **doğru** çalışıyor
ve testle sabitlendi.

---

## 2. P2-02 — Namespace

Düz isim alanı 250 pakette çakışır. `@kapsam/paket` desteği eklendi.

| Girdi | Depo dizini |
|---|---|
| `plain` | `plain` |
| `@acme/json` | `@acme__json` |

- `import "@acme/util"` → `<deps>/@acme__util/src/lib.ax`
- Aynı adlı iki paket (`@acme/json`, `@other/json`) çakışmadan kurulur
- Geçersiz adlar reddedilir: `../evil`, `a/b/c`, `@u/../x`, boşluk, `\`

**Path traversal koruması:** `is_valid_dep_name` + `dep_dir_name`; resolver de
aynı doğrulamayı yapar.

Testler: `tests/test_registry.py` +5 test (toplam 43).

---

## 3. Durum

```bash
781 passed in 489.22s
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **781** (+18) |
| LLVM örnekleri | 20/20 |
| `bin/axiomc` bootstrap | ✅ |
| `make fmt-check` | ✅ |

---

## 4. Sıradaki

| # | İş | Neden |
|---|---|---|
| 1 | **P2-03** `///` doc comment + `axiom doc` | Paket yazarı API dokümanı olmadan gelmez |
| 2 | **P2-04** İngilizce doküman | Global erişim |
| 3 | **P2-05** tam LSP (references/rename/format) | Editör deneyimi |
| 4 | **P1-05/06** ofansif sertleştirme + DFIR akışı | Faz 1 kapısı |
