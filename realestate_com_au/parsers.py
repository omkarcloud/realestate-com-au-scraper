"""realestate.com.au page / JSON payloads -> clean dicts. Pure functions, no
I/O (fixtures in realestate_com_au/fixtures/, captured 2026-10-30/31 and
trimmed to the <title>, the canonical link and the state script).

Every www page embeds its server-rendered state as ONE script:

    window.ArgonautExchange = {"<micro-frontend>": {"<key>": "<JSON string>"}}

whose string values are themselves JSON (sometimes JSON inside JSON), so
`state(html)` decodes recursively. The micro-frontend keys per page:

  search pages      resi-property_listing-experience-web.urqlClientCache.<hash>
                    .data.{buySearch|rentSearch|soldSearch}
                    -> resolvedQuery + results {totalResultsCount, pagination,
                       exact.items[].listing, surrounding.totalCount}
  listing page      same cache -> data.details.{listing, inspections, property,
                    relatedListings, recentSales, listingMetrics} and
                    data.components.details.components.<Component>.component
                    (features, NBN, highlights, agents with phone, agency copy)
  project page      same cache -> data.details.listing (ProjectProfile)
  /find-agent       resi-agent_customer-search-mfe.AGENT_SEARCH
  /find-agency      resi-agent_customer-search-mfe.AGENCY_SEARCH.agencySearch
  /agent/<id>       resi-agent_customer-profile-experience.{AGENT_PROFILE,
                    AGENT_PROFILE_LISTINGS}
  /agency/<id>      resi-agent_customer-profile-experience.AGENCY_PROFILE
  /<state>/<sub>/   resi-property_market-explorer.suburb_data.marketProfileBySlug
  /property/<slug>/ resi-property_property-profile.property_detail_data.propertyProfile
  /auction-results  resi-property_sales-events-web.{state|location}.body

Image URLs are templates ("https://i2.au.reastatic.net/{size}/<hash>/image.jpg");
the parsers fill the site's own large size so every link is fetchable.
"""
import json
import re
from datetime import datetime
from html import unescape

from realestate_com_au.refs import SITE

_STATE_RE = re.compile(r"window\.ArgonautExchange\s*=\s*(\{.*?\})\s*;?\s*</script>", re.S)
_TITLE_RE = re.compile(r"<title>([^<]*)</title>", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>", re.I)
# The k / m shorthand only counts as a whole word ("$7.95m", "$2.5 million",
# "$500k+"), never the first letter of what follows ("$3,000 Monthly").
_MONEY_RE = re.compile(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)(?:\s*([kKmM])(?:illion|il)?(?![A-Za-z]))?")
_DATE_RE = re.compile(r"([0-9]{1,2}) ([A-Za-z]{3,9}),? ([0-9]{4})")
_ISO_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}")

IMAGE_SIZE = "1144x888"          # the site's own detail-gallery size
LOGO_SIZE = "340x64"
PHOTO_SIZE = "400x400"
_CID_RE = re.compile(r"\?cid=\{cid\}$")


# ---- the page state ------------------------------------------------------------------

def _deep(value):
    if isinstance(value, str):
        text = value.strip()
        if text[:1] in "{[":
            try:
                return _deep(json.loads(text))
            except ValueError:
                return value
        return value
    if isinstance(value, dict):
        return {k: _deep(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep(v) for v in value]
    return value


def state(html):
    """The decoded window.ArgonautExchange object, or None when the page
    carries none (a 404 page, the Kasada bootstrap page)."""
    match = _STATE_RE.search(html or "")
    if not match:
        return None
    raw = match.group(1)
    try:
        data = json.loads(raw)
    except ValueError:
        try:
            data = json.loads(raw[:raw.rfind("}") + 1])
        except ValueError:
            return None
    return _deep(data)


def page_title(html):
    match = _TITLE_RE.search(html or "")
    return unescape(match.group(1)).strip() if match else ""


def _listing_data(st):
    """The urql cache entry's `data` of a listing-experience page."""
    cache = _get(st, "resi-property_listing-experience-web", "urqlClientCache")
    if not isinstance(cache, dict):
        return None
    for entry in cache.values():
        data = (entry or {}).get("data") if isinstance(entry, dict) else None
        if isinstance(data, dict):
            return data
    return None


# ---- value helpers ---------------------------------------------------------------------

def _get(obj, *path, default=None):
    for key in path:
        if isinstance(obj, dict):
            obj = obj.get(key)
        elif isinstance(obj, list) and isinstance(key, int) and -len(obj) <= key < len(obj):
            obj = obj[key]
        else:
            return default
        if obj is None:
            return default
    return obj


def _int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        digits = value.replace(",", "").strip()
        try:
            return int(float(digits))
        except ValueError:
            return None
    return None


def _float(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").replace("%", "").strip())
        except ValueError:
            return None
    return None


def text(value):
    """Listing copy with <br/> as newlines and other tags dropped; None when
    empty."""
    if not isinstance(value, str):
        return None
    cleaned = _TAG_RE.sub("", _BR_RE.sub("\n", value))
    cleaned = unescape(cleaned).replace("\r", "")
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned or None


_SUFFIX_SCALE = {"k": 1_000, "m": 1_000_000}


def _amounts(display):
    """Every "$<n>[k|m]" in `display` as (number, multiplier). A range whose
    shorthand sits on the last figure only ("$1.9 - $2.0 million") lends it
    to the bare small figures before it."""
    found = []
    for match in _MONEY_RE.finditer(display):
        amount = float(match.group(1).replace(",", ""))
        found.append([amount, _SUFFIX_SCALE.get((match.group(2) or "").lower(), 1)])
    if found and found[-1][1] != 1:
        for row in found[:-1]:
            if row[1] == 1 and row[0] < 1_000:
                row[1] = found[-1][1]
    out = []
    for amount, scale in found:
        amount *= scale
        out.append(int(amount) if amount == int(amount) else amount)
    return out


def money(display):
    """"$2,750,000" -> 2750000, "$520 per week" -> 520, "$7.95m" -> 7950000;
    None for "Contact agent" / price guides without a number."""
    if not isinstance(display, str):
        return None
    amounts = _amounts(display)
    return amounts[0] if amounts else None


def price_range(display):
    """"$780,000 - $850,000" -> (780000, 850000); a single figure -> (n, n)."""
    if not isinstance(display, str):
        return None, None
    amounts = _amounts(display)
    if not amounts:
        return None, None
    return amounts[0], amounts[-1]


def date(display):
    """"25 Aug 2026" / "Wed 28 Oct 2026" / "21 September, 2026" -> ISO date;
    ISO input is passed through; None otherwise."""
    if not isinstance(display, str):
        return None
    if _ISO_DATE_RE.match(display):
        return display[:10]
    match = _DATE_RE.search(display)
    if not match:
        return None
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(" ".join(match.groups()), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def image(node, size=IMAGE_SIZE):
    """A templated image node ({templatedUrl} / {url, templated} / a bare
    template string) -> a fetchable URL."""
    if isinstance(node, dict):
        template = node.get("templatedUrl") or node.get("url") or node.get("uri")
    else:
        template = node
    if not isinstance(template, str) or not template:
        return None
    if template.startswith("/"):
        template = "https://i1.au.reastatic.net/{size}" + template
    width, _, height = size.partition("x")
    return template.replace("{size}", size).replace("{width}x{height}", size) \
                   .replace("{width}", width).replace("{height}", height)


def images(nodes, size=IMAGE_SIZE):
    out = []
    for node in nodes or []:
        link = image(node, size)
        if link and link not in out:
            out.append(link)
    return out


def link(node):
    """A link node ({href} / {canonical: {href}} / a string) with the
    site's tracking placeholder stripped."""
    if isinstance(node, dict):
        canonical = node.get("canonical")
        if isinstance(canonical, str):
            node = canonical
        else:
            node = node.get("href") or _get(node, "canonical", "href") or _get(node, "canonical", "path") \
                or node.get("path") or _get(node, "profile", "href")
    if not isinstance(node, str) or not node:
        return None
    node = _CID_RE.sub("", node).split("?cid=")[0]
    return node if node.startswith("http") else SITE + node


def _value(node):
    """{value: n} -> n (the site's IntValue / Attribute wrappers)."""
    if isinstance(node, dict):
        return node.get("value")
    return node


def _size(node):
    """A PropertySize ({displayValue, sizeUnit.displayValue}) -> {value, unit}."""
    if not isinstance(node, dict):
        return None
    display = node.get("displayValue") or node.get("display")
    unit = _get(node, "sizeUnit", "displayValue") or node.get("unit")
    value = _float(display) if display else node.get("value")
    if value is None and unit is None:
        return None
    return {"value": value, "unit": unit}


def _first(*values):
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


# ---- shared records ----------------------------------------------------------------------

def _address(node):
    display = _get(node, "display") or {}
    geocode = display.get("geocode") or node.get("geocode") or {} if isinstance(node, dict) else {}
    if not isinstance(node, dict):
        return None
    short = _first(display.get("shortAddress"), node.get("shortAddress"), node.get("street"), node.get("streetAddress"))
    composed = ", ".join(p for p in (short, node.get("suburb"), " ".join(
        x for x in (node.get("state"), node.get("postcode")) if x)) if p) or None
    return {
        "short": short,
        "full": _first(display.get("fullAddress"), node.get("fullAddress"), node.get("addressDisplayText"), composed),
        "suburb": node.get("suburb"),
        "state": node.get("state"),
        "postcode": node.get("postcode"),
        "latitude": _first(geocode.get("latitude"), node.get("latitude")),
        "longitude": _first(geocode.get("longitude"), node.get("longitude")),
    }


def _agency(node):
    if not isinstance(node, dict):
        return None
    ratings = node.get("ratingsReviews") or node.get("reviewsStats") or node.get("reviewStats") or {}
    return {
        "id": node.get("id") or node.get("agencyId"),
        "name": node.get("name"),
        "link": link(node.get("_links") or node.get("link") or node.get("agencyProfileUrl") or node.get("agencyUrl")),
        "type": node.get("__typename") if node.get("__typename") in ("Developer", "Builder") else None,
        "address": _first(_get(node, "address", "display", "fullAddress"), _get(node, "address", "addressDisplayText")),
        "logo": image(_get(node, "media", "logo") or node.get("logo"), LOGO_SIZE),
        "rating": ratings.get("avgRating"),
        "reviews_count": ratings.get("totalReviews"),
        "brand_colour": _first(_get(node, "branding", "primaryColour"), _get(node, "branding", "primaryColor")),
    }


def _agent(node):
    if not isinstance(node, dict):
        return None
    ratings = node.get("listerRatingsReviews") or node.get("agentRatingsReviews") or node.get("reviewStats") \
        or node.get("reviewsStats") or {}
    phone = _first(_get(node, "phoneNumber", "display"), node.get("phone"), node.get("mobile"))
    return {
        "id": _first(node.get("id"), node.get("salespersonId"), node.get("profileId")),
        "name": node.get("name"),
        "link": link(node.get("_links") or node.get("profileLink") or node.get("profileUrl")),
        "job_title": node.get("jobTitle"),
        "phone": phone,
        "photo": image(node.get("photo") or node.get("profileImage") or node.get("image"), PHOTO_SIZE),
        "rating": ratings.get("avgRating"),
        "reviews_count": ratings.get("totalReviews"),
    }


def _inspection(node):
    if not isinstance(node, dict):
        return None
    display = node.get("display") or {}
    return {
        "starts_at": node.get("startTime"),
        "ends_at": node.get("endTime"),
        "label": _first(display.get("longLabel"), display.get("longDate")),
    }


def _auction(node):
    if not isinstance(node, dict):
        return None
    when = node.get("dateTime") or {}
    return {
        "at": when.get("value"),
        "label": _get(when, "display", "longLabel"),
        "online_links": [l.get("href") if isinstance(l, dict) else l for l in node.get("onlineLinks") or []] or None,
    }


def _media(node):
    if not isinstance(node, dict):
        return None
    videos = []
    for video in node.get("videos") or []:
        if isinstance(video, dict) and video.get("id"):
            vid = video["id"]
            videos.append(f"https://www.youtube.com/watch?v={vid}" if video.get("__typename") == "YouTubeVideo"
                          else vid)
    tours = [t.get("href") or t.get("url") if isinstance(t, dict) else t
             for t in (node.get("threeDimensionalTours") or [])]
    return {
        "main_image": image(node.get("mainImage")),
        "images": images(node.get("images")),
        "floorplans": images(node.get("floorplans")),
        "videos": videos,
        "virtual_tours": [t for t in tours if t],
        "statement_of_information": link(node.get("statementOfInformation")) if node.get("statementOfInformation") else None,
    }


def _channel_of(typename):
    typename = typename or ""
    for channel in ("Buy", "Rent", "Sold"):
        if typename.startswith(channel):
            return channel.lower()
    return None


def listing_card(node):
    """One listing as the search results / related / child lists carry it
    (BuyResidentialListing, RentResidentialListing, SoldResidentialListing;
    a ProjectProfile goes through project_card). The detail page's listing
    is a superset parsed by listing_details."""
    if not isinstance(node, dict):
        return None
    if node.get("__typename") == "ProjectProfile":
        return project_card(node)
    features = node.get("generalFeatures") or {}
    sizes = node.get("propertySizes") or {}
    price = node.get("price") or {}
    price_display = price.get("display") if isinstance(price, dict) else price
    price_from, price_to = price_range(price_display)
    channel = _channel_of(node.get("__typename"))
    parent = node.get("parent")
    href = link(node.get("_links"))
    listing_id = node.get("id")
    if not listing_id and href:
        match = re.search(r"-([0-9]{6,10})$", href.split("?")[0])
        listing_id = match.group(1) if match else None
    if channel is None and href and "/sold/" in href:
        channel = "sold"
    return {
        "id": listing_id,
        "link": href,
        "channel": channel,
        "status": _first(_get(node, "badge", "label"), node.get("listingStatus")),
        "property_type": _first(_get(node, "propertyType", "display"), node.get("propertyType")
                                if isinstance(node.get("propertyType"), str) else None),
        "property_type_id": _get(node, "propertyType", "id"),
        "address": _address(node.get("address")),
        "price": {
            "display": price_display,
            "amount": price_from if price_from == price_to else None,
            "from": price_from,
            "to": price_to,
            "currency": "AUD",
            "period": "week" if channel == "rent" and isinstance(price_display, str) and "week" in price_display.lower()
            else None,
            "note": _first(price.get("information"), _get(price, "searchRange", "display")) if isinstance(price, dict) else None,
        },
        "bedrooms": _value(features.get("bedrooms")),
        "bathrooms": _value(features.get("bathrooms")),
        "parking_spaces": _value(features.get("parkingSpaces")),
        "studies": _value(features.get("studies")),
        "land_size": _size(sizes.get("land")),
        "building_size": _size(sizes.get("building")),
        "date_sold": date(_get(node, "dateSold", "display")),
        "bond": {"display": _get(node, "bond", "display"), "amount": money(_get(node, "bond", "display"))}
        if node.get("bond") else None,
        "available_from": date(_get(node, "availableDate", "display")) if node.get("availableDate") else None,
        "available_label": _get(node, "availableDate", "display"),
        "is_build_to_rent": bool(node.get("buildToRent")) if "buildToRent" in node else None,
        "description": text(node.get("description")),
        "agency": _agency(node.get("listingCompany")),
        "agents": [a for a in (_agent(l) for l in node.get("listers") or []) if a],
        "inspections": [i for i in (_inspection(x) for x in node.get("inspections") or []) if i],
        "auction": _auction(node.get("auction")),
        "media": _media(node.get("media")),
        "project": {"id": parent.get("id"), "name": parent.get("name"), "link": link(parent.get("_links"))}
        if isinstance(parent, dict) else None,
        "listing_tier": node.get("productDepth"),
    }


def project_card(node):
    """A new-development project (ProjectProfile) as the search / project
    page carries it."""
    if not isinstance(node, dict):
        return None
    price_from, price_to = price_range(_get(node, "priceRange", "display"))
    children = _get(node, "childListings", "results") or node.get("childListings") or []
    if isinstance(children, dict):
        children = children.get("results") or []
    return {
        "id": node.get("id"),
        "link": link(node.get("_links")),
        "channel": "buy",
        "is_project": True,
        "name": node.get("name"),
        "title": node.get("title"),
        "status": _get(node, "badge", "label"),
        "property_type": _get(node, "propertyType", "display"),
        "property_type_id": _get(node, "propertyType", "id"),
        "address": _address(node.get("address") or _get(node, "displayLocation", "address")),
        "price": {"display": _get(node, "priceRange", "display"), "from": price_from, "to": price_to, "currency": "AUD"},
        "description": text(node.get("description")),
        "developer": _agency(node.get("listingCompany")),
        "project_team": [{"role": t.get("type"), "name": t.get("name"), "description": text(t.get("description"))}
                         for t in node.get("projectTeams") or [] if isinstance(t, dict)],
        "agents": [a for a in (_agent(l) for l in node.get("listers") or []) if a],
        "media": _media(node.get("media")),
        "logo": image(_get(node, "media", "logo"), LOGO_SIZE),
        "properties_count_label": node.get("totalNumberOfPropertiesDisplay"),
        "estimated_completion": _first(_get(node, "estimatedCompletionDate", "display"), node.get("estimatedCompletionDate")),
        "features": [f.get("displayLabel") if isinstance(f, dict) else f for f in node.get("features") or []] or None,
        "faq": _faq(node.get("faq")),
        "child_listings": [c for c in (listing_card(x) for x in children) if c],
        "listing_tier": node.get("productDepth"),
    }


def _faq(node):
    items = _get(node, "list") or []
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        answer = item.get("answer")
        if isinstance(answer, list):
            parts = []
            for piece in answer:
                if isinstance(piece, dict):
                    parts.append(piece.get("faqListTextValue") or piece.get("text") or "")
                    parts.extend(x if isinstance(x, str) else json.dumps(x) for x in piece.get("faqListItems") or [])
                else:
                    parts.append(str(piece))
            answer = "\n".join(p for p in parts if p)
        out.append({"id": item.get("id"), "question": item.get("question"), "answer": text(answer) if isinstance(answer, str) else answer})
    return out or None


# ---- search results ---------------------------------------------------------------------

def _locality(node):
    return {
        "display": node.get("display"),
        "name": node.get("name"),
        "type": (node.get("precision") or "").lower() or None,
        "state": node.get("state"),
        "url_value": node.get("urlValue"),
        "atlas_id": node.get("atlasId"),
    }


def search_results(html):
    """A /buy|rent|sold/ search page -> {channel, localities, filters, sort,
    total_count, surrounding_count, page, total_pages, results,
    surrounding_results}. A page past the end has empty results and
    total_count 0 (the site answers it 200 with maxPageNumberAvailable 1).
    None when the page carries no search state."""
    data = _listing_data(state(html))
    if not data:
        return None
    key = next((k for k in ("buySearch", "rentSearch", "soldSearch") if isinstance(data.get(k), dict)), None)
    if not key:
        return None
    search = data[key]
    results = search.get("results") or {}
    pagination = results.get("pagination") or {}
    resolved = search.get("resolvedQuery") or {}
    saved = _get(resolved, "metadata", "savedSearchQuery") or {}
    filters = {k: v for k, v in (saved.get("filters") or {}).items()
               if v not in (None, False, [], {}, "") and k != "__typename"}
    exact = [c for c in (listing_card(_get(i, "listing")) for i in _get(results, "exact", "items") or []) if c]
    surrounding = [c for c in (listing_card(_get(i, "listing")) for i in _get(results, "surrounding", "items") or []) if c]
    return {
        "channel": saved.get("channel") or key[:-6],
        "localities": [_locality(l) for l in resolved.get("localities") or [] if isinstance(l, dict)],
        "canonical_link": _get(resolved, "prettyUrl", "value"),
        "sort": saved.get("sortType"),
        "filters": filters or None,
        "total_count": results.get("totalResultsCount"),
        "surrounding_count": _get(results, "surrounding", "totalCount"),
        "page": pagination.get("page") or saved.get("page"),
        "page_size": saved.get("pageSize"),
        "total_pages": pagination.get("maxPageNumberAvailable"),
        "has_next": bool(pagination.get("moreResultsAvailable")),
        "results": exact,
        "surrounding_results": surrounding,
    }


# ---- listing details -------------------------------------------------------------------------

def _component(components, name):
    node = components.get(name) if isinstance(components, dict) else None
    return node.get("component") if isinstance(node, dict) else None


def _features(component):
    """PropertyFeatureComponent -> {top: [...], categories: [{title, items}]}."""
    if not component:
        return None
    top = [i.get("displayLabel") for i in _get(component, "topPropertyFeatures", "propertyFeatureItems") or []
           if isinstance(i, dict) and i.get("displayLabel")]
    categories = []
    for cat in _get(component, "allPropertyFeatures", "propertyFeatureCategories") or []:
        if not isinstance(cat, dict):
            continue
        items = [{"id": i.get("propertyFeatureId"), "label": i.get("displayLabel")}
                 for i in cat.get("propertyFeatureItems") or [] if isinstance(i, dict)]
        categories.append({"title": cat.get("title"), "items": items})
    if not top and not categories:
        return None
    return {"top": top, "categories": categories}


def _nbn(component):
    if not component:
        return None
    speed = component.get("speed") or {}
    metrics = speed.get("speedMetrics") or {}
    connection = component.get("connection") or {}
    return {
        "connection": text(connection.get("description")),
        "connection_type": _nbn_type(connection.get("description")),
        "download": _get(metrics, "downloadSpeed", "title"),
        "upload": _get(metrics, "uploadSpeed", "title"),
        "speed_note": text(speed.get("description")),
    }


def _nbn_type(description):
    match = re.search(r"nbn ([A-Za-z ]+?) \(([A-Z]+)\)", description or "")
    return match.group(2) if match else None


def _highlights(component):
    items = _get(component, "propertyHighlights") or []
    out = [{"headline": h.get("headline"), "category": h.get("categoryId"), "detail": h.get("subtext")}
           for h in items if isinstance(h, dict)]
    return out or None


def _component_agents(component):
    """AgentOrConsultantInfoComponent -> {agent link: phone} (the one place
    the listing page carries the agents' numbers)."""
    phones = {}
    for a in _get(component, "agentsOrConsultants") or []:
        if not isinstance(a, dict):
            continue
        href = _get(a, "agentOrConsultantName", "webContactProfileLink", "href")
        number = _first(_get(a, "contactActions", "smsButton", "contactNumber"),
                        (_get(a, "contactNumber", "value") or "").replace("tel:", "") or None)
        if href and number:
            phones[link(href)] = number
    return phones


def listing_details(html):
    """A listing page -> the listing card plus everything else the page
    carries. A project page (/project/...) -> project_card plus the shared
    sections. None when the page carries no listing state."""
    data = _listing_data(state(html))
    if not data:
        return None
    details = data.get("details") or {}
    node = details.get("listing")
    if not isinstance(node, dict):
        return None
    components = _get(data, "components", "details", "components") or {}
    record = listing_card(node)
    if record is None:
        return None
    phones = _component_agents(_component(components, "AgentOrConsultantInfoComponent"))
    for agent in record.get("agents") or []:
        if not agent.get("phone"):
            agent["phone"] = phones.get(agent.get("link"))
    agency_copy = _get(_component(components, "AgencyOrProjectInfoComponent"), "agencyOrProjectInfo") or {}
    if record.get("agency") and isinstance(record["agency"], dict):
        record["agency"]["address"] = record["agency"].get("address") or agency_copy.get("fullAddress")
        record["agency"]["description"] = text(agency_copy.get("description"))
    if record.get("developer") and isinstance(record["developer"], dict):
        record["developer"]["description"] = text(agency_copy.get("description"))
    description = _component(components, "PropertyDescriptionComponent") or {}
    inspections = []
    for i in details.get("inspections") or []:
        if isinstance(i, dict):
            inspections.append({
                "starts_at": i.get("startTime"), "ends_at": i.get("endTime"),
                "label": _first(_get(i, "display", "longDate"), _get(i, "display", "shortDate")),
                "time": _get(i, "display", "time"),
                "type": i.get("plannerEventType"),
            })
    if inspections:
        record["inspections"] = inspections
    tracking = _get(details, "trackingData", "listing", "data") or {}
    related = [c for c in (listing_card(x) for x in _get(details, "relatedListings", "items") or []) if c]
    recent = [c for c in (listing_card(x) for x in _get(details, "recentSales", "items") or []) if c]
    page_views = _get(details, "listingMetrics", "pageViews") or {}
    summary_badge = _get(_component(components, "PropertySummaryComponent"), "summary", "badge", "title")
    record.update({
        "status": _first(record.get("status"), summary_badge,
                         (tracking.get("status") or "").replace("-", " ").capitalize() or None),
        "title": _first(description.get("title"), node.get("title")),
        "published_at": date(description.get("publishedDate")),
        "construction_status": tracking.get("construction_status"),
        "is_new_construction": node.get("newConstruction") if "newConstruction" in node else None,
        "features": _features(_component(components, "PropertyFeatureComponent")),
        "highlights": _highlights(_component(components, "PropertyHighlightsComponent")),
        "nbn": _nbn(_component(components, "NbnDetailsComponent")),
        "faq": record.get("faq") or _faq(node.get("faq")),
        "inspections_need_registration": _get(node, "inspectionTimes", "registrationsEnabled"),
        "can_apply_online": bool(details.get("applyOnline")) if "applyOnline" in details else None,
        "page_views": {"count": _int(page_views.get("display")),
                       "as_of": date(_get(page_views, "lastUpdated", "value"))} if page_views else None,
        "property_page_link": _first(link(_get(details, "property", "propertyPage", "link")),
                                     _get(details, "property", "propertyPage", "link", "href")),
        "related_listings": related,
        "recent_sales": {"title": _get(details, "recentSales", "title"), "items": recent} if recent else None,
        "enquiry_link": _get(node, "_links", "submitEnquiry", "href"),
    })
    return record


# ---- agents ---------------------------------------------------------------------------------

def _social(node):
    if not isinstance(node, dict):
        return None
    out = {k: v for k, v in node.items() if k != "__typename"}
    return out or None


def _compliments(items):
    return [{"tag": c.get("tag"), "count": c.get("count")} for c in items or [] if isinstance(c, dict)] or None


def _review(node):
    if not isinstance(node, dict):
        return None
    listing = node.get("listing") or {}
    return {
        "id": node.get("id"),
        "rating": node.get("rating"),
        "text": text(node.get("review")),
        "reply": text(node.get("reply")),
        "reviewer_role": node.get("reviewerRole"),
        "published_at": date(node.get("publishDate")),
        "agent_id": node.get("agentProfileId"),
        "listing": {"id": listing.get("id") or node.get("context"), "property_type": listing.get("propertyType"),
                    "suburb": _get(listing, "address", "suburb"), "state": _get(listing, "address", "state")}
        if (listing or node.get("context")) else None,
    }


def _agent_search_result(node):
    stats = _get(node, "listings", "stats") or {}
    breakdown = _get(node, "listings", "salesBreakdown") or {}
    review_stats = _get(node, "reviews", "stats") or {}
    best = _get(node, "reviews", "bestAndLatestReview") or {}
    award = node.get("topAgentSuburbAward") or {}
    return {
        "id": node.get("salespersonId"),
        "name": node.get("name"),
        "link": link(node.get("_links")),
        "job_title": node.get("jobTitle"),
        "photo": image(node.get("profileImage"), PHOTO_SIZE),
        "cover_photo": image(node.get("coverPhoto")),
        "years_experience": node.get("yearsExperience"),
        "specialities": [s.strip() for s in (node.get("specialities") or "").split(",") if s.strip()] or None,
        "awards": [a for a in (node.get("awards") or "").split("\n") if a.strip()] or None,
        "top_agent_award": {"description": award.get("description"), "year": award.get("year"),
                            "suburbs": award.get("suburbs")} if award else None,
        "description": text(node.get("description")),
        "review_summary": text(node.get("reviewSummary")),
        "rating": review_stats.get("avgRating"),
        "reviews_count": review_stats.get("totalReviews"),
        "reviews_last_12_months": review_stats.get("reviewCountInTimeRange"),
        "compliments": _compliments(review_stats.get("compliments")),
        "latest_review": {"rating": best.get("rating"), "reviewer_role": best.get("role"), "text": text(best.get("content"))}
        if best else None,
        "sales": {
            "sold_count": stats.get("sumSoldProperties"),
            "sold_as_lead_agent": stats.get("sumSoldPropertiesPrimaryLister"),
            "sold_as_secondary_agent": stats.get("sumSoldPropertiesSecondaryLister"),
            "median_sold_price": stats.get("medianSoldPrice"),
            "median_days_on_site": stats.get("medianSoldDaysOnSite"),
            "leased_count": stats.get("sumLeasedProperties"),
            "median_leased_price": stats.get("medianLeasedPrice"),
            "by_property_type": {k: {"count": v.get("count"), "median_sold_price": v.get("medianSoldPrice"),
                                     "median_days_on_site": v.get("medianDaysOnSite")}
                                 for k, v in breakdown.items() if isinstance(v, dict)} or None,
        },
        "social": _social(node.get("social")),
        "agency": _agency(node.get("agency")),
    }


def agents_search(html):
    """A /find-agent/<place> page -> {location, surrounding_suburbs, total_count,
    page, page_size, total_pages, results}."""
    node = _get(state(html), "resi-agent_customer-search-mfe", "AGENT_SEARCH")
    if not isinstance(node, dict):
        return None
    location = node.get("location") or {}
    return {
        "location": {"display": location.get("display"), "name": location.get("name"), "slug": location.get("slug"),
                     "state": location.get("state"), "postcode": location.get("postcode"),
                     "atlas_id": location.get("atlasId")},
        "surrounding_suburbs": [{"suburb": s.get("suburb"), "state": s.get("state"), "slug": s.get("suburbSlug")}
                                for s in node.get("surroundingSuburbs") or [] if isinstance(s, dict)],
        "total_count": node.get("totalCount"),
        "page": node.get("pageNumber"),
        "page_size": node.get("pageSize"),
        "total_pages": node.get("pageCount"),
        "results": [_agent_search_result(r) for r in node.get("results") or [] if isinstance(r, dict)],
    }


def _map_listing(node):
    """The compact listing shape of agent / agency profile pages."""
    if not isinstance(node, dict):
        return None
    features = node.get("generalFeatures") or {}
    price_from, price_to = price_range(node.get("price"))
    status = node.get("listingStatus") or ""
    geocode = node.get("geocode") or {}
    return {
        "id": node.get("id"),
        "link": link(node.get("_links")),
        "status": _first(_get(node, "badge", "label"), status.split(" ")[0] if status else None),
        "status_label": status or None,
        "status_date": date(status),
        "property_type": node.get("propertyType"),
        "address": {"short": _get(node, "address", "shortAddress"), "suburb": _get(node, "address", "suburb"),
                    "state": _get(node, "address", "state"), "postcode": _get(node, "address", "postcode"),
                    "latitude": geocode.get("latitude"), "longitude": geocode.get("longitude")},
        "price": {"display": node.get("price"), "amount": price_from if price_from == price_to else None,
                  "from": price_from, "to": price_to, "currency": "AUD"},
        "bedrooms": features.get("bedrooms"),
        "bathrooms": features.get("bathrooms"),
        "parking_spaces": features.get("parkingSpaces"),
        "agents": [{"name": l.get("name"), "photo": image(l.get("photo"), PHOTO_SIZE)}
                   for l in node.get("listers") or [] if isinstance(l, dict)] or None,
        "main_image": image(_get(node, "media", "mainImage")),
        "images": images(_get(node, "media", "images")),
        "next_inspection": node.get("nextInspection"),
    }


def agent_profile(html):
    """An /agent/<id> page -> the profile, its stats, every review, and the
    sold / for-sale / for-rent listings the page embeds."""
    root = _get(state(html), "resi-agent_customer-profile-experience")
    agent = _get(root, "AGENT_PROFILE", "agent")
    if not isinstance(agent, dict):
        return None
    stats = _get(root, "AGENT_PROFILE", "agentStats") or {}
    listings = _get(root, "AGENT_PROFILE_LISTINGS") or {}

    def channel(map_key, list_key):
        node = listings.get(map_key) or {}
        rows = [r for r in (_map_listing(x) for x in node.get("listings") or []) if r]
        if not rows:
            rows = [r for r in (_map_listing(x) for x in _get(listings, list_key, "listings") or []) if r]
        total = _first(node.get("totalResultsCount"), _get(listings, list_key, "totalResultsCount"))
        return {"total_count": total, "items": rows}

    awards = node_awards = agent.get("topAgentSuburbAwards") or []
    return {
        "id": agent.get("profileId"),
        "name": agent.get("name"),
        "link": link(agent.get("_links")),
        "job_title": agent.get("jobTitle"),
        "phone": agent.get("mobile"),
        "business_phone": agent.get("businessPhone"),
        "photo": image(agent.get("profileImage"), PHOTO_SIZE),
        "description": text(agent.get("description")),
        "years_experience": agent.get("yearsExperience"),
        "in_industry_since": agent.get("startYearInIndustry"),
        "specialities": [s.strip() for s in (agent.get("specialities") or "").split(",") if s.strip()] or None,
        "awards": [a for a in (agent.get("awards") or "").split("\n") if a.strip()] or None,
        "top_agent_awards": [{"year": a.get("year"), "suburbs": a.get("suburbs"), "is_last_year_winner": a.get("isLastYearWinner")}
                             for a in node_awards if isinstance(a, dict)] or None,
        "community_involvement": text(agent.get("communityInvolvement")),
        "most_active_suburb": _address(agent.get("mostActiveLocation")) if agent.get("mostActiveLocation") else None,
        "rating": agent.get("avgRating"),
        "reviews_count": agent.get("totalReviews"),
        "compliments": _compliments(agent.get("compliments")),
        "reviews": [r for r in (_review(x) for x in agent.get("reviews") or []) if r],
        "sales": {
            "count": _get(stats, "salesCount", "overall"),
            "as_lead_agent": _get(stats, "salesCount", "asLeadAgent"),
            "as_secondary_agent": _get(stats, "salesCount", "asSecondaryAgent"),
            "median_sold_price": _get(stats, "medianSoldPrice", "overall"),
            "median_days_on_site": _get(stats, "medianDaysOnSite", "overall"),
            "by_property_type": {
                ptype: {"count": _get(stats, "salesCount", ptype), "median_sold_price": _get(stats, "medianSoldPrice", ptype),
                        "median_days_on_site": _get(stats, "medianDaysOnSite", ptype)}
                for ptype in sorted(set(list((stats.get("salesCount") or {}).keys()))
                                    - {"overall", "asLeadAgent", "asSecondaryAgent", "__typename"})
            } or None,
        } if stats else None,
        "agency": _agency(agent.get("agency")),
        "linked_agent_ids": agent.get("linkedSalespeopleIds") or None,
        "video": _first(_get(agent, "video", "href"), _get(agent, "video", "url")) if agent.get("video") else None,
        "listings": {
            "for_sale": channel("agentMapBuyListings", "buyListings"),
            "for_rent": channel("agentMapRentListings", "rentListings"),
            "sold": channel("agentMapSoldListings", "soldListings"),
        },
    }


# ---- agencies ------------------------------------------------------------------------------

def _performance(node):
    if not isinstance(node, dict):
        return None
    out = {}
    for key, name in (("sales", "sales"), ("rent", "rentals")):
        row = node.get(key)
        if isinstance(row, dict):
            out[name] = {"count": row.get("properties"), "median_price": row.get("medianPrice"),
                         "median_days_on_site": row.get("medianDaysOnSite"), "offices": row.get("offices")}
    return out or None


def _breakdown(rows):
    out = [{"property_type": r.get("propertyType") or (r.get("label") or "").lower() or None, "label": r.get("label"),
            "count": r.get("properties"), "median_price": r.get("medianPrice"), "median_days_on_site": r.get("medianDaysOnSite")}
           for r in rows or [] if isinstance(r, dict)]
    return out or None


def _suburb_rows(rows):
    out = [{"suburb": r.get("name"), "state": r.get("state"), "postcode": r.get("postcode"), "count": r.get("properties")}
           for r in rows or [] if isinstance(r, dict)]
    return out or None


def agency_profile(html):
    """An /agency/<id> page -> the office, its team, reviews, 12-month
    performance and the listings the page embeds (the SOLD channel's map
    list plus the current spotlight)."""
    agency = _get(state(html), "resi-agent_customer-profile-experience", "AGENCY_PROFILE", "agencyProfile")
    if not isinstance(agency, dict):
        return None
    reviews = agency.get("reviews") or {}
    performance = agency.get("performance") or {}
    channels = agency.get("residentialChannels") or {}
    counts = {(c.get("label") or "").lower(): c.get("totalResultsCount")
              for c in channels.get("activeChannelDetails") or [] if isinstance(c, dict)}
    embedded = [r for r in (_map_listing(x) for x in _get(channels, "listings", "mapSearch", "listings") or []) if r]
    stats = agency.get("reviewsStats") or {}
    return {
        "id": agency.get("agencyId"),
        "name": agency.get("name"),
        "link": link(agency.get("_links")),
        "website": agency.get("agencyUrl"),
        "phone": agency.get("businessPhone"),
        "address": _address(agency.get("address")),
        "description": text(agency.get("description")),
        "logo": image(agency.get("logo"), LOGO_SIZE),
        "cover_photo": image(agency.get("coverPhoto")),
        "brand_colour": _get(agency, "branding", "primaryColor"),
        "social": _social(agency.get("urls")),
        "is_residential": agency.get("isResidential"),
        "is_commercial": agency.get("isCommercial"),
        "group_id": agency.get("agencyGroupId"),
        "rating": stats.get("avgRating"),
        "reviews_count": stats.get("totalReviews"),
        "compliments": _compliments(stats.get("compliments")),
        "reviews": {
            "from_sellers": [r for r in (_review(x) for x in reviews.get("sellersReview") or []) if r],
            "from_buyers": [r for r in (_review(x) for x in reviews.get("buyersReview") or []) if r],
        },
        "performance": {
            "last_12_months": _performance(performance.get("snapshot")),
            "by_property_type": {"sales": _breakdown(_get(performance, "breakdown", "sales")),
                                 "rentals": _breakdown(_get(performance, "breakdown", "rent"))},
            "by_suburb": {"sales": _suburb_rows(_get(performance, "breakdown12MonthsBySuburb", "sales")),
                          "rentals": _suburb_rows(_get(performance, "breakdown12MonthsBySuburb", "rent"))},
            "all_time_note": (channels.get("listingsDisclaimer") or "").replace("{{agencyName}}", agency.get("name") or "") or None,
        },
        "agents": [{**(_agent(a) or {}),
                    "sold_as_lead_agent": next((p.get("value") for p in a.get("performanceStats") or []
                                                if isinstance(p, dict) and p.get("label") == "SUM_SOLD_PRIMARY"), None)}
                   for a in agency.get("agents") or [] if isinstance(a, dict)],
        "listing_counts": {"for_sale": counts.get("buy"), "for_rent": counts.get("rent"),
                           "sold": counts.get("sold"), "leased": counts.get("leased")},
        "listings": {"sold": {"total_count": _get(channels, "listings", "mapSearch", "totalResultsCount"), "items": embedded}},
        "spotlight_listings": [r for r in (_map_listing(x) for x in agency.get("spotlightProperties") or []) if r],
    }


def _agency_search_member(node):
    stats = _get(node, "listingsStats", "statsByPropertyType") or []
    by_type = {}
    for row in stats:
        if isinstance(row, dict) and row.get("propertyType"):
            by_type[row["propertyType"]] = {
                "sold_count": row.get("soldProperties"), "median_sold_price": row.get("medianSoldPrice"),
                "median_days_on_site_sold": row.get("medianDaysOnSiteSold"), "leased_count": row.get("leasedProperties"),
                "median_leased_price": row.get("medianLeasedPrice"), "median_days_on_site_leased": row.get("medianDaysOnSiteLeased"),
            }
    reviews_all = _get(node, "reviewsStats", "all") or {}
    reviews_year = _get(node, "reviewsStats", "twelveMonths") or {}
    return {
        "id": node.get("id") or node.get("agencyId"),
        "name": node.get("name"),
        "link": link(node.get("_links") or node.get("agencyUrl")),
        "address": _address(node.get("address")),
        "logo": image(node.get("logo"), LOGO_SIZE),
        "rating": reviews_all.get("avgRating"),
        "reviews_count": reviews_all.get("totalReviews"),
        "reviews_last_12_months": {"rating": reviews_year.get("avgRating"), "count": reviews_year.get("totalReviews")}
        if reviews_year else None,
        "compliments": _compliments(reviews_all.get("compliments")),
        "performance": _performance(node.get("performance")),
        "stats_by_property_type": by_type or None,
        "recent_listings": {"channel": (_get(node, "recentListings", "listingsChannel") or "").lower() or None,
                            "items": [r for r in (_map_listing(x) for x in _get(node, "recentListings", "listings") or []) if r]}
        if node.get("recentListings") else None,
    }


def agencies_search(html):
    """A /find-agency/<place> page -> {location, total_count, page, page_size,
    total_pages, results} where each result is an agency group with its
    member offices."""
    node = _get(state(html), "resi-agent_customer-search-mfe", "AGENCY_SEARCH", "agencySearch")
    if not isinstance(node, dict):
        return None
    pagination = node.get("pagination") or {}
    location = node.get("location") or {}
    results = []
    for group in node.get("results") or []:
        if not isinstance(group, dict):
            continue
        members = [_agency_search_member(m) for m in group.get("membersServicing") or group.get("members") or []
                   if isinstance(m, dict)]
        if not members and group.get("agencyId"):
            # a single-office agency is its own result: the office fields
            # (agencyId, address, recentListings...) sit on the group itself
            members = [_agency_search_member(group)]
        reviews_all = _get(group, "reviewsStats", "all") or {}
        results.append({
            "group_id": group.get("agencyGroupId"),
            "name": group.get("name"),
            "primary_agency_id": _first(group.get("primaryAgencyId"), group.get("agencyId")),
            "franchise": group.get("franchiseName"),
            "is_franchise": group.get("isGroupPartOfFranchise"),
            "logo": image(_get(group, "branding", "logo"), LOGO_SIZE),
            "brand_colour": _get(group, "branding", "primaryColor"),
            "rating": reviews_all.get("avgRating"),
            "reviews_count": reviews_all.get("totalReviews"),
            "compliments": _compliments(reviews_all.get("compliments")),
            "performance": _performance(group.get("performance")),
            "offices": members,
        })
    return {
        "location": {"display": location.get("display"), "name": location.get("name"), "state": location.get("state"),
                     "postcode": location.get("postcode"), "atlas_id": location.get("atlasId")},
        "total_count": node.get("totalResults"),
        "page": pagination.get("page"),
        "page_size": pagination.get("pageSize"),
        "total_pages": pagination.get("maxPageNumberAvailable"),
        "results": results,
    }


# ---- suburb market profile ------------------------------------------------------------------

_BED_KEYS = {"allBed": "all", "zeroBed": "0", "oneBed": "1", "twoBed": "2", "threeBed": "3", "fourBed": "4",
             "fivePlusBed": "5+"}


def _period(node):
    if not isinstance(node, dict):
        return None
    change = node.get("changePercentage") or {}
    value = node.get("value")
    if value is None and node.get("display"):
        value = money(node["display"]) if "$" in node["display"] else _float(node["display"])
    out = {"value": value, "display": node.get("display"), "volume": node.get("volume"),
           "from": node.get("startDate"), "to": node.get("endDate"),
           "change_percent": change.get("value") if change else None}
    for key in ("supply", "demand"):
        if key in node:
            out[key] = node.get(key)
    return {k: v for k, v in out.items() if v is not None} or None


def _trend(rows):
    out = []
    for row in rows or []:
        if isinstance(row, dict):
            out.append({"from": row.get("startDate"), "to": row.get("endDate"), "value": row.get("value"),
                        "display": row.get("display"), "volume": row.get("volume")})
    return out or None


def _by_bedrooms(node, with_trends=False):
    if not isinstance(node, dict):
        return None
    out = {}
    for key, beds in _BED_KEYS.items():
        row = node.get(key)
        if not isinstance(row, dict):
            continue
        period = row.get("yearly") or row.get("monthly")
        entry = _period(period)
        if entry is None and not row.get("trends"):
            continue
        entry = entry or {}
        if with_trends:
            entry["trend"] = _trend(row.get("trends"))
        out[beds] = entry
    return out or None


def _section(node, with_trends=False):
    """A site section (buy / rent) with house / unit -> {house: by-bed, unit: by-bed}."""
    if not isinstance(node, dict):
        return None
    out = {}
    for ptype in ("house", "unit"):
        rows = _by_bedrooms(node.get(ptype), with_trends)
        if rows:
            out[ptype] = rows
    return out or None


def suburb_profile(html):
    """A /<state>/<suburb>-<postcode>/ page -> the market profile: median
    prices with 5-year monthly trends, transaction volumes, days on site,
    rental yield, supply/demand per property type and bedroom count, plus
    the parent region, surrounding suburbs and the suburb's bounding box."""
    profile = _get(state(html), "resi-property_market-explorer", "suburb_data", "marketProfileBySlug")
    if not isinstance(profile, dict):
        return None
    insights = profile.get("insights") or {}
    location = _get(profile, "market", "location") or {}
    bounds = _get(profile, "geoLocation", "bounds") or {}
    return {
        "suburb": location.get("suburb"),
        "state": location.get("state"),
        "postcode": location.get("postcode"),
        "link": _get(profile, "market", "url", "href"),
        "region": _get(profile, "parentMarket", "name"),
        "bounds": {"north_east": {"latitude": _get(bounds, "northEast", "latitude"), "longitude": _get(bounds, "northEast", "longitude")},
                   "south_west": {"latitude": _get(bounds, "southWest", "latitude"), "longitude": _get(bounds, "southWest", "longitude")}}
        if bounds else None,
        "median_price": {"buy": _section(_get(insights, "medianPrice", "buy"), with_trends=True),
                         "rent": _section(_get(insights, "medianPrice", "rent"), with_trends=True)},
        "transaction_volume": {"buy": _section(_get(insights, "transactionVolume", "buy")),
                               "rent": _section(_get(insights, "transactionVolume", "rent"))},
        "days_on_site": {"buy": _section(_get(insights, "daysOnSite", "buy")),
                         "rent": _section(_get(insights, "daysOnSite", "rent"))},
        "rental_yield": _section({"house": _get(insights, "rentalYield", "house"), "unit": _get(insights, "rentalYield", "unit")}),
        "supply_demand": {"buy": _section(_get(insights, "supplyDemand", "buy")),
                          "rent": _section(_get(insights, "supplyDemand", "rent"))},
        "surrounding_suburbs": [{"suburb": _get(m, "location", "suburb"), "state": _get(m, "location", "state"),
                                 "postcode": _get(m, "location", "postcode"),
                                 "link": SITE + _get(m, "url", "path") if _get(m, "url", "path") else None}
                                for m in profile.get("surroundingMarkets") or [] if isinstance(m, dict)],
        "appraisal_link": _get(profile, "leadGen", "actionUrl"),
    }


# ---- the property address page --------------------------------------------------------------

def _attribute(node):
    if isinstance(node, dict):
        return node.get("value") if "value" in node else node.get("display")
    return node


def _valuation(node):
    if not isinstance(node, dict):
        return None
    return {
        "estimate": money(_get(node, "medianValuation", "display")),
        "low": money(_get(node, "minValuation", "display")),
        "high": money(_get(node, "maxValuation", "display")),
        "currency": "AUD",
        "confidence": node.get("confidence"),
        "as_of": date(_get(node, "medianValuation", "lastUpdated")),
    }


def _timeline(rows):
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        event = row.get("listingEvent") or {}
        out.append({
            "date": date(row.get("date")),
            "event": row.get("eventType"),
            "price": {"display": row.get("price"), "amount": money(row.get("price")), "currency": "AUD"},
            "agency": _first(row.get("agency"), _get(event, "listingAgency", "name")),
            "agency_id": _get(event, "listingAgency", "id"),
            "listing_id": _first(event.get("listingId"), row.get("listingId")),
            "main_image": image(_get(event, "listingMedia", "mainImage")),
            "images_count": _get(event, "listingMedia", "imageCount"),
        })
    return out


def _overlays(node):
    if not isinstance(node, dict):
        return None
    out = {"land_use": node.get("landUse"), "lot_plan": node.get("lotPlanNumber"), "updated_at": date(node.get("updatedAt")),
           "council": {"name": _get(node, "council", "label"), "link": _get(node, "council", "url")} if node.get("council") else None,
           "planning_portal": {"name": _get(node, "statePlanningPortal", "label"), "link": _get(node, "statePlanningPortal", "url")}
           if node.get("statePlanningPortal") else None}
    for key in ("heritage", "bushfire", "flood", "zoning"):
        value = node.get(key)
        out[key] = value.get("items") if isinstance(value, dict) else value
    return out


def _market_listing(node):
    if not isinstance(node, dict):
        return None
    features = node.get("features") or {}
    price_from, price_to = price_range(node.get("price"))
    return {
        "link": _get(node, "link", "href"),
        "address": node.get("address"),
        "property_type": node.get("propertyType"),
        "price": {"display": node.get("price"), "from": price_from, "to": price_to, "currency": "AUD"},
        "bedrooms": _int(features.get("bedrooms")),
        "bathrooms": _int(features.get("bathrooms")),
        "parking_spaces": _int(features.get("parkingSpaces")),
        "size": _get(node, "propertySize", "size"),
        "image": image(node.get("image")),
        "events": [e if isinstance(e, str) else (e.get("display") or e.get("label") or e.get("date")) for e in node.get("events") or []] or None,
    }


def _local_market(node):
    if not isinstance(node, dict):
        return None
    out = {"title": node.get("title"), "summary": node.get("subTitle")}
    for channel in ("buy", "rent", "sold"):
        row = node.get(channel)
        if isinstance(row, dict):
            out[channel] = {"total_count": row.get("totalCount"), "inspections_count": row.get("inspectionCount"),
                            "auctions_count": row.get("auctionCount"), "search_link": _get(row, "searchLink", "href"),
                            "listings": [r for r in (_market_listing(x) for x in row.get("marketListings") or []) if r]}
    return out


def _demographics(node):
    if not isinstance(node, dict):
        return None
    charts = []
    for section in node.get("chartSections") or []:
        for chart in (section.get("charts") or []) if isinstance(section, dict) else []:
            if isinstance(chart, dict):
                charts.append({"title": chart.get("title"), "caption": chart.get("caption"),
                               "data": [{k: v for k, v in d.items() if k != "__typename"} for d in chart.get("data") or [] if isinstance(d, dict)]})
    return {
        "summary": _get(node, "header", "description"),
        "highlights": [{"title": m.get("title"), "value": m.get("value")} for m in _get(node, "header", "primaryMetrics") or []
                       if isinstance(m, dict)] or None,
        "charts": charts or None,
    }


def property_profile(html):
    """A /property/<address-slug>/ page -> the address record: attributes,
    sale / listing timeline, value estimate (null when the site withholds
    it: the AVM loads client-side for a property that is currently listed),
    government overlays, boundary, current listings, neighbours, the local
    market, the suburb's agents and the ABS demographics."""
    profile = _get(state(html), "resi-property_property-profile", "property_detail_data", "propertyProfile")
    if not isinstance(profile, dict):
        return None
    prop = profile.get("property") or {}
    attrs = prop.get("attributes") or {}
    media = prop.get("propertyMedia") or {}
    boundary = prop.get("propertyBoundary") or {}
    rings = []
    for ring in boundary.get("geometry") or []:
        rings.append([{"latitude": p.get("lat"), "longitude": p.get("lng")} for p in ring if isinstance(p, dict)])
    listings = []
    for row in profile.get("listings") or []:
        if not isinstance(row, dict):
            continue
        listings.append({
            "id": row.get("id"), "link": _get(row, "link", "href"), "status": row.get("statusDescription"),
            "price": {"display": row.get("displayPrice"), "amount": money(row.get("displayPrice")), "currency": "AUD"},
            "agency": _agency(row.get("agency")),
            "lead_agent": {**(_agent(row.get("leadAgent")) or {}),
                           "sold_as_lead_agent": _int(_get(row, "leadAgent", "agentPerformance", "propertyTransactions", "displayValue")),
                           "median_sale_price": money(_get(row, "leadAgent", "agentPerformance", "medianPrice", "displayValue"))}
            if row.get("leadAgent") else None,
        })
    status = prop.get("statusBadge") or {}
    return {
        "id": prop.get("id"),
        "slug": prop.get("slug"),
        "link": prop.get("propertyPageLink"),
        "address": {"short": prop.get("shortAddress"), "full": prop.get("fullAddress"), "street": prop.get("streetName"),
                    "suburb": prop.get("suburb"), "state": prop.get("state"), "postcode": prop.get("postcode"),
                    "latitude": _get(prop, "geocode", "latitude"), "longitude": _get(prop, "geocode", "longitude")},
        "status": status.get("label"),
        "status_note": status.get("information"),
        "market_status": prop.get("marketStatus") or None,
        "current_listing_id": prop.get("displayListingId"),
        "property_type": attrs.get("propertyType"),
        "bedrooms": _attribute(attrs.get("bedrooms")),
        "bathrooms": _attribute(attrs.get("bathrooms")),
        "parking_spaces": _attribute(attrs.get("carSpaces")),
        "land_size": {"value": _attribute(attrs.get("landArea")), "unit": "m²", "display": _get(attrs, "landArea", "display")}
        if attrs.get("landArea") else None,
        "floor_size": {"value": _attribute(attrs.get("floorArea")), "unit": "m²", "display": _get(attrs, "floorArea", "display")}
        if attrs.get("floorArea") else None,
        "building_size": {"value": _attribute(attrs.get("buildingArea")), "unit": "m²", "display": _get(attrs, "buildingArea", "display")}
        if attrs.get("buildingArea") else None,
        "year_built": _attribute(attrs.get("yearBuilt")),
        "storeys": _attribute(attrs.get("storeys")),
        "features": {key: _attribute(attrs.get(key)) for key in
                     ("study", "garden", "openPlan", "solarPanels", "fullyFenced", "swimmingPool", "roofType", "roofColour",
                      "roofHeight", "groundElevation") if key in attrs} or None,
        "energy_efficiency": prop.get("energyEfficiency"),
        "valuation": {"sale": _valuation(_get(prop, "valuations", "sale")), "rental": _valuation(_get(prop, "valuations", "rental"))},
        "valuation_insights": {
            "sale_confidence": _get(profile, "avmInsightsMetrics", "sale", "confidence"),
            "change_since_last_month_percent": _float(_get(profile, "avmInsightsMetrics", "sale", "sinceLastMonthAvmChange", "percent")),
            "change_since_last_sale_percent": _float(_get(profile, "avmInsightsMetrics", "sale", "sinceLastSaleAvmChange", "percent")),
            "estimated_rental_yield_percent": _float(_get(profile, "avmInsightsMetrics", "rental", "estimatedRentalYield", "percent")),
            "suburb_rental_yield_percent": _float(_get(profile, "avmInsightsMetrics", "rental", "suburbAverageRentalYield", "percentDisplay")),
        } if profile.get("avmInsightsMetrics") else None,
        "timeline": _timeline(prop.get("propertyTimeline")),
        "listings": listings,
        "media": {"images_count": media.get("imageCount"), "floorplans_count": media.get("floorplanCount"),
                  "main_image": image(media.get("mainImage")),
                  "images": images([m.get("image") for m in media.get("media") or [] if isinstance(m, dict) and m.get("mediaType") == "image"]),
                  "floorplans": images([m.get("image") for m in media.get("media") or [] if isinstance(m, dict) and m.get("mediaType") == "floorplan"])},
        "boundary": rings or None,
        "government_overlays": _overlays(prop.get("governmentOverlays")),
        "street": {"name": prop.get("streetName"), "link": _get(profile, "streetDetails", "link", "url", "href")},
        "neighbours": [{"address": n.get("fullAddress"), "slug": n.get("slug"), "link": n.get("propertyPageLink")}
                       for n in _get(profile, "streetDetails", "neighbouringProperties") or [] if isinstance(n, dict)],
        "local_market": _local_market(profile.get("localMarketActivity")),
        "local_agents": [{**(_agent(a) or {}), "agency": _agency(a.get("agency")),
                          "listings_as_lead_agent": a.get("primaryListerCount"), "listings_as_secondary_agent": a.get("secondaryListerCount")}
                         for a in _get(profile, "agentSearch", "items") or [] if isinstance(a, dict)],
        "demographics": _demographics(profile.get("demographics")),
        "property_com_au_link": _get(profile, "pca", "pcaPropertyLink", "href"),
    }


# ---- auction results ------------------------------------------------------------------------

def _auction_stats(node):
    if not isinstance(node, dict):
        return None
    auction = node.get("auction") or {}

    def bucket(key):
        row = auction.get(key) or {}
        return {"count": row.get("count"), "percent": row.get("rate")} if row else None
    return {
        "clearance_rate_percent": auction.get("clearanceRate"),
        "results_available": auction.get("resultsAvailable"),
        "scheduled": auction.get("scheduled"),
        "sold_prior": bucket("soldPriorTo"),
        "sold_at_auction": bucket("soldAt"),
        "sold_via_auction": bucket("soldVia"),
        "sold_after": bucket("soldAfter"),
        "passed_in": bucket("passedIn"),
        "withdrawn": bucket("withdrawn"),
        "private_sales": node.get("privateSale"),
        "off_market_sales": node.get("offMarket"),
        "updated_at": node.get("updatedAt"),
    }


def _auction_result(node):
    if not isinstance(node, dict):
        return None
    listing = node.get("listing") or {}
    return {
        "event_id": node.get("eventId"),
        "event_type": node.get("eventType"),
        "outcome": _get(node, "outcome", "display"),
        "outcome_code": _get(node, "outcome", "value"),
        "price": {"display": _get(node, "price", "display"), "amount": money(_get(node, "price", "display")), "currency": "AUD"},
        "listing": {
            "link": _first(_get(listing, "trackedCanonical", "templatedUrl", default="").split("?")[0] or None,
                           listing.get("canonicalLink")),
            "address": listing.get("address"),
            "property_type": _get(listing, "propertyType", "display"),
            "bedrooms": listing.get("numBedrooms"),
            "size": listing.get("size"),
            "main_image": image(listing.get("mainImage")),
            "agency": {"name": _get(listing, "listingCompany", "name"), "link": link(_get(listing, "listingCompany", "agencyProfile")),
                       "logo": image(_get(listing, "listingCompany", "logo"), LOGO_SIZE)} if listing.get("listingCompany") else None,
            "agents": [{"name": l.get("name"), "link": link(l.get("_links") or l.get("profileUrl")), "photo": image(l.get("photo"), PHOTO_SIZE)}
                       for l in listing.get("listers") or [] if isinstance(l, dict)] or None,
        },
    }


def auction_results(html):
    """An /auction-results/<state> page -> the week's state statistics and a
    per-suburb count table; an /auction-results/<suburb-slug> page -> the
    same statistics plus every auction (and private-sale) result in the
    suburb."""
    root = _get(state(html), "resi-property_sales-events-web") or {}
    body = _get(root, "state", "body") or _get(root, "location", "body")
    if not isinstance(body, dict):
        return None
    data = body.get("data") or {}
    suburb = data.get("suburb") or {}
    return {
        "week": {"from": date(body.get("startDate")), "to": date(body.get("endDate"))},
        "state": {"code": _get(data, "state", "urlValue"), "name": _get(data, "state", "display", "long"),
                  "capital_city": _get(data, "state", "capitalCity")},
        "suburb": {"name": suburb.get("name"), "postcode": suburb.get("postcode"), "slug": suburb.get("urlValue")} if suburb else None,
        "statistics": _auction_stats(data.get("stateStats")),
        "suburbs": [{"suburb": _get(r, "suburb", "name"), "postcode": _get(r, "suburb", "postcode"),
                     "slug": _get(r, "suburb", "urlValue"), "results_count": r.get("resultCount")}
                    for r in data.get("suburbResults") or [] if isinstance(r, dict)] if "suburbResults" in data else None,
        "results": [r for r in (_auction_result(x) for x in data.get("auctionResults") or []) if r] if "auctionResults" in data else None,
        "private_sale_results": [r for r in (_auction_result(x) for x in data.get("privateSaleResults") or []) if r]
        if "privateSaleResults" in data else None,
    }


# ---- open JSON hosts ------------------------------------------------------------------------------

def suggestions(payload):
    """suggest.realestate.com.au -> [{type, display, id, ...}] with the token
    each other endpoint takes for the place."""
    out = []
    for s in _get(payload, "_embedded", "suggestions") or []:
        if not isinstance(s, dict):
            continue
        kind = s.get("type")
        source = s.get("source") or {}
        display = _get(s, "display", "text")
        row = {"type": kind, "display": display, "id": s.get("id"), "atlas_id": source.get("atlasId"),
               "name": source.get("name"), "state": source.get("state"), "postcode": source.get("postcode")}
        if kind == "address":
            row.update({"name": source.get("shortAddress"), "street": source.get("streetName"), "suburb": source.get("suburb"),
                        "lot_number": source.get("lotNumber"), "property_page_link": source.get("url")})
        if kind in ("suburb", "region", "postcode", "state", "street") and display:
            row["search_location"] = display
        if kind == "suburb" and source.get("name") and source.get("state") and source.get("postcode"):
            row["slug"] = re.sub(r"[^a-z0-9]+", "-", f"{source['name']} {source['state']} {source['postcode']}".lower()).strip("-")
        out.append(row)
    return out


def schools(payload):
    """school-service.realestate.com.au closest_by_type -> {primary, secondary,
    all} lists of {name, type, sector, years, address, latitude, longitude,
    distance_m, link}."""
    def row(s):
        if not isinstance(s, dict):
            return None
        address = s.get("address") or {}
        return {
            "name": s.get("name"), "type": s.get("school_type"), "sector": s.get("sector"), "years": s.get("year_range"),
            "address": {"street": address.get("street"), "suburb": address.get("suburb"), "state": address.get("state"),
                        "postcode": address.get("postcode")},
            "latitude": _get(s, "location", "latitude"), "longitude": _get(s, "location", "longitude"),
            "distance_m": _get(s, "distance", "value") if _get(s, "distance", "unit") in (None, "m") else None,
            "link": s.get("url"),
        }
    if not isinstance(payload, dict):
        return None
    return {key: [r for r in (row(x) for x in payload.get(key) or []) if r] for key in ("primary", "secondary", "all")}
