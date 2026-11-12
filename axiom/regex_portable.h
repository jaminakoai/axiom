/**
 * Axiom (λx) — Taşınabilir düzenli ifade motoru (POSIX regex yoksa)
 *
 * Neden: Sigma ve YARA kuralları regex kullanır. Windows'ta POSIX regex
 * bulunmadığı için "regex yok" demek, güvenlik araçlarının kural motorunu
 * işe yaramaz hale getirir. Bu motor o boşluğu doldurur.
 *
 * MOTOR: geri izlemeli (backtracking), fakat **adım bütçesi** ile sınırlıdır.
 * Bütçe aşılırsa eşleşme başarısız sayılır — sonsuz/üstel çalışma olmaz.
 * Ek olarak `axiom_regex_risk_level` iç içe niceleyicileri zaten reddeder.
 *
 * DESTEKLENEN (POSIX ERE alt kümesi):
 *   literal, \. \\ \d \s \w, .  [abc] [^abc] [a-z]
 *   *  +  ?  {n} {n,} {n,m}   ( )   |   ^  $   (?i)
 *
 * DESTEKLENMEYEN: geri referans (\1), ileri bakış ((?=...)), isimli gruplar.
 * Bunlar DERLEME HATASI olarak bildirilir; sessiz yanlış sonuç verilmez.
 */
#ifndef AXIOM_REGEX_PORTABLE_H
#define AXIOM_REGEX_PORTABLE_H

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

#define AX_RE_DEFAULT_BUDGET 2000000

typedef enum {
    AX_RE_CHAR, AX_RE_ANY, AX_RE_CLASS, AX_RE_GROUP, AX_RE_ALT,
    AX_RE_REPEAT, AX_RE_BOL, AX_RE_EOL, AX_RE_EMPTY
} ax_re_kind;

typedef struct ax_re_node {
    ax_re_kind kind;
    int ch;
    unsigned char* cls;        /* 256 bitlik küme */
    int negated;
    struct ax_re_node* a;
    struct ax_re_node* b;
    struct ax_re_node* next;
    int min_rep, max_rep;      /* -1 = sınırsız */
} ax_re_node;

typedef struct {
    ax_re_node* root;
    int ignore_case;
    int ok;
    const char* err;
} ax_re;

/* ---------------- düğümler ---------------- */
static ax_re_node* ax_re_node_new(ax_re_kind k) {
    ax_re_node* n = (ax_re_node*)calloc(1, sizeof(ax_re_node));
    if (n) { n->kind = k; n->max_rep = -1; }
    return n;
}

static void ax_re_free(ax_re_node* n) {
    while (n) {
        ax_re_node* next = n->next;
        if (n->kind == AX_RE_CLASS && n->cls) free(n->cls);
        if (n->a) ax_re_free(n->a);
        if (n->b) ax_re_free(n->b);
        free(n);
        n = next;
    }
}

/* ---------------- sınıf yardımcıları ---------------- */
static void ax_re_cls_add(unsigned char* cls, int c) {
    if (c >= 0 && c < 256) cls[c >> 3] |= (unsigned char)(1u << (c & 7u));
}
static int ax_re_cls_has(const unsigned char* cls, int c) {
    if (c < 0 || c >= 256) return 0;
    return (cls[c >> 3] >> (c & 7u)) & 1u;
}
static void ax_re_cls_add_escape(unsigned char* cls, char e) {
    if (e == 'd') { for (int c = '0'; c <= '9'; c++) ax_re_cls_add(cls, c); }
    else if (e == 's') {
        ax_re_cls_add(cls, ' '); ax_re_cls_add(cls, '\t');
        ax_re_cls_add(cls, '\n'); ax_re_cls_add(cls, '\r');
        ax_re_cls_add(cls, '\f'); ax_re_cls_add(cls, '\v');
    } else if (e == 'w') {
        for (int c = '0'; c <= '9'; c++) ax_re_cls_add(cls, c);
        for (int c = 'a'; c <= 'z'; c++) ax_re_cls_add(cls, c);
        for (int c = 'A'; c <= 'Z'; c++) ax_re_cls_add(cls, c);
        ax_re_cls_add(cls, '_');
    } else {
        ax_re_cls_add(cls, (unsigned char)e);
    }
}

/* ---------------- ayrıştırıcı ---------------- */
typedef struct { const char* p; int ok; const char* err; } ax_re_parser;

static ax_re_node* ax_re_parse_alt(ax_re_parser* ps);

static ax_re_node* ax_re_parse_class(ax_re_parser* ps) {
    ax_re_node* n = ax_re_node_new(AX_RE_CLASS);
    if (!n) { ps->ok = 0; ps->err = "bellek yetersiz"; return NULL; }
    n->cls = (unsigned char*)calloc(32, 1);
    if (!n->cls) { free(n); ps->ok = 0; ps->err = "bellek yetersiz"; return NULL; }

    if (*ps->p == '^') { n->negated = 1; ps->p++; }

    int first = 1;
    while (*ps->p && (*ps->p != ']' || first)) {
        first = 0;
        int lo;
        if (*ps->p == '\\' && ps->p[1]) {
            ps->p++;
            char e = *ps->p++;
            if (e == 'd' || e == 's' || e == 'w') { ax_re_cls_add_escape(n->cls, e); continue; }
            lo = (unsigned char)e;
        } else {
            lo = (unsigned char)*ps->p++;
        }
        if (*ps->p == '-' && ps->p[1] && ps->p[1] != ']') {
            ps->p++;
            int hi;
            if (*ps->p == '\\' && ps->p[1]) { ps->p++; hi = (unsigned char)*ps->p++; }
            else hi = (unsigned char)*ps->p++;
            if (hi < lo) { ps->ok = 0; ps->err = "gecersiz karakter araligi"; return n; }
            for (int c = lo; c <= hi; c++) ax_re_cls_add(n->cls, c);
        } else {
            ax_re_cls_add(n->cls, lo);
        }
    }
    if (*ps->p != ']') { ps->ok = 0; ps->err = "kapatilmamis karakter sinifi '['"; return n; }
    ps->p++;
    return n;
}

static int ax_re_read_int(ax_re_parser* ps, int* any) {
    int v = 0; *any = 0;
    while (*ps->p >= '0' && *ps->p <= '9') { v = v * 10 + (*ps->p - '0'); ps->p++; *any = 1; }
    return v;
}

static ax_re_node* ax_re_parse_atom(ax_re_parser* ps) {
    if (!*ps->p) return ax_re_node_new(AX_RE_EMPTY);
    char c = *ps->p;

    if (c == '(') {
        if (ps->p[1] == '?') {
            ps->ok = 0;
            ps->err = "desteklenmeyen grup sozdizimi '(?...)' (ileri bakis/geri referans)";
            return NULL;
        }
        ps->p++;
        ax_re_node* inner = ax_re_parse_alt(ps);
        if (*ps->p != ')') { ps->ok = 0; ps->err = "kapatilmamis grup '('"; return inner; }
        ps->p++;
        ax_re_node* g = ax_re_node_new(AX_RE_GROUP);
        if (!g) { ps->ok = 0; ps->err = "bellek yetersiz"; return inner; }
        g->a = inner;
        return g;
    }
    if (c == '[') { ps->p++; return ax_re_parse_class(ps); }
    if (c == '.') { ps->p++; return ax_re_node_new(AX_RE_ANY); }
    if (c == '^') { ps->p++; return ax_re_node_new(AX_RE_BOL); }
    if (c == '$') { ps->p++; return ax_re_node_new(AX_RE_EOL); }
    if (c == '\\') {
        if (!ps->p[1]) { ps->ok = 0; ps->err = "sondaki ters bolu"; return NULL; }
        ps->p++;
        char e = *ps->p++;
        if (e == 'd' || e == 's' || e == 'w') {
            ax_re_node* n = ax_re_node_new(AX_RE_CLASS);
            if (!n) { ps->ok = 0; ps->err = "bellek yetersiz"; return NULL; }
            n->cls = (unsigned char*)calloc(32, 1);
            if (!n->cls) { free(n); ps->ok = 0; ps->err = "bellek yetersiz"; return NULL; }
            ax_re_cls_add_escape(n->cls, e);
            return n;
        }
        if (e >= '1' && e <= '9') {
            ps->ok = 0;
            ps->err = "desteklenmeyen geri referans (\\1)";
            return NULL;
        }
        ax_re_node* n = ax_re_node_new(AX_RE_CHAR);
        if (!n) { ps->ok = 0; ps->err = "bellek yetersiz"; return NULL; }
        n->ch = (unsigned char)e;
        return n;
    }
    ps->p++;
    ax_re_node* n = ax_re_node_new(AX_RE_CHAR);
    if (!n) { ps->ok = 0; ps->err = "bellek yetersiz"; return NULL; }
    n->ch = (unsigned char)c;
    return n;
}

static ax_re_node* ax_re_parse_quant(ax_re_parser* ps) {
    ax_re_node* atom = ax_re_parse_atom(ps);
    if (!ps->ok || !atom) return atom;

    for (;;) {
        if (!*ps->p) break;
        char q = *ps->p;
        ax_re_node* w = NULL;
        if (q == '*') { ps->p++; w = ax_re_node_new(AX_RE_REPEAT); if (w) { w->min_rep = 0; w->max_rep = -1; } }
        else if (q == '+') { ps->p++; w = ax_re_node_new(AX_RE_REPEAT); if (w) { w->min_rep = 1; w->max_rep = -1; } }
        else if (q == '?') { ps->p++; w = ax_re_node_new(AX_RE_REPEAT); if (w) { w->min_rep = 0; w->max_rep = 1; } }
        else if (q == '{') {
            ps->p++;
            int a1 = 0, a2 = 0;
            int lo = ax_re_read_int(ps, &a1);
            int hi = lo;
            if (*ps->p == ',') {
                ps->p++;
                hi = ax_re_read_int(ps, &a2);
                if (!a2) hi = -1;
                else if (a2 && hi == 0) hi = 0;
            }
            if (*ps->p != '}') { ps->ok = 0; ps->err = "kapatilmamis '{' niceleyicisi"; return atom; }
            ps->p++;
            if (!a1) { ps->ok = 0; ps->err = "gecersiz niceleyici"; return atom; }
            w = ax_re_node_new(AX_RE_REPEAT);
            if (w) { w->min_rep = lo; w->max_rep = hi; }
        } else {
            break;
        }
        if (!w) { ps->ok = 0; ps->err = "bellek yetersiz"; return atom; }
        w->a = atom;
        atom = w;
    }
    return atom;
}

static ax_re_node* ax_re_parse_seq(ax_re_parser* ps) {
    ax_re_node* head = NULL;
    ax_re_node* tail = NULL;
    while (*ps->p && *ps->p != '|' && *ps->p != ')') {
        ax_re_node* n = ax_re_parse_quant(ps);
        if (!ps->ok) return head;
        if (!n) break;
        if (!head) head = n; else tail->next = n;
        tail = n;
        while (tail->next) tail = tail->next;
    }
    return head;
}

static ax_re_node* ax_re_parse_alt(ax_re_parser* ps) {
    ax_re_node* left = ax_re_parse_seq(ps);
    if (!ps->ok) return left;
    if (*ps->p != '|') return left;
    ps->p++;
    ax_re_node* right = ax_re_parse_alt(ps);
    ax_re_node* n = ax_re_node_new(AX_RE_ALT);
    if (!n) { ps->ok = 0; ps->err = "bellek yetersiz"; return left; }
    n->a = left;
    n->b = right;
    return n;
}

static void ax_re_compile(ax_re* re, const char* pattern) {
    re->root = NULL; re->ignore_case = 0; re->ok = 1; re->err = NULL;
    if (!pattern) { re->ok = 0; re->err = "bos desen"; return; }
    ax_re_parser ps;
    ps.p = pattern; ps.ok = 1; ps.err = NULL;

    if (ps.p[0] == '(' && ps.p[1] == '?' && ps.p[2] == 'i' && ps.p[3] == ')') {
        re->ignore_case = 1;
        ps.p += 4;
    }
    re->root = ax_re_parse_alt(&ps);
    if (ps.ok && *ps.p) { ps.ok = 0; ps.err = "beklenmeyen karakter"; }
    re->ok = ps.ok;
    re->err = ps.err;
}

/* ---------------- eşleştirici ----------------
 * Sözleşme: ax_re_m(ctx, node, pos) düğüm DİZİSİNİ pos'tan eşleştirir ve
 * başarıda BİTİŞ KONUMUNU, başarısızlıkta -1 döndürür.
 */
typedef struct {
    const char* text;
    size_t len;
    int ignore_case;
    long budget;
    int exhausted;
} ax_re_ctx;

static inline int ax_re_lower(int c) { return (c >= 'A' && c <= 'Z') ? c + 32 : c; }

static long ax_re_m(ax_re_ctx* ctx, ax_re_node* n, size_t pos);

/* Tek karakter düğümü (CHAR/ANY/CLASS) eşleşirse bitiş konumu, yoksa -1. */
static long ax_re_m_one(ax_re_ctx* ctx, ax_re_node* n, size_t pos) {
    if (pos >= ctx->len) return -1;
    int c = (unsigned char)ctx->text[pos];
    switch (n->kind) {
        case AX_RE_ANY:
            return (c == '\n') ? -1 : (long)(pos + 1);
        case AX_RE_CHAR: {
            int a = c, b = n->ch;
            if (ctx->ignore_case) { a = ax_re_lower(a); b = ax_re_lower(b); }
            return (a == b) ? (long)(pos + 1) : -1;
        }
        case AX_RE_CLASS: {
            int hit = ax_re_cls_has(n->cls, c);
            if (!hit && ctx->ignore_case) {
                int alt = islower(c) ? toupper(c) : (isupper(c) ? tolower(c) : c);
                hit = ax_re_cls_has(n->cls, alt);
            }
            if (n->negated) hit = !hit;
            return hit ? (long)(pos + 1) : -1;
        }
        default:
            return -1;
    }
}

/* node'un tamamını (n ve next zinciri) pos'tan eşleştir; bitiş konumu veya -1 */
static long ax_re_m(ax_re_ctx* ctx, ax_re_node* n, size_t pos) {
    if (--ctx->budget <= 0) { ctx->exhausted = 1; return -1; }
    if (!n) return (long)pos;

    switch (n->kind) {
        case AX_RE_EMPTY:
            return ax_re_m(ctx, n->next, pos);
        case AX_RE_BOL:
            return (pos == 0) ? ax_re_m(ctx, n->next, pos) : -1;
        case AX_RE_EOL:
            return (pos == ctx->len) ? ax_re_m(ctx, n->next, pos) : -1;
        case AX_RE_ANY:
        case AX_RE_CHAR:
        case AX_RE_CLASS: {
            long e = ax_re_m_one(ctx, n, pos);
            if (e < 0) return -1;
            return ax_re_m(ctx, n->next, (size_t)e);
        }
        case AX_RE_GROUP:
        case AX_RE_ALT: {
            /* Grubu/dalları next ile birleştirip dene. */
            ax_re_node* branches[2] = { n->a, n->b };
            int nb = (n->kind == AX_RE_ALT) ? 2 : 1;
            for (int bi = 0; bi < nb; bi++) {
                ax_re_node* body = branches[bi];
                if (!body) {
                    long r = ax_re_m(ctx, n->next, pos);
                    if (r >= 0) return r;
                    continue;
                }
                /* body zincirinin kuyruğuna n->next'i geçici olarak ekle */
                ax_re_node* tail = body;
                while (tail->next) tail = tail->next;
                ax_re_node* saved = tail->next;
                tail->next = n->next;
                long r = ax_re_m(ctx, body, pos);
                tail->next = saved;
                if (r >= 0) return r;
                if (ctx->exhausted) return -1;
            }
            return -1;
        }
        case AX_RE_REPEAT: {
            ax_re_node* body = n->a;
            int minr = n->min_rep;
            int maxr = n->max_rep;

            /* Greedy: gövdeyi olabildiğince çok kez eşleştir. */
            size_t cap = 16, cnt = 0;
            size_t* pos_list = (size_t*)malloc(cap * sizeof(size_t));
            if (!pos_list) return -1;
            pos_list[cnt++] = pos;
            size_t cur = pos;

            for (;;) {
                if (maxr >= 0 && (int)cnt - 1 >= maxr) break;
                if (--ctx->budget <= 0) { ctx->exhausted = 1; break; }

                /* gövdeyi TEK başına eşleştir (next'e bağlamadan) */
                long e;
                if (body->kind == AX_RE_GROUP || body->kind == AX_RE_ALT) {
                    /* grup: içeriğini next'siz eşleştir */
                    ax_re_node* inner = body->a;
                    ax_re_node* saved = NULL;
                    ax_re_node* tail = inner;
                    if (tail) { while (tail->next) tail = tail->next; }
                    if (tail) { saved = tail->next; tail->next = NULL; }
                    e = ax_re_m(ctx, inner, cur);
                    if (tail) tail->next = saved;
                    /* ALT gövdesi de olabilir: ikinci dalı dene */
                    if (e < 0 && body->kind == AX_RE_ALT && body->b) {
                        ax_re_node* t2 = body->b;
                        ax_re_node* sv2 = NULL;
                        while (t2->next) t2 = t2->next;
                        sv2 = t2->next; t2->next = NULL;
                        e = ax_re_m(ctx, body->b, cur);
                        t2->next = sv2;
                    }
                } else {
                    e = ax_re_m_one(ctx, body, cur);
                }
                if (e < 0 || (size_t)e == cur) break;   /* eşleşme yok / sıfır uzunluk */
                cur = (size_t)e;
                if (cnt == cap) {
                    cap *= 2;
                    size_t* g = (size_t*)realloc(pos_list, cap * sizeof(size_t));
                    if (!g) { free(pos_list); return -1; }
                    pos_list = g;
                }
                pos_list[cnt++] = cur;
            }

            long result = -1;
            for (int k = (int)cnt - 1; k >= 0; k--) {
                if (k < minr) break;
                if (--ctx->budget <= 0) { ctx->exhausted = 1; break; }
                long r = ax_re_m(ctx, n->next, pos_list[k]);
                if (r >= 0) { result = r; break; }
                if (ctx->exhausted) break;
            }
            free(pos_list);
            return result;
        }
        default:
            return -1;
    }
}

/* Metinde ara. Başarıda başlangıç konumu (>=0) ve *mlen* uzunluk; yoksa -1. */
static long ax_re_search(const ax_re* re, const char* text, size_t* mlen,
                         int* exhausted, long budget) {
    if (exhausted) *exhausted = 0;
    if (mlen) *mlen = 0;
    if (!re->ok) return -1;

    size_t len = strlen(text);
    ax_re_ctx ctx;
    ctx.text = text; ctx.len = len;
    ctx.ignore_case = re->ignore_case;
    ctx.budget = (budget > 0) ? budget : AX_RE_DEFAULT_BUDGET;
    ctx.exhausted = 0;

    int anchored_bol = (re->root && re->root->kind == AX_RE_BOL);

    for (size_t start = 0; start <= len; start++) {
        long e = ax_re_m(&ctx, re->root, start);
        if (e >= 0) {
            if (mlen) *mlen = (size_t)e - start;
            return (long)start;
        }
        if (ctx.exhausted) { if (exhausted) *exhausted = 1; return -1; }
        if (anchored_bol) break;
    }
    return -1;
}

#endif /* AXIOM_REGEX_PORTABLE_H */
