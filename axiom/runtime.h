/**
 * Axiom Programming Language (λx) - Zero-Cost Native Runtime
 *
 * Taşınabilirlik: platforma özgü her şey `platform.h` içindedir.
 * Bu dosya yalnızca dil semantiği ve kütüphane fonksiyonlarını içerir.
 */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#ifndef AXIOM_RUNTIME_H
#define AXIOM_RUNTIME_H

#include "platform.h"

/* ==== Linux'a özgü çekirdek arayüzleri (yalnızca Katman 3) ==== */
#if defined(AXIOM_OS_LINUX)
#  include <sys/epoll.h>
#  include <sys/un.h>
#  include <sys/wait.h>
#  include <sys/mman.h>
#  include <sys/ptrace.h>
#  include <sys/prctl.h>
#  include <poll.h>
#  include <cpuid.h>
#endif

#if defined(AXIOM_OS_MACOS)
#  include <sys/mman.h>
#  include <sys/wait.h>
#  include <poll.h>
#  include <sys/un.h>
#endif

#if defined(AXIOM_OS_WINDOWS)
#  define AXIOM_NO_EPOLL 1
#endif

/* SIMD başlığı yalnızca x86'da ve derleyici destekliyorsa */
#if defined(__x86_64__) || defined(_M_X64) || defined(__i386__) || defined(_M_IX86) \
    || defined(__aarch64__) || defined(_M_ARM64)
#  if defined(__has_include)
#    if __has_include(<immintrin.h>) && (defined(__x86_64__) || defined(_M_X64) || defined(__i386__) || defined(_M_IX86))
#      include <immintrin.h>
#    endif
#  endif
#endif

/* ==== Katman 4: harici kütüphaneler (opsiyonel) ====
 *
 * Test/doğrulama için kapatılabilir:
 *   -DAXIOM_DISABLE_OPENSSL   -DAXIOM_DISABLE_ZLIB
 * Böylece "OpenSSL'siz yol" (Windows'un kullandığı yol) Linux'ta da
 * ÇALIŞTIRILARAK doğrulanabilir; yalnız derlenerek değil.
 */
#ifndef AXIOM_HAVE_OPENSSL
#define AXIOM_HAVE_OPENSSL 0
#endif
#ifndef AXIOM_HAVE_ZLIB
#define AXIOM_HAVE_ZLIB 0
#endif
#if defined(__has_include)
#  if __has_include(<openssl/evp.h>) && !defined(AXIOM_DISABLE_OPENSSL)
#    include <openssl/evp.h>
#    include <openssl/hmac.h>
#    include <openssl/rand.h>
#    include <openssl/crypto.h>
#    undef AXIOM_HAVE_OPENSSL
#    define AXIOM_HAVE_OPENSSL 1
#  endif
#  if __has_include(<zlib.h>) && !defined(AXIOM_DISABLE_ZLIB)
#    include <zlib.h>
#    undef AXIOM_HAVE_ZLIB
#    define AXIOM_HAVE_ZLIB 1
#  endif
#endif

/* Unicode Character Database tabloları (tools/gen_unicode_tables.py üretir). */
#include "unicode_tables.h"
#include "crypto_portable.h"
#include "regex_portable.h"

/* Runtime fonksiyon gorunurlugu: C backend'de static inline, LLVM koprunde external */
#ifndef AXIOM_RUNTIME_FN
#define AXIOM_RUNTIME_FN static inline
#endif

/* Donanımsal CPUID & AVX2/FMA Özellik Denetimi */
#if defined(__x86_64__) || defined(_M_X64) || defined(__i386__) || defined(_M_IX86)
AXIOM_RUNTIME_FN int axiom_cpu_has_avx2(void) {
    static int cached = -1;
    if (cached != -1) return cached;
    unsigned int eax, ebx, ecx, edx;
    if (ax_os_cpuid(1, 0, &eax, &ebx, &ecx, &edx)) {
        int osxsave = (ecx & (1 << 27)) != 0;
        int avx = (ecx & (1 << 28)) != 0;
        if (osxsave && avx) {
            uint64_t xcr0 = ax_os_read_xcr0();
            if ((xcr0 & 6) == 6) {
                if (ax_os_cpuid(7, 0, &eax, &ebx, &ecx, &edx)) {
                    int avx2 = (ebx & (1 << 5)) != 0;
                    cached = avx2 ? 1 : 0;
                    return cached;
                }
            }
        }
    }
    cached = 0;
    return cached;
}
#else
AXIOM_RUNTIME_FN int axiom_cpu_has_avx2(void) {
    return 0;
}
#endif

/* ANSI Terminal Renkleri */
#define AXIOM_CLR_RED     "\033[1;31m"
#define AXIOM_CLR_GREEN   "\033[1;32m"
#define AXIOM_CLR_YELLOW  "\033[1;33m"
#define AXIOM_CLR_CYAN    "\033[1;36m"
#define AXIOM_CLR_RESET   "\033[0m"

#ifndef AXIOM_RUNTIME_FN
#define AXIOM_RUNTIME_FN static inline
#endif

/* Axiom Mantıksal Doğrulama ve Sözleşme İhlal İşleyicisi */
AXIOM_RUNTIME_FN void axiom_contract_fail(const char* kind, const char* expr_str, const char* func_name, int line, const char* custom_msg) {
    fprintf(stderr, "\n" AXIOM_CLR_RED "[AXIOM GUVENLIK IHLALI] %s Basarisiz Oldu!" AXIOM_CLR_RESET "\n", kind);
    fprintf(stderr, "  Fonksiyon   : " AXIOM_CLR_CYAN "%s" AXIOM_CLR_RESET "\n", func_name);
    fprintf(stderr, "  Satir       : %d\n", line);
    fprintf(stderr, "  Sözleşme    : " AXIOM_CLR_YELLOW "%s" AXIOM_CLR_RESET "\n", expr_str);
    if (custom_msg && strlen(custom_msg) > 0) {
        fprintf(stderr, "  Detay       : %s\n", custom_msg);
    }
    fprintf(stderr, AXIOM_CLR_RED "Program mantık bütünlüğü ve güvenlik gerekçesiyle durduruldu." AXIOM_CLR_RESET "\n\n");
    exit(101);
}

/* Tip Tanımları */
#ifndef ax_typeof
#define ax_typeof(x) __typeof__(x)
#endif
typedef int64_t  ax_int;
typedef double   ax_float;
typedef bool     ax_bool;
typedef const char* ax_str;

/* Standart Dizi (Array) Tipleri */
typedef struct {
    ax_int length;
    ax_int capacity;
    ax_int* data;
} ax_array_int;

typedef struct {
    ax_int length;
    ax_int capacity;
    ax_float* data;
} ax_array_float;

typedef struct {
    ax_int length;
    ax_int capacity;
    ax_bool* data;
} ax_array_bool;

typedef struct {
    ax_int length;
    ax_int capacity;
    ax_str* data;
} ax_array_str;

#define axiom_len(arr) ((arr).length)

/* Self-hosted derleyici `len(x)` cagrilarinda x'in tipini bilemez (tek gecis,
 * tip ortami yok). Bu makro hem `str` hem `ax_array_*` icin dogru sonucu
 * verir: `ax_str` bir pointer, diziler ise ilk alani `length` olan struct'tir.
 * Statement expression, rvalue argumanlari da destekler. */
AXIOM_RUNTIME_FN ax_int axiom_str_len(const char* s);

static inline ax_int axiom_len_str_v_(const void* p) {
    if (!p) return 0;
    return axiom_str_len(*(const char* const*)p);
}
static inline ax_int axiom_len_arr_v_(const void* p) {
    if (!p) return 0;
    return ((const ax_int*)p)[0];  /* tum ax_array_* struct'larinda ilk alan length */
}
#define axiom_slen_auto(x) ({ \
    __typeof__(x) _ax_len_tmp_ = (x); \
    _Generic(&_ax_len_tmp_, \
        ax_str*: axiom_len_str_v_((const void*)&_ax_len_tmp_), \
        default: axiom_len_arr_v_((const void*)&_ax_len_tmp_)); \
})

/* Güvenli Serbest Bırakma ve Çift Serbest Bırakma (Double-Free) Koruması */
#define axiom_safe_free(ptr) do { \
    if ((ptr) != NULL) { \
        free((void*)(ptr)); \
        (ptr) = NULL; \
    } \
} while(0)

/* --- Dinamik Sahiplik Takipli String (P2-17b: intrusive header) ---
 *
 * Eski model: her string bir GLOBAL hash tablosunda (ptr -> refs) izlenirdi.
 * 150k canli string icin tablo 6 MB ve her retain/release bir cache miss
 * demekti. Yeni model: refcount string'in HEMEN ONUNDE, ayni tahsiste durur.
 * Boylece retain/release veriyle ayni cache satirina dokunur; tablo yok.
 *
 * GUVENLIK: `str` tipi literal ve dis kaynakli isaretcileri de tasiyabilir.
 * Her isaretci icin `hdr_of()` ONCE `axiom_ptr_is_static` (ELF segment
 * araligi) kontrolu yapar, sonra magic dogrular. Sahipsiz isaretcilerde
 * retain/release no-op'tur (eski tablo davranisiyla ayni).
 */
/* --- Result yardimcilari: TIP PARAMETRESI COZULMEMISSE ---
 *
 * Self-hosted derleyici tek gecisli oldugu icin `result_ok<T>` gibi generic
 * yardimcilarin T'sini genel olarak bilemez. Bu makrolar dogru Result
 * struct'ini secer.
 */
#define axiom_result_ok_int(v)  ((ax_Result_int_str){  .is_ok = true, .value = (v), .error = "" })
#define axiom_result_ok_str(v)  ((ax_Result_str_str){  .is_ok = true, .value = (v), .error = "" })
#define axiom_result_ok_bool(v) ((ax_Result_bool_str){ .is_ok = true, .value = (v), .error = "" })

#define axiom_result_err_with_int(msg, e)  ((ax_Result_int_str){  .is_ok = false, .value = (e), .error = (msg) })
#define axiom_result_err_with_str(msg, e)  ((ax_Result_str_str){  .is_ok = false, .value = (e), .error = (msg) })

/* --- Result yardimcilari: ALAN ERISIMLI MAKROLAR ---
 * `result_is_ok(r)` gibi yardimcilar yalnizca struct alanlarini okur; T'nin
 * ne oldugu onemli degildir. C makrosu her somut Result tipiyle calisir.
 */
#define axiom_result_is_ok(r)   ((r).is_ok)
#define axiom_result_is_err(r)  (!((r).is_ok))
#define axiom_result_error(r)   ((r).error)
#define axiom_result_value(r)   ((r).value)
#define axiom_result_unwrap(r)  ((r).value)
#define axiom_result_unwrap_or(r, fb) \
    ((r).is_ok ? (r).value : (fb))
#define axiom_result_expect(r, msg) \
    ((r).is_ok ? (r).value : \
     (axiom_contract_fail("VERIFY", (msg), "result_expect", __LINE__, NULL), (r).value))

/* --- Statik/literal isaretci tespiti ---
 *
 * Eski kod her string olusturmada `dladdr` cagiriyordu (~17 ns/op, dinamik
 * sembol tablosunu dolasir). Burada ELF'in PT_LOAD (calistirilabilir OLMAYAN)
 * segmentleri BIR KEZ toplanir; kontrol 2-6 aralik karsilastirmasidir.
 *
 * Semantik aynidir: .rodata/.data icindeki literal ve statik metinler
 * sahiplik takibine ALINMAZ; heap/stack isaretcileri alinir.
 */
#if defined(__linux__)
typedef struct { uintptr_t lo; uintptr_t hi; } axiom_seg_t;
#define AXIOM_MAX_STATIC_SEGS 96
static axiom_seg_t g_ax_segs[AXIOM_MAX_STATIC_SEGS];
static int g_ax_seg_count = -1;
static pthread_once_t g_ax_seg_once = PTHREAD_ONCE_INIT;

static int axiom_seg_collect(struct dl_phdr_info* info, size_t size, void* data) {
    (void)size; (void)data;
    for (int i = 0; i < info->dlpi_phnum && g_ax_seg_count < AXIOM_MAX_STATIC_SEGS; i++) {
        const ElfW(Phdr)* ph = &info->dlpi_phdr[i];
        if (ph->p_type != PT_LOAD) continue;
        if (ph->p_flags & PF_X) continue;   /* kod segmente dokunma */
        uintptr_t lo = (uintptr_t)info->dlpi_addr + (uintptr_t)ph->p_vaddr;
        g_ax_segs[g_ax_seg_count].lo = lo;
        g_ax_segs[g_ax_seg_count].hi = lo + (uintptr_t)ph->p_memsz;
        g_ax_seg_count++;
    }
    return 0;
}

static void axiom_seg_init(void) {
    g_ax_seg_count = 0;
    dl_iterate_phdr(axiom_seg_collect, NULL);
}

static inline ax_bool axiom_ptr_is_static(const void* p) {
    if (g_ax_seg_count < 0) pthread_once(&g_ax_seg_once, axiom_seg_init);
    uintptr_t x = (uintptr_t)p;
    for (int i = 0; i < g_ax_seg_count; i++) {
        if (x >= g_ax_segs[i].lo && x < g_ax_segs[i].hi) return true;
    }
    return false;
}
#else
static inline ax_bool axiom_ptr_is_static(const void* p) {
#if defined(__unix__) || defined(__APPLE__)
    Dl_info info;
    if (dladdr(p, &info) != 0) return true;
#endif
    (void)p;
    return false;
}
#endif

/* Olusturma sirasina gore kayit: temp_release O(gecici sayisi) calisir.
 *
 * GUNLUK THREAD-LOCAL'DIR: temp_mark/temp_release ayni ifade icinde, ayni
 * thread'de calisir. Boylece hot path'te kilit YOKTUR (eski global tablo
 * her islemde mutex aliyordu). */
typedef struct { char* ptr; int64_t seq; } ax_seq_log_ent;
#if defined(__GNUC__) || defined(__clang__)
#define AXIOM_TLS __thread
#else
#define AXIOM_TLS _Thread_local
#endif
static AXIOM_TLS ax_seq_log_ent* g_ax_seq_log = NULL;
static AXIOM_TLS size_t g_ax_seq_log_len = 0;
static AXIOM_TLS size_t g_ax_seq_log_cap = 0;

static size_t axiom_seq_log_push(char* p, int64_t seq) {
    if (g_ax_seq_log_len == g_ax_seq_log_cap) {
        size_t ncap = g_ax_seq_log_cap ? g_ax_seq_log_cap * 2 : 64;
        ax_seq_log_ent* np = (ax_seq_log_ent*)realloc(g_ax_seq_log, ncap * sizeof(ax_seq_log_ent));
        if (!np) return (size_t)-1;
        g_ax_seq_log = np;
        g_ax_seq_log_cap = ncap;
    }
    size_t idx = g_ax_seq_log_len;
    g_ax_seq_log[idx].ptr = p;
    g_ax_seq_log[idx].seq = seq;
    __atomic_store_n(&g_ax_seq_log_len, idx + 1, __ATOMIC_RELEASE);
    return idx;
}

#define AXIOM_STR_MAGIC 0x54535841u  /* 'AXST' */

typedef struct {
    uint32_t magic;     /* AXIOM_STR_MAGIC */
    uint32_t refs;      /* atomik refcount */
    uint32_t in_log;    /* gecicilik gunlugunde mi */
    uint32_t _pad;
    int64_t  seq;       /* olusturma sirasi (adres yeniden kullanimi icin) */
    int64_t  log_idx;   /* gunlukteki yuva (-1 = yok) — O(1) unlog icin */
} axiom_str_hdr;

#define AXIOM_STR_HDR_SIZE ((size_t)sizeof(axiom_str_hdr))

static ax_mutex_t g_axiom_owned_str_mu = AX_MUTEX_STATIC_INIT;
static ax_int g_axiom_str_seq = 0;
static ax_int g_axiom_owned_live = 0;   /* tanilama: canli string sayisi */

static inline axiom_str_hdr* axiom_str_hdr_of(const char* s) {
    if (!s) return NULL;
    if (axiom_ptr_is_static(s)) return NULL;
    axiom_str_hdr* h = (axiom_str_hdr*)((char*)s - AXIOM_STR_HDR_SIZE);
    if (h->magic != AXIOM_STR_MAGIC) return NULL;
    return h;
}

static inline ax_int axiom_str_next_seq(void) {
    return __atomic_add_fetch(&g_axiom_str_seq, 1, __ATOMIC_RELAXED);
}

/* Basi header'li, sahipli string tamponu ayirir ve veri isaretcisini doner.
 * Ureticiler bunu kullanirsa `axiom_owned_str_wrap` kopya YAPMAZ (header
 * zaten yerinde). Boylece kisa omurlu stringlerde ek tahsis olmaz. */
AXIOM_RUNTIME_FN char* axiom_str_alloc(size_t len) {
    axiom_str_hdr* h = (axiom_str_hdr*)malloc(AXIOM_STR_HDR_SIZE + len + 1);
    if (!h) {
        fprintf(stderr, "Axiom OOM: Bellek yetersiz!\n");
        exit(1);
    }
    h->magic = AXIOM_STR_MAGIC;
    h->refs = 1;
    h->in_log = 1;
    h->seq = axiom_str_next_seq();
    h->log_idx = -1;
    char* data = (char*)(h + 1);
    data[0] = '\0';

    h->log_idx = (int64_t)axiom_seq_log_push(data, h->seq);
    __atomic_add_fetch(&g_axiom_owned_live, 1, __ATOMIC_RELAXED);
    return data;
}

/* Yeni sahipli string olustur (refcount = 1).
 * Gelen tamponun sahipligini DEVRALIR: veri header'in arkasina kopyalanir ve
 * eski tampon serbest birakilir. Boylece refcount her zaman veriyle ayni
 * cache satirinda kalir. */
AXIOM_RUNTIME_FN char* axiom_owned_str_wrap(const char* buf) {
    if (!buf) return (char*)buf;
    if (axiom_ptr_is_static(buf)) {
        return (char*)buf; /* literal / statik metin: sahiplik alinmaz */
    }
    /* Burada `axiom_str_hdr_of(buf)` CAGRILMAZ: buf baska bir yardimcinin
     * (orn. axiom_p3_strdup) duz malloc tamponu olabilir ve geriye dogru
     * 24 bayt okumak ASan altinda segfault verir. Baslikli tampon ureten
     * yollar (axiom_str_alloc) wrap'i zaten cagirmaz. */
    size_t n = strlen(buf);
    axiom_str_hdr* h = (axiom_str_hdr*)malloc(AXIOM_STR_HDR_SIZE + n + 1);
    if (!h) return (char*)buf;   /* OOM: ham isaretci ile devam (sahipsiz) */
    h->magic = AXIOM_STR_MAGIC;
    h->refs = 1;
    h->in_log = 1;
    h->seq = axiom_str_next_seq();
    h->log_idx = -1;
    char* data = (char*)(h + 1);
    memcpy(data, buf, n + 1);
    free((void*)buf);

    h->log_idx = (int64_t)axiom_seq_log_push(data, h->seq);
    __atomic_add_fetch(&g_axiom_owned_live, 1, __ATOMIC_RELAXED);
    return data;
}

AXIOM_RUNTIME_FN void axiom_str_retain(const char* s) {
    axiom_str_hdr* h = axiom_str_hdr_of(s);
    if (h) __atomic_add_fetch(&h->refs, 1, __ATOMIC_RELAXED);
    /* Sahipsiz (literal/dis) isaretci: no-op. */
}

/* Bir ifade sonucunun sahipligini devral: yalnizca hala gecicilik
 * gunlugundeyse refcount'u artir (ifade sonu temizligi degeri silmesin). */
AXIOM_RUNTIME_FN const char* axiom_str_adopt(const char* s) {
    axiom_str_hdr* h = axiom_str_hdr_of(s);
    if (h && __atomic_load_n(&h->in_log, __ATOMIC_RELAXED)) {
        __atomic_add_fetch(&h->refs, 1, __ATOMIC_RELAXED);
    }
    return s;
}

/* Gunlukteki bir kaydi birak (refcount 1 azalt, gerekirse serbest birak). */
/* Log'daki (ptr, seq) kaydini olu isaretle: sonraki temp_release bu adrese
 * DOKUNMAZ (serbest birakilmis bellek okunmaz). */
static void axiom_str_unlog(axiom_str_hdr* h, const char* ptr) {
    int64_t idx = h->log_idx;
    h->log_idx = -1;
    if (idx < 0) return;
    /* Gunluk thread-local: kilit gerekmez. */
    if ((size_t)idx < g_ax_seq_log_cap
        && g_ax_seq_log[idx].ptr == (char*)ptr
        && g_ax_seq_log[idx].seq == h->seq) {
        g_ax_seq_log[idx].seq = -1;   /* olu kayit: temp_release dokunmaz */
    }
}

static void axiom_str_release_logged(char* ptr, int64_t seq) {
    if (seq < 0) return;   /* olu kayit: bellek zaten birakildi */
    axiom_str_hdr* h = axiom_str_hdr_of(ptr);
    if (!h || h->seq != seq) return;   /* adres yeniden kullanilmis / sahipsiz */
    __atomic_store_n(&h->in_log, 0, __ATOMIC_RELAXED);
    h->log_idx = -1;
    if (__atomic_sub_fetch(&h->refs, 1, __ATOMIC_RELAXED) == 0) {
        __atomic_sub_fetch(&g_axiom_owned_live, 1, __ATOMIC_RELAXED);
        free(h);
    }
}

AXIOM_RUNTIME_FN const char* axiom_temp_release_keep(ax_int mark, const char* keep) {
    if (mark < 0) mark = 0;
    bool keep_was_logged = false;
    int64_t keep_seq = 0;
    for (;;) {
        size_t len = g_ax_seq_log_len;
        if ((ax_int)len <= mark) break;
        size_t idx = len - 1;
        ax_seq_log_ent ent = g_ax_seq_log[idx];
        g_ax_seq_log_len = idx;
        if (ent.ptr == keep) {
            /* 'keep' hala yasiyor: sahipligi cagirana devrediyoruz ama gunlukten
             * TAMAMEN cikarmiyoruz; dis kapsam kendi temp_release'i ile birakir. */
            keep_was_logged = true;
            keep_seq = ent.seq;
            continue;
        }
        axiom_str_release_logged(ent.ptr, ent.seq);
    }

    if (keep_was_logged) {
        axiom_str_hdr* h = axiom_str_hdr_of(keep);
        if (h && h->seq == keep_seq) {
            __atomic_store_n(&h->in_log, 1, __ATOMIC_RELAXED);
            h->log_idx = (int64_t)axiom_seq_log_push((char*)keep, keep_seq);
        }
    }
    return keep;
}

AXIOM_RUNTIME_FN void axiom_str_release(const char* s) {
    axiom_str_hdr* h = axiom_str_hdr_of(s);
    if (!h) return;    /* literal / dis isaretci: serbest birakma yok */
    uint32_t old = __atomic_load_n(&h->refs, __ATOMIC_RELAXED);
    if (old == 0) return;   /* zaten birakilmis */
    if (__atomic_sub_fetch(&h->refs, 1, __ATOMIC_RELAXED) == 0) {
        /* Log hala bu adresi tutuyorsa once kaydi OLU isaretle (UAF onlenir),
         * sonra gercekten serbest birak. */
        if (__atomic_load_n(&h->in_log, __ATOMIC_RELAXED)) {
            axiom_str_unlog(h, s);
            __atomic_store_n(&h->in_log, 0, __ATOMIC_RELAXED);
        }
        __atomic_sub_fetch(&g_axiom_owned_live, 1, __ATOMIC_RELAXED);
        free(h);
    }
}

AXIOM_RUNTIME_FN void axiom_str_free(const char* s) {
    if (!s) return;
    axiom_str_hdr* h = axiom_str_hdr_of(s);
    if (h) {
        if (__atomic_load_n(&h->in_log, __ATOMIC_RELAXED)) {
            axiom_str_unlog(h, s);
            __atomic_store_n(&h->in_log, 0, __ATOMIC_RELAXED);
        }
        __atomic_sub_fetch(&g_axiom_owned_live, 1, __ATOMIC_RELAXED);
        free(h);
        return;
    }
    if (axiom_ptr_is_static(s)) return;
    free((void*)s);
}

/* Cift serbest birakma ve literal korumasini birlikte saglayan slot tabanli serbest birakma. */
AXIOM_RUNTIME_FN void axiom_str_free_slot(const char** slot) {
    if (!slot || !*slot) return;
    axiom_str_release(*slot);
    *slot = NULL;
}

AXIOM_RUNTIME_FN void axiom_str_owned_release(const char** target) {
    if (!target || !*target) return;
    axiom_str_release(*target);
    *target = NULL;
}

/* `s = s + x` deseni: tek sahipliyse yerinde buyut (O(n^2) onlenir). */
AXIOM_RUNTIME_FN void axiom_str_concat_assign(const char** target, const char* suffix) {
    if (!target) return;
    if (!suffix) suffix = "";
    const char* old = *target ? *target : "";
    size_t l1 = strlen(old);
    size_t l2 = strlen(suffix);

    int alias = (suffix >= old && suffix <= old + l1);
    size_t suffix_offset = alias ? (size_t)(suffix - old) : 0;

    axiom_str_hdr* h = axiom_str_hdr_of(old);
    if (h && __atomic_load_n(&h->refs, __ATOMIC_RELAXED) == 1) {
        axiom_str_hdr* nh = (axiom_str_hdr*)realloc(h, AXIOM_STR_HDR_SIZE + l1 + l2 + 1);
        if (!nh) {
            fprintf(stderr, "Axiom OOM: Bellek yetersiz!\n");
            exit(1);
        }
        char* data = (char*)(nh + 1);
        const char* src = alias ? (data + suffix_offset) : suffix;
        memmove(data + l1, src, l2 + 1);
        if (nh != h) {
            /* Adres degisti: gunlukteki kaydi O(1) guncelle. */
            int64_t li = nh->log_idx;
            ax_os_mutex_lock(&g_axiom_owned_str_mu);
            if (li >= 0 && (size_t)li < g_ax_seq_log_cap
                && g_ax_seq_log[li].ptr == (char*)old) {
                g_ax_seq_log[li].ptr = data;
            }
            ax_os_mutex_unlock(&g_axiom_owned_str_mu);
        }
        *target = data;
        return;
    }

    size_t n = l1 + l2;
    axiom_str_hdr* nh2 = (axiom_str_hdr*)malloc(AXIOM_STR_HDR_SIZE + n + 1);
    if (!nh2) {
        fprintf(stderr, "Axiom OOM: Bellek yetersiz!\n");
        exit(1);
    }
    nh2->magic = AXIOM_STR_MAGIC;
    nh2->refs = 1;
    nh2->in_log = 1;
    nh2->seq = axiom_str_next_seq();
    nh2->log_idx = -1;
    char* data2 = (char*)(nh2 + 1);
    memcpy(data2, old, l1);
    memcpy(data2 + l1, suffix, l2 + 1);

    ax_os_mutex_lock(&g_axiom_owned_str_mu);
    nh2->log_idx = (int64_t)axiom_seq_log_push(data2, nh2->seq);
    __atomic_add_fetch(&g_axiom_owned_live, 1, __ATOMIC_RELAXED);
    ax_os_mutex_unlock(&g_axiom_owned_str_mu);

    axiom_str_release(old);   /* eski degeri birak */
    *target = data2;
}

/* --- Islem (statement) Bazli Gecici String Temizligi --- */
AXIOM_RUNTIME_FN ax_int axiom_temp_mark(void) {
    return (ax_int)g_ax_seq_log_len;
}

AXIOM_RUNTIME_FN void axiom_temp_release(ax_int mark) {
    if (mark < 0) mark = 0;
    while ((ax_int)g_ax_seq_log_len > mark) {
        g_ax_seq_log_len--;
        ax_seq_log_ent ent = g_ax_seq_log[g_ax_seq_log_len];
        axiom_str_release_logged(ent.ptr, ent.seq);
    }
}

/* Test/diagnostik: su anda canli (izlenen) string sayisi. */
AXIOM_RUNTIME_FN ax_int axiom_owned_str_count(void) {
    return __atomic_load_n(&g_axiom_owned_live, __ATOMIC_RELAXED);
}

/* --- Dizi Kopyalama (Deger Anlambilimi) --- */
/* Ileri bildirimler: heap dizi tampon kayit defteri (tanimi asagida) */
static void axiom_heap_buf_track(void* p);
static int axiom_heap_buf_untrack(void* p);
static void axiom_heap_buf_release_if_owned(void* p);

AXIOM_RUNTIME_FN ax_array_int axiom_array_clone_int(ax_array_int a) {
    ax_array_int r; r.length = a.length; r.capacity = a.length; r.data = NULL;
    if (a.length > 0 && a.data) {
        r.data = (ax_int*)malloc((size_t)a.length * sizeof(ax_int));
        if (r.data) {
            memcpy(r.data, a.data, (size_t)a.length * sizeof(ax_int));
            axiom_heap_buf_track((void*)r.data);
        }
    }
    return r;
}
AXIOM_RUNTIME_FN ax_array_float axiom_array_clone_float(ax_array_float a) {
    ax_array_float r; r.length = a.length; r.capacity = a.length; r.data = NULL;
    if (a.length > 0 && a.data) {
        r.data = (ax_float*)malloc((size_t)a.length * sizeof(ax_float));
        if (r.data) {
            memcpy(r.data, a.data, (size_t)a.length * sizeof(ax_float));
            axiom_heap_buf_track((void*)r.data);
        }
    }
    return r;
}
AXIOM_RUNTIME_FN ax_array_bool axiom_array_clone_bool(ax_array_bool a) {
    ax_array_bool r; r.length = a.length; r.capacity = a.length; r.data = NULL;
    if (a.length > 0 && a.data) {
        r.data = (ax_bool*)malloc((size_t)a.length * sizeof(ax_bool));
        if (r.data) {
            memcpy(r.data, a.data, (size_t)a.length * sizeof(ax_bool));
            axiom_heap_buf_track((void*)r.data);
        }
    }
    return r;
}
AXIOM_RUNTIME_FN ax_array_str axiom_array_clone_str(ax_array_str a) {
    ax_array_str r; r.length = a.length; r.capacity = a.length; r.data = NULL;
    if (a.length > 0 && a.data) {
        r.data = (ax_str*)malloc((size_t)a.length * sizeof(ax_str));
        if (r.data) {
            memcpy(r.data, a.data, (size_t)a.length * sizeof(ax_str));
            for (ax_int i = 0; i < a.length; i++) {
                axiom_str_retain(r.data[i]);
            }
        }
    }
    return r;
}

#define axiom_safe_str_free(s) do { \
    if ((s) != NULL) { \
        free((void*)(s)); \
        (s) = NULL; \
    } \
} while(0)

/* --- Heap Dizi Tampon Kayit Defteri ---
 * Dizi literalleri (compound literal) stack/statik alanda yasar; push sirasinda
 * yalnizca gercekten heap'te ayrilmis eski tamponlar serbest birakilmalidir.
 * Bu defter, hangi tamponlarin heap'e ait oldugunu izler. */
typedef struct {
    void** slots;
    size_t cap;
    size_t count;
} ax_heap_buf_tbl;

static ax_heap_buf_tbl g_ax_heap_bufs = { NULL, 0, 0 };
static ax_mutex_t g_ax_heap_bufs_mu = AX_MUTEX_STATIC_INIT;

static size_t axiom_buf_hash(const void* p, size_t cap) {
    uintptr_t x = (uintptr_t)p;
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ULL;
    x ^= x >> 33;
    return (size_t)(x & (cap - 1));
}

static void axiom_heap_buf_rehash(size_t new_cap) {
    if (new_cap < 256) new_cap = 256;
    void** ns = (void**)calloc(new_cap, sizeof(void*));
    if (!ns) return;
    for (size_t i = 0; i < g_ax_heap_bufs.cap; i++) {
        void* p = g_ax_heap_bufs.slots ? g_ax_heap_bufs.slots[i] : NULL;
        if (!p) continue;
        size_t k = axiom_buf_hash(p, new_cap);
        while (ns[k]) k = (k + 1) & (new_cap - 1);
        ns[k] = p;
    }
    free(g_ax_heap_bufs.slots);
    g_ax_heap_bufs.slots = ns;
    g_ax_heap_bufs.cap = new_cap;
}

static void axiom_heap_buf_track(void* p) {
    if (!p) return;
    ax_os_mutex_lock(&g_ax_heap_bufs_mu);
    if (g_ax_heap_bufs.cap == 0) axiom_heap_buf_rehash(256);
    if (g_ax_heap_bufs.count * 4 >= g_ax_heap_bufs.cap * 3) {
        axiom_heap_buf_rehash(g_ax_heap_bufs.cap * 2);
    }
    size_t cap = g_ax_heap_bufs.cap;
    if (cap == 0) { ax_os_mutex_unlock(&g_ax_heap_bufs_mu); return; }
    size_t k = axiom_buf_hash(p, cap);
    while (g_ax_heap_bufs.slots[k]) {
        if (g_ax_heap_bufs.slots[k] == p) {
            ax_os_mutex_unlock(&g_ax_heap_bufs_mu);
            return;
        }
        k = (k + 1) & (cap - 1);
    }
    g_ax_heap_bufs.slots[k] = p;
    g_ax_heap_bufs.count++;
    ax_os_mutex_unlock(&g_ax_heap_bufs_mu);
}

static int axiom_heap_buf_untrack(void* p) {
    if (!p || g_ax_heap_bufs.cap == 0) return 0;
    int found = 0;
    ax_os_mutex_lock(&g_ax_heap_bufs_mu);
    size_t cap = g_ax_heap_bufs.cap;
    if (cap == 0) { ax_os_mutex_unlock(&g_ax_heap_bufs_mu); return 0; }
    size_t k = axiom_buf_hash(p, cap);
    size_t start = k;
    while (g_ax_heap_bufs.slots[k]) {
        if (g_ax_heap_bufs.slots[k] == p) {
            g_ax_heap_bufs.slots[k] = NULL;
            g_ax_heap_bufs.count--;
            /* Backward-shift: sonraki kayitlari dogru yuvaya tasi. */
            size_t j = k;
            for (;;) {
                j = (j + 1) & (cap - 1);
                if (!g_ax_heap_bufs.slots[j]) break;
                size_t h = axiom_buf_hash(g_ax_heap_bufs.slots[j], cap);
                int move = 0;
                if (k <= j) {
                    if (h <= k || h > j) move = 1;
                } else {
                    if (h <= k && h > j) move = 1;
                }
                if (move) {
                    g_ax_heap_bufs.slots[k] = g_ax_heap_bufs.slots[j];
                    g_ax_heap_bufs.slots[j] = NULL;
                    k = j;
                }
            }
            found = 1;
            break;
        }
        k = (k + 1) & (cap - 1);
        if (k == start) break;
    }
    ax_os_mutex_unlock(&g_ax_heap_bufs_mu);
    return found;
}

/* Yalnizca heap'e aitse serbest birakir; literal/stack tamponlara dokunmaz. */
static void axiom_heap_buf_release_if_owned(void* p) {
    if (p && axiom_heap_buf_untrack(p)) {
        free(p);
    }
}

#define axiom_array_free(arr) do { \
    if ((arr).data != NULL) { \
        axiom_heap_buf_release_if_owned((void*)(arr).data); \
        (arr).data = NULL; \
        (arr).length = 0; \
    } \
} while(0)

AXIOM_RUNTIME_FN void axiom_array_int_free(ax_array_int* arr) {
    if (arr && arr->data) {
        axiom_heap_buf_release_if_owned((void*)arr->data);
        arr->data = NULL;
        arr->length = 0;
        arr->capacity = 0;
    }
}

AXIOM_RUNTIME_FN void axiom_array_float_free(ax_array_float* arr) {
    if (arr && arr->data) {
        axiom_heap_buf_release_if_owned((void*)arr->data);
        arr->data = NULL;
        arr->length = 0;
        arr->capacity = 0;
    }
}

AXIOM_RUNTIME_FN void axiom_array_bool_free(ax_array_bool* arr) {
    if (arr && arr->data) {
        axiom_heap_buf_release_if_owned((void*)arr->data);
        arr->data = NULL;
        arr->length = 0;
        arr->capacity = 0;
    }
}

AXIOM_RUNTIME_FN void axiom_array_str_free(ax_array_str* arr) {
    if (arr && arr->data) {
        for (ax_int i = 0; i < arr->length; i++) {
            if (arr->data[i]) {
                axiom_str_release(arr->data[i]);
                arr->data[i] = NULL;
            }
        }
        axiom_heap_buf_release_if_owned((void*)arr->data);
        arr->data = NULL;
        arr->length = 0;
        arr->capacity = 0;
    }
}

/* Dizi Sınır Denetimi (Runtime Bounds Check) */
AXIOM_RUNTIME_FN ax_int axiom_bounds_check(ax_int idx, ax_int len, const char* file, ax_int line) {
    if (idx < 0 || idx >= len) {
        fprintf(stderr, "[AXIOM BELLEK IHLALI] Dizi sınır aşımı (Index out of bounds)!\n");
        if (file) {
            fprintf(stderr, "  Konum: %s:%" PRId64 "\n", file, line);
        }
        fprintf(stderr, "  Indeks: %" PRId64 ", Dizi Uzunlugu: %" PRId64 "\n", idx, len);
        exit(102);
    }
    return idx;
}

/* Güvenli Aritmetik Bölme ve Mod İşlemleri (Sıfıra Bölme Koruması) */
#define axiom_safe_div(a, b, line) ({ \
    __typeof__(a) _ax_div_a = (a); \
    __typeof__(b) _ax_div_b = (b); \
    if (_ax_div_b == 0) { \
        axiom_contract_fail("ARITHMETIC_ZERO_DIV", "bolen != 0", "div", (int)(line), "Sifira bolme hatasi!"); \
    } \
    _ax_div_a / _ax_div_b; \
})

#define axiom_safe_mod(a, b, line) ({ \
    __typeof__(a) _ax_mod_a = (a); \
    __typeof__(b) _ax_mod_b = (b); \
    if ((ax_int)(_ax_mod_b) == 0) { \
        axiom_contract_fail("ARITHMETIC_ZERO_DIV", "bolen != 0", "mod", (int)(line), "Sifira bolme (mod) hatasi!"); \
    } \
    (ax_int)_ax_mod_a % (ax_int)_ax_mod_b; \
})

/* Güvenli Tamsayı Aritmetiği (Taşma Koruması) */
#define axiom_safe_add(a, b, line) ({ \
    ax_int _ax_add_a = (ax_int)(a); \
    ax_int _ax_add_b = (ax_int)(b); \
    ax_int _ax_add_r; \
    if (__builtin_add_overflow(_ax_add_a, _ax_add_b, &_ax_add_r)) { \
        axiom_contract_fail("ARITHMETIC_OVERFLOW", "tasma yok", "add", (int)(line), "Tamsayi toplama tasmasi!"); \
    } \
    _ax_add_r; \
})

#define axiom_safe_sub(a, b, line) ({ \
    ax_int _ax_sub_a = (ax_int)(a); \
    ax_int _ax_sub_b = (ax_int)(b); \
    ax_int _ax_sub_r; \
    if (__builtin_sub_overflow(_ax_sub_a, _ax_sub_b, &_ax_sub_r)) { \
        axiom_contract_fail("ARITHMETIC_OVERFLOW", "tasma yok", "sub", (int)(line), "Tamsayi cikarma tasmasi!"); \
    } \
    _ax_sub_r; \
})

#define axiom_safe_mul(a, b, line) ({ \
    ax_int _ax_mul_a = (ax_int)(a); \
    ax_int _ax_mul_b = (ax_int)(b); \
    ax_int _ax_mul_r; \
    if (__builtin_mul_overflow(_ax_mul_a, _ax_mul_b, &_ax_mul_r)) { \
        axiom_contract_fail("ARITHMETIC_OVERFLOW", "tasma yok", "mul", (int)(line), "Tamsayi carpma tasmasi!"); \
    } \
    _ax_mul_r; \
})

#define axiom_safe_neg(a, line) ({ \
    ax_int _ax_neg_a = (ax_int)(a); \
    if (_ax_neg_a == INT64_MIN) { \
        axiom_contract_fail("ARITHMETIC_OVERFLOW", "tasma yok", "neg", (int)(line), "Tamsayi negasyon tasmasi!"); \
    } \
    -_ax_neg_a; \
})

#define axiom_array_push(arr, elem) ({ \
    __typeof__(arr) _ax_arr = (arr); \
    __typeof__(elem) _ax_val = (elem); \
    __typeof__(arr) _ax_new; \
    if (_ax_arr.data != NULL && _ax_arr.capacity > _ax_arr.length) { \
        _ax_new = _ax_arr; \
        _ax_new.data[_ax_arr.length] = _ax_val; \
        _ax_new.length = _ax_arr.length + 1; \
    } else { \
        ax_int _ax_cap = _ax_arr.capacity > 0 ? _ax_arr.capacity * 2 : 8; \
        if (_ax_cap <= _ax_arr.length) _ax_cap = _ax_arr.length + 1; \
        __typeof__(_ax_arr.data) _ax_buf; \
        if (_ax_arr.capacity > 0 && _ax_arr.data != NULL) { \
            _ax_buf = (__typeof__(_ax_arr.data))realloc( \
                (void*)_ax_arr.data, (size_t)_ax_cap * sizeof(*_ax_arr.data)); \
            if (_ax_buf) axiom_heap_buf_track((void*)_ax_buf); \
        } else { \
            _ax_buf = (__typeof__(_ax_arr.data))malloc( \
                (size_t)_ax_cap * sizeof(*_ax_arr.data)); \
            if (_ax_buf && _ax_arr.length > 0 && _ax_arr.data) { \
                memcpy(_ax_buf, _ax_arr.data, \
                       (size_t)_ax_arr.length * sizeof(*_ax_arr.data)); \
            } \
            if (_ax_buf) axiom_heap_buf_track((void*)_ax_buf); \
        } \
        if (!_ax_buf) { \
            fprintf(stderr, "Axiom OOM: Bellek yetersiz!\n"); \
            exit(1); \
        } \
        _ax_new.length = _ax_arr.length + 1; \
        _ax_new.capacity = _ax_cap; \
        _ax_new.data = _ax_buf; \
        _ax_new.data[_ax_arr.length] = _ax_val; \
        _ax_arr.length = 0; \
        _ax_arr.capacity = 0; \
        _ax_arr.data = NULL; \
    } \
    _ax_new; \
})

/* Metin (String) İşlemleri */
AXIOM_RUNTIME_FN char* axiom_safe_strdup(const char* s) {
    if (!s) return (char*)"";
    size_t len = strlen(s);
    char* r = axiom_str_alloc(len);
    memcpy(r, s, len + 1);
    return r;
}
AXIOM_RUNTIME_FN ax_str axiom_str_concat(const char* s1, const char* s2) {
    if (!s1) s1 = "";
    if (!s2) s2 = "";
    size_t len1 = strlen(s1);
    size_t len2 = strlen(s2);
    char* result = axiom_str_alloc(len1 + len2);
    memcpy(result, s1, len1);
    memcpy(result + len1, s2, len2);
    result[len1 + len2] = '\0';
    return result;
}

/* --- Self-hosted derleyici icin tip-cozucu operator yardimcilari ---
 *
 * Tek gecisli self-hosted derleyici degisken tiplerini izlemez; `a + b`'nin
 * tamsayi toplami mi string birlestirme mi oldugunu bilemez. Bu makro karari
 * C derleyicisine birakir: `_Generic` sol operandin tipine bakar.
 */
static inline ax_str axiom_add_str_(const char* a, const char* b) {
    return axiom_str_concat(a, b);
}
static inline ax_int axiom_add_int_(ax_int a, ax_int b) { return a + b; }
static inline ax_float axiom_add_float_(ax_float a, ax_float b) { return a + b; }

static inline ax_bool axiom_eq_int_(ax_int a, ax_int b) { return a == b; }
static inline ax_bool axiom_eq_float_(ax_float a, ax_float b) { return a == b; }
static inline ax_bool axiom_neq_int_(ax_int a, ax_int b) { return a != b; }
static inline ax_bool axiom_neq_float_(ax_float a, ax_float b) { return a != b; }

/* `a == b`: metinlerde icerik karsilastirmasi, sayilarda deger
 * karsilastirmasi. Iki degisken karsilastirilirken tipleri bilinmedigi icin
 * karar C derleyicisine birakilir (pointer karsilastirmasi sessiz hataydi). */
#define axiom_eq_auto(a, b) _Generic((a), \
    char*: axiom_str_eq, \
    const char*: axiom_str_eq, \
    float: axiom_eq_float_, \
    double: axiom_eq_float_, \
    default: axiom_eq_int_)(a, b)

#define axiom_neq_auto(a, b) _Generic((a), \
    char*: axiom_str_neq, \
    const char*: axiom_str_neq, \
    float: axiom_neq_float_, \
    double: axiom_neq_float_, \
    default: axiom_neq_int_)(a, b)

#define axiom_add_auto(a, b) _Generic((a), \
    char*: axiom_add_str_, \
    const char*: axiom_add_str_, \
    float: axiom_add_float_, \
    double: axiom_add_float_, \
    default: axiom_add_int_)(a, b)

AXIOM_RUNTIME_FN ax_bool axiom_str_eq(const char* s1, const char* s2) {
    if (s1 == s2) return true;
    if (!s1 || !s2) return false;
    return strcmp(s1, s2) == 0;
}

AXIOM_RUNTIME_FN ax_bool axiom_str_neq(const char* s1, const char* s2) {
    return !axiom_str_eq(s1, s2);
}

/* Gelişmiş Metin (String) İşlemleri */
AXIOM_RUNTIME_FN ax_str axiom_str_char_at(const char* s, ax_int idx) {
    if (!s) return axiom_owned_str_wrap("");
    size_t len = strlen(s);
    if (idx < 0 || (size_t)idx >= len) return axiom_owned_str_wrap("");
    char* buf = (char*)malloc(2);
    if (!buf) return axiom_owned_str_wrap("");
    buf[0] = s[idx];
    buf[1] = '\0';
    return axiom_owned_str_wrap(buf);
}

AXIOM_RUNTIME_FN ax_str axiom_str_sub(const char* s, ax_int start, ax_int count) {
    if (!s) return axiom_owned_str_wrap("");
    size_t len = strlen(s);
    if (start < 0 || (size_t)start >= len || count <= 0) return axiom_owned_str_wrap("");
    if ((size_t)(start + count) > len) count = (ax_int)(len - start);
    char* buf = axiom_str_alloc((size_t)count);
    memcpy(buf, s + start, (size_t)count);
    buf[count] = '\0';
    return buf;
}

AXIOM_RUNTIME_FN ax_int axiom_str_byte_len(const char* s) {
    if (!s) return 0;
    return (ax_int)strlen(s);
}

AXIOM_RUNTIME_FN ax_int axiom_str_len(const char* s) {
    if (!s) return 0;
    ax_int count = 0;
    const unsigned char* p = (const unsigned char*)s;
    while (*p) {
        if ((*p & 0xC0) != 0x80) {
            count++;
        }
        p++;
    }
    return count;
}

/* ========================================================================= */
/* Unicode Annex #29 UTF-8 Codepoint, Grapheme Cluster & Turkce Motoru       */
/* ========================================================================= */

AXIOM_RUNTIME_FN ax_int axiom_utf8_next_codepoint(const char* s, ax_int* offset) {
    if (!s || !offset) return -1;
    const unsigned char* bytes = (const unsigned char*)s;
    ax_int idx = *offset;
    if (bytes[idx] == '\0') return -1;

    unsigned char b0 = bytes[idx];
    ax_int cp = 0;
    if ((b0 & 0x80) == 0x00) {
        cp = b0;
        *offset = idx + 1;
    } else if ((b0 & 0xE0) == 0xC0) {
        unsigned char b1 = bytes[idx + 1];
        if ((b1 & 0xC0) != 0x80) { *offset = idx + 1; return 0xFFFD; }
        cp = ((b0 & 0x1F) << 6) | (b1 & 0x3F);
        *offset = idx + 2;
    } else if ((b0 & 0xF0) == 0xE0) {
        unsigned char b1 = bytes[idx + 1];
        unsigned char b2 = bytes[idx + 2];
        if ((b1 & 0xC0) != 0x80 || (b2 & 0xC0) != 0x80) { *offset = idx + 1; return 0xFFFD; }
        cp = ((b0 & 0x0F) << 12) | ((b1 & 0x3F) << 6) | (b2 & 0x3F);
        *offset = idx + 3;
    } else if ((b0 & 0xF8) == 0xF0) {
        unsigned char b1 = bytes[idx + 1];
        unsigned char b2 = bytes[idx + 2];
        unsigned char b3 = bytes[idx + 3];
        if ((b1 & 0xC0) != 0x80 || (b2 & 0xC0) != 0x80 || (b3 & 0xC0) != 0x80) { *offset = idx + 1; return 0xFFFD; }
        cp = ((b0 & 0x07) << 18) | ((b1 & 0x3F) << 12) | ((b2 & 0x3F) << 6) | (b3 & 0x3F);
        *offset = idx + 4;
    } else {
        *offset = idx + 1;
        return 0xFFFD;
    }
    return cp;
}

AXIOM_RUNTIME_FN ax_int axiom_utf8_codepoint_count(const char* s) {
    if (!s) return 0;
    ax_int offset = 0;
    ax_int count = 0;
    while (axiom_utf8_next_codepoint(s, &offset) != -1) {
        count++;
    }
    return count;
}

AXIOM_RUNTIME_FN bool axiom_utf8_is_combining_or_extend(ax_int cp) {
    if (cp >= 0x0300 && cp <= 0x036F) return true;
    if (cp >= 0x1AB0 && cp <= 0x1AFF) return true;
    if (cp >= 0x1DC0 && cp <= 0x1DFF) return true;
    if (cp >= 0x20D0 && cp <= 0x20FF) return true;
    if (cp >= 0xFE20 && cp <= 0xFE2F) return true;
    if (cp >= 0xFE00 && cp <= 0xFE0F) return true;
    if (cp >= 0xE0100 && cp <= 0xE01EF) return true;
    if (cp == 0x200D || cp == 0x200C) return true;
    if (cp >= 0x1F3FB && cp <= 0x1F3FF) return true;
    if (cp >= 0x20DD && cp <= 0x20E4) return true;
    if (cp >= 0xE0020 && cp <= 0xE007F) return true;
    return false;
}

AXIOM_RUNTIME_FN bool axiom_utf8_is_pictographic(ax_int cp) {
    if (cp >= 0x1F300 && cp <= 0x1FAFF) return true;
    if (cp >= 0x2600 && cp <= 0x27BF) return true;
    if (cp >= 0x1F1E6 && cp <= 0x1F1FF) return true;
    return false;
}

AXIOM_RUNTIME_FN ax_int axiom_utf8_next_grapheme_len(const char* s, ax_int start_offset) {
    if (!s || s[start_offset] == '\0') return 0;
    ax_int offset = start_offset;
    ax_int cp1 = axiom_utf8_next_codepoint(s, &offset);
    if (cp1 == -1) return 0;

    if (cp1 == '\r' && s[offset] == '\n') {
        offset++;
        return offset - start_offset;
    }

    bool last_was_zwj = (cp1 == 0x200D);
    while (s[offset] != '\0') {
        ax_int next_offset = offset;
        ax_int next_cp = axiom_utf8_next_codepoint(s, &next_offset);
        if (next_cp == -1) break;

        if (axiom_utf8_is_combining_or_extend(next_cp)) {
            offset = next_offset;
            last_was_zwj = (next_cp == 0x200D);
        } else if (last_was_zwj && (axiom_utf8_is_pictographic(next_cp) || next_cp > 0x7F)) {
            offset = next_offset;
            last_was_zwj = false;
        } else {
            break;
        }
    }
    return offset - start_offset;
}

AXIOM_RUNTIME_FN ax_int axiom_str_grapheme_len(const char* s) {
    if (!s) return 0;
    ax_int count = 0;
    ax_int offset = 0;
    while (s[offset] != '\0') {
        ax_int glen = axiom_utf8_next_grapheme_len(s, offset);
        if (glen <= 0) break;
        count++;
        offset += glen;
    }
    return count;
}

AXIOM_RUNTIME_FN ax_str axiom_str_grapheme_at(const char* s, ax_int target_idx) {
    if (!s || target_idx < 0) return axiom_owned_str_wrap("");
    ax_int current_idx = 0;
    ax_int offset = 0;
    while (s[offset] != '\0') {
        ax_int glen = axiom_utf8_next_grapheme_len(s, offset);
        if (glen <= 0) break;
        if (current_idx == target_idx) {
            char* buf = (char*)malloc((size_t)glen + 1);
            if (!buf) return axiom_owned_str_wrap("");
            memcpy(buf, s + offset, (size_t)glen);
            buf[glen] = '\0';
            return axiom_owned_str_wrap(buf);
        }
        current_idx++;
        offset += glen;
    }
    return axiom_owned_str_wrap("");
}

AXIOM_RUNTIME_FN void axiom_utf8_encode_cp(char** dst, ax_int cp) {
    char* p = *dst;
    if (cp <= 0x7F) {
        *p++ = (char)cp;
    } else if (cp <= 0x7FF) {
        *p++ = (char)(0xC0 | ((cp >> 6) & 0x1F));
        *p++ = (char)(0x80 | (cp & 0x3F));
    } else if (cp <= 0xFFFF) {
        *p++ = (char)(0xE0 | ((cp >> 12) & 0x0F));
        *p++ = (char)(0x80 | ((cp >> 6) & 0x3F));
        *p++ = (char)(0x80 | (cp & 0x3F));
    } else {
        *p++ = (char)(0xF0 | ((cp >> 18) & 0x07));
        *p++ = (char)(0x80 | ((cp >> 12) & 0x3F));
        *p++ = (char)(0x80 | ((cp >> 6) & 0x3F));
        *p++ = (char)(0x80 | (cp & 0x3F));
    }
    *dst = p;
}

/* -------------------------------------------------------------------------
 * Unicode Normalleştirme (UAX #15): NFD / NFC
 *
 * Tablolar `unicode_tables.h` içinde UCD'den üretilir; Hangul algoritmiktir.
 * NFKC/NFKD desteklenmez (compatibility ayrıştırma tablosu yok) — sessizce
 * yanlış sonuç vermek yerine açık hata döndürülür.
 * ------------------------------------------------------------------------- */

typedef struct {
    uint32_t* cp;
    size_t len;
    size_t cap;
} axiom_cpbuf_t;

static bool axiom_cpbuf_push(axiom_cpbuf_t* b, uint32_t cp) {
    if (b->len == b->cap) {
        size_t ncap = b->cap ? b->cap * 2 : 64;
        uint32_t* grown = (uint32_t*)realloc(b->cp, ncap * sizeof(uint32_t));
        if (!grown) return false;
        b->cp = grown;
        b->cap = ncap;
    }
    b->cp[b->len++] = cp;
    return true;
}

static const axiom_ucd_decomp_t* axiom_ucd_find_decomp(uint32_t cp) {
    size_t lo = 0, hi = AXIOM_UCD_DECOMP_COUNT;
    while (lo < hi) {
        size_t mid = (lo + hi) / 2;
        if (axiom_ucd_decomp[mid].cp == cp) return &axiom_ucd_decomp[mid];
        if (axiom_ucd_decomp[mid].cp < cp) lo = mid + 1;
        else hi = mid;
    }
    return NULL;
}

static uint8_t axiom_ucd_ccc_of(uint32_t cp) {
    size_t lo = 0, hi = AXIOM_UCD_CCC_COUNT;
    while (lo < hi) {
        size_t mid = (lo + hi) / 2;
        uint32_t at = axiom_ucd_ccc[mid].cp;
        if (at == cp) return axiom_ucd_ccc[mid].ccc;
        if (at < cp) lo = mid + 1;
        else hi = mid;
    }
    return 0;
}

static bool axiom_ucd_compose_pair(uint32_t a, uint32_t b, uint32_t* out) {
    size_t lo = 0, hi = AXIOM_UCD_COMP_COUNT;
    while (lo < hi) {
        size_t mid = (lo + hi) / 2;
        const axiom_ucd_comp_t* e = &axiom_ucd_comp[mid];
        if (e->a == a && e->b == b) { *out = e->cp; return true; }
        if (e->a < a || (e->a == a && e->b < b)) lo = mid + 1;
        else hi = mid;
    }
    return false;
}

/* Hangul: LV / LVT algoritmik ayrıştırma (Unicode §3.12) */
static bool axiom_hangul_decompose(uint32_t cp, uint32_t* a, uint32_t* b) {
    if (cp < AXIOM_UCD_HANGUL_S_BASE ||
        cp >= AXIOM_UCD_HANGUL_S_BASE + AXIOM_UCD_HANGUL_S_COUNT) return false;
    uint32_t s_index = cp - AXIOM_UCD_HANGUL_S_BASE;
    uint32_t t_index = s_index % AXIOM_UCD_HANGUL_T_COUNT;
    if (t_index == 0) {
        /* LV -> L + V */
        *a = AXIOM_UCD_HANGUL_L_BASE + (s_index / AXIOM_UCD_HANGUL_N_COUNT);
        *b = AXIOM_UCD_HANGUL_V_BASE +
             ((s_index % AXIOM_UCD_HANGUL_N_COUNT) / AXIOM_UCD_HANGUL_T_COUNT);
    } else {
        /* LVT -> (LV hecesi) + T ; ozyineleme LV'yi L + V'ye ayirir. */
        *a = cp - t_index;
        *b = AXIOM_UCD_HANGUL_T_BASE + t_index;
    }
    return true;
}

static bool axiom_hangul_compose(uint32_t a, uint32_t b, uint32_t* out) {
    /* L + V -> LV */
    if (a >= AXIOM_UCD_HANGUL_L_BASE && a < AXIOM_UCD_HANGUL_L_BASE + AXIOM_UCD_HANGUL_L_COUNT &&
        b >= AXIOM_UCD_HANGUL_V_BASE && b < AXIOM_UCD_HANGUL_V_BASE + AXIOM_UCD_HANGUL_V_COUNT) {
        uint32_t l_index = a - AXIOM_UCD_HANGUL_L_BASE;
        uint32_t v_index = b - AXIOM_UCD_HANGUL_V_BASE;
        *out = AXIOM_UCD_HANGUL_S_BASE +
               (l_index * AXIOM_UCD_HANGUL_V_COUNT + v_index) * AXIOM_UCD_HANGUL_T_COUNT;
        return true;
    }
    /* LV + T -> LVT */
    if (a >= AXIOM_UCD_HANGUL_S_BASE && a < AXIOM_UCD_HANGUL_S_BASE + AXIOM_UCD_HANGUL_S_COUNT &&
        ((a - AXIOM_UCD_HANGUL_S_BASE) % AXIOM_UCD_HANGUL_T_COUNT) == 0 &&
        b > AXIOM_UCD_HANGUL_T_BASE && b < AXIOM_UCD_HANGUL_T_BASE + AXIOM_UCD_HANGUL_T_COUNT) {
        *out = a + (b - AXIOM_UCD_HANGUL_T_BASE);
        return true;
    }
    return false;
}

/* Tek bir kod noktasını (özyinelemeli) tam ayrıştırır. */
static bool axiom_ucd_decompose_cp(uint32_t cp, axiom_cpbuf_t* out) {
    uint32_t a, b;
    if (axiom_hangul_decompose(cp, &a, &b)) {
        if (!axiom_ucd_decompose_cp(a, out)) return false;
        return axiom_ucd_decompose_cp(b, out);
    }
    const axiom_ucd_decomp_t* d = axiom_ucd_find_decomp(cp);
    if (d) {
        if (!axiom_ucd_decompose_cp(d->a, out)) return false;
        if (d->b && !axiom_ucd_decompose_cp(d->b, out)) return false;
        return true;
    }
    return axiom_cpbuf_push(out, cp);
}

/* Kanonik sıralama: eşit ccc'de özgün sıra korunur (kararlı). */
static void axiom_ucd_canonical_order(axiom_cpbuf_t* b) {
    size_t i = 1;
    while (i < b->len) {
        uint8_t c = axiom_ucd_ccc_of(b->cp[i]);
        if (c == 0) { i++; continue; }
        size_t j = i;
        while (j > 0) {
            uint8_t prev = axiom_ucd_ccc_of(b->cp[j - 1]);
            if (prev == 0 || prev <= c) break;
            uint32_t tmp = b->cp[j];
            b->cp[j] = b->cp[j - 1];
            b->cp[j - 1] = tmp;
            j--;
        }
        i++;
    }
}

/* UTF-8 -> kod noktası dizisi */
static bool axiom_ucd_decode(const char* s, axiom_cpbuf_t* out) {
    ax_int offset = 0;
    for (;;) {
        ax_int cp = axiom_utf8_next_codepoint(s, &offset);
        if (cp == -1) break;
        if (!axiom_cpbuf_push(out, (uint32_t)cp)) return false;
    }
    return true;
}

/* Kod noktası dizisi -> UTF-8 (sahipli string) */
static ax_str axiom_ucd_encode(const axiom_cpbuf_t* b) {
    size_t cap = b->len * 4 + 1;
    char* buf = (char*)malloc(cap);
    if (!buf) return axiom_owned_str_wrap("");
    char* dst = buf;
    for (size_t i = 0; i < b->len; i++) {
        axiom_utf8_encode_cp(&dst, (ax_int)b->cp[i]);
    }
    *dst = '\0';
    return axiom_owned_str_wrap(buf);
}

AXIOM_RUNTIME_FN ax_str axiom_unicode_nfd(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    axiom_cpbuf_t decoded = {NULL, 0, 0};
    if (!axiom_ucd_decode(s, &decoded)) {
        free(decoded.cp);
        return axiom_owned_str_wrap("");
    }
    axiom_cpbuf_t out = {NULL, 0, 0};
    bool ok = true;
    for (size_t i = 0; i < decoded.len && ok; i++) {
        ok = axiom_ucd_decompose_cp(decoded.cp[i], &out);
    }
    free(decoded.cp);
    if (!ok) { free(out.cp); return axiom_owned_str_wrap(""); }
    axiom_ucd_canonical_order(&out);
    ax_str res = axiom_ucd_encode(&out);
    free(out.cp);
    return res;
}

AXIOM_RUNTIME_FN ax_str axiom_unicode_nfc(const char* s) {
    if (!s) return axiom_owned_str_wrap("");

    /* 1) NFD'ye indir */
    axiom_cpbuf_t decoded = {NULL, 0, 0};
    if (!axiom_ucd_decode(s, &decoded)) {
        free(decoded.cp);
        return axiom_owned_str_wrap("");
    }
    axiom_cpbuf_t nfd = {NULL, 0, 0};
    bool ok = true;
    for (size_t i = 0; i < decoded.len && ok; i++) {
        ok = axiom_ucd_decompose_cp(decoded.cp[i], &nfd);
    }
    free(decoded.cp);
    if (!ok) { free(nfd.cp); return axiom_owned_str_wrap(""); }
    axiom_ucd_canonical_order(&nfd);

    if (nfd.len == 0) { free(nfd.cp); return axiom_owned_str_wrap(""); }

    /* 2) Kanonik birleştirme (D117) */
    axiom_cpbuf_t out = {NULL, 0, 0};
    if (!axiom_cpbuf_push(&out, nfd.cp[0])) { free(nfd.cp); free(out.cp); return axiom_owned_str_wrap(""); }
    size_t starter_pos = 0;
    uint32_t starter = nfd.cp[0];
    uint8_t last_ccc = 0;

    for (size_t i = 1; i < nfd.len; i++) {
        uint32_t ch = nfd.cp[i];
        uint8_t c = axiom_ucd_ccc_of(ch);
        uint32_t composite = 0;
        bool composed = false;

        if (last_ccc < c || last_ccc == 0) {
            composed = axiom_ucd_compose_pair(starter, ch, &composite);
            if (!composed) composed = axiom_hangul_compose(starter, ch, &composite);
        }

        if (composed) {
            out.cp[starter_pos] = composite;
            starter = composite;
        } else {
            if (c == 0) {
                starter_pos = out.len;
                starter = ch;
            }
            last_ccc = c;
            if (!axiom_cpbuf_push(&out, ch)) break;
        }
    }
    free(nfd.cp);
    ax_str res = axiom_ucd_encode(&out);
    free(out.cp);
    return res;
}

/* Verilen metin zaten NFD mi? */
AXIOM_RUNTIME_FN ax_bool axiom_unicode_is_nfd(const char* s) {
    if (!s) return true;
    ax_str n = axiom_unicode_nfd(s);
    ax_bool eq = (strcmp(n, s) == 0);
    axiom_str_release(n);
    return eq;
}

/* Verilen metin zaten NFC mi? */
AXIOM_RUNTIME_FN ax_bool axiom_unicode_is_nfc(const char* s) {
    if (!s) return true;
    ax_str n = axiom_unicode_nfc(s);
    ax_bool eq = (strcmp(n, s) == 0);
    axiom_str_release(n);
    return eq;
}

/* "NFC" / "NFD" secici; digerleri icin bos + hata nedeni dondurur. */
AXIOM_RUNTIME_FN ax_str axiom_unicode_normalize(const char* s, const char* form) {
    if (!form) return axiom_owned_str_wrap("");
    if (strcmp(form, "NFC") == 0) return axiom_unicode_nfc(s);
    if (strcmp(form, "NFD") == 0) return axiom_unicode_nfd(s);
    return axiom_owned_str_wrap("");
}

AXIOM_RUNTIME_FN ax_str axiom_unicode_ucd_version(void) {
    return axiom_owned_str_wrap(strdup(AXIOM_UCD_VERSION));
}

AXIOM_RUNTIME_FN ax_str axiom_str_to_upper_tr(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    size_t in_len = strlen(s);
    char* out = (char*)malloc(in_len * 2 + 16);
    if (!out) return axiom_owned_str_wrap("");
    char* dst = out;
    ax_int offset = 0;
    while (s[offset] != '\0') {
        ax_int cp = axiom_utf8_next_codepoint(s, &offset);
        if (cp == -1) break;
        if (cp == 'i') {
            axiom_utf8_encode_cp(&dst, 0x0130);
        } else if (cp == 0x0131) {
            axiom_utf8_encode_cp(&dst, 'I');
        } else if (cp == 0x011F) {
            axiom_utf8_encode_cp(&dst, 0x011E);
        } else if (cp == 0x00FC) {
            axiom_utf8_encode_cp(&dst, 0x00DC);
        } else if (cp == 0x015F) {
            axiom_utf8_encode_cp(&dst, 0x015E);
        } else if (cp == 0x00F6) {
            axiom_utf8_encode_cp(&dst, 0x00D6);
        } else if (cp == 0x00E7) {
            axiom_utf8_encode_cp(&dst, 0x00C7);
        } else if (cp >= 'a' && cp <= 'z') {
            axiom_utf8_encode_cp(&dst, cp - 32);
        } else {
            axiom_utf8_encode_cp(&dst, cp);
        }
    }
    *dst = '\0';
    return axiom_owned_str_wrap(out);
}

AXIOM_RUNTIME_FN ax_str axiom_str_to_lower_tr(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    size_t in_len = strlen(s);
    char* out = (char*)malloc(in_len * 2 + 16);
    if (!out) return axiom_owned_str_wrap("");
    char* dst = out;
    ax_int offset = 0;
    while (s[offset] != '\0') {
        ax_int cp = axiom_utf8_next_codepoint(s, &offset);
        if (cp == -1) break;
        if (cp == 'I') {
            axiom_utf8_encode_cp(&dst, 0x0131);
        } else if (cp == 0x0130) {
            axiom_utf8_encode_cp(&dst, 'i');
        } else if (cp == 0x011E) {
            axiom_utf8_encode_cp(&dst, 0x011F);
        } else if (cp == 0x00DC) {
            axiom_utf8_encode_cp(&dst, 0x00FC);
        } else if (cp == 0x015E) {
            axiom_utf8_encode_cp(&dst, 0x015F);
        } else if (cp == 0x00D6) {
            axiom_utf8_encode_cp(&dst, 0x00F6);
        } else if (cp == 0x00C7) {
            axiom_utf8_encode_cp(&dst, 0x00E7);
        } else if (cp >= 'A' && cp <= 'Z') {
            axiom_utf8_encode_cp(&dst, cp + 32);
        } else {
            axiom_utf8_encode_cp(&dst, cp);
        }
    }
    *dst = '\0';
    return axiom_owned_str_wrap(out);
}

AXIOM_RUNTIME_FN ax_int axiom_str_char_code(const char* s, ax_int idx) {
    if (!s) return -1;
    size_t len = strlen(s);
    if (idx < 0 || (size_t)idx >= len) return -1;
    return (ax_int)((unsigned char)s[idx]);
}

/* Unicode kod noktasini UTF-8 olarak kodlar.
 *
 * NOT: Eski davranis 0..255 araligini *tek bayt* olarak yaziyordu; bu Latin-1
 * anlamina gelir ve U+0080..U+00FF icin gecersiz UTF-8 uretir. Artik her
 * kod noktasi dogru UTF-8 dizisine cevrilir (ASCII icin davranis ayni). */
AXIOM_RUNTIME_FN ax_str axiom_char_to_str(ax_int code) {
    if (code < 0 || code > 0x10FFFF) return axiom_owned_str_wrap("");
    if (code >= 0xD800 && code <= 0xDFFF) return axiom_owned_str_wrap("");

    char buf[5];
    char* dst = buf;
    axiom_utf8_encode_cp(&dst, code);
    *dst = '\0';

    size_t len = (size_t)(dst - buf);
    char* out = (char*)malloc(len + 1);
    if (!out) return axiom_owned_str_wrap("");
    memcpy(out, buf, len + 1);
    return axiom_owned_str_wrap(out);
}

AXIOM_RUNTIME_FN ax_int axiom_str_index_of(const char* s, const char* needle) {
    if (!s || !needle) return -1;
    const char* p = strstr(s, needle);
    if (!p) return -1;
    return (ax_int)(p - s);
}

/* YARA text `nocase`: locale-independent ASCII-only case folding. */
AXIOM_RUNTIME_FN ax_int axiom_ascii_case_find(const char* s, const char* needle) {
    if (!s || !needle) return -1;
    const unsigned char* hay = (const unsigned char*)s;
    const unsigned char* pat = (const unsigned char*)needle;
    size_t hay_len = strlen(s);
    size_t pat_len = strlen(needle);
    if (pat_len == 0) return 0;
    if (pat_len > hay_len) return -1;
    for (size_t i = 0; i <= hay_len - pat_len; i++) {
        size_t j = 0;
        while (j < pat_len) {
            unsigned char a = hay[i + j];
            unsigned char b = pat[j];
            if (a >= 'A' && a <= 'Z') a = (unsigned char)(a + ('a' - 'A'));
            if (b >= 'A' && b <= 'Z') b = (unsigned char)(b + ('a' - 'A'));
            if (a != b) break;
            j++;
        }
        if (j == pat_len) return (ax_int)i;
    }
    return -1;
}

static inline unsigned char axiom_yara_fold_ascii(unsigned char c) {
    if (c >= 'A' && c <= 'Z') return (unsigned char)(c + ('a' - 'A'));
    return c;
}

static inline int axiom_yara_is_alnum_ascii(unsigned char c) {
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9');
}

/* Flags: 1=nocase, 2=ascii, 8=fullword. */
AXIOM_RUNTIME_FN ax_int axiom_yara_find_text(const char* s, const char* needle,
                                              ax_int flags, ax_int min_offset,
                                              ax_int max_offset) {
    if (!s || !needle) return -1;
    const unsigned char* hay = (const unsigned char*)s;
    const unsigned char* pat = (const unsigned char*)needle;
    size_t hay_len = strlen(s);
    size_t pat_len = strlen(needle);
    if (pat_len == 0) return -1;
    int nocase = (flags & 1) != 0;
    int ascii = 1; /* ASCII is YARA's default; the modifier is explicit but optional. */
    int fullword = (flags & 8) != 0;
    ax_int ascii_best = -1;

    if (ascii && pat_len <= hay_len) {
        size_t last = hay_len - pat_len;
        if (max_offset >= 0 && (size_t)max_offset < last) last = (size_t)max_offset;
        size_t first = min_offset > 0 ? (size_t)min_offset : 0;
        for (size_t i = first; i <= last; i++) {
            size_t j = 0;
            while (j < pat_len) {
                unsigned char a = hay[i + j];
                unsigned char b = pat[j];
                if (nocase) { a = axiom_yara_fold_ascii(a); b = axiom_yara_fold_ascii(b); }
                if (a != b) break;
                j++;
            }
            if (j != pat_len) continue;
            if (fullword && ((i > 0 && axiom_yara_is_alnum_ascii(hay[i - 1])) ||
                             (i + pat_len < hay_len && axiom_yara_is_alnum_ascii(hay[i + pat_len])))) continue;
            ascii_best = (ax_int)i;
            break;
        }
    }

    return ascii_best;
}

/* Count text hits in one pass; overlapping occurrences are included.
 * Flags: 1=nocase, 8=fullword. */
AXIOM_RUNTIME_FN ax_int axiom_yara_count_text(const char* s, const char* needle, ax_int flags) {
    if (!s || !needle) return 0;
    const unsigned char* hay = (const unsigned char*)s;
    const unsigned char* pat = (const unsigned char*)needle;
    size_t hay_len = strlen(s);
    size_t pat_len = strlen(needle);
    if (pat_len == 0 || pat_len > hay_len) return 0;
    int nocase = (flags & 1) != 0;
    int fullword = (flags & 8) != 0;
    ax_int count = 0;
    size_t last = hay_len - pat_len;
    for (size_t i = 0; i <= last; i++) {
        size_t j = 0;
        while (j < pat_len) {
            unsigned char a = hay[i + j];
            unsigned char b = pat[j];
            if (nocase) { a = axiom_yara_fold_ascii(a); b = axiom_yara_fold_ascii(b); }
            if (a != b) break;
            j++;
        }
        if (j != pat_len) continue;
        if (fullword && ((i > 0 && axiom_yara_is_alnum_ascii(hay[i - 1])) ||
                         (i + pat_len < hay_len && axiom_yara_is_alnum_ascii(hay[i + pat_len])))) continue;
        count++;
    }
    return count;
}

/* Return the 1-based nth text match offset, including overlapping hits. */
AXIOM_RUNTIME_FN ax_int axiom_yara_nth_text_offset(const char* s, const char* needle,
                                                    ax_int flags, ax_int occurrence) {
    if (!s || !needle || occurrence <= 0) return -1;
    const unsigned char* hay = (const unsigned char*)s;
    const unsigned char* pat = (const unsigned char*)needle;
    size_t hay_len = strlen(s);
    size_t pat_len = strlen(needle);
    if (pat_len == 0 || pat_len > hay_len) return -1;
    int nocase = (flags & 1) != 0;
    int fullword = (flags & 8) != 0;
    ax_int seen = 0;
    size_t last = hay_len - pat_len;
    for (size_t i = 0; i <= last; i++) {
        size_t j = 0;
        while (j < pat_len) {
            unsigned char a = hay[i + j];
            unsigned char b = pat[j];
            if (nocase) { a = axiom_yara_fold_ascii(a); b = axiom_yara_fold_ascii(b); }
            if (a != b) break;
            j++;
        }
        if (j != pat_len) continue;
        if (fullword && ((i > 0 && axiom_yara_is_alnum_ascii(hay[i - 1])) ||
                         (i + pat_len < hay_len && axiom_yara_is_alnum_ascii(hay[i + pat_len])))) continue;
        seen++;
        if (seen == occurrence) return (ax_int)i;
    }
    return -1;
}

AXIOM_RUNTIME_FN ax_str axiom_str_replace(const char* s, const char* old_s, const char* new_s) {
    if (!s) return axiom_owned_str_wrap("");
    if (!old_s || old_s[0] == '\0') return axiom_safe_strdup(s);
    if (!new_s) new_s = "";
    size_t old_len = strlen(old_s);
    size_t new_len = strlen(new_s);
    size_t s_len = strlen(s);

    size_t count = 0;
    const char* p = s;
    while ((p = strstr(p, old_s)) != NULL) {
        count++;
        p += old_len;
    }
    if (count == 0) return axiom_safe_strdup(s);

    size_t result_len = s_len + count * (new_len - old_len);
    char* result = (char*)malloc(result_len + 1);
    if (!result) return axiom_owned_str_wrap("");

    char* dst = result;
    p = s;
    while (*p) {
        if (strncmp(p, old_s, old_len) == 0) {
            memcpy(dst, new_s, new_len);
            dst += new_len;
            p += old_len;
        } else {
            *dst++ = *p++;
        }
    }
    *dst = '\0';
    return axiom_owned_str_wrap(result);
}

AXIOM_RUNTIME_FN ax_array_str axiom_str_split(const char* s, const char* delim) {
    ax_array_str res;
    res.length = 0;
    res.data = NULL;
    if (!s) return res;
    if (!delim || delim[0] == '\0') {
        size_t slen = strlen(s);
        res.length = (ax_int)slen;
        res.data = (ax_str*)malloc(sizeof(ax_str) * slen);
        for (size_t i = 0; i < slen; i++) {
            char* cstr = (char*)malloc(2);
            cstr[0] = s[i];
            cstr[1] = '\0';
            res.data[i] = axiom_owned_str_wrap(cstr);
        }
        axiom_heap_buf_track((void*)res.data);
        return res;
    }

    size_t delim_len = strlen(delim);
    size_t count = 1;
    const char* p = s;
    while ((p = strstr(p, delim)) != NULL) {
        count++;
        p += delim_len;
    }

    res.length = (ax_int)count;
    res.data = (ax_str*)malloc(sizeof(ax_str) * count);
    p = s;
    size_t idx = 0;
    while (1) {
        const char* next = strstr(p, delim);
        if (!next) {
            res.data[idx++] = axiom_safe_strdup(p);
            break;
        }
        size_t seg_len = next - p;
        char* seg = (char*)malloc(seg_len + 1);
        memcpy(seg, p, seg_len);
        seg[seg_len] = '\0';
        res.data[idx++] = axiom_owned_str_wrap(seg);
        p = next + delim_len;
    }
    axiom_heap_buf_track((void*)res.data);
    return res;
}

AXIOM_RUNTIME_FN ax_str axiom_str_join(ax_array_str arr, const char* delim) {
    if (arr.length <= 0 || !arr.data) return axiom_owned_str_wrap("");
    if (!delim) delim = "";
    size_t dlen = strlen(delim);
    size_t total_len = 0;
    for (ax_int i = 0; i < arr.length; i++) {
        if (arr.data[i]) total_len += strlen(arr.data[i]);
        if (i < arr.length - 1) total_len += dlen;
    }
    char* buf = (char*)malloc(total_len + 1);
    if (!buf) return axiom_owned_str_wrap("");
    char* dst = buf;
    for (ax_int i = 0; i < arr.length; i++) {
        if (arr.data[i]) {
            size_t slen = strlen(arr.data[i]);
            memcpy(dst, arr.data[i], slen);
            dst += slen;
        }
        if (i < arr.length - 1) {
            memcpy(dst, delim, dlen);
            dst += dlen;
        }
    }
    *dst = '\0';
    return axiom_owned_str_wrap(buf);
}

/* LLVM ABI: struct-by-value yerine pointer alan sarmalayici.
 * clang, 24 baytlik ax_array_str'yi byval(ptr) olarak gecer; LLVM kod
 * ureticisi de bu sozlesmeyi kullanir. */
AXIOM_RUNTIME_FN ax_str axiom_str_join_ptr(const ax_array_str* arr, const char* delim) {
    if (!arr) return axiom_owned_str_wrap("");
    return axiom_str_join(*arr, delim);
}

/* Dinamik Dizi Yardımcıları */
AXIOM_RUNTIME_FN ax_array_int axiom_array_create_int(ax_int size) {
    ax_array_int arr;
    arr.length = size < 0 ? 0 : size;
    arr.capacity = arr.length;
    arr.data = arr.length > 0 ? (ax_int*)calloc((size_t)arr.length, sizeof(ax_int)) : NULL;
    if (arr.data) axiom_heap_buf_track((void*)arr.data);
    return arr;
}

AXIOM_RUNTIME_FN ax_array_str axiom_array_create_str(ax_int size) {
    ax_array_str arr;
    arr.length = size < 0 ? 0 : size;
    arr.capacity = arr.length;
    arr.data = arr.length > 0 ? (ax_str*)calloc((size_t)arr.length, sizeof(ax_str)) : NULL;
    if (arr.data) {
        for (ax_int i = 0; i < arr.length; i++) arr.data[i] = "";
        axiom_heap_buf_track((void*)arr.data);
    }
    return arr;
}

AXIOM_RUNTIME_FN ax_array_int axiom_array_push_int(ax_array_int arr, ax_int val) {
    if (arr.data != NULL && arr.capacity > arr.length) {
        arr.data[arr.length] = val;
        arr.length += 1;
        return arr;
    }
    ax_int cap = arr.capacity > 0 ? arr.capacity * 2 : 8;
    if (cap <= arr.length) cap = arr.length + 1;
    ax_int* buf;
    if (arr.capacity > 0 && arr.data != NULL) {
        buf = (ax_int*)realloc((void*)arr.data, (size_t)cap * sizeof(ax_int));
        if (buf) axiom_heap_buf_track((void*)buf);
    } else {
        buf = (ax_int*)malloc((size_t)cap * sizeof(ax_int));
        if (buf && arr.length > 0 && arr.data) {
            memcpy(buf, arr.data, (size_t)arr.length * sizeof(ax_int));
        }
        if (buf) axiom_heap_buf_track((void*)buf);
    }
    if (!buf) {
        fprintf(stderr, "Axiom OOM: Bellek yetersiz!\n");
        exit(1);
    }
    buf[arr.length] = val;
    ax_array_int out;
    out.length = arr.length + 1;
    out.capacity = cap;
    out.data = buf;
    return out;
}

AXIOM_RUNTIME_FN ax_array_str axiom_array_push_str(ax_array_str arr, const char* val) {
    const char* item = val ? axiom_safe_strdup(val) : "";
    if (arr.data != NULL && arr.capacity > arr.length) {
        arr.data[arr.length] = item;
        arr.length += 1;
        return arr;
    }
    ax_int cap = arr.capacity > 0 ? arr.capacity * 2 : 8;
    if (cap <= arr.length) cap = arr.length + 1;
    ax_str* buf;
    if (arr.capacity > 0 && arr.data != NULL) {
        buf = (ax_str*)realloc((void*)arr.data, (size_t)cap * sizeof(ax_str));
        if (buf) axiom_heap_buf_track((void*)buf);
    } else {
        buf = (ax_str*)malloc((size_t)cap * sizeof(ax_str));
        if (buf && arr.length > 0 && arr.data) {
            memcpy(buf, arr.data, (size_t)arr.length * sizeof(ax_str));
        }
        if (buf) axiom_heap_buf_track((void*)buf);
    }
    if (!buf) {
        fprintf(stderr, "Axiom OOM: Bellek yetersiz!\n");
        exit(1);
    }
    buf[arr.length] = item;
    ax_array_str out;
    out.length = arr.length + 1;
    out.capacity = cap;
    out.data = buf;
    return out;
}

/* Yazdırma (Print) Rutinleri */
AXIOM_RUNTIME_FN void axiom_print_int(ax_int val) {
    printf("%" PRId64, val);
}

AXIOM_RUNTIME_FN void axiom_print_float(ax_float val) {
    printf("%g", val);
}

AXIOM_RUNTIME_FN void axiom_print_bool(ax_bool val) {
    printf("%s", val ? "true" : "false");
}

AXIOM_RUNTIME_FN void axiom_print_str(const char* val) {
    if (val) {
        fputs(val, stdout);
    }
}

AXIOM_RUNTIME_FN void axiom_print_newline(void) {
    putchar('\n');
}

/* Hata mesajini stderr'e yazar. `main -> Result` koprusu (C ve LLVM arka ucu)
 * ayni bicimi uretsin diye ortak: "[AXIOM HATA] <mesaj>\n". */
AXIOM_RUNTIME_FN void axiom_eprint_error(const char* msg) {
    if (msg) {
        fprintf(stderr, "[AXIOM HATA] %s\n", msg);
    }
}

#define axiom_print_auto(x) _Generic((x), \
    int: axiom_print_int, \
    long: axiom_print_int, \
    long long: axiom_print_int, \
    double: axiom_print_float, \
    float: axiom_print_float, \
    bool: axiom_print_bool, \
    char*: axiom_print_str, \
    const char*: axiom_print_str, \
    default: axiom_print_str \
)(x)

/* --- Yerel POSIX Ağ ve Sistem Zamanı Fonksiyonları --- */

/**
 * tcp_connect(host: str, port: int) -> int
 * Belirtilen host ve port'a TCP soketi ile bağlanır.
 * Başarılıysa socket fd döner, aksi halde -1 döner.
 */
/* --- Thread-safe IPv4 cozumleme -------------------------------------------
 * `gethostbyname` **statik bir tampon** dondurur; POSIX'te MT-Unsafe'tir.
 * Ayni anda birden fazla is parcacigi cagirinca (orn. examples/08 dort
 * thread ile tcp_connect) veri yarisi olusur: `hostent` yapisi baska bir
 * thread tarafindan ezilir, `h_length` bozulur ve memcpy tasabilir.
 * Belirti: aralikli SIGSEGV (exit -11 / 245).
 * `getaddrinfo` thread-safe'tir; sayisal adreslerde DNS'e hic gidilmez. */
AXIOM_RUNTIME_FN ax_int axiom_internal_resolve_ipv4(const char* host, struct in_addr* out) {
    if (!host || !out) return 0;
    if (inet_pton(AF_INET, host, out) == 1) return 1;

    struct addrinfo hints;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    struct addrinfo* res = NULL;
    if (getaddrinfo(host, NULL, &hints, &res) != 0 || !res) {
        return 0;
    }
    *out = ((struct sockaddr_in*)res->ai_addr)->sin_addr;
    freeaddrinfo(res);
    return 1;
}

AXIOM_RUNTIME_FN ax_int axiom_tcp_connect(const char* host, ax_int port) {
    if (!host || port <= 0 || port > 65535) return -1;

    int sock = ax_os_socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return -1;

    /* 2 saniyelik zaman aşımı (timeout) */
    ax_os_sock_set_timeout(ax_os_int_to_sock(sock), 2000);

    struct in_addr resolved;
    if (!axiom_internal_resolve_ipv4(host, &resolved)) {
        close(sock);
        return -1;
    }

    struct sockaddr_in serv_addr;
    memset(&serv_addr, 0, sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr = resolved;
    serv_addr.sin_port = htons((uint16_t)port);

    if (connect(sock, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) < 0) {
        close(sock);
        return -1;
    }

    return (ax_int)sock;
}

/**
 * tcp_send(fd: int, data: str) -> int
 * Sokete veri gönderir. Gönderilen bayt sayısını veya hata durumunda -1 döner.
 */
AXIOM_RUNTIME_FN ax_int axiom_tcp_send(ax_int fd, const char* data) {
    if (fd < 0 || !data) return -1;
    size_t len = strlen(data);
    ssize_t sent = send((int)fd, data, len, 0);
    return (ax_int)sent;
}

/**
 * tcp_recv(fd: int, max_len: int) -> str
 * Soketten en fazla max_len bayt okur ve string olarak döner.
 */

/**
 * tcp_recv_all(fd: int, max_bytes: int) -> str
 * Baglanti kapanana (EOF) veya max_bytes'a ulasana kadar okur.
 * Tek `recv` cagrisi buyuk yanitlari kesiyordu; bu dongu kullanir.
 */
AXIOM_RUNTIME_FN ax_str axiom_tcp_recv_all(ax_int fd, ax_int max_bytes) {
    if (fd < 0 || max_bytes <= 0) return axiom_owned_str_wrap("");
    size_t cap = (size_t)(max_bytes < 8192 ? max_bytes : 8192);
    size_t len = 0;
    char* buf = (char*)malloc(cap + 1);
    if (!buf) return axiom_owned_str_wrap("");

    for (;;) {
        if (len >= (size_t)max_bytes) break;
        size_t want = cap - len;
        if (want == 0) {
            size_t ncap = cap * 2;
            if (ncap > (size_t)max_bytes) ncap = (size_t)max_bytes;
            if (ncap <= cap) break;
            char* nb = (char*)realloc(buf, ncap + 1);
            if (!nb) break;
            buf = nb; cap = ncap;
            continue;
        }
        if (want > (size_t)max_bytes - len) want = (size_t)max_bytes - len;
        ssize_t r = recv((int)fd, buf + len, want, 0);
        if (r <= 0) break;   /* 0 = EOF, <0 = timeout/hata */
        len += (size_t)r;
    }
    buf[len] = '\0';
    return axiom_owned_str_wrap(buf);
}

/**
 * http_header_value(response, name) -> str
 * Yanit basliklarindan (govde ayiricisindan ONCE) buyuk/kucuk harf
 * duyarsiz sekilde baslik degeri cikarir. Yoksa "" doner.
 */
AXIOM_RUNTIME_FN ax_str axiom_http_header_value(const char* response, const char* name) {
    if (!response || !name) return axiom_owned_str_wrap("");
    const char* body = strstr(response, "\r\n\r\n");
    const char* end = body ? body : response + strlen(response);
    size_t nlen = strlen(name);
    const char* p = strstr(response, "\r\n");
    if (!p) return axiom_owned_str_wrap("");
    p += 2;
    while (p < end) {
        const char* eol = strstr(p, "\r\n");
        if (!eol || eol > end) eol = end;
        if ((size_t)(eol - p) > nlen && strncasecmp(p, name, nlen) == 0 && p[nlen] == ':') {
            const char* v = p + nlen + 1;
            while (v < eol && (*v == ' ' || *v == '\t')) v++;
            size_t vlen = (size_t)(eol - v);
            char* out = (char*)malloc(vlen + 1);
            if (!out) return axiom_owned_str_wrap("");
            memcpy(out, v, vlen);
            out[vlen] = '\0';
            return axiom_owned_str_wrap(out);
        }
        p = eol + 2;
    }
    return axiom_owned_str_wrap("");
}

/**
 * http_chunked_decode(body) -> str
 * "Transfer-Encoding: chunked" govdesini cozer. Bozuksa "" doner.
 * "0\r\n\r\n" sonlandiricisina kadar okur.
 */
AXIOM_RUNTIME_FN ax_str axiom_http_chunked_decode(const char* body) {
    if (!body) return axiom_owned_str_wrap("");
    size_t total = strlen(body);
    char* out = (char*)malloc(total + 1);
    if (!out) return axiom_owned_str_wrap("");
    size_t olen = 0;
    const char* p = body;

    for (;;) {
        /* chunk boyutu (hex) */
        char* endp = NULL;
        long sz = strtol(p, &endp, 16);
        if (endp == p || sz < 0) { free(out); return axiom_owned_str_wrap(""); }
        while (*endp == ';') {           /* chunk extension: atla */
            while (*endp && *endp != '\r') endp++;
            break;
        }
        if (*endp == '\r' && *(endp + 1) == '\n') endp += 2;
        else if (*endp == '\n') endp += 1;
        else { free(out); return axiom_owned_str_wrap(""); }

        if (sz == 0) break;              /* son chunk */
        if ((size_t)sz > total - (size_t)(endp - body)) { free(out); return axiom_owned_str_wrap(""); }
        memcpy(out + olen, endp, (size_t)sz);
        olen += (size_t)sz;
        p = endp + sz;
        if (*p == '\r' && *(p + 1) == '\n') p += 2;
        else if (*p == '\n') p += 1;
        else { free(out); return axiom_owned_str_wrap(""); }
    }
    out[olen] = '\0';
    return axiom_owned_str_wrap(out);
}

/**
 * tcp_set_timeout(fd: int, ms: int) -> int
 */
AXIOM_RUNTIME_FN ax_int axiom_tcp_set_timeout(ax_int fd, ax_int ms) {
    if (fd < 0 || ms < 0) return -1;
    return ax_os_sock_set_timeout(ax_os_int_to_sock(fd), (long long)ms);
}

AXIOM_RUNTIME_FN ax_str axiom_tcp_recv(ax_int fd, ax_int max_len) {
    if (fd < 0 || max_len <= 0) return axiom_owned_str_wrap("");
    char* buf = (char*)malloc(max_len + 1);
    if (!buf) return axiom_owned_str_wrap("");
    ssize_t received = recv((int)fd, buf, max_len, 0);
    if (received <= 0) {
        free(buf);
        return axiom_owned_str_wrap("");
    }
    buf[received] = '\0';
    return axiom_owned_str_wrap(buf);
}

/**
 * socket_close(fd: int) -> void
 * Soketi kapatır.
 */
AXIOM_RUNTIME_FN void axiom_socket_close(ax_int fd) {
    if (fd >= 0) {
        close((int)fd);
    }
}

/**
 * time_now_ms() -> int
 * Unix epoch'tan itibaren geçen süreyi milisaniye olarak döner.
 */
AXIOM_RUNTIME_FN ax_int axiom_time_now_ms(void) {
    return (ax_int)ax_os_time_ms();
}

/* --- Dosya Giriş/Çıkış (File I/O) ve Sistem Çağrıları --- */

/**
 * file_read(path: str) -> str
 * Belirtilen dosyanın tüm içeriğini metin olarak okur.
 * Dosya bulunamazsa veya açılamazsa boş metin ("") döner.
 */
AXIOM_RUNTIME_FN ax_str axiom_file_read(const char* path) {
    if (!path) return axiom_owned_str_wrap("");
    FILE* f = fopen(path, "rb");
    if (!f) return axiom_owned_str_wrap("");

    /* Normal dosyalar: boyutu one al ve tek okumada al. */
    if (fseek(f, 0, SEEK_END) == 0) {
        long size = ftell(f);
        if (size > 0) {
            if (fseek(f, 0, SEEK_SET) != 0) {
                fclose(f);
                return axiom_owned_str_wrap("");
            }
            char* buf = (char*)malloc((size_t)size + 1);
            if (!buf) {
                fclose(f);
                return axiom_owned_str_wrap("");
            }
            size_t read_bytes = fread(buf, 1, (size_t)size, f);
            buf[read_bytes] = '\0';
            fclose(f);
            return axiom_owned_str_wrap(buf);
        }
    }

    /* procfs/sysfs gibi boyutu 0 gorunen sanal dosyalar: akisa gore oku. */
    if (fseek(f, 0, SEEK_SET) != 0) {
        /* Aranmayan (pipe) dosyalar icin konum zaten bastadir. */
    }
    size_t cap = 4096, len = 0;
    char* buf = (char*)malloc(cap);
    if (!buf) {
        fclose(f);
        return axiom_owned_str_wrap("");
    }
    size_t n;
    while ((n = fread(buf + len, 1, cap - len - 1, f)) > 0) {
        len += n;
        if (len + 1 >= cap) {
            size_t new_cap = cap * 2;
            char* grown = (char*)realloc(buf, new_cap);
            if (!grown) break;
            buf = grown;
            cap = new_cap;
        }
    }
    buf[len] = '\0';
    fclose(f);
    return axiom_owned_str_wrap(buf);
}

/**
 * file_write(path: str, content: str) -> bool
 * Belirtilen dosyaya metin yazar (mevcut dosyanın üzerine yazar veya yenisini oluşturur).
 * Başarılıysa true, hata durumunda false döner.
 */
AXIOM_RUNTIME_FN ax_bool axiom_file_write(const char* path, const char* content) {
    if (!path) return false;
    FILE* f = fopen(path, "wb");
    if (!f) return false;
    if (content) {
        size_t len = strlen(content);
        if (len > 0) {
            size_t written = fwrite(content, 1, len, f);
            if (written < len) {
                fclose(f);
                return false;
            }
        }
    }
    fclose(f);
    return true;
}

/**
 * file_exists(path: str) -> bool
 * Belirtilen yolun mevcut olup olmadığını doğrular.
 */
AXIOM_RUNTIME_FN ax_bool axiom_file_exists(const char* path) {
    if (!path) return false;
    return access(path, F_OK) == 0;
}

/**
 * file_size(path: str) -> int
 * Normal dosyanin bayt boyutunu dondurur; hata durumunda -1.
 */
AXIOM_RUNTIME_FN ax_int axiom_file_size(const char* path) {
    if (!path) return -1;
    struct stat st;
    if (stat(path, &st) != 0) return -1;
    if (!S_ISREG(st.st_mode)) return -1;
    return (ax_int)st.st_size;
}

/**
 * is_directory(path: str) -> bool
 */
AXIOM_RUNTIME_FN ax_bool axiom_is_directory(const char* path) {
    if (!path) return false;
    struct stat st;
    if (stat(path, &st) != 0) return false;
    return S_ISDIR(st.st_mode);
}

/**
 * list_dir(path: str) -> str
 * Dizin girdilerini satir satir (sirali, "." ve ".." haric) dondurur.
 * Hata durumunda bos metin.
 */
static int axiom_cmp_str_ptr(const void* a, const void* b) {
    const char* sa = *(const char* const*)a;
    const char* sb = *(const char* const*)b;
    return strcmp(sa, sb);
}

AXIOM_RUNTIME_FN ax_str axiom_list_dir(const char* path) {
    if (!path || path[0] == '\0') return axiom_owned_str_wrap("");
    ax_os_dir_t d;
    if (ax_os_dir_open(&d, path) != 0) return axiom_owned_str_wrap("");

    size_t cap = 256, count = 0;
    char** names = (char**)malloc(cap * sizeof(char*));
    if (!names) { ax_os_dir_close(&d); return axiom_owned_str_wrap(""); }

    const char* nm;
    while ((nm = ax_os_dir_next(&d)) != NULL) {
        if (count == cap) {
            size_t ncap = cap * 2;
            char** grown = (char**)realloc(names, ncap * sizeof(char*));
            if (!grown) break;
            names = grown;
            cap = ncap;
        }
        size_t len = strlen(nm);
        char* copy = (char*)malloc(len + 1);
        if (!copy) break;
        memcpy(copy, nm, len + 1);
        names[count++] = copy;
    }
    ax_os_dir_close(&d);

    /* Deterministik cikti: sozluk sirasi. */
    qsort(names, count, sizeof(char*), axiom_cmp_str_ptr);

    size_t total = 0;
    for (size_t k = 0; k < count; k++) total += strlen(names[k]) + 1;
    char* out = (char*)malloc(total + 1);
    if (!out) {
        for (size_t k = 0; k < count; k++) free(names[k]);
        free(names);
        return axiom_owned_str_wrap("");
    }
    char* dst = out;
    for (size_t k = 0; k < count; k++) {
        size_t len = strlen(names[k]);
        memcpy(dst, names[k], len);
        dst += len;
        *dst++ = '\n';
        free(names[k]);
    }
    *dst = '\0';
    free(names);
    return axiom_owned_str_wrap(out);
}

/**
 * remove_file(path: str) -> bool
 * Dosyayi (veya bos dizini) siler.
 */
AXIOM_RUNTIME_FN ax_bool axiom_remove_file(const char* path) {
    if (!path || path[0] == '\0') return false;
    struct stat st;
    if (stat(path, &st) != 0) return false;
    if (S_ISDIR(st.st_mode)) return rmdir(path) == 0;
    return unlink(path) == 0;
}

/**
 * rename_file(from: str, to: str) -> bool
 */
AXIOM_RUNTIME_FN ax_bool axiom_rename_file(const char* from, const char* to) {
    if (!from || !to || from[0] == '\0' || to[0] == '\0') return false;
    return rename(from, to) == 0;
}

/**
 * create_dir(path: str) -> bool
 * Ara dizinleri de olusturur (mkdir -p semantigi).
 */
AXIOM_RUNTIME_FN ax_bool axiom_create_dir(const char* path) {
    if (!path || path[0] == '\0') return false;
    if (axiom_is_directory(path)) return true;

    size_t len = strlen(path);
    char* tmp = (char*)malloc(len + 1);
    if (!tmp) return false;
    memcpy(tmp, path, len + 1);

    /* Sondaki '/' karakterlerini kirp. */
    while (len > 1 && tmp[len - 1] == '/') tmp[--len] = '\0';

    for (char* p = tmp + 1; *p; p++) {
        if (*p != '/') continue;
        *p = '\0';
        if (ax_os_mkdir(tmp) != 0 && errno != EEXIST) {
            free(tmp);
            return false;
        }
        *p = '/';
    }
    bool ok = (ax_os_mkdir(tmp) == 0) || (errno == EEXIST);
    free(tmp);
    return ok;
}

/**
 * os_exec(cmd: str) -> int
 * İşletim sistemi kabuk komutunu çalıştırır ve çıkış kodunu (exit code) döner.
 */
AXIOM_RUNTIME_FN ax_int axiom_os_exec(const char* cmd) {
    if (!cmd) return -1;
    return (ax_int)ax_os_run_shell(cmd);
}

/**
 * os_exec_argv(argv: str[]) -> int
 * Shell cagrisi yapmadan doğrudan execvp ile calistirir; komut enjeksiyonunu onler.
 */
AXIOM_RUNTIME_FN ax_int axiom_os_exec_argv(ax_array_str argv) {
    if (argv.length <= 0 || !argv.data) return -1;
    char** c_argv = (char**)malloc((size_t)(argv.length + 1) * sizeof(char*));
    if (!c_argv) return -1;
    for (ax_int i = 0; i < argv.length; i++) {
        c_argv[i] = (char*)(argv.data[i] ? argv.data[i] : "");
    }
    c_argv[argv.length] = NULL;

    long long rc = ax_os_run_argv(c_argv);
    free(c_argv);
    return (ax_int)rc;
}

/**
 * compile_c(c_file: str, out_bin: str) -> int
 * Clang derleyicisini kabuk cagrisi olmadan dogrudan execvp ile calistirir.
 * Shell injection ve komut enjeksiyonu risklerini tamamen bertaraf eder.
 */
AXIOM_RUNTIME_FN ax_int axiom_compile_c(const char* c_file, const char* out_bin) {
    if (!c_file || !out_bin) return -1;
    char* const argv[] = {
        (char*)"clang",
        (char*)"-O3",
        (char*)"-Wall",
        (char*)"-Wno-parentheses-equality",
        (char*)"-Wno-unused-variable",
        (char*)"-Wno-unused-but-set-variable",
        (char*)"-Wno-unused-function",
        (char*)"-Wno-unused-label",
        (char*)"-Werror=incompatible-pointer-types",
        (char*)"-Werror=int-conversion",
        (char*)"-Werror=return-type",
        (char*)"-Werror=pointer-bool-conversion",
        (char*)"-Werror=string-compare",
        (char*)"-Werror=pointer-to-int-cast",
        (char*)"-Werror=int-to-pointer-cast",
        (char*)"-pthread",
        (char*)c_file,
        (char*)"-lz",
        (char*)"-lssl",
        (char*)"-lcrypto",
        (char*)"-ldl",
        (char*)"-lm",
        (char*)"-o",
        (char*)out_bin,
        NULL
    };
    long long rc = ax_os_run_argv(argv);
    return (ax_int)rc;
}

/**
 * os_getenv(key: str) -> str
 * Belirtilen çevre değişkeninin (environment variable) değerini döner.
 * Tanımlı değilse boş metin ("") döner.
 */
AXIOM_RUNTIME_FN ax_str axiom_os_getenv(const char* key) {
    if (!key) return "";
    const char* val = getenv(key);
    /* getenv isaretcisi environ dizisine bakar (heap/stack); intrusive header
     * modelinde sahipsiz heap isaretcisi birakmamak icin sahipli kopya doner. */
    if (!val) return "";
    return axiom_safe_strdup(val);
}

/* --- Yüksek Performanslı Metin ve Matematik Yardımcıları --- */

/**
 * str_contains(s: str, sub: str) -> bool
 */
AXIOM_RUNTIME_FN ax_bool axiom_str_contains(const char* s, const char* sub) {
    if (!s || !sub) return false;
    return strstr(s, sub) != NULL;
}

/**
 * str_starts_with(s: str, prefix: str) -> bool
 */
AXIOM_RUNTIME_FN ax_bool axiom_str_starts_with(const char* s, const char* prefix) {
    if (!s || !prefix) return false;
    size_t plen = strlen(prefix);
    size_t slen = strlen(s);
    if (slen < plen) return false;
    return strncmp(s, prefix, plen) == 0;
}

/**
 * str_ends_with(s: str, suffix: str) -> bool
 */
AXIOM_RUNTIME_FN ax_bool axiom_str_ends_with(const char* s, const char* suffix) {
    if (!s || !suffix) return false;
    size_t suflen = strlen(suffix);
    size_t slen = strlen(s);
    if (slen < suflen) return false;
    return strcmp(s + (slen - suflen), suffix) == 0;
}

/**
 * str_trim(s: str) -> str
 */
AXIOM_RUNTIME_FN ax_str axiom_str_trim(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    while (*s && isspace((unsigned char)*s)) {
        s++;
    }
    if (*s == '\0') {
        return axiom_owned_str_wrap("");
    }
    const char* end = s + strlen(s) - 1;
    while (end > s && isspace((unsigned char)*end)) {
        end--;
    }
    size_t len = (size_t)(end - s + 1);
    char* result = axiom_str_alloc(len);
    memcpy(result, s, len);
    result[len] = '\0';
    return result;
}

/**
 * str_to_int(s: str) -> int
 */
AXIOM_RUNTIME_FN ax_int axiom_str_to_int(const char* s) {
    if (!s) return 0;
    return (ax_int)strtoll(s, NULL, 10);
}

/**
 * int_to_str(val: int) -> str
 */
AXIOM_RUNTIME_FN ax_str axiom_int_to_str(ax_int val) {
    char buf[64];
    int n = snprintf(buf, sizeof(buf), "%" PRId64, val);
    if (n < 0) return axiom_safe_strdup("");
    size_t len = (size_t)n;
    char* result = axiom_str_alloc(len);
    memcpy(result, buf, len + 1);
    return result;
}

/**
 * math_abs(x: int) -> int
 */
AXIOM_RUNTIME_FN ax_int axiom_math_abs(ax_int x) {
    return x < 0 ? -x : x;
}

/**
 * math_min(a: int, b: int) -> int
 */
AXIOM_RUNTIME_FN ax_int axiom_math_min(ax_int a, ax_int b) {
    return a < b ? a : b;
}

/**
 * math_max(a: int, b: int) -> int
 */
AXIOM_RUNTIME_FN ax_int axiom_math_max(ax_int a, ax_int b) {
    return a > b ? a : b;
}

/**
 * math_pow(base: int, exp: int) -> int
 */
AXIOM_RUNTIME_FN ax_int axiom_math_pow(ax_int base, ax_int exp) {
    if (exp < 0) return 0;
    ax_int result = 1;
    ax_int b = base;
    ax_int e = exp;
    while (e > 0) {
        if (e & 1) {
            result *= b;
        }
        b *= b;
        e >>= 1;
    }
    return result;
}

/* --- Çok İş Parçacıklı Eşzamanlılık (Pthreads & Concurrency) --- */

#define MAX_AXIOM_THREADS 4096
#define MAX_AXIOM_MUTEXES 2048
#define MAX_AXIOM_ATOMICS 2048

static ax_thread_t axiom_thread_table[MAX_AXIOM_THREADS];
static atomic_int_fast64_t axiom_thread_counter = 1;

typedef struct {
    void* fn;
    ax_int arg;
    bool is_void;
} axiom_thread_payload_t;

AXIOM_RUNTIME_FN void* axiom_thread_trampoline(void* p) {
    axiom_thread_payload_t* payload = (axiom_thread_payload_t*)p;
    void* fn = payload->fn;
    ax_int arg = payload->arg;
    bool is_void = payload->is_void;
    free(payload);
    if (is_void) {
        ((void (*)(ax_int))fn)(arg);
        return NULL;
    } else {
        ax_int res = ((ax_int (*)(ax_int))fn)(arg);
        return (void*)(intptr_t)res;
    }
}

/**
 * thread_create(fn_name, arg: int) -> int
 * POSIX pthread_create sarmalayıcısı. Başarılıysa thread id (>= 1), hata durumunda -1 döner.
 */
AXIOM_RUNTIME_FN ax_int axiom_thread_create(void* fn, ax_int arg, bool is_void) {
    if (!fn) return -1;
    ax_int th_id = atomic_fetch_add(&axiom_thread_counter, 1);
    if (th_id >= MAX_AXIOM_THREADS) {
        return -1;
    }
    axiom_thread_payload_t* payload = (axiom_thread_payload_t*)malloc(sizeof(axiom_thread_payload_t));
    if (!payload) return -1;
    payload->fn = fn;
    payload->arg = arg;
    payload->is_void = is_void;

    ax_thread_t t = ax_os_thread_create(axiom_thread_trampoline, payload);
    if (!t) {
        free(payload);
        return -1;
    }
    axiom_thread_table[th_id] = t;
    return th_id;
}

/**
 * thread_join(th_id: int) -> int
 * Belirtilen thread'in tamamlanmasını bekler ve fonksiyonun döndürdüğü değeri (varsa) int olarak döner.
 */
AXIOM_RUNTIME_FN ax_int axiom_thread_join(ax_int th_id) {
    if (th_id <= 0 || th_id >= MAX_AXIOM_THREADS) return -1;
    long long rc = ax_os_thread_join(axiom_thread_table[th_id]);
    return (ax_int)rc;
}

/* --- Mutex Mekanizması --- */
static ax_mutex_t axiom_mutex_table[MAX_AXIOM_MUTEXES];
static atomic_int_fast64_t axiom_mutex_counter = 1;

/**
 * mutex_init() -> int
 * Yeni bir POSIX mutex ilklendirir ve mutex id'sini döner.
 */
AXIOM_RUNTIME_FN ax_int axiom_mutex_init(void) {
    ax_int m_id = atomic_fetch_add(&axiom_mutex_counter, 1);
    if (m_id >= MAX_AXIOM_MUTEXES) return -1;
    ax_os_mutex_init(&axiom_mutex_table[m_id]);
    return m_id;
}

/**
 * mutex_lock(m_id: int) -> void
 * Belirtilen mutex'i kilitler.
 */
AXIOM_RUNTIME_FN void axiom_mutex_lock(ax_int m_id) {
    if (m_id > 0 && m_id < MAX_AXIOM_MUTEXES) {
        ax_os_mutex_lock(&axiom_mutex_table[m_id]);
    }
}

/**
 * mutex_unlock(m_id: int) -> void
 * Belirtilen mutex kilidini açar.
 */
AXIOM_RUNTIME_FN void axiom_mutex_unlock(ax_int m_id) {
    if (m_id > 0 && m_id < MAX_AXIOM_MUTEXES) {
        ax_os_mutex_unlock(&axiom_mutex_table[m_id]);
    }
}

/* --- Atomic Sayaçlar --- */
static atomic_int_fast64_t axiom_atomic_table[MAX_AXIOM_ATOMICS];
static atomic_int_fast64_t axiom_atomic_counter = 1;

/**
 * atomic_init(val: int) -> int
 * Yeni bir atomik sayaç başlatır ve id'sini döner.
 */
AXIOM_RUNTIME_FN ax_int axiom_atomic_init(ax_int val) {
    ax_int a_id = atomic_fetch_add(&axiom_atomic_counter, 1);
    if (a_id >= MAX_AXIOM_ATOMICS) return -1;
    atomic_store(&axiom_atomic_table[a_id], val);
    return a_id;
}

/**
 * atomic_add(counter_id: int, val: int) -> int
 * Belirtilen atomik sayaca val ekler ve ekleme sonrası yeni güncel değeri döner.
 */
AXIOM_RUNTIME_FN ax_int axiom_atomic_add(ax_int counter_id, ax_int val) {
    if (counter_id > 0 && counter_id < MAX_AXIOM_ATOMICS) {
        return (ax_int)(atomic_fetch_add(&axiom_atomic_table[counter_id], val) + val);
    }
    return 0;
}

/**
 * atomic_get(counter_id: int) -> int
 * Belirtilen atomik sayacın değerini okur.
 */
AXIOM_RUNTIME_FN ax_int axiom_atomic_get(ax_int counter_id) {
    if (counter_id > 0 && counter_id < MAX_AXIOM_ATOMICS) {
        return (ax_int)atomic_load(&axiom_atomic_table[counter_id]);
    }
    return 0;
}

/**
 * sleep_ms(ms: int) -> void
 * Belirtilen milisaniye kadar iş parçacığını uyutur.
 */
AXIOM_RUNTIME_FN void axiom_sleep_ms(ax_int ms) {
    if (ms > 0) ax_os_sleep_ms((long long)ms);
}

/* ========================================================================= */
/* --- Heterojen & SIMD Vektör Hızlandırma Altyapısı (AVX2 / SSE / NEON) --- */
/* ========================================================================= */

typedef int64_t ax_simd_i64 __attribute__((vector_size(32)));
typedef double  ax_simd_f64 __attribute__((vector_size(32)));

/**
 * 4x64-bit SIMD Paralel Toplama: a + b
 */
/* --- LLVM koprusu icin pointer tabanli SIMD sarmalayicilari ---
 * LLVM IR'de 24 baytlik struct'lari degerle gecirmek SysV ABI ile
 * C tarafindaki derlenmis imza arasinda uyumsuzluga yol acabiliyor.
 * Bu sarmalayicilar yalnizca pointer alir; IR tarafi alloca+store kullanir. */
AXIOM_RUNTIME_FN void axiom_simd_add_i64_ptr(ax_array_int* out, const ax_array_int* a, const ax_array_int* b);
AXIOM_RUNTIME_FN void axiom_simd_mul_i64_ptr(ax_array_int* out, const ax_array_int* a, const ax_array_int* b);
AXIOM_RUNTIME_FN void axiom_simd_sub_i64_ptr(ax_array_int* out, const ax_array_int* a, const ax_array_int* b);
AXIOM_RUNTIME_FN ax_int axiom_simd_sum_i64_ptr(const ax_array_int* a);
AXIOM_RUNTIME_FN ax_int axiom_simd_scan_match_ptr(const ax_array_int* a, ax_int target);

AXIOM_RUNTIME_FN ax_array_int axiom_simd_add_i64(ax_array_int a, ax_array_int b) {
    ax_int len = a.length < b.length ? a.length : b.length;
    ax_int* res_data = (ax_int*)malloc(len * sizeof(ax_int));
    if (!res_data && len > 0) {
        fprintf(stderr, "Axiom SIMD OOM: Bellek yetersiz!\n");
        exit(1);
    }
    ax_int i = 0;
    for (; i + 4 <= len; i += 4) {
        ax_simd_i64 va, vb, vr;
        memcpy(&va, &a.data[i], sizeof(ax_simd_i64));
        memcpy(&vb, &b.data[i], sizeof(ax_simd_i64));
        vr = va + vb;
        memcpy(&res_data[i], &vr, sizeof(ax_simd_i64));
    }
    for (; i < len; i++) {
        res_data[i] = a.data[i] + b.data[i];
    }
    ax_array_int ret = { .length = len, .capacity = len, .data = res_data };
    axiom_heap_buf_track((void*)res_data);
    return ret;
}

/**
 * 4x64-bit SIMD Paralel Çarpma: a * b
 */
AXIOM_RUNTIME_FN ax_array_int axiom_simd_mul_i64(ax_array_int a, ax_array_int b) {
    ax_int len = a.length < b.length ? a.length : b.length;
    ax_int* res_data = (ax_int*)malloc(len * sizeof(ax_int));
    if (!res_data && len > 0) {
        fprintf(stderr, "Axiom SIMD OOM: Bellek yetersiz!\n");
        exit(1);
    }
    ax_int i = 0;
    for (; i + 4 <= len; i += 4) {
        ax_simd_i64 va, vb, vr;
        memcpy(&va, &a.data[i], sizeof(ax_simd_i64));
        memcpy(&vb, &b.data[i], sizeof(ax_simd_i64));
        vr = va * vb;
        memcpy(&res_data[i], &vr, sizeof(ax_simd_i64));
    }
    for (; i < len; i++) {
        res_data[i] = a.data[i] * b.data[i];
    }
    ax_array_int ret = { .length = len, .capacity = len, .data = res_data };
    axiom_heap_buf_track((void*)res_data);
    return ret;
}

/**
 * 4x64-bit SIMD Paralel Çıkarma: a - b
 */
AXIOM_RUNTIME_FN ax_array_int axiom_simd_sub_i64(ax_array_int a, ax_array_int b) {
    ax_int len = a.length < b.length ? a.length : b.length;
    ax_int* res_data = (ax_int*)malloc(len * sizeof(ax_int));
    if (!res_data && len > 0) {
        fprintf(stderr, "Axiom SIMD OOM: Bellek yetersiz!\n");
        exit(1);
    }
    ax_int i = 0;
    for (; i + 4 <= len; i += 4) {
        ax_simd_i64 va, vb, vr;
        memcpy(&va, &a.data[i], sizeof(ax_simd_i64));
        memcpy(&vb, &b.data[i], sizeof(ax_simd_i64));
        vr = va - vb;
        memcpy(&res_data[i], &vr, sizeof(ax_simd_i64));
    }
    for (; i < len; i++) {
        res_data[i] = a.data[i] - b.data[i];
    }
    ax_array_int ret = { .length = len, .capacity = len, .data = res_data };
    axiom_heap_buf_track((void*)res_data);
    return ret;
}

/**
 * 4x64-bit SIMD Paralel Toplam (Reduction): sum(arr)
 */
AXIOM_RUNTIME_FN ax_int axiom_simd_sum_i64(ax_array_int arr) {
    ax_simd_i64 vsum = {0, 0, 0, 0};
    ax_int i = 0;
    for (; i + 4 <= arr.length; i += 4) {
        ax_simd_i64 va;
        memcpy(&va, &arr.data[i], sizeof(ax_simd_i64));
        vsum += va;
    }
    ax_int total = vsum[0] + vsum[1] + vsum[2] + vsum[3];
    for (; i < arr.length; i++) {
        total += arr.data[i];
    }
    return total;
}

/**
 * 4x64-bit SIMD Paralel Eşleşme Taraması (Security/Vector Scan):
 * Belirtilen dizide hedef değeri arar ve eşleşen eleman sayısını döner.
 */
AXIOM_RUNTIME_FN ax_int axiom_simd_scan_match(ax_array_int arr, ax_int target) {
    ax_int count = 0;
    ax_int i = 0;
    for (; i + 4 <= arr.length; i += 4) {
        if (arr.data[i] == target) count++;
        if (arr.data[i + 1] == target) count++;
        if (arr.data[i + 2] == target) count++;
        if (arr.data[i + 3] == target) count++;
    }
    for (; i < arr.length; i++) {
        if (arr.data[i] == target) count++;
    }
    return count;
}

AXIOM_RUNTIME_FN void axiom_simd_add_i64_ptr(ax_array_int* out, const ax_array_int* a, const ax_array_int* b) {
    if (out && a && b) *out = axiom_simd_add_i64(*a, *b);
}
AXIOM_RUNTIME_FN void axiom_simd_mul_i64_ptr(ax_array_int* out, const ax_array_int* a, const ax_array_int* b) {
    if (out && a && b) *out = axiom_simd_mul_i64(*a, *b);
}
AXIOM_RUNTIME_FN void axiom_simd_sub_i64_ptr(ax_array_int* out, const ax_array_int* a, const ax_array_int* b) {
    if (out && a && b) *out = axiom_simd_sub_i64(*a, *b);
}
AXIOM_RUNTIME_FN ax_int axiom_simd_sum_i64_ptr(const ax_array_int* a) {
    return a ? axiom_simd_sum_i64(*a) : 0;
}
AXIOM_RUNTIME_FN ax_int axiom_simd_scan_match_ptr(const ax_array_int* a, ax_int target) {
    return a ? axiom_simd_scan_match(*a, target) : 0;
}

/* --- LLVM koprusu: dizi parametreli runtime fonksiyonlari icin pointer sarmalayicilar --- */
AXIOM_RUNTIME_FN ax_int axiom_os_exec_argv_ptr(const ax_array_str* argv);
AXIOM_RUNTIME_FN ax_str axiom_json_build_object_ptr(const ax_array_str* keys, const ax_array_str* values);
AXIOM_RUNTIME_FN void axiom_csv_add_row_ptr(ax_int handle, const ax_array_str* cols);
AXIOM_RUNTIME_FN void axiom_cli_set_args_ptr(const ax_array_str* args);


/* ========================================================================= */
/* --- Standart Kütüphane Paket 1: Encoding, Crypto, URL & JSON Çekirdeği --- */
/* ========================================================================= */


/* --- 1. Base64 Encode & Decode (RFC 4648) --- */
static const char AXIOM_B64_CHARS[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

AXIOM_RUNTIME_FN ax_str axiom_base64_encode(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    size_t in_len = strlen(s);
    if (in_len == 0) return axiom_owned_str_wrap("");

    size_t out_len = 4 * ((in_len + 2) / 3);
    char* out = (char*)malloc(out_len + 1);
    if (!out) return axiom_owned_str_wrap("");

    size_t i = 0, j = 0;
    while (i < in_len) {
        size_t remain = in_len - i;
        uint32_t octet_a = (unsigned char)s[i++];
        uint32_t octet_b = (remain > 1) ? (unsigned char)s[i++] : 0;
        uint32_t octet_c = (remain > 2) ? (unsigned char)s[i++] : 0;

        uint32_t triple = (octet_a << 16) | (octet_b << 8) | octet_c;

        out[j++] = AXIOM_B64_CHARS[(triple >> 18) & 0x3F];
        out[j++] = AXIOM_B64_CHARS[(triple >> 12) & 0x3F];
        out[j++] = (remain > 1) ? AXIOM_B64_CHARS[(triple >> 6) & 0x3F] : '=';
        out[j++] = (remain > 2) ? AXIOM_B64_CHARS[triple & 0x3F] : '=';
    }
    out[j] = '\0';
    return out;
}

AXIOM_RUNTIME_FN ax_str axiom_base64_decode(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    size_t in_len = strlen(s);
    if (in_len == 0) return axiom_owned_str_wrap("");

    static int b64_rev_tbl[256];
    static bool b64_inited = false;
    if (!b64_inited) {
        memset(b64_rev_tbl, -1, sizeof(b64_rev_tbl));
        for (int k = 0; k < 64; k++) {
            b64_rev_tbl[(unsigned char)AXIOM_B64_CHARS[k]] = k;
        }
        b64_inited = true;
    }

    size_t out_cap = (in_len / 4) * 3 + 4;
    char* out = (char*)malloc(out_cap);
    if (!out) return axiom_owned_str_wrap("");

    size_t j = 0;
    uint32_t buf = 0;
    int bits = 0;
    for (size_t i = 0; i < in_len; i++) {
        unsigned char c = (unsigned char)s[i];
        if (c == '=') break;
        int val = b64_rev_tbl[c];
        if (val < 0) continue;
        buf = (buf << 6) | (uint32_t)val;
        bits += 6;
        if (bits >= 8) {
            bits -= 8;
            out[j++] = (char)((buf >> bits) & 0xFF);
        }
    }
    out[j] = '\0';
    return axiom_owned_str_wrap(out);
}

/* --- 2. Hexadecimal Encode & Decode --- */
AXIOM_RUNTIME_FN ax_str axiom_hex_encode(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    size_t len = strlen(s);
    if (len == 0) return axiom_owned_str_wrap("");
    static const char hex_digits[] = "0123456789abcdef";
    char* out = (char*)malloc(len * 2 + 1);
    if (!out) return axiom_owned_str_wrap("");
    for (size_t i = 0; i < len; i++) {
        unsigned char b = (unsigned char)s[i];
        out[i * 2]     = hex_digits[(b >> 4) & 0x0F];
        out[i * 2 + 1] = hex_digits[b & 0x0F];
    }
    out[len * 2] = '\0';
    return axiom_owned_str_wrap(out);
}

AXIOM_RUNTIME_FN ax_str axiom_hex_decode(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    size_t len = strlen(s);
    if (len == 0) return axiom_owned_str_wrap("");
    size_t out_len = len / 2;
    char* out = (char*)malloc(out_len + 1);
    if (!out) return axiom_owned_str_wrap("");

    size_t oi = 0;
    for (size_t i = 0; i + 1 < len; i += 2) {
        int hi = -1, lo = -1;
        char c1 = s[i], c2 = s[i+1];
        if (c1 >= '0' && c1 <= '9') hi = c1 - '0';
        else if (c1 >= 'a' && c1 <= 'f') hi = c1 - 'a' + 10;
        else if (c1 >= 'A' && c1 <= 'F') hi = c1 - 'A' + 10;

        if (c2 >= '0' && c2 <= '9') lo = c2 - '0';
        else if (c2 >= 'a' && c2 <= 'f') lo = c2 - 'a' + 10;
        else if (c2 >= 'A' && c2 <= 'F') lo = c2 - 'A' + 10;

        if (hi >= 0 && lo >= 0) {
            out[oi++] = (char)((hi << 4) | lo);
        }
    }
    out[oi] = '\0';
    return axiom_owned_str_wrap(out);
}

/* --- 3. Cryptographic Hashes: MD5, SHA-1, SHA-256 (Zero Dependency) --- */

/* MD5 */
typedef struct {
    uint32_t state[4];
    uint32_t count[2];
    uint8_t buffer[64];
} axiom_md5_ctx;

#define AXIOM_MD5_F(x, y, z) (((x) & (y)) | ((~x) & (z)))
#define AXIOM_MD5_G(x, y, z) (((x) & (z)) | ((y) & (~z)))
#define AXIOM_MD5_H(x, y, z) ((x) ^ (y) ^ (z))
#define AXIOM_MD5_I(x, y, z) ((y) ^ ((x) | (~z)))
#define AXIOM_MD5_ROTL(x, n) (((x) << (n)) | ((x) >> (32 - (n))))

#define AXIOM_MD5_STEP(f, a, b, c, d, x, ac, s) { \
    (a) += f((b), (c), (d)) + (x) + (uint32_t)(ac); \
    (a) = AXIOM_MD5_ROTL((a), (s)); \
    (a) += (b); \
}

AXIOM_RUNTIME_FN void axiom_md5_transform(uint32_t state[4], const uint8_t block[64]) {
    uint32_t a = state[0], b = state[1], c = state[2], d = state[3], x[16];
    for (int i = 0; i < 16; i++) {
        x[i] = (uint32_t)block[i*4] | ((uint32_t)block[i*4+1] << 8) |
               ((uint32_t)block[i*4+2] << 16) | ((uint32_t)block[i*4+3] << 24);
    }
    /* Round 1 */
    AXIOM_MD5_STEP(AXIOM_MD5_F, a, b, c, d, x[ 0], 0xd76aa478, 7);
    AXIOM_MD5_STEP(AXIOM_MD5_F, d, a, b, c, x[ 1], 0xe8c7b756, 12);
    AXIOM_MD5_STEP(AXIOM_MD5_F, c, d, a, b, x[ 2], 0x242070db, 17);
    AXIOM_MD5_STEP(AXIOM_MD5_F, b, c, d, a, x[ 3], 0xc1bdceee, 22);
    AXIOM_MD5_STEP(AXIOM_MD5_F, a, b, c, d, x[ 4], 0xf57c0faf, 7);
    AXIOM_MD5_STEP(AXIOM_MD5_F, d, a, b, c, x[ 5], 0x4787c62a, 12);
    AXIOM_MD5_STEP(AXIOM_MD5_F, c, d, a, b, x[ 6], 0xa8304613, 17);
    AXIOM_MD5_STEP(AXIOM_MD5_F, b, c, d, a, x[ 7], 0xfd469501, 22);
    AXIOM_MD5_STEP(AXIOM_MD5_F, a, b, c, d, x[ 8], 0x698098d8, 7);
    AXIOM_MD5_STEP(AXIOM_MD5_F, d, a, b, c, x[ 9], 0x8b44f7af, 12);
    AXIOM_MD5_STEP(AXIOM_MD5_F, c, d, a, b, x[10], 0xffff5bb1, 17);
    AXIOM_MD5_STEP(AXIOM_MD5_F, b, c, d, a, x[11], 0x895cd7be, 22);
    AXIOM_MD5_STEP(AXIOM_MD5_F, a, b, c, d, x[12], 0x6b901122, 7);
    AXIOM_MD5_STEP(AXIOM_MD5_F, d, a, b, c, x[13], 0xfd987193, 12);
    AXIOM_MD5_STEP(AXIOM_MD5_F, c, d, a, b, x[14], 0xa679438e, 17);
    AXIOM_MD5_STEP(AXIOM_MD5_F, b, c, d, a, x[15], 0x49b40821, 22);
    /* Round 2 */
    AXIOM_MD5_STEP(AXIOM_MD5_G, a, b, c, d, x[ 1], 0xf61e2562, 5);
    AXIOM_MD5_STEP(AXIOM_MD5_G, d, a, b, c, x[ 6], 0xc040b340, 9);
    AXIOM_MD5_STEP(AXIOM_MD5_G, c, d, a, b, x[11], 0x265e5a51, 14);
    AXIOM_MD5_STEP(AXIOM_MD5_G, b, c, d, a, x[ 0], 0xe9b6c7aa, 20);
    AXIOM_MD5_STEP(AXIOM_MD5_G, a, b, c, d, x[ 5], 0xd62f105d, 5);
    AXIOM_MD5_STEP(AXIOM_MD5_G, d, a, b, c, x[10], 0x02441453, 9);
    AXIOM_MD5_STEP(AXIOM_MD5_G, c, d, a, b, x[15], 0xd8a1e681, 14);
    AXIOM_MD5_STEP(AXIOM_MD5_G, b, c, d, a, x[ 4], 0xe7d3fbc8, 20);
    AXIOM_MD5_STEP(AXIOM_MD5_G, a, b, c, d, x[ 9], 0x21e1cde6, 5);
    AXIOM_MD5_STEP(AXIOM_MD5_G, d, a, b, c, x[14], 0xc33707d6, 9);
    AXIOM_MD5_STEP(AXIOM_MD5_G, c, d, a, b, x[ 3], 0xf4d50d87, 14);
    AXIOM_MD5_STEP(AXIOM_MD5_G, b, c, d, a, x[ 8], 0x455a14ed, 20);
    AXIOM_MD5_STEP(AXIOM_MD5_G, a, b, c, d, x[13], 0xa9e3e905, 5);
    AXIOM_MD5_STEP(AXIOM_MD5_G, d, a, b, c, x[ 2], 0xfcefa3f8, 9);
    AXIOM_MD5_STEP(AXIOM_MD5_G, c, d, a, b, x[ 7], 0x676f02d9, 14);
    AXIOM_MD5_STEP(AXIOM_MD5_G, b, c, d, a, x[12], 0x8d2a4c8a, 20);
    /* Round 3 */
    AXIOM_MD5_STEP(AXIOM_MD5_H, a, b, c, d, x[ 5], 0xfffa3942, 4);
    AXIOM_MD5_STEP(AXIOM_MD5_H, d, a, b, c, x[ 8], 0x8771f681, 11);
    AXIOM_MD5_STEP(AXIOM_MD5_H, c, d, a, b, x[11], 0x6d9d6122, 16);
    AXIOM_MD5_STEP(AXIOM_MD5_H, b, c, d, a, x[14], 0xfde5380c, 23);
    AXIOM_MD5_STEP(AXIOM_MD5_H, a, b, c, d, x[ 1], 0xa4beea44, 4);
    AXIOM_MD5_STEP(AXIOM_MD5_H, d, a, b, c, x[ 4], 0x4bdecfa9, 11);
    AXIOM_MD5_STEP(AXIOM_MD5_H, c, d, a, b, x[ 7], 0xf6bb4b60, 16);
    AXIOM_MD5_STEP(AXIOM_MD5_H, b, c, d, a, x[10], 0xbebfbc70, 23);
    AXIOM_MD5_STEP(AXIOM_MD5_H, a, b, c, d, x[13], 0x289b7ec6, 4);
    AXIOM_MD5_STEP(AXIOM_MD5_H, d, a, b, c, x[ 0], 0xeaa127fa, 11);
    AXIOM_MD5_STEP(AXIOM_MD5_H, c, d, a, b, x[ 3], 0xd4ef3085, 16);
    AXIOM_MD5_STEP(AXIOM_MD5_H, b, c, d, a, x[ 6], 0x04881d05, 23);
    AXIOM_MD5_STEP(AXIOM_MD5_H, a, b, c, d, x[ 9], 0xd9d4d039, 4);
    AXIOM_MD5_STEP(AXIOM_MD5_H, d, a, b, c, x[12], 0xe6db99e5, 11);
    AXIOM_MD5_STEP(AXIOM_MD5_H, c, d, a, b, x[15], 0x1fa27cf8, 16);
    AXIOM_MD5_STEP(AXIOM_MD5_H, b, c, d, a, x[ 2], 0xc4ac5665, 23);
    /* Round 4 */
    AXIOM_MD5_STEP(AXIOM_MD5_I, a, b, c, d, x[ 0], 0xf4292244, 6);
    AXIOM_MD5_STEP(AXIOM_MD5_I, d, a, b, c, x[ 7], 0x432aff97, 10);
    AXIOM_MD5_STEP(AXIOM_MD5_I, c, d, a, b, x[14], 0xab9423a7, 15);
    AXIOM_MD5_STEP(AXIOM_MD5_I, b, c, d, a, x[ 5], 0xfc93a039, 21);
    AXIOM_MD5_STEP(AXIOM_MD5_I, a, b, c, d, x[12], 0x655b59c3, 6);
    AXIOM_MD5_STEP(AXIOM_MD5_I, d, a, b, c, x[ 3], 0x8f0ccc92, 10);
    AXIOM_MD5_STEP(AXIOM_MD5_I, c, d, a, b, x[10], 0xffeff47d, 15);
    AXIOM_MD5_STEP(AXIOM_MD5_I, b, c, d, a, x[ 1], 0x85845dd1, 21);
    AXIOM_MD5_STEP(AXIOM_MD5_I, a, b, c, d, x[ 8], 0x6fa87e4f, 6);
    AXIOM_MD5_STEP(AXIOM_MD5_I, d, a, b, c, x[15], 0xfe2ce6e0, 10);
    AXIOM_MD5_STEP(AXIOM_MD5_I, c, d, a, b, x[ 6], 0xa3014314, 15);
    AXIOM_MD5_STEP(AXIOM_MD5_I, b, c, d, a, x[13], 0x4e0811a1, 21);
    AXIOM_MD5_STEP(AXIOM_MD5_I, a, b, c, d, x[ 4], 0xf7537e82, 6);
    AXIOM_MD5_STEP(AXIOM_MD5_I, d, a, b, c, x[11], 0xbd3af235, 10);
    AXIOM_MD5_STEP(AXIOM_MD5_I, c, d, a, b, x[ 2], 0x2ad7d2bb, 15);
    AXIOM_MD5_STEP(AXIOM_MD5_I, b, c, d, a, x[ 9], 0xeb86d391, 21);

    state[0] += a;
    state[1] += b;
    state[2] += c;
    state[3] += d;
}

#if AXIOM_HAVE_OPENSSL
AXIOM_RUNTIME_FN ax_str axiom_hash_md5(const char* s) {
    if (!s) s = "";
    size_t len = strlen(s);
    axiom_md5_ctx ctx;
    ctx.count[0] = ctx.count[1] = 0;
    ctx.state[0] = 0x67452301;
    ctx.state[1] = 0xefcdab89;
    ctx.state[2] = 0x98badcfe;
    ctx.state[3] = 0x10325476;

    uint32_t i = 0, index = 0, part_len = 0;
    index = (uint32_t)((ctx.count[0] >> 3) & 0x3F);
    if ((ctx.count[0] += ((uint32_t)len << 3)) < ((uint32_t)len << 3)) ctx.count[1]++;
    ctx.count[1] += ((uint32_t)len >> 29);
    part_len = 64 - index;

    if (len >= part_len) {
        memcpy(&ctx.buffer[index], s, part_len);
        axiom_md5_transform(ctx.state, ctx.buffer);
        for (i = part_len; i + 63 < len; i += 64) {
            axiom_md5_transform(ctx.state, (const uint8_t*)s + i);
        }
        index = 0;
    } else {
        i = 0;
    }
    memcpy(&ctx.buffer[index], &s[i], len - i);

    static const uint8_t PADDING[64] = {
        0x80, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
    };
    uint8_t bits[8];
    for (int k = 0; k < 8; k++) {
        bits[k] = (uint8_t)((k < 4 ? ctx.count[0] : ctx.count[1]) >> ((k % 4) * 8));
    }
    index = (uint32_t)((ctx.count[0] >> 3) & 0x3F);
    uint32_t pad_len = (index < 56) ? (56 - index) : (120 - index);

    uint32_t p_index = (uint32_t)((ctx.count[0] >> 3) & 0x3F);
    uint32_t p_part = 64 - p_index;
    if (pad_len >= p_part) {
        memcpy(&ctx.buffer[p_index], PADDING, p_part);
        axiom_md5_transform(ctx.state, ctx.buffer);
        for (uint32_t pi = p_part; pi + 63 < pad_len; pi += 64) {
            axiom_md5_transform(ctx.state, PADDING + pi);
        }
        p_index = 0;
    }
    memcpy(&ctx.buffer[p_index], PADDING + (pad_len >= p_part ? p_part : 0), pad_len - (pad_len >= p_part ? p_part : 0));

    memcpy(&ctx.buffer[56], bits, 8);
    axiom_md5_transform(ctx.state, ctx.buffer);

    uint8_t digest[16];
    for (int k = 0; k < 16; k++) {
        digest[k] = (uint8_t)((ctx.state[k / 4] >> ((k % 4) * 8)) & 0xFF);
    }

    char* hex = (char*)malloc(33);
    if (!hex) return axiom_owned_str_wrap("");
    for (int k = 0; k < 16; k++) {
        sprintf(hex + k * 2, "%02x", digest[k]);
    }
    hex[32] = '\0';
    return axiom_owned_str_wrap(hex);
}
#else
AXIOM_RUNTIME_FN ax_str axiom_hash_md5(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    uint8_t d[16]; char hex[33];
    ax_md5(s, strlen(s), d);
    ax_hex_from_bytes(d, 16, hex);
    return axiom_safe_strdup(hex);
}
#endif /* AXIOM_HAVE_OPENSSL */

/* SHA-1 */
#define AXIOM_SHA1_ROTL(bits, word) (((word) << (bits)) | ((word) >> (32 - (bits))))

AXIOM_RUNTIME_FN void axiom_sha1_transform(uint32_t state[5], const uint8_t buffer[64]) {
    uint32_t a = state[0], b = state[1], c = state[2], d = state[3], e = state[4];
    uint32_t w[80];
    for (int i = 0; i < 16; i++) {
        w[i] = ((uint32_t)buffer[i * 4] << 24) |
               ((uint32_t)buffer[i * 4 + 1] << 16) |
               ((uint32_t)buffer[i * 4 + 2] << 8) |
               ((uint32_t)buffer[i * 4 + 3]);
    }
    for (int i = 16; i < 80; i++) {
        w[i] = AXIOM_SHA1_ROTL(1, w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16]);
    }
    for (int i = 0; i < 80; i++) {
        uint32_t f, k;
        if (i < 20) {
            f = (b & c) | ((~b) & d);
            k = 0x5A827999;
        } else if (i < 40) {
            f = b ^ c ^ d;
            k = 0x6ED9EBA1;
        } else if (i < 60) {
            f = (b & c) | (b & d) | (c & d);
            k = 0x8F1BBCDC;
        } else {
            f = b ^ c ^ d;
            k = 0xCA62C1D6;
        }
        uint32_t temp = AXIOM_SHA1_ROTL(5, a) + f + e + k + w[i];
        e = d;
        d = c;
        c = AXIOM_SHA1_ROTL(30, b);
        b = a;
        a = temp;
    }
    state[0] += a;
    state[1] += b;
    state[2] += c;
    state[3] += d;
    state[4] += e;
}

#if AXIOM_HAVE_OPENSSL
AXIOM_RUNTIME_FN ax_str axiom_hash_sha1(const char* s) {
    if (!s) s = "";
    uint64_t total_bytes = (uint64_t)strlen(s);
    uint32_t state[5] = { 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0 };

    uint64_t i = 0;
    while (i + 64 <= total_bytes) {
        axiom_sha1_transform(state, (const uint8_t*)s + i);
        i += 64;
    }
    uint8_t block[128];
    memset(block, 0, sizeof(block));
    uint64_t rem = total_bytes - i;
    memcpy(block, s + i, rem);
    block[rem] = 0x80;

    uint64_t pad_block_len = (rem < 56) ? 64 : 128;
    uint64_t total_bits = total_bytes * 8;
    for (int k = 0; k < 8; k++) {
        block[pad_block_len - 1 - k] = (uint8_t)(total_bits >> (k * 8));
    }
    axiom_sha1_transform(state, block);
    if (pad_block_len == 128) {
        axiom_sha1_transform(state, block + 64);
    }

    char* hex = (char*)malloc(41);
    if (!hex) return axiom_owned_str_wrap("");
    for (int k = 0; k < 5; k++) {
        sprintf(hex + k * 8, "%08x", state[k]);
    }
    hex[40] = '\0';
    return axiom_owned_str_wrap(hex);
}
#else
AXIOM_RUNTIME_FN ax_str axiom_hash_sha1(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    uint8_t d[20]; char hex[41];
    ax_sha1(s, strlen(s), d);
    ax_hex_from_bytes(d, 20, hex);
    return axiom_safe_strdup(hex);
}
#endif /* AXIOM_HAVE_OPENSSL */

/* SHA-256 */
#define AXIOM_SHA256_ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
#define AXIOM_SHA256_CH(x, y, z)  (((x) & (y)) ^ (~(x) & (z)))
#define AXIOM_SHA256_MAJ(x, y, z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define AXIOM_SHA256_EP0(x) (AXIOM_SHA256_ROTR(x, 2) ^ AXIOM_SHA256_ROTR(x, 13) ^ AXIOM_SHA256_ROTR(x, 22))
#define AXIOM_SHA256_EP1(x) (AXIOM_SHA256_ROTR(x, 6) ^ AXIOM_SHA256_ROTR(x, 11) ^ AXIOM_SHA256_ROTR(x, 25))
#define AXIOM_SHA256_SIG0(x) (AXIOM_SHA256_ROTR(x, 7) ^ AXIOM_SHA256_ROTR(x, 18) ^ ((x) >> 3))
#define AXIOM_SHA256_SIG1(x) (AXIOM_SHA256_ROTR(x, 17) ^ AXIOM_SHA256_ROTR(x, 19) ^ ((x) >> 10))

static const uint32_t AXIOM_SHA256_K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

AXIOM_RUNTIME_FN void axiom_sha256_transform(uint32_t state[8], const uint8_t data[64]) {
    uint32_t a, b, c, d, e, f, g, h, t1, t2, m[64];
    for (int i = 0, j = 0; i < 16; ++i, j += 4) {
        m[i] = ((uint32_t)data[j] << 24) | ((uint32_t)data[j + 1] << 16) |
               ((uint32_t)data[j + 2] << 8) | ((uint32_t)data[j + 3]);
    }
    for (int i = 16; i < 64; ++i) {
        m[i] = AXIOM_SHA256_SIG1(m[i - 2]) + m[i - 7] + AXIOM_SHA256_SIG0(m[i - 15]) + m[i - 16];
    }
    a = state[0]; b = state[1]; c = state[2]; d = state[3];
    e = state[4]; f = state[5]; g = state[6]; h = state[7];

    for (int i = 0; i < 64; ++i) {
        t1 = h + AXIOM_SHA256_EP1(e) + AXIOM_SHA256_CH(e, f, g) + AXIOM_SHA256_K[i] + m[i];
        t2 = AXIOM_SHA256_EP0(a) + AXIOM_SHA256_MAJ(a, b, c);
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }
    state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    state[4] += e; state[5] += f; state[6] += g; state[7] += h;
}

#if AXIOM_HAVE_OPENSSL
AXIOM_RUNTIME_FN ax_str axiom_hash_sha256(const char* s) {
    if (!s) s = "";
    uint64_t total_bytes = (uint64_t)strlen(s);
    uint32_t state[8] = {
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    };
    uint64_t i = 0;
    while (i + 64 <= total_bytes) {
        axiom_sha256_transform(state, (const uint8_t*)s + i);
        i += 64;
    }
    uint8_t block[128];
    memset(block, 0, sizeof(block));
    uint64_t rem = total_bytes - i;
    memcpy(block, s + i, rem);
    block[rem] = 0x80;

    uint64_t pad_block_len = (rem < 56) ? 64 : 128;
    uint64_t total_bits = total_bytes * 8;
    for (int k = 0; k < 8; k++) {
        block[pad_block_len - 1 - k] = (uint8_t)(total_bits >> (k * 8));
    }
    axiom_sha256_transform(state, block);
    if (pad_block_len == 128) {
        axiom_sha256_transform(state, block + 64);
    }

    char* hex = (char*)malloc(65);
    if (!hex) return axiom_owned_str_wrap("");
    for (int k = 0; k < 8; k++) {
        sprintf(hex + k * 8, "%08x", state[k]);
    }
    hex[64] = '\0';
    return axiom_owned_str_wrap(hex);
}
#else
AXIOM_RUNTIME_FN ax_str axiom_hash_sha256(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    uint8_t d[32]; char hex[65];
    ax_sha256(s, strlen(s), d);
    ax_hex_from_bytes(d, 32, hex);
    return axiom_safe_strdup(hex);
}
#endif /* AXIOM_HAVE_OPENSSL */

/* --- 4. URL Encode / Decode / Parse (RFC 3986) --- */
AXIOM_RUNTIME_FN ax_str axiom_url_encode(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    size_t len = strlen(s);
    if (len == 0) return axiom_owned_str_wrap("");
    static const char hex_digits_upper[] = "0123456789ABCDEF";
    char* out = (char*)malloc(len * 3 + 1);
    if (!out) return axiom_owned_str_wrap("");
    size_t j = 0;
    for (size_t i = 0; i < len; i++) {
        unsigned char c = (unsigned char)s[i];
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
            (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == '~') {
            out[j++] = (char)c;
        } else {
            out[j++] = '%';
            out[j++] = hex_digits_upper[(c >> 4) & 0x0F];
            out[j++] = hex_digits_upper[c & 0x0F];
        }
    }
    out[j] = '\0';
    return axiom_owned_str_wrap(out);
}

AXIOM_RUNTIME_FN ax_str axiom_url_decode(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    size_t len = strlen(s);
    if (len == 0) return axiom_owned_str_wrap("");
    char* out = (char*)malloc(len + 1);
    if (!out) return axiom_owned_str_wrap("");
    size_t j = 0;
    for (size_t i = 0; i < len; i++) {
        if (s[i] == '+') {
            out[j++] = ' ';
        } else if (s[i] == '%' && i + 2 < len) {
            int hi = -1, lo = -1;
            char c1 = s[i+1], c2 = s[i+2];
            if (c1 >= '0' && c1 <= '9') hi = c1 - '0';
            else if (c1 >= 'a' && c1 <= 'f') hi = c1 - 'a' + 10;
            else if (c1 >= 'A' && c1 <= 'F') hi = c1 - 'A' + 10;

            if (c2 >= '0' && c2 <= '9') lo = c2 - '0';
            else if (c2 >= 'a' && c2 <= 'f') lo = c2 - 'a' + 10;
            else if (c2 >= 'A' && c2 <= 'F') lo = c2 - 'A' + 10;

            if (hi >= 0 && lo >= 0) {
                out[j++] = (char)((hi << 4) | lo);
                i += 2;
            } else {
                out[j++] = s[i];
            }
        } else {
            out[j++] = s[i];
        }
    }
    out[j] = '\0';
    return axiom_owned_str_wrap(out);
}

typedef struct {
    char scheme[32];
    char host[256];
    ax_int port;
    char path[1024];
    char query[1024];
} axiom_parsed_url_t;

AXIOM_RUNTIME_FN axiom_parsed_url_t axiom_internal_parse_url(const char* raw) {
    axiom_parsed_url_t u;
    memset(&u, 0, sizeof(u));
    strcpy(u.path, "/");
    u.port = 0;
    if (!raw || strlen(raw) == 0) return u;

    const char* p = raw;
    const char* scheme_sep = strstr(p, "://");
    if (scheme_sep) {
        size_t slen = (size_t)(scheme_sep - p);
        if (slen < sizeof(u.scheme)) {
            strncpy(u.scheme, p, slen);
            u.scheme[slen] = '\0';
        }
        p = scheme_sep + 3;
    }

    const char* slash = strchr(p, '/');
    const char* question = strchr(p, '?');
    const char* hash = strchr(p, '#');
    const char* auth_end = p + strlen(p);
    if (slash && slash < auth_end) auth_end = slash;
    if (question && question < auth_end) auth_end = question;
    if (hash && hash < auth_end) auth_end = hash;

    const char* at = memchr(p, '@', (size_t)(auth_end - p));
    if (at) {
        p = at + 1;
    }

    const char* colon = memchr(p, ':', (size_t)(auth_end - p));
    if (colon) {
        size_t hlen = (size_t)(colon - p);
        if (hlen < sizeof(u.host)) {
            strncpy(u.host, p, hlen);
            u.host[hlen] = '\0';
        }
        u.port = (ax_int)strtoll(colon + 1, NULL, 10);
    } else {
        size_t hlen = (size_t)(auth_end - p);
        if (hlen < sizeof(u.host)) {
            strncpy(u.host, p, hlen);
            u.host[hlen] = '\0';
        }
    }

    if (u.port == 0) {
        if (strcmp(u.scheme, "http") == 0) u.port = 80;
        else if (strcmp(u.scheme, "https") == 0) u.port = 443;
        else if (strcmp(u.scheme, "ssh") == 0) u.port = 22;
        else if (strcmp(u.scheme, "ftp") == 0) u.port = 21;
        else u.port = 80;
    }

    p = auth_end;
    if (*p == '/') {
        const char* path_end = p + strlen(p);
        const char* q = strchr(p, '?');
        const char* h = strchr(p, '#');
        if (q && q < path_end) path_end = q;
        if (h && h < path_end) path_end = h;
        size_t plen = (size_t)(path_end - p);
        if (plen < sizeof(u.path)) {
            strncpy(u.path, p, plen);
            u.path[plen] = '\0';
        }
        p = path_end;
    }

    if (*p == '?') {
        p++;
        const char* q_end = p + strlen(p);
        const char* h = strchr(p, '#');
        if (h && h < q_end) q_end = h;
        size_t qlen = (size_t)(q_end - p);
        if (qlen < sizeof(u.query)) {
            strncpy(u.query, p, qlen);
            u.query[qlen] = '\0';
        }
    }

    return u;
}

AXIOM_RUNTIME_FN ax_str axiom_url_parse_scheme(const char* raw) {
    axiom_parsed_url_t u = axiom_internal_parse_url(raw);
    return axiom_safe_strdup(u.scheme);
}

AXIOM_RUNTIME_FN ax_str axiom_url_parse_host(const char* raw) {
    axiom_parsed_url_t u = axiom_internal_parse_url(raw);
    return axiom_safe_strdup(u.host);
}

AXIOM_RUNTIME_FN ax_int axiom_url_parse_port(const char* raw) {
    axiom_parsed_url_t u = axiom_internal_parse_url(raw);
    return u.port;
}

AXIOM_RUNTIME_FN ax_str axiom_url_parse_path(const char* raw) {
    axiom_parsed_url_t u = axiom_internal_parse_url(raw);
    return axiom_safe_strdup(u.path);
}

AXIOM_RUNTIME_FN ax_str axiom_url_parse_query(const char* raw) {
    axiom_parsed_url_t u = axiom_internal_parse_url(raw);
    return axiom_safe_strdup(u.query);
}

/* --- 5. JSON Scanner, Parser & Builder --- */
AXIOM_RUNTIME_FN const char* axiom_json_find_key(const char* json, const char* key) {
    if (!json || !key) return NULL;
    size_t klen = strlen(key);
    const char* p = json;
    while (*p) {
        if (*p == '"') {
            p++;
            if (strncmp(p, key, klen) == 0 && p[klen] == '"') {
                const char* colon = p + klen + 1;
                while (*colon && isspace((unsigned char)*colon)) colon++;
                if (*colon == ':') {
                    colon++;
                    while (*colon && isspace((unsigned char)*colon)) colon++;
                    return colon;
                }
            }
            while (*p && *p != '"') {
                if (*p == '\\' && *(p + 1)) p += 2;
                else p++;
            }
            if (*p == '"') p++;
        } else {
            p++;
        }
    }
    return NULL;
}

AXIOM_RUNTIME_FN ax_bool axiom_json_has_key(const char* json, const char* key) {
    return axiom_json_find_key(json, key) != NULL;
}

AXIOM_RUNTIME_FN ax_str axiom_json_get_str(const char* json, const char* key) {
    const char* val = axiom_json_find_key(json, key);
    if (!val || *val != '"') return axiom_owned_str_wrap("");
    val++;
    const char* end = val;
    while (*end && *end != '"') {
        if (*end == '\\' && *(end + 1)) end += 2;
        else end++;
    }
    size_t len = (size_t)(end - val);
    char* res = (char*)malloc(len + 1);
    if (!res) return axiom_owned_str_wrap("");
    size_t j = 0;
    for (size_t i = 0; i < len; i++) {
        if (val[i] == '\\' && i + 1 < len) {
            char next = val[++i];
            if (next == 'n') res[j++] = '\n';
            else if (next == 'r') res[j++] = '\r';
            else if (next == 't') res[j++] = '\t';
            else if (next == '"') res[j++] = '"';
            else if (next == '\\') res[j++] = '\\';
            else res[j++] = next;
        } else {
            res[j++] = val[i];
        }
    }
    res[j] = '\0';
    return axiom_owned_str_wrap(res);
}

AXIOM_RUNTIME_FN ax_int axiom_json_get_int(const char* json, const char* key) {
    const char* val = axiom_json_find_key(json, key);
    if (!val) return 0;
    return (ax_int)strtoll(val, NULL, 10);
}

AXIOM_RUNTIME_FN ax_bool axiom_json_get_bool(const char* json, const char* key) {
    const char* val = axiom_json_find_key(json, key);
    if (!val) return false;
    if (strncmp(val, "true", 4) == 0) return true;
    return false;
}


/* ==========================================================================
 * Gerçek JSON Parser (recursive descent, DOM)
 *
 * Eski `axiom_json_find_key` düz metin arıyordu: iç içe nesne, dizi, null,
 * Unicode kaçışı ve tip ayrımı yoktu. Bu bölüm gerçek bir parser ekler.
 *
 * Kullanım:
 *   ax_int root = axiom_json_parse(text, err, sizeof(err));  // 0 = hata
 *   ax_int node = axiom_json_path(root, "a.b[0].c");
 *   const char* s = axiom_json_node_str(node);
 *   axiom_json_free(root);
 *
 * Not: node tutamacları root'a ait ÖDÜNÇ işaretçilerdir; ayrıca serbest
 * bırakılmaz. Yalnızca root `axiom_json_free` ile bırakılır.
 * ========================================================================== */

typedef enum {
    AXJ_NULL = 0, AXJ_BOOL, AXJ_NUM, AXJ_STR, AXJ_ARR, AXJ_OBJ
} ax_json_type;

typedef struct ax_json_node {
    ax_json_type type;
    ax_bool b;
    double num;
    char* str;                    /* AXJ_STR */
    struct ax_json_node** items;  /* AXJ_ARR / AXJ_OBJ değerleri */
    char** keys;                  /* AXJ_OBJ anahtarları */
    int count;
    int cap;
} ax_json_node;

typedef struct {
    const char* src;
    size_t pos;
    size_t len;
    int depth;
    const char* err;
} ax_json_parser;

#define AXJ_MAX_DEPTH 200

static ax_json_node* axj_new(ax_json_type t) {
    ax_json_node* n = (ax_json_node*)calloc(1, sizeof(ax_json_node));
    if (n) n->type = t;
    return n;
}

static void axj_free(ax_json_node* n) {
    if (!n) return;
    if (n->items) {
        for (int i = 0; i < n->count; i++) axj_free(n->items[i]);
        free(n->items);
    }
    if (n->keys) {
        for (int i = 0; i < n->count; i++) free(n->keys[i]);
        free(n->keys);
    }
    if (n->str) free(n->str);
    free(n);
}

static void axj_skip_ws(ax_json_parser* p) {
    while (p->pos < p->len) {
        char c = p->src[p->pos];
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r') p->pos++;
        else break;
    }
}

static int axj_utf8_encode(unsigned cp, char* out) {
    if (cp < 0x80) { out[0] = (char)cp; return 1; }
    if (cp < 0x800) {
        out[0] = (char)(0xC0 | (cp >> 6));
        out[1] = (char)(0x80 | (cp & 0x3F));
        return 2;
    }
    if (cp < 0x10000) {
        out[0] = (char)(0xE0 | (cp >> 12));
        out[1] = (char)(0x80 | ((cp >> 6) & 0x3F));
        out[2] = (char)(0x80 | (cp & 0x3F));
        return 3;
    }
    out[0] = (char)(0xF0 | (cp >> 18));
    out[1] = (char)(0x80 | ((cp >> 12) & 0x3F));
    out[2] = (char)(0x80 | ((cp >> 6) & 0x3F));
    out[3] = (char)(0x80 | (cp & 0x3F));
    return 4;
}

static int axj_hex4(const char* s, unsigned* out) {
    unsigned v = 0;
    for (int i = 0; i < 4; i++) {
        char c = s[i];
        v <<= 4;
        if (c >= '0' && c <= '9') v |= (unsigned)(c - '0');
        else if (c >= 'a' && c <= 'f') v |= (unsigned)(c - 'a' + 10);
        else if (c >= 'A' && c <= 'F') v |= (unsigned)(c - 'A' + 10);
        else return 0;
    }
    *out = v;
    return 1;
}

/* String parse: p->pos açılış " karakterinde. Kapanıştan sonra durur. */
static char* axj_parse_string(ax_json_parser* p) {
    if (p->pos >= p->len || p->src[p->pos] != '"') return NULL;
    p->pos++;
    size_t cap = 32, n = 0;
    char* buf = (char*)malloc(cap);
    if (!buf) return NULL;

    while (p->pos < p->len) {
        char c = p->src[p->pos];
        if (c == '"') { p->pos++; buf[n] = '\0'; return buf; }
        if (c == '\\') {
            p->pos++;
            if (p->pos >= p->len) { free(buf); return NULL; }
            char e = p->src[p->pos++];
            char tmp[4]; int k = 1;
            switch (e) {
                case '"': tmp[0] = '"'; break;
                case '\\': tmp[0] = '\\'; break;
                case '/': tmp[0] = '/'; break;
                case 'b': tmp[0] = '\b'; break;
                case 'f': tmp[0] = '\f'; break;
                case 'n': tmp[0] = '\n'; break;
                case 'r': tmp[0] = '\r'; break;
                case 't': tmp[0] = '\t'; break;
                case 'u': {
                    unsigned cp = 0;
                    if (p->pos + 4 > p->len || !axj_hex4(p->src + p->pos, &cp)) {
                        free(buf); return NULL;
                    }
                    p->pos += 4;
                    /* surrogate pair */
                    if (cp >= 0xD800 && cp <= 0xDBFF && p->pos + 6 <= p->len
                        && p->src[p->pos] == '\\' && p->src[p->pos + 1] == 'u') {
                        unsigned lo = 0;
                        if (axj_hex4(p->src + p->pos + 2, &lo)
                            && lo >= 0xDC00 && lo <= 0xDFFF) {
                            p->pos += 6;
                            cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                        }
                    }
                    k = axj_utf8_encode(cp, tmp);
                    break;
                }
                default: free(buf); return NULL;
            }
            if (n + (size_t)k + 1 > cap) {
                while (n + (size_t)k + 1 > cap) cap *= 2;
                char* nb = (char*)realloc(buf, cap);
                if (!nb) { free(buf); return NULL; }
                buf = nb;
            }
            memcpy(buf + n, tmp, (size_t)k);
            n += (size_t)k;
            continue;
        }
        if ((unsigned char)c < 0x20) { free(buf); return NULL; } /* kontrol karakteri */
        if (n + 2 > cap) {
            cap *= 2;
            char* nb = (char*)realloc(buf, cap);
            if (!nb) { free(buf); return NULL; }
            buf = nb;
        }
        buf[n++] = c;
        p->pos++;
    }
    free(buf);
    return NULL;
}

static ax_json_node* axj_parse_value(ax_json_parser* p);

static ax_json_node* axj_parse_array(ax_json_parser* p) {
    p->pos++; /* [ */
    ax_json_node* arr = axj_new(AXJ_ARR);
    if (!arr) return NULL;
    axj_skip_ws(p);
    if (p->pos < p->len && p->src[p->pos] == ']') { p->pos++; return arr; }
    for (;;) {
        ax_json_node* item = axj_parse_value(p);
        if (!item) { axj_free(arr); return NULL; }
        if (arr->count == arr->cap) {
            int nc = arr->cap ? arr->cap * 2 : 8;
            ax_json_node** ni = (ax_json_node**)realloc(arr->items, (size_t)nc * sizeof(*ni));
            if (!ni) { axj_free(item); axj_free(arr); return NULL; }
            arr->items = ni; arr->cap = nc;
        }
        arr->items[arr->count++] = item;
        axj_skip_ws(p);
        if (p->pos < p->len && p->src[p->pos] == ',') { p->pos++; axj_skip_ws(p); continue; }
        if (p->pos < p->len && p->src[p->pos] == ']') { p->pos++; return arr; }
        axj_free(arr); return NULL;
    }
}

static ax_json_node* axj_parse_object(ax_json_parser* p) {
    p->pos++; /* { */
    ax_json_node* obj = axj_new(AXJ_OBJ);
    if (!obj) return NULL;
    axj_skip_ws(p);
    if (p->pos < p->len && p->src[p->pos] == '}') { p->pos++; return obj; }
    for (;;) {
        char* key = axj_parse_string(p);
        if (!key) { axj_free(obj); return NULL; }
        axj_skip_ws(p);
        if (p->pos >= p->len || p->src[p->pos] != ':') { free(key); axj_free(obj); return NULL; }
        p->pos++;
        axj_skip_ws(p);
        ax_json_node* val = axj_parse_value(p);
        if (!val) { free(key); axj_free(obj); return NULL; }
        if (obj->count == obj->cap) {
            int nc = obj->cap ? obj->cap * 2 : 8;
            ax_json_node** ni = (ax_json_node**)realloc(obj->items, (size_t)nc * sizeof(*ni));
            char** nk = (char**)realloc(obj->keys, (size_t)nc * sizeof(*nk));
            if (!ni || !nk) {
                if (ni) obj->items = ni;
                if (nk) obj->keys = nk;
                free(key); axj_free(val); axj_free(obj); return NULL;
            }
            obj->items = ni; obj->keys = nk; obj->cap = nc;
        }
        obj->keys[obj->count] = key;
        obj->items[obj->count] = val;
        obj->count++;
        axj_skip_ws(p);
        if (p->pos < p->len && p->src[p->pos] == ',') { p->pos++; axj_skip_ws(p); continue; }
        if (p->pos < p->len && p->src[p->pos] == '}') { p->pos++; return obj; }
        axj_free(obj); return NULL;
    }
}

static ax_json_node* axj_parse_number(ax_json_parser* p) {
    size_t start = p->pos;
    if (p->pos < p->len && p->src[p->pos] == '-') p->pos++;
    if (p->pos >= p->len || !isdigit((unsigned char)p->src[p->pos])) return NULL;
    /* JSON: basi sifir olamaz ("01" gecersiz, "0" ve "0.5" gecerli) */
    if (p->src[p->pos] == '0' && p->pos + 1 < p->len
        && isdigit((unsigned char)p->src[p->pos + 1])) {
        return NULL;
    }
    while (p->pos < p->len && isdigit((unsigned char)p->src[p->pos])) p->pos++;
    if (p->pos < p->len && p->src[p->pos] == '.') {
        p->pos++;
        if (p->pos >= p->len || !isdigit((unsigned char)p->src[p->pos])) return NULL;
        while (p->pos < p->len && isdigit((unsigned char)p->src[p->pos])) p->pos++;
    }
    if (p->pos < p->len && (p->src[p->pos] == 'e' || p->src[p->pos] == 'E')) {
        p->pos++;
        if (p->pos < p->len && (p->src[p->pos] == '+' || p->src[p->pos] == '-')) p->pos++;
        if (p->pos >= p->len || !isdigit((unsigned char)p->src[p->pos])) return NULL;
        while (p->pos < p->len && isdigit((unsigned char)p->src[p->pos])) p->pos++;
    }
    char tmp[64];
    size_t n = p->pos - start;
    if (n >= sizeof(tmp)) return NULL;
    memcpy(tmp, p->src + start, n);
    tmp[n] = '\0';
    ax_json_node* node = axj_new(AXJ_NUM);
    if (!node) return NULL;
    node->num = strtod(tmp, NULL);
    return node;
}

static ax_json_node* axj_parse_value(ax_json_parser* p) {
    if (++p->depth > AXJ_MAX_DEPTH) return NULL;
    axj_skip_ws(p);
    ax_json_node* node = NULL;
    if (p->pos >= p->len) { p->depth--; return NULL; }

    char c = p->src[p->pos];
    if (c == '{') node = axj_parse_object(p);
    else if (c == '[') node = axj_parse_array(p);
    else if (c == '"') {
        char* s = axj_parse_string(p);
        if (s) { node = axj_new(AXJ_STR); if (node) node->str = s; else free(s); }
    } else if (c == 't' && p->len - p->pos >= 4 && strncmp(p->src + p->pos, "true", 4) == 0) {
        p->pos += 4; node = axj_new(AXJ_BOOL); if (node) node->b = true;
    } else if (c == 'f' && p->len - p->pos >= 5 && strncmp(p->src + p->pos, "false", 5) == 0) {
        p->pos += 5; node = axj_new(AXJ_BOOL); if (node) node->b = false;
    } else if (c == 'n' && p->len - p->pos >= 4 && strncmp(p->src + p->pos, "null", 4) == 0) {
        p->pos += 4; node = axj_new(AXJ_NULL);
    } else if (c == '-' || isdigit((unsigned char)c)) {
        node = axj_parse_number(p);
    }
    p->depth--;
    return node;
}

/* Son parse hatasi (thread-local). */
static _Thread_local char g_ax_json_err[160];

/* Metni parse eder. Hata durumunda 0 döner ve err buf'a mesaj yazar. */
AXIOM_RUNTIME_FN ax_int axiom_json_parse(const char* text, char* errbuf, ax_int errlen) {
    if (!text) {
        if (errbuf && errlen > 0) snprintf(errbuf, (size_t)errlen, "bos girdi");
        return 0;
    }
    ax_json_parser p;
    p.src = text; p.pos = 0; p.len = strlen(text); p.depth = 0; p.err = NULL;
    ax_json_node* root = axj_parse_value(&p);
    if (!root) {
        snprintf(g_ax_json_err, sizeof(g_ax_json_err),
                 "gecersiz JSON (konum %zu)", p.pos);
        if (errbuf && errlen > 0) snprintf(errbuf, (size_t)errlen, "%s", g_ax_json_err);
        return 0;
    }
    axj_skip_ws(&p);
    if (p.pos != p.len) {
        snprintf(g_ax_json_err, sizeof(g_ax_json_err),
                 "JSON sonrasinda fazladan veri (konum %zu)", p.pos);
        if (errbuf && errlen > 0) snprintf(errbuf, (size_t)errlen, "%s", g_ax_json_err);
        axj_free(root);
        return 0;
    }
    g_ax_json_err[0] = '\0';
    return (ax_int)(uintptr_t)root;
}

/* Axiom seviyesi: tek argümanlı sarmalayıcı. Hata mesajı icin
 * axiom_json_last_error() kullanilir. */
AXIOM_RUNTIME_FN ax_int axiom_json_parse_wrap(const char* text) {
    return axiom_json_parse(text, NULL, 0);
}

AXIOM_RUNTIME_FN ax_str axiom_json_last_error(void) {
    return axiom_safe_strdup(g_ax_json_err);
}

AXIOM_RUNTIME_FN void axiom_json_free(ax_int handle) {
    axj_free((ax_json_node*)(uintptr_t)handle);
}

AXIOM_RUNTIME_FN ax_int axiom_json_type_of(ax_int handle) {
    ax_json_node* n = (ax_json_node*)(uintptr_t)handle;
    return n ? (ax_int)n->type : -1;
}

AXIOM_RUNTIME_FN ax_int axiom_json_len(ax_int handle) {
    ax_json_node* n = (ax_json_node*)(uintptr_t)handle;
    if (!n) return 0;
    if (n->type == AXJ_ARR || n->type == AXJ_OBJ) return (ax_int)n->count;
    if (n->type == AXJ_STR) return (ax_int)strlen(n->str ? n->str : "");
    return 0;
}

AXIOM_RUNTIME_FN ax_int axiom_json_at(ax_int handle, ax_int index) {
    ax_json_node* n = (ax_json_node*)(uintptr_t)handle;
    if (!n || (n->type != AXJ_ARR && n->type != AXJ_OBJ)) return 0;
    if (index < 0 || index >= n->count) return 0;
    return (ax_int)(uintptr_t)n->items[index];
}

AXIOM_RUNTIME_FN ax_str axiom_json_key_at(ax_int handle, ax_int index) {
    ax_json_node* n = (ax_json_node*)(uintptr_t)handle;
    if (!n || n->type != AXJ_OBJ) return axiom_owned_str_wrap("");
    if (index < 0 || index >= n->count) return axiom_owned_str_wrap("");
    return axiom_safe_strdup(n->keys[index]);
}

/* Nesnede anahtar araması (tek seviye). 0 = bulunamadı. */
AXIOM_RUNTIME_FN ax_int axiom_json_get(ax_int handle, const char* key) {
    ax_json_node* n = (ax_json_node*)(uintptr_t)handle;
    if (!n || n->type != AXJ_OBJ || !key) return 0;
    for (int i = 0; i < n->count; i++) {
        if (strcmp(n->keys[i], key) == 0) return (ax_int)(uintptr_t)n->items[i];
    }
    return 0;
}

/* Yol ile erişim: "a.b[0].c" — nokta nesne, [n] dizi indeksi. */
AXIOM_RUNTIME_FN ax_int axiom_json_path(ax_int handle, const char* path) {
    ax_json_node* cur = (ax_json_node*)(uintptr_t)handle;
    if (!cur || !path) return 0;
    const char* p = path;
    while (*p) {
        if (*p == '.') { p++; continue; }
        if (*p == '[') {
            p++;
            char* endp = NULL;
            long idx = strtol(p, &endp, 10);
            if (endp == p || *endp != ']') return 0;
            p = endp + 1;
            if (!cur || (cur->type != AXJ_ARR && cur->type != AXJ_OBJ)) return 0;
            if (idx < 0 || idx >= cur->count) return 0;
            cur = cur->items[idx];
            continue;
        }
        /* anahtar */
        const char* start = p;
        while (*p && *p != '.' && *p != '[') p++;
        size_t klen = (size_t)(p - start);
        if (!cur || cur->type != AXJ_OBJ) return 0;
        int found = 0;
        for (int i = 0; i < cur->count; i++) {
            if (strlen(cur->keys[i]) == klen && strncmp(cur->keys[i], start, klen) == 0) {
                cur = cur->items[i];
                found = 1;
                break;
            }
        }
        if (!found) return 0;
    }
    return (ax_int)(uintptr_t)cur;
}

AXIOM_RUNTIME_FN ax_str axiom_json_node_str(ax_int handle) {
    ax_json_node* n = (ax_json_node*)(uintptr_t)handle;
    if (!n || n->type != AXJ_STR) return axiom_owned_str_wrap("");
    return axiom_safe_strdup(n->str ? n->str : "");
}

AXIOM_RUNTIME_FN ax_int axiom_json_node_int(ax_int handle) {
    ax_json_node* n = (ax_json_node*)(uintptr_t)handle;
    if (!n) return 0;
    if (n->type == AXJ_NUM) return (ax_int)n->num;
    if (n->type == AXJ_BOOL) return n->b ? 1 : 0;
    return 0;
}

AXIOM_RUNTIME_FN ax_float axiom_json_node_float(ax_int handle) {
    ax_json_node* n = (ax_json_node*)(uintptr_t)handle;
    return (n && n->type == AXJ_NUM) ? n->num : 0.0;
}

AXIOM_RUNTIME_FN ax_bool axiom_json_node_bool(ax_int handle) {
    ax_json_node* n = (ax_json_node*)(uintptr_t)handle;
    return (n && n->type == AXJ_BOOL) ? n->b : false;
}

AXIOM_RUNTIME_FN ax_bool axiom_json_node_is_null(ax_int handle) {
    ax_json_node* n = (ax_json_node*)(uintptr_t)handle;
    return (n && n->type == AXJ_NULL) ? true : false;
}

AXIOM_RUNTIME_FN ax_str axiom_json_build_object(ax_array_str keys, ax_array_str values) {
    ax_int n = keys.length < values.length ? keys.length : values.length;
    size_t cap = 32;
    for (ax_int i = 0; i < n; i++) {
        cap += (keys.data[i] ? strlen(keys.data[i]) * 2 : 0) +
               (values.data[i] ? strlen(values.data[i]) * 2 : 0) + 16;
    }
    char* buf = (char*)malloc(cap);
    if (!buf) return axiom_owned_str_wrap((char*)"{}");
    char* p = buf;
    *p++ = '{';
    for (ax_int i = 0; i < n; i++) {
        if (i > 0) *p++ = ',';
        *p++ = '"';
        const char* k = keys.data[i] ? keys.data[i] : "";
        while (*k) {
            if (*k == '"' || *k == '\\') *p++ = '\\';
            *p++ = *k++;
        }
        *p++ = '"';
        *p++ = ':';
        *p++ = '"';
        const char* v = values.data[i] ? values.data[i] : "";
        while (*v) {
            if (*v == '"' || *v == '\\') {
                *p++ = '\\';
                *p++ = *v;
            } else if (*v == '\n') {
                *p++ = '\\'; *p++ = 'n';
            } else if (*v == '\r') {
                *p++ = '\\'; *p++ = 'r';
            } else if (*v == '\t') {
                *p++ = '\\'; *p++ = 't';
            } else {
                *p++ = *v;
            }
            v++;
        }
        *p++ = '"';
    }
    *p++ = '}';
    *p = '\0';
    return axiom_owned_str_wrap(buf);
}

/* ========================================================================= */
/* --- PAKET 2: İLERİ AĞ VE İLETİŞİM PROTOKOLLERİ                        --- */
/* ========================================================================= */

/* --- 6. DNS Çözümleyici (std:net:dns) --- */

AXIOM_RUNTIME_FN ax_str axiom_dns_resolve_ipv4(const char* host) {
    if (!host || strlen(host) == 0) return axiom_owned_str_wrap("");
    struct addrinfo hints, *res = NULL;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;

    if (getaddrinfo(host, NULL, &hints, &res) != 0 || !res) {
        return axiom_owned_str_wrap("");
    }

    char buf[INET_ADDRSTRLEN];
    struct sockaddr_in* sa = (struct sockaddr_in*)res->ai_addr;
    if (inet_ntop(AF_INET, &(sa->sin_addr), buf, sizeof(buf)) == NULL) {
        freeaddrinfo(res);
        return axiom_owned_str_wrap("");
    }
    freeaddrinfo(res);
    return axiom_safe_strdup(buf);
}

AXIOM_RUNTIME_FN ax_str axiom_dns_resolve_ipv6(const char* host) {
    if (!host || strlen(host) == 0) return axiom_owned_str_wrap("");
    struct addrinfo hints, *res = NULL;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET6;
    hints.ai_socktype = SOCK_STREAM;

    if (getaddrinfo(host, NULL, &hints, &res) != 0 || !res) {
        return axiom_owned_str_wrap("");
    }

    char buf[INET6_ADDRSTRLEN];
    struct sockaddr_in6* sa = (struct sockaddr_in6*)res->ai_addr;
    if (inet_ntop(AF_INET6, &(sa->sin6_addr), buf, sizeof(buf)) == NULL) {
        freeaddrinfo(res);
        return axiom_owned_str_wrap("");
    }
    freeaddrinfo(res);
    return axiom_safe_strdup(buf);
}

AXIOM_RUNTIME_FN ax_str axiom_dns_reverse_lookup(const char* ip) {
    if (!ip || strlen(ip) == 0) return axiom_owned_str_wrap("");
    struct sockaddr_in sa;
    struct sockaddr_in6 sa6;
    struct sockaddr* sa_ptr = NULL;
    socklen_t sa_len = 0;

    if (inet_pton(AF_INET, ip, &sa.sin_addr) == 1) {
        sa.sin_family = AF_INET;
        sa_ptr = (struct sockaddr*)&sa;
        sa_len = sizeof(sa);
    } else if (inet_pton(AF_INET6, ip, &sa6.sin6_addr) == 1) {
        sa6.sin6_family = AF_INET6;
        sa_ptr = (struct sockaddr*)&sa6;
        sa_len = sizeof(sa6);
    } else {
        return axiom_owned_str_wrap("");
    }

    char host[NI_MAXHOST];
    if (getnameinfo(sa_ptr, sa_len, host, sizeof(host), NULL, 0, NI_NAMEREQD) == 0) {
        return axiom_safe_strdup(host);
    }
    return axiom_owned_str_wrap("");
}

/* --- 7. UDP Soket API'si (std:net:udp) --- */

AXIOM_RUNTIME_FN ax_int axiom_udp_socket(void) {
    int fd = ax_os_socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) return -1;
    struct timeval tv;
    tv.tv_sec = 2;
    tv.tv_usec = 0;
    ax_os_sock_set_timeout(fd, 2000);
    return (ax_int)fd;
}

AXIOM_RUNTIME_FN ax_int axiom_udp_bind(ax_int port) {
    if (port <= 0 || port > 65535) return -1;
    int fd = ax_os_socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) return -1;
    int opt = 1;
    ax_os_sock_set_reuse(fd);
    struct timeval tv;
    tv.tv_sec = 2;
    tv.tv_usec = 0;
    ax_os_sock_set_timeout(fd, 2000);

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons((uint16_t)port);

    if (bind(fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(fd);
        return -1;
    }
    return (ax_int)fd;
}

AXIOM_RUNTIME_FN ax_int axiom_udp_sendto(ax_int fd, const char* host, ax_int port, const char* data) {
    if (fd < 0 || !host || port <= 0 || port > 65535 || !data) return -1;
    struct sockaddr_in dest;
    memset(&dest, 0, sizeof(dest));
    dest.sin_family = AF_INET;
    dest.sin_port = htons((uint16_t)port);

    if (!axiom_internal_resolve_ipv4(host, &dest.sin_addr)) {
        return -1;
    }

    size_t len = strlen(data);
    ssize_t sent = sendto((int)fd, data, len, 0, (struct sockaddr*)&dest, sizeof(dest));
    return (ax_int)sent;
}

AXIOM_RUNTIME_FN ax_str axiom_udp_recvfrom(ax_int fd, ax_int max_bytes) {
    if (fd < 0) return axiom_owned_str_wrap("");
    if (max_bytes <= 0 || max_bytes > 65536) max_bytes = 4096;
    char* buf = (char*)malloc(max_bytes + 1);
    if (!buf) return axiom_owned_str_wrap("");

    struct sockaddr_in src;
    socklen_t srclen = sizeof(src);
    ssize_t r = recvfrom((int)fd, buf, (size_t)max_bytes, 0, (struct sockaddr*)&src, &srclen);
    if (r < 0) {
        free(buf);
        return axiom_owned_str_wrap("");
    }
    buf[r] = '\0';
    return axiom_owned_str_wrap(buf);
}

AXIOM_RUNTIME_FN void axiom_udp_close(ax_int fd) {
    if (fd >= 0) close((int)fd);
}

/* --- 8. Hafif Yerel HTTP Sunucusu (std:net:http_server) --- */

AXIOM_RUNTIME_FN ax_int axiom_http_server_create(ax_int port) {
    if (port <= 0 || port > 65535) return -1;
    int fd = ax_os_socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return -1;

    int opt = 1;
    ax_os_sock_set_reuse(fd);

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons((uint16_t)port);

    if (bind(fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(fd);
        return -1;
    }
    if (listen(fd, 64) < 0) {
        close(fd);
        return -1;
    }
    return (ax_int)fd;
}

AXIOM_RUNTIME_FN ax_int axiom_http_server_accept(ax_int server_fd) {
    if (server_fd < 0) return -1;
    struct sockaddr_in client;
    socklen_t clen = sizeof(client);
    int client_fd = accept((int)server_fd, (struct sockaddr*)&client, &clen);
    if (client_fd < 0) return -1;

    ax_os_sock_set_timeout(client_fd, 3000);
    return (ax_int)client_fd;
}

AXIOM_RUNTIME_FN void axiom_http_server_send_response(ax_int client_fd, ax_int status, const char* content_type, const char* body) {
    if (client_fd < 0) return;
    if (!content_type) content_type = "text/plain";
    if (!body) body = "";
    size_t body_len = strlen(body);

    const char* reason = "OK";
    if (status == 201) reason = "Created";
    else if (status == 204) reason = "No Content";
    else if (status == 400) reason = "Bad Request";
    else if (status == 404) reason = "Not Found";
    else if (status == 500) reason = "Internal Server Error";

    char header[512];
    int hlen = snprintf(header, sizeof(header),
        "HTTP/1.1 %" PRId64 " %s\r\n"
        "Content-Type: %s\r\n"
        "Content-Length: %zu\r\n"
        "Connection: close\r\n\r\n",
        status, reason, content_type, body_len);

    if (hlen > 0) {
        size_t total_len = (size_t)hlen + body_len;
        char* full_resp = (char*)malloc(total_len + 1);
        if (full_resp) {
            memcpy(full_resp, header, (size_t)hlen);
            if (body_len > 0) {
                memcpy(full_resp + hlen, body, body_len);
            }
            full_resp[total_len] = '\0';
            send((int)client_fd, full_resp, total_len, 0);
            free(full_resp);
        } else {
            send((int)client_fd, header, (size_t)hlen, 0);
            if (body_len > 0) send((int)client_fd, body, body_len, 0);
        }
    }
    ax_os_sock_shutdown_write(ax_os_int_to_sock(client_fd));

    /* Istek okunmadan kapatmak RST uretir; RST gonderilmis yaniti da
     * dusurebilir (istemci yarim/bozuk veri gorur). Yazma yonunu kapattiktan
     * sonra gelen baytlari tuketip temiz FIN ile kapat. */
    {
        char drain[512];
        int guard = 0;
        for (;;) {
            ssize_t r = recv((int)client_fd, drain, sizeof(drain), 0);
            if (r <= 0) break;
            if (++guard > 64) break;
        }
    }
    close((int)client_fd);
}

AXIOM_RUNTIME_FN void axiom_http_server_close(ax_int server_fd) {
    if (server_fd >= 0) close((int)server_fd);
}

/* --- 9. OpenSSL / TLS Güvenli Soket İstemcisi (std:crypto:tls) --- */

typedef void* (*ax_fn_TLS_client_method)(void);
typedef void* (*ax_fn_SSL_CTX_new)(const void*);
typedef void  (*ax_fn_SSL_CTX_free)(void*);
typedef void  (*ax_fn_SSL_CTX_set_verify)(void*, int, void*);
typedef int   (*ax_fn_SSL_CTX_set_default_verify_paths)(void*);
typedef int   (*ax_fn_SSL_CTX_load_verify_locations)(void*, const char*, const char*);
typedef void* (*ax_fn_SSL_new)(void*);
typedef int   (*ax_fn_SSL_set_fd)(void*, int);
typedef long  (*ax_fn_SSL_ctrl)(void*, int, long, void*);
typedef int   (*ax_fn_SSL_set1_host)(void*, const char*);
typedef int   (*ax_fn_SSL_set1_ip_asc)(void*, const char*);
typedef void* (*ax_fn_SSL_CTX_get0_param)(void*);
typedef int   (*ax_fn_X509_VERIFY_PARAM_set_flags)(void*, unsigned long);
typedef int   (*ax_fn_SSL_connect)(void*);
typedef int   (*ax_fn_SSL_write)(void*, const void*, int);
typedef int   (*ax_fn_SSL_read)(void*, void*, int);
typedef int   (*ax_fn_SSL_shutdown)(void*);
typedef void  (*ax_fn_SSL_free)(void*);
typedef long  (*ax_fn_SSL_get_verify_result)(const void*);

typedef struct {
    int fd;
    void* ssl;
    void* ctx;
    bool active;
} axiom_tls_slot_t;

#define AXIOM_MAX_TLS_SLOTS 64
static axiom_tls_slot_t g_axiom_tls_slots[AXIOM_MAX_TLS_SLOTS];
static bool g_axiom_tls_initialized = false;
static void* g_axiom_ssl_lib = NULL;
static ax_fn_TLS_client_method g_p_TLS_client_method = NULL;
static ax_fn_SSL_CTX_new g_p_SSL_CTX_new = NULL;
static ax_fn_SSL_CTX_free g_p_SSL_CTX_free = NULL;
static ax_fn_SSL_CTX_set_verify g_p_SSL_CTX_set_verify = NULL;
static ax_fn_SSL_CTX_set_default_verify_paths g_p_SSL_CTX_set_default_verify_paths = NULL;
static ax_fn_SSL_CTX_load_verify_locations g_p_SSL_CTX_load_verify_locations = NULL;
static ax_fn_SSL_new g_p_SSL_new = NULL;
static ax_fn_SSL_set_fd g_p_SSL_set_fd = NULL;
static ax_fn_SSL_ctrl g_p_SSL_ctrl = NULL;
static ax_fn_SSL_set1_host g_p_SSL_set1_host = NULL;
static ax_fn_SSL_set1_ip_asc g_p_SSL_set1_ip_asc = NULL;
static ax_fn_SSL_CTX_get0_param g_p_SSL_CTX_get0_param = NULL;
static ax_fn_X509_VERIFY_PARAM_set_flags g_p_X509_VERIFY_PARAM_set_flags = NULL;
static ax_fn_SSL_connect g_p_SSL_connect = NULL;
static ax_fn_SSL_write g_p_SSL_write = NULL;
static ax_fn_SSL_read g_p_SSL_read = NULL;
static ax_fn_SSL_shutdown g_p_SSL_shutdown = NULL;
static ax_fn_SSL_free g_p_SSL_free = NULL;
static ax_fn_SSL_get_verify_result g_p_SSL_get_verify_result = NULL;

AXIOM_RUNTIME_FN bool axiom_init_tls_lib(void) {
    if (g_axiom_tls_initialized) return g_axiom_ssl_lib != NULL;
    g_axiom_tls_initialized = true;

#if defined(AXIOM_OS_WINDOWS)
    g_axiom_ssl_lib = ax_os_lib_open("libssl-3-x64.dll");
    if (!g_axiom_ssl_lib) g_axiom_ssl_lib = ax_os_lib_open("libssl-1_1-x64.dll");
    if (!g_axiom_ssl_lib) g_axiom_ssl_lib = ax_os_lib_open("ssleay32.dll");
#else
    g_axiom_ssl_lib = ax_os_lib_open("libssl.so.3");
    if (!g_axiom_ssl_lib) g_axiom_ssl_lib = ax_os_lib_open("libssl.so");
#endif
    if (!g_axiom_ssl_lib) return false;

    g_p_TLS_client_method = (ax_fn_TLS_client_method)ax_os_lib_sym(g_axiom_ssl_lib, "TLS_client_method");
    g_p_SSL_CTX_new = (ax_fn_SSL_CTX_new)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_CTX_new");
    g_p_SSL_CTX_free = (ax_fn_SSL_CTX_free)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_CTX_free");
    g_p_SSL_CTX_set_verify = (ax_fn_SSL_CTX_set_verify)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_CTX_set_verify");
    g_p_SSL_CTX_set_default_verify_paths = (ax_fn_SSL_CTX_set_default_verify_paths)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_CTX_set_default_verify_paths");
    g_p_SSL_CTX_load_verify_locations = (ax_fn_SSL_CTX_load_verify_locations)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_CTX_load_verify_locations");
    g_p_SSL_new = (ax_fn_SSL_new)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_new");
    g_p_SSL_set_fd = (ax_fn_SSL_set_fd)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_set_fd");
    g_p_SSL_ctrl = (ax_fn_SSL_ctrl)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_ctrl");
    g_p_SSL_set1_host = (ax_fn_SSL_set1_host)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_set1_host");
    g_p_SSL_set1_ip_asc = (ax_fn_SSL_set1_ip_asc)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_set1_ip_asc");
    g_p_SSL_CTX_get0_param = (ax_fn_SSL_CTX_get0_param)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_CTX_get0_param");
    g_p_X509_VERIFY_PARAM_set_flags = (ax_fn_X509_VERIFY_PARAM_set_flags)ax_os_lib_sym(g_axiom_ssl_lib, "X509_VERIFY_PARAM_set_flags");
    g_p_SSL_connect = (ax_fn_SSL_connect)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_connect");
    g_p_SSL_write = (ax_fn_SSL_write)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_write");
    g_p_SSL_read = (ax_fn_SSL_read)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_read");
    g_p_SSL_shutdown = (ax_fn_SSL_shutdown)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_shutdown");
    g_p_SSL_free = (ax_fn_SSL_free)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_free");
    g_p_SSL_get_verify_result = (ax_fn_SSL_get_verify_result)ax_os_lib_sym(g_axiom_ssl_lib, "SSL_get_verify_result");

    if (!g_p_TLS_client_method || !g_p_SSL_CTX_new || !g_p_SSL_new || !g_p_SSL_connect) {
        ax_os_lib_close(g_axiom_ssl_lib);
        g_axiom_ssl_lib = NULL;
        return false;
    }
    return true;
}

AXIOM_RUNTIME_FN ax_int axiom_tls_connect(const char* host, ax_int port) {
    if (!host || port <= 0 || port > 65535) return -1;
    if (!axiom_init_tls_lib()) return -1;

    int slot = -1;
    for (int i = 0; i < AXIOM_MAX_TLS_SLOTS; i++) {
        if (!g_axiom_tls_slots[i].active) {
            slot = i;
            break;
        }
    }
    if (slot == -1) return -1;

    int sock = (int)axiom_tcp_connect(host, port);
    if (sock < 0) return -1;

    void* meth = g_p_TLS_client_method();
    void* ctx = g_p_SSL_CTX_new(meth);
    if (!ctx) {
        close(sock);
        return -1;
    }

    // TLS Guvenlik Sertlestirmesi: CA Sertifika Havuzu ve Peer Dogrulama
    const char* insecure_env = getenv("AXIOM_TLS_INSECURE");
    if (!insecure_env && g_p_SSL_CTX_set_default_verify_paths) {
        g_p_SSL_CTX_set_default_verify_paths(ctx);
    }
    const char* cert_file_env = getenv("SSL_CERT_FILE");
    if (cert_file_env && g_p_SSL_CTX_load_verify_locations) {
        g_p_SSL_CTX_load_verify_locations(ctx, cert_file_env, NULL);
    }
    if (g_p_SSL_CTX_get0_param && g_p_X509_VERIFY_PARAM_set_flags) {
        void* vpm = g_p_SSL_CTX_get0_param(ctx);
        if (vpm) g_p_X509_VERIFY_PARAM_set_flags(vpm, 0x80000 /* X509_V_FLAG_PARTIAL_CHAIN */);
    }
    if (g_p_SSL_CTX_set_verify) {
        int v_mode = (insecure_env && strcmp(insecure_env, "1") == 0) ? 0 /* SSL_VERIFY_NONE */ : 1 /* SSL_VERIFY_PEER */;
        g_p_SSL_CTX_set_verify(ctx, v_mode, NULL);
    }

    void* ssl = g_p_SSL_new(ctx);
    if (!ssl) {
        g_p_SSL_CTX_free(ctx);
        close(sock);
        return -1;
    }

    g_p_SSL_set_fd(ssl, sock);
    g_p_SSL_ctrl(ssl, 55, 0, (void*)host); // SSL_CTRL_SET_TLSEXT_HOSTNAME = 55
    if (!insecure_env || strcmp(insecure_env, "1") != 0) {
        struct in_addr _addr4;
        struct in6_addr _addr6;
        if (inet_pton(AF_INET, host, &_addr4) == 1 || inet_pton(AF_INET6, host, &_addr6) == 1) {
            if (g_p_SSL_set1_ip_asc) {
                g_p_SSL_set1_ip_asc(ssl, host);
            }
        } else {
            if (g_p_SSL_set1_host) {
                g_p_SSL_set1_host(ssl, host); // Hostname dogrulama
            }
        }
    }

    int conn_res = g_p_SSL_connect(ssl);
    if (conn_res <= 0) {
        g_p_SSL_free(ssl);
        g_p_SSL_CTX_free(ctx);
        close(sock);
        return -1;
    }

    if (!insecure_env || strcmp(insecure_env, "1") != 0) {
        if (g_p_SSL_get_verify_result) {
            long v_res = g_p_SSL_get_verify_result(ssl);
            if (v_res != 0 /* X509_V_OK */) {
                g_p_SSL_free(ssl);
                g_p_SSL_CTX_free(ctx);
                close(sock);
                return -1;
            }
        }
    }

    g_axiom_tls_slots[slot].fd = sock;
    g_axiom_tls_slots[slot].ssl = ssl;
    g_axiom_tls_slots[slot].ctx = ctx;
    g_axiom_tls_slots[slot].active = true;
    return (ax_int)slot;
}

AXIOM_RUNTIME_FN ax_int axiom_tls_send(ax_int tls_id, const char* data) {
    if (tls_id < 0 || tls_id >= AXIOM_MAX_TLS_SLOTS || !g_axiom_tls_slots[tls_id].active || !data) return -1;
    int len = (int)strlen(data);
    int written = g_p_SSL_write(g_axiom_tls_slots[tls_id].ssl, data, len);
    return (ax_int)written;
}

AXIOM_RUNTIME_FN ax_str axiom_tls_recv(ax_int tls_id, ax_int max_bytes) {
    if (tls_id < 0 || tls_id >= AXIOM_MAX_TLS_SLOTS || !g_axiom_tls_slots[tls_id].active) return axiom_owned_str_wrap("");
    if (max_bytes <= 0 || max_bytes > 1048576) max_bytes = 16384;
    char* buf = (char*)malloc(max_bytes + 1);
    if (!buf) return axiom_owned_str_wrap("");

    int read_bytes = g_p_SSL_read(g_axiom_tls_slots[tls_id].ssl, buf, (int)max_bytes);
    if (read_bytes <= 0) {
        free(buf);
        return axiom_owned_str_wrap("");
    }
    buf[read_bytes] = '\0';
    return axiom_owned_str_wrap(buf);
}

AXIOM_RUNTIME_FN void axiom_tls_close(ax_int tls_id) {
    if (tls_id < 0 || tls_id >= AXIOM_MAX_TLS_SLOTS || !g_axiom_tls_slots[tls_id].active) return;
    g_p_SSL_shutdown(g_axiom_tls_slots[tls_id].ssl);
    g_p_SSL_free(g_axiom_tls_slots[tls_id].ssl);
    g_p_SSL_CTX_free(g_axiom_tls_slots[tls_id].ctx);
    close(g_axiom_tls_slots[tls_id].fd);
    g_axiom_tls_slots[tls_id].ssl = NULL;
    g_axiom_tls_slots[tls_id].ctx = NULL;
    g_axiom_tls_slots[tls_id].active = false;
}

/* --- 10. RFC 6455 WebSocket İstemcisi (std:net:websocket) --- */

AXIOM_RUNTIME_FN ax_int axiom_ws_connect(const char* host, ax_int port, const char* path) {
    if (!host || port <= 0 || port > 65535) return -1;
    if (!path || strlen(path) == 0) path = "/";

    int sock = (int)axiom_tcp_connect(host, port);
    if (sock < 0) return -1;

    char handshake[1024];
    int hlen = snprintf(handshake, sizeof(handshake),
        "GET %s HTTP/1.1\r\n"
        "Host: %s:%" PRId64 "\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n",
        path, host, port);

    if (send(sock, handshake, (size_t)hlen, 0) < 0) {
        close(sock);
        return -1;
    }

    char resp[1024];
    memset(resp, 0, sizeof(resp));
    ssize_t r = recv(sock, resp, sizeof(resp) - 1, 0);
    if (r <= 0 || strstr(resp, "101") == NULL) {
        close(sock);
        return -1;
    }

    return (ax_int)sock;
}

AXIOM_RUNTIME_FN ax_int axiom_ws_send(ax_int fd, const char* message) {
    if (fd < 0 || !message) return -1;
    size_t len = strlen(message);
    size_t header_len = 2; // opcode + len
    if (len >= 126 && len <= 65535) header_len += 2;
    else if (len > 65535) header_len += 8;
    header_len += 4; // 4 bytes mask

    uint8_t* frame = (uint8_t*)malloc(header_len + len);
    if (!frame) return -1;

    size_t idx = 0;
    frame[idx++] = 0x81; // FIN + text opcode

    if (len <= 125) {
        frame[idx++] = 0x80 | (uint8_t)len;
    } else if (len <= 65535) {
        frame[idx++] = 0x80 | 126;
        frame[idx++] = (uint8_t)((len >> 8) & 0xFF);
        frame[idx++] = (uint8_t)(len & 0xFF);
    } else {
        frame[idx++] = 0x80 | 127;
        for (int i = 7; i >= 0; i--) {
            frame[idx++] = (uint8_t)((len >> (i * 8)) & 0xFF);
        }
    }

    uint8_t mask[4] = { 0x41, 0x58, 0x49, 0x4F }; // 'AXIO'
    memcpy(&frame[idx], mask, 4);
    idx += 4;

    for (size_t i = 0; i < len; i++) {
        frame[idx++] = ((uint8_t)message[i]) ^ mask[i % 4];
    }

    ssize_t total_sent = 0;
    size_t to_send = idx;
    while (to_send > 0) {
        ssize_t s = send((int)fd, frame + total_sent, to_send, 0);
        if (s <= 0) {
            free(frame);
            return -1;
        }
        total_sent += s;
        to_send -= (size_t)s;
    }

    free(frame);
    return (ax_int)len;
}

AXIOM_RUNTIME_FN ax_str axiom_ws_recv(ax_int fd) {
    if (fd < 0) return axiom_owned_str_wrap("");
    uint8_t hdr[2];
    ssize_t r = recv((int)fd, hdr, 2, MSG_WAITALL);
    if (r < 2) return axiom_owned_str_wrap("");

    uint8_t b1 = hdr[1];
    bool is_masked = (b1 & 0x80) != 0;
    uint64_t payload_len = (b1 & 0x7F);

    if (payload_len == 126) {
        uint8_t ext[2];
        if (recv((int)fd, ext, 2, MSG_WAITALL) < 2) return axiom_owned_str_wrap("");
        payload_len = ((uint64_t)ext[0] << 8) | (uint64_t)ext[1];
    } else if (payload_len == 127) {
        uint8_t ext[8];
        if (recv((int)fd, ext, 8, MSG_WAITALL) < 8) return axiom_owned_str_wrap("");
        payload_len = 0;
        for (int i = 0; i < 8; i++) {
            payload_len = (payload_len << 8) | (uint64_t)ext[i];
        }
    }

    uint8_t mask[4];
    if (is_masked) {
        if (recv((int)fd, mask, 4, MSG_WAITALL) < 4) return axiom_owned_str_wrap("");
    }

    if (payload_len > 10485760) return axiom_owned_str_wrap("");

    char* buf = (char*)malloc(payload_len + 1);
    if (!buf) return axiom_owned_str_wrap("");

    size_t recvd = 0;
    while (recvd < payload_len) {
        ssize_t n = recv((int)fd, buf + recvd, payload_len - recvd, 0);
        if (n <= 0) break;
        recvd += (size_t)n;
    }
    buf[recvd] = '\0';

    if (is_masked) {
        for (size_t i = 0; i < recvd; i++) {
            buf[i] ^= mask[i % 4];
        }
    }

    return axiom_owned_str_wrap(buf);
}

AXIOM_RUNTIME_FN void axiom_ws_close(ax_int fd) {
    if (fd >= 0) {
        uint8_t close_frame[6] = { 0x88, 0x80, 0x12, 0x34, 0x56, 0x78 };
        send((int)fd, close_frame, sizeof(close_frame), 0);
        close((int)fd);
    }
}

/* =========================================================================
 * PAKET 3: Sistem, İkili Veri ve Dosya İşleme Motorları
 * 11. std:io:binary
 * 12. std:os:process
 * 13. std:compress:zlib
 * 14. std:text:regex
 * 15. std:collections:map
 * ========================================================================= */

AXIOM_RUNTIME_FN char* axiom_p3_strdup(const char* s) {
    if (!s) return NULL;
    size_t l = strlen(s);
    char* r = (char*)malloc(l + 1);
    if (r) {
        memcpy(r, s, l + 1);
    }
    return r;
}

/* -------------------------------------------------------------------------
 * 11. std:io:binary (Byte Buffer)
 * ------------------------------------------------------------------------- */
typedef struct {
    uint8_t* data;
    size_t len;
    size_t cap;
} AxiomByteBuffer;

#define AXIOM_MAX_BUFFERS 4096
static AxiomByteBuffer* g_active_buffers[AXIOM_MAX_BUFFERS] = {0};

AXIOM_RUNTIME_FN void axiom_buf_register(AxiomByteBuffer* b) {
    if (!b) return;
    for (int i = 0; i < AXIOM_MAX_BUFFERS; i++) {
        if (!g_active_buffers[i]) {
            g_active_buffers[i] = b;
            return;
        }
    }
}

AXIOM_RUNTIME_FN bool axiom_buf_is_valid(AxiomByteBuffer* b) {
    if (!b) return false;
    for (int i = 0; i < AXIOM_MAX_BUFFERS; i++) {
        if (g_active_buffers[i] == b) return true;
    }
    return false;
}

AXIOM_RUNTIME_FN bool axiom_buf_unregister(AxiomByteBuffer* b) {
    if (!b) return false;
    for (int i = 0; i < AXIOM_MAX_BUFFERS; i++) {
        if (g_active_buffers[i] == b) {
            g_active_buffers[i] = NULL;
            return true;
        }
    }
    return false;
}

AXIOM_RUNTIME_FN void axiom_buf_ensure_cap(AxiomByteBuffer* b, size_t needed) {
    if (!b) return;
    if (b->len + needed > b->cap) {
        size_t new_cap = b->cap * 2;
        if (new_cap < b->len + needed) new_cap = b->len + needed + 64;
        uint8_t* nd = (uint8_t*)realloc(b->data, new_cap);
        if (nd) {
            b->data = nd;
            b->cap = new_cap;
        }
    }
}

AXIOM_RUNTIME_FN ax_int axiom_buf_create(ax_int cap) {
    if (cap < 16) cap = 16;
    AxiomByteBuffer* b = (AxiomByteBuffer*)malloc(sizeof(AxiomByteBuffer));
    if (!b) return 0;
    b->data = (uint8_t*)malloc((size_t)cap);
    if (!b->data) {
        free(b);
        return 0;
    }
    b->len = 0;
    b->cap = (size_t)cap;
    axiom_buf_register(b);
    return (ax_int)(uintptr_t)b;
}

AXIOM_RUNTIME_FN void axiom_buf_write_u8(ax_int handle, ax_int val) {
    if (handle <= 0) return;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data) return;
    axiom_buf_ensure_cap(b, 1);
    b->data[b->len++] = (uint8_t)(val & 0xFF);
}

AXIOM_RUNTIME_FN void axiom_buf_write_u16_be(ax_int handle, ax_int val) {
    if (handle <= 0) return;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data) return;
    axiom_buf_ensure_cap(b, 2);
    uint16_t v = (uint16_t)(val & 0xFFFF);
    b->data[b->len++] = (uint8_t)((v >> 8) & 0xFF);
    b->data[b->len++] = (uint8_t)(v & 0xFF);
}

AXIOM_RUNTIME_FN void axiom_buf_write_u16_le(ax_int handle, ax_int val) {
    if (handle <= 0) return;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data) return;
    axiom_buf_ensure_cap(b, 2);
    uint16_t v = (uint16_t)(val & 0xFFFF);
    b->data[b->len++] = (uint8_t)(v & 0xFF);
    b->data[b->len++] = (uint8_t)((v >> 8) & 0xFF);
}

AXIOM_RUNTIME_FN void axiom_buf_write_u32_be(ax_int handle, ax_int val) {
    if (handle <= 0) return;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data) return;
    axiom_buf_ensure_cap(b, 4);
    uint32_t v = (uint32_t)(val & 0xFFFFFFFF);
    b->data[b->len++] = (uint8_t)((v >> 24) & 0xFF);
    b->data[b->len++] = (uint8_t)((v >> 16) & 0xFF);
    b->data[b->len++] = (uint8_t)((v >> 8) & 0xFF);
    b->data[b->len++] = (uint8_t)(v & 0xFF);
}

AXIOM_RUNTIME_FN void axiom_buf_write_u32_le(ax_int handle, ax_int val) {
    if (handle <= 0) return;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data) return;
    axiom_buf_ensure_cap(b, 4);
    uint32_t v = (uint32_t)(val & 0xFFFFFFFF);
    b->data[b->len++] = (uint8_t)(v & 0xFF);
    b->data[b->len++] = (uint8_t)((v >> 8) & 0xFF);
    b->data[b->len++] = (uint8_t)((v >> 16) & 0xFF);
    b->data[b->len++] = (uint8_t)((v >> 24) & 0xFF);
}

AXIOM_RUNTIME_FN void axiom_buf_write_u64_be(ax_int handle, ax_int val) {
    if (handle <= 0) return;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data) return;
    axiom_buf_ensure_cap(b, 8);
    uint64_t v = (uint64_t)val;
    for (int i = 7; i >= 0; i--) {
        b->data[b->len++] = (uint8_t)((v >> (i * 8)) & 0xFF);
    }
}

AXIOM_RUNTIME_FN void axiom_buf_write_u64_le(ax_int handle, ax_int val) {
    if (handle <= 0) return;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data) return;
    axiom_buf_ensure_cap(b, 8);
    uint64_t v = (uint64_t)val;
    for (int i = 0; i < 8; i++) {
        b->data[b->len++] = (uint8_t)((v >> (i * 8)) & 0xFF);
    }
}

AXIOM_RUNTIME_FN void axiom_buf_write_str(ax_int handle, const char* s) {
    if (handle <= 0 || !s) return;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data) return;
    size_t slen = strlen(s);
    if (slen == 0) return;
    axiom_buf_ensure_cap(b, slen);
    memcpy(b->data + b->len, s, slen);
    b->len += slen;
}

AXIOM_RUNTIME_FN ax_str axiom_buf_to_hex(ax_int handle) {
    if (handle <= 0) return axiom_owned_str_wrap("");
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data || b->len == 0) return axiom_owned_str_wrap("");
    char* hex = (char*)malloc(b->len * 2 + 1);
    if (!hex) return axiom_owned_str_wrap("");
    static const char hex_chars[] = "0123456789abcdef";
    for (size_t i = 0; i < b->len; i++) {
        hex[i * 2] = hex_chars[(b->data[i] >> 4) & 0x0F];
        hex[i * 2 + 1] = hex_chars[b->data[i] & 0x0F];
    }
    hex[b->len * 2] = '\0';
    return axiom_owned_str_wrap(hex);
}

AXIOM_RUNTIME_FN ax_str axiom_buf_to_str(ax_int handle) {
    if (handle <= 0) return axiom_owned_str_wrap("");
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data || b->len == 0) return axiom_owned_str_wrap("");
    char* s = (char*)malloc(b->len + 1);
    if (!s) return axiom_owned_str_wrap("");
    memcpy(s, b->data, b->len);
    s[b->len] = '\0';
    return axiom_owned_str_wrap(s);
}

AXIOM_RUNTIME_FN ax_int axiom_buf_len(ax_int handle) {
    if (handle <= 0) return 0;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b)) return 0;
    return (ax_int)b->len;
}

AXIOM_RUNTIME_FN ax_int axiom_buf_from_hex(const char* hex_str) {
    if (!hex_str) return axiom_buf_create(16);
    size_t slen = strlen(hex_str);
    size_t byte_len = slen / 2;
    ax_int handle = axiom_buf_create((ax_int)(byte_len > 0 ? byte_len : 16));
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!b) return 0;
    for (size_t i = 0; i < byte_len; i++) {
        char h1 = hex_str[i * 2];
        char h2 = hex_str[i * 2 + 1];
        int v1 = (h1 >= '0' && h1 <= '9') ? (h1 - '0') :
                 (h1 >= 'a' && h1 <= 'f') ? (h1 - 'a' + 10) :
                 (h1 >= 'A' && h1 <= 'F') ? (h1 - 'A' + 10) : 0;
        int v2 = (h2 >= '0' && h2 <= '9') ? (h2 - '0') :
                 (h2 >= 'a' && h2 <= 'f') ? (h2 - 'a' + 10) :
                 (h2 >= 'A' && h2 <= 'F') ? (h2 - 'A' + 10) : 0;
        b->data[b->len++] = (uint8_t)((v1 << 4) | v2);
    }
    return handle;
}

AXIOM_RUNTIME_FN ax_int axiom_buf_read_u8(ax_int handle, ax_int offset) {
    if (handle <= 0) return 0;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data || offset < 0 || (size_t)offset >= b->len) return 0;
    return (ax_int)b->data[offset];
}

AXIOM_RUNTIME_FN ax_int axiom_buf_read_u16_be(ax_int handle, ax_int offset) {
    if (handle <= 0) return 0;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data || offset < 0 || (size_t)offset + 2 > b->len) return 0;
    size_t o = (size_t)offset;
    uint16_t v = ((uint16_t)b->data[o] << 8) | (uint16_t)b->data[o + 1];
    return (ax_int)v;
}

AXIOM_RUNTIME_FN ax_int axiom_buf_read_u16_le(ax_int handle, ax_int offset) {
    if (handle <= 0) return 0;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data || offset < 0 || (size_t)offset + 2 > b->len) return 0;
    size_t o = (size_t)offset;
    uint16_t v = (uint16_t)b->data[o] | ((uint16_t)b->data[o + 1] << 8);
    return (ax_int)v;
}

AXIOM_RUNTIME_FN ax_int axiom_buf_read_u32_be(ax_int handle, ax_int offset) {
    if (handle <= 0) return 0;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data || offset < 0 || (size_t)offset + 4 > b->len) return 0;
    size_t o = (size_t)offset;
    uint32_t v = ((uint32_t)b->data[o] << 24) |
                 ((uint32_t)b->data[o + 1] << 16) |
                 ((uint32_t)b->data[o + 2] << 8) |
                 ((uint32_t)b->data[o + 3]);
    return (ax_int)v;
}

AXIOM_RUNTIME_FN ax_int axiom_buf_read_u32_le(ax_int handle, ax_int offset) {
    if (handle <= 0) return 0;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data || offset < 0 || (size_t)offset + 4 > b->len) return 0;
    size_t o = (size_t)offset;
    uint32_t v = ((uint32_t)b->data[o]) |
                 ((uint32_t)b->data[o + 1] << 8) |
                 ((uint32_t)b->data[o + 2] << 16) |
                 ((uint32_t)b->data[o + 3] << 24);
    return (ax_int)v;
}

AXIOM_RUNTIME_FN ax_int axiom_buf_read_u64_be(ax_int handle, ax_int offset) {
    if (handle <= 0) return 0;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data || offset < 0 || (size_t)offset + 8 > b->len) return 0;
    size_t o = (size_t)offset;
    uint64_t v = 0;
    for (int i = 0; i < 8; i++) {
        v = (v << 8) | (uint64_t)b->data[o + i];
    }
    return (ax_int)v;
}

AXIOM_RUNTIME_FN ax_int axiom_buf_read_u64_le(ax_int handle, ax_int offset) {
    if (handle <= 0) return 0;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data || offset < 0 || (size_t)offset + 8 > b->len) return 0;
    size_t o = (size_t)offset;
    uint64_t v = 0;
    for (int i = 7; i >= 0; i--) {
        v = (v << 8) | (uint64_t)b->data[o + i];
    }
    return (ax_int)v;
}

AXIOM_RUNTIME_FN void axiom_buf_free(ax_int handle) {
    if (handle <= 0) return;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_unregister(b)) {
        return; /* Zaten serbest bırakılmış veya geçersiz handle (Double-Free Koruması) */
    }
    axiom_safe_free(b->data);
    axiom_safe_free(b);
}

/* -------------------------------------------------------------------------
 * 12. std:os:process (Alt Süreç ve Sinyal Yönetimi)
 * ------------------------------------------------------------------------- */
AXIOM_RUNTIME_FN ax_str axiom_process_exec_output(const char* cmd) {
    if (!cmd) return axiom_owned_str_wrap("");
    FILE* fp = popen(cmd, "r");
    if (!fp) return axiom_owned_str_wrap("");

    size_t cap = 1024;
    size_t len = 0;
    char* buf = (char*)malloc(cap);
    if (!buf) {
        pclose(fp);
        return axiom_owned_str_wrap("");
    }

    char temp[512];
    while (fgets(temp, sizeof(temp), fp) != NULL) {
        size_t n = strlen(temp);
        if (len + n + 1 > cap) {
            cap = (cap * 2 > len + n + 1) ? cap * 2 : len + n + 512;
            char* nb = (char*)realloc(buf, cap);
            if (!nb) break;
            buf = nb;
        }
        memcpy(buf + len, temp, n);
        len += n;
    }
    buf[len] = '\0';
    pclose(fp);
    return axiom_owned_str_wrap(buf);
}

AXIOM_RUNTIME_FN ax_int axiom_process_get_pid(void) {
    return (ax_int)ax_os_getpid();
}

AXIOM_RUNTIME_FN ax_int axiom_process_kill(ax_int pid, ax_int sig) {
    return (ax_int)ax_os_kill((long long)pid, (int)sig);
}

AXIOM_RUNTIME_FN ax_int axiom_process_spawn_bg(const char* cmd) {
    return (ax_int)ax_os_spawn_bg(cmd);
}

#if AXIOM_HAVE_ZLIB
/* -------------------------------------------------------------------------
 * 13. std:compress:zlib (Gzip & Deflate Sıkıştırma/Açma)
 * ------------------------------------------------------------------------- */
typedef int (*ax_fn_deflateInit2)(z_streamp, int, int, int, int, int, const char*, int);
typedef uLong (*ax_fn_deflateBound)(z_streamp, uLong);
typedef int (*ax_fn_deflate)(z_streamp, int);
typedef int (*ax_fn_deflateEnd)(z_streamp);
typedef int (*ax_fn_inflateInit2)(z_streamp, int, const char*, int);
typedef int (*ax_fn_inflate)(z_streamp, int);
typedef int (*ax_fn_inflateEnd)(z_streamp);
typedef int (*ax_fn_deflateInit)(z_streamp, int, const char*, int);

static void* g_axiom_zlib_handle = NULL;
static bool g_axiom_zlib_initialized = false;
static ax_fn_deflateInit2 g_p_deflateInit2 = NULL;
static ax_fn_deflateBound g_p_deflateBound = NULL;
static ax_fn_deflate g_p_deflate = NULL;
static ax_fn_deflateEnd g_p_deflateEnd = NULL;
static ax_fn_inflateInit2 g_p_inflateInit2 = NULL;
static ax_fn_inflate g_p_inflate = NULL;
static ax_fn_inflateEnd g_p_inflateEnd = NULL;
static ax_fn_deflateInit g_p_deflateInit = NULL;

AXIOM_RUNTIME_FN bool axiom_init_zlib(void) {
    if (g_axiom_zlib_initialized) return g_axiom_zlib_handle != NULL;
    g_axiom_zlib_initialized = true;

    g_axiom_zlib_handle = ax_os_lib_open("libz.so.1");
    if (!g_axiom_zlib_handle) g_axiom_zlib_handle = ax_os_lib_open("libz.so");
    if (!g_axiom_zlib_handle) return false;

    g_p_deflateInit2 = (ax_fn_deflateInit2)ax_os_lib_sym(g_axiom_zlib_handle, "deflateInit2_");
    g_p_deflateBound = (ax_fn_deflateBound)ax_os_lib_sym(g_axiom_zlib_handle, "deflateBound");
    g_p_deflate = (ax_fn_deflate)ax_os_lib_sym(g_axiom_zlib_handle, "deflate");
    g_p_deflateEnd = (ax_fn_deflateEnd)ax_os_lib_sym(g_axiom_zlib_handle, "deflateEnd");
    g_p_inflateInit2 = (ax_fn_inflateInit2)ax_os_lib_sym(g_axiom_zlib_handle, "inflateInit2_");
    g_p_inflate = (ax_fn_inflate)ax_os_lib_sym(g_axiom_zlib_handle, "inflate");
    g_p_inflateEnd = (ax_fn_inflateEnd)ax_os_lib_sym(g_axiom_zlib_handle, "inflateEnd");
    g_p_deflateInit = (ax_fn_deflateInit)ax_os_lib_sym(g_axiom_zlib_handle, "deflateInit_");

    if (!g_p_deflateInit2 || !g_p_deflateBound || !g_p_deflate || !g_p_deflateEnd ||
        !g_p_inflateInit2 || !g_p_inflate || !g_p_inflateEnd || !g_p_deflateInit) {
        ax_os_lib_close(g_axiom_zlib_handle);
        g_axiom_zlib_handle = NULL;
        return false;
    }
    return true;
}

AXIOM_RUNTIME_FN ax_str axiom_gzip_compress(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    if (!axiom_init_zlib()) return axiom_owned_str_wrap("");
    size_t slen = strlen(s);
    z_stream strm;
    memset(&strm, 0, sizeof(strm));
    if (g_p_deflateInit2(&strm, Z_DEFAULT_COMPRESSION, Z_DEFLATED, 15 + 16, 8, Z_DEFAULT_STRATEGY, ZLIB_VERSION, (int)sizeof(z_stream)) != Z_OK) {
        return axiom_owned_str_wrap("");
    }

    size_t out_cap = g_p_deflateBound(&strm, (uLong)slen) + 64;
    uint8_t* out_buf = (uint8_t*)malloc(out_cap);
    if (!out_buf) {
        g_p_deflateEnd(&strm);
        return axiom_owned_str_wrap("");
    }

    strm.next_in = (Bytef*)s;
    strm.avail_in = (uInt)slen;
    strm.next_out = out_buf;
    strm.avail_out = (uInt)out_cap;

    g_p_deflate(&strm, Z_FINISH);
    size_t comp_len = strm.total_out;
    g_p_deflateEnd(&strm);

    char* hex = (char*)malloc(comp_len * 2 + 1);
    if (!hex) {
        free(out_buf);
        return axiom_owned_str_wrap("");
    }
    static const char hex_chars[] = "0123456789abcdef";
    for (size_t i = 0; i < comp_len; i++) {
        hex[i * 2] = hex_chars[(out_buf[i] >> 4) & 0x0F];
        hex[i * 2 + 1] = hex_chars[out_buf[i] & 0x0F];
    }
    hex[comp_len * 2] = '\0';
    free(out_buf);
    return axiom_owned_str_wrap(hex);
}

AXIOM_RUNTIME_FN ax_str axiom_gzip_decompress(const char* hex_str) {
    if (!hex_str) return axiom_owned_str_wrap("");
    if (!axiom_init_zlib()) return axiom_owned_str_wrap("");
    size_t hlen = strlen(hex_str);
    size_t in_len = hlen / 2;
    if (in_len == 0) return axiom_owned_str_wrap("");

    uint8_t* in_buf = (uint8_t*)malloc(in_len);
    if (!in_buf) return axiom_owned_str_wrap("");

    for (size_t i = 0; i < in_len; i++) {
        char h1 = hex_str[i * 2];
        char h2 = hex_str[i * 2 + 1];
        int v1 = (h1 >= '0' && h1 <= '9') ? (h1 - '0') :
                 (h1 >= 'a' && h1 <= 'f') ? (h1 - 'a' + 10) :
                 (h1 >= 'A' && h1 <= 'F') ? (h1 - 'A' + 10) : 0;
        int v2 = (h2 >= '0' && h2 <= '9') ? (h2 - '0') :
                 (h2 >= 'a' && h2 <= 'f') ? (h2 - 'a' + 10) :
                 (h2 >= 'A' && h2 <= 'F') ? (h2 - 'A' + 10) : 0;
        in_buf[i] = (uint8_t)((v1 << 4) | v2);
    }

    z_stream strm;
    memset(&strm, 0, sizeof(strm));
    if (g_p_inflateInit2(&strm, 15 + 32, ZLIB_VERSION, (int)sizeof(z_stream)) != Z_OK) {
        free(in_buf);
        return axiom_owned_str_wrap("");
    }

    strm.next_in = in_buf;
    strm.avail_in = (uInt)in_len;

    size_t out_cap = in_len * 4 + 1024;
    char* out_buf = (char*)malloc(out_cap);
    if (!out_buf) {
        g_p_inflateEnd(&strm);
        free(in_buf);
        return axiom_owned_str_wrap("");
    }

    strm.next_out = (Bytef*)out_buf;
    strm.avail_out = (uInt)out_cap;

    int ret = Z_OK;
    while (ret == Z_OK) {
        ret = g_p_inflate(&strm, Z_NO_FLUSH);
        if (ret == Z_STREAM_END) break;
        if (ret != Z_OK) break;
        if (strm.avail_out == 0) {
            size_t old_len = out_cap;
            out_cap *= 2;
            char* nb = (char*)realloc(out_buf, out_cap);
            if (!nb) {
                ret = Z_MEM_ERROR;
                break;
            }
            out_buf = nb;
            strm.next_out = (Bytef*)(out_buf + old_len);
            strm.avail_out = (uInt)(out_cap - old_len);
        }
    }

    size_t final_len = strm.total_out;
    g_p_inflateEnd(&strm);
    free(in_buf);

    if (ret != Z_STREAM_END && ret != Z_OK) {
        free(out_buf);
        return axiom_owned_str_wrap("");
    }

    out_buf[final_len] = '\0';
    return axiom_owned_str_wrap(out_buf);
}

AXIOM_RUNTIME_FN ax_str axiom_zlib_compress_str(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    if (!axiom_init_zlib()) return axiom_owned_str_wrap("");
    size_t slen = strlen(s);
    z_stream strm;
    memset(&strm, 0, sizeof(strm));
    if (g_p_deflateInit(&strm, Z_DEFAULT_COMPRESSION, ZLIB_VERSION, (int)sizeof(z_stream)) != Z_OK) {
        return axiom_owned_str_wrap("");
    }

    size_t out_cap = g_p_deflateBound(&strm, (uLong)slen) + 64;
    uint8_t* out_buf = (uint8_t*)malloc(out_cap);
    if (!out_buf) {
        g_p_deflateEnd(&strm);
        return axiom_owned_str_wrap("");
    }

    strm.next_in = (Bytef*)s;
    strm.avail_in = (uInt)slen;
    strm.next_out = out_buf;
    strm.avail_out = (uInt)out_cap;

    g_p_deflate(&strm, Z_FINISH);
    size_t comp_len = strm.total_out;
    g_p_deflateEnd(&strm);

    char* hex = (char*)malloc(comp_len * 2 + 1);
    if (!hex) {
        free(out_buf);
        return axiom_owned_str_wrap("");
    }
    static const char hex_chars[] = "0123456789abcdef";
    for (size_t i = 0; i < comp_len; i++) {
        hex[i * 2] = hex_chars[(out_buf[i] >> 4) & 0x0F];
        hex[i * 2 + 1] = hex_chars[out_buf[i] & 0x0F];
    }
    hex[comp_len * 2] = '\0';
    free(out_buf);
    return axiom_owned_str_wrap(hex);
}

AXIOM_RUNTIME_FN ax_str axiom_zlib_decompress_str(const char* hex_str) {
    return axiom_gzip_decompress(hex_str);
}

#else  /* !AXIOM_HAVE_ZLIB ------------------------------------------------ */

/* zlib yoksa sikistirma ACIK HATA dondurur (sessiz bos veri yasak). */
#define AXIOM_NO_ZLIB_MSG "sikistirma: bu yapida zlib yok (sessiz bos sonuc verilmez)"
AXIOM_RUNTIME_FN ax_str axiom_gzip_compress(const char* s) {
    (void)s; return axiom_owned_str_wrap(AXIOM_NO_ZLIB_MSG);
}
AXIOM_RUNTIME_FN ax_str axiom_gzip_decompress(const char* h) {
    (void)h; return axiom_owned_str_wrap("");
}
AXIOM_RUNTIME_FN ax_str axiom_zlib_compress_str(const char* s) {
    (void)s; return axiom_owned_str_wrap(AXIOM_NO_ZLIB_MSG);
}
AXIOM_RUNTIME_FN ax_str axiom_zlib_decompress_str(const char* h) {
    (void)h; return axiom_owned_str_wrap("");
}

#endif /* AXIOM_HAVE_ZLIB */

#define AXIOM_REGEX_MAX_PATTERN   4096
#define AXIOM_REGEX_MAX_DEPTH       32
#define AXIOM_REGEX_MAX_REPEAT    1024

#if AXIOM_HAVE_POSIX_REGEX
/* -------------------------------------------------------------------------
 * 14. std:text:regex (POSIX Regular Expressions)
 *
 * Motor: glibc POSIX `regexec` — geri izleme (backtracking) yapmayan NFA.
 * Yine de derleme/DFA buyumesi ve asiri tekrar sayilari icin sert sinirlar
 * uygulanir. Guvenlik araclarinda sessiz `false` yerine neden donduren
 * `*_result` API'si tercih edilmelidir.
 * ------------------------------------------------------------------------- */
/* ')' karakterinin eslestigi '(' konumunu dondurur; yoksa -1. */
static int axiom_regex_matching_open(const char* p, int close_idx) {
    int depth = 0;
    for (int i = close_idx; i >= 0; i--) {
        if (p[i] == ')') depth++;
        else if (p[i] == '(') {
            depth--;
            if (depth == 0) return i;
        }
    }
    return -1;
}

/* [open, close) araliginda niceleyici (* + ? {) var mi? */
static int axiom_regex_has_quantifier(const char* p, int open_idx, int close_idx) {
    int in_class = 0;
    for (int i = open_idx + 1; i < close_idx; i++) {
        char c = p[i];
        if (c == '\\') { i++; continue; }
        if (c == '[') { in_class = 1; continue; }
        if (c == ']') { in_class = 0; continue; }
        if (in_class) continue;
        if (c == '*' || c == '+' || c == '?' || c == '{') return 1;
    }
    return 0;
}

/* Guvenlik taramasi: 0 = guvenli, 1 = pahali, 2 = reddedilir. */
AXIOM_RUNTIME_FN ax_int axiom_regex_risk_level(const char* pattern) {
    if (!pattern) return 2;
    size_t n = strlen(pattern);
    if (n == 0) return 2;
    if (n > AXIOM_REGEX_MAX_PATTERN) return 2;

    int depth = 0;
    int in_class = 0;
    for (size_t i = 0; i < n; i++) {
        char c = pattern[i];
        if (c == '\\') { i++; continue; }
        if (in_class) {
            if (c == ']') in_class = 0;
            continue;
        }
        if (c == '[') { in_class = 1; continue; }
        if (c == '(') {
            depth++;
            if (depth > AXIOM_REGEX_MAX_DEPTH) return 2;
            continue;
        }
        if (c == ')') { if (depth > 0) depth--; continue; }

        if (c == '*' || c == '+' || c == '?' || c == '{') {
            /* Onceki karakter ')' ise: grubun ICINDE niceleyici var mi?
             * Varsa (a+)+ / (a*)* / (a|a)* gibi ustel patlama kaliplari. */
            if (i > 0 && pattern[i - 1] == ')') {
                int open_idx = axiom_regex_matching_open(pattern, (int)i - 1);
                if (open_idx >= 0 &&
                    axiom_regex_has_quantifier(pattern, open_idx, (int)i - 1)) {
                    return 2;
                }
            }
            /* {n,m} tekrar sayisi siniri (hem alt hem ust sinir). */
            if (c == '{') {
                size_t j = i + 1;
                long val = 0;
                while (j < n && isdigit((unsigned char)pattern[j])) {
                    val = val * 10 + (pattern[j] - '0');
                    if (val > AXIOM_REGEX_MAX_REPEAT) return 2;
                    j++;
                }
                if (j < n && pattern[j] == ',') {
                    j++;
                    while (j < n && isdigit((unsigned char)pattern[j])) {
                        val = val * 10 + (pattern[j] - '0');
                        if (val > AXIOM_REGEX_MAX_REPEAT) return 2;
                        j++;
                    }
                }
            }
        }
    }
    return depth == 0 ? 0 : 2;
}

/* Derleme hatasini metin olarak dondurur; "" = gecerli ve guvenli. */
AXIOM_RUNTIME_FN ax_str axiom_regex_validate(const char* pattern) {
    if (!pattern) return axiom_owned_str_wrap("bos desen");
    if (pattern[0] == '\0') return axiom_owned_str_wrap("bos desen");
    if (axiom_regex_risk_level(pattern) >= 2) {
        return axiom_owned_str_wrap(
            "guvensiz veya cok uzun desen (ic ice niceleyici / derinlik / tekrar siniri)");
    }
    int cflags = REG_EXTENDED;
    const char* p = pattern;
    if (strncmp(p, "(?i)", 4) == 0) {
        cflags |= REG_ICASE;
        p += 4;
    }
    regex_t reg;
    int rc = regcomp(&reg, p, cflags);
    if (rc != 0) {
        char err[256];
        regerror(rc, &reg, err, sizeof(err));
        size_t len = strlen(err);
        char* msg = (char*)malloc(len + 1);
        if (!msg) return axiom_owned_str_wrap("gecersiz desen");
        memcpy(msg, err, len + 1);
        return axiom_owned_str_wrap(msg);
    }
    regfree(&reg);
    return axiom_owned_str_wrap("");
}

AXIOM_RUNTIME_FN ax_bool axiom_regex_is_match(const char* pattern, const char* text) {
    if (!pattern || !text) return false;
    int cflags = REG_EXTENDED;
    const char* p = pattern;
    if (strncmp(p, "(?i)", 4) == 0) {
        cflags |= REG_ICASE;
        p += 4;
    }
    regex_t reg;
    if (regcomp(&reg, p, cflags) != 0) {
        return false;
    }
    int status = regexec(&reg, text, 0, NULL, 0);
    regfree(&reg);
    return status == 0;
}

AXIOM_RUNTIME_FN ax_str axiom_regex_find(const char* pattern, const char* text) {
    if (!pattern || !text) return axiom_owned_str_wrap("");
    int cflags = REG_EXTENDED;
    const char* p = pattern;
    if (strncmp(p, "(?i)", 4) == 0) {
        cflags |= REG_ICASE;
        p += 4;
    }
    regex_t reg;
    if (regcomp(&reg, p, cflags) != 0) {
        return axiom_owned_str_wrap("");
    }
    regmatch_t pmatch[1];
    int status = regexec(&reg, text, 1, pmatch, 0);
    regfree(&reg);
    if (status != 0 || pmatch[0].rm_so == -1) {
        return axiom_owned_str_wrap("");
    }
    size_t len = (size_t)(pmatch[0].rm_eo - pmatch[0].rm_so);
    char* res = (char*)malloc(len + 1);
    if (!res) return axiom_owned_str_wrap("");
    memcpy(res, text + pmatch[0].rm_so, len);
    res[len] = '\0';
    return axiom_owned_str_wrap(res);
}

AXIOM_RUNTIME_FN ax_str axiom_regex_replace(const char* pattern, const char* text, const char* repl) {
    if (!pattern || !text) return axiom_owned_str_wrap("");
    if (!repl) repl = "";
    regex_t reg;
    if (regcomp(&reg, pattern, REG_EXTENDED) != 0) {
        return axiom_owned_str_wrap(axiom_p3_strdup(text));
    }

    size_t repl_len = strlen(repl);
    size_t cap = strlen(text) * 2 + repl_len + 64;
    char* out = (char*)malloc(cap);
    if (!out) {
        regfree(&reg);
        return axiom_owned_str_wrap(axiom_p3_strdup(text));
    }
    size_t out_len = 0;
    const char* cursor = text;
    regmatch_t pmatch[1];

    while (*cursor && regexec(&reg, cursor, 1, pmatch, 0) == 0) {
        size_t match_start = (size_t)pmatch[0].rm_so;
        size_t match_end = (size_t)pmatch[0].rm_eo;

        size_t needed = out_len + match_start + repl_len + 1;
        if (needed > cap) {
            cap = (cap * 2 > needed) ? cap * 2 : needed + 128;
            char* no = (char*)realloc(out, cap);
            if (!no) break;
            out = no;
        }

        memcpy(out + out_len, cursor, match_start);
        out_len += match_start;

        memcpy(out + out_len, repl, repl_len);
        out_len += repl_len;

        if (match_end == 0) {
            if (out_len + 2 > cap) {
                cap += 64;
                out = (char*)realloc(out, cap);
            }
            out[out_len++] = *cursor;
            cursor++;
        } else {
            cursor += match_end;
        }
    }

    size_t rest = strlen(cursor);
    if (out_len + rest + 1 > cap) {
        cap = out_len + rest + 1;
        out = (char*)realloc(out, cap);
    }
    memcpy(out + out_len, cursor, rest);
    out_len += rest;
    out[out_len] = '\0';

    regfree(&reg);
    return axiom_owned_str_wrap(out);
}

#else  /* !AXIOM_HAVE_POSIX_REGEX — taşınabilir motor (Windows) ---------- */

/* POSIX regex yoksa `regex_portable.h` devreye girer. Davranış aynıdır:
 * aynı sözdizimi alt kümesi, aynı API, aynı güvenlik sınırları.
 * Geri izleme adım bütçesiyle sınırlıdır (üstel patlama yok). */

AXIOM_RUNTIME_FN ax_bool axiom_regex_is_match(const char* pattern, const char* text) {
    if (!pattern || !text) return false;
    ax_re re;
    ax_re_compile(&re, pattern);
    if (!re.ok) { ax_re_free(re.root); return false; }
    size_t ml = 0; int ex = 0;
    long r = ax_re_search(&re, text, &ml, &ex, 0);
    ax_re_free(re.root);
    return r >= 0;
}

AXIOM_RUNTIME_FN ax_str axiom_regex_find(const char* pattern, const char* text) {
    if (!pattern || !text) return axiom_owned_str_wrap("");
    ax_re re;
    ax_re_compile(&re, pattern);
    if (!re.ok) { ax_re_free(re.root); return axiom_owned_str_wrap(""); }
    size_t ml = 0; int ex = 0;
    long r = ax_re_search(&re, text, &ml, &ex, 0);
    ax_re_free(re.root);
    if (r < 0) return axiom_owned_str_wrap("");
    char* out = (char*)malloc(ml + 1);
    if (!out) return axiom_owned_str_wrap("");
    memcpy(out, text + r, ml);
    out[ml] = '\0';
    return axiom_owned_str_wrap(out);
}

AXIOM_RUNTIME_FN ax_str axiom_regex_replace(const char* pattern, const char* text, const char* repl) {
    if (!pattern || !text) return axiom_owned_str_wrap("");
    if (!repl) repl = "";
    ax_re re;
    ax_re_compile(&re, pattern);
    if (!re.ok) {
        ax_re_free(re.root);
        return axiom_owned_str_wrap(axiom_p3_strdup(text));
    }

    size_t cap = strlen(text) * 2 + strlen(repl) + 64;
    char* out = (char*)malloc(cap);
    if (!out) { ax_re_free(re.root); return axiom_owned_str_wrap(axiom_p3_strdup(text)); }
    size_t out_len = 0;
    const char* cursor = text;
    size_t repl_len = strlen(repl);

    while (*cursor) {
        size_t ml = 0; int ex = 0;
        long r = ax_re_search(&re, cursor, &ml, &ex, 0);
        if (r < 0) break;
        size_t start = (size_t)r;
        size_t need = out_len + start + repl_len + 1;
        if (need > cap) {
            cap = need * 2;
            char* g = (char*)realloc(out, cap);
            if (!g) break;
            out = g;
        }
        memcpy(out + out_len, cursor, start); out_len += start;
        memcpy(out + out_len, repl, repl_len); out_len += repl_len;
        if (ml == 0) {
            /* sıfır uzunluklu eşleşme: ilerlemeyi garanti et */
            if (out_len + 2 > cap) { cap += 64; out = (char*)realloc(out, cap); }
            out[out_len++] = *cursor;
            cursor++;
        } else {
            cursor += start + ml;
        }
    }
    size_t rest = strlen(cursor);
    if (out_len + rest + 1 > cap) {
        cap = out_len + rest + 1;
        char* g = (char*)realloc(out, cap);
        if (g) out = g;
    }
    memcpy(out + out_len, cursor, rest);
    out_len += rest;
    out[out_len] = '\0';
    ax_re_free(re.root);
    return axiom_owned_str_wrap(out);
}

/* Aynı güvenlik taraması (iç içe niceleyici / derinlik / tekrar sınırı). */
AXIOM_RUNTIME_FN ax_int axiom_regex_risk_level(const char* pattern) {
    if (!pattern) return 2;
    size_t n = strlen(pattern);
    if (n == 0) return 2;
    if (n > AXIOM_REGEX_MAX_PATTERN) return 2;

    int depth = 0, in_class = 0;
    for (size_t i = 0; i < n; i++) {
        char c = pattern[i];
        if (c == '\\') { i++; continue; }
        if (in_class) { if (c == ']') in_class = 0; continue; }
        if (c == '[') { in_class = 1; continue; }
        if (c == '(') { if (++depth > AXIOM_REGEX_MAX_DEPTH) return 2; continue; }
        if (c == ')') { if (depth > 0) depth--; continue; }
        if (c == '*' || c == '+' || c == '?' || c == '{') {
            if (i > 0 && pattern[i - 1] == ')') {
                /* grubun içinde niceleyici var mı? -> iç içe niceleyici */
                int d = 0;
                int open_idx = -1;
                for (int j = (int)i - 1; j >= 0; j--) {
                    if (pattern[j] == ')') d++;
                    else if (pattern[j] == '(') { if (--d == 0) { open_idx = j; break; } }
                }
                if (open_idx >= 0) {
                    int inner_q = 0, cls2 = 0;
                    for (int j = open_idx + 1; j < (int)i - 1; j++) {
                        if (pattern[j] == '\\') { j++; continue; }
                        if (pattern[j] == '[') { cls2 = 1; continue; }
                        if (pattern[j] == ']') { cls2 = 0; continue; }
                        if (cls2) continue;
                        if (pattern[j] == '*' || pattern[j] == '+' ||
                            pattern[j] == '?' || pattern[j] == '{') { inner_q = 1; break; }
                    }
                    if (inner_q) return 2;
                }
            }
            if (c == '{') {
                long v = 0;
                for (size_t j = i + 1; j < n && pattern[j] >= '0' && pattern[j] <= '9'; j++) {
                    v = v * 10 + (pattern[j] - '0');
                    if (v > AXIOM_REGEX_MAX_REPEAT) return 2;
                }
                /* üst sınır */
                size_t k = i + 1;
                while (k < n && pattern[k] >= '0' && pattern[k] <= '9') k++;
                if (k < n && pattern[k] == ',') {
                    k++;
                    v = 0;
                    while (k < n && pattern[k] >= '0' && pattern[k] <= '9') {
                        v = v * 10 + (pattern[k] - '0');
                        if (v > AXIOM_REGEX_MAX_REPEAT) return 2;
                        k++;
                    }
                }
            }
        }
    }
    return depth == 0 ? 0 : 2;
}

AXIOM_RUNTIME_FN ax_str axiom_regex_validate(const char* pattern) {
    if (!pattern || pattern[0] == '\0') return axiom_owned_str_wrap("bos desen");
    if (axiom_regex_risk_level(pattern) >= 2) {
        return axiom_owned_str_wrap(
            "guvensiz veya cok uzun desen (ic ice niceleyici / derinlik / tekrar siniri)");
    }
    ax_re re;
    ax_re_compile(&re, pattern);
    if (!re.ok) {
        const char* e = re.err ? re.err : "gecersiz desen";
        size_t n = strlen(e);
        char* m = (char*)malloc(n + 1);
        if (!m) return axiom_owned_str_wrap("gecersiz desen");
        memcpy(m, e, n + 1);
        return axiom_owned_str_wrap(m);
    }
    ax_re_free(re.root);
    return axiom_owned_str_wrap("");
}

#endif /* AXIOM_HAVE_POSIX_REGEX */
/* -------------------------------------------------------------------------
 * 15. std:collections:map (Yüksek Hızlı Hash Map)
 * ------------------------------------------------------------------------- */
typedef struct AxiomMapEntry {
    char* key;
    char* val;
    struct AxiomMapEntry* next;
} AxiomMapEntry;

typedef struct {
    AxiomMapEntry** buckets;
    size_t num_buckets;
    size_t count;
} AxiomHashMap;

AXIOM_RUNTIME_FN uint32_t axiom_map_hash(const char* s) {
    uint32_t hash = 5381;
    int c;
    while ((c = *s++)) {
        hash = ((hash << 5) + hash) + c;
    }
    return hash;
}

AXIOM_RUNTIME_FN ax_int axiom_map_create(void) {
    AxiomHashMap* m = (AxiomHashMap*)malloc(sizeof(AxiomHashMap));
    if (!m) return 0;
    m->num_buckets = 16;
    m->count = 0;
    m->buckets = (AxiomMapEntry**)calloc(m->num_buckets, sizeof(AxiomMapEntry*));
    if (!m->buckets) {
        free(m);
        return 0;
    }
    return (ax_int)(uintptr_t)m;
}

AXIOM_RUNTIME_FN void axiom_map_rehash(AxiomHashMap* m) {
    size_t new_num = m->num_buckets * 2;
    AxiomMapEntry** new_b = (AxiomMapEntry**)calloc(new_num, sizeof(AxiomMapEntry*));
    if (!new_b) return;

    for (size_t i = 0; i < m->num_buckets; i++) {
        AxiomMapEntry* curr = m->buckets[i];
        while (curr) {
            AxiomMapEntry* next = curr->next;
            uint32_t idx = axiom_map_hash(curr->key) % new_num;
            curr->next = new_b[idx];
            new_b[idx] = curr;
            curr = next;
        }
    }
    free(m->buckets);
    m->buckets = new_b;
    m->num_buckets = new_num;
}

AXIOM_RUNTIME_FN void axiom_map_set(ax_int handle, const char* key, const char* val) {
    AxiomHashMap* m = (AxiomHashMap*)(uintptr_t)handle;
    if (!m || !key || !val) return;

    if (m->count >= m->num_buckets * 3 / 4) {
        axiom_map_rehash(m);
    }

    uint32_t idx = axiom_map_hash(key) % m->num_buckets;
    AxiomMapEntry* curr = m->buckets[idx];
    while (curr) {
        if (strcmp(curr->key, key) == 0) {
            free(curr->val);
            curr->val = axiom_p3_strdup(val);
            return;
        }
        curr = curr->next;
    }

    AxiomMapEntry* entry = (AxiomMapEntry*)malloc(sizeof(AxiomMapEntry));
    if (!entry) return;
    entry->key = axiom_p3_strdup(key);
    entry->val = axiom_p3_strdup(val);
    entry->next = m->buckets[idx];
    m->buckets[idx] = entry;
    m->count++;
}

AXIOM_RUNTIME_FN ax_str axiom_map_get(ax_int handle, const char* key) {
    AxiomHashMap* m = (AxiomHashMap*)(uintptr_t)handle;
    if (!m || !key) return axiom_owned_str_wrap("");
    uint32_t idx = axiom_map_hash(key) % m->num_buckets;
    AxiomMapEntry* curr = m->buckets[idx];
    while (curr) {
        if (strcmp(curr->key, key) == 0) {
            return axiom_owned_str_wrap(axiom_p3_strdup(curr->val));
        }
        curr = curr->next;
    }
    return axiom_owned_str_wrap("");
}

AXIOM_RUNTIME_FN ax_bool axiom_map_has(ax_int handle, const char* key) {
    AxiomHashMap* m = (AxiomHashMap*)(uintptr_t)handle;
    if (!m || !key) return false;
    uint32_t idx = axiom_map_hash(key) % m->num_buckets;
    AxiomMapEntry* curr = m->buckets[idx];
    while (curr) {
        if (strcmp(curr->key, key) == 0) return true;
        curr = curr->next;
    }
    return false;
}

AXIOM_RUNTIME_FN ax_bool axiom_map_delete(ax_int handle, const char* key) {
    AxiomHashMap* m = (AxiomHashMap*)(uintptr_t)handle;
    if (!m || !key) return false;
    uint32_t idx = axiom_map_hash(key) % m->num_buckets;
    AxiomMapEntry* curr = m->buckets[idx];
    AxiomMapEntry* prev = NULL;
    while (curr) {
        if (strcmp(curr->key, key) == 0) {
            if (prev) prev->next = curr->next;
            else m->buckets[idx] = curr->next;
            free(curr->key);
            free(curr->val);
            free(curr);
            m->count--;
            return true;
        }
        prev = curr;
        curr = curr->next;
    }
    return false;
}

AXIOM_RUNTIME_FN ax_int axiom_map_len(ax_int handle) {
    AxiomHashMap* m = (AxiomHashMap*)(uintptr_t)handle;
    if (!m) return 0;
    return (ax_int)m->count;
}

AXIOM_RUNTIME_FN void axiom_map_free(ax_int handle) {
    AxiomHashMap* m = (AxiomHashMap*)(uintptr_t)handle;
    if (!m) return;
    for (size_t i = 0; i < m->num_buckets; i++) {
        AxiomMapEntry* curr = m->buckets[i];
        while (curr) {
            AxiomMapEntry* next = curr->next;
            free(curr->key);
            free(curr->val);
            free(curr);
            curr = next;
        }
    }
    free(m->buckets);
    free(m);
}

/* ========================================================================= */
/* --- PAKET 4: GUVENLIK, FUZZING VE VERI YAPILARI                       --- */
/* ========================================================================= */

/* 16. std:collections:queue (Thread-Safe FIFO Queue) */

typedef struct AxiomQueueNode {
    char* data;
    struct AxiomQueueNode* next;
} AxiomQueueNode;

typedef struct AxiomQueue {
    AxiomQueueNode* head;
    AxiomQueueNode* tail;
    int64_t count;
    ax_mutex_t lock;
    ax_cond_t not_empty;
} AxiomQueue;

AXIOM_RUNTIME_FN ax_int axiom_queue_create(void) {
    AxiomQueue* q = (AxiomQueue*)malloc(sizeof(AxiomQueue));
    if (!q) return 0;
    q->head = NULL;
    q->tail = NULL;
    q->count = 0;
    ax_os_mutex_init(&q->lock);
    ax_os_cond_init(&q->not_empty);
    return (ax_int)(uintptr_t)q;
}

AXIOM_RUNTIME_FN void axiom_queue_push(ax_int handle, const char* item) {
    AxiomQueue* q = (AxiomQueue*)(uintptr_t)handle;
    if (!q) return;
    AxiomQueueNode* node = (AxiomQueueNode*)malloc(sizeof(AxiomQueueNode));
    if (!node) return;
    node->data = item ? strdup(item) : strdup("");
    node->next = NULL;

    ax_os_mutex_lock(&q->lock);
    if (q->tail) {
        q->tail->next = node;
        q->tail = node;
    } else {
        q->head = q->tail = node;
    }
    q->count++;
    ax_os_cond_signal(&q->not_empty);
    ax_os_mutex_unlock(&q->lock);
}

AXIOM_RUNTIME_FN ax_str axiom_queue_pop(ax_int handle) {
    AxiomQueue* q = (AxiomQueue*)(uintptr_t)handle;
    if (!q) return axiom_owned_str_wrap("");
    ax_os_mutex_lock(&q->lock);
    if (!q->head || q->count <= 0) {
        ax_os_mutex_unlock(&q->lock);
        return axiom_owned_str_wrap("");
    }
    AxiomQueueNode* node = q->head;
    q->head = node->next;
    if (!q->head) {
        q->tail = NULL;
    }
    q->count--;
    ax_os_mutex_unlock(&q->lock);

    char* res = node->data;
    free(node);
    return axiom_owned_str_wrap(res ? res : "");
}

AXIOM_RUNTIME_FN ax_int axiom_queue_len(ax_int handle) {
    AxiomQueue* q = (AxiomQueue*)(uintptr_t)handle;
    if (!q) return 0;
    ax_os_mutex_lock(&q->lock);
    ax_int count = (ax_int)q->count;
    ax_os_mutex_unlock(&q->lock);
    return count;
}

AXIOM_RUNTIME_FN ax_bool axiom_queue_is_empty(ax_int handle) {
    AxiomQueue* q = (AxiomQueue*)(uintptr_t)handle;
    if (!q) return true;
    ax_os_mutex_lock(&q->lock);
    ax_bool empty = (q->count == 0);
    ax_os_mutex_unlock(&q->lock);
    return empty;
}

AXIOM_RUNTIME_FN void axiom_queue_free(ax_int handle) {
    AxiomQueue* q = (AxiomQueue*)(uintptr_t)handle;
    if (!q) return;
    ax_os_mutex_lock(&q->lock);
    AxiomQueueNode* curr = q->head;
    while (curr) {
        AxiomQueueNode* nxt = curr->next;
        if (curr->data) free(curr->data);
        free(curr);
        curr = nxt;
    }
    q->head = q->tail = NULL;
    q->count = 0;
    ax_os_mutex_unlock(&q->lock);
    ax_os_mutex_destroy(&q->lock);
    ax_os_cond_destroy(&q->not_empty);
    free(q);
}

/* 17. std:security:fuzzer (Fuzzing & Payload Engine) */

AXIOM_RUNTIME_FN ax_str axiom_fuzz_replace_marker(const char* tpl, const char* marker, const char* payload) {
    if (!tpl) return axiom_owned_str_wrap("");
    if (!marker || strlen(marker) == 0) return axiom_owned_str_wrap(strdup(tpl));
    if (!payload) payload = "";

    size_t tpl_len = strlen(tpl);
    size_t m_len = strlen(marker);
    size_t p_len = strlen(payload);

    size_t count = 0;
    const char* tmp = tpl;
    while ((tmp = strstr(tmp, marker)) != NULL) {
        count++;
        tmp += m_len;
    }

    if (count == 0) return axiom_owned_str_wrap(strdup(tpl));

    size_t new_len = tpl_len + count * (p_len - m_len);
    char* result = (char*)malloc(new_len + 1);
    if (!result) return axiom_owned_str_wrap("");

    char* dst = result;
    const char* src = tpl;
    while (1) {
        const char* p = strstr(src, marker);
        if (!p) {
            strcpy(dst, src);
            break;
        }
        size_t part_len = (size_t)(p - src);
        memcpy(dst, src, part_len);
        dst += part_len;
        memcpy(dst, payload, p_len);
        dst += p_len;
        src = p + m_len;
    }
    result[new_len] = '\0';
    return axiom_owned_str_wrap(result);
}

AXIOM_RUNTIME_FN ax_str axiom_fuzz_url_encode(const char* payload) {
    if (!payload) return axiom_owned_str_wrap("");
    size_t len = strlen(payload);
    char* out = (char*)malloc(len * 3 + 1);
    if (!out) return axiom_owned_str_wrap("");
    char* p = out;
    for (size_t i = 0; i < len; i++) {
        unsigned char c = (unsigned char)payload[i];
        if (isalnum(c) || c == '-' || c == '_' || c == '.' || c == '~') {
            *p++ = (char)c;
        } else {
            sprintf(p, "%%%02X", c);
            p += 3;
        }
    }
    *p = '\0';
    return axiom_owned_str_wrap(out);
}

AXIOM_RUNTIME_FN ax_str axiom_fuzz_double_encode(const char* payload) {
    if (!payload) return axiom_owned_str_wrap("");
    char* single = (char*)axiom_fuzz_url_encode(payload);
    size_t s_len = strlen(single);
    size_t count_pct = 0;
    for (size_t i = 0; i < s_len; i++) {
        if (single[i] == '%') count_pct++;
    }
    char* out = (char*)malloc(s_len + count_pct * 2 + 1);
    if (!out) {
        return axiom_owned_str_wrap(single);
    }
    char* p = out;
    for (size_t i = 0; i < s_len; i++) {
        if (single[i] == '%') {
            *p++ = '%';
            *p++ = '2';
            *p++ = '5';
        } else {
            *p++ = single[i];
        }
    }
    *p = '\0';
    axiom_str_release(single);
    return axiom_owned_str_wrap(out);
}

AXIOM_RUNTIME_FN ax_str axiom_fuzz_add_null_byte(const char* payload) {
    if (!payload) return axiom_owned_str_wrap(strdup("%00"));
    size_t len = strlen(payload);
    char* res = (char*)malloc(len + 4);
    if (!res) return axiom_owned_str_wrap("");
    memcpy(res, payload, len);
    memcpy(res + len, "%00", 3);
    res[len + 3] = '\0';
    return axiom_owned_str_wrap(res);
}

typedef struct AxiomWordlist {
    char** lines;
    int64_t count;
    int64_t capacity;
} AxiomWordlist;

AXIOM_RUNTIME_FN ax_int axiom_wordlist_load(const char* path) {
    AxiomWordlist* wl = (AxiomWordlist*)malloc(sizeof(AxiomWordlist));
    if (!wl) return 0;
    wl->lines = NULL;
    wl->count = 0;
    wl->capacity = 0;

    if (!path) return (ax_int)(uintptr_t)wl;

    FILE* fp = fopen(path, "r");
    if (!fp) return (ax_int)(uintptr_t)wl;

    char line_buf[4096];
    while (fgets(line_buf, sizeof(line_buf), fp)) {
        size_t l = strlen(line_buf);
        while (l > 0 && (line_buf[l - 1] == '\n' || line_buf[l - 1] == '\r')) {
            line_buf[l - 1] = '\0';
            l--;
        }
        if (wl->count >= wl->capacity) {
            int64_t new_cap = wl->capacity == 0 ? 32 : wl->capacity * 2;
            char** new_lines = (char**)realloc(wl->lines, (size_t)new_cap * sizeof(char*));
            if (!new_lines) break;
            wl->lines = new_lines;
            wl->capacity = new_cap;
        }
        wl->lines[wl->count++] = strdup(line_buf);
    }
    fclose(fp);
    return (ax_int)(uintptr_t)wl;
}

AXIOM_RUNTIME_FN ax_int axiom_wordlist_count(ax_int handle) {
    AxiomWordlist* wl = (AxiomWordlist*)(uintptr_t)handle;
    if (!wl) return 0;
    return (ax_int)wl->count;
}

AXIOM_RUNTIME_FN ax_str axiom_wordlist_get(ax_int handle, ax_int idx) {
    AxiomWordlist* wl = (AxiomWordlist*)(uintptr_t)handle;
    if (!wl || idx < 0 || idx >= wl->count) return axiom_owned_str_wrap("");
    return axiom_owned_str_wrap(strdup(wl->lines[idx]));
}

AXIOM_RUNTIME_FN void axiom_wordlist_free(ax_int handle) {
    AxiomWordlist* wl = (AxiomWordlist*)(uintptr_t)handle;
    if (!wl) return;
    for (int64_t i = 0; i < wl->count; i++) {
        if (wl->lines[i]) free(wl->lines[i]);
    }
    if (wl->lines) free(wl->lines);
    free(wl);
}

/* 18. std:time:date (Date, Time & ISO 8601) */

AXIOM_RUNTIME_FN ax_str axiom_date_now_iso(void) {
    char buf[64];
    ax_os_strftime_tz(ax_os_epoch_seconds(), 0, "%Y-%m-%dT%H:%M:%SZ", buf, sizeof(buf));
    return axiom_safe_strdup(buf);
}

AXIOM_RUNTIME_FN ax_int axiom_date_now_epoch(void) {
    return (ax_int)ax_os_epoch_seconds();
}

AXIOM_RUNTIME_FN ax_str axiom_date_format_epoch(ax_int epoch, const char* fmt) {
    char buf[256];
    const char* pattern = (fmt && strlen(fmt) > 0) ? fmt : "%Y-%m-%d %H:%M:%S";
    size_t n = ax_os_strftime_tz((long long)epoch, 0, pattern, buf, sizeof(buf));
    if (n == 0) return axiom_owned_str_wrap("");
    return axiom_safe_strdup(buf);
}

AXIOM_RUNTIME_FN ax_int axiom_date_diff_seconds(ax_int t1, ax_int t2) {
    ax_int diff = t1 - t2;
    return diff < 0 ? -diff : diff;
}

/* --- Sabit ofsetli saat dilimi destegi (IANA tz veritabani YOK) --- */
#define AXIOM_TZ_MAX_OFFSET_MIN 840

static int axiom_tz_clamp(int offset_minutes) {
    if (offset_minutes > AXIOM_TZ_MAX_OFFSET_MIN) return AXIOM_TZ_MAX_OFFSET_MIN;
    if (offset_minutes < -AXIOM_TZ_MAX_OFFSET_MIN) return -AXIOM_TZ_MAX_OFFSET_MIN;
    return offset_minutes;
}

AXIOM_RUNTIME_FN ax_str axiom_date_format_tz(ax_int epoch, const char* fmt, ax_int offset_minutes) {
    int off = axiom_tz_clamp((int)offset_minutes);
    char buf[256];
    const char* pattern = (fmt && strlen(fmt) > 0) ? fmt : "%Y-%m-%d %H:%M:%S";
    size_t n = ax_os_strftime_tz((long long)epoch, off, pattern, buf, sizeof(buf));
    if (n == 0) return axiom_owned_str_wrap("");
    return axiom_safe_strdup(buf);
}

/* "+03:00" / "-0530" / "Z" -> dakika. Gecersizse 0. */
static int axiom_tz_parse_offset(const char* s) {
    if (!s || !*s) return 0;
    if (*s == 'Z' || *s == 'z') return 0;
    int sign = 1;
    if (*s == '+') s++;
    else if (*s == '-') { sign = -1; s++; }
    else return 0;
    int hh = 0, mm = 0;
    if (sscanf(s, "%2d:%2d", &hh, &mm) != 2) {
        if (sscanf(s, "%2d%2d", &hh, &mm) != 2) {
            if (sscanf(s, "%2d", &hh) != 1) return 0;
            mm = 0;
        }
    }
    if (hh < 0 || hh > 23 || mm < 0 || mm > 59) return 0;
    return sign * (hh * 60 + mm);
}

/* ISO 8601 -> epoch (UTC). Gecersizse INT64_MIN. */
AXIOM_RUNTIME_FN ax_int axiom_date_parse_iso(const char* s) {
    if (!s) return INT64_MIN;
    int y = 0, mo = 0, d = 0, h = 0, mi = 0, se = 0;
    int n = sscanf(s, "%4d-%2d-%2dT%2d:%2d:%2d", &y, &mo, &d, &h, &mi, &se);
    if (n != 6) {
        n = sscanf(s, "%4d-%2d-%2d %2d:%2d:%2d", &y, &mo, &d, &h, &mi, &se);
    }
    if (n != 6) return INT64_MIN;
    if (mo < 1 || mo > 12 || d < 1 || d > 31 ||
        h < 0 || h > 23 || mi < 0 || mi > 59 || se < 0 || se > 60) {
        return INT64_MIN;
    }

    long long utc = ax_os_timegm(y, mo, d, h, mi, se);
    if (utc == (long long)-1 && !(y == 1969 && mo == 12 && d == 31)) {
        /* bazi platformlarda -1 hata; yine de devam et */
    }

    size_t slen = strlen(s);
    const char* p = NULL;
    for (size_t i = slen; i-- > 10; ) {
        char c = s[i];
        if (c == 'Z' || c == 'z') { p = s + i; break; }
        if ((c == '+' || c == '-') && i > 10) { p = s + i; break; }
    }
    if (p) {
        int off = axiom_tz_parse_offset(p);
        utc -= (long long)off * 60;
    }
    return (ax_int)utc;
}

AXIOM_RUNTIME_FN ax_str axiom_date_iso_tz(ax_int epoch, ax_int offset_minutes) {
    int off = axiom_tz_clamp((int)offset_minutes);
    char base[32];
    ax_os_strftime_tz((long long)epoch, off, "%Y-%m-%dT%H:%M:%S", base, sizeof(base));

    char buf[48];
    if (off == 0) {
        snprintf(buf, sizeof(buf), "%sZ", base);
    } else {
        int a = off < 0 ? -off : off;
        snprintf(buf, sizeof(buf), "%s%c%02d:%02d", base, off < 0 ? '-' : '+', a / 60, a % 60);
    }
    return axiom_safe_strdup(buf);
}

AXIOM_RUNTIME_FN ax_int axiom_date_local_offset_minutes(void) {
    long long now = ax_os_epoch_seconds();
    ax_tm_parts l, u;
    ax_os_localtime(now, &l);
    ax_os_gmtime(now, &u);
    int diff = (l.hour - u.hour) * 60 + (l.min - u.min);
    if (l.yday != u.yday) diff += (l.yday > u.yday) ? 1440 : -1440;
    return (ax_int)diff;
}

/* 19. std:io:csv (CSV & Report Generator) */

typedef struct AxiomCsvRow {
    char** cols;
    int64_t count;
    struct AxiomCsvRow* next;
} AxiomCsvRow;

typedef struct AxiomCsv {
    AxiomCsvRow* head;
    AxiomCsvRow* tail;
    int64_t row_count;
} AxiomCsv;

AXIOM_RUNTIME_FN ax_int axiom_csv_create(void) {
    AxiomCsv* c = (AxiomCsv*)malloc(sizeof(AxiomCsv));
    if (!c) return 0;
    c->head = NULL;
    c->tail = NULL;
    c->row_count = 0;
    return (ax_int)(uintptr_t)c;
}

AXIOM_RUNTIME_FN void axiom_csv_add_row(ax_int handle, ax_array_str cols) {
    AxiomCsv* c = (AxiomCsv*)(uintptr_t)handle;
    if (!c) return;

    AxiomCsvRow* row = (AxiomCsvRow*)malloc(sizeof(AxiomCsvRow));
    if (!row) return;
    row->count = cols.length;
    row->cols = (char**)malloc((size_t)cols.length * sizeof(char*));
    row->next = NULL;

    for (ax_int i = 0; i < cols.length; i++) {
        row->cols[i] = cols.data[i] ? strdup(cols.data[i]) : strdup("");
    }

    if (c->tail) {
        c->tail->next = row;
        c->tail = row;
    } else {
        c->head = c->tail = row;
    }
    c->row_count++;
}

AXIOM_RUNTIME_FN ax_str axiom_csv_to_str(ax_int handle) {
    AxiomCsv* c = (AxiomCsv*)(uintptr_t)handle;
    if (!c || !c->head) return axiom_owned_str_wrap(strdup(""));

    size_t cap = 256;
    size_t len = 0;
    char* buf = (char*)malloc(cap);
    if (!buf) return axiom_owned_str_wrap(strdup(""));
    buf[0] = '\0';

    AxiomCsvRow* curr = c->head;
    while (curr) {
        for (int64_t i = 0; i < curr->count; i++) {
            const char* col = curr->cols[i];
            bool needs_quote = false;
            size_t q_count = 0;
            for (const char* p = col; *p; p++) {
                if (*p == ',' || *p == '"' || *p == '\n' || *p == '\r') {
                    needs_quote = true;
                }
                if (*p == '"') q_count++;
            }

            size_t col_len = strlen(col);
            size_t needed = col_len + (needs_quote ? (q_count + 3) : 1);
            while (len + needed >= cap) {
                cap *= 2;
                char* nb = (char*)realloc(buf, cap);
                if (!nb) { free(buf); return axiom_owned_str_wrap(strdup("")); }
                buf = nb;
            }

            if (needs_quote) {
                buf[len++] = '"';
                for (const char* p = col; *p; p++) {
                    if (*p == '"') {
                        buf[len++] = '"';
                    }
                    buf[len++] = *p;
                }
                buf[len++] = '"';
            } else {
                memcpy(buf + len, col, col_len);
                len += col_len;
            }

            if (i + 1 < curr->count) {
                buf[len++] = ',';
            }
        }
        while (len + 2 >= cap) {
            cap *= 2;
            char* nb = (char*)realloc(buf, cap);
            if (!nb) { free(buf); return axiom_owned_str_wrap(strdup("")); }
            buf = nb;
        }
        buf[len++] = '\n';
        curr = curr->next;
    }
    buf[len] = '\0';
    return axiom_owned_str_wrap(buf);
}

AXIOM_RUNTIME_FN ax_bool axiom_csv_save_file(ax_int handle, const char* path) {
    if (!path) return false;
    const char* content = axiom_csv_to_str(handle);
    FILE* fp = fopen(path, "w");
    if (!fp) {
        axiom_str_release(content);
        return false;
    }
    if (content && strlen(content) > 0) {
        fputs(content, fp);
    }
    fclose(fp);
    axiom_str_release(content);
    return true;
}

AXIOM_RUNTIME_FN void axiom_csv_free(ax_int handle) {
    AxiomCsv* c = (AxiomCsv*)(uintptr_t)handle;
    if (!c) return;
    AxiomCsvRow* curr = c->head;
    while (curr) {
        AxiomCsvRow* nxt = curr->next;
        for (int64_t i = 0; i < curr->count; i++) {
            if (curr->cols[i]) free(curr->cols[i]);
        }
        if (curr->cols) free(curr->cols);
        free(curr);
        curr = nxt;
    }
    free(c);
}

/* 20. std:cli:args (CLI Arguments & Flags) */

static int axiom_global_argc = 0;
static char** axiom_global_argv = NULL;
static bool axiom_global_argv_allocated = false;

AXIOM_RUNTIME_FN void axiom_cli_init_args(int argc, char** argv) {
    axiom_global_argc = argc;
    axiom_global_argv = argv;
    axiom_global_argv_allocated = false;
}

AXIOM_RUNTIME_FN void axiom_cli_set_args(ax_array_str args) {
    if (axiom_global_argv_allocated && axiom_global_argv) {
        for (int i = 0; i < axiom_global_argc; i++) {
            if (axiom_global_argv[i]) free(axiom_global_argv[i]);
        }
        free(axiom_global_argv);
    }
    axiom_global_argc = (int)args.length;
    axiom_global_argv = (char**)malloc((size_t)args.length * sizeof(char*));
    axiom_global_argv_allocated = true;
    for (ax_int i = 0; i < args.length; i++) {
        axiom_global_argv[i] = args.data[i] ? strdup(args.data[i]) : strdup("");
    }
}

AXIOM_RUNTIME_FN ax_int axiom_os_exec_argv_ptr(const ax_array_str* argv) {
    return argv ? axiom_os_exec_argv(*argv) : -1;
}
AXIOM_RUNTIME_FN ax_str axiom_json_build_object_ptr(const ax_array_str* keys, const ax_array_str* values) {
    return (keys && values) ? axiom_json_build_object(*keys, *values) : axiom_owned_str_wrap(strdup("{}"));
}
AXIOM_RUNTIME_FN void axiom_csv_add_row_ptr(ax_int handle, const ax_array_str* cols) {
    if (cols) axiom_csv_add_row(handle, *cols);
}
AXIOM_RUNTIME_FN void axiom_cli_set_args_ptr(const ax_array_str* args) {
    if (args) axiom_cli_set_args(*args);
}

AXIOM_RUNTIME_FN ax_int axiom_cli_args_count(void) {
    return (ax_int)axiom_global_argc;
}

AXIOM_RUNTIME_FN ax_str axiom_cli_args_get(ax_int idx) {
    if (idx < 0 || idx >= axiom_global_argc || !axiom_global_argv) {
        return "";
    }
    return axiom_safe_strdup(axiom_global_argv[idx]);
}

AXIOM_RUNTIME_FN ax_bool axiom_cli_has_flag(const char* flag) {
    if (!flag || !axiom_global_argv) return false;
    for (int i = 1; i < axiom_global_argc; i++) {
        if (axiom_global_argv[i] && strcmp(axiom_global_argv[i], flag) == 0) {
            return true;
        }
    }
    return false;
}

AXIOM_RUNTIME_FN ax_str axiom_cli_get_option(const char* opt, const char* default_val) {
    if (!opt || !axiom_global_argv) {
        return axiom_owned_str_wrap(strdup(default_val ? default_val : ""));
    }
    size_t opt_len = strlen(opt);
    for (int i = 1; i < axiom_global_argc; i++) {
        const char* arg = axiom_global_argv[i];
        if (!arg) continue;
        if (strcmp(arg, opt) == 0) {
            if (i + 1 < axiom_global_argc && axiom_global_argv[i + 1]) {
                return axiom_owned_str_wrap(strdup(axiom_global_argv[i + 1]));
            }
            return axiom_owned_str_wrap(strdup(default_val ? default_val : ""));
        }
        if (strncmp(arg, opt, opt_len) == 0 && arg[opt_len] == '=') {
            return axiom_owned_str_wrap(strdup(arg + opt_len + 1));
        }
    }
    return axiom_owned_str_wrap(strdup(default_val ? default_val : ""));
}

AXIOM_RUNTIME_FN ax_int axiom_cli_get_int_option(const char* opt, ax_int default_val) {
    if (!opt || !axiom_global_argv) return default_val;
    size_t opt_len = strlen(opt);
    for (int i = 1; i < axiom_global_argc; i++) {
        const char* arg = axiom_global_argv[i];
        if (!arg) continue;
        if (strcmp(arg, opt) == 0) {
            if (i + 1 < axiom_global_argc && axiom_global_argv[i + 1]) {
                return (ax_int)strtoll(axiom_global_argv[i + 1], NULL, 10);
            }
            return default_val;
        }
        if (strncmp(arg, opt, opt_len) == 0 && arg[opt_len] == '=') {
            return (ax_int)strtoll(arg + opt_len + 1, NULL, 10);
        }
    }
    return default_val;
}

/* ========================================================================= */
/* --- 21. AES CBC Simetrik Kriptografi (std:crypto:aes) --- */
/* ========================================================================= */

AXIOM_RUNTIME_FN void axiom_internal_hex_to_bytes(const char* hex, unsigned char* out, int max_bytes) {
    if (!hex || !out || max_bytes <= 0) return;
    for (int i = 0; i < max_bytes && hex[i * 2] && hex[i * 2 + 1]; i++) {
        unsigned int val = 0;
        sscanf(hex + i * 2, "%02x", &val);
        out[i] = (unsigned char)val;
    }
}

#if AXIOM_HAVE_OPENSSL
AXIOM_RUNTIME_FN ax_str axiom_aes_cbc_encrypt_internal(const char* plaintext, const char* key_hex, const char* iv_hex, int is_256) {
    if (!plaintext || !key_hex || !iv_hex) return axiom_owned_str_wrap("");
    int key_len = is_256 ? 32 : 16;
    unsigned char key[32] = {0};
    unsigned char iv[16] = {0};
    axiom_internal_hex_to_bytes(key_hex, key, key_len);
    axiom_internal_hex_to_bytes(iv_hex, iv, 16);

    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    if (!ctx) return axiom_owned_str_wrap("");
    const EVP_CIPHER *cipher = is_256 ? EVP_aes_256_cbc() : EVP_aes_128_cbc();
    if (EVP_EncryptInit_ex(ctx, cipher, NULL, key, iv) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        return axiom_owned_str_wrap("");
    }

    int in_len = (int)strlen(plaintext);
    int out_len1 = 0, out_len2 = 0;
    unsigned char *out = (unsigned char*)malloc(in_len + 32);
    if (!out) {
        EVP_CIPHER_CTX_free(ctx);
        return axiom_owned_str_wrap("");
    }

    EVP_EncryptUpdate(ctx, out, &out_len1, (const unsigned char*)plaintext, in_len);
    EVP_EncryptFinal_ex(ctx, out + out_len1, &out_len2);
    int total_out = out_len1 + out_len2;
    EVP_CIPHER_CTX_free(ctx);

    char *hex_out = (char*)malloc(total_out * 2 + 1);
    if (!hex_out) {
        free(out);
        return axiom_owned_str_wrap("");
    }
    for (int i = 0; i < total_out; i++) {
        sprintf(hex_out + i * 2, "%02x", out[i]);
    }
    hex_out[total_out * 2] = '\0';
    free(out);
    return axiom_owned_str_wrap(hex_out);
}
#else
AXIOM_RUNTIME_FN ax_str axiom_aes_cbc_encrypt_internal(const char* a, const char* b, const char* c) {
    (void)a; (void)b; (void)c;
    return axiom_owned_str_wrap(
        "AES: bu yapida OpenSSL yok (sessiz yanlis sonuc verilmez)");
}
#endif

#if AXIOM_HAVE_OPENSSL
AXIOM_RUNTIME_FN ax_str axiom_aes_cbc_decrypt_internal(const char* ciphertext_hex, const char* key_hex, const char* iv_hex, int is_256) {
    if (!ciphertext_hex || !key_hex || !iv_hex) return axiom_owned_str_wrap("");
    int key_len = is_256 ? 32 : 16;
    unsigned char key[32] = {0};
    unsigned char iv[16] = {0};
    axiom_internal_hex_to_bytes(key_hex, key, key_len);
    axiom_internal_hex_to_bytes(iv_hex, iv, 16);

    int ct_hex_len = (int)strlen(ciphertext_hex);
    if (ct_hex_len % 2 != 0 || ct_hex_len == 0) return axiom_owned_str_wrap("");
    int ct_len = ct_hex_len / 2;
    unsigned char *ct = (unsigned char*)malloc(ct_len);
    if (!ct) return axiom_owned_str_wrap("");
    axiom_internal_hex_to_bytes(ciphertext_hex, ct, ct_len);

    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    if (!ctx) {
        free(ct);
        return axiom_owned_str_wrap("");
    }
    const EVP_CIPHER *cipher = is_256 ? EVP_aes_256_cbc() : EVP_aes_128_cbc();
    if (EVP_DecryptInit_ex(ctx, cipher, NULL, key, iv) != 1) {
        free(ct);
        EVP_CIPHER_CTX_free(ctx);
        return axiom_owned_str_wrap("");
    }

    unsigned char *pt = (unsigned char*)malloc(ct_len + 32);
    if (!pt) {
        free(ct);
        EVP_CIPHER_CTX_free(ctx);
        return axiom_owned_str_wrap("");
    }
    int pt_len1 = 0, pt_len2 = 0;
    if (EVP_DecryptUpdate(ctx, pt, &pt_len1, ct, ct_len) != 1) {
        free(ct); free(pt); EVP_CIPHER_CTX_free(ctx); return axiom_owned_str_wrap("");
    }
    if (EVP_DecryptFinal_ex(ctx, pt + pt_len1, &pt_len2) != 1) {
        free(ct); free(pt); EVP_CIPHER_CTX_free(ctx); return axiom_owned_str_wrap("");
    }
    int total_pt = pt_len1 + pt_len2;
    pt[total_pt] = '\0';
    char *res = strdup((char*)pt);
    free(ct); free(pt); EVP_CIPHER_CTX_free(ctx);
    return axiom_owned_str_wrap(res ? res : "");
}
#else
AXIOM_RUNTIME_FN ax_str axiom_aes_cbc_decrypt_internal(const char* a, const char* b, const char* c) {
    (void)a; (void)b; (void)c;
    return axiom_owned_str_wrap(
        "AES: bu yapida OpenSSL yok (sessiz yanlis sonuc verilmez)");
}
#endif

#if AXIOM_HAVE_OPENSSL
AXIOM_RUNTIME_FN ax_str axiom_aes256_cbc_encrypt(const char* plaintext, const char* key_hex, const char* iv_hex) {
    return axiom_aes_cbc_encrypt_internal(plaintext, key_hex, iv_hex, 1);
}
#else
AXIOM_RUNTIME_FN ax_str axiom_aes256_cbc_encrypt(const char* a, const char* b, const char* c) {
    (void)a; (void)b; (void)c;
    return axiom_owned_str_wrap(
        "AES: bu yapida OpenSSL yok (sessiz yanlis sonuc verilmez)");
}
#endif

#if AXIOM_HAVE_OPENSSL
AXIOM_RUNTIME_FN ax_str axiom_aes256_cbc_decrypt(const char* ciphertext_hex, const char* key_hex, const char* iv_hex) {
    return axiom_aes_cbc_decrypt_internal(ciphertext_hex, key_hex, iv_hex, 1);
}
#else
AXIOM_RUNTIME_FN ax_str axiom_aes256_cbc_decrypt(const char* a, const char* b, const char* c) {
    (void)a; (void)b; (void)c;
    return axiom_owned_str_wrap(
        "AES: bu yapida OpenSSL yok (sessiz yanlis sonuc verilmez)");
}
#endif

#if AXIOM_HAVE_OPENSSL
AXIOM_RUNTIME_FN ax_str axiom_aes128_cbc_encrypt(const char* plaintext, const char* key_hex, const char* iv_hex) {
    return axiom_aes_cbc_encrypt_internal(plaintext, key_hex, iv_hex, 0);
}
#else
AXIOM_RUNTIME_FN ax_str axiom_aes128_cbc_encrypt(const char* a, const char* b, const char* c) {
    (void)a; (void)b; (void)c;
    return axiom_owned_str_wrap(
        "AES: bu yapida OpenSSL yok (sessiz yanlis sonuc verilmez)");
}
#endif

#if AXIOM_HAVE_OPENSSL
AXIOM_RUNTIME_FN ax_str axiom_aes128_cbc_decrypt(const char* ciphertext_hex, const char* key_hex, const char* iv_hex) {
    return axiom_aes_cbc_decrypt_internal(ciphertext_hex, key_hex, iv_hex, 0);
}
#else
AXIOM_RUNTIME_FN ax_str axiom_aes128_cbc_decrypt(const char* a, const char* b, const char* c) {
    (void)a; (void)b; (void)c;
    return axiom_owned_str_wrap(
        "AES: bu yapida OpenSSL yok (sessiz yanlis sonuc verilmez)");
}
#endif

/**
 * Kriptografik Rastgele Hex Dizisi Uretimi (Anti-Predictable IV)
 */
#if AXIOM_HAVE_OPENSSL
AXIOM_RUNTIME_FN ax_str axiom_crypto_random_hex(ax_int num_bytes) {
    if (num_bytes <= 0) return axiom_owned_str_wrap((char*)"");
    unsigned char* buf = (unsigned char*)malloc((size_t)num_bytes);
    if (!buf) return axiom_owned_str_wrap((char*)"");
    if (RAND_bytes(buf, (int)num_bytes) != 1) {
        int fd = open("/dev/urandom", O_RDONLY);
        if (fd >= 0) {
            ssize_t r = read(fd, buf, (size_t)num_bytes);
            (void)r;
            close(fd);
        }
    }
    char* hex = (char*)malloc((size_t)num_bytes * 2 + 1);
    if (!hex) { free(buf); return axiom_owned_str_wrap((char*)""); }
    for (ax_int i = 0; i < num_bytes; i++) {
        sprintf(hex + (i * 2), "%02x", buf[i]);
    }
    hex[num_bytes * 2] = '\0';
    free(buf);
    return axiom_owned_str_wrap(hex);
}
#else
AXIOM_RUNTIME_FN ax_str axiom_crypto_random_hex(ax_int num_bytes) {
    if (num_bytes <= 0) return axiom_owned_str_wrap("");
    if (num_bytes > 4096) num_bytes = 4096;
    size_t n = (size_t)num_bytes;
    uint8_t* buf = (uint8_t*)malloc(n);
    if (!buf) return axiom_owned_str_wrap("");
#if defined(AXIOM_OS_WINDOWS)
    {
        /* BCryptGenRandom: CSPRNG */
        typedef LONG (WINAPI *fp_bcrypt)(void*, unsigned char*, unsigned long, unsigned long);
        HMODULE b = LoadLibraryA("bcrypt.dll");
        int ok = 0;
        if (b) {
            fp_bcrypt f = (fp_bcrypt)GetProcAddress(b, "BCryptGenRandom");
            if (f && f(NULL, buf, (unsigned long)n, 0x00000002UL) == 0) ok = 1;
        }
        if (!ok) { for (size_t i = 0; i < n; i++) buf[i] = (uint8_t)(rand() & 0xFF); }
    }
#else
    {
        FILE* f = fopen("/dev/urandom", "rb");
        size_t got = 0;
        if (f) { got = fread(buf, 1, n, f); fclose(f); }
        if (got != n) { for (size_t i = got; i < n; i++) buf[i] = (uint8_t)(rand() & 0xFF); }
    }
#endif
    char* hex = (char*)malloc(n * 2 + 1);
    if (!hex) { free(buf); return axiom_owned_str_wrap(""); }
    ax_hex_from_bytes(buf, n, hex);
    free(buf);
    return axiom_owned_str_wrap(hex);
}
#endif /* AXIOM_HAVE_OPENSSL */

/**
 * Standart HMAC-SHA256 Fonksiyonu
 */
#if AXIOM_HAVE_OPENSSL
AXIOM_RUNTIME_FN ax_str axiom_hmac_sha256(const char* key, const char* data) {
    if (!key || !data) return axiom_owned_str_wrap((char*)"");
    unsigned char md[EVP_MAX_MD_SIZE];
    unsigned int md_len = 0;
    HMAC(EVP_sha256(), key, (int)strlen(key), (const unsigned char*)data, strlen(data), md, &md_len);
    char* hex = (char*)malloc((size_t)md_len * 2 + 1);
    if (!hex) return axiom_owned_str_wrap((char*)"");
    for (unsigned int i = 0; i < md_len; i++) {
        sprintf(hex + (i * 2), "%02x", md[i]);
    }
    hex[md_len * 2] = '\0';
    return axiom_owned_str_wrap(hex);
}
#else
AXIOM_RUNTIME_FN ax_str axiom_hmac_sha256(const char* key, const char* data) {
    if (!key) key = "";
    if (!data) data = "";
    uint8_t mac[32]; char hex[65];
    ax_hmac_sha256(key, strlen(key), data, strlen(data), mac);
    ax_hex_from_bytes(mac, 32, hex);
    return axiom_safe_strdup(hex);
}
#endif /* AXIOM_HAVE_OPENSSL */

/**
 * Sabit Zamanlı Karakter/İmza Karşılaştırması (Anti-Timing Attack)
 */
#if AXIOM_HAVE_OPENSSL
AXIOM_RUNTIME_FN ax_bool axiom_crypto_memcmp(const char* s1, const char* s2) {
    if (!s1 || !s2) return s1 == s2;
    size_t len1 = strlen(s1);
    size_t len2 = strlen(s2);
    if (len1 != len2) return false;
    return CRYPTO_memcmp(s1, s2, len1) == 0;
}
#else
AXIOM_RUNTIME_FN ax_bool axiom_crypto_memcmp(const char* s1, const char* s2) {
    if (!s1 || !s2) return false;
    size_t l1 = strlen(s1), l2 = strlen(s2);
    if (l1 != l2) return false;
    return ax_ct_memcmp(s1, s2, l1) ? true : false;
}
#endif /* AXIOM_HAVE_OPENSSL */

/* ========================================================================= */
/* --- 22. JSON Web Token & HMAC-SHA256 (std:security:jwt) --- */
/* ========================================================================= */

static const char AXIOM_B64URL_CHARS[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

static char* axiom_internal_b64url_encode(const unsigned char* in, size_t in_len) {
    if (!in || in_len == 0) return strdup("");
    size_t out_len = 4 * ((in_len + 2) / 3);
    char* out = (char*)malloc(out_len + 1);
    if (!out) return strdup("");

    size_t i = 0, j = 0;
    while (i < in_len) {
        size_t remain = in_len - i;
        uint32_t octet_a = (unsigned char)in[i++];
        uint32_t octet_b = (remain > 1) ? (unsigned char)in[i++] : 0;
        uint32_t octet_c = (remain > 2) ? (unsigned char)in[i++] : 0;
        uint32_t triple = (octet_a << 16) | (octet_b << 8) | octet_c;

        out[j++] = AXIOM_B64URL_CHARS[(triple >> 18) & 0x3F];
        out[j++] = AXIOM_B64URL_CHARS[(triple >> 12) & 0x3F];
        if (remain > 1) out[j++] = AXIOM_B64URL_CHARS[(triple >> 6) & 0x3F];
        if (remain > 2) out[j++] = AXIOM_B64URL_CHARS[triple & 0x3F];
    }
    out[j] = '\0';
    return out;
}

static char* axiom_internal_b64url_decode(const char* s) {
    if (!s) return strdup("");
    size_t in_len = strlen(s);
    if (in_len == 0) return strdup("");

    static int b64url_rev[256];
    static int inited = 0;
    if (!inited) {
        memset(b64url_rev, -1, sizeof(b64url_rev));
        for (int k = 0; k < 64; k++) {
            b64url_rev[(unsigned char)AXIOM_B64URL_CHARS[k]] = k;
        }
        inited = 1;
    }

    size_t out_cap = (in_len / 4) * 3 + 8;
    char* out = (char*)malloc(out_cap);
    if (!out) return strdup("");

    size_t j = 0;
    uint32_t buf = 0;
    int bits = 0;
    for (size_t i = 0; i < in_len; i++) {
        unsigned char c = (unsigned char)s[i];
        if (c == '=') break;
        int val = b64url_rev[c];
        if (val < 0) continue;
        buf = (buf << 6) | (uint32_t)val;
        bits += 6;
        if (bits >= 8) {
            bits -= 8;
            out[j++] = (char)((buf >> bits) & 0xFF);
        }
    }
    out[j] = '\0';
    return out;
}

AXIOM_RUNTIME_FN ax_str axiom_jwt_create_hs256(const char* payload_json, const char* secret) {
    if (!payload_json || !secret) return axiom_owned_str_wrap("");
    const char* header_json = "{\"alg\":\"HS256\",\"typ\":\"JWT\"}";
    char* h_b64 = (char*)axiom_internal_b64url_encode((const unsigned char*)header_json, strlen(header_json));
    char* p_b64 = (char*)axiom_internal_b64url_encode((const unsigned char*)payload_json, strlen(payload_json));

    size_t signing_len = strlen(h_b64) + 1 + strlen(p_b64);
    char* signing_input = (char*)malloc(signing_len + 1);
    if (!signing_input) {
        free(h_b64); free(p_b64);
        return axiom_owned_str_wrap("");
    }
    sprintf(signing_input, "%s.%s", h_b64, p_b64);

    /* HMAC-SHA256: OpenSSL varsa onu, yoksa tasinabilir implementasyonu kullan */
    unsigned char md[32];
    unsigned int md_len = 32;
#if AXIOM_HAVE_OPENSSL
    {
        unsigned int tmp_len = 0;
        unsigned char tmp[EVP_MAX_MD_SIZE];
        HMAC(EVP_sha256(), secret, (int)strlen(secret),
             (const unsigned char*)signing_input, strlen(signing_input), tmp, &tmp_len);
        memcpy(md, tmp, tmp_len < 32 ? tmp_len : 32);
        md_len = tmp_len < 32 ? tmp_len : 32;
    }
#else
    ax_hmac_sha256(secret, strlen(secret), signing_input, strlen(signing_input), md);
    md_len = 32;
#endif
    char* s_b64 = (char*)axiom_internal_b64url_encode(md, md_len);

    size_t jwt_len = signing_len + 1 + strlen(s_b64);
    char* jwt = (char*)malloc(jwt_len + 1);
    if (!jwt) {
        free(h_b64); free(p_b64); free(signing_input); free(s_b64);
        return axiom_owned_str_wrap("");
    }
    sprintf(jwt, "%s.%s", signing_input, s_b64);

    free(h_b64);
    free(p_b64);
    free(signing_input);
    free(s_b64);
    return axiom_owned_str_wrap(jwt);
}

AXIOM_RUNTIME_FN ax_str axiom_jwt_get_header(const char* token) {
    if (!token) return axiom_owned_str_wrap((char*)"");
    const char* p1 = strchr(token, '.');
    if (!p1) return axiom_owned_str_wrap((char*)"");
    size_t len = (size_t)(p1 - token);
    char* h_b64 = (char*)malloc(len + 1);
    if (!h_b64) return axiom_owned_str_wrap((char*)"");
    memcpy(h_b64, token, len);
    h_b64[len] = '\0';
    char* decoded = (char*)axiom_internal_b64url_decode(h_b64);
    free(h_b64);
    return axiom_owned_str_wrap(decoded ? decoded : (char*)"");
}

AXIOM_RUNTIME_FN ax_str axiom_jwt_get_payload(const char* token) {
    if (!token) return axiom_owned_str_wrap((char*)"");
    const char* p1 = strchr(token, '.');
    if (!p1) return axiom_owned_str_wrap((char*)"");
    const char* p2 = strchr(p1 + 1, '.');
    if (!p2) return axiom_owned_str_wrap((char*)"");
    size_t len = (size_t)(p2 - (p1 + 1));
    char* p_b64 = (char*)malloc(len + 1);
    if (!p_b64) return axiom_owned_str_wrap((char*)"");
    memcpy(p_b64, p1 + 1, len);
    p_b64[len] = '\0';
    char* decoded = (char*)axiom_internal_b64url_decode(p_b64);
    free(p_b64);
    return axiom_owned_str_wrap(decoded ? decoded : (char*)"");
}

AXIOM_RUNTIME_FN ax_bool axiom_jwt_verify_hs256(const char* token, const char* secret) {
    if (!token || !secret) return false;
    const char* p1 = strchr(token, '.');
    if (!p1) return false;
    const char* p2 = strchr(p1 + 1, '.');
    if (!p2) return false;

    // 1. Header Kontrolü (alg doğrulaması: yalnızca HS256 kabul edilir, alg: none ve algorithm confusion atakları engellenir)
    ax_str header = axiom_jwt_get_header(token);
    if (!header || strlen(header) == 0) return false;
    if (strstr(header, "\"none\"") || strstr(header, "'none'")) {
        axiom_str_release(header);
        return false;
    }
    if (!strstr(header, "\"HS256\"") && !strstr(header, "'HS256'")) {
        axiom_str_release(header);
        return false;
    }
    axiom_str_release(header);

    // 2. İmza Doğrulama (HMAC-SHA256 ve Sabit Zamanlı CRYPTO_memcmp)
    size_t signing_len = (size_t)(p2 - token);
    char* signing_input = (char*)malloc(signing_len + 1);
    if (!signing_input) return false;
    memcpy(signing_input, token, signing_len);
    signing_input[signing_len] = '\0';

    const char* sig = p2 + 1;
    unsigned char md[32];
    unsigned int md_len = 32;
#if AXIOM_HAVE_OPENSSL
    {
        unsigned int tmp_len = 0;
        unsigned char tmp[EVP_MAX_MD_SIZE];
        HMAC(EVP_sha256(), secret, (int)strlen(secret),
             (const unsigned char*)signing_input, signing_len, tmp, &tmp_len);
        memcpy(md, tmp, tmp_len < 32 ? tmp_len : 32);
        md_len = tmp_len < 32 ? tmp_len : 32;
    }
#else
    ax_hmac_sha256(secret, strlen(secret), signing_input, signing_len, md);
    md_len = 32;
#endif
    char* expected_sig = (char*)axiom_internal_b64url_encode(md, md_len);

    size_t sig_len = strlen(sig);
    size_t exp_len = strlen(expected_sig);
    bool match = (sig_len == exp_len && ax_ct_memcmp(sig, expected_sig, exp_len));
    free(signing_input);
    free(expected_sig);

    if (!match) return false;

    // 3. Zaman Doğrulaması (exp: expiration ve nbf: not-before denetimleri)
    ax_str payload = axiom_jwt_get_payload(token);
    if (!payload || strlen(payload) == 0) return false;

    time_t now = time(NULL);
    if (axiom_json_has_key(payload, "exp")) {
        ax_int exp_time = axiom_json_get_int(payload, "exp");
        if (exp_time > 0 && (ax_int)now > exp_time) {
            if (payload && strlen(payload) > 0) axiom_str_release(payload);
            return false; // Token süresi geçmiş!
        }
    }

    if (axiom_json_has_key(payload, "nbf")) {
        ax_int nbf_time = axiom_json_get_int(payload, "nbf");
        if (nbf_time > 0 && (ax_int)now < nbf_time) {
            if (payload && strlen(payload) > 0) axiom_str_release(payload);
            return false; // Token henüz geçerli değil!
        }
    }

    if (payload && strlen(payload) > 0) axiom_str_release(payload);
    return true;
}

AXIOM_RUNTIME_FN ax_str axiom_jwt_get_claim(const char* token, const char* claim_name) {
    if (!token || !claim_name) return axiom_owned_str_wrap("");
    const char* payload = axiom_jwt_get_payload(token);
    if (!payload || strlen(payload) == 0) return axiom_owned_str_wrap("");
    const char* val = axiom_json_find_key(payload, claim_name);
    if (!val) return axiom_owned_str_wrap("");
    if (*val == '"') {
        val++;
        const char* end = val;
        while (*end && *end != '"') {
            if (*end == '\\' && *(end + 1)) end += 2;
            else end++;
        }
        size_t len = (size_t)(end - val);
        char* res = (char*)malloc(len + 1);
        if (!res) return axiom_owned_str_wrap("");
        memcpy(res, val, len);
        res[len] = '\0';
        return axiom_owned_str_wrap(res);
    } else {
        const char* end = val;
        while (*end && *end != ',' && *end != '}' && *end != ']' && !isspace((unsigned char)*end)) {
            end++;
        }
        size_t len = (size_t)(end - val);
        char* res = (char*)malloc(len + 1);
        if (!res) return axiom_owned_str_wrap("");
        memcpy(res, val, len);
        res[len] = '\0';
        return axiom_owned_str_wrap(res);
    }
}

/* ========================================================================= */
/* --- 23. HTML Entity & XSS Güvenlik Yardımcıları (std:encoding:html) --- */
/* ========================================================================= */

AXIOM_RUNTIME_FN ax_str axiom_html_escape(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    size_t len = strlen(s);
    size_t cap = len * 6 + 1;
    char* out = (char*)malloc(cap);
    if (!out) return axiom_owned_str_wrap("");
    size_t j = 0;
    for (size_t i = 0; i < len; i++) {
        switch (s[i]) {
            case '&': memcpy(&out[j], "&amp;", 5); j += 5; break;
            case '<': memcpy(&out[j], "&lt;", 4); j += 4; break;
            case '>': memcpy(&out[j], "&gt;", 4); j += 4; break;
            case '"': memcpy(&out[j], "&quot;", 6); j += 6; break;
            case '\'': memcpy(&out[j], "&#39;", 5); j += 5; break;
            default: out[j++] = s[i]; break;
        }
    }
    out[j] = '\0';
    return axiom_owned_str_wrap(out);
}

AXIOM_RUNTIME_FN ax_str axiom_html_unescape(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    size_t len = strlen(s);
    char* out = (char*)malloc(len + 1);
    if (!out) return axiom_owned_str_wrap("");
    size_t j = 0;
    for (size_t i = 0; i < len; ) {
        if (s[i] == '&') {
            if (strncmp(&s[i], "&amp;", 5) == 0) { out[j++] = '&'; i += 5; }
            else if (strncmp(&s[i], "&lt;", 4) == 0) { out[j++] = '<'; i += 4; }
            else if (strncmp(&s[i], "&gt;", 4) == 0) { out[j++] = '>'; i += 4; }
            else if (strncmp(&s[i], "&quot;", 6) == 0) { out[j++] = '"'; i += 6; }
            else if (strncmp(&s[i], "&#39;", 5) == 0) { out[j++] = '\''; i += 5; }
            else { out[j++] = s[i++]; }
        } else {
            out[j++] = s[i++];
        }
    }
    out[j] = '\0';
    return axiom_owned_str_wrap(out);
}

AXIOM_RUNTIME_FN ax_str axiom_html_strip_tags(const char* s) {
    if (!s) return axiom_owned_str_wrap("");
    size_t len = strlen(s);
    char* out = (char*)malloc(len + 1);
    if (!out) return axiom_owned_str_wrap("");
    size_t j = 0;
    int in_tag = 0;
    for (size_t i = 0; i < len; i++) {
        if (s[i] == '<') {
            in_tag = 1;
        } else if (s[i] == '>') {
            in_tag = 0;
        } else if (!in_tag) {
            out[j++] = s[i];
        }
    }
    out[j] = '\0';
    return axiom_owned_str_wrap(out);
}

/* ========================================================================= */
/* --- 24. Seviyeli ve Renkli Loglama Motoru (std:log:logger) --- */
/* ========================================================================= */

static int g_axiom_log_level = 0; // 0: DEBUG, 1: INFO, 2: WARN, 3: ERROR

AXIOM_RUNTIME_FN void axiom_log_set_level(ax_int level) {
    g_axiom_log_level = (int)level;
}

AXIOM_RUNTIME_FN void axiom_internal_log(int level, const char* module, const char* msg) {
    if (level < g_axiom_log_level) return;
    time_t rawtime;
    struct tm *info;
    char time_str[32];
    time(&rawtime);
    info = localtime(&rawtime);
    strftime(time_str, sizeof(time_str), "%Y-%m-%d %H:%M:%S", info);

    const char* color_code;
    const char* level_name;
    switch (level) {
        case 0: color_code = "\033[36m"; level_name = "DEBUG"; break; // Cyan
        case 1: color_code = "\033[32m"; level_name = "INFO";  break; // Green
        case 2: color_code = "\033[33m"; level_name = "WARN";  break; // Yellow
        case 3: color_code = "\033[31m"; level_name = "ERROR"; break; // Red
        default: color_code = "\033[0m"; level_name = "LOG";   break;
    }

    if (!module || strlen(module) == 0) {
        module = "main";
    }

    printf("[%s] %s[%-5s]\033[0m [%s] %s\n",
           time_str, color_code, level_name, module, msg ? msg : "");
    fflush(stdout);
}

AXIOM_RUNTIME_FN void axiom_log_debug(const char* module, const char* msg) {
    axiom_internal_log(0, module, msg);
}

AXIOM_RUNTIME_FN void axiom_log_info(const char* module, const char* msg) {
    axiom_internal_log(1, module, msg);
}

AXIOM_RUNTIME_FN void axiom_log_warn(const char* module, const char* msg) {
    axiom_internal_log(2, module, msg);
}

AXIOM_RUNTIME_FN void axiom_log_error(const char* module, const char* msg) {
    axiom_internal_log(3, module, msg);
}

/* ========================================================================= */
/* --- 25. Ham Ağ, Ping & Checksum (std:net:raw_socket) --- */
/* ========================================================================= */

struct axiom_icmp_echo_hdr {
    uint8_t type;
    uint8_t code;
    uint16_t checksum;
    uint16_t id;
    uint16_t seq;
    char data[32];
};

AXIOM_RUNTIME_FN uint16_t axiom_internal_in_cksum(uint16_t *addr, int len) {
    int nleft = len;
    int sum = 0;
    uint16_t *w = addr;
    uint16_t answer = 0;

    while (nleft > 1) {
        sum += *w++;
        nleft -= 2;
    }
    if (nleft == 1) {
        *(unsigned char *)(&answer) = *(unsigned char *)w;
        sum += answer;
    }
    sum = (sum >> 16) + (sum & 0xffff);
    sum += (sum >> 16);
    answer = ~sum;
    return answer;
}

AXIOM_RUNTIME_FN ax_int axiom_icmp_ping(const char* host, ax_int timeout_ms) {
    if (!host || strlen(host) == 0) return -1;
    struct in_addr resolved;
    if (!axiom_internal_resolve_ipv4(host, &resolved)) return -1;

    int s = ax_os_socket(AF_INET, SOCK_DGRAM, IPPROTO_ICMP);
    if (s < 0) {
        s = ax_os_socket(AF_INET, SOCK_RAW, IPPROTO_ICMP);
        if (s < 0) return -1;
    }

    struct sockaddr_in dest;
    memset(&dest, 0, sizeof(dest));
    dest.sin_family = AF_INET;
    dest.sin_addr = resolved;

    struct axiom_icmp_echo_hdr pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.type = 8; // ICMP_ECHO
    pkt.code = 0;
    pkt.id = (uint16_t)(getpid() & 0xFFFF);
    pkt.seq = 1;
    strcpy(pkt.data, "Axiom Security ICMP Ping");
    pkt.checksum = axiom_internal_in_cksum((uint16_t*)&pkt, sizeof(pkt));

    long to_ms = timeout_ms > 0 ? (long)timeout_ms : 1000;
        ax_os_sock_set_timeout(s, 2000);

    long long t1_ms = ax_os_time_ms();

    int sent = sendto(s, (const char*)&pkt, sizeof(pkt), 0, (struct sockaddr*)&dest, sizeof(dest));
    if (sent < 0) {
        close(s);
        return -1;
    }

    char recv_buf[256];
    socklen_t slen = sizeof(dest);
    int recvd = recvfrom(s, recv_buf, sizeof(recv_buf), 0, (struct sockaddr*)&dest, &slen);
    long long t2_ms = ax_os_time_ms();
    close(s);

    if (recvd < 0) {
        return -1;
    }
    long long ms = t2_ms - t1_ms;
    return (ax_int)(ms >= 0 ? ms : 0);
}

AXIOM_RUNTIME_FN ax_int axiom_tcp_ping(const char* host, ax_int port, ax_int timeout_ms) {
    if (!host || port <= 0) return -1;
    struct in_addr resolved;
    if (!axiom_internal_resolve_ipv4(host, &resolved)) return -1;

    int s = ax_os_socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) return -1;

    ax_os_sock_set_nonblocking(ax_os_int_to_sock(s), 1);

    struct sockaddr_in dest;
    memset(&dest, 0, sizeof(dest));
    dest.sin_family = AF_INET;
    dest.sin_port = htons((uint16_t)port);
    dest.sin_addr = resolved;

    long long t1_ms = ax_os_time_ms();

    int res = connect(s, (struct sockaddr*)&dest, sizeof(dest));
    if (res < 0 && ax_os_sock_last_error() != ax_os_inprogress_error()) {
        close(s);
        return -1;
    }

    if (res != 0) {
        int poll_res = ax_os_poll_write(ax_os_int_to_sock(s),
                                        timeout_ms > 0 ? (int)timeout_ms : 1000);
        if (poll_res <= 0) {
            close(s);
            return -1;
        }
        int err = ax_os_sock_get_error(ax_os_int_to_sock(s));
        if (err < 0 || err != 0) {
            close(s);
            return -1;
        }
    }

    long long t2_ms = ax_os_time_ms();
    close(s);

    long long ms = t2_ms - t1_ms;
    return (ax_int)(ms >= 0 ? ms : 0);
}

AXIOM_RUNTIME_FN ax_int axiom_raw_checksum(const char* data_hex) {
    if (!data_hex) return 0;
    size_t hex_len = strlen(data_hex);
    if (hex_len == 0) return 0;
    size_t byte_len = hex_len / 2;
    uint8_t *bytes = (uint8_t*)malloc(byte_len);
    if (!bytes) return 0;
    for (size_t i = 0; i < byte_len; i++) {
        unsigned int v = 0;
        sscanf(data_hex + i * 2, "%02x", &v);
        bytes[i] = (uint8_t)v;
    }

    uint32_t sum = 0;
    size_t i = 0;
    while (i + 1 < byte_len) {
        uint16_t word = ((uint16_t)bytes[i] << 8) | (uint16_t)bytes[i + 1];
        sum += word;
        i += 2;
    }
    if (i < byte_len) {
        uint16_t word = ((uint16_t)bytes[i] << 8);
        sum += word;
    }
    while (sum >> 16) {
        sum = (sum & 0xFFFF) + (sum >> 16);
    }
    uint16_t result = ~sum;
    free(bytes);
    return (ax_int)result;
}

/* ========================================================================= */
/* FAZ 2: RED TEAM & GUVENLIK SISTEM MUHENDISLIGI                             */
/* ========================================================================= */

/* 1. Dinamik Calistirilabilir Bellek (Executable Memory / JIT Execution) */
AXIOM_RUNTIME_FN ax_int axiom_exec_mem_run(const char* hex_code) {
    if (!hex_code || strlen(hex_code) == 0) return -1;
    size_t hex_len = strlen(hex_code);
    if (hex_len % 2 != 0) return -1;
    size_t byte_len = hex_len / 2;

    void* mem = ax_os_alloc_rwx(byte_len);
    if (!mem) return -2;   /* desteklenmeyen platform: acik hata */

    uint8_t* p = (uint8_t*)mem;
    for (size_t i = 0; i < byte_len; i++) {
        unsigned int val = 0;
        sscanf(hex_code + i * 2, "%02x", &val);
        p[i] = (uint8_t)val;
    }

    typedef int (*fn_t)(void);
    fn_t code_fn = (fn_t)mem;
    int ret_val = code_fn();

    ax_os_free_exec(mem, byte_len);
    return (ax_int)ret_val;
}

AXIOM_RUNTIME_FN ax_int axiom_exec_mem_alloc(ax_int size) {
    if (size <= 0) return 0;
    void* mem = ax_os_alloc_exec((size_t)size);
    if (!mem) return 0;
    return (ax_int)(uintptr_t)mem;
}

AXIOM_RUNTIME_FN ax_bool axiom_exec_mem_protect(ax_int ptr, ax_int size, ax_int prot) {
    if (!ptr || size <= 0) return false;
    return ax_os_protect_exec((void*)(uintptr_t)ptr, (size_t)size, (int)prot) ? true : false;
}

/* 2. Ozel Ag Paketi Sentezi (Raw Packet Synthesis) */
AXIOM_RUNTIME_FN ax_str axiom_packet_craft_ip(const char* src_ip, const char* dst_ip, ax_int proto, ax_int payload_len) {
    uint8_t hdr[20];
    memset(hdr, 0, 20);
    hdr[0] = 0x45; /* Version 4, IHL 5 */
    hdr[1] = 0x00; /* DSCP / ECN */
    uint16_t total_len = (uint16_t)(20 + payload_len);
    hdr[2] = (uint8_t)(total_len >> 8);
    hdr[3] = (uint8_t)(total_len & 0xFF);
    hdr[4] = 0x13; hdr[5] = 0x37; /* Identification */
    hdr[6] = 0x40; hdr[7] = 0x00; /* Flags: Don't Fragment */
    hdr[8] = 64;   /* TTL */
    hdr[9] = (uint8_t)proto; /* Protocol (e.g. 6 TCP, 17 UDP, 1 ICMP) */
    
    struct in_addr src_addr, dst_addr;
    inet_pton(AF_INET, src_ip ? src_ip : "127.0.0.1", &src_addr);
    inet_pton(AF_INET, dst_ip ? dst_ip : "127.0.0.1", &dst_addr);
    memcpy(hdr + 12, &src_addr.s_addr, 4);
    memcpy(hdr + 16, &dst_addr.s_addr, 4);

    /* Checksum */
    uint32_t sum = 0;
    for (int i = 0; i < 20; i += 2) {
        if (i == 10) continue; /* Header checksum field */
        sum += ((uint16_t)hdr[i] << 8) | (uint16_t)hdr[i + 1];
    }
    while (sum >> 16) sum = (sum & 0xFFFF) + (sum >> 16);
    uint16_t csum = ~sum;
    hdr[10] = (uint8_t)(csum >> 8);
    hdr[11] = (uint8_t)(csum & 0xFF);

    char* out = (char*)malloc(41);
    for (int i = 0; i < 20; i++) {
        sprintf(out + i * 2, "%02x", hdr[i]);
    }
    out[40] = '\0';
    return axiom_owned_str_wrap(out);
}

AXIOM_RUNTIME_FN ax_str axiom_packet_craft_tcp(const char* src_ip, const char* dst_ip, ax_int src_port, ax_int dst_port, ax_int seq, ax_int flags) {
    (void)src_ip; (void)dst_ip;
    uint8_t tcp[20];
    memset(tcp, 0, 20);
    tcp[0] = (uint8_t)(src_port >> 8);
    tcp[1] = (uint8_t)(src_port & 0xFF);
    tcp[2] = (uint8_t)(dst_port >> 8);
    tcp[3] = (uint8_t)(dst_port & 0xFF);
    tcp[4] = (uint8_t)(seq >> 24);
    tcp[5] = (uint8_t)(seq >> 16);
    tcp[6] = (uint8_t)(seq >> 8);
    tcp[7] = (uint8_t)(seq & 0xFF);
    tcp[12] = 0x50; /* Data offset: 5 (20 bytes) */
    tcp[13] = (uint8_t)flags; /* TCP flags: SYN=0x02, ACK=0x10, PSH=0x08, RST=0x04 */
    tcp[14] = 0x72; tcp[15] = 0x10; /* Window size: 29200 */

    char* out = (char*)malloc(41);
    for (int i = 0; i < 20; i++) {
        sprintf(out + i * 2, "%02x", tcp[i]);
    }
    out[40] = '\0';
    return axiom_owned_str_wrap(out);
}

AXIOM_RUNTIME_FN ax_str axiom_packet_craft_udp(ax_int src_port, ax_int dst_port, const char* payload) {
    size_t plen = payload ? strlen(payload) : 0;
    uint16_t ulen = (uint16_t)(8 + plen);
    uint8_t udp[8];
    udp[0] = (uint8_t)(src_port >> 8);
    udp[1] = (uint8_t)(src_port & 0xFF);
    udp[2] = (uint8_t)(dst_port >> 8);
    udp[3] = (uint8_t)(dst_port & 0xFF);
    udp[4] = (uint8_t)(ulen >> 8);
    udp[5] = (uint8_t)(ulen & 0xFF);
    udp[6] = 0; udp[7] = 0; /* Optional checksum */

    size_t total_hex = (8 + plen) * 2;
    char* out = (char*)malloc(total_hex + 1);
    for (int i = 0; i < 8; i++) {
        sprintf(out + i * 2, "%02x", udp[i]);
    }
    for (size_t i = 0; i < plen; i++) {
        sprintf(out + 16 + i * 2, "%02x", (uint8_t)payload[i]);
    }
    out[total_hex] = '\0';
    return axiom_owned_str_wrap(out);
}

/* 3. Ortam ve Hata Ayiklayici Teshisi (Environment Diagnostics) */
AXIOM_RUNTIME_FN ax_bool axiom_diag_is_debugged(void) {
    FILE* fp = fopen("/proc/self/status", "r");
    if (!fp) return false;
    char line[256];
    int tracer_pid = 0;
    while (fgets(line, sizeof(line), fp)) {
        if (strncmp(line, "TracerPid:", 10) == 0) {
            tracer_pid = atoi(line + 10);
            break;
        }
    }
    fclose(fp);
    return tracer_pid > 0;
}

AXIOM_RUNTIME_FN ax_bool axiom_diag_is_virtualized(void) {
    #if defined(__x86_64__) || defined(_M_X64)
    unsigned int eax, ebx, ecx, edx;
    if (ax_os_cpuid(1, 0, &eax, &ebx, &ecx, &edx)) {
        if (ecx & (1 << 31)) return true; /* Hypervisor present bit */
    }
    #endif

    FILE* fp = fopen("/sys/class/dmi/id/product_name", "r");
    if (fp) {
        char buf[128];
        if (fgets(buf, sizeof(buf), fp)) {
            if (strstr(buf, "VMware") || strstr(buf, "VirtualBox") || 
                strstr(buf, "KVM") || strstr(buf, "QEMU")) {
                fclose(fp);
                return true;
            }
        }
        fclose(fp);
    }
    return false;
}

AXIOM_RUNTIME_FN void axiom_diag_set_dumpable(ax_bool dumpable) {
    #ifdef PR_SET_DUMPABLE
    prctl(PR_SET_DUMPABLE, dumpable ? 1 : 0, 0, 0, 0);
    #endif
}

/* 4. Canli Surec Bellek Inceleme ve Teshis (Process Memory Inspection) */
#if defined(AXIOM_OS_LINUX)
AXIOM_RUNTIME_FN ax_int axiom_proc_search_pattern(ax_int pid, const char* pattern) {
    if (!pattern || strlen(pattern) == 0) return 0;
    char maps_path[64], mem_path[64];
    sprintf(maps_path, "/proc/%" PRId64 "/maps", pid);
    sprintf(mem_path, "/proc/%" PRId64 "/mem", pid);

    FILE* maps_fp = fopen(maps_path, "r");
    if (!maps_fp) return 0;

    int mem_fd = open(mem_path, O_RDONLY);
    if (mem_fd < 0) {
        fclose(maps_fp);
        return 0;
    }

    size_t pat_len = strlen(pattern);
    char line[256];
    ax_int match_count = 0;

    while (fgets(line, sizeof(line), maps_fp)) {
        uintptr_t start = 0, end = 0;
        char perms[8];
        if (sscanf(line, "%lx-%lx %s", &start, &end, perms) >= 3) {
            if (perms[0] == 'r' && (end > start) && (end - start <= 16 * 1024 * 1024)) {
                size_t region_size = end - start;
                uint8_t* buf = (uint8_t*)malloc(region_size);
                if (buf) {
                    ssize_t bytes_read = pread(mem_fd, buf, region_size, (off_t)start);
                    if (bytes_read > (ssize_t)pat_len) {
                        for (ssize_t i = 0; i <= bytes_read - (ssize_t)pat_len; i++) {
                            if (memcmp(buf + i, pattern, pat_len) == 0) {
                                match_count++;
                            }
                        }
                    }
                    free(buf);
                }
            }
        }
    }

    close(mem_fd);
    fclose(maps_fp);
    return match_count;
}
#else
/* /proc dosya sistemi yalnizca Linux'ta var. Sessiz 0 yerine acik hata:
 * "desen bulunamadi" ile "platform desteklemiyor" karistirilmamali. */
AXIOM_RUNTIME_FN ax_int axiom_proc_search_pattern(ax_int pid, const char* pattern) {
    (void)pid; (void)pattern;
    fprintf(stderr, "[axiom] proc_search_pattern: bu platformda /proc yok (yalnizca Linux)\n");
    return -1;
}
#endif

AXIOM_RUNTIME_FN ax_str axiom_proc_get_maps(ax_int pid) {
    char maps_path[64];
    sprintf(maps_path, "/proc/%" PRId64 "/maps", pid);
    FILE* fp = fopen(maps_path, "r");
    if (!fp) return axiom_owned_str_wrap("");

    fseek(fp, 0, SEEK_END);
    long sz = ftell(fp);
    rewind(fp);

    if (sz <= 0) sz = 4096;
    char* buf = (char*)malloc(sz + 1);
    size_t r = fread(buf, 1, sz, fp);
    buf[r] = '\0';
    fclose(fp);
    return axiom_owned_str_wrap(buf);
}

/* ========================================================================= */
/* FAZ 3: BLUE TEAM, DEFANSİF GÜVENLİK VE ADLİ BİLİŞİM (DFIR)                */
/* ========================================================================= */

typedef struct {
    FILE* fp;
    int is_writer;
    uint32_t packet_count;
} AxiomPcapHandle;

#define AXIOM_MAX_PCAP_HANDLES 32
static AxiomPcapHandle* g_pcap_handles[AXIOM_MAX_PCAP_HANDLES] = {0};

AXIOM_RUNTIME_FN ax_int axiom_pcap_create_writer(const char* path) {
    if (!path) return -1;
    FILE* fp = fopen(path, "wb");
    if (!fp) return -1;

    /* Standart PCAP Global Header (24 bytes) */
    uint32_t magic = 0xa1b2c3d4;
    uint16_t v_maj = 2, v_min = 4;
    int32_t  zone = 0;
    uint32_t sigfigs = 0, snaplen = 65535, network = 1; /* 1 = Ethernet */

    fwrite(&magic, 4, 1, fp);
    fwrite(&v_maj, 2, 1, fp);
    fwrite(&v_min, 2, 1, fp);
    fwrite(&zone, 4, 1, fp);
    fwrite(&sigfigs, 4, 1, fp);
    fwrite(&snaplen, 4, 1, fp);
    fwrite(&network, 4, 1, fp);
    fflush(fp);

    for (int i = 1; i < AXIOM_MAX_PCAP_HANDLES; i++) {
        if (!g_pcap_handles[i]) {
            AxiomPcapHandle* h = (AxiomPcapHandle*)malloc(sizeof(AxiomPcapHandle));
            h->fp = fp;
            h->is_writer = 1;
            h->packet_count = 0;
            g_pcap_handles[i] = h;
            return (ax_int)i;
        }
    }
    fclose(fp);
    return -1;
}

AXIOM_RUNTIME_FN ax_bool axiom_pcap_write_packet(ax_int handle, const char* packet_hex) {
    if (handle <= 0 || handle >= AXIOM_MAX_PCAP_HANDLES || !g_pcap_handles[handle]) return false;
    AxiomPcapHandle* h = g_pcap_handles[handle];
    if (!h->is_writer || !packet_hex) return false;

    size_t hex_len = strlen(packet_hex);
    if (hex_len % 2 != 0) return false;
    uint32_t byte_len = (uint32_t)(hex_len / 2);

    long long now_ms = ax_os_time_ms();
    uint32_t ts_sec = (uint32_t)(now_ms / 1000);
    uint32_t ts_usec = (uint32_t)((now_ms % 1000) * 1000);

    /* PCAP Packet Header (16 bytes) */
    fwrite(&ts_sec, 4, 1, h->fp);
    fwrite(&ts_usec, 4, 1, h->fp);
    fwrite(&byte_len, 4, 1, h->fp);
    fwrite(&byte_len, 4, 1, h->fp);

    /* Payload */
    uint8_t* buf = (uint8_t*)malloc(byte_len);
    for (size_t i = 0; i < byte_len; i++) {
        unsigned int v = 0;
        sscanf(packet_hex + i * 2, "%02x", &v);
        buf[i] = (uint8_t)v;
    }
    fwrite(buf, 1, byte_len, h->fp);
    free(buf);
    fflush(h->fp);
    h->packet_count++;
    return true;
}

AXIOM_RUNTIME_FN ax_int axiom_pcap_open_file(const char* path) {
    if (!path) return -1;
    FILE* fp = fopen(path, "rb");
    if (!fp) return -1;

    uint32_t magic = 0;
    if (fread(&magic, 4, 1, fp) != 1 || (magic != 0xa1b2c3d4 && magic != 0xd4c3b2a1)) {
        fclose(fp);
        return -2; /* Gecersiz PCAP magic */
    }
    fseek(fp, 24, SEEK_SET); /* Global header'i gec */

    for (int i = 1; i < AXIOM_MAX_PCAP_HANDLES; i++) {
        if (!g_pcap_handles[i]) {
            AxiomPcapHandle* h = (AxiomPcapHandle*)malloc(sizeof(AxiomPcapHandle));
            h->fp = fp;
            h->is_writer = 0;
            h->packet_count = 0;
            g_pcap_handles[i] = h;
            return (ax_int)i;
        }
    }
    fclose(fp);
    return -1;
}

AXIOM_RUNTIME_FN ax_str axiom_pcap_next_packet(ax_int handle) {
    if (handle <= 0 || handle >= AXIOM_MAX_PCAP_HANDLES || !g_pcap_handles[handle]) return axiom_owned_str_wrap("");
    AxiomPcapHandle* h = g_pcap_handles[handle];
    if (h->is_writer) return axiom_owned_str_wrap("");

    uint32_t ts_sec, ts_usec, incl_len, orig_len;
    if (fread(&ts_sec, 4, 1, h->fp) != 1) return axiom_owned_str_wrap("");
    if (fread(&ts_usec, 4, 1, h->fp) != 1) return axiom_owned_str_wrap("");
    if (fread(&incl_len, 4, 1, h->fp) != 1) return axiom_owned_str_wrap("");
    if (fread(&orig_len, 4, 1, h->fp) != 1) return axiom_owned_str_wrap("");

    if (incl_len == 0 || incl_len > 65535) return axiom_owned_str_wrap("");
    uint8_t* raw = (uint8_t*)malloc(incl_len);
    if (fread(raw, 1, incl_len, h->fp) != incl_len) {
        free(raw);
        return axiom_owned_str_wrap("");
    }

    char* out = (char*)malloc(incl_len * 2 + 1);
    for (size_t i = 0; i < incl_len; i++) {
        sprintf(out + i * 2, "%02x", raw[i]);
    }
    out[incl_len * 2] = '\0';
    free(raw);
    h->packet_count++;
    return axiom_owned_str_wrap(out);
}

AXIOM_RUNTIME_FN ax_int axiom_pcap_packet_count(ax_int handle) {
    if (handle <= 0 || handle >= AXIOM_MAX_PCAP_HANDLES || !g_pcap_handles[handle]) return 0;
    return (ax_int)g_pcap_handles[handle]->packet_count;
}

AXIOM_RUNTIME_FN void axiom_pcap_close(ax_int handle) {
    if (handle <= 0 || handle >= AXIOM_MAX_PCAP_HANDLES || !g_pcap_handles[handle]) return;
    fclose(g_pcap_handles[handle]->fp);
    free(g_pcap_handles[handle]);
    g_pcap_handles[handle] = NULL;
}

/* FIM (File Integrity Monitoring) SHA-256 */
AXIOM_RUNTIME_FN ax_str axiom_fim_hash_file(const char* file_path) {
    if (!file_path) return axiom_owned_str_wrap("");
    FILE* fp = fopen(file_path, "rb");
    if (!fp) return axiom_owned_str_wrap("");

    ax_sha256_ctx ctx;
    ax_sha256_init(&ctx);

    uint8_t buf[65536];
    size_t n;
    while ((n = fread(buf, 1, sizeof(buf), fp)) > 0) {
        ax_sha256_update(&ctx, buf, n);
    }
    fclose(fp);

    uint8_t hash[32];
    ax_sha256_final(&ctx, hash);

    char* out = (char*)malloc(65);
    if (!out) return axiom_owned_str_wrap("");
    ax_hex_from_bytes(hash, 32, out);
    return axiom_owned_str_wrap(out);
}

#if defined(AXIOM_OS_LINUX)
/* ========================================================================= */
/* Linux Adli Bilisim (Forensics): Acik Portlar (yalnizca Linux) */
AXIOM_RUNTIME_FN ax_str axiom_forensics_get_ports(void) {
    FILE* fp = fopen("/proc/net/tcp", "r");
    if (!fp) return axiom_owned_str_wrap("");

    char line[256];
    char* result = (char*)calloc(1, 4096);
    if (!result) { fclose(fp); return axiom_owned_str_wrap(""); }
    size_t cur_len = 0;

    /* Header satirini atla */
    if (fgets(line, sizeof(line), fp)) {}

    while (fgets(line, sizeof(line), fp)) {
        unsigned int local_ip = 0, local_port = 0, state = 0;
        int n = sscanf(line, " %*d: %x:%x %*x:%*x %x", &local_ip, &local_port, &state);
        if (n >= 3 && state == 0x0A) {   /* 0x0A = TCP_LISTEN */
            struct in_addr addr;
            addr.s_addr = local_ip;
            char ipbuf[32];
            inet_ntop(AF_INET, &addr, ipbuf, sizeof(ipbuf));
            char entry[64];
            snprintf(entry, sizeof(entry), "%s:%d\n", ipbuf, local_port);
            size_t elen = strlen(entry);
            if (cur_len + elen < 4000) {
                strcat(result, entry);
                cur_len += elen;
            }
        }
    }
    fclose(fp);
    return axiom_owned_str_wrap(result);
}

/* ========================================================================= */
AXIOM_RUNTIME_FN ax_str axiom_forensics_get_processes(void) {
    DIR* dir = opendir("/proc");
    if (!dir) return axiom_owned_str_wrap("");

    char* result = (char*)calloc(1, 16384);
    if (!result) { closedir(dir); return axiom_owned_str_wrap(""); }
    size_t cur_len = 0;
    struct dirent* ent;

    while ((ent = readdir(dir)) != NULL) {
        /* Yalnızca sayısal dizin adları (= PID) */
        const char* nm = ent->d_name;
        size_t k = 0;
        bool numeric = nm[0] != '\0';
        while (nm[k]) {
            if (!isdigit((unsigned char)nm[k])) { numeric = false; break; }
            k++;
        }
        if (!numeric || k > 10) continue;

        char comm_path[64];
        snprintf(comm_path, sizeof(comm_path), "/proc/%s/comm", nm);
        FILE* fp = fopen(comm_path, "r");
        if (!fp) continue;

        char comm[128] = {0};
        if (!fgets(comm, sizeof(comm), fp)) { fclose(fp); continue; }
        fclose(fp);
        comm[strcspn(comm, "\n")] = '\0';
        if (comm[0] == '\0') continue;

        char entry[192];
        int n = snprintf(entry, sizeof(entry), "%s:%s\n", nm, comm);
        if (n <= 0) continue;
        if (cur_len + (size_t)n >= 16000) break;
        memcpy(result + cur_len, entry, (size_t)n + 1);
        cur_len += (size_t)n;
    }
    closedir(dir);
    return axiom_owned_str_wrap(result);
}

/* ========================================================================= */
AXIOM_RUNTIME_FN ax_str axiom_forensics_get_modules(void) {
    FILE* fp = fopen("/proc/modules", "r");
    if (!fp) return axiom_owned_str_wrap("");

    char line[256];
    char* result = (char*)calloc(1, 8192);
    size_t cur_len = 0;

    while (fgets(line, sizeof(line), fp)) {
        char mod_name[64];
        if (sscanf(line, "%63s", mod_name) == 1) {
            size_t elen = strlen(mod_name);
            if (cur_len + elen + 2 < 8000) {
                if (cur_len > 0) {
                    strcat(result, ",");
                    cur_len++;
                }
                strcat(result, mod_name);
                cur_len += elen;
            }
        }
    }
    fclose(fp);
    return axiom_owned_str_wrap(result);
}

#else  /* !AXIOM_OS_LINUX ------------------------------------------------ */

/* /proc yalnizca Linux'ta var. Bos sonuc dondurmek "temiz sistem" gibi
 * yanlis okunur; bu yuzden ACIK HATA mesaji yazilir. */
static void ax_forensics_unsupported(const char* fn_name) {
    fprintf(stderr,
            "[axiom] %s: bu platformda /proc yok (yalnizca Linux destekler)\n",
            fn_name);
}
AXIOM_RUNTIME_FN ax_str axiom_forensics_get_ports(void) {
    ax_forensics_unsupported("forensics_list_listening_ports");
    return axiom_owned_str_wrap("");
}
AXIOM_RUNTIME_FN ax_str axiom_forensics_get_processes(void) {
    ax_forensics_unsupported("forensics_list_processes");
    return axiom_owned_str_wrap("");
}
AXIOM_RUNTIME_FN ax_str axiom_forensics_get_modules(void) {
    ax_forensics_unsupported("forensics_list_kernel_modules");
    return axiom_owned_str_wrap("");
}

#endif /* AXIOM_OS_LINUX */

/* ========================================================================= */
/* FAZ 4: YAPAY ZEKA (AI / ML) & HETEROJEN TENSÖR HESAPLAMA ÇEKİRDEĞİ        */
/* ========================================================================= */

typedef struct {
    int rows;
    int cols;
    int size;
    double* data;
} AxiomTensor;

#define AXIOM_MAX_TENSORS 128
static AxiomTensor* g_tensors[AXIOM_MAX_TENSORS] = {0};

AXIOM_RUNTIME_FN ax_int axiom_tensor_create_2d(ax_int rows, ax_int cols) {
    if (rows <= 0 || cols <= 0) return -1;
    for (int i = 1; i < AXIOM_MAX_TENSORS; i++) {
        if (!g_tensors[i]) {
            AxiomTensor* t = (AxiomTensor*)malloc(sizeof(AxiomTensor));
            t->rows = (int)rows;
            t->cols = (int)cols;
            t->size = (int)(rows * cols);
            t->data = (double*)calloc(t->size, sizeof(double));
            g_tensors[i] = t;
            return (ax_int)i;
        }
    }
    return -1;
}

AXIOM_RUNTIME_FN void axiom_tensor_set(ax_int h, ax_int r, ax_int c, ax_float val) {
    if (h <= 0 || h >= AXIOM_MAX_TENSORS || !g_tensors[h]) return;
    AxiomTensor* t = g_tensors[h];
    if (r >= 0 && r < t->rows && c >= 0 && c < t->cols) {
        t->data[r * t->cols + c] = (double)val;
    }
}

AXIOM_RUNTIME_FN ax_float axiom_tensor_get(ax_int h, ax_int r, ax_int c) {
    if (h <= 0 || h >= AXIOM_MAX_TENSORS || !g_tensors[h]) return 0.0;
    AxiomTensor* t = g_tensors[h];
    if (r >= 0 && r < t->rows && c >= 0 && c < t->cols) {
        return (ax_float)t->data[r * t->cols + c];
    }
    return 0.0;
}

AXIOM_RUNTIME_FN ax_int axiom_tensor_rows(ax_int h) {
    if (h <= 0 || h >= AXIOM_MAX_TENSORS || !g_tensors[h]) return 0;
    return (ax_int)g_tensors[h]->rows;
}

AXIOM_RUNTIME_FN ax_int axiom_tensor_cols(ax_int h) {
    if (h <= 0 || h >= AXIOM_MAX_TENSORS || !g_tensors[h]) return 0;
    return (ax_int)g_tensors[h]->cols;
}

/* AVX2 / SIMD & Cache-Blocked Matris Çarpımı (GEMM): C = A x B */
#define AXIOM_GEMM_BLOCK_M 64
#define AXIOM_GEMM_BLOCK_K 64
#define AXIOM_GEMM_BLOCK_N 64

AXIOM_RUNTIME_FN void axiom_gemm_scalar_tiled(const double* A, const double* B, double* C, int M, int K, int N) {
    for (int i0 = 0; i0 < M; i0 += AXIOM_GEMM_BLOCK_M) {
        int imax = (i0 + AXIOM_GEMM_BLOCK_M < M) ? (i0 + AXIOM_GEMM_BLOCK_M) : M;
        for (int k0 = 0; k0 < K; k0 += AXIOM_GEMM_BLOCK_K) {
            int kmax = (k0 + AXIOM_GEMM_BLOCK_K < K) ? (k0 + AXIOM_GEMM_BLOCK_K) : K;
            for (int j0 = 0; j0 < N; j0 += AXIOM_GEMM_BLOCK_N) {
                int jmax = (j0 + AXIOM_GEMM_BLOCK_N < N) ? (j0 + AXIOM_GEMM_BLOCK_N) : N;

                for (int i = i0; i < imax; i++) {
                    for (int k = k0; k < kmax; k++) {
                        double a_ik = A[i * K + k];
                        for (int j = j0; j < jmax; j++) {
                            C[i * N + j] += a_ik * B[k * N + j];
                        }
                    }
                }
            }
        }
    }
}

#if defined(__x86_64__) || defined(_M_X64) || defined(__i386__) || defined(_M_IX86)
__attribute__((target("avx2,fma")))
AXIOM_RUNTIME_FN void axiom_gemm_avx2_fma_tiled(const double* A, const double* B, double* C, int M, int K, int N) {
    for (int i0 = 0; i0 < M; i0 += AXIOM_GEMM_BLOCK_M) {
        int imax = (i0 + AXIOM_GEMM_BLOCK_M < M) ? (i0 + AXIOM_GEMM_BLOCK_M) : M;
        for (int k0 = 0; k0 < K; k0 += AXIOM_GEMM_BLOCK_K) {
            int kmax = (k0 + AXIOM_GEMM_BLOCK_K < K) ? (k0 + AXIOM_GEMM_BLOCK_K) : K;
            for (int j0 = 0; j0 < N; j0 += AXIOM_GEMM_BLOCK_N) {
                int jmax = (j0 + AXIOM_GEMM_BLOCK_N < N) ? (j0 + AXIOM_GEMM_BLOCK_N) : N;

                for (int i = i0; i < imax; i++) {
                    for (int k = k0; k < kmax; k++) {
                        double a_ik = A[i * K + k];
                        __m256d va = _mm256_set1_pd(a_ik);
                        int j = j0;

                        /* 16 double (4x 256-bit YMM register) unrolled loop */
                        for (; j + 15 < jmax; j += 16) {
                            __m256d vb0 = _mm256_loadu_pd(&B[k * N + j]);
                            __m256d vb1 = _mm256_loadu_pd(&B[k * N + j + 4]);
                            __m256d vb2 = _mm256_loadu_pd(&B[k * N + j + 8]);
                            __m256d vb3 = _mm256_loadu_pd(&B[k * N + j + 12]);

                            __m256d vc0 = _mm256_loadu_pd(&C[i * N + j]);
                            __m256d vc1 = _mm256_loadu_pd(&C[i * N + j + 4]);
                            __m256d vc2 = _mm256_loadu_pd(&C[i * N + j + 8]);
                            __m256d vc3 = _mm256_loadu_pd(&C[i * N + j + 12]);

                            vc0 = _mm256_fmadd_pd(va, vb0, vc0);
                            vc1 = _mm256_fmadd_pd(va, vb1, vc1);
                            vc2 = _mm256_fmadd_pd(va, vb2, vc2);
                            vc3 = _mm256_fmadd_pd(va, vb3, vc3);

                            _mm256_storeu_pd(&C[i * N + j], vc0);
                            _mm256_storeu_pd(&C[i * N + j + 4], vc1);
                            _mm256_storeu_pd(&C[i * N + j + 8], vc2);
                            _mm256_storeu_pd(&C[i * N + j + 12], vc3);
                        }

                        /* 4 double (1x 256-bit YMM register) step */
                        for (; j + 3 < jmax; j += 4) {
                            __m256d vb = _mm256_loadu_pd(&B[k * N + j]);
                            __m256d vc = _mm256_loadu_pd(&C[i * N + j]);
                            vc = _mm256_fmadd_pd(va, vb, vc);
                            _mm256_storeu_pd(&C[i * N + j], vc);
                        }

                        /* Scalar tail */
                        for (; j < jmax; j++) {
                            C[i * N + j] += a_ik * B[k * N + j];
                        }
                    }
                }
            }
        }
    }
}
#endif

AXIOM_RUNTIME_FN ax_bool axiom_simd_avx2_supported(void) {
    return (ax_bool)(axiom_cpu_has_avx2() != 0);
}

AXIOM_RUNTIME_FN ax_int axiom_tensor_matmul(ax_int h1, ax_int h2) {
    if (h1 <= 0 || h1 >= AXIOM_MAX_TENSORS || !g_tensors[h1]) return -1;
    if (h2 <= 0 || h2 >= AXIOM_MAX_TENSORS || !g_tensors[h2]) return -1;
    AxiomTensor* A = g_tensors[h1];
    AxiomTensor* B = g_tensors[h2];
    if (A->cols != B->rows) return -2; /* Boyut uyumsuzluğu */

    ax_int h_out = axiom_tensor_create_2d(A->rows, B->cols);
    if (h_out <= 0) return -1;
    AxiomTensor* C = g_tensors[h_out];

    int M = A->rows;
    int K = A->cols;
    int N = B->cols;

#if defined(__x86_64__) || defined(_M_X64) || defined(__i386__) || defined(_M_IX86)
    if (axiom_cpu_has_avx2()) {
        axiom_gemm_avx2_fma_tiled(A->data, B->data, C->data, M, K, N);
        return h_out;
    }
#endif

    axiom_gemm_scalar_tiled(A->data, B->data, C->data, M, K, N);
    return h_out;
}

AXIOM_RUNTIME_FN ax_int axiom_tensor_add(ax_int h1, ax_int h2) {
    if (h1 <= 0 || h1 >= AXIOM_MAX_TENSORS || !g_tensors[h1]) return -1;
    if (h2 <= 0 || h2 >= AXIOM_MAX_TENSORS || !g_tensors[h2]) return -1;
    AxiomTensor* A = g_tensors[h1];
    AxiomTensor* B = g_tensors[h2];
    if (A->rows != B->rows || A->cols != B->cols) return -2;

    ax_int h_out = axiom_tensor_create_2d(A->rows, A->cols);
    AxiomTensor* C = g_tensors[h_out];
    for (int i = 0; i < A->size; i++) {
        C->data[i] = A->data[i] + B->data[i];
    }
    return h_out;
}

AXIOM_RUNTIME_FN ax_int axiom_tensor_transpose(ax_int h) {
    if (h <= 0 || h >= AXIOM_MAX_TENSORS || !g_tensors[h]) return -1;
    AxiomTensor* A = g_tensors[h];
    ax_int h_out = axiom_tensor_create_2d(A->cols, A->rows);
    AxiomTensor* T = g_tensors[h_out];
    for (int r = 0; r < A->rows; r++) {
        for (int c = 0; c < A->cols; c++) {
            T->data[c * T->cols + r] = A->data[r * A->cols + c];
        }
    }
    return h_out;
}

AXIOM_RUNTIME_FN ax_str axiom_tensor_to_str(ax_int h) {
    if (h <= 0 || h >= AXIOM_MAX_TENSORS || !g_tensors[h]) return axiom_owned_str_wrap("Tensor(None");
    AxiomTensor* t = g_tensors[h];
    char* buf = (char*)malloc(t->size * 32 + 64);
    sprintf(buf, "Tensor(shape=[%d, %d]):\n", t->rows, t->cols);
    for (int r = 0; r < t->rows; r++) {
        strcat(buf, "  [");
        for (int c = 0; c < t->cols; c++) {
            char num[32];
            sprintf(num, "%.4g%s", t->data[r * t->cols + c], (c < t->cols - 1) ? ", " : "");
            strcat(buf, num);
        }
        strcat(buf, "]\n");
    }
    return axiom_owned_str_wrap(buf);
}

AXIOM_RUNTIME_FN void axiom_tensor_free(ax_int h) {
    if (h <= 0 || h >= AXIOM_MAX_TENSORS || !g_tensors[h]) return;
    AxiomTensor* t = g_tensors[h];
    g_tensors[h] = NULL;
    axiom_safe_free(t->data);
    axiom_safe_free(t);
}

/* AI Aktivasyon ve Katman Fonksiyonları */
AXIOM_RUNTIME_FN ax_float axiom_nn_relu(ax_float x) {
    return (x > 0.0) ? x : 0.0;
}

AXIOM_RUNTIME_FN ax_float axiom_nn_sigmoid(ax_float x) {
    return (ax_float)(1.0 / (1.0 + exp(-((double)x))));
}

AXIOM_RUNTIME_FN ax_int axiom_nn_argmax(ax_int h) {
    if (h <= 0 || h >= AXIOM_MAX_TENSORS || !g_tensors[h]) return -1;
    AxiomTensor* t = g_tensors[h];
    if (t->size == 0) return -1;
    int max_idx = 0;
    double max_val = t->data[0];
    for (int i = 1; i < t->size; i++) {
        if (t->data[i] > max_val) {
            max_val = t->data[i];
            max_idx = i;
        }
    }
    return (ax_int)max_idx;
}

AXIOM_RUNTIME_FN ax_float axiom_dot_product(ax_int h1, ax_int h2) {
    if (h1 <= 0 || h1 >= AXIOM_MAX_TENSORS || !g_tensors[h1]) return 0.0;
    if (h2 <= 0 || h2 >= AXIOM_MAX_TENSORS || !g_tensors[h2]) return 0.0;
    AxiomTensor* A = g_tensors[h1];
    AxiomTensor* B = g_tensors[h2];
    int len = (A->size < B->size) ? A->size : B->size;
    double sum = 0.0;
    for (int i = 0; i < len; i++) {
        sum += A->data[i] * B->data[i];
    }
    return (ax_float)sum;
}

/* ========================================================================= */
/* FAZ 4.2: Linux Epoll Tabanli Asenkron Ag Reaktoru (Async Reactor)        */
/* ========================================================================= */

#define AXIOM_MAX_EPOLL_INSTANCES 128
#define AXIOM_DEFAULT_EPOLL_EVENTS 1024

typedef struct {
    int epfd;
    int max_events;
    int ready_count;
#if defined(__linux__)
    struct epoll_event* events;
#else
    void* events;
#endif
    bool active;
} AxiomEpollInstance;

static AxiomEpollInstance g_epoll_instances[AXIOM_MAX_EPOLL_INSTANCES];
static ax_mutex_t g_epoll_mutex = AX_MUTEX_STATIC_INIT;

AXIOM_RUNTIME_FN AxiomEpollInstance* axiom_find_epoll(int epfd) {
    if (epfd < 0) return NULL;
    for (int i = 0; i < AXIOM_MAX_EPOLL_INSTANCES; i++) {
        if (g_epoll_instances[i].active && g_epoll_instances[i].epfd == epfd) {
            return &g_epoll_instances[i];
        }
    }
    return NULL;
}

AXIOM_RUNTIME_FN ax_int axiom_epoll_create(ax_int max_events) {
#if defined(__linux__)
    if (max_events <= 0) max_events = AXIOM_DEFAULT_EPOLL_EVENTS;
    int epfd = epoll_create1(EPOLL_CLOEXEC);
    if (epfd < 0) return -1;

    ax_os_mutex_lock(&g_epoll_mutex);
    int slot = -1;
    for (int i = 0; i < AXIOM_MAX_EPOLL_INSTANCES; i++) {
        if (!g_epoll_instances[i].active) {
            slot = i;
            break;
        }
    }
    if (slot == -1) {
        ax_os_mutex_unlock(&g_epoll_mutex);
        close(epfd);
        return -1;
    }

    struct epoll_event* evs = (struct epoll_event*)calloc((size_t)max_events, sizeof(struct epoll_event));
    if (!evs) {
        ax_os_mutex_unlock(&g_epoll_mutex);
        close(epfd);
        return -1;
    }

    g_epoll_instances[slot].epfd = epfd;
    g_epoll_instances[slot].max_events = (int)max_events;
    g_epoll_instances[slot].ready_count = 0;
    g_epoll_instances[slot].events = evs;
    g_epoll_instances[slot].active = true;
    ax_os_mutex_unlock(&g_epoll_mutex);

    return (ax_int)epfd;
#else
    (void)max_events;
    return -1;
#endif
}

AXIOM_RUNTIME_FN ax_int axiom_epoll_add(ax_int epfd, ax_int fd, ax_int events) {
#if defined(__linux__)
    if (epfd < 0 || fd < 0) return -1;
    struct epoll_event ev;
    memset(&ev, 0, sizeof(ev));
    ev.events = (uint32_t)events;
    ev.data.fd = (int)fd;

    if (epoll_ctl((int)epfd, EPOLL_CTL_ADD, (int)fd, &ev) < 0) {
        if (errno == EEXIST) {
            if (epoll_ctl((int)epfd, EPOLL_CTL_MOD, (int)fd, &ev) < 0) {
                return -1;
            }
            return 0;
        }
        return -1;
    }
    return 0;
#else
    (void)epfd; (void)fd; (void)events;
    return -1;
#endif
}

AXIOM_RUNTIME_FN ax_int axiom_epoll_mod(ax_int epfd, ax_int fd, ax_int events) {
#if defined(__linux__)
    if (epfd < 0 || fd < 0) return -1;
    struct epoll_event ev;
    memset(&ev, 0, sizeof(ev));
    ev.events = (uint32_t)events;
    ev.data.fd = (int)fd;
    return (epoll_ctl((int)epfd, EPOLL_CTL_MOD, (int)fd, &ev) == 0) ? 0 : -1;
#else
    (void)epfd; (void)fd; (void)events;
    return -1;
#endif
}

AXIOM_RUNTIME_FN ax_int axiom_epoll_del(ax_int epfd, ax_int fd) {
#if defined(__linux__)
    if (epfd < 0 || fd < 0) return -1;
    return (epoll_ctl((int)epfd, EPOLL_CTL_DEL, (int)fd, NULL) == 0) ? 0 : -1;
#else
    (void)epfd; (void)fd;
    return -1;
#endif
}

AXIOM_RUNTIME_FN ax_int axiom_epoll_wait(ax_int epfd, ax_int timeout_ms) {
#if defined(__linux__)
    ax_os_mutex_lock(&g_epoll_mutex);
    AxiomEpollInstance* inst = axiom_find_epoll((int)epfd);
    if (!inst) {
        ax_os_mutex_unlock(&g_epoll_mutex);
        return -1;
    }
    int max_ev = inst->max_events;
    struct epoll_event* evs = inst->events;
    ax_os_mutex_unlock(&g_epoll_mutex);

    int n = epoll_wait((int)epfd, evs, max_ev, (int)timeout_ms);
    ax_os_mutex_lock(&g_epoll_mutex);
    inst = axiom_find_epoll((int)epfd);
    if (inst) {
        inst->ready_count = (n > 0) ? n : 0;
    }
    ax_os_mutex_unlock(&g_epoll_mutex);

    return (ax_int)n;
#else
    (void)epfd; (void)timeout_ms;
    return -1;
#endif
}

AXIOM_RUNTIME_FN ax_int axiom_epoll_event_fd(ax_int epfd, ax_int idx) {
#if defined(__linux__)
    ax_os_mutex_lock(&g_epoll_mutex);
    AxiomEpollInstance* inst = axiom_find_epoll((int)epfd);
    if (!inst || idx < 0 || idx >= inst->ready_count) {
        ax_os_mutex_unlock(&g_epoll_mutex);
        return -1;
    }
    ax_int fd = (ax_int)inst->events[idx].data.fd;
    ax_os_mutex_unlock(&g_epoll_mutex);
    return fd;
#else
    (void)epfd; (void)idx;
    return -1;
#endif
}

AXIOM_RUNTIME_FN ax_int axiom_epoll_event_events(ax_int epfd, ax_int idx) {
#if defined(__linux__)
    ax_os_mutex_lock(&g_epoll_mutex);
    AxiomEpollInstance* inst = axiom_find_epoll((int)epfd);
    if (!inst || idx < 0 || idx >= inst->ready_count) {
        ax_os_mutex_unlock(&g_epoll_mutex);
        return 0;
    }
    ax_int events = (ax_int)inst->events[idx].events;
    ax_os_mutex_unlock(&g_epoll_mutex);
    return events;
#else
    (void)epfd; (void)idx;
    return 0;
#endif
}

AXIOM_RUNTIME_FN void axiom_epoll_close(ax_int epfd) {
    if (epfd < 0) return;
    ax_os_mutex_lock(&g_epoll_mutex);
    for (int i = 0; i < AXIOM_MAX_EPOLL_INSTANCES; i++) {
        if (g_epoll_instances[i].active && g_epoll_instances[i].epfd == (int)epfd) {
            free(g_epoll_instances[i].events);
            g_epoll_instances[i].events = NULL;
            g_epoll_instances[i].active = false;
            g_epoll_instances[i].ready_count = 0;
            g_epoll_instances[i].epfd = -1;
            break;
        }
    }
    ax_os_mutex_unlock(&g_epoll_mutex);
    close((int)epfd);
}

AXIOM_RUNTIME_FN ax_int axiom_net_set_nonblocking(ax_int fd) {
    if (fd < 0) return -1;
    return ax_os_sock_set_nonblocking(ax_os_int_to_sock(fd), 1) == 0 ? 0 : -1;
}

AXIOM_RUNTIME_FN ax_int axiom_tcp_server_nonblocking(ax_int port) {
    if (port <= 0 || port > 65535) return -1;
    int fd = ax_os_socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return -1;

    ax_os_sock_set_reuse(ax_os_int_to_sock(fd));
    ax_os_sock_set_nonblocking(ax_os_int_to_sock(fd), 1);

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons((uint16_t)port);

    if (bind(fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(fd);
        return -1;
    }
    if (listen(fd, 1024) < 0) {
        close(fd);
        return -1;
    }
    return (ax_int)fd;
}

AXIOM_RUNTIME_FN ax_int axiom_tcp_accept_nonblocking(ax_int server_fd) {
    if (server_fd < 0) return -1;
    struct sockaddr_in client;
    socklen_t clen = sizeof(client);
#if defined(__linux__) && defined(SOCK_NONBLOCK)
    int client_fd = accept4((int)server_fd, (struct sockaddr*)&client, &clen, SOCK_NONBLOCK | SOCK_CLOEXEC);
#else
    int client_fd = accept((int)server_fd, (struct sockaddr*)&client, &clen);
    if (client_fd >= 0) {
        ax_os_sock_set_nonblocking(ax_os_int_to_sock(client_fd), 1);
    }
#endif
    if (client_fd < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) {
            return -2; /* EAGAIN: bekleyen baglanti yok */
        }
        return -1;
    }
    return (ax_int)client_fd;
}

AXIOM_RUNTIME_FN ax_int axiom_fd_write(ax_int fd, const char* data) {
    if (fd < 0 || !data) return -1;
    size_t len = strlen(data);
    long long written = ax_os_fd_write((long long)fd, data, len);
    return (ax_int)written;
}

AXIOM_RUNTIME_FN ax_str axiom_fd_read(ax_int fd, ax_int max_len) {
    if (fd < 0 || max_len <= 0) return axiom_owned_str_wrap("");
    char* buf = (char*)malloc((size_t)max_len + 1);
    if (!buf) return axiom_owned_str_wrap("");
    long long n = ax_os_fd_read((long long)fd, buf, (size_t)max_len);
    if (n <= 0) {
        free(buf);
        return axiom_owned_str_wrap("");
    }
    buf[n] = '\0';
    return axiom_owned_str_wrap(buf);
}

#define AXIOM_MAX_FD_PAIRS 64
typedef struct {
    int fd1;
    int fd2;
    bool active;
} AxiomFdPair;

static AxiomFdPair g_pipe_pairs[AXIOM_MAX_FD_PAIRS];
static AxiomFdPair g_socket_pairs[AXIOM_MAX_FD_PAIRS];
static ax_mutex_t g_pairs_mutex = AX_MUTEX_STATIC_INIT;

AXIOM_RUNTIME_FN ax_int axiom_pipe_create(void) {
    int fds[2];
    if (ax_os_pipe(fds) < 0) return -1;

    ax_os_sock_set_nonblocking(ax_os_int_to_sock(fds[0]), 1);
    ax_os_sock_set_nonblocking(ax_os_int_to_sock(fds[1]), 1);

    ax_os_mutex_lock(&g_pairs_mutex);
    int slot = -1;
    for (int i = 0; i < AXIOM_MAX_FD_PAIRS; i++) {
        if (!g_pipe_pairs[i].active) {
            slot = i;
            break;
        }
    }
    if (slot == -1) {
        ax_os_mutex_unlock(&g_pairs_mutex);
        close(fds[0]);
        close(fds[1]);
        return -1;
    }
    g_pipe_pairs[slot].fd1 = fds[0]; /* read fd */
    g_pipe_pairs[slot].fd2 = fds[1]; /* write fd */
    g_pipe_pairs[slot].active = true;
    ax_os_mutex_unlock(&g_pairs_mutex);
    return (ax_int)slot;
}

AXIOM_RUNTIME_FN ax_int axiom_pipe_read_fd(ax_int handle) {
    if (handle < 0 || handle >= AXIOM_MAX_FD_PAIRS) return -1;
    ax_os_mutex_lock(&g_pairs_mutex);
    ax_int fd = g_pipe_pairs[handle].active ? (ax_int)g_pipe_pairs[handle].fd1 : -1;
    ax_os_mutex_unlock(&g_pairs_mutex);
    return fd;
}

AXIOM_RUNTIME_FN ax_int axiom_pipe_write_fd(ax_int handle) {
    if (handle < 0 || handle >= AXIOM_MAX_FD_PAIRS) return -1;
    ax_os_mutex_lock(&g_pairs_mutex);
    ax_int fd = g_pipe_pairs[handle].active ? (ax_int)g_pipe_pairs[handle].fd2 : -1;
    ax_os_mutex_unlock(&g_pairs_mutex);
    return fd;
}

AXIOM_RUNTIME_FN void axiom_pipe_close(ax_int handle) {
    if (handle < 0 || handle >= AXIOM_MAX_FD_PAIRS) return;
    ax_os_mutex_lock(&g_pairs_mutex);
    if (g_pipe_pairs[handle].active) {
        close(g_pipe_pairs[handle].fd1);
        close(g_pipe_pairs[handle].fd2);
        g_pipe_pairs[handle].active = false;
    }
    ax_os_mutex_unlock(&g_pairs_mutex);
}

AXIOM_RUNTIME_FN ax_int axiom_socketpair_create(void) {
    int sv[2];
    if (ax_os_socketpair(sv) < 0) return -1;

    ax_os_sock_set_nonblocking(ax_os_int_to_sock(sv[0]), 1);
    ax_os_sock_set_nonblocking(ax_os_int_to_sock(sv[1]), 1);

    ax_os_mutex_lock(&g_pairs_mutex);
    int slot = -1;
    for (int i = 0; i < AXIOM_MAX_FD_PAIRS; i++) {
        if (!g_socket_pairs[i].active) {
            slot = i;
            break;
        }
    }
    if (slot == -1) {
        ax_os_mutex_unlock(&g_pairs_mutex);
        close(sv[0]);
        close(sv[1]);
        return -1;
    }
    g_socket_pairs[slot].fd1 = sv[0];
    g_socket_pairs[slot].fd2 = sv[1];
    g_socket_pairs[slot].active = true;
    ax_os_mutex_unlock(&g_pairs_mutex);
    return (ax_int)slot;
}

AXIOM_RUNTIME_FN ax_int axiom_socketpair_fd1(ax_int handle) {
    if (handle < 0 || handle >= AXIOM_MAX_FD_PAIRS) return -1;
    ax_os_mutex_lock(&g_pairs_mutex);
    ax_int fd = g_socket_pairs[handle].active ? (ax_int)g_socket_pairs[handle].fd1 : -1;
    ax_os_mutex_unlock(&g_pairs_mutex);
    return fd;
}

AXIOM_RUNTIME_FN ax_int axiom_socketpair_fd2(ax_int handle) {
    if (handle < 0 || handle >= AXIOM_MAX_FD_PAIRS) return -1;
    ax_os_mutex_lock(&g_pairs_mutex);
    ax_int fd = g_socket_pairs[handle].active ? (ax_int)g_socket_pairs[handle].fd2 : -1;
    ax_os_mutex_unlock(&g_pairs_mutex);
    return fd;
}

AXIOM_RUNTIME_FN void axiom_socketpair_close(ax_int handle) {
    if (handle < 0 || handle >= AXIOM_MAX_FD_PAIRS) return;
    ax_os_mutex_lock(&g_pairs_mutex);
    if (g_socket_pairs[handle].active) {
        close(g_socket_pairs[handle].fd1);
        close(g_socket_pairs[handle].fd2);
        g_socket_pairs[handle].active = false;
    }
    ax_os_mutex_unlock(&g_pairs_mutex);
}

AXIOM_RUNTIME_FN ax_bool axiom_epoll_is_readable(ax_int events) {
#if defined(__linux__)
    return (events & (EPOLLIN | EPOLLPRI)) != 0;
#else
    return (events & 1) != 0;
#endif
}

AXIOM_RUNTIME_FN ax_bool axiom_epoll_is_writable(ax_int events) {
#if defined(__linux__)
    return (events & EPOLLOUT) != 0;
#else
    return (events & 4) != 0;
#endif
}

AXIOM_RUNTIME_FN ax_bool axiom_epoll_is_error(ax_int events) {
#if defined(__linux__)
    return (events & EPOLLERR) != 0;
#else
    return (events & 8) != 0;
#endif
}

AXIOM_RUNTIME_FN ax_bool axiom_epoll_is_hangup(ax_int events) {
#if defined(__linux__)
    return (events & (EPOLLHUP | EPOLLRDHUP)) != 0;
#else
    return (events & 16) != 0;
#endif
}

/* -------------------------------------------------------------------------
 * 23. std:security:yara - Real YARA Byte & Wildcard Mask Pattern Engine
 * (Boyer-Moore-Horspool / Sunday Quick-Search with Wildcard Masks)
 * ------------------------------------------------------------------------- */

typedef struct {
    uint8_t* vals;
    uint8_t* masks;
    int len;
} AxiomYaraCompiledPattern;

// Bound direct runtime pattern inputs before allocating or scanning them.
#define AXIOM_YARA_MAX_HEX_PATTERN_TEXT 8192u

AXIOM_RUNTIME_FN void axiom_yara_pattern_free(AxiomYaraCompiledPattern* pat) {
    if (pat) {
        if (pat->vals) { free(pat->vals); pat->vals = NULL; }
        if (pat->masks) { free(pat->masks); pat->masks = NULL; }
        pat->len = 0;
    }
}

AXIOM_RUNTIME_FN int axiom_yara_parse_hex_pattern_internal(const char* pattern_str, AxiomYaraCompiledPattern* pat) {
    if (!pat) return 0;
    pat->vals = NULL;
    pat->masks = NULL;
    pat->len = 0;
    if (!pattern_str) return 0;
    size_t s_len = strlen(pattern_str);
    if (s_len == 0 || s_len > AXIOM_YARA_MAX_HEX_PATTERN_TEXT) return 0;
    pat->vals = (uint8_t*)malloc(s_len + 1);
    pat->masks = (uint8_t*)malloc(s_len + 1);
    if (!pat->vals || !pat->masks) {
        if (pat->vals) free(pat->vals);
        if (pat->masks) free(pat->masks);
        pat->vals = NULL;
        pat->masks = NULL;
        return 0;
    }

    const char* begin = pattern_str;
    const char* end = pattern_str + s_len;
    while (begin < end && isspace((unsigned char)*begin)) begin++;
    while (end > begin && isspace((unsigned char)end[-1])) end--;
    if (begin == end) goto invalid_pattern;

    // Braces are accepted only as one balanced outer pair, as used by YARA
    // hex strings. Every other non-token character is rejected below.
    if (*begin == '{') {
        begin++;
        if (end <= begin || end[-1] != '}') goto invalid_pattern;
        end--;
    }

    const char* p = begin;
    while (p < end) {
        if (isspace((unsigned char)*p)) {
            p++;
            continue;
        }
        if ((size_t)(end - p) < 2) goto invalid_pattern;

        char c1 = *p;
        char c2 = p[1];
        if (c1 == '?') {
            if (c2 == '?') {
                pat->vals[pat->len] = 0x00;
                pat->masks[pat->len] = 0x00;
            } else if (isxdigit((unsigned char)c2)) {
                int low = isdigit((unsigned char)c2) ? (c2 - '0') : (tolower((unsigned char)c2) - 'a' + 10);
                pat->vals[pat->len] = (uint8_t)(low & 0x0F);
                pat->masks[pat->len] = 0x0F;
            } else {
                goto invalid_pattern;
            }
        } else if (isxdigit((unsigned char)c1)) {
            int high = isdigit((unsigned char)c1) ? (c1 - '0') : (tolower((unsigned char)c1) - 'a' + 10);
            if (c2 == '?') {
                pat->vals[pat->len] = (uint8_t)((high << 4) & 0xF0);
                pat->masks[pat->len] = 0xF0;
            } else if (isxdigit((unsigned char)c2)) {
                int low = isdigit((unsigned char)c2) ? (c2 - '0') : (tolower((unsigned char)c2) - 'a' + 10);
                pat->vals[pat->len] = (uint8_t)(((high << 4) | low) & 0xFF);
                pat->masks[pat->len] = 0xFF;
            } else {
                // A byte must be exactly two adjacent hex/wildcard nibbles.
                goto invalid_pattern;
            }
        } else {
            goto invalid_pattern;
        }
        pat->len++;
        p += 2;
    }
    if (pat->len == 0) goto invalid_pattern;
    return pat->len;

invalid_pattern:
    if (pat->vals) free(pat->vals);
    if (pat->masks) free(pat->masks);
    pat->vals = NULL;
    pat->masks = NULL;
    pat->len = 0;
    return 0;
}

AXIOM_RUNTIME_FN ax_int axiom_yara_pattern_len(const char* hex_pattern) {
    if (!hex_pattern) return 0;
    AxiomYaraCompiledPattern pat;
    int len = axiom_yara_parse_hex_pattern_internal(hex_pattern, &pat);
    axiom_yara_pattern_free(&pat);
    return (ax_int)len;
}

/* Wildcard-aware search; occurrence 0 counts all hits, 1-based values select a hit. */
AXIOM_RUNTIME_FN ax_int axiom_yara_scan_bytes(const uint8_t* data, size_t data_len,
                                               const AxiomYaraCompiledPattern* pat,
                                               ax_int min_offset, ax_int max_offset,
                                               ax_int occurrence, ax_int* count_out) {
    if (count_out) *count_out = 0;
    if (!data || !pat || pat->len <= 0 || occurrence < 0) return -1;
    if (data_len > (size_t)INT64_MAX) return -1;
    int m = pat->len;
    if ((size_t)m > data_len) return -1;

    int64_t last_start = (int64_t)data_len - (int64_t)m;
    int64_t start = (min_offset >= 0) ? min_offset : 0;
    int64_t end = last_start;
    if (max_offset >= 0 && max_offset < end) end = max_offset;
    if (start > last_start || start > end) return -1;

    // Fast-path for exact offset check
    if (min_offset >= 0 && min_offset == max_offset) {
        if (min_offset > last_start) return -1;
        for (int j = 0; j < m; j++) {
            if ((data[min_offset + j] & pat->masks[j]) != pat->vals[j]) {
                return -1;
            }
        }
        if (count_out) *count_out = 1;
        return occurrence == 0 || occurrence == 1 ? min_offset : -1;
    }

    // Build Sunday Quick-Search shift table with wildcard mask awareness
    int shift[256];
    for (int c = 0; c < 256; c++) {
        shift[c] = m + 1;
    }
    for (int j = 0; j < m; j++) {
        uint8_t mask = pat->masks[j];
        uint8_t val = pat->vals[j];
        int dist = m - j;
        if (mask == 0xFF) {
            shift[val] = dist;
        } else {
            for (int c = 0; c < 256; c++) {
                if ((c & mask) == val) {
                    if (dist < shift[c]) shift[c] = dist;
                }
            }
        }
    }

    // Search window loop
    int64_t i = start;
    ax_int seen = 0;
    while (i <= end) {
        int match = 1;
        for (int j = 0; j < m; j++) {
            if ((data[i + j] & pat->masks[j]) != pat->vals[j]) {
                match = 0;
                break;
            }
        }
        if (match) {
            seen++;
            if (count_out) *count_out = seen;
            if (occurrence > 0 && seen == occurrence) return (ax_int)i;
            i++;
            continue;
        }

        if (i + m < (int64_t)data_len) {
            uint8_t next_c = data[i + m];
            int s = shift[next_c];
            if (s < 1) s = 1;
            i += s;
        } else {
            break;
        }
    }

    return -1;
}

AXIOM_RUNTIME_FN ax_int axiom_yara_find_nth_bytes(const uint8_t* data, size_t data_len,
                                                   const AxiomYaraCompiledPattern* pat,
                                                   ax_int min_offset, ax_int max_offset,
                                                   ax_int occurrence) {
    if (occurrence <= 0) return -1;
    return axiom_yara_scan_bytes(data, data_len, pat, min_offset, max_offset, occurrence, NULL);
}

AXIOM_RUNTIME_FN ax_int axiom_yara_count_bytes(const uint8_t* data, size_t data_len,
                                                const AxiomYaraCompiledPattern* pat) {
    ax_int count = 0;
    axiom_yara_scan_bytes(data, data_len, pat, -1, -1, 0, &count);
    return count;
}

AXIOM_RUNTIME_FN ax_int axiom_yara_find_bytes(const uint8_t* data, size_t data_len,
                                               const AxiomYaraCompiledPattern* pat,
                                               ax_int min_offset, ax_int max_offset) {
    return axiom_yara_find_nth_bytes(data, data_len, pat, min_offset, max_offset, 1);
}

AXIOM_RUNTIME_FN ax_int axiom_yara_find_hex_wildcard_raw(const char* target, ax_int target_len, const char* hex_pattern, ax_int min_offset, ax_int max_offset) {
    if (!target || !hex_pattern) return -1;
    size_t dlen = (target_len >= 0) ? (size_t)target_len : strlen(target);
    AxiomYaraCompiledPattern pat;
    if (axiom_yara_parse_hex_pattern_internal(hex_pattern, &pat) <= 0) {
        axiom_yara_pattern_free(&pat);
        return -1;
    }
    ax_int res = axiom_yara_find_bytes((const uint8_t*)target, dlen, &pat, min_offset, max_offset);
    axiom_yara_pattern_free(&pat);
    return res;
}

AXIOM_RUNTIME_FN ax_int axiom_yara_find_hex_wildcard(const char* target, const char* hex_pattern, ax_int min_offset, ax_int max_offset) {
    return axiom_yara_find_hex_wildcard_raw(target, -1, hex_pattern, min_offset, max_offset);
}

AXIOM_RUNTIME_FN ax_int axiom_yara_nth_hex_wildcard(const char* target, const char* hex_pattern, ax_int occurrence) {
    if (!target || !hex_pattern || occurrence <= 0) return -1;
    AxiomYaraCompiledPattern pat;
    if (axiom_yara_parse_hex_pattern_internal(hex_pattern, &pat) <= 0) {
        axiom_yara_pattern_free(&pat);
        return -1;
    }
    ax_int res = axiom_yara_find_nth_bytes((const uint8_t*)target, strlen(target), &pat, -1, -1, occurrence);
    axiom_yara_pattern_free(&pat);
    return res;
}

AXIOM_RUNTIME_FN ax_int axiom_yara_count_hex_wildcard(const char* target, const char* hex_pattern) {
    if (!target || !hex_pattern) return 0;
    AxiomYaraCompiledPattern pat;
    if (axiom_yara_parse_hex_pattern_internal(hex_pattern, &pat) <= 0) {
        axiom_yara_pattern_free(&pat);
        return 0;
    }
    ax_int count = axiom_yara_count_bytes((const uint8_t*)target, strlen(target), &pat);
    axiom_yara_pattern_free(&pat);
    return count;
}

AXIOM_RUNTIME_FN ax_int axiom_yara_find_hex_stream(const char* hex_target, const char* hex_pattern) {
    if (!hex_target || !hex_pattern) return -1;
    size_t slen = strlen(hex_target);
    if (slen == 0) return -1;
    uint8_t* raw = (uint8_t*)malloc(slen / 2 + 1);
    if (!raw) return -1;
    size_t raw_len = 0;
    const char* p = hex_target;
    while (*p) {
        while (*p && isspace((unsigned char)*p)) p++;
        if (!*p) break;
        if (!isxdigit((unsigned char)*p) || !p[1] || !isxdigit((unsigned char)p[1])) {
            free(raw);
            return -1;
        }
        char c1 = *p++;
        char c2 = *p++;
        int hi = isdigit((unsigned char)c1) ? (c1 - '0') : (tolower((unsigned char)c1) - 'a' + 10);
        int lo = isdigit((unsigned char)c2) ? (c2 - '0') : (tolower((unsigned char)c2) - 'a' + 10);
        raw[raw_len++] = (uint8_t)((hi << 4) | lo);
    }
    if (raw_len == 0) {
        free(raw);
        return -1;
    }

    AxiomYaraCompiledPattern pat;
    if (axiom_yara_parse_hex_pattern_internal(hex_pattern, &pat) <= 0) {
        free(raw);
        axiom_yara_pattern_free(&pat);
        return -1;
    }

    ax_int res = axiom_yara_find_bytes(raw, raw_len, &pat, -1, -1);
    free(raw);
    axiom_yara_pattern_free(&pat);
    return res;
}

typedef struct {
    AxiomYaraCompiledPattern prefix;
    AxiomYaraCompiledPattern suffix;
    int min_gap;
    int max_gap;
    int suffix_anchor;
    size_t suffix_anchor_matches;
    uint8_t* suffix_anchor_bits;
    size_t suffix_anchor_bits_len;
} AxiomYaraHexRangePattern;

AXIOM_RUNTIME_FN void axiom_yara_hex_range_free(AxiomYaraHexRangePattern* range) {
    if (!range) return;
    axiom_yara_pattern_free(&range->prefix);
    axiom_yara_pattern_free(&range->suffix);
    range->min_gap = 0;
    range->max_gap = 0;
    range->suffix_anchor = -1;
    range->suffix_anchor_matches = 0;
    if (range->suffix_anchor_bits) free(range->suffix_anchor_bits);
    range->suffix_anchor_bits = NULL;
    range->suffix_anchor_bits_len = 0;
}

AXIOM_RUNTIME_FN int axiom_yara_hex_range_anchor_in_window(const AxiomYaraHexRangePattern* range,
                                                            size_t first, size_t last) {
    if (!range || !range->suffix_anchor_bits || first > last || last / 8 >= range->suffix_anchor_bits_len) return 1;
    size_t first_byte = first / 8;
    size_t last_byte = last / 8;
    for (size_t byte = first_byte; byte <= last_byte; byte++) {
        unsigned int low = byte == first_byte ? (unsigned int)(first & 7) : 0;
        unsigned int high = byte == last_byte ? (unsigned int)(last & 7) : 7;
        uint8_t mask = (uint8_t)(0xFFu << low);
        mask = (uint8_t)(mask & (uint8_t)(0xFFu >> (7u - high)));
        if ((range->suffix_anchor_bits[byte] & mask) != 0) return 1;
    }
    return 0;
}

AXIOM_RUNTIME_FN int axiom_yara_hex_range_choose_anchor(const uint8_t* target, size_t target_len,
                                                         AxiomYaraHexRangePattern* range) {
    if (!target || !range || range->suffix.len <= 0) return -1;
    size_t frequencies[256] = {0};
    for (size_t i = 0; i < target_len; i++) frequencies[target[i]]++;
    size_t least_matches = SIZE_MAX;
    int anchor = -1;
    for (int i = 0; i < range->suffix.len; i++) {
        uint8_t mask = range->suffix.masks[i];
        if (mask == 0) continue;
        size_t matches = 0;
        for (int byte = 0; byte < 256; byte++) {
            if (((uint8_t)byte & mask) == range->suffix.vals[i]) matches += frequencies[byte];
        }
        if (matches < least_matches) {
            least_matches = matches;
            anchor = i;
            if (matches == 0) break;
        }
    }
    range->suffix_anchor_matches = least_matches;
    if (anchor >= 0) {
        size_t bits_len = target_len / 8 + (target_len % 8 != 0);
        range->suffix_anchor_bits = (uint8_t*)calloc(bits_len, sizeof(uint8_t));
        if (range->suffix_anchor_bits) {
            range->suffix_anchor_bits_len = bits_len;
            uint8_t mask = range->suffix.masks[anchor];
            uint8_t value = range->suffix.vals[anchor];
            for (size_t i = 0; i < target_len; i++) {
                if ((target[i] & mask) == value) range->suffix_anchor_bits[i / 8] |= (uint8_t)(1u << (i & 7));
            }
        }
    }
    return anchor;
}

AXIOM_RUNTIME_FN int axiom_yara_parse_jump_bound(const char* value, size_t value_len, int* out) {
    if (!value || !out || value_len == 0) return 0;
    int parsed = 0;
    for (size_t i = 0; i < value_len; i++) {
        unsigned char ch = (unsigned char)value[i];
        if (ch < '0' || ch > '9') return 0;
        parsed = parsed * 10 + (ch - '0');
        if (parsed > 64) return 0;
    }
    *out = parsed;
    return 1;
}

// Internal encoding: hexrange:<prefix>|<min-gap>|<max-gap>|<suffix>
AXIOM_RUNTIME_FN int axiom_yara_parse_hex_range_internal(const char* encoded, AxiomYaraHexRangePattern* range) {
    if (!range) return 0;
    range->prefix = (AxiomYaraCompiledPattern){NULL, NULL, 0};
    range->suffix = (AxiomYaraCompiledPattern){NULL, NULL, 0};
    range->min_gap = 0;
    range->max_gap = 0;
    range->suffix_anchor = -1;
    range->suffix_anchor_matches = 0;
    range->suffix_anchor_bits = NULL;
    range->suffix_anchor_bits_len = 0;
    if (!encoded) return 0;

    size_t encoded_len = strlen(encoded);
    static const char prefix_tag[] = "hexrange:";
    const size_t tag_len = sizeof(prefix_tag) - 1;
    if (encoded_len <= tag_len || encoded_len > AXIOM_YARA_MAX_HEX_PATTERN_TEXT ||
        memcmp(encoded, prefix_tag, tag_len) != 0) return 0;

    const char* fields[4] = {0};
    size_t field_lens[4] = {0};
    size_t field_index = 0;
    const char* field_start = encoded + tag_len;
    for (const char* p = field_start; ; p++) {
        if (*p == '|' || *p == '\0') {
            if (field_index >= 4) return 0;
            fields[field_index] = field_start;
            field_lens[field_index] = (size_t)(p - field_start);
            field_index++;
            if (*p == '\0') break;
            field_start = p + 1;
        }
    }
    if (field_index != 4 || field_lens[0] == 0 || field_lens[3] == 0) return 0;
    if (!axiom_yara_parse_jump_bound(fields[1], field_lens[1], &range->min_gap) ||
        !axiom_yara_parse_jump_bound(fields[2], field_lens[2], &range->max_gap)) goto invalid_range;
    if (range->min_gap > range->max_gap || range->max_gap > 64 ||
        range->max_gap - range->min_gap > 16) goto invalid_range;

    char* prefix_text = (char*)malloc(field_lens[0] + 1);
    char* suffix_text = (char*)malloc(field_lens[3] + 1);
    if (!prefix_text || !suffix_text) {
        if (prefix_text) free(prefix_text);
        if (suffix_text) free(suffix_text);
        goto invalid_range;
    }
    memcpy(prefix_text, fields[0], field_lens[0]);
    prefix_text[field_lens[0]] = '\0';
    memcpy(suffix_text, fields[3], field_lens[3]);
    suffix_text[field_lens[3]] = '\0';

    int prefix_len = axiom_yara_parse_hex_pattern_internal(prefix_text, &range->prefix);
    int suffix_len = axiom_yara_parse_hex_pattern_internal(suffix_text, &range->suffix);
    free(prefix_text);
    free(suffix_text);
    if (prefix_len <= 0 || suffix_len <= 0) goto invalid_range;
    return 1;

invalid_range:
    axiom_yara_hex_range_free(range);
    return 0;
}

AXIOM_RUNTIME_FN int axiom_yara_hex_range_match_at(const uint8_t* target, size_t target_len,
                                                    const AxiomYaraHexRangePattern* range,
                                                    int64_t start, int* match_len_out);

// Returns the lowest matching start offset. For the same start, the smallest
// matching jump is tested first, so the selected match has the shortest length.
AXIOM_RUNTIME_FN ax_int axiom_yara_find_hex_pattern(const char* target, const char* pattern,
                                                     ax_int min_offset, ax_int max_offset);
AXIOM_RUNTIME_FN ax_int axiom_yara_hex_pattern_length_at(const char* target, const char* pattern,
                                                          ax_int offset);

AXIOM_RUNTIME_FN ax_int axiom_yara_find_hex_range(const char* target, const char* encoded,
                                                   ax_int min_offset, ax_int max_offset) {
    return axiom_yara_find_hex_pattern(target, encoded, min_offset, max_offset);
}

// Returns the shortest matching total length at exactly exact_offset, or -1.
AXIOM_RUNTIME_FN ax_int axiom_yara_find_hex_range_length(const char* target, const char* encoded,
                                                         ax_int exact_offset) {
    return axiom_yara_hex_pattern_length_at(target, encoded, exact_offset);
}

typedef struct {
    AxiomYaraCompiledPattern prefix;
    AxiomYaraCompiledPattern suffix;
    uint8_t excluded_mask;
    uint8_t excluded_value;
} AxiomYaraHexNegation;

AXIOM_RUNTIME_FN void axiom_yara_hex_negation_free(AxiomYaraHexNegation* negation) {
    if (!negation) return;
    axiom_yara_pattern_free(&negation->prefix);
    axiom_yara_pattern_free(&negation->suffix);
    negation->excluded_mask = 0;
    negation->excluded_value = 0;
}

AXIOM_RUNTIME_FN int axiom_yara_negated_hex_nibble(char ch, uint8_t* mask, uint8_t* value,
                                                    uint8_t nibble_mask, unsigned int shift) {
    if (ch == '?') {
        *mask = 0;
        *value = 0;
        return 1;
    }
    if (!isxdigit((unsigned char)ch)) return 0;
    unsigned char lower = (unsigned char)tolower((unsigned char)ch);
    uint8_t nibble = (uint8_t)(isdigit(lower) ? lower - '0' : lower - 'a' + 10);
    *mask = nibble_mask;
    *value = (uint8_t)(nibble << shift);
    return 1;
}

// Internal form: hexnot:<prefix>|<negated-byte-token>|<suffix>
AXIOM_RUNTIME_FN int axiom_yara_parse_hex_negation_internal(const char* encoded,
                                                             AxiomYaraHexNegation* negation) {
    if (!negation) return 0;
    memset(negation, 0, sizeof(*negation));
    if (!encoded) return 0;
    size_t encoded_len = strlen(encoded);
    static const char tag[] = "hexnot:";
    const size_t tag_len = sizeof(tag) - 1;
    if (encoded_len < tag_len + 4 || encoded_len > AXIOM_YARA_MAX_HEX_PATTERN_TEXT ||
        memcmp(encoded, tag, tag_len) != 0) return 0;

    const char* fields[3] = {0};
    size_t field_lens[3] = {0};
    size_t field_index = 0;
    const char* field_start = encoded + tag_len;
    for (const char* p = field_start; ; p++) {
        if (*p == '|' || *p == '\0') {
            if (field_index >= 3) return 0;
            fields[field_index] = field_start;
            field_lens[field_index] = (size_t)(p - field_start);
            field_index++;
            if (*p == '\0') break;
            field_start = p + 1;
        }
    }
    if (field_index != 3 || field_lens[1] != 2) goto invalid_negation;

    uint8_t mask_hi = 0, value_hi = 0, mask_lo = 0, value_lo = 0;
    if (!axiom_yara_negated_hex_nibble(fields[1][0], &mask_hi, &value_hi, 0xF0, 4) ||
        !axiom_yara_negated_hex_nibble(fields[1][1], &mask_lo, &value_lo, 0x0F, 0)) goto invalid_negation;
    negation->excluded_mask = (uint8_t)(mask_hi | mask_lo);
    negation->excluded_value = (uint8_t)(value_hi | value_lo);
    if (negation->excluded_mask == 0) goto invalid_negation;

    AxiomYaraCompiledPattern* parts[2] = {&negation->prefix, &negation->suffix};
    const size_t part_indexes[2] = {0, 2};
    for (int part = 0; part < 2; part++) {
        size_t part_len = field_lens[part_indexes[part]];
        if (part_len == 0) continue;
        char* text = (char*)malloc(part_len + 1);
        if (!text) goto invalid_negation;
        memcpy(text, fields[part_indexes[part]], part_len);
        text[part_len] = '\0';
        int has_brace = 0;
        for (size_t i = 0; i < part_len; i++) {
            if (text[i] == '{' || text[i] == '}') has_brace = 1;
        }
        int parsed = has_brace ? 0 : axiom_yara_parse_hex_pattern_internal(text, parts[part]);
        free(text);
        if (parsed <= 0) goto invalid_negation;
    }
    return 1;

invalid_negation:
    axiom_yara_hex_negation_free(negation);
    return 0;
}

AXIOM_RUNTIME_FN int axiom_yara_hex_negation_match_at(const uint8_t* target, size_t target_len,
                                                       const AxiomYaraHexNegation* negation,
                                                       int64_t start);

AXIOM_RUNTIME_FN ax_int axiom_yara_find_hex_negation(const char* target, const char* encoded,
                                                       ax_int min_offset, ax_int max_offset) {
    return axiom_yara_find_hex_pattern(target, encoded, min_offset, max_offset);
}

AXIOM_RUNTIME_FN ax_int axiom_yara_hex_negation_len(const char* encoded) {
    if (!encoded) return -1;
    AxiomYaraHexNegation negation;
    if (!axiom_yara_parse_hex_negation_internal(encoded, &negation)) return -1;
    int result = negation.prefix.len + 1 + negation.suffix.len;
    axiom_yara_hex_negation_free(&negation);
    return (ax_int)result;
}

typedef struct {
    AxiomYaraCompiledPattern branches[4];
    int branch_count;
    int common_len;
} AxiomYaraHexAlternation;

AXIOM_RUNTIME_FN void axiom_yara_hex_alternation_free(AxiomYaraHexAlternation* alt) {
    if (!alt) return;
    for (int i = 0; i < 4; i++) axiom_yara_pattern_free(&alt->branches[i]);
    alt->branch_count = 0;
    alt->common_len = 0;
}

// Internal form: hexalt:<fixed-branch>|<fixed-branch>[|<branch>...]
AXIOM_RUNTIME_FN int axiom_yara_parse_hex_alternation_internal(const char* encoded,
                                                                AxiomYaraHexAlternation* alt) {
    if (!alt) return 0;
    memset(alt, 0, sizeof(*alt));
    if (!encoded) return 0;
    size_t encoded_len = strlen(encoded);
    static const char tag[] = "hexalt:";
    const size_t tag_len = sizeof(tag) - 1;
    if (encoded_len <= tag_len || encoded_len > AXIOM_YARA_MAX_HEX_PATTERN_TEXT ||
        memcmp(encoded, tag, tag_len) != 0) return 0;

    const char* branch_start = encoded + tag_len;
    const char* cursor = branch_start;
    int has_constrained_byte = 0;
    while (1) {
        if (*cursor == '|' || *cursor == '\0') {
            size_t branch_len = (size_t)(cursor - branch_start);
            if (branch_len == 0 || alt->branch_count >= 4) goto invalid_alt;
            char* branch_text = (char*)malloc(branch_len + 1);
            if (!branch_text) goto invalid_alt;
            memcpy(branch_text, branch_start, branch_len);
            branch_text[branch_len] = '\0';
            for (size_t i = 0; i < branch_len; i++) {
                if (branch_text[i] == '{' || branch_text[i] == '}') {
                    free(branch_text);
                    goto invalid_alt;
                }
            }
            AxiomYaraCompiledPattern* branch = &alt->branches[alt->branch_count];
            int parsed_len = axiom_yara_parse_hex_pattern_internal(branch_text, branch);
            free(branch_text);
            if (parsed_len <= 0 || parsed_len > 16) goto invalid_alt;
            if (alt->branch_count == 0) alt->common_len = parsed_len;
            else if (parsed_len != alt->common_len) goto invalid_alt;
            for (int i = 0; i < parsed_len; i++) {
                if (branch->masks[i] != 0) has_constrained_byte = 1;
            }
            alt->branch_count++;
            if (*cursor == '\0') break;
            branch_start = cursor + 1;
        }
        cursor++;
    }
    if (alt->branch_count < 2 || !has_constrained_byte) goto invalid_alt;
    return 1;

invalid_alt:
    axiom_yara_hex_alternation_free(alt);
    return 0;
}

AXIOM_RUNTIME_FN ax_int axiom_yara_find_hex_alternation(const char* target, const char* encoded,
                                                         ax_int min_offset, ax_int max_offset) {
    return axiom_yara_find_hex_pattern(target, encoded, min_offset, max_offset);
}

AXIOM_RUNTIME_FN ax_int axiom_yara_hex_alternation_len(const char* encoded) {
    if (!encoded) return -1;
    AxiomYaraHexAlternation alt;
    if (!axiom_yara_parse_hex_alternation_internal(encoded, &alt)) return -1;
    int result = alt.common_len;
    axiom_yara_hex_alternation_free(&alt);
    return (ax_int)result;
}

AXIOM_RUNTIME_FN int axiom_yara_hex_compiled_match_at(const uint8_t* target, size_t target_len,
                                                       const AxiomYaraCompiledPattern* pattern,
                                                       int64_t start) {
    if (!target || !pattern || pattern->len <= 0 || start < 0 || target_len > (size_t)INT64_MAX) return 0;
    if (start > (int64_t)target_len - pattern->len) return 0;
    for (int i = 0; i < pattern->len; i++) {
        if ((target[start + i] & pattern->masks[i]) != pattern->vals[i]) return 0;
    }
    return 1;
}

AXIOM_RUNTIME_FN ax_int axiom_yara_find_next_compiled(const uint8_t* target, size_t target_len,
                                                       const AxiomYaraCompiledPattern* pattern,
                                                       int64_t start, int64_t end) {
    if (!target || !pattern || pattern->len <= 0 || start < 0 || start > end ||
        target_len > (size_t)INT64_MAX) return -1;
    int64_t last_valid = (int64_t)target_len - pattern->len;
    if (end > last_valid) end = last_valid;
    if (start > end) return -1;
    if (pattern->len == 1 && pattern->masks[0] == 0xFF) {
        const uint8_t* found = (const uint8_t*)memchr(target + start, pattern->vals[0], (size_t)(end - start + 1));
        return found ? (ax_int)(found - target) : -1;
    }
    if (pattern->len == 1) {
        for (int64_t i = start; i <= end; i++) {
            if ((target[i] & pattern->masks[0]) == pattern->vals[0]) return (ax_int)i;
        }
        return -1;
    }
    return axiom_yara_find_bytes(target, target_len, pattern, start, end);
}

AXIOM_RUNTIME_FN int axiom_yara_hex_ast_append(char* dst, size_t cap, size_t* used,
                                                const char* src, size_t len) {
    if (!dst || !used || (!src && len) || *used >= cap || len >= cap - *used) return 0;
    if (len) memcpy(dst + *used, src, len);
    *used += len;
    dst[*used] = '\0';
    return 1;
}

enum {
    AXIOM_YARA_ATOM_BYTES = 1,
    AXIOM_YARA_ATOM_JUMP = 2,
    AXIOM_YARA_ATOM_ALTERNATION = 3,
    AXIOM_YARA_ATOM_NOT_BYTE = 4
};

typedef struct {
    int kind;
    union {
        AxiomYaraCompiledPattern bytes;
        struct {
            int min_gap;
            int max_gap;
            int suffix_anchor;
            size_t suffix_anchor_matches;
            uint8_t* suffix_anchor_bits;
            size_t suffix_anchor_bits_len;
        } jump;
        AxiomYaraHexAlternation alternation;
        struct { uint8_t mask; uint8_t value; } not_byte;
    } as;
} AxiomYaraHexAtom;

typedef struct {
    size_t count;
    AxiomYaraHexAtom atoms[3];
} AxiomYaraHexPattern;

AXIOM_RUNTIME_FN void axiom_yara_hex_pattern_free(AxiomYaraHexPattern* pattern) {
    if (!pattern) return;
    for (size_t i = 0; i < pattern->count && i < 3; i++) {
        AxiomYaraHexAtom* atom = &pattern->atoms[i];
        if (atom->kind == AXIOM_YARA_ATOM_BYTES) axiom_yara_pattern_free(&atom->as.bytes);
        else if (atom->kind == AXIOM_YARA_ATOM_JUMP && atom->as.jump.suffix_anchor_bits) {
            free(atom->as.jump.suffix_anchor_bits);
        } else if (atom->kind == AXIOM_YARA_ATOM_ALTERNATION) {
            axiom_yara_hex_alternation_free(&atom->as.alternation);
        }
    }
    memset(pattern, 0, sizeof(*pattern));
}

AXIOM_RUNTIME_FN int axiom_yara_hex_pattern_add_bytes(AxiomYaraHexPattern* pattern, const char* source) {
    if (!pattern || !source || pattern->count >= 3) return 0;
    AxiomYaraHexAtom* atom = &pattern->atoms[pattern->count];
    memset(atom, 0, sizeof(*atom));
    atom->kind = AXIOM_YARA_ATOM_BYTES;
    if (axiom_yara_parse_hex_pattern_internal(source, &atom->as.bytes) <= 0) return 0;
    pattern->count++;
    return 1;
}

AXIOM_RUNTIME_FN int axiom_yara_hex_pattern_add_bytes_move(AxiomYaraHexPattern* pattern,
                                                             AxiomYaraCompiledPattern* source) {
    if (!pattern || !source || source->len <= 0 || pattern->count >= 3) return 0;
    AxiomYaraHexAtom* atom = &pattern->atoms[pattern->count++];
    memset(atom, 0, sizeof(*atom));
    atom->kind = AXIOM_YARA_ATOM_BYTES;
    atom->as.bytes = *source;
    *source = (AxiomYaraCompiledPattern){NULL, NULL, 0};
    return 1;
}

// Parse hexast:v1 directly into the occurrence matcher's typed model. This
// removes legacy tag construction from the hot path while retaining adapters
// for callers that still pass the old encodings directly.
AXIOM_RUNTIME_FN int axiom_yara_parse_hex_ast_internal(const char* encoded,
                                                        AxiomYaraHexPattern* pattern) {
    static const char tag[] = "hexast:v1:";
    if (!encoded || !pattern ||
        strncmp(encoded, tag, sizeof(tag) - 1) != 0) return 0;
    size_t encoded_len = strlen(encoded);
    if (encoded_len <= sizeof(tag) - 1 || encoded_len > AXIOM_YARA_MAX_HEX_PATTERN_TEXT) return 0;

    char prefix[AXIOM_YARA_MAX_HEX_PATTERN_TEXT + 1] = {0};
    char suffix[AXIOM_YARA_MAX_HEX_PATTERN_TEXT + 1] = {0};
    char special[AXIOM_YARA_MAX_HEX_PATTERN_TEXT + 1] = {0};
    size_t prefix_len = 0, suffix_len = 0;
    int special_kind = 0;
    const char* cursor = encoded + sizeof(tag) - 1;
    const char* end = encoded + encoded_len;

    while (cursor < end) {
        char opcode = *cursor++;
        const char* operand = cursor;
        while (cursor < end && *cursor != ';') cursor++;
        if (cursor >= end) return 0;
        size_t operand_len = (size_t)(cursor - operand);
        cursor++;
        if (operand_len == 0 || operand_len > AXIOM_YARA_MAX_HEX_PATTERN_TEXT) return 0;
        if (opcode == 'B') {
            char* destination = special_kind == 0 ? prefix : suffix;
            size_t* used = special_kind == 0 ? &prefix_len : &suffix_len;
            if (*used + operand_len + (*used > 0 ? 1u : 0u) >= AXIOM_YARA_MAX_HEX_PATTERN_TEXT + 1u) return 0;
            if (*used) destination[(*used)++] = ' ';
            memcpy(destination + *used, operand, operand_len);
            *used += operand_len;
            destination[*used] = '\0';
        } else if (opcode == 'J' || opcode == 'A' || opcode == 'N') {
            if (special_kind != 0) return 0;
            special_kind = opcode == 'J' ? 1 : (opcode == 'A' ? 2 : 3);
            memcpy(special, operand, operand_len);
            special[operand_len] = '\0';
        } else {
            return 0;
        }
    }

    if (special_kind == 0) return prefix_len > 0 && axiom_yara_hex_pattern_add_bytes(pattern, prefix);
    if (special_kind == 1) {
        char* dash = strchr(special, '-');
        int min_gap = 0, max_gap = 0;
        if (!prefix_len || !suffix_len || !dash || strchr(dash + 1, '-') ||
            !axiom_yara_parse_jump_bound(special, (size_t)(dash - special), &min_gap) ||
            !axiom_yara_parse_jump_bound(dash + 1, strlen(dash + 1), &max_gap) ||
            min_gap > max_gap || max_gap - min_gap > 16) return 0;
        if (!axiom_yara_hex_pattern_add_bytes(pattern, prefix)) return 0;
        AxiomYaraHexAtom* jump = &pattern->atoms[pattern->count++];
        memset(jump, 0, sizeof(*jump));
        jump->kind = AXIOM_YARA_ATOM_JUMP;
        jump->as.jump.min_gap = min_gap;
        jump->as.jump.max_gap = max_gap;
        jump->as.jump.suffix_anchor = -1;
        if (!axiom_yara_hex_pattern_add_bytes(pattern, suffix)) return 0;
        int constrained = 0;
        AxiomYaraCompiledPattern* left = &pattern->atoms[0].as.bytes;
        AxiomYaraCompiledPattern* right = &pattern->atoms[2].as.bytes;
        for (int i = 0; i < left->len; i++) if (left->masks[i] != 0) constrained = 1;
        for (int i = 0; i < right->len; i++) if (right->masks[i] != 0) constrained = 1;
        if (!constrained) return 0;
        return 1;
    }
    if (special_kind == 3) {
        if (strlen(special) != 2 || (special[0] == '?' && special[1] == '?')) return 0;
        uint8_t mask_hi = 0, value_hi = 0, mask_lo = 0, value_lo = 0;
        if (!axiom_yara_negated_hex_nibble(special[0], &mask_hi, &value_hi, 0xF0, 4) ||
            !axiom_yara_negated_hex_nibble(special[1], &mask_lo, &value_lo, 0x0F, 0)) return 0;
        if (prefix_len && !axiom_yara_hex_pattern_add_bytes(pattern, prefix)) return 0;
        AxiomYaraHexAtom* negated = &pattern->atoms[pattern->count++];
        memset(negated, 0, sizeof(*negated));
        negated->kind = AXIOM_YARA_ATOM_NOT_BYTE;
        negated->as.not_byte.mask = (uint8_t)(mask_hi | mask_lo);
        negated->as.not_byte.value = (uint8_t)(value_hi | value_lo);
        if (!negated->as.not_byte.mask) return 0;
        if (suffix_len && !axiom_yara_hex_pattern_add_bytes(pattern, suffix)) return 0;
        return 1;
    }

    if (prefix_len && !axiom_yara_hex_pattern_add_bytes(pattern, prefix)) return 0;
    if (pattern->count >= 3) return 0;
    AxiomYaraHexAtom* alt_atom = &pattern->atoms[pattern->count++];
    memset(alt_atom, 0, sizeof(*alt_atom));
    alt_atom->kind = AXIOM_YARA_ATOM_ALTERNATION;
    const char* branch = special;
    int has_constrained_byte = 0;
    while (1) {
        const char* separator = strchr(branch, '|');
        size_t branch_len = separator ? (size_t)(separator - branch) : strlen(branch);
        if (!branch_len || alt_atom->as.alternation.branch_count >= 4) return 0;
        char branch_text[AXIOM_YARA_MAX_HEX_PATTERN_TEXT + 1] = {0};
        size_t used = 0;
        if (!axiom_yara_hex_ast_append(branch_text, sizeof(branch_text), &used, branch, branch_len)) return 0;
        AxiomYaraCompiledPattern* compiled = &alt_atom->as.alternation.branches[alt_atom->as.alternation.branch_count];
        int parsed_len = axiom_yara_parse_hex_pattern_internal(branch_text, compiled);
        if (parsed_len <= 0 || parsed_len > 16) return 0;
        if (alt_atom->as.alternation.branch_count == 0) alt_atom->as.alternation.common_len = parsed_len;
        else if (parsed_len != alt_atom->as.alternation.common_len) return 0;
        for (int i = 0; i < parsed_len; i++) {
            if (compiled->masks[i] != 0) has_constrained_byte = 1;
        }
        alt_atom->as.alternation.branch_count++;
        if (!separator) break;
        branch = separator + 1;
    }
    if (alt_atom->as.alternation.branch_count < 2 || !has_constrained_byte) return 0;
    if (suffix_len && !axiom_yara_hex_pattern_add_bytes(pattern, suffix)) return 0;
    return 1;
}

AXIOM_RUNTIME_FN int axiom_yara_parse_hex_legacy_pattern(const char* encoded,
                                                          AxiomYaraHexPattern* pattern) {
    if (!encoded || !pattern || strlen(encoded) > AXIOM_YARA_MAX_HEX_PATTERN_TEXT) return 0;
    if (strncmp(encoded, "hex:", 4) == 0) return axiom_yara_hex_pattern_add_bytes(pattern, encoded + 4);
    if (strncmp(encoded, "hexrange:", 9) == 0) {
        AxiomYaraHexRangePattern range = {{NULL, NULL, 0}, {NULL, NULL, 0}, 0, 0, -1, 0, NULL, 0};
        if (!axiom_yara_parse_hex_range_internal(encoded, &range)) return 0;
        if (!axiom_yara_hex_pattern_add_bytes_move(pattern, &range.prefix) || pattern->count >= 3) {
            axiom_yara_hex_range_free(&range);
            return 0;
        }
        AxiomYaraHexAtom* jump = &pattern->atoms[pattern->count++];
        memset(jump, 0, sizeof(*jump));
        jump->kind = AXIOM_YARA_ATOM_JUMP;
        jump->as.jump.min_gap = range.min_gap;
        jump->as.jump.max_gap = range.max_gap;
        jump->as.jump.suffix_anchor = range.suffix_anchor;
        jump->as.jump.suffix_anchor_matches = range.suffix_anchor_matches;
        jump->as.jump.suffix_anchor_bits = range.suffix_anchor_bits;
        jump->as.jump.suffix_anchor_bits_len = range.suffix_anchor_bits_len;
        range.suffix_anchor_bits = NULL;
        range.suffix_anchor_bits_len = 0;
        if (!axiom_yara_hex_pattern_add_bytes_move(pattern, &range.suffix)) {
            axiom_yara_hex_range_free(&range);
            return 0;
        }
        axiom_yara_hex_range_free(&range);
        return 1;
    }
    if (strncmp(encoded, "hexalt:", 7) == 0) {
        if (pattern->count >= 3) return 0;
        AxiomYaraHexAtom* atom = &pattern->atoms[pattern->count];
        memset(atom, 0, sizeof(*atom));
        atom->kind = AXIOM_YARA_ATOM_ALTERNATION;
        if (!axiom_yara_parse_hex_alternation_internal(encoded, &atom->as.alternation)) return 0;
        pattern->count++;
        return 1;
    }
    if (strncmp(encoded, "hexnot:", 7) == 0) {
        AxiomYaraHexNegation negation;
        if (!axiom_yara_parse_hex_negation_internal(encoded, &negation)) return 0;
        if (negation.prefix.len && !axiom_yara_hex_pattern_add_bytes_move(pattern, &negation.prefix)) {
            axiom_yara_hex_negation_free(&negation);
            return 0;
        }
        if (pattern->count >= 3) { axiom_yara_hex_negation_free(&negation); return 0; }
        AxiomYaraHexAtom* atom = &pattern->atoms[pattern->count++];
        memset(atom, 0, sizeof(*atom));
        atom->kind = AXIOM_YARA_ATOM_NOT_BYTE;
        atom->as.not_byte.mask = negation.excluded_mask;
        atom->as.not_byte.value = negation.excluded_value;
        if (negation.suffix.len && !axiom_yara_hex_pattern_add_bytes_move(pattern, &negation.suffix)) {
            axiom_yara_hex_negation_free(&negation);
            return 0;
        }
        axiom_yara_hex_negation_free(&negation);
        return 1;
    }
    return 0;
}

AXIOM_RUNTIME_FN int64_t axiom_yara_hex_pattern_min_length(const AxiomYaraHexPattern* pattern) {
    if (!pattern || pattern->count == 0 || pattern->count > 3) return -1;
    int64_t total = 0;
    for (size_t i = 0; i < pattern->count; i++) {
        const AxiomYaraHexAtom* atom = &pattern->atoms[i];
        if (atom->kind == AXIOM_YARA_ATOM_BYTES) total += atom->as.bytes.len;
        else if (atom->kind == AXIOM_YARA_ATOM_JUMP) total += atom->as.jump.min_gap;
        else if (atom->kind == AXIOM_YARA_ATOM_ALTERNATION) total += atom->as.alternation.common_len;
        else if (atom->kind == AXIOM_YARA_ATOM_NOT_BYTE) total++;
        else return -1;
        if (total > INT64_MAX) return -1;
    }
    return total;
}

AXIOM_RUNTIME_FN int axiom_yara_hex_pattern_prepare(const uint8_t* target, size_t target_len,
                                                     AxiomYaraHexPattern* pattern) {
    if (!target || !pattern || target_len > (size_t)INT64_MAX) return 0;
    for (size_t i = 0; i < pattern->count; i++) {
        AxiomYaraHexAtom* atom = &pattern->atoms[i];
        if (atom->kind != AXIOM_YARA_ATOM_JUMP) continue;
        if (i == 0 || i + 1 >= pattern->count ||
            pattern->atoms[i - 1].kind != AXIOM_YARA_ATOM_BYTES ||
            pattern->atoms[i + 1].kind != AXIOM_YARA_ATOM_BYTES) return 0;
        AxiomYaraHexRangePattern view = {
            pattern->atoms[i - 1].as.bytes,
            pattern->atoms[i + 1].as.bytes,
            atom->as.jump.min_gap,
            atom->as.jump.max_gap,
            -1, 0, NULL, 0
        };
        int suffix_constrained = 0;
        for (int b = 0; b < view.suffix.len; b++) {
            if (view.suffix.masks[b] != 0) { suffix_constrained = 1; break; }
        }
        if (suffix_constrained) atom->as.jump.suffix_anchor = axiom_yara_hex_range_choose_anchor(target, target_len, &view);
        atom->as.jump.suffix_anchor_matches = view.suffix_anchor_matches;
        atom->as.jump.suffix_anchor_bits = view.suffix_anchor_bits;
        atom->as.jump.suffix_anchor_bits_len = view.suffix_anchor_bits_len;
    }
    return 1;
}

AXIOM_RUNTIME_FN int axiom_yara_hex_pattern_match_at(const uint8_t* target, size_t target_len,
                                                      const AxiomYaraHexPattern* pattern,
                                                      int64_t start, int64_t* match_length) {
    if (!target || !pattern || start < 0 || target_len > (size_t)INT64_MAX ||
        start > (int64_t)target_len) return 0;
    int64_t position = start;
    for (size_t i = 0; i < pattern->count; i++) {
        const AxiomYaraHexAtom* atom = &pattern->atoms[i];
        if (atom->kind == AXIOM_YARA_ATOM_BYTES) {
            if (!axiom_yara_hex_compiled_match_at(target, target_len, &atom->as.bytes, position)) return 0;
            position += atom->as.bytes.len;
        } else if (atom->kind == AXIOM_YARA_ATOM_JUMP) {
            if (i == 0 || i + 1 >= pattern->count ||
                pattern->atoms[i - 1].kind != AXIOM_YARA_ATOM_BYTES ||
                pattern->atoms[i + 1].kind != AXIOM_YARA_ATOM_BYTES) return 0;
            const AxiomYaraCompiledPattern* prefix = &pattern->atoms[i - 1].as.bytes;
            const AxiomYaraCompiledPattern* suffix = &pattern->atoms[i + 1].as.bytes;
            if (atom->as.jump.suffix_anchor >= 0 && atom->as.jump.suffix_anchor_matches == 0) return 0;
            if (atom->as.jump.suffix_anchor >= 0 && atom->as.jump.suffix_anchor_bits &&
                position <= INT64_MAX - atom->as.jump.max_gap - atom->as.jump.suffix_anchor) {
                AxiomYaraHexRangePattern view = {
                    *prefix, *suffix,
                    atom->as.jump.min_gap, atom->as.jump.max_gap,
                    atom->as.jump.suffix_anchor, atom->as.jump.suffix_anchor_matches,
                    atom->as.jump.suffix_anchor_bits, atom->as.jump.suffix_anchor_bits_len
                };
                size_t first = (size_t)(position + atom->as.jump.min_gap + atom->as.jump.suffix_anchor);
                size_t last = (size_t)(position + atom->as.jump.max_gap + atom->as.jump.suffix_anchor);
                if (!axiom_yara_hex_range_anchor_in_window(&view, first, last)) return 0;
            }
            int suffix_constrained = 0;
            for (int b = 0; b < suffix->len; b++) {
                if (suffix->masks[b] != 0) { suffix_constrained = 1; break; }
            }
            int found_gap = -1;
            if (!suffix_constrained) {
                if (position <= INT64_MAX - atom->as.jump.min_gap &&
                    position + atom->as.jump.min_gap <= (int64_t)target_len - suffix->len) {
                    found_gap = atom->as.jump.min_gap;
                }
            } else {
                for (int gap = atom->as.jump.min_gap; gap <= atom->as.jump.max_gap; gap++) {
                    if (position > INT64_MAX - gap) break;
                    int64_t suffix_start = position + gap;
                    if (suffix_start <= (int64_t)target_len - suffix->len &&
                        axiom_yara_hex_compiled_match_at(target, target_len, suffix, suffix_start)) {
                        found_gap = gap;
                        break;
                    }
                }
            }
            if (found_gap < 0) return 0;
            position += found_gap;
        } else if (atom->kind == AXIOM_YARA_ATOM_ALTERNATION) {
            int matched = 0;
            for (int branch = 0; branch < atom->as.alternation.branch_count; branch++) {
                if (axiom_yara_hex_compiled_match_at(target, target_len,
                        &atom->as.alternation.branches[branch], position)) {
                    matched = 1;
                    break;
                }
            }
            if (!matched) return 0;
            position += atom->as.alternation.common_len;
        } else if (atom->kind == AXIOM_YARA_ATOM_NOT_BYTE) {
            if (position >= (int64_t)target_len ||
                ((target[position] & atom->as.not_byte.mask) == atom->as.not_byte.value)) return 0;
            position++;
        } else {
            return 0;
        }
    }
    if (match_length) *match_length = position - start;
    return position > start;
}

// Keep legacy parsed-pattern entry points, but execute their matches with the
// same typed atom matcher used by AST and occurrence APIs.
AXIOM_RUNTIME_FN int axiom_yara_hex_range_match_at(const uint8_t* target, size_t target_len,
                                                    const AxiomYaraHexRangePattern* range,
                                                    int64_t start, int* match_len_out) {
    if (match_len_out) *match_len_out = -1;
    if (!range || range->prefix.len <= 0 || range->suffix.len <= 0 ||
        range->min_gap < 0 || range->max_gap < range->min_gap || range->max_gap > 64) return 0;

    AxiomYaraHexPattern pattern = {0};
    pattern.count = 3;
    pattern.atoms[0].kind = AXIOM_YARA_ATOM_BYTES;
    pattern.atoms[0].as.bytes = range->prefix;
    pattern.atoms[1].kind = AXIOM_YARA_ATOM_JUMP;
    pattern.atoms[1].as.jump.min_gap = range->min_gap;
    pattern.atoms[1].as.jump.max_gap = range->max_gap;
    pattern.atoms[1].as.jump.suffix_anchor = range->suffix_anchor;
    pattern.atoms[1].as.jump.suffix_anchor_matches = range->suffix_anchor_matches;
    pattern.atoms[1].as.jump.suffix_anchor_bits = range->suffix_anchor_bits;
    pattern.atoms[1].as.jump.suffix_anchor_bits_len = range->suffix_anchor_bits_len;
    pattern.atoms[2].kind = AXIOM_YARA_ATOM_BYTES;
    pattern.atoms[2].as.bytes = range->suffix;

    int64_t match_length = -1;
    int matched = axiom_yara_hex_pattern_match_at(target, target_len, &pattern, start, &match_length);
    if (matched && match_len_out) {
        if (match_length > INT_MAX) return 0;
        *match_len_out = (int)match_length;
    }
    return matched;
}

AXIOM_RUNTIME_FN int axiom_yara_hex_negation_match_at(const uint8_t* target, size_t target_len,
                                                       const AxiomYaraHexNegation* negation,
                                                       int64_t start) {
    if (!negation || negation->prefix.len < 0 || negation->suffix.len < 0 ||
        (negation->excluded_mask == 0 && negation->excluded_value != 0)) return 0;
    AxiomYaraHexPattern pattern = {0};
    if (negation->prefix.len > 0) {
        pattern.atoms[pattern.count].kind = AXIOM_YARA_ATOM_BYTES;
        pattern.atoms[pattern.count++].as.bytes = negation->prefix;
    }
    pattern.atoms[pattern.count].kind = AXIOM_YARA_ATOM_NOT_BYTE;
    pattern.atoms[pattern.count].as.not_byte.mask = negation->excluded_mask;
    pattern.atoms[pattern.count++].as.not_byte.value = negation->excluded_value;
    if (negation->suffix.len > 0) {
        pattern.atoms[pattern.count].kind = AXIOM_YARA_ATOM_BYTES;
        pattern.atoms[pattern.count++].as.bytes = negation->suffix;
    }
    return axiom_yara_hex_pattern_match_at(target, target_len, &pattern, start, NULL);
}

AXIOM_RUNTIME_FN ax_int axiom_yara_hex_pattern_next_candidate(const uint8_t* target, size_t target_len,
                                                                const AxiomYaraHexPattern* pattern,
                                                                int64_t cursor, int64_t last_start) {
    if (!target || !pattern || pattern->count == 0 || cursor < 0 || cursor > last_start) return -1;
    const AxiomYaraHexAtom* first = &pattern->atoms[0];
    if (first->kind == AXIOM_YARA_ATOM_BYTES) {
        return axiom_yara_find_next_compiled(target, target_len, &first->as.bytes, cursor, last_start);
    }
    if (first->kind == AXIOM_YARA_ATOM_NOT_BYTE && pattern->count > 1 &&
        pattern->atoms[1].kind == AXIOM_YARA_ATOM_BYTES) {
        int64_t suffix_start = cursor + 1;
        int64_t suffix_end = last_start + 1;
        ax_int found = axiom_yara_find_next_compiled(target, target_len,
            &pattern->atoms[1].as.bytes, suffix_start, suffix_end);
        return found < 0 ? -1 : found - 1;
    }
    return cursor;
}

// Shared occurrence executor for supported hex-pattern encodings. A distinct
// start offset contributes at most one instance; scanning every byte permits
// overlap, while each matcher selects its canonical instance length.
AXIOM_RUNTIME_FN ax_int axiom_yara_hex_pattern_occurrence_internal(const char* target,
                                                                    const char* encoded,
                                                                    ax_int occurrence,
                                                                    int return_length,
                                                                    ax_int min_offset,
                                                                    ax_int max_offset) {
    if (!target || !encoded || occurrence < 0 || min_offset < -1 || max_offset < -1 ||
        (min_offset >= 0 && max_offset >= 0 && min_offset > max_offset)) return -1;
    size_t target_len = strlen(target);
    if (target_len > (size_t)INT64_MAX) return -1;

    AxiomYaraHexPattern pattern;
    memset(&pattern, 0, sizeof(pattern));
    int parsed = strncmp(encoded, "hexast:v1:", 10) == 0
        ? axiom_yara_parse_hex_ast_internal(encoded, &pattern)
        : axiom_yara_parse_hex_legacy_pattern(encoded, &pattern);
    if (!parsed) goto invalid_pattern;

    int64_t min_len = axiom_yara_hex_pattern_min_length(&pattern);
    if (min_len <= 0 || min_len > (int64_t)target_len) {
        axiom_yara_hex_pattern_free(&pattern);
        return occurrence == 0 && !return_length ? 0 : -1;
    }
    if (!axiom_yara_hex_pattern_prepare((const uint8_t*)target, target_len, &pattern)) goto invalid_pattern;
    for (size_t i = 0; i < pattern.count; i++) {
        const AxiomYaraHexAtom* atom = &pattern.atoms[i];
        if (atom->kind == AXIOM_YARA_ATOM_JUMP && atom->as.jump.suffix_anchor >= 0 &&
            atom->as.jump.suffix_anchor_matches == 0) {
            axiom_yara_hex_pattern_free(&pattern);
            return occurrence == 0 && !return_length ? 0 : -1;
        }
    }

    int64_t last_start = (int64_t)target_len - min_len;
    if (max_offset >= 0 && last_start > (int64_t)max_offset) last_start = (int64_t)max_offset;
    int64_t cursor = min_offset > 0 ? (int64_t)min_offset : 0;
    ax_int seen = 0;
    int64_t selected_length = -1;
    while (cursor <= last_start) {
        int64_t start = axiom_yara_hex_pattern_next_candidate((const uint8_t*)target, target_len,
                                                               &pattern, cursor, last_start);
        if (start < 0) break;
        int64_t match_length = -1;
        int matched = axiom_yara_hex_pattern_match_at((const uint8_t*)target, target_len,
                                                       &pattern, start, &match_length);
        if (matched) {
            seen++;
            if (occurrence > 0 && seen == occurrence) {
                selected_length = match_length;
                if (!return_length) {
                    axiom_yara_hex_pattern_free(&pattern);
                    return (ax_int)start;
                }
                break;
            }
        }
        cursor = start + 1;
    }

    axiom_yara_hex_pattern_free(&pattern);
    if (occurrence == 0) return return_length ? -1 : seen;
    if (seen < occurrence) return -1;
    return return_length ? (ax_int)selected_length : -1;

invalid_pattern:
    axiom_yara_hex_pattern_free(&pattern);
    return -1;
}

AXIOM_RUNTIME_FN ax_int axiom_yara_count_hex_pattern(const char* target, const char* pattern) {
    return axiom_yara_hex_pattern_occurrence_internal(target, pattern, 0, 0, -1, -1);
}

AXIOM_RUNTIME_FN ax_int axiom_yara_find_hex_pattern(const char* target, const char* pattern,
                                                     ax_int min_offset, ax_int max_offset) {
    return axiom_yara_hex_pattern_occurrence_internal(target, pattern, 1, 0, min_offset, max_offset);
}

AXIOM_RUNTIME_FN ax_int axiom_yara_hex_pattern_length_at(const char* target, const char* pattern,
                                                          ax_int offset) {
    if (offset < 0) return -1;
    return axiom_yara_hex_pattern_occurrence_internal(target, pattern, 1, 1, offset, offset);
}

AXIOM_RUNTIME_FN ax_int axiom_yara_nth_hex_pattern_offset(const char* target, const char* pattern,
                                                            ax_int occurrence) {
    if (occurrence <= 0) return -1;
    return axiom_yara_hex_pattern_occurrence_internal(target, pattern, occurrence, 0, -1, -1);
}

AXIOM_RUNTIME_FN ax_int axiom_yara_nth_hex_pattern_length(const char* target, const char* pattern,
                                                            ax_int occurrence) {
    if (occurrence <= 0) return -1;
    return axiom_yara_hex_pattern_occurrence_internal(target, pattern, occurrence, 1, -1, -1);
}

AXIOM_RUNTIME_FN ax_int axiom_yara_scan_buf_handle(ax_int handle, const char* hex_pattern, ax_int min_offset, ax_int max_offset) {
    if (handle <= 0 || !hex_pattern) return -1;
    AxiomByteBuffer* b = (AxiomByteBuffer*)(uintptr_t)handle;
    if (!axiom_buf_is_valid(b) || !b->data || b->len == 0) return -1;
    AxiomYaraCompiledPattern pat;
    if (axiom_yara_parse_hex_pattern_internal(hex_pattern, &pat) <= 0) {
        axiom_yara_pattern_free(&pat);
        return -1;
    }
    ax_int res = axiom_yara_find_bytes(b->data, b->len, &pat, min_offset, max_offset);
    axiom_yara_pattern_free(&pat);
    return res;
}

#endif /* AXIOM_RUNTIME_H */
