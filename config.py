"""Configuration for the Realestate Com Au Scraper. Everything can be set
with an environment variable; the defaults work out of the box.

    PORT                     port the API listens on (default 8000)
    REALESTATE_COM_AU_PROXY  proxy URL for every request and for the Chrome
                             that passes Kasada, e.g. http://user:pass@host:port
                             (default: none — direct). From a home or office
                             connection you don't need one: a real Google
                             Chrome on this machine passes Kasada and every
                             request after that runs over plain HTTP. On a
                             cloud server, set a residential proxy (Australian
                             works best) — realestate.com.au refuses most
                             datacenter IPs.

Everything else below is a plain constant with a working default — edit it
here if you need to.
"""
import os

PORT = int(os.environ.get("PORT", "8000"))

# Retry policy for transport errors (every request).
MAX_RETRIES = 3
RETRY_BACKOFF = 2          # seconds, multiplied by the attempt number

# Kasada lets one Chrome-earned cookie serve ~65-110 pages, then refuses it
# for good. The scraper replaces it after this many pages, before the site
# says no, and once more at once whenever the site refuses it.
REALESTATE_COM_AU_IDENTITY_USES = 50
# Cookies tried per page: the current one, then one fresh one after a refusal.
REALESTATE_COM_AU_IDENTITIES = 2

REALESTATE_COM_AU_PROXY = os.environ.get("REALESTATE_COM_AU_PROXY") or None
REALESTATE_COM_AU_EXIT = "proxy" if REALESTATE_COM_AU_PROXY else "direct"


def realestate_com_au_proxy():
    """The proxy for one plain-HTTP session (None = direct)."""
    return os.environ.get("REALESTATE_COM_AU_PROXY") or None


def realestate_com_au_mint_proxy():
    """The proxy the Chrome that passes Kasada uses (None = direct)."""
    return os.environ.get("REALESTATE_COM_AU_PROXY") or None
