"""Reference resolvers, URL grammar and slug tables for /realestate-com-au/*.

ONE param per input (tripadvisor QueryOrIdField convention, never a sibling
`url` / `id` pair): every resolver takes a bare id / slug / free text OR a
www.realestate.com.au link for the same record and returns what the fetch
layer needs. Resolvers raise ValueError with a user-facing message (RefField
turns it into a 400).

Identifier shapes (captured 2026-10-30/31):
  * listing id   6-10 digits (152216904; rentals 440365388); the listing
                 page is /property-<type>-<state>-<suburb>-<id>, and the bare
                 /property-<id> canonicalises to it (sold listings live
                 under /sold/property-...). Ids are global across channels.
  * agent        /agent/<name-slug>-<salespersonId>; /agent/<id> redirects
  * agency       /agency/<name-slug>-<AGENCYID>; the id is 6 upper-case
                 letters (PCSWUZ); /agency/<ID> redirects
  * property     the address page /property/<address-slug>/
                 (1-buena-vista-ave-mosman-nsw-2088); the autocomplete's
                 address id reaches it through /property/lookup?id=<n>
  * suburb       /<state>/<suburb>-<postcode>/ (nsw/mosman-2088); the
                 agent / auction directories spell the same place
                 mosman-nsw-2088
  * search       /{buy|rent|sold}/[filters-]in-<location>/list-<page>?...
                 (see search_path); a location is "mosman,+nsw+2088",
                 "2088", "sydney+-+greater+region,+nsw" or "nsw"
"""
import re
from urllib.parse import parse_qs, quote, urlencode, urlparse

SITE = "https://www.realestate.com.au"
HOST_RE = re.compile(r"(^|\.)realestate\.com\.au$", re.I)

CHANNELS = ("buy", "rent", "sold")
STATES = ("nsw", "vic", "qld", "wa", "sa", "tas", "act", "nt")

# Public property-type value -> the site's path token. The site's own
# "unit+apartment" token covers both unit and apartment listings (resolved
# filter propertyTypes ["unit", "apartment"], 2026-10-31).
PROPERTY_TYPES = {
    "house": "house", "apartment": "unit+apartment", "unit": "unit+apartment",
    "townhouse": "townhouse", "villa": "villa", "land": "land", "acreage": "acreage",
    "rural": "rural", "retirement": "retire", "block_of_units": "unitblock",
}

# Public sort -> the site's activeSort token (only these five are honoured
# by the SSR page, 2026-10-31: the resolved sortType echoes them; price
# and date sorts for sold listings other than sold date are ignored).
SORTS = {
    "relevance": "relevance", "newest": "list-date", "price_asc": "price-asc",
    "price_desc": "price-desc", "sold_date": "solddate",
}

# Exclusion flags -> the site's `misc` tokens (all applied server-side on
# 2026-10-31; ex-deposit-taken is a rent filter).
EXCLUDES = {
    "exclude_under_contract": "ex-under-contract",
    "exclude_no_price": "ex-no-display-price",
    "exclude_auctions": "ex-auctions",
    "exclude_private_sales": "ex-private-sales",
    "exclude_deposit_taken": "ex-deposit-taken",
}

SUGGESTION_TYPES = ("suburb", "region", "postcode", "state", "street", "address")
SUGGEST_URL = "https://suggest.realestate.com.au/consumer-suggest/suggestions"
SCHOOLS_URL = "https://school-service.realestate.com.au/closest_by_type"

LISTING_ID_RE = re.compile(r"^[0-9]{6,10}$")
_LINK_LISTING_RE = re.compile(r"/(?:project/)?[^/?#]*?-([0-9]{6,10})(?:[/?#]|$)")
AGENT_ID_RE = re.compile(r"^[0-9]{1,10}$")
_LINK_AGENT_RE = re.compile(r"/agent/(?:[^/?#]*?-)?([0-9]{1,10})(?:[/?#]|$)")
AGENCY_ID_RE = re.compile(r"^[A-Z0-9]{4,8}$")
_LINK_AGENCY_RE = re.compile(r"/agency/(?:[^/?#]*?-)?([A-Za-z0-9]{4,8})(?:[/?#]|$)")
_LINK_PROPERTY_RE = re.compile(r"/property/([a-z0-9]+(?:-[a-z0-9]+)+)/?(?:[?#]|$)", re.I)
_LINK_LOOKUP_RE = re.compile(r"/property/lookup\?(?:.*&)?id=([0-9]+)")
PROPERTY_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*-(nsw|vic|qld|wa|sa|tas|act|nt)-[0-9]{4}$", re.I)
PLACE_SLUG_RE = re.compile(r"^([a-z0-9]+(?:-[a-z0-9]+)*)-(nsw|vic|qld|wa|sa|tas|act|nt)-([0-9]{4})$", re.I)
_LINK_SUBURB_RE = re.compile(r"/(nsw|vic|qld|wa|sa|tas|act|nt)/([a-z0-9]+(?:-[a-z0-9]+)*)-([0-9]{4})/?(?:[?#]|$)", re.I)
_LINK_SEARCH_RE = re.compile(r"^/(buy|rent|sold)/(.*?)(?:/list-([0-9]+))?/?$", re.I)
_LINK_FIND_AGENT_RE = re.compile(r"/find-(agent|agency)/([^/?#]+)")
_LINK_AUCTION_RE = re.compile(r"/auction-results/([^/?#]+)")
LATLNG_RE = re.compile(r"^(-?[0-9]{1,2}(?:\.[0-9]+)?)\s*,\s*(-?[0-9]{1,3}(?:\.[0-9]+)?)$")


def _link(value):
    """The parsed URL when `value` is a realestate.com.au link, else None;
    another site's link raises."""
    if not value.startswith(("http://", "https://", "//")):
        return None
    url = value if not value.startswith("//") else "https:" + value
    parsed = urlparse(url)
    if not HOST_RE.search(parsed.hostname or ""):
        raise ValueError("Must be a realestate.com.au link.")
    return parsed


def _place_text_to_slug(value):
    """"Mosman, NSW 2088" / "mosman nsw 2088" -> "mosman-nsw-2088"; None when
    the text is not a suburb + state + postcode."""
    words = re.findall(r"[a-z0-9]+", value.lower())
    if len(words) >= 3 and words[-1].isdigit() and len(words[-1]) == 4 and words[-2] in STATES:
        return "-".join(words)
    return None


# ---- listings ---------------------------------------------------------------------

def resolve_listing(value):
    """Bare listing id or any listing link -> the id."""
    value = (value or "").strip()
    if LISTING_ID_RE.match(value):
        return value
    link = _link(value)
    if link is not None:
        match = _LINK_LISTING_RE.search(link.path)
        if match:
            return match.group(1)
        raise ValueError("Must be a realestate.com.au listing link "
                         "(https://www.realestate.com.au/property-house-nsw-mosman-152216904).")
    raise ValueError("Must be a listing id (152216904) or a realestate.com.au listing link.")


def listing_link(listing_id):
    """The bare canonical form; the site redirects it to the full slug."""
    return f"{SITE}/property-{listing_id}"


def listing_path(listing_id):
    return f"/property-{listing_id}"


def project_path(listing_id):
    """A new-development project's page: /property-<id> is a 404 for a
    project id, /project/<id> redirects to /project/<slug>-<id> (2026-11-02)."""
    return f"/project/{listing_id}"


# ---- agents / agencies ----------------------------------------------------------------

def resolve_agent(value):
    """Bare salesperson id or an /agent/<slug>-<id> link -> the id."""
    value = (value or "").strip()
    if AGENT_ID_RE.match(value):
        return value
    link = _link(value)
    if link is not None:
        match = _LINK_AGENT_RE.search(link.path)
        if match:
            return match.group(1)
        raise ValueError("Must be a realestate.com.au agent link "
                         "(https://www.realestate.com.au/agent/david-murphy-58466).")
    raise ValueError("Must be an agent id (58466) or a realestate.com.au agent link.")


def agent_path(agent_id):
    return f"/agent/{agent_id}"


def resolve_agency(value):
    """Bare agency id (PCSWUZ) or an /agency/<slug>-<ID> link -> the id."""
    value = (value or "").strip()
    if AGENCY_ID_RE.match(value.upper()) and not value.isdigit():
        return value.upper()
    link = _link(value)
    if link is not None:
        match = _LINK_AGENCY_RE.search(link.path)
        if match:
            return match.group(1).upper()
        raise ValueError("Must be a realestate.com.au agency link "
                         "(https://www.realestate.com.au/agency/murphy-residential-PCSWUZ).")
    raise ValueError("Must be an agency id (PCSWUZ) or a realestate.com.au agency link.")


def agency_path(agency_id):
    return f"/agency/{agency_id}"


def resolve_directory_location(value):
    """A place for the agent / agency directories: "Mosman, NSW 2088",
    the slug mosman-nsw-2088, a region ("Sydney - Greater Region, NSW")
    or a /find-agent/... link -> the path segment the directory takes."""
    value = (value or "").strip()
    if not value:
        raise ValueError("Must not be empty.")
    link = _link(value)
    if link is not None:
        match = _LINK_FIND_AGENT_RE.search(link.path)
        if match:
            return match.group(2)
        raise ValueError("Must be a realestate.com.au find-agent link "
                         "(https://www.realestate.com.au/find-agent/mosman-nsw-2088).")
    if PLACE_SLUG_RE.match(value):
        return value.lower()
    slug = _place_text_to_slug(value)
    if slug:
        return slug
    return location_url_value(value)


# ---- the property address page ----------------------------------------------------------

def resolve_property(value):
    """An address slug (1-buena-vista-ave-mosman-nsw-2088), a /property/<slug>/
    link, or the autocomplete's numeric address id (also as a
    /property/lookup?id= link) -> the page path."""
    value = (value or "").strip()
    if value.isdigit():
        return f"/property/lookup?id={value}"
    if PROPERTY_SLUG_RE.match(value):
        return f"/property/{value.lower()}/"
    link = _link(value)
    if link is not None:
        match = _LINK_LOOKUP_RE.search(link.path + "?" + link.query)
        if match:
            return f"/property/lookup?id={match.group(1)}"
        match = _LINK_PROPERTY_RE.search(link.path)
        if match and PROPERTY_SLUG_RE.match(match.group(1)):
            return f"/property/{match.group(1).lower()}/"
        raise ValueError("Must be a realestate.com.au property page link "
                         "(https://www.realestate.com.au/property/1-buena-vista-ave-mosman-nsw-2088/).")
    raise ValueError("Must be a property address slug (1-buena-vista-ave-mosman-nsw-2088), "
                     "an address id from locations/autocomplete, or a realestate.com.au property page link.")


# ---- suburbs ------------------------------------------------------------------------------

def resolve_suburb(value):
    """"Mosman, NSW 2088", mosman-nsw-2088 or a /nsw/mosman-2088/ link -> the
    market-profile path /nsw/mosman-2088/."""
    value = (value or "").strip()
    link = _link(value)
    if link is not None:
        match = _LINK_SUBURB_RE.search(link.path)
        if match:
            return f"/{match.group(1).lower()}/{match.group(2).lower()}-{match.group(3)}/"
        raise ValueError("Must be a realestate.com.au suburb profile link "
                         "(https://www.realestate.com.au/nsw/mosman-2088/).")
    slug = value.lower() if PLACE_SLUG_RE.match(value) else _place_text_to_slug(value)
    if slug:
        suburb, state, postcode = PLACE_SLUG_RE.match(slug).groups()
        return f"/{state}/{suburb}-{postcode}/"
    raise ValueError("Must be a suburb as 'Mosman, NSW 2088' (or mosman-nsw-2088), "
                     "or a realestate.com.au suburb profile link.")


# ---- auction results ----------------------------------------------------------------------

def resolve_auction_location(value):
    """A state code (nsw), a suburb ("Mosman, NSW 2088" / mosman-nsw-2088)
    or an /auction-results/... link -> the page path."""
    value = (value or "").strip()
    link = _link(value)
    if link is not None:
        match = _LINK_AUCTION_RE.search(link.path)
        if match:
            return f"/auction-results/{match.group(1).lower()}"
        raise ValueError("Must be a realestate.com.au auction-results link "
                         "(https://www.realestate.com.au/auction-results/nsw).")
    low = value.lower()
    if low in STATES:
        return f"/auction-results/{low}"
    slug = low if PLACE_SLUG_RE.match(low) else _place_text_to_slug(value)
    if slug:
        return f"/auction-results/{slug}"
    raise ValueError("Must be a state code (nsw, vic, qld, wa, sa, tas, act, nt), a suburb as "
                     "'Mosman, NSW 2088', or a realestate.com.au auction-results link.")


# ---- search -------------------------------------------------------------------------------

def location_url_value(text):
    """Free text -> the site's location token: "Mosman, NSW 2088" ->
    "mosman,+nsw+2088"; "Sydney - Greater Region, NSW" ->
    "sydney+-+greater+region,+nsw"; several places joined by ";" ->
    "a;+b" (the site's own multi-locality separator)."""
    places = [" ".join(p.split()).lower() for p in text.split(";") if p.strip()]
    if not places:
        raise ValueError("Must not be empty.")
    return ";+".join(p.replace(" ", "+") for p in places)


def resolve_search_location(value):
    """The `location` of properties/search: free text (suburb, postcode,
    region, state, several joined by ";") -> {"location": <url token>};
    a pasted search link -> {"link": {channel, filters, page, query}} whose
    filters / sort / page are carried through (api.search_url)."""
    value = (value or "").strip()
    if not value:
        raise ValueError("Must not be empty.")
    link = _link(value)
    if link is None:
        return {"location": location_url_value(value)}
    match = _LINK_SEARCH_RE.match(link.path)
    if not match:
        raise ValueError("Must be a realestate.com.au search link "
                         "(https://www.realestate.com.au/buy/in-mosman,+nsw+2088/list-1).")
    channel, middle, page = match.group(1).lower(), match.group(2), match.group(3)
    query = {k: v[-1] for k, v in parse_qs(link.query, keep_blank_values=False).items()}
    return {"link": {"channel": channel, "filters": middle, "page": int(page) if page else 1, "query": query}}


def search_path(channel, location=None, link=None, page=1, property_types=None, beds_min=None, beds_max=None,
                baths_min=None, cars_min=None, price_min=None, price_max=None, land_min=None, land_max=None,
                keywords=None, sort=None, surrounding=None, excludes=None):
    """The search page path + query for one page. With `link` (a parsed
    search link from resolve_search_location) the link's own filter path and
    query are kept and only the explicit params override them.

    Path grammar (every piece verified server-side 2026-10-31):
      /<channel>/[property-<t1>-<t2>-][with-<n>-bedrooms-][between-<min>-<max>-]
                 [size-<min>-<max>-]in-<location>/list-<page>
      ?activeSort=..&includeSurrounding=false&keywords=a,b&misc=ex-..,ex-..
       &maxBeds=n&numBaths=n&numParkingSpaces=n
    `any` stands for an open upper bound and 0 for an open lower one."""
    query = {}
    if link:
        channel = link["channel"]
        middle = link["filters"]
        query.update(link.get("query") or {})
        query.pop("page", None)
    else:
        parts = []
        if property_types:
            parts.append("property-" + "-".join(property_types))
        if beds_min:
            parts.append(f"with-{beds_min}-bedrooms")
        if price_min is not None or price_max is not None:
            parts.append(f"between-{int(price_min or 0)}-{int(price_max) if price_max is not None else 'any'}")
        if land_min is not None or land_max is not None:
            parts.append(f"size-{int(land_min or 0)}-{int(land_max) if land_max is not None else 'any'}")
        parts.append(f"in-{location}")
        middle = "-".join(parts)
    if sort:
        query["activeSort"] = SORTS.get(sort, sort)
    if surrounding is False:
        query["includeSurrounding"] = "false"
    elif surrounding is True:
        query.pop("includeSurrounding", None)
    if keywords:
        query["keywords"] = ",".join(keywords)
    if beds_max:
        query["maxBeds"] = str(beds_max)
    if baths_min:
        query["numBaths"] = str(baths_min)
    if cars_min:
        query["numParkingSpaces"] = str(cars_min)
    if excludes:
        tokens = [EXCLUDES[name] for name in excludes if name in EXCLUDES]
        if tokens:
            query["misc"] = ",".join(tokens)
    # A pasted bare /buy/ link (all of Australia) has no filter segment.
    path = f"/{channel}/{middle}/list-{int(page)}" if middle else f"/{channel}/list-{int(page)}"
    if query:
        path += "?" + urlencode(query, safe="+,:-", quote_via=quote)
    return path


def is_site_link(value):
    try:
        return _link((value or "").strip()) is not None
    except ValueError:
        return False
