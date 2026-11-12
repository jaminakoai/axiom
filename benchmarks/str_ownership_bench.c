/* String sahiplik modeli benchmark'i (P2-17b).
 * Derle: clang -O2 -pthread benchmarks/str_ownership_bench.c -lssl -lcrypto -lz -ldl -lm -o /tmp/strbench
 */
#define AXIOM_RUNTIME_FN
#include "../axiom/runtime.h"
#include <time.h>

static double ms(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1000.0 + t.tv_nsec / 1e6;
}

int main(void) {
    const int N = 300000;
    const int LIVE = 150000;
    static const char* keep[150000];
    volatile long acc = 0;

    /* 0) Uretim yolu: int_to_str (baslikli tahsis, kopya yok) */
    double tr = ms();
    for (int i = 0; i < N; i++) {
        const char* s = axiom_int_to_str(i);
        acc += s[0];
        axiom_str_release(s);
    }
    printf("int_to_str_300k_ms    %.1f\n", ms() - tr);

    /* 1) Kisa omurlu: olustur + birak */
    double t0 = ms();
    for (int i = 0; i < N; i++) {
        char* p = malloc(24);
        snprintf(p, 24, "%d", i);
        const char* s = axiom_owned_str_wrap(p);
        acc += s[0];
        axiom_str_release(s);
    }
    printf("short_lived_300k_ms   %.1f\n", ms() - t0);

    /* 2) Uzun omurlu: canli tut, sonra toplu birak */
    t0 = ms();
    for (int i = 0; i < LIVE; i++) {
        char* p = malloc(24);
        snprintf(p, 24, "%d", i);
        keep[i] = axiom_owned_str_wrap(p);
    }
    printf("live_alloc_150k_ms    %.1f\n", ms() - t0);
    t0 = ms();
    for (int i = 0; i < LIVE; i++) axiom_str_release(keep[i]);
    printf("live_release_150k_ms  %.1f\n", ms() - t0);

    /* 3) Bellek ayak izi */
    for (int i = 0; i < LIVE; i++) {
        char* p = malloc(24);
        snprintf(p, 24, "%d", i);
        keep[i] = axiom_owned_str_wrap(p);
    }
    printf("hdr_bytes             %zu\n", (size_t)sizeof(axiom_str_hdr));
    printf("live_strings          %ld\n", (long)axiom_owned_str_count());
    printf("table_mb              0.00  (tablo yok)\n");
    for (int i = 0; i < LIVE; i++) axiom_str_release(keep[i]);

    /* 4) Literal (sahipsiz) uzerinde retain/release guvenligi */
    const char* lit = "literal-string-not-owned";
    axiom_str_retain(lit);
    axiom_str_release(lit);
    printf("literal_safe          1\n");
    printf("acc                   %ld\n", acc);
    return 0;
}
