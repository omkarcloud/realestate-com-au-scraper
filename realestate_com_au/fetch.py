"""realestate.com.au transport: plain curl_cffi (impersonate chrome) with a
Kasada clearance cookie minted by a real Chrome on the browser box.

Kasada fronts every www page (search, listing, agent, agency, suburb,
property, auction results), the old mobile API (services.) and the lexa
GraphQL host: a bare request is HTTP 429 with the 700 B KPSDK bootstrap
page on every curl identity (chrome / safari17_0 / edge101) and every exit
(the pod's own IP, AU residential; AU datacenter exits draw Akamai 403
"Access Denied" instead). What passes is the `KP_UIDz` cookie a headed
Chrome earns on the home page (recipes/realestate_com_au.py, Ubuntu box,
minted through an AU residential exit so the browser speaks en-AU):

  * the cookie is NOT bound to the exit IP — pod probe 2026-10-31
    (scrapers-patchright-depl-68b5779f9c-7wt8m): a Mac-minted jar replayed
    200 on all 9 www surfaces from the pod's own IP, 2/2 datacenter ports
    and 1/2 AU residential ports (one residential exit was refused even
    with the cookie), so the replay rides the pod's own IP
    (config.REALESTATE_COM_AU_EXIT = "direct");
  * a cookie serves a BUDGET of pages, not a time: ~65 pages in a 90 s burst
    (2026-10-31, Mac) / ~110 spread over an hour, then every request is 429
    for good (the cookie's own 24 h Max-Age never comes into play). So the
    identity is rotated after REALESTATE_COM_AU_IDENTITY_USES pages, and a
    429 bootstrap forces a fresh mint at once (single-flight per site in
    browser_client; REMINT_PER_MINUTE caps a block loop);
  * a mint is ~11 s of box browser + a few hundred KB on the residential
    exit (images, fonts, media and trackers blocked).

Open hosts (no cookie, no challenge, every tier 200 from the pod):
  suggest.realestate.com.au/consumer-suggest/suggestions   (`src` required)
  school-service.realestate.com.au/closest_by_type?lat=&lon=&count=

Not-found pages are real HTTP 404s (an unknown listing / agent / agency /
suburb / property / find-agent place). A search for an unknown place is a
200 with the nearest fuzzy match (reported in the response's localities).

Failure taxonomy (scraper_errors, mapped to HTTP by route_glue):
  RealestateUpstreamError  transport failure / 5xx / page without state — retryable
  RealestateBlocked        Kasada 429 bootstrap / 403 on every identity    — retryable
  RealestateBadRequest     upstream 400                                     — never retried
  RealestateNotFound       HTTP 404                                         — never retried
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import browser_client
import config
import egress
from realestate_com_au.refs import SCHOOLS_URL, SITE, SUGGEST_URL
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError

IMPERSONATE = "chrome"
PAGE_TIMEOUT = 60          # search pages are 1.2-2 MB
JSON_TIMEOUT = 20
BOX_SITE = "realestate-com-au"     # recipes/realestate_com_au.py
STATE_MARKER = "window.ArgonautExchange"
KASADA_MARKERS = ("KPSDK", "x-kpsdk")

PAGE_ACCEPT = ("text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
               "image/apng,*/*;q=0.8")
JSON_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": egress.site_accept_language("realestate-com-au"),
    "origin": SITE,
    "referer": SITE + "/",
}


class RealestateUpstreamError(UpstreamError):
    """Transport failure / 5xx / a page without its state — retryable."""


class RealestateBlocked(RealestateUpstreamError, Blocked):
    """Kasada bootstrap (429) / 403 that a fresh identity did not clear — retryable."""


class RealestateBadRequest(BadRequest):
    """Upstream 400 — never retried."""


class RealestateNotFound(NotFound):
    """Listing / agent / agency / suburb / property / place does not exist."""


# One curl session per cheroot worker thread (a handle is never shared
# across threads); the cookie travels per request, so the session only
# carries keep-alive and the exit (config.realestate_com_au_proxy()).
_local = threading.local()


def _session():
    sess = getattr(_local, "session", None)
    if sess is None:
        from curl_cffi import requests as curl_requests
        sess = curl_requests.Session(impersonate=IMPERSONATE)
        proxy = config.realestate_com_au_proxy()
        if proxy:
            sess.proxies = {"http": proxy, "https": proxy}
        _local.session = sess
    return sess


def _drop_session():
    """Close the thread's session so the retry rides a fresh connection / exit."""
    sess = getattr(_local, "session", None)
    _local.session = None
    if sess is not None:
        try:
            sess.close()
        except Exception:
            pass


# ---- the Kasada identity -----------------------------------------------------------------
# One identity for the process at a time, minted on a fresh sticky AU
# residential exit (config.realestate_com_au_mint_proxy()) each time, used
# for REALESTATE_COM_AU_IDENTITY_USES pages, then replaced. browser_client
# caches the mint per (site, exit) and single-flights it, so a burst of
# threads hitting a spent identity causes one mint.

_ident_lock = threading.Lock()
# `ready` False until the first mint exit is drawn: with a "direct" mint
# exit the proxy is None for good, so the proxy alone cannot tell "never
# minted" from "minted on the box's own IP".
_ident = {"proxy": None, "uses": 0, "ready": False}


def _identity(force=False, refused=None):
    """The cached Kasada identity, re-minted when spent (its page budget)
    or when `force` reports that the identity minted on exit `refused`
    was refused by the site. The decision and the exit rotation happen
    under one lock, so a burst of threads that hit the same spent /
    refused identity rotates ONCE and the rest ride the fresh one
    (browser_client then single-flights the mint per exit). A peer that
    already rotated past `refused` makes the forced call a plain read.
    Mint failures map to the taxonomy."""
    with _ident_lock:
        spent = _ident["uses"] >= config.REALESTATE_COM_AU_IDENTITY_USES
        stale = force and (not _ident["ready"] or refused == _ident["proxy"])
        rotate = not _ident["ready"] or spent or stale
        if rotate:
            old = _ident["proxy"] if _ident["ready"] else None
            _ident["proxy"] = config.realestate_com_au_mint_proxy()
            _ident["uses"] = 0
            _ident["ready"] = True
            if old is not None and old != _ident["proxy"]:
                browser_client.invalidate(BOX_SITE, proxy=old)
        proxy = _ident["proxy"]
    try:
        return browser_client.identity(BOX_SITE, proxy=proxy, force=rotate)
    except browser_client.BoxUnavailable as e:
        raise RealestateUpstreamError(f"browser box unavailable for the Kasada cookie mint: {e}")
    except browser_client.BoxRefused as e:
        raise RealestateBlocked(f"the Kasada cookie mint did not pass on the browser box: {e}")
    except browser_client.RemintBudgetExceeded as e:
        raise RealestateBlocked(str(e))


def _charge(ident):
    with _ident_lock:
        if ident.get("proxy") == _ident["proxy"]:
            _ident["uses"] += 1


def _burn(ident):
    """The site refused this identity: forget it so the next call mints."""
    browser_client.invalidate(BOX_SITE, proxy=ident.get("proxy"))
    with _ident_lock:
        if ident.get("proxy") == _ident["proxy"]:
            _ident["uses"] = config.REALESTATE_COM_AU_IDENTITY_USES


def identity_status():
    """For logs / tests: the exit the current identity was minted on and
    how many pages it has served."""
    with _ident_lock:
        return dict(_ident)


# ---- pages ------------------------------------------------------------------------------------

def _is_kasada(resp):
    return resp.status_code == 429 or (resp.status_code == 200 and len(resp.content) < 5000
                                        and any(m in resp.text for m in KASADA_MARKERS))


def _classify(resp, label):
    status = resp.status_code
    if status == 404:
        raise RealestateNotFound(f"{label} not found")
    if status == 400:
        raise RealestateBadRequest(resp.text[:200])
    if status in (401, 403, 429):
        raise RealestateBlocked(f"HTTP {status} for {label}")
    if status != 200:
        raise RealestateUpstreamError(f"HTTP {status} for {label}")
    return resp.text


def fetch_page(path, label):
    """GET a www page with the Kasada identity; returns the HTML (with its
    ArgonautExchange state). Ladder: the current identity, then one fresh
    mint when the site refuses it (429 bootstrap / 403); a transport
    failure or a stateless 200 is retried MAX_RETRIES times on a fresh
    connection. 404 and 400 surface at once."""
    url = SITE + path
    last = None
    forced, refused = False, None
    for attempt in range(1, config.MAX_RETRIES + config.REALESTATE_COM_AU_IDENTITIES):
        ident = _identity(force=forced, refused=refused)
        forced, refused = False, None
        headers = browser_client.headers_for(ident, accept=PAGE_ACCEPT)
        headers["cookie"] = browser_client.cookie_header(ident)
        try:
            resp = _session().get(url, headers=headers, timeout=PAGE_TIMEOUT, allow_redirects=True)
        except Exception as e:
            last = RealestateUpstreamError(f"request failed: {type(e).__name__}: {e}")
            _drop_session()
            time.sleep(config.RETRY_BACKOFF * attempt)
            continue
        _charge(ident)
        if _is_kasada(resp) or resp.status_code == 403:
            _burn(ident)
            last = RealestateBlocked(f"Kasada refused the identity for {label} (HTTP {resp.status_code})")
            forced, refused = True, ident.get("proxy")
            continue
        text = _classify(resp, label)
        if STATE_MARKER not in text:
            last = RealestateUpstreamError(f"page without state for {label} ({len(text)} bytes)")
            _drop_session()
            continue
        return text
    raise last


# ---- open JSON hosts ----------------------------------------------------------------------------

def _get_json(url, params, label, headers=None):
    def once():
        try:
            resp = _session().get(url, params=params, headers=headers or JSON_HEADERS, timeout=JSON_TIMEOUT)
        except Exception as e:
            raise RealestateUpstreamError(f"request failed: {type(e).__name__}: {e}")
        text = _classify(resp, label)
        try:
            return resp.json()
        except Exception:
            raise RealestateUpstreamError(f"non-JSON response for {label}: {text[:120]}")
    last = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            return once()
        except RealestateUpstreamError as e:
            last = e
            _drop_session()
            if attempt < config.MAX_RETRIES:
                time.sleep(config.RETRY_BACKOFF * attempt)
    raise last


def fetch_suggestions(query, types, limit):
    """The search-box autocomplete (suggest.realestate.com.au). The `src`
    parameter is required by the host (400 without it)."""
    params = {"max": str(limit), "type": ",".join(types), "src": "homepage-web", "query": query}
    return _get_json(SUGGEST_URL, params, f"suggestions for {query!r}")


def fetch_schools(latitude, longitude, count):
    """The nearest schools by type around a point (school-service)."""
    params = {"lat": f"{latitude:.6f}", "lon": f"{longitude:.6f}", "count": str(count)}
    return _get_json(SCHOOLS_URL, params, f"schools near {latitude},{longitude}",
                     headers={"accept": "application/json", "accept-language": JSON_HEADERS["accept-language"]})
