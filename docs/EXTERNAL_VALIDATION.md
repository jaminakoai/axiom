# Axiom dış kullanıcı denemesi / External user trial

Bu rehber G3 doğrulaması içindir. İlk akış yaklaşık beş dakikalık kurulum ve
zararsız sentetik hedefle bir duman testidir. Ardından bağımsız testçi, yalnızca
kullanma yetkisi olduğu kendi dosya veya PCAP'inde gerçek iş akışını dener.

This guide supports roadmap gate G3. The first flow is a roughly five-minute
setup and smoke test against a harmless synthetic target. An independent tester
then tries a real workflow using only a file or PCAP they are authorized to use.

## Ön koşullar / Prerequisites

- Debian/Ubuntu tabanlı 64-bit Linux; destek matrisi: Python 3.10+, `clang`,
  OpenSSL ve zlib geliştirme başlıkları.
- Git ve Python venv/pip.
- Kendi tarama kuralınız ve tarama yetkinizin olduğu bir dosya/PCAP.

On Debian/Ubuntu, install the system tools once:

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip clang libssl-dev zlib1g-dev
```

## 5 dakikalık kurulum ve zararsız duman testi / Five-minute setup and smoke test

```bash
git clone https://github.com/jaminakoai/axiom.git
cd axiom
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
axiom --version
axiom build examples/21_axiom_scan.ax -o /tmp/axiom-scan
```

Create a local test rule and target. The marker is not a malware signature:

```bash
cat > /tmp/axiom-external.yar <<'EOF'
rule Axiom_External_Validation {
  strings:
    $marker = "AXIOM_EXTERNAL_VALIDATION_SENTINEL_v1" ascii
  condition:
    $marker
}
EOF
printf '%s\n' 'Axiom external validation sentinel: AXIOM_EXTERNAL_VALIDATION_SENTINEL_v1' > /tmp/axiom-external.txt

/tmp/axiom-scan rules /tmp/axiom-external.yar
/tmp/axiom-scan scan /tmp/axiom-external.txt --rules /tmp/axiom-external.yar
```

Expected: `rules` returns `"ok":true` and `"rules":1`; `scan` returns
`"ok":true`, `"match_count":1`, the rule name
`Axiom_External_Validation`, and a 64-character `target_sha256`.

The same clean-clone flow was checked on Linux x86_64 (Kali 2026.3), Python
3.13.14, from commit `79e27c5`. The synthetic smoke scan returned one match at
offset 36, length 37, and SHA-256
`1672850fcdc2a61c372188931ea164f8df197a0f87df96e0dd211a4ff02ed405`.
This proves the install/build/smoke path; it does **not** count as independent
user validation.

## Yetkili girdinizle gerçek deneme / Try your authorized input

Use your own YARA-subset rule file and a local file:

```bash
/tmp/axiom-scan rules /absolute/path/to/your-rules.yar
/tmp/axiom-scan scan /absolute/path/to/authorized-file --rules /absolute/path/to/your-rules.yar
```

For a PCAP, each packet is scanned separately; TCP stream reassembly is not
implemented:

```bash
/tmp/axiom-scan pcap /absolute/path/to/authorized-capture.pcap --rules /absolute/path/to/your-rules.yar
```

If the command rejects a rule, keep the exact error text. The supported YARA
subset and explicit limitations are listed in the bilingual README feature
matrix. Do not treat a successful run as proof that Axiom implements all of
YARA or detects malware reliably.

## Geri bildirim / Feedback template

Share this text with the project maintainer. Do not attach or paste the file,
PCAP, packet contents, credentials, or personal data. Hashes and a redacted JSON
summary are optional and should be shared only if permitted by your policy.

```text
OS/version and architecture:
Axiom commit:
Input type (file / PCAP):
Was this input authorized for the test? (yes/no):
Rule construct or use case (redact rule names if needed):
Command (redact local paths if needed):
Expected behavior:
Actual result/error and exit code:
match_count / relevant JSON fields:
SHA-256 (only if allowed):
Can the maintainer use this report in a public issue? (yes/no):
```

Only record findings after the tester provides them. A report may be documented
without collecting or storing the user's input. Add each confirmed finding to
`TODO.md` with a sanitized reproduction and severity.

---

Bu sayfa Türkçe ve İngilizce ortak test akışıdır. / This page is the shared
Turkish/English test procedure.
