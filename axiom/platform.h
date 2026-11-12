/**
 * Axiom (λx) — Platform Soyutlama Katmanı
 *
 * Destek katmanları (dürüst sınırlar):
 *
 *   Katman 1 — ÇEKİRDEK (taşınabilir)
 *     string, dizi, dosya, dizin, matematik, printf, sözleşmeler, thread,
 *     mutex, zaman. Linux / macOS / Windows.
 *
 *   Katman 2 — AĞ (taşınabilir)
 *     TCP, UDP, DNS, HTTP istemcisi. POSIX sockets / Winsock2.
 *
 *   Katman 3 — YALNIZ LINUX (derleme anında açık hata)
 *     epoll, /proc adli bilişim, ham soket (pcap), ptrace, shellcode.
 *     Başka platformda sessizce yanlış sonuç vermek yerine
 *     `#error` veya açık runtime hatası üretir (ilke D7).
 *
 *   Katman 4 — HARİCİ KÜTÜPHANE
 *     OpenSSL (hash/AES/HMAC/TLS) ve zlib. Kütüphane yoksa fonksiyonlar
 *     boş değer değil AÇIK HATA döndürür.
 */
#ifndef AXIOM_PLATFORM_H
#define AXIOM_PLATFORM_H

#if defined(_WIN32) || defined(_WIN64)
#  define AXIOM_OS_WINDOWS 1
#elif defined(__APPLE__)
#  define AXIOM_OS_MACOS 1
#elif defined(__linux__)
#  define AXIOM_OS_LINUX 1
#else
#  define AXIOM_OS_OTHER 1
#endif

/* ==== 1. Ortak başlıklar ==== */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <inttypes.h>
#include <ctype.h>
#include <math.h>
#include <errno.h>

#if defined(AXIOM_OS_WINDOWS)
#  ifndef WIN32_LEAN_AND_MEAN
#    define WIN32_LEAN_AND_MEAN
#  endif
#  ifndef _CRT_SECURE_NO_WARNINGS
#    define _CRT_SECURE_NO_WARNINGS
#  endif
#  include <winsock2.h>
#  include <ws2tcpip.h>
#  include <windows.h>
#  include <io.h>
#  include <direct.h>
#  include <process.h>
#  include <fcntl.h>
#  include <psapi.h>
#  include <sys/types.h>
#  include <sys/stat.h>
#  include <time.h>
#  define AXIOM_PATH_SEP '\\'
#  define AXIOM_HAVE_POSIX_REGEX 0
typedef int socklen_t;
#  ifndef SHUT_WR
#    define SHUT_WR SD_SEND
#  endif
#else
#  include <sys/types.h>
#  include <sys/socket.h>
#  include <netinet/in.h>
#  include <arpa/inet.h>
#  include <netdb.h>
#  include <unistd.h>
#  include <fcntl.h>
#  include <dirent.h>
#  include <sys/stat.h>
#  include <sys/time.h>
#  include <signal.h>
#  include <time.h>
#  include <poll.h>
#  include <sys/mman.h>
#  include <sys/wait.h>
#  include <regex.h>
#  define AXIOM_HAVE_POSIX_REGEX 1
#  define AXIOM_PATH_SEP '/'
#endif

/* Atomikler: C11 — gcc/clang/MSVC 2019+ */
#include <stdatomic.h>

/* ==== 2. İş parçacıkları ==== */
#if defined(AXIOM_OS_WINDOWS)

typedef HANDLE ax_thread_t;
/* SRWLOCK: statik baslatma destekler (CRITICAL_SECTION desteklemez) ve
 * InitializeCriticalSection'a gore daha hizli. */
typedef SRWLOCK ax_mutex_t;
#define AX_MUTEX_STATIC_INIT SRWLOCK_INIT

static inline int ax_os_mutex_init(ax_mutex_t* m) {
    InitializeSRWLock(m);
    return 0;
}
static inline void ax_os_mutex_lock(ax_mutex_t* m) { AcquireSRWLockExclusive(m); }
static inline void ax_os_mutex_unlock(ax_mutex_t* m) { ReleaseSRWLockExclusive(m); }
static inline void ax_os_mutex_destroy(ax_mutex_t* m) { (void)m; }

typedef struct { void* (*fn)(void*); void* arg; } ax_thread_thunk_t;

static inline unsigned __stdcall ax_thread_trampoline(void* p) {
    ax_thread_thunk_t* t = (ax_thread_thunk_t*)p;
    t->fn(t->arg);
    free(t);
    return 0;
}

static inline ax_thread_t ax_os_thread_create(void* (*fn)(void*), void* arg) {
    ax_thread_thunk_t* t = (ax_thread_thunk_t*)malloc(sizeof(ax_thread_thunk_t));
    if (!t) return NULL;
    t->fn = fn;
    t->arg = arg;
    uintptr_t h = _beginthreadex(NULL, 0, ax_thread_trampoline, t, 0, NULL);
    if (h == 0) { free(t); return NULL; }
    return (HANDLE)h;
}

static inline long long ax_os_thread_join(ax_thread_t h) {
    if (!h) return 0;
    WaitForSingleObject(h, INFINITE);
    DWORD rc = 0;
    GetExitCodeThread(h, &rc);
    CloseHandle(h);
    return (long long)rc;
}

#else /* POSIX */

#include <pthread.h>
typedef pthread_t ax_thread_t;
typedef pthread_mutex_t ax_mutex_t;
#define AX_MUTEX_STATIC_INIT PTHREAD_MUTEX_INITIALIZER

static inline int ax_os_mutex_init(ax_mutex_t* m) {
    return pthread_mutex_init(m, NULL);
}
static inline void ax_os_mutex_lock(ax_mutex_t* m) { pthread_mutex_lock(m); }
static inline void ax_os_mutex_unlock(ax_mutex_t* m) { pthread_mutex_unlock(m); }
static inline void ax_os_mutex_destroy(ax_mutex_t* m) { pthread_mutex_destroy(m); }

static inline ax_thread_t ax_os_thread_create(void* (*fn)(void*), void* arg) {
    pthread_t t;
    if (pthread_create(&t, NULL, fn, arg) != 0) return (pthread_t)0;
    return t;
}

static inline long long ax_os_thread_join(ax_thread_t h) {
    void* rc = NULL;
    pthread_join(h, &rc);
    return (long long)(intptr_t)rc;
}

#endif

/* ==== 2b. Koşul değişkeni ==== */
#if defined(AXIOM_OS_WINDOWS)
typedef CONDITION_VARIABLE ax_cond_t;
#define AX_COND_STATIC_INIT CONDITION_VARIABLE_INIT
static inline int ax_os_cond_init(ax_cond_t* c) { InitializeConditionVariable(c); return 0; }
static inline void ax_os_cond_wait(ax_cond_t* c, ax_mutex_t* m) {
    SleepConditionVariableSRW(c, m, INFINITE, 0);
}
static inline void ax_os_cond_signal(ax_cond_t* c) { WakeConditionVariable(c); }
static inline void ax_os_cond_broadcast(ax_cond_t* c) { WakeAllConditionVariable(c); }
static inline void ax_os_cond_destroy(ax_cond_t* c) { (void)c; }
#else
typedef pthread_cond_t ax_cond_t;
#define AX_COND_STATIC_INIT PTHREAD_COND_INITIALIZER
static inline int ax_os_cond_init(ax_cond_t* c) { return pthread_cond_init(c, NULL); }
static inline void ax_os_cond_wait(ax_cond_t* c, ax_mutex_t* m) { pthread_cond_wait(c, m); }
static inline void ax_os_cond_signal(ax_cond_t* c) { pthread_cond_signal(c); }
static inline void ax_os_cond_broadcast(ax_cond_t* c) { pthread_cond_broadcast(c); }
static inline void ax_os_cond_destroy(ax_cond_t* c) { pthread_cond_destroy(c); }
#endif

/* ==== 3. Zaman ==== */
static inline long long ax_os_time_ms(void) {
#if defined(AXIOM_OS_WINDOWS)
    FILETIME ft;
    GetSystemTimeAsFileTime(&ft);
    ULARGE_INTEGER u;
    u.LowPart = ft.dwLowDateTime;
    u.HighPart = ft.dwHighDateTime;
    /* 100 ns birim, 1601-01-01'den beri */
    return (long long)((u.QuadPart - 116444736000000000ULL) / 10000ULL);
#else
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (long long)tv.tv_sec * 1000LL + (long long)(tv.tv_usec / 1000);
#endif
}

static inline long long ax_os_epoch_seconds(void) {
    return (long long)time(NULL);
}

/* Yerel kırılım; dönüş: yıl, ay(1-12), gün, saat, dakika, saniye, yday */
typedef struct {
    int year, mon, mday, hour, min, sec, yday;
} ax_tm_parts;

static inline void ax_os_gmtime(long long epoch, ax_tm_parts* out) {
    time_t t = (time_t)epoch;
#if defined(AXIOM_OS_WINDOWS)
    struct tm tmv;
    gmtime_s(&tmv, &t);
    out->year = tmv.tm_year + 1900; out->mon = tmv.tm_mon + 1;
    out->mday = tmv.tm_mday; out->hour = tmv.tm_hour;
    out->min = tmv.tm_min; out->sec = tmv.tm_sec; out->yday = tmv.tm_yday;
#else
    struct tm tmv;
    gmtime_r(&t, &tmv);
    out->year = tmv.tm_year + 1900; out->mon = tmv.tm_mon + 1;
    out->mday = tmv.tm_mday; out->hour = tmv.tm_hour;
    out->min = tmv.tm_min; out->sec = tmv.tm_sec; out->yday = tmv.tm_yday;
#endif
}

static inline void ax_os_localtime(long long epoch, ax_tm_parts* out) {
    time_t t = (time_t)epoch;
#if defined(AXIOM_OS_WINDOWS)
    struct tm tmv;
    localtime_s(&tmv, &t);
    out->year = tmv.tm_year + 1900; out->mon = tmv.tm_mon + 1;
    out->mday = tmv.tm_mday; out->hour = tmv.tm_hour;
    out->min = tmv.tm_min; out->sec = tmv.tm_sec; out->yday = tmv.tm_yday;
#else
    struct tm tmv;
    localtime_r(&t, &tmv);
    out->year = tmv.tm_year + 1900; out->mon = tmv.tm_mon + 1;
    out->mday = tmv.tm_mday; out->hour = tmv.tm_hour;
    out->min = tmv.tm_min; out->sec = tmv.tm_sec; out->yday = tmv.tm_yday;
#endif
}

/* epoch'u strftime ile biçimlendirir; ofset dakika cinsindendir. */
static inline size_t ax_os_strftime_tz(long long epoch, int offset_minutes,
                                        const char* fmt, char* buf, size_t cap) {
    time_t t = (time_t)(epoch + (long long)offset_minutes * 60);
    struct tm tmv;
#if defined(AXIOM_OS_WINDOWS)
    gmtime_s(&tmv, &t);
#else
    gmtime_r(&t, &tmv);
#endif
    return strftime(buf, cap, fmt, &tmv);
}

static inline long long ax_os_timegm(int year, int mon, int mday,
                                     int hour, int min, int sec) {
    struct tm tmv;
    memset(&tmv, 0, sizeof(tmv));
    tmv.tm_year = year - 1900;
    tmv.tm_mon = mon - 1;
    tmv.tm_mday = mday;
    tmv.tm_hour = hour;
    tmv.tm_min = min;
    tmv.tm_sec = sec;
#if defined(AXIOM_OS_WINDOWS)
    return (long long)_mkgmtime(&tmv);
#else
    return (long long)timegm(&tmv);
#endif
}

/* ==== 4. Dosya sistemi ==== */
typedef struct {
    long long size;
    int is_dir;
    int is_reg;
} ax_os_stat_t;

static inline int ax_os_stat(const char* path, ax_os_stat_t* out) {
    if (!path || !out) return -1;
    out->size = -1; out->is_dir = 0; out->is_reg = 0;
#if defined(AXIOM_OS_WINDOWS)
    struct _stat64 st;
    if (_stat64(path, &st) != 0) return -1;
    out->size = (long long)st.st_size;
    out->is_dir = (st.st_mode & _S_IFDIR) ? 1 : 0;
    out->is_reg = (st.st_mode & _S_IFREG) ? 1 : 0;
#else
    struct stat st;
    if (stat(path, &st) != 0) return -1;
    out->size = (long long)st.st_size;
    out->is_dir = S_ISDIR(st.st_mode) ? 1 : 0;
    out->is_reg = S_ISREG(st.st_mode) ? 1 : 0;
#endif
    return 0;
}

static inline int ax_os_exists(const char* path) {
    ax_os_stat_t st;
    return ax_os_stat(path, &st) == 0;
}

static inline int ax_os_mkdir(const char* path) {
#if defined(AXIOM_OS_WINDOWS)
    return _mkdir(path);
#else
    return mkdir(path, 0755);
#endif
}

static inline int ax_os_rmdir(const char* path) {
#if defined(AXIOM_OS_WINDOWS)
    return _rmdir(path);
#else
    return rmdir(path);
#endif
}

static inline int ax_os_unlink(const char* path) {
#if defined(AXIOM_OS_WINDOWS)
    return _unlink(path);
#else
    return unlink(path);
#endif
}

static inline int ax_os_rename(const char* from, const char* to) {
    return rename(from, to);
}

/* Dizin yineleme */
#if defined(AXIOM_OS_WINDOWS)
typedef struct {
    HANDLE h;
    WIN32_FIND_DATAA data;
    int first;
    int valid;
} ax_os_dir_t;

static inline int ax_os_dir_open(ax_os_dir_t* d, const char* path) {
    char pattern[1024];
    snprintf(pattern, sizeof(pattern), "%s\\*", path);
    d->h = FindFirstFileA(pattern, &d->data);
    d->first = 1;
    d->valid = (d->h != INVALID_HANDLE_VALUE);
    return d->valid ? 0 : -1;
}

static inline const char* ax_os_dir_next(ax_os_dir_t* d) {
    if (!d->valid) return NULL;
    for (;;) {
        if (d->first) {
            d->first = 0;
        } else {
            if (!FindNextFileA(d->h, &d->data)) return NULL;
        }
        if (d->data.cFileName[0] == '.' &&
            (d->data.cFileName[1] == '\0' ||
             (d->data.cFileName[1] == '.' && d->data.cFileName[2] == '\0'))) continue;
        return d->data.cFileName;
    }
}

static inline void ax_os_dir_close(ax_os_dir_t* d) {
    if (d->valid) FindClose(d->h);
    d->valid = 0;
}
#else
typedef struct {
    DIR* d;
} ax_os_dir_t;

static inline int ax_os_dir_open(ax_os_dir_t* d, const char* path) {
    d->d = opendir(path);
    return d->d ? 0 : -1;
}

static inline const char* ax_os_dir_next(ax_os_dir_t* d) {
    if (!d->d) return NULL;
    struct dirent* e;
    while ((e = readdir(d->d)) != NULL) {
        if (strcmp(e->d_name, ".") == 0 || strcmp(e->d_name, "..") == 0) continue;
        return e->d_name;
    }
    return NULL;
}

static inline void ax_os_dir_close(ax_os_dir_t* d) {
    if (d->d) closedir(d->d);
    d->d = NULL;
}
#endif

/* ==== 5. Ortam değişkenleri ==== */
/* Çağıran `free()` etmelidir; yoksa NULL. */
static inline char* ax_os_getenv_dup(const char* key) {
    if (!key) return NULL;
#if defined(AXIOM_OS_WINDOWS)
    char* buf = NULL;
    size_t len = 0;
    if (_dupenv_s(&buf, &len, key) != 0) return NULL;
    return buf;
#else
    const char* v = getenv(key);
    if (!v) return NULL;
    size_t n = strlen(v);
    char* out = (char*)malloc(n + 1);
    if (!out) return NULL;
    memcpy(out, v, n + 1);
    return out;
#endif
}

/* ==== 6. Süreç ==== */
static inline long long ax_os_getpid(void) {
#if defined(AXIOM_OS_WINDOWS)
    return (long long)_getpid();
#else
    return (long long)getpid();
#endif
}

static inline int ax_os_sleep_ms(long long ms) {
#if defined(AXIOM_OS_WINDOWS)
    Sleep((DWORD)ms);
    return 0;
#else
    struct timespec ts;
    ts.tv_sec = (time_t)(ms / 1000);
    ts.tv_nsec = (long)((ms % 1000) * 1000000L);
    return nanosleep(&ts, NULL);
#endif
}

/* ==== 7. Ağ ==== */
#if defined(AXIOM_OS_WINDOWS)
typedef SOCKET ax_socket_t;
#  define AX_INVALID_SOCKET INVALID_SOCKET
#else
typedef int ax_socket_t;
#  define AX_INVALID_SOCKET (-1)
#endif

static inline void ax_os_net_init(void) {
#if defined(AXIOM_OS_WINDOWS)
    static volatile long done = 0;
    if (__atomic_load_n(&done, __ATOMIC_ACQUIRE) == 0) {
        WSADATA wsa;
        if (WSAStartup(MAKEWORD(2, 2), &wsa) == 0) {
            __atomic_store_n(&done, 1, __ATOMIC_RELEASE);
        }
    }
#endif
}

/* Program baslamadan once ag altyapisini hazirla (Windows'ta WSAStartup).
 * MSVC'de constructor yok; orada socket sarmalayicilari tembel baslatir. */
#if defined(__GNUC__) || defined(__clang__)
__attribute__((constructor))
static void ax_os_net_bootstrap(void) { ax_os_net_init(); }
#endif

static inline int ax_os_sock_valid(ax_socket_t s) {
    return s != AX_INVALID_SOCKET;
}

static inline void ax_os_sock_close(ax_socket_t s) {
#if defined(AXIOM_OS_WINDOWS)
    if (s != INVALID_SOCKET) closesocket(s);
#else
    if (s >= 0) close(s);
#endif
}


static inline int ax_os_sock_last_error(void) {
#if defined(AXIOM_OS_WINDOWS)
    return WSAGetLastError();
#else
    return errno;
#endif
}

static inline int ax_os_sock_would_block(int err) {
#if defined(AXIOM_OS_WINDOWS)
    return err == WSAEWOULDBLOCK || err == WSAEINPROGRESS;
#else
    return err == EWOULDBLOCK || err == EAGAIN || err == EINPROGRESS;
#endif
}

/* Guvenli soket olusturma: ag altyapisi hazir mi diye once kontrol eder. */
static inline ax_socket_t ax_os_socket(int domain, int type, int protocol) {
    ax_os_net_init();
    return socket(domain, type, protocol);
}

/* Soket -> ax_int (Axiom FD tipi) dönüşümleri */
static inline long long ax_os_sock_to_int(ax_socket_t s) {
    return (long long)(intptr_t)s;
}
static inline ax_socket_t ax_os_int_to_sock(long long v) {
    return (ax_socket_t)(intptr_t)v;
}
static inline void ax_os_close_sock_int(int fd) {
    ax_os_sock_close(ax_os_int_to_sock(fd));
}

/* Soket yazma/okuma (Windows'ta char* farkı için sarmalayıcı) */
static inline long long ax_os_sock_send(ax_socket_t s, const char* buf, size_t len) {
    return (long long)send(s, buf, (int)len, 0);
}
static inline long long ax_os_sock_recv(ax_socket_t s, char* buf, size_t len) {
    return (long long)recv(s, buf, (int)len, 0);
}

static inline int ax_os_sock_set_nonblocking(ax_socket_t s, int on) {
#if defined(AXIOM_OS_WINDOWS)
    u_long mode = on ? 1 : 0;
    return ioctlsocket(s, FIONBIO, &mode);
#else
    int flags = fcntl(s, F_GETFL, 0);
    if (flags < 0) return -1;
    if (on) flags |= O_NONBLOCK; else flags &= ~O_NONBLOCK;
    return fcntl(s, F_SETFL, flags);
#endif
}

static inline int ax_os_sock_shutdown_write(ax_socket_t s) {
#if defined(AXIOM_OS_WINDOWS)
    return shutdown(s, SD_SEND);
#else
    return shutdown(s, SHUT_WR);
#endif
}

/* poll: Windows'ta WSAPoll, POSIX'te poll */
static inline int ax_os_poll_read(ax_socket_t s, int timeout_ms) {
#if defined(AXIOM_OS_WINDOWS)
    WSAPOLLFD pfd;
    pfd.fd = s;
    pfd.events = POLLRDNORM;
    pfd.revents = 0;
    return WSAPoll(&pfd, 1, timeout_ms);
#else
    struct pollfd pfd;
    pfd.fd = s;
    pfd.events = POLLIN;
    pfd.revents = 0;
    return poll(&pfd, 1, timeout_ms);
#endif
}

/* ==== 8. Yürütülebilir bellek (Linux/macOS) ==== */
/* RW tahsisi (sonradan PROT_EXEC verilebilir). */
static inline void* ax_os_alloc_exec(size_t size) {
#if defined(AXIOM_OS_WINDOWS)
    return VirtualAlloc(NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
#else
    void* p = mmap(NULL, size, PROT_READ | PROT_WRITE,
                   MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);
    return (p == MAP_FAILED) ? NULL : p;
#endif
}

/* Dogrudan calistirilabilir (RWX) tahsis — exec_mem_run icin. */
static inline void* ax_os_alloc_rwx(size_t size) {
#if defined(AXIOM_OS_WINDOWS)
    return VirtualAlloc(NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
#else
    void* p = mmap(NULL, size, PROT_READ | PROT_WRITE | PROT_EXEC,
                   MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);
    return (p == MAP_FAILED) ? NULL : p;
#endif
}

static inline void ax_os_free_exec(void* p, size_t size) {
#if defined(AXIOM_OS_WINDOWS)
    (void)size;
    if (p) VirtualFree(p, 0, MEM_RELEASE);
#else
    if (p) munmap(p, size);
#endif
}

/* 1=R, 2=W, 4=X */
static inline int ax_os_protect_exec(void* p, size_t size, int prot) {
#if defined(AXIOM_OS_WINDOWS)
    (void)p; (void)size; (void)prot;
    return 0;
#else
    int m = 0;
    if (prot & 1) m |= PROT_READ;
    if (prot & 2) m |= PROT_WRITE;
    if (prot & 4) m |= PROT_EXEC;
    return mprotect(p, size, m) == 0 ? 1 : 0;
#endif
}

/* ==== 6b. Süreç çalıştırma (kabuksuz argv) ==== */
/* argv NULL ile biten dizi. Dönüş: çıkış kodu, hata -1.
 * POSIX: fork+execvp (kabuk yok -> komut enjeksiyonu yok).
 * Windows: CreateProcessA ile aynı semantik. */
static inline long long ax_os_run_argv(char* const* argv) {
    if (!argv || !argv[0]) return -1;
#if defined(AXIOM_OS_WINDOWS)
    /* Windows'ta argv'yi tek komut satırına çevir (tırnaklama ile). */
    size_t total = 0;
    for (int i = 0; argv[i]; i++) total += strlen(argv[i]) * 2 + 4;
    char* cmdline = (char*)malloc(total + 1);
    if (!cmdline) return -1;
    cmdline[0] = '\0';
    for (int i = 0; argv[i]; i++) {
        if (i > 0) strcat(cmdline, " ");
        int need_quote = strchr(argv[i], ' ') != NULL;
        if (need_quote) strcat(cmdline, "\"");
        strcat(cmdline, argv[i]);
        if (need_quote) strcat(cmdline, "\"");
    }
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    memset(&si, 0, sizeof(si));
    si.cb = sizeof(si);
    memset(&pi, 0, sizeof(pi));
    BOOL ok = CreateProcessA(NULL, cmdline, NULL, NULL, FALSE, 0,
                             NULL, NULL, &si, &pi);
    free(cmdline);
    if (!ok) return -1;
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 1;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    return (long long)code;
#else
    pid_t pid = fork();
    if (pid < 0) return -1;
    if (pid == 0) {
        execvp(argv[0], argv);
        _exit(127);
    }
    int status = 0;
    if (waitpid(pid, &status, 0) < 0) return -1;
    if (WIFEXITED(status)) return (long long)WEXITSTATUS(status);
    if (WIFSIGNALED(status)) return (long long)(128 + WTERMSIG(status));
    return (long long)status;
#endif
}

/* Kabuk üzerinden çalıştır (yalnızca os_exec için; komut enjeksiyonuna açıktır,
 * bu yüzden dil tarafında `os_exec_argv` tercih edilir). */
static inline long long ax_os_run_shell(const char* cmd) {
    if (!cmd) return -1;
#if defined(AXIOM_OS_WINDOWS)
    char* buf = (char*)malloc(strlen(cmd) + 8);
    if (!buf) return -1;
    sprintf(buf, "cmd /C %s", cmd);
    char* av[4];
    av[0] = (char*)"cmd";
    av[1] = (char*)"/C";
    av[2] = (char*)cmd;
    av[3] = NULL;
    (void)buf;
    free(buf);
    return ax_os_run_argv(av);
#else
    char* av[4];
    av[0] = (char*)"sh";
    av[1] = (char*)"-c";
    av[2] = (char*)cmd;
    av[3] = NULL;
    return ax_os_run_argv(av);
#endif
}

/* ==== 6b-2. Arka planda başlatma ==== */
/* Dönüş: çocuk süreç kimliği (POSIX) veya süreç tanıtıcısı (Windows), hata -1. */
static inline long long ax_os_spawn_bg(const char* cmd) {
    if (!cmd) return -1;
#if defined(AXIOM_OS_WINDOWS)
    size_t n = strlen(cmd) + 16;
    char* buf = (char*)malloc(n);
    if (!buf) return -1;
    snprintf(buf, n, "cmd /C %s", cmd);
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    memset(&si, 0, sizeof(si));
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    memset(&pi, 0, sizeof(pi));
    BOOL ok = CreateProcessA(NULL, buf, NULL, NULL, FALSE,
                             CREATE_NO_WINDOW, NULL, NULL, &si, &pi);
    free(buf);
    if (!ok) return -1;
    long long id = (long long)pi.dwProcessId;
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    return id;
#else
    pid_t pid = fork();
    if (pid < 0) return -1;
    if (pid == 0) {
        setsid();
        int devnull = open("/dev/null", O_RDWR);
        if (devnull >= 0) {
            dup2(devnull, STDIN_FILENO);
            dup2(devnull, STDOUT_FILENO);
            dup2(devnull, STDERR_FILENO);
            if (devnull > 2) close(devnull);
        }
        execl("/bin/sh", "sh", "-c", cmd, (char*)NULL);
        _exit(127);
    }
    return (long long)pid;
#endif
}

/* ==== 6c. Dinamik kütüphane yükleme ==== */
#if defined(AXIOM_OS_WINDOWS)
typedef HMODULE ax_lib_t;
static inline ax_lib_t ax_os_lib_open(const char* name) {
    ax_lib_t h = LoadLibraryA(name);
    return h ? h : NULL;
}
static inline void* ax_os_lib_sym(ax_lib_t h, const char* name) {
    return h ? (void*)GetProcAddress(h, name) : NULL;
}
static inline void ax_os_lib_close(ax_lib_t h) { if (h) FreeLibrary(h); }
#  define AX_LIB_PREFIX ""
#  define AX_LIB_SUFFIX ".dll"
#  define AX_LIB_GLOBAL 0
#else
#  include <dlfcn.h>
typedef void* ax_lib_t;
static inline ax_lib_t ax_os_lib_open(const char* name) { return dlopen(name, RTLD_LAZY | RTLD_GLOBAL); }
static inline void* ax_os_lib_sym(ax_lib_t h, const char* name) { return h ? dlsym(h, name) : NULL; }
static inline void ax_os_lib_close(ax_lib_t h) { if (h) dlclose(h); }
#  define AX_LIB_PREFIX "lib"
#  define AX_LIB_SUFFIX ".so"
#  define AX_LIB_GLOBAL RTLD_GLOBAL
#endif

/* ==== 6d. Süreç sonlandırma ==== */
static inline int ax_os_kill(long long pid, int sig) {
#if defined(AXIOM_OS_WINDOWS)
    (void)sig;
    HANDLE h = OpenProcess(PROCESS_TERMINATE, FALSE, (DWORD)pid);
    if (!h) return -1;
    int ok = TerminateProcess(h, 1) ? 0 : -1;
    CloseHandle(h);
    return ok;
#else
    return kill((pid_t)pid, sig);
#endif
}

/* ==== 7d. Ham fd (pipe vb.) yazma/okuma ==== */
static inline long long ax_os_fd_write(long long fd, const char* data, size_t len) {
#if defined(AXIOM_OS_WINDOWS)
    return (long long)_write((int)fd, data, (unsigned int)len);
#else
    return (long long)write((int)fd, data, len);
#endif
}

static inline long long ax_os_fd_read(long long fd, char* buf, size_t len) {
#if defined(AXIOM_OS_WINDOWS)
    return (long long)_read((int)fd, buf, (unsigned int)len);
#else
    return (long long)read((int)fd, buf, len);
#endif
}

static inline int ax_os_pipe(int fds[2]) {
#if defined(AXIOM_OS_WINDOWS)
    return _pipe(fds, 4096, _O_BINARY);
#else
    return pipe(fds);
#endif
}

/* Windows'ta socketpair() yoktur. Ayni semantigi saglamak icin loopback
 * TCP cifti kurulur (AF_UNIX yalnizca Win10+ ve sinirli). */
static inline int ax_os_socketpair(int sv[2]) {
#if defined(AXIOM_OS_WINDOWS)
    SOCKET listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener == INVALID_SOCKET) return -1;
    struct sockaddr_in a;
    int alen = (int)sizeof(a);
    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    a.sin_port = 0;
    if (bind(listener, (struct sockaddr*)&a, sizeof(a)) != 0 ||
        listen(listener, 1) != 0 ||
        getsockname(listener, (struct sockaddr*)&a, &alen) != 0) {
        closesocket(listener);
        return -1;
    }
    SOCKET c1 = socket(AF_INET, SOCK_STREAM, 0);
    if (c1 == INVALID_SOCKET) { closesocket(listener); return -1; }
    if (connect(c1, (struct sockaddr*)&a, sizeof(a)) != 0) {
        closesocket(c1); closesocket(listener); return -1;
    }
    SOCKET c2 = accept(listener, NULL, NULL);
    closesocket(listener);
    if (c2 == INVALID_SOCKET) { closesocket(c1); return -1; }
    sv[0] = (int)c1;
    sv[1] = (int)c2;
    return 0;
#else
    return socketpair(AF_UNIX, SOCK_STREAM, 0, sv);
#endif
}

static inline int ax_os_close_fd(int fd) {
#if defined(AXIOM_OS_WINDOWS)
    return _close(fd);
#else
    return close(fd);
#endif
}

/* ==== 7c. Soket poll (yazma yönü) ve SO_ERROR ==== */
static inline int ax_os_poll_write(ax_socket_t s, int timeout_ms) {
#if defined(AXIOM_OS_WINDOWS)
    WSAPOLLFD pfd;
    pfd.fd = s;
    pfd.events = POLLWRNORM;
    pfd.revents = 0;
    return WSAPoll(&pfd, 1, timeout_ms);
#else
    struct pollfd pfd;
    pfd.fd = s;
    pfd.events = POLLOUT;
    pfd.revents = 0;
    return poll(&pfd, 1, timeout_ms);
#endif
}

static inline int ax_os_sock_get_error(ax_socket_t s) {
    int err = 0;
#if defined(AXIOM_OS_WINDOWS)
    int len = (int)sizeof(err);
    if (getsockopt(s, SOL_SOCKET, SO_ERROR, (char*)&err, &len) != 0) return -1;
#else
    socklen_t len = sizeof(err);
    if (getsockopt(s, SOL_SOCKET, SO_ERROR, &err, &len) != 0) return -1;
#endif
    return err;
}

static inline int ax_os_inprogress_error(void) {
#if defined(AXIOM_OS_WINDOWS)
    return WSAEWOULDBLOCK;
#else
    return EINPROGRESS;
#endif
}

/* ==== 7a. Soket seçenekleri (int ve süre) ==== */
static inline int ax_os_sock_set_int_opt(ax_socket_t s, int level, int opt, int value) {
#if defined(AXIOM_OS_WINDOWS)
    return setsockopt(s, level, opt, (const char*)&value, (int)sizeof(value));
#else
    return setsockopt(s, level, opt, &value, (socklen_t)sizeof(value));
#endif
}

/* SO_REUSEPORT yalnizca bazi platformlarda var; yoksa sessizce atlanir
 * (SO_REUSEADDR zaten ayarlandi). */
static inline void ax_os_sock_set_reuse(ax_socket_t s) {
    ax_os_sock_set_int_opt(s, SOL_SOCKET, SO_REUSEADDR, 1);
#if defined(SO_REUSEPORT)
    ax_os_sock_set_int_opt(s, SOL_SOCKET, SO_REUSEPORT, 1);
#endif
}

/* ==== 7b. Soket zaman aşımı (platforma göre farklı tip) ==== */
static inline int ax_os_sock_set_timeout(ax_socket_t s, long long ms) {
#if defined(AXIOM_OS_WINDOWS)
    DWORD v = (DWORD)ms;
    int ok1 = setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, (const char*)&v, sizeof(v));
    int ok2 = setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, (const char*)&v, sizeof(v));
    return (ok1 == 0 && ok2 == 0) ? 0 : -1;
#else
    struct timeval tv;
    tv.tv_sec = (time_t)(ms / 1000);
    tv.tv_usec = (suseconds_t)((ms % 1000) * 1000);
    int ok1 = setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    int ok2 = setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
    return (ok1 == 0 && ok2 == 0) ? 0 : -1;
#endif
}

/* ==== 8b. CPUID (x86 özellik denetimi) ==== */
#if (defined(__x86_64__) || defined(_M_X64) || defined(__i386__) || defined(_M_IX86))
#  if defined(AXIOM_OS_WINDOWS)
#    include <intrin.h>
static inline int ax_os_cpuid(unsigned int leaf, unsigned int subleaf,
                              unsigned int* a, unsigned int* b,
                              unsigned int* c, unsigned int* d) {
    int regs[4];
    __cpuidex(regs, (int)leaf, (int)subleaf);
    *a = (unsigned int)regs[0]; *b = (unsigned int)regs[1];
    *c = (unsigned int)regs[2]; *d = (unsigned int)regs[3];
    return 1;
}
/* _xgetbv, -mxsave olmadan inline edilemez; hedef niteligiyle yerelde acilir. */
__attribute__((target("xsave")))
static inline unsigned long long ax_os_read_xcr0(void) {
    return _xgetbv(0);
}
#  else
#    include <cpuid.h>
static inline int ax_os_cpuid(unsigned int leaf, unsigned int subleaf,
                              unsigned int* a, unsigned int* b,
                              unsigned int* c, unsigned int* d) {
    return __get_cpuid_count(leaf, subleaf, a, b, c, d) ? 1 : 0;
}
__attribute__((target("xsave")))
static inline unsigned long long ax_os_read_xcr0(void) {
    unsigned int lo, hi;
    __asm__ __volatile__("xgetbv" : "=a"(lo), "=d"(hi) : "c"(0));
    return ((unsigned long long)hi << 32) | lo;
}
#  endif
#endif

/* ==== 9. Statik işaretçi tespiti (string sahipliği için) ==== */
static inline int ax_os_ptr_is_static(const void* p);

#if defined(AXIOM_OS_LINUX)
#  include <dlfcn.h>
#  include <link.h>
typedef struct { uintptr_t lo; uintptr_t hi; } ax_seg_t;
#define AX_MAX_STATIC_SEGS 96
static ax_seg_t g_ax_plat_segs[AX_MAX_STATIC_SEGS];
static int g_ax_plat_seg_count = -1;
static pthread_once_t g_ax_plat_seg_once = PTHREAD_ONCE_INIT;

static int ax_plat_seg_collect(struct dl_phdr_info* info, size_t size, void* data) {
    (void)size; (void)data;
    for (int i = 0; i < info->dlpi_phnum && g_ax_plat_seg_count < AX_MAX_STATIC_SEGS; i++) {
        const ElfW(Phdr)* ph = &info->dlpi_phdr[i];
        if (ph->p_type != PT_LOAD) continue;
        if (ph->p_flags & PF_X) continue;
        uintptr_t lo = (uintptr_t)info->dlpi_addr + (uintptr_t)ph->p_vaddr;
        g_ax_plat_segs[g_ax_plat_seg_count].lo = lo;
        g_ax_plat_segs[g_ax_plat_seg_count].hi = lo + (uintptr_t)ph->p_memsz;
        g_ax_plat_seg_count++;
    }
    return 0;
}

static void ax_plat_seg_init(void) {
    g_ax_plat_seg_count = 0;
    dl_iterate_phdr(ax_plat_seg_collect, NULL);
}

static inline int ax_os_ptr_is_static(const void* p) {
    if (g_ax_plat_seg_count < 0) pthread_once(&g_ax_plat_seg_once, ax_plat_seg_init);
    uintptr_t x = (uintptr_t)p;
    for (int i = 0; i < g_ax_plat_seg_count; i++) {
        if (x >= g_ax_plat_segs[i].lo && x < g_ax_plat_segs[i].hi) return 1;
    }
    return 0;
}

#elif defined(AXIOM_OS_WINDOWS)

static inline int ax_os_ptr_is_static(const void* p) {
    /* `VirtualQuery` ile sayfa tipi bakilir: MEM_IMAGE = calistirilabilir
     * dosyadan eslenmis bolge (.rdata/.data = literal ve statik veriler).
     * MEM_PRIVATE = heap/stack. Boylece literal korunurken heap isaretcileri
     * sahiplik takibine girer (POSIX'teki segment kontrolunun karsiligi). */
    MEMORY_BASIC_INFORMATION mbi;
    if (!p) return 0;
    if (VirtualQuery(p, &mbi, sizeof(mbi)) == 0) return 0;
    return mbi.Type == MEM_IMAGE;
}

#else /* macOS ve diğer */

#  include <dlfcn.h>
static inline int ax_os_ptr_is_static(const void* p) {
    Dl_info info;
    if (p && dladdr(p, &info) != 0) return 1;
    return 0;
}

#endif

#endif /* AXIOM_PLATFORM_H */
