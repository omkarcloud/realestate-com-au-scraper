"""The 11 Realestate Com Au endpoints. Every path is served with and without
the `/realestate-com-au` prefix, so code generated against the hosted API on
RapidAPI (paths like /properties/details) runs unchanged against this server.

Each route validates its query with the module's own schema
(realestate_com_au/schemas.py: one param per input, a bare id OR the site
link), calls the module and maps failures to HTTP:

    bad params / site rejected the request   400
    listing / agent / agency / place unknown 404
    Kasada block, transport failure          500
"""
import json
from urllib.parse import urlencode

from bottle import request, response, route

from realestate_com_au import api, schemas
from schema_fields import load_query
from scraper_errors import BadRequest, NotFound

PREFIX = "/realestate-com-au"


def json_response(data, status=200):
    response.status = status
    response.content_type = "application/json"
    return json.dumps(data, ensure_ascii=False)


def query_dict():
    """The request query as unicode strings (bottle 0.12's .get() hands back
    latin-1 decoded bytes, so a UTF-8 "Mérimbula" would arrive mangled)."""
    return {key: request.query.getunicode(key) for key in request.query.keys()}


def _page_link(path, params, page):
    if not page:
        return None
    query = {k: v for k, v in params.items() if v not in (None, "", False)}
    query["page"] = page
    scheme, host = request.urlparts.scheme, request.urlparts.netloc
    return f"{scheme}://{host}{path}?{urlencode(query, doseq=True)}"


def paginate(result, path, params):
    """Lift the module's `pagination` block into the flat shape the hosted
    API returns: count / per_page / current_page / total_pages / next /
    previous first, then the result."""
    pagination = result.pop("pagination", None) or {}
    page = int(pagination.get("page") or params.get("page") or 1)
    if "has_next" in pagination:
        has_next = bool(pagination["has_next"])
        total_pages = pagination.get("total_pages")
    else:
        total_pages = max(int(pagination.get("total_pages") or 0), 0)
        has_next = page < total_pages
    out = {
        "count": pagination.get("total_count"),
        "per_page": pagination.get("items_per_page"),
        "current_page": page,
        "total_pages": total_pages,
        "next": _page_link(path, params, page + 1 if has_next else None),
        "previous": _page_link(path, params, page - 1 if page > 1 else None),
    }
    out.update(result)
    return out


def call(path, schema, impl, paginated=False):
    raw = query_dict()
    data, error = load_query(schema, raw)
    if error:
        return json_response(error, 400)
    try:
        result = impl(**data)
    except ValueError as e:
        return json_response({"error": str(e)}, 400)
    except BadRequest as e:
        return json_response({"error": f"realestate.com.au rejected the request: {e}"}, 400)
    except NotFound as e:
        return json_response({"error": str(e) or "not found"}, 404)
    except Exception as e:                 # Kasada block / retries exhausted
        return json_response({"error": f"realestate-com-au {path.strip('/')} failed: {e}"}, 500)
    if paginated:
        result = paginate(result, request.path, raw)
    return json_response(result)


ENDPOINTS = [
    ("/properties/details", schemas.ListingSchema, api.property_details, False),
    ("/locations/autocomplete", schemas.LocationsAutocompleteSchema, api.locations_autocomplete, False),
    ("/properties/search", schemas.PropertiesSearchSchema, api.properties_search, True),
    ("/properties/history", schemas.PropertySchema, api.property_history, False),
    ("/properties/schools", schemas.SchoolsSchema, api.property_schools, False),
    ("/suburbs/profile", schemas.SuburbSchema, api.suburb_profile, False),
    ("/auctions/results", schemas.AuctionsSchema, api.auction_results, False),
    ("/agents/search", schemas.AgentsSearchSchema, api.agents_search, True),
    ("/agents/details", schemas.AgentSchema, api.agent_details, False),
    ("/agencies/search", schemas.AgenciesSearchSchema, api.agencies_search, True),
    ("/agencies/details", schemas.AgencySchema, api.agency_details, False),
]


def mount(path, schema, impl, paginated):
    """Serve one endpoint at /path and /realestate-com-au/path."""
    def handler():
        return call(path, schema, impl, paginated)
    handler.__name__ = "realestate_com_au_" + path.strip("/").replace("/", "_")
    route(path, method="GET")(handler)
    route(PREFIX + path, method="GET")(handler)


for _path, _schema, _impl, _paginated in ENDPOINTS:
    mount(_path, _schema, _impl, _paginated)


@route("/", method="GET")
@route("/health", method="GET")
def health():
    return json_response({"status": "ok", "endpoints": [p for p, *_ in ENDPOINTS]})
