# Axiom dış kullanıcı denemesi / External user trial

Bu rehber G3 doğrulaması içindir. Önce zararsız, sentetik bir hedefle kurulum
ve duman testi yapın; ardından yalnızca kullanma yetkiniz olan bir dosya veya
PCAP üzerinde kendi gerçek iş akışınızı deneyin. Beş dakikalık tahmin, Debian/
Ubuntu sistem araçlarının önceden kurulu olduğunu varsayar.

This guide supports roadmap gate G3. First install and run a smoke test against
a harmless synthetic target. Then try your real workflow only on a file or PCAP
you are authorized to use. The five-minute estimate assumes the Debian/Ubuntu
system tools are already installed.

## Ön koşullar / Prerequisites

- Debian/Ubuntu tabanlı 64-bit Linux; Python 3.10+, Git, venv/pip, `clang`,
  OpenSSL ve zlib geliştirme başlıkları gerekir.
- Gerçek deneme için kendi YARA-alt-kümesi kuralınız ve kullanma yetkinizin
  olduğu bir dosya veya PCAP gerekir.

- 64-bit Debian/Ubuntu-based Linux with Python 3.10+, Git, venv/pip, `clang`,
  and OpenSSL and zlib development headers.
- For the real trial, bring your own YARA-subset rule and a file or PCAP you
  are authorized to use.

Sistem araçlarını bir kez kurun / Install the system tools once:

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip clang libssl-dev zlib1g-dev
```

## 5 dakikalık kurulum ve zararsız duman testi / Five-minute setup and smoke test

Depoyu klonlayın, Python ortamını kurun ve `axiom-scan` örneğini derleyin.
Gerçekten hangi kodu denediğinizi kaydetmek için commit kimliğini alın.

Clone the repository, install its Python environment, and build the
`axiom-scan` example. Record the commit so the tested code can be identified.

```bash
git clone https://github.com/jaminakoai/axiom.git
cd axiom
git rev-parse HEAD
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
axiom --version
axiom build examples/21_axiom_scan.ax -o /tmp/axiom-scan
```

Aşağıdaki kural ve hedef yalnızca yerel, zararsız bir işaretleyici kullanır; bir
zararlı yazılım imzası değildir.

The following rule and target use only a harmless local marker; it is not a
malware signature.

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

Beklenen: `rules` çıktısında `"ok":true` ve `"rules":1`; `scan` çıktısında
`"ok":true`, `"match_count":1`, `Axiom_External_Validation` kuralı ve 64
karakterli `target_sha256` alanı bulunur. Eşleşme ofseti 36, uzunluğu 37 olur.

Expected: `rules` returns `"ok":true` and `"rules":1`; `scan` returns
`"ok":true`, `"match_count":1`, the `Axiom_External_Validation` rule, and a
64-character `target_sha256`. The match offset is 36 and its length is 37.

Bu akışın temiz klondan kurulumu ve sentetik taraması Linux x86_64 üzerinde
doğrulanmıştır. Ayrıntılı commit, süre ve çıktı kanıtı aşağıdaki G3 raporundadır.
Bu kanıt kurulum/duman testini gösterir; bağımsız kullanıcı doğrulaması sayılmaz.

The clean-clone install and synthetic scan have been verified on Linux x86_64.
The G3 report below records the commit, duration, and output. This proves the
setup/smoke path only; it does not count as independent user validation.

[G3 onboarding evidence / G3 başlangıç kanıtı](reports/2026-11-16-g3-external-onboarding.md)

## Yetkili girdinizle gerçek deneme / Try your authorized input

Kendi YARA-alt-kümesi kural dosyanızı önce doğrulayın, sonra yetkili olduğunuz
yerel dosyayı tarayın. Yerel yolları başkasına gönderirken gizli olabilecek
klasör veya dosya adlarını maskeleyin.

Validate your YARA-subset rule file, then scan a local file you are authorized
to use. Redact directory or file names that could reveal private information
before sharing a command.

```bash
/tmp/axiom-scan rules /absolute/path/to/your-rules.yar
/tmp/axiom-scan scan /absolute/path/to/authorized-file --rules /absolute/path/to/your-rules.yar
```

PCAP taramasında her paket ayrı taranır; TCP akışı yeniden birleştirilmez.

For PCAP scans, each packet is scanned separately; TCP streams are not
reassembled.

```bash
/tmp/axiom-scan pcap /absolute/path/to/authorized-capture.pcap --rules /absolute/path/to/your-rules.yar
```

Bir kural reddedilirse hata metnini kaydedin. Desteklenen YARA alt kümesi ve
sınırlar README'deki TR/EN özellik tablosunda açıklanır. Başarılı sonuç, Axiom'ın
tüm YARA'yı uyguladığını veya zararlı yazılımı güvenilir biçimde tespit ettiğini
kanıtlamaz.

If a rule is rejected, record the error text. The Turkish and English README
feature matrix lists the supported YARA subset and its limits. A successful run
does not prove full YARA compatibility or reliable malware detection.

## Geri bildirim gönderme / How to submit feedback

Güvenlik açığı şüphesi olmayan, kamuya açık paylaşılmasına izin verdiğiniz
kullanılabilirlik geri bildirimini [GitHub Issues](https://github.com/jaminakoai/axiom/issues/new)
üzerinden **yalnızca aşağıdaki temizlenmiş şablonla** gönderin. Ham dosya/PCAP,
paket içeriği, kural metni, kimlik bilgisi, kişisel veri, hassas dosya adı veya
yerel tam yolu issue'ya eklemeyin. SHA-256 da dosyanın kimliğini açığa
çıkarabilir; varsayılan olarak boş bırakın ve ancak paylaşmaya yetkiniz varsa
ekleyin.

For usability feedback that is not a suspected security vulnerability and is
approved for public sharing, use [GitHub Issues](https://github.com/jaminakoai/axiom/issues/new)
and include **only the sanitized template below**. Never attach a raw file/PCAP,
packet contents, rule text, credentials, personal data, sensitive filenames, or
absolute local paths. A SHA-256 can identify a file; leave it blank by default
and include it only when you are authorized to share it.

Geri bildiriminizin kamuya açık kullanılmasına izin vermiyorsanız public issue
açmayın ve özel bilgileri göndermeyin; önce proje sorumlusuyla uygun özel kanalı
kararlaştırın. Güvenlik açığı veya güvenlik etkisi olabilecek bir bulgu için
**asla public issue açmayın**; [SECURITY.md](../SECURITY.md) içindeki özel
bildirim adımlarını izleyin.

If you do not consent to public use of your feedback, do not open a public issue
or send private details; first agree on an appropriate private channel with the
maintainer. For a suspected vulnerability or security-impacting finding, **do
not open a public issue**; follow the private reporting steps in
[SECURITY.md](../SECURITY.md).

```text
İşletim sistemi/sürümü ve mimari / OS/version and architecture:
Axiom commit (git rev-parse HEAD):
Girdi türü (dosya/PCAP) / Input type (file/PCAP):
Girdi bu deneme için kullanma yetkiniz dahilinde miydi? / Were you authorized to use it? (yes/no):
Kural yapısı veya kullanım senaryosu (gerekirse adları maskeleyin) / Rule construct or use case (redact names if needed):
Komut (tam yolları ve gizli değerleri maskeleyin) / Command (redact full paths and secrets):
Beklenen davranış / Expected behavior:
Gerçek sonuç/hata ve çıkış kodu / Actual result/error and exit code:
match_count ve ilgili JSON alanları / match_count and relevant JSON fields:
SHA-256 (varsayılan boş; yalnızca paylaşma izni varsa / blank by default; only if authorized):
Kamuya açık issue olarak paylaşılmasına izin var mı? / Is public issue use permitted? (yes/no):
```

Bulgu yalnızca testçi geri bildirim verdikten sonra kaydedilir. Rapor, kullanıcı
girdisini almadan veya saklamadan; temizlenmiş yeniden üretim adımı ve önem
derecesiyle `TODO.md`'ye eklenebilir.

Record a finding only after the tester submits feedback. Add a sanitized
reproduction and severity to `TODO.md` without receiving or storing the user's
input.

---

Bu rehberin yönergeleri ve geri bildirim alanları Türkçe ve İngilizce sunulur.
/ The instructions and feedback fields in this guide are provided in Turkish
and English.
