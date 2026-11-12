/**
 * Axiom (λx) — Taşınabilir kripto özetleri (OpenSSL yoksa)
 *
 * Neden: güvenlik araçlarının çekirdeği hash/HMAC'tir. OpenSSL bulunmayan
 * platformda bu fonksiyonları "yok" demek yerine doğru sonuç veren küçük
 * implementasyonlar sağlanır.
 *
 * KAPSAM: MD5, SHA-1, SHA-256, HMAC-SHA256, sabit zamanlı karşılaştırma.
 * KAPSAM DIŞI: AES, RSA, TLS — bunlar OpenSSL gerektirir ve o platformda
 *            açık hata döndürür (sessiz yanlış sonuç yasak, ilke D7).
 *
 * Implementasyon: FIPS 180-4 (SHA-1/256), RFC 1321 (MD5), RFC 2104 (HMAC).
 * Sabit zamanlı karşılaştırma: boyut ve içerik sızıntısı yok.
 */
#ifndef AXIOM_CRYPTO_PORTABLE_H
#define AXIOM_CRYPTO_PORTABLE_H

#include <stdint.h>
#include <string.h>
#include <stdlib.h>

/* ---- yardımcılar ---- */
static inline uint32_t ax_rotr32(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }
static inline uint32_t ax_rotl32(uint32_t x, int n) { return (x << n) | (x >> (32 - n)); }

static inline void ax_store_be32(uint8_t* p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);  p[3] = (uint8_t)v;
}
static inline uint32_t ax_load_be32(const uint8_t* p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}
static inline uint32_t ax_load_le32(const uint8_t* p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static inline void ax_store_le32(uint8_t* p, uint32_t v) {
    p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8);
    p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24);
}

/* ============================ SHA-256 ============================ */
typedef struct {
    uint32_t h[8];
    uint64_t len;
    uint8_t buf[64];
    size_t buflen;
} ax_sha256_ctx;

static const uint32_t AX_SHA256_K[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};

static inline void ax_sha256_init(ax_sha256_ctx* c) {
    c->h[0]=0x6a09e667; c->h[1]=0xbb67ae85; c->h[2]=0x3c6ef372; c->h[3]=0xa54ff53a;
    c->h[4]=0x510e527f; c->h[5]=0x9b05688c; c->h[6]=0x1f83d9ab; c->h[7]=0x5be0cd19;
    c->len = 0; c->buflen = 0;
}

static inline void ax_sha256_block(ax_sha256_ctx* c, const uint8_t* p) {
    uint32_t w[64];
    for (int i = 0; i < 16; i++) w[i] = ax_load_be32(p + i * 4);
    for (int i = 16; i < 64; i++) {
        uint32_t s0 = ax_rotr32(w[i-15], 7) ^ ax_rotr32(w[i-15], 18) ^ (w[i-15] >> 3);
        uint32_t s1 = ax_rotr32(w[i-2], 17) ^ ax_rotr32(w[i-2], 19) ^ (w[i-2] >> 10);
        w[i] = w[i-16] + s0 + w[i-7] + s1;
    }
    uint32_t a=c->h[0],b=c->h[1],cc=c->h[2],d=c->h[3],e=c->h[4],f=c->h[5],g=c->h[6],hh=c->h[7];
    for (int i = 0; i < 64; i++) {
        uint32_t S1 = ax_rotr32(e,6) ^ ax_rotr32(e,11) ^ ax_rotr32(e,25);
        uint32_t ch = (e & f) ^ ((~e) & g);
        uint32_t t1 = hh + S1 + ch + AX_SHA256_K[i] + w[i];
        uint32_t S0 = ax_rotr32(a,2) ^ ax_rotr32(a,13) ^ ax_rotr32(a,22);
        uint32_t maj = (a & b) ^ (a & cc) ^ (b & cc);
        uint32_t t2 = S0 + maj;
        hh=g; g=f; f=e; e=d+t1; d=cc; cc=b; b=a; a=t1+t2;
    }
    c->h[0]+=a; c->h[1]+=b; c->h[2]+=cc; c->h[3]+=d;
    c->h[4]+=e; c->h[5]+=f; c->h[6]+=g; c->h[7]+=hh;
}

static inline void ax_sha256_update(ax_sha256_ctx* c, const void* data, size_t n) {
    const uint8_t* p = (const uint8_t*)data;
    c->len += (uint64_t)n;
    while (n > 0) {
        size_t take = 64 - c->buflen;
        if (take > n) take = n;
        memcpy(c->buf + c->buflen, p, take);
        c->buflen += take; p += take; n -= take;
        if (c->buflen == 64) { ax_sha256_block(c, c->buf); c->buflen = 0; }
    }
}

static inline void ax_sha256_final(ax_sha256_ctx* c, uint8_t out[32]) {
    uint64_t bits = c->len * 8;
    uint8_t pad[72];
    size_t padlen = (c->buflen < 56) ? (56 - c->buflen) : (120 - c->buflen);
    memset(pad, 0, sizeof(pad));
    pad[0] = 0x80;
    for (int i = 0; i < 8; i++) pad[padlen + i] = (uint8_t)(bits >> (56 - 8 * i));
    ax_sha256_update(c, pad, padlen + 8);
    for (int i = 0; i < 8; i++) ax_store_be32(out + i * 4, c->h[i]);
}

static inline void ax_sha256(const void* data, size_t n, uint8_t out[32]) {
    ax_sha256_ctx c;
    ax_sha256_init(&c);
    ax_sha256_update(&c, data, n);
    ax_sha256_final(&c, out);
}

/* ============================ SHA-1 ============================ */
typedef struct {
    uint32_t h[5];
    uint64_t len;
    uint8_t buf[64];
    size_t buflen;
} ax_sha1_ctx;

static inline void ax_sha1_init(ax_sha1_ctx* c) {
    c->h[0]=0x67452301; c->h[1]=0xEFCDAB89; c->h[2]=0x98BADCFE;
    c->h[3]=0x10325476; c->h[4]=0xC3D2E1F0;
    c->len = 0; c->buflen = 0;
}

static inline void ax_sha1_block(ax_sha1_ctx* c, const uint8_t* p) {
    uint32_t w[80];
    for (int i = 0; i < 16; i++) w[i] = ax_load_be32(p + i * 4);
    for (int i = 16; i < 80; i++)
        w[i] = ax_rotl32(w[i-3] ^ w[i-8] ^ w[i-14] ^ w[i-16], 1);

    uint32_t a=c->h[0],b=c->h[1],cc=c->h[2],d=c->h[3],e=c->h[4];
    for (int i = 0; i < 80; i++) {
        uint32_t f, k;
        if (i < 20)      { f = (b & cc) | ((~b) & d);        k = 0x5A827999; }
        else if (i < 40) { f = b ^ cc ^ d;                    k = 0x6ED9EBA1; }
        else if (i < 60) { f = (b & cc) | (b & d) | (cc & d); k = 0x8F1BBCDC; }
        else             { f = b ^ cc ^ d;                    k = 0xCA62C1D6; }
        uint32_t t = ax_rotl32(a,5) + f + e + k + w[i];
        e = d; d = cc; cc = ax_rotl32(b,30); b = a; a = t;
    }
    c->h[0]+=a; c->h[1]+=b; c->h[2]+=cc; c->h[3]+=d; c->h[4]+=e;
}

static inline void ax_sha1_update(ax_sha1_ctx* c, const void* data, size_t n) {
    const uint8_t* p = (const uint8_t*)data;
    c->len += (uint64_t)n;
    while (n > 0) {
        size_t take = 64 - c->buflen;
        if (take > n) take = n;
        memcpy(c->buf + c->buflen, p, take);
        c->buflen += take; p += take; n -= take;
        if (c->buflen == 64) { ax_sha1_block(c, c->buf); c->buflen = 0; }
    }
}

static inline void ax_sha1_final(ax_sha1_ctx* c, uint8_t out[20]) {
    uint64_t bits = c->len * 8;
    uint8_t pad[72];
    size_t padlen = (c->buflen < 56) ? (56 - c->buflen) : (120 - c->buflen);
    memset(pad, 0, sizeof(pad));
    pad[0] = 0x80;
    for (int i = 0; i < 8; i++) pad[padlen + i] = (uint8_t)(bits >> (56 - 8 * i));
    ax_sha1_update(c, pad, padlen + 8);
    for (int i = 0; i < 5; i++) ax_store_be32(out + i * 4, c->h[i]);
}

static inline void ax_sha1(const void* data, size_t n, uint8_t out[20]) {
    ax_sha1_ctx c;
    ax_sha1_init(&c);
    ax_sha1_update(&c, data, n);
    ax_sha1_final(&c, out);
}

/* ============================ MD5 ============================ */
typedef struct {
    uint32_t h[4];
    uint64_t len;
    uint8_t buf[64];
    size_t buflen;
} ax_md5_ctx;

static const uint32_t AX_MD5_K[64] = {
    0xd76aa478,0xe8c7b756,0x242070db,0xc1bdceee,0xf57c0faf,0x4787c62a,0xa8304613,0xfd469501,
    0x698098d8,0x8b44f7af,0xffff5bb1,0x895cd7be,0x6b901122,0xfd987193,0xa679438e,0x49b40821,
    0xf61e2562,0xc040b340,0x265e5a51,0xe9b6c7aa,0xd62f105d,0x02441453,0xd8a1e681,0xe7d3fbc8,
    0x21e1cde6,0xc33707d6,0xf4d50d87,0x455a14ed,0xa9e3e905,0xfcefa3f8,0x676f02d9,0x8d2a4c8a,
    0xfffa3942,0x8771f681,0x6d9d6122,0xfde5380c,0xa4beea44,0x4bdecfa9,0xf6bb4b60,0xbebfbc70,
    0x289b7ec6,0xeaa127fa,0xd4ef3085,0x04881d05,0xd9d4d039,0xe6db99e5,0x1fa27cf8,0xc4ac5665,
    0xf4292244,0x432aff97,0xab9423a7,0xfc93a039,0x655b59c3,0x8f0ccc92,0xffeff47d,0x85845dd1,
    0x6fa87e4f,0xfe2ce6e0,0xa3014314,0x4e0811a1,0xf7537e82,0xbd3af235,0x2ad7d2bb,0xeb86d391
};

static inline void ax_md5_init(ax_md5_ctx* c) {
    c->h[0]=0x67452301; c->h[1]=0xefcdab89; c->h[2]=0x98badcfe; c->h[3]=0x10325476;
    c->len = 0; c->buflen = 0;
}

static inline void ax_md5_block(ax_md5_ctx* c, const uint8_t* p) {
    uint32_t m[16];
    for (int i = 0; i < 16; i++) m[i] = ax_load_le32(p + i * 4);
    uint32_t a=c->h[0],b=c->h[1],cc=c->h[2],d=c->h[3];
    static const uint32_t S[4][4] = {{7,12,17,22},{5,9,14,20},{4,11,16,23},{6,10,15,21}};
    for (int i = 0; i < 64; i++) {
        uint32_t f, g;
        if (i < 16)      { f = (b & cc) | ((~b) & d); g = (uint32_t)i; }
        else if (i < 32) { f = (d & b) | ((~d) & cc); g = (uint32_t)(5*i + 1) % 16; }
        else if (i < 48) { f = b ^ cc ^ d;            g = (uint32_t)(3*i + 5) % 16; }
        else             { f = cc ^ (b | (~d));       g = (uint32_t)(7*i) % 16; }
        uint32_t tmp = d;
        d = cc;
        cc = b;
        b = b + ax_rotl32(a + f + AX_MD5_K[i] + m[g], (int)S[i/16][i%4]);
        a = tmp;
    }
    c->h[0]+=a; c->h[1]+=b; c->h[2]+=cc; c->h[3]+=d;
}

static inline void ax_md5_update(ax_md5_ctx* c, const void* data, size_t n) {
    const uint8_t* p = (const uint8_t*)data;
    c->len += (uint64_t)n;
    while (n > 0) {
        size_t take = 64 - c->buflen;
        if (take > n) take = n;
        memcpy(c->buf + c->buflen, p, take);
        c->buflen += take; p += take; n -= take;
        if (c->buflen == 64) { ax_md5_block(c, c->buf); c->buflen = 0; }
    }
}

static inline void ax_md5_final(ax_md5_ctx* c, uint8_t out[16]) {
    uint64_t bits = c->len * 8;
    uint8_t pad[72];
    size_t padlen = (c->buflen < 56) ? (56 - c->buflen) : (120 - c->buflen);
    memset(pad, 0, sizeof(pad));
    pad[0] = 0x80;
    for (int i = 0; i < 8; i++) pad[padlen + i] = (uint8_t)(bits >> (8 * i));
    ax_md5_update(c, pad, padlen + 8);
    for (int i = 0; i < 4; i++) ax_store_le32(out + i * 4, c->h[i]);
}

static inline void ax_md5(const void* data, size_t n, uint8_t out[16]) {
    ax_md5_ctx c;
    ax_md5_init(&c);
    ax_md5_update(&c, data, n);
    ax_md5_final(&c, out);
}

/* ============================ HMAC-SHA256 ============================ */
static inline void ax_hmac_sha256(const void* key, size_t keylen,
                                  const void* data, size_t datalen,
                                  uint8_t out[32]) {
    uint8_t k[64];
    memset(k, 0, sizeof(k));
    if (keylen > 64) {
        uint8_t kh[32];
        ax_sha256(key, keylen, kh);
        memcpy(k, kh, 32);
    } else if (keylen > 0) {
        memcpy(k, key, keylen);
    }

    uint8_t ipad[64], opad[64];
    for (int i = 0; i < 64; i++) {
        ipad[i] = (uint8_t)(k[i] ^ 0x36);
        opad[i] = (uint8_t)(k[i] ^ 0x5c);
    }

    ax_sha256_ctx c;
    uint8_t inner[32];
    ax_sha256_init(&c);
    ax_sha256_update(&c, ipad, 64);
    ax_sha256_update(&c, data, datalen);
    ax_sha256_final(&c, inner);

    ax_sha256_init(&c);
    ax_sha256_update(&c, opad, 64);
    ax_sha256_update(&c, inner, 32);
    ax_sha256_final(&c, out);
}

/* ---- hex yardımcıları ---- */
static inline void ax_hex_from_bytes(const uint8_t* b, size_t n, char* out) {
    static const char H[] = "0123456789abcdef";
    for (size_t i = 0; i < n; i++) {
        out[i * 2] = H[b[i] >> 4];
        out[i * 2 + 1] = H[b[i] & 0x0f];
    }
    out[n * 2] = '\0';
}

/* ---- sabit zamanlı karşılaştırma (uzunluk sızdırmaz) ---- */
static inline int ax_ct_memcmp(const void* a, const void* b, size_t n) {
    const uint8_t* x = (const uint8_t*)a;
    const uint8_t* y = (const uint8_t*)b;
    uint8_t diff = 0;
    for (size_t i = 0; i < n; i++) diff |= (uint8_t)(x[i] ^ y[i]);
    return diff == 0;
}

#endif /* AXIOM_CRYPTO_PORTABLE_H */
