"""Mints the Kasada cookie that realestate_com_au/fetch.py replays over plain
HTTP, with a real Google Chrome (patchright) on this machine.

Every realestate.com.au page sits behind Kasada: a plain HTTP request gets a
429 challenge page. One Chrome opens the home page (through
REALESTATE_COM_AU_PROXY when it is set), solves Kasada's challenge, and keeps
the `KP_UIDz` cookie it earned. The Chrome closes right after; the cookie and
the browser's user agent are reused for ~50 pages, then a fresh one is minted
(realestate_com_au/fetch.py decides when). A mint takes ~10 seconds.

Same call shape as the hosted service's client (identity, invalidate,
headers_for, cookie_header and the three exceptions), so realestate_com_au/
runs unchanged.
"""
import threading
import time

import egress

SEED_URL = "https://www.realestate.com.au/"
ORIGIN = "https://www.realestate.com.au"
WAIT_FOR_COOKIE = "KP_UIDz"
RENDERED_MARKER = "window.ArgonautExchange"
TTL_SECONDS = 12 * 3600        # the cookie lives 24 h; its page budget runs out long before
CLEAR_TIMEOUT = 45             # seconds Chrome waits for Kasada to clear
REMINT_PER_MINUTE = 5          # stop a block from relaunching Chrome in a loop
# Trackers and ads Chrome skips while it passes Kasada (faster, less data).
BLOCK_HOSTS = ("*.doubleclick.net", "*.googletagmanager.com", "*.google-analytics.com",
               "*.googlesyndication.com", "*.facebook.net", "*.facebook.com", "*.adnxs.com",
               "*.demdex.net", "*.omtrdc.net", "*.adobedtm.com", "*.tealiumiq.com",
               "*.reagroupdata.com.au", "smetrics.realestate.com.au", "analytics.realestate.com.au",
               "*.newrelic.com", "*.nr-data.net", "*.criteo.com", "*.rubiconproject.com",
               "*.casalemedia.com", "*.pubmatic.com", "*.dotmetrics.net", "*.id5-sync.com",
               "*.adsrvr.org", "*.bing.com", "*.pinterest.com", "*.qualtrics.com")


class BoxUnavailable(Exception):
    """Chrome could not start on this machine (not installed, no display)."""


class BoxRefused(Exception):
    """Kasada did not let Chrome through on this connection."""


class RemintBudgetExceeded(Exception):
    """Too many cookies minted in the last minute."""


_cache = {}
_locks = {}
_locks_guard = threading.Lock()
_mints = []


def mint(site, proxy=None, variant=""):
    """Open Chrome on the home page, wait for Kasada to clear, return the identity."""
    try:
        from patchright_driver import PatchrightDriver
        driver = PatchrightDriver(proxy, headless=False, block_resources=("image", "font", "media"),
                                  block_hosts=BLOCK_HOSTS, geoip_timezone=False)
    except Exception as e:
        raise BoxUnavailable(f"could not start Chrome: {type(e).__name__}: {e}")
    try:
        driver.nav(SEED_URL, referer="https://www.google.com/", mode="blocked", challenge_markers=("KPSDK",))
        deadline = time.monotonic() + CLEAR_TIMEOUT
        while True:
            cookies = driver.call(lambda page: page.context.cookies(ORIGIN))
            names = {c["name"] for c in cookies}
            try:
                html = driver.content() or ""
            except Exception:
                html = ""
            if WAIT_FOR_COOKIE in names and RENDERED_MARKER in html:
                return {
                    "cookies": [{k: c[k] for k in ("name", "value", "domain", "path") if k in c} for c in cookies],
                    "user_agent": driver.evaluate("navigator.userAgent"),
                    # Kasada checks that the sec-ch-ua brands match the user
                    # agent: a replay without them is refused after one page
                    "client_hints": driver.evaluate(
                        "navigator.userAgentData ? navigator.userAgentData.toJSON() : null") or {},
                    "tokens": {},
                    "exit_ip": None,
                    "expires_at": time.time() + TTL_SECONDS,
                }
            if time.monotonic() >= deadline:
                raise BoxRefused(f"Kasada did not clear in {CLEAR_TIMEOUT}s (cookies: {sorted(names)}); "
                                 "on a cloud server set REALESTATE_COM_AU_PROXY to a residential proxy")
            time.sleep(1)
    except (BoxRefused, BoxUnavailable):
        raise
    except Exception as e:
        raise BoxRefused(f"Chrome failed while passing Kasada: {type(e).__name__}: {e}")
    finally:
        driver.close()


def _charge_budget():
    now = time.monotonic()
    _mints[:] = [t for t in _mints if t > now - 60]
    if len(_mints) >= REMINT_PER_MINUTE:
        raise RemintBudgetExceeded(f"{REMINT_PER_MINUTE} cookies minted in the last minute")
    _mints.append(now)


def identity(site, proxy=None, variant="", force=False):
    """The cached identity for (site, proxy), minting on a miss, expiry or
    `force`; one mint at a time, the other threads wait and reuse it."""
    key = (site, proxy, variant)
    now = time.time()
    ident = _cache.get(key)
    if not force and ident and ident["expires_at"] > now:
        return ident
    with _locks_guard:
        lock = _locks.setdefault(key, threading.Lock())
    with lock:
        ident = _cache.get(key)
        if not force and ident and ident["expires_at"] > time.time():
            return ident
        if force and ident and ident.get("minted_at", 0) > time.time() - 5:
            return ident               # a peer just minted a fresh one
        _charge_budget()
        ident = mint(site, proxy, variant)
        ident["minted_at"] = time.time()
        ident["proxy"] = proxy
        _cache[key] = ident
        return ident


def invalidate(site, proxy=None, variant=""):
    _cache.pop((site, proxy, variant), None)


def cookie_header(ident):
    return "; ".join(f"{c['name']}={c['value']}" for c in ident.get("cookies", []))


def headers_for(ident, **extra):
    """Request headers that make a plain-HTTP replay look like the Chrome that
    minted `ident`: its user agent, its client-hint brands and an Australian
    Accept-Language. `extra` adds or overrides (accept, referer...)."""
    out = {"user-agent": ident.get("user_agent") or "",
           "accept-language": egress.site_accept_language("realestate-com-au")}
    hints = ident.get("client_hints") or {}
    brands = hints.get("brands")
    if brands:
        out["sec-ch-ua"] = ", ".join(f'"{b.get("brand")}";v="{b.get("version")}"' for b in brands)
        out["sec-ch-ua-mobile"] = "?1" if hints.get("mobile") else "?0"
        if hints.get("platform"):
            out["sec-ch-ua-platform"] = f'"{hints["platform"]}"'
    out.update({k.lower(): v for k, v in extra.items() if v is not None})
    return {k: v for k, v in out.items() if v != ""}
