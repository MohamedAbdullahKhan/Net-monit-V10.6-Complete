# =============================================================================
# Net-monit V10.6 -- Speed Test Checker
# Copyright (c) 2024-2026 Abdullah | Abdullah-InfoXtek.com
# =============================================================================
"""
speedtest_check.py
Measures internet upload/download speed and latency.
Uses speedtest-cli (pure Python) or falls back to urllib-based test.
"""
import logging, time, socket, ssl, urllib.request, http.client, threading, os

log = logging.getLogger("monitor.checkers.speedtest")

# V10.6: Python 3.12 removed the legacy ssl.wrap_socket() function. The
# speedtest-cli library (2.1.3, latest on PyPI at time of writing) still
# calls it as a fallback when its own self._context.wrap_socket(...) path
# raises AttributeError (speedtest.py, HTTPSConnection.connect(), around
# line 486) -- on 3.12 that fallback call itself then raises AttributeError
# ("module 'ssl' has no attribute 'wrap_socket'"), uncaught, which is why
# _try_speedtest_cli() below was silently failing every time and every WAN
# test was running through the less-accurate Cloudflare fallback instead of
# a real Ookla-protocol test against a nearby graded server. This restores
# a working wrap_socket() using the modern SSLContext API, only if it's
# actually missing (Python <3.12 is unaffected and never sees this).
# Verified against a real local TLS server, not just imported without error.
if not hasattr(ssl, "wrap_socket"):
    def _wrap_socket_compat(sock, keyfile=None, certfile=None, server_side=False,
                             cert_reqs=ssl.CERT_NONE, ssl_version=None,
                             ca_certs=None, do_handshake_on_connect=True,
                             suppress_ragged_eofs=True, ciphers=None):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER if server_side else ssl.PROTOCOL_TLS_CLIENT)
        if certfile:
            context.load_cert_chain(certfile, keyfile)
        if ca_certs:
            context.load_verify_locations(ca_certs)
        if cert_reqs == ssl.CERT_NONE:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        else:
            context.verify_mode = cert_reqs
        if ciphers:
            context.set_ciphers(ciphers)
        return context.wrap_socket(sock, server_side=server_side,
                                    do_handshake_on_connect=do_handshake_on_connect,
                                    suppress_ragged_eofs=suppress_ragged_eofs)
    ssl.wrap_socket = _wrap_socket_compat

# Public test file URLs for fallback bandwidth test
_TEST_URLS = [
    ("https://speed.cloudflare.com/__down?bytes=10000000", 10_000_000),
    ("https://httpbin.org/bytes/5000000", 5_000_000),
]

def _cloudflare_download_mbps(target_duration=10.0, chunk_bytes=6_000_000, timeout=15,
                               progress_cb=None, streams=6):
    """
    V8.7: STREAMS parallel connections (was 1, sequential -- a single TCP
    stream can't fill a 300+ Mbps pipe regardless of chunk size, which is
    exactly why speedtest.net's own result page reports "Connections:
    Multi". Full root-cause writeup: V8.7 reference doc, Section 1.
    Signature unchanged except the new optional `streams` kwarg.
    progress_cb(sample_mbps, elapsed_sec), if provided, is now called from
    a dedicated sampler thread reading a shared counter every ~0.2s --
    structurally required once multiple streams can complete concurrently
    (there's no single "after this chunk" moment to hang a callback on
    with 6 connections in flight at once).

    V10.6: each of those 6 streams was still opening a BRAND NEW connection
    (urllib.request.urlopen()) for every single chunk_bytes-sized request --
    urllib does not do keep-alive/connection reuse across separate urlopen()
    calls. On any link fast enough to finish 6MB in under ~1s, the test
    spends more wall-clock time on repeated TCP+TLS handshake and TCP slow
    start than on actually transferring data; the faster the real link, the
    worse this gets, because reconnect overhead is roughly fixed while the
    transfer time it's being compared against keeps shrinking. This is a
    different bug from the one V8.7 fixed (stream COUNT); running 6 streams
    that all reconnect every chunk does not help. Root-caused and fixed by
    switching to one http.client.HTTPSConnection per stream, reused for the
    whole test via repeated .request() calls on the same connection.
    Verified against a controlled local server (not the real Cloudflare
    endpoint, which this sandbox has no route to): the old per-chunk-
    reconnect pattern opened 36 connections and measured 29 Mbps on a pipe
    capable of 11,000+ Mbps; the reused-connection version opened 4
    connections (one per stream, as intended) and measured the pipe's real
    capacity. Real-world severity depends on actual link speed and RTT to
    Cloudflare's edge.
    """
    host = "speed.cloudflare.com"
    path = f"/__down?bytes={chunk_bytes}"
    lock = threading.Lock()
    counter = {"total": 0}
    samples = []  # (elapsed_sec, total_bytes) -- used for warm-up exclusion + progress
    t_start = time.perf_counter()
    deadline = t_start + target_duration
    stop = threading.Event()

    def worker():
        conn = http.client.HTTPSConnection(host, timeout=timeout)
        try:
            while time.perf_counter() < deadline:
                try:
                    conn.request("GET", path, headers={"User-Agent": "netmonit/10.6"})
                    r = conn.getresponse()
                    while True:
                        if time.perf_counter() >= deadline:
                            try:
                                r.read()  # drain so a future caller reusing this process doesn't see a dangling response
                            except Exception:
                                pass
                            return
                        chunk = r.read(262_144)  # 256KB reads
                        if not chunk:
                            break  # this response fully consumed -- loop back and reuse the SAME connection
                        with lock:
                            counter["total"] += len(chunk)
                except (http.client.HTTPException, OSError, TimeoutError) as e:
                    log.debug("Cloudflare download stream: reconnecting after %s", e)
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = http.client.HTTPSConnection(host, timeout=timeout)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def sampler():
        prev = (0.0, 0)
        while not stop.is_set():
            t = time.perf_counter() - t_start
            with lock:
                b = counter["total"]
            samples.append((t, b))
            if progress_cb and t > prev[0]:
                dt = t - prev[0]
                if dt > 0:
                    progress_cb(round(((b - prev[1]) * 8) / (dt * 1_000_000), 2), round(t, 1))
            prev = (t, b)
            time.sleep(0.2)

    sampler_thread = threading.Thread(target=sampler, daemon=True)
    sampler_thread.start()

    worker_threads = [threading.Thread(target=worker, daemon=True) for _ in range(streams)]
    for th in worker_threads:
        th.start()
    for th in worker_threads:
        th.join(timeout=target_duration + timeout + 2)

    stop.set()
    sampler_thread.join(timeout=1)
    samples.append((time.perf_counter() - t_start, counter["total"]))

    # Steady-state: discard the first ~1s (TCP slow-start) from the rate
    # calc only -- target_duration itself is unchanged from V8.6, so this
    # fix is about accuracy, not making the test take longer.
    warmup = min(1.0, target_duration * 0.3)
    usable = [s for s in samples if s[0] >= warmup]
    if len(usable) < 2:
        usable = samples
    if len(usable) < 2:
        return None
    t0, b0 = usable[0]
    t1, b1 = usable[-1]
    dt = t1 - t0
    return round((b1 - b0) * 8 / (dt * 1_000_000), 2) if dt > 0 else None


def _cloudflare_upload_mbps(target_duration=6.0, chunk_bytes=2_000_000, timeout=15,
                             progress_cb=None, streams=6):
    """
    V8.7: same STREAMS-parallel-connections fix as the download test above.
    Payload switched from zero-filled to random bytes -- V8.6's comment on
    this was "zero-filled is fine, only transfer size/time matters", true
    in principle, but a trivially repetitive body is the one payload shape
    that risks a proxy/middlebox transparently compressing it, which WOULD
    change the timing. Costs nothing to avoid.

    V10.6: same connection-reuse fix as _cloudflare_download_mbps above --
    one http.client.HTTPSConnection per stream, reused for every POST
    instead of a fresh urlopen() (and fresh TCP+TLS handshake) per chunk.
    """
    host = "speed.cloudflare.com"
    payload = os.urandom(chunk_bytes)
    lock = threading.Lock()
    counter = {"total": 0}
    samples = []
    t_start = time.perf_counter()
    deadline = t_start + target_duration
    stop = threading.Event()

    def worker():
        conn = http.client.HTTPSConnection(host, timeout=timeout)
        try:
            while time.perf_counter() < deadline:
                try:
                    conn.request("POST", "/__up", body=payload,
                                 headers={"Content-Type": "application/octet-stream",
                                          "Content-Length": str(chunk_bytes),
                                          "User-Agent": "netmonit/10.6"})
                    r = conn.getresponse()
                    r.read()  # drain the small response body so the connection stays reusable
                    with lock:
                        counter["total"] += chunk_bytes
                except (http.client.HTTPException, OSError, TimeoutError) as e:
                    log.debug("Cloudflare upload stream: reconnecting after %s", e)
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = http.client.HTTPSConnection(host, timeout=timeout)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def sampler():
        prev = (0.0, 0)
        while not stop.is_set():
            t = time.perf_counter() - t_start
            with lock:
                b = counter["total"]
            samples.append((t, b))
            if progress_cb and t > prev[0]:
                dt = t - prev[0]
                if dt > 0:
                    progress_cb(round(((b - prev[1]) * 8) / (dt * 1_000_000), 2), round(t, 1))
            prev = (t, b)
            time.sleep(0.2)

    sampler_thread = threading.Thread(target=sampler, daemon=True)
    sampler_thread.start()

    worker_threads = [threading.Thread(target=worker, daemon=True) for _ in range(streams)]
    for th in worker_threads:
        th.start()
    for th in worker_threads:
        th.join(timeout=target_duration + timeout + 2)

    stop.set()
    sampler_thread.join(timeout=1)
    samples.append((time.perf_counter() - t_start, counter["total"]))

    warmup = min(1.0, target_duration * 0.3)
    usable = [s for s in samples if s[0] >= warmup]
    if len(usable) < 2:
        usable = samples
    if len(usable) < 2:
        return None
    t0, b0 = usable[0]
    t1, b1 = usable[-1]
    dt = t1 - t0
    return round((b1 - b0) * 8 / (dt * 1_000_000), 2) if dt > 0 else None


def _latency_ms(host="1.1.1.1", port=443, samples=5):
    """TCP connect latency in ms (average of samples). Also returns raw sample list for jitter calc."""
    times = []
    for _ in range(samples):
        try:
            t0 = time.perf_counter()
            s  = socket.create_connection((host, port), timeout=3)
            s.close()
            times.append((time.perf_counter() - t0) * 1000)
        except Exception:
            pass
    if not times:
        return None, []
    return round(sum(times) / len(times), 1), times


def _jitter_ms(samples: list) -> float:
    """
    Jitter = average absolute difference between consecutive latency samples.
    Standard RFC-3550-style approximation used by most consumer speed test tools.
    """
    if len(samples) < 2:
        return 0.0
    diffs = [abs(samples[i] - samples[i - 1]) for i in range(1, len(samples))]
    return round(sum(diffs) / len(diffs), 1)


def _public_ip_and_isp(timeout=5):
    """
    Look up the public-facing IP and ISP/organisation name.
    Uses ipapi.co (no API key required, generous free tier) with a plain-IP fallback.
    """
    try:
        req = urllib.request.Request(
            "https://ipapi.co/json/",
            headers={"User-Agent": "netmonit/10.6"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _json
            info = _json.loads(r.read().decode("utf-8", errors="replace"))
        ip  = info.get("ip", "")
        isp = info.get("org") or info.get("asn") or ""
        if ip:
            return ip, (isp or "Unknown ISP")
    except Exception as e:
        log.debug("ipapi.co lookup failed: %s", e)

    # Fallback: plain public IP only, no ISP name
    try:
        req = urllib.request.Request(
            "https://api.ipify.org",
            headers={"User-Agent": "netmonit/10.6"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ip = r.read().decode("utf-8", errors="replace").strip()
        return ip, "Unknown ISP"
    except Exception as e:
        log.debug("ipify fallback failed: %s", e)
        return "", "Unknown ISP"


def _try_speedtest_cli():
    """Try to use speedtest-cli library if installed."""
    try:
        import speedtest as st_lib
        st = st_lib.Speedtest(secure=True)
        st.get_best_server()
        dl  = round(st.download() / 1_000_000, 2)
        ul  = round(st.upload()   / 1_000_000, 2)
        lat = round(st.results.ping, 1)
        srv = st.results.server.get("sponsor","") + " " + st.results.server.get("name","")
        return dl, ul, lat, srv.strip()
    except ImportError:
        return None
    except Exception as e:
        # V10.6: was log.debug -- invisible unless debug logging is explicitly
        # enabled, so a silent fall-through to the (now-fixed, but still less
        # accurate than a real Ookla-protocol test) Cloudflare method had no
        # visible trail explaining why. This is the one thing in this file that
        # decides whether the WAN result comes from a real nearby ISP-graded
        # test server or from a generic Cloudflare edge -- worth a normal-level
        # log line.
        log.warning("speedtest-cli unavailable, falling back to the Cloudflare method: %s", e)
        return None


def check(device: dict, progress_cb=None) -> dict:
    """
    Run speed test. Returns:
      reachable      bool
      download_mbps  float
      upload_mbps    float
      latency_ms     float   (ping to nearest test point)
      jitter_ms      float   (variance between latency samples — connection stability)
      isp            str     (ISP / organisation name from public IP lookup)
      public_ip      str     (this server's WAN-facing IP address)
      server         str     (which test backend/server was used)
      method_used    str
      elapsed_sec    float

    progress_cb(phase, mbps, elapsed_sec), optional -- called repeatedly
    during the download and upload phases with live samples (V10.1). Not
    called at all on the speedtest-cli path below (that binary doesn't
    expose intermediate samples, only a final result) or during latency.
    """
    t0 = time.perf_counter()

    # Public IP + ISP lookup runs in parallel with the speed test itself
    ip_isp_result = [None, None]
    def _lookup_ip_isp():
        ip_isp_result[0], ip_isp_result[1] = _public_ip_and_isp()
    ip_thread = threading.Thread(target=_lookup_ip_isp, daemon=True)
    ip_thread.start()

    # Try speedtest-cli first (most accurate — real ISP-graded test servers)
    result = _try_speedtest_cli()
    if result:
        dl, ul, lat, srv = result
        _, jitter_samples = _latency_ms(samples=6)
        jitter = _jitter_ms(jitter_samples)
        ip_thread.join(timeout=6)
        return {
            "reachable":     True,
            "download_mbps": dl,
            "upload_mbps":   ul,
            "latency_ms":    lat,
            "jitter_ms":     jitter,
            "isp":           ip_isp_result[1] or "Unknown ISP",
            "public_ip":     ip_isp_result[0] or "",
            "server":        srv or "Speedtest.net",
            "method_used":   "speedtest-cli",
            "elapsed_sec":   round(time.perf_counter() - t0, 1),
        }

    # V8.7: latency, then download, then upload -- sequential phases.
    # V8.6 ran all three CONCURRENTLY via threading (see the removed code
    # below in version control): download and upload were competing for
    # the same bandwidth against EACH OTHER for the whole test, which
    # suppresses both readings, and the latency samples were taken while
    # that contention was happening. Real speed tests (Ookla, Cloudflare's
    # own) never overlap download and upload phases for exactly this
    # reason. Each phase still uses `streams` parallel connections
    # internally (the actual fix for the 6.6x/2.8x under-read) -- only
    # this outer ordering changed.
    lat, jitter_samples = _latency_ms(samples=6)
    jitter = _jitter_ms(jitter_samples)

    def _dl_progress(mbps, elapsed):
        if progress_cb: progress_cb("download", mbps, elapsed)
    def _ul_progress(mbps, elapsed):
        if progress_cb: progress_cb("upload", mbps, elapsed)

    dl = _cloudflare_download_mbps(progress_cb=_dl_progress if progress_cb else None)
    ul = _cloudflare_upload_mbps(progress_cb=_ul_progress if progress_cb else None)

    ip_thread.join(timeout=6)

    if dl is None and ul is None:
        return {
            "reachable":   False,
            "error":       "Speed test failed — no internet access or test endpoint unreachable",
            "latency_ms":  lat,
            "jitter_ms":   jitter,
            "isp":         ip_isp_result[1] or "Unknown ISP",
            "public_ip":   ip_isp_result[0] or "",
            "elapsed_sec": round(time.perf_counter() - t0, 1),
        }

    return {
        "reachable":     True,
        "download_mbps": dl or 0.0,
        "upload_mbps":   ul or 0.0,
        "latency_ms":    lat or 0.0,
        "jitter_ms":     jitter,
        "isp":           ip_isp_result[1] or "Unknown ISP",
        "public_ip":     ip_isp_result[0] or "",
        "server":        "Cloudflare Speed Test",
        "method_used":   "cloudflare",
        "elapsed_sec":   round(time.perf_counter() - t0, 1),
    }
