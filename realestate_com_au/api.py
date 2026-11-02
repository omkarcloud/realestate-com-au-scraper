"""The /realestate-com-au/* endpoint functions (route_glue's route_table
calls them with the schema's loaded kwargs). Every endpoint caches its own
parsed result through cache.cached_call keyed on the validated params
(TTLs in cache_config.py); properties/details and properties/schools (by
listing id) share ONE cached listing page parse (_listing_record), so the
schools around a listing never cost a second page.

Every www page costs one slot of a Kasada identity that serves ~65-110
pages (fetch.py), so each endpoint fetches exactly the page it needs.
"""
from cache import cached_call
from realestate_com_au import cache_config as ttl
from realestate_com_au import parsers, refs
from realestate_com_au.fetch import (RealestateNotFound, RealestateUpstreamError, fetch_page, fetch_schools,
                                     fetch_suggestions)

SEARCH_PAGE_SIZE = 25        # the site's own page size
AGENTS_PAGE_SIZE = 24
AGENCIES_PAGE_SIZE = 12


def _parsed(parse, html, label):
    record = parse(html)
    if record is None:
        raise RealestateUpstreamError(f"{label}: page carried no state")
    return record


# ---- locations/autocomplete ---------------------------------------------------------------

def _autocomplete(query, types, limit):
    types = types or list(refs.SUGGESTION_TYPES)
    rows = parsers.suggestions(fetch_suggestions(query, types, limit))
    return {"query": query, "count": len(rows), "results": rows}


def locations_autocomplete(**data):
    return cached_call("realestate_com_au.autocomplete", data, _autocomplete, ttl.AUTOCOMPLETE_CACHE)


# ---- properties/search ---------------------------------------------------------------------

def _search(location, channel, page, property_type=None, beds_min=None, beds_max=None, baths_min=None,
            cars_min=None, price_min=None, price_max=None, land_min=None, land_max=None, keywords=None,
            sort=None, surrounding=None, exclude_under_contract=None, exclude_no_price=None,
            exclude_auctions=None, exclude_private_sales=None, exclude_deposit_taken=None):
    excludes = [name for name, flag in (
        ("exclude_under_contract", exclude_under_contract), ("exclude_no_price", exclude_no_price),
        ("exclude_auctions", exclude_auctions), ("exclude_private_sales", exclude_private_sales),
        ("exclude_deposit_taken", exclude_deposit_taken)) if flag]
    types = []
    for name in property_type or []:
        token = refs.PROPERTY_TYPES[name]
        if token not in types:
            types.append(token)
    path = refs.search_path(
        channel, location=location.get("location"), link=location.get("link"), page=page,
        property_types=types, beds_min=beds_min, beds_max=beds_max, baths_min=baths_min, cars_min=cars_min,
        price_min=price_min, price_max=price_max, land_min=land_min, land_max=land_max, keywords=keywords,
        sort=sort, surrounding=surrounding, excludes=excludes)
    parsed = _parsed(parsers.search_results, fetch_page(path, f"search {path}"), "search")
    # A page past the end is an empty page (the site answers it 200 with a
    # 0 total), never an error; the totals stay those the site publishes.
    total = parsed["total_count"] or 0
    total_pages = parsed["total_pages"] if parsed["results"] else None
    return {
        "channel": parsed["channel"],
        "localities": parsed["localities"],
        "sort": parsed["sort"],
        "applied_filters": parsed["filters"],
        "search_link": refs.SITE + path,
        "surrounding_count": parsed["surrounding_count"],
        "results": parsed["results"],
        "surrounding_results": parsed["surrounding_results"],
        "pagination": {
            "page": page,
            "items_per_page": SEARCH_PAGE_SIZE,
            "total_pages": total_pages if total_pages is not None else max(1, min(80, -(-total // SEARCH_PAGE_SIZE))),
            "total_count": total,
        },
    }


def properties_search(**data):
    return cached_call("realestate_com_au.search", data, _search, ttl.SEARCH_CACHE)


# ---- properties/details + the shared listing record ---------------------------------------

def _listing_page(listing):
    """A listing id is ambiguous: residential listings live at
    /property-<id>, new-development projects at /project/<id>. Try the
    listing first (the common case), then the project once."""
    label = f"listing {listing}"
    try:
        html = fetch_page(refs.listing_path(listing), label)
    except RealestateNotFound:
        html = fetch_page(refs.project_path(listing), label)
    return _parsed(parsers.listing_details, html, label)


def _listing_record(listing):
    return cached_call("realestate_com_au.listing", {"listing": listing}, _listing_page, ttl.LISTING_CACHE)


def property_details(listing):
    """Everything the listing page carries."""
    return _listing_record(listing)


# ---- properties/history (the address page) -------------------------------------------------------

def _property(property):
    return _parsed(parsers.property_profile, fetch_page(property, f"property {property}"), f"property {property}")


def property_history(**data):
    return cached_call("realestate_com_au.property", data, _property, ttl.PROPERTY_CACHE)


# ---- properties/schools ---------------------------------------------------------------------------

def _schools(location, limit):
    if "listing" in location:
        record = _listing_record(location["listing"])
        address = record.get("address") or {}
        latitude, longitude = address.get("latitude"), address.get("longitude")
        if latitude is None or longitude is None:
            raise RealestateNotFound(f"listing {location['listing']} publishes no coordinates")
        origin = {"listing_id": record.get("id"), "address": address.get("full"), "latitude": latitude, "longitude": longitude}
    else:
        latitude, longitude = location["latitude"], location["longitude"]
        origin = {"listing_id": None, "address": None, "latitude": latitude, "longitude": longitude}
    rows = parsers.schools(fetch_schools(latitude, longitude, limit))
    return {"origin": origin, "schools": rows}


def property_schools(**data):
    return cached_call("realestate_com_au.schools", data, _schools, ttl.SCHOOLS_CACHE)


# ---- agents ----------------------------------------------------------------------------------------

def _agents_search(location, page):
    path = f"/find-agent/{location}" + (f"?page={page}" if page > 1 else "")
    parsed = _parsed(parsers.agents_search, fetch_page(path, f"agents in {location}"), "agents search")
    return {
        "location": parsed["location"],
        "surrounding_suburbs": parsed["surrounding_suburbs"],
        "results": parsed["results"],
        "pagination": {
            "page": page,
            "items_per_page": parsed["page_size"] or AGENTS_PAGE_SIZE,
            "total_pages": parsed["total_pages"] or 1,
            "total_count": parsed["total_count"] or 0,
        },
    }


def agents_search(**data):
    return cached_call("realestate_com_au.agents_search", data, _agents_search, ttl.AGENTS_SEARCH_CACHE)


def _agent(agent):
    return _parsed(parsers.agent_profile, fetch_page(refs.agent_path(agent), f"agent {agent}"), f"agent {agent}")


def agent_details(**data):
    return cached_call("realestate_com_au.agent", data, _agent, ttl.AGENT_CACHE)


# ---- agencies -------------------------------------------------------------------------------------

def _agencies_search(location, page):
    path = f"/find-agency/{location}" + (f"?page={page}" if page > 1 else "")
    parsed = _parsed(parsers.agencies_search, fetch_page(path, f"agencies in {location}"), "agencies search")
    return {
        "location": parsed["location"],
        "results": parsed["results"],
        "pagination": {
            "page": page,
            "items_per_page": parsed["page_size"] or AGENCIES_PAGE_SIZE,
            "total_pages": parsed["total_pages"] or 1,
            "total_count": parsed["total_count"] or 0,
        },
    }


def agencies_search(**data):
    return cached_call("realestate_com_au.agencies_search", data, _agencies_search, ttl.AGENTS_SEARCH_CACHE)


def _agency(agency):
    return _parsed(parsers.agency_profile, fetch_page(refs.agency_path(agency), f"agency {agency}"), f"agency {agency}")


def agency_details(**data):
    return cached_call("realestate_com_au.agency", data, _agency, ttl.AGENCY_CACHE)


# ---- suburbs / auctions ----------------------------------------------------------------------------

def _suburb(suburb):
    return _parsed(parsers.suburb_profile, fetch_page(suburb, f"suburb {suburb}"), f"suburb {suburb}")


def suburb_profile(**data):
    return cached_call("realestate_com_au.suburb", data, _suburb, ttl.SUBURB_CACHE)


def _auctions(location):
    return _parsed(parsers.auction_results, fetch_page(location, f"auction results {location}"), "auction results")


def auction_results(**data):
    return cached_call("realestate_com_au.auctions", data, _auctions, ttl.AUCTIONS_CACHE)
