"""Offline tests for the realestate.com.au parsers, reference resolvers and
URL grammar.

    python -m pytest realestate_com_au/test_parsers.py -q

Fixtures are real www.realestate.com.au pages captured 2026-10-30/31
(realestate_com_au/fixtures/), trimmed to the <title>, the canonical link
and the window.ArgonautExchange state script the parsers read: buy / rent /
sold search pages (page 1, page 2, a page past the end, an unknown place,
a filtered search, a region, two localities), a for-sale / sold / rental
listing and a new-development project, the agent and agency directories
(page 1, a page past the end, a region), an agent and an agency profile, a
suburb and a street profile, a listed and an unlisted property-address
page, state and suburb auction results, the site's 404 page and the
Kasada bootstrap page, plus the autocomplete and school-service JSON. No
network.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from realestate_com_au import parsers as P, refs  # noqa: E402

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return json.load(f) if name.endswith(".json") else f.read()


# ---- refs ---------------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("152216904", "152216904"),
    ("https://www.realestate.com.au/property-house-nsw-mosman-152216904", "152216904"),
    ("https://www.realestate.com.au/sold/property-house-nsw-bondi-151817252?x=1", "151817252"),
    ("https://www.realestate.com.au/property-152216904", "152216904"),
    ("https://www.realestate.com.au/project/the-manors-of-mosman-retirement-village-600045596", "600045596"),
])
def test_resolve_listing(value, expected):
    assert refs.resolve_listing(value) == expected


@pytest.mark.parametrize("value", ["", "abc", "12", "https://example.com/property-house-nsw-mosman-152216904",
                                   "https://www.realestate.com.au/agent/david-murphy-58466"])
def test_resolve_listing_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_listing(value)


def test_resolve_agent_and_agency():
    assert refs.resolve_agent("58466") == "58466"
    assert refs.resolve_agent("https://www.realestate.com.au/agent/david-murphy-58466") == "58466"
    assert refs.resolve_agent("https://www.realestate.com.au/agent/58466") == "58466"
    assert refs.resolve_agency("pcswuz") == "PCSWUZ"
    assert refs.resolve_agency("https://www.realestate.com.au/agency/murphy-residential-PCSWUZ?cid=x") == "PCSWUZ"
    assert refs.resolve_agency("https://www.realestate.com.au/agency/PCSWUZ") == "PCSWUZ"
    for bad in ("", "58466", "https://www.realestate.com.au/agent/x"):
        with pytest.raises(ValueError):
            refs.resolve_agency(bad)
    with pytest.raises(ValueError):
        refs.resolve_agent("david murphy")


def test_resolve_property():
    assert refs.resolve_property("1-buena-vista-ave-mosman-nsw-2088") == "/property/1-buena-vista-ave-mosman-nsw-2088/"
    assert refs.resolve_property("https://www.realestate.com.au/property/1-buena-vista-ave-mosman-nsw-2088/") == \
        "/property/1-buena-vista-ave-mosman-nsw-2088/"
    assert refs.resolve_property("256990") == "/property/lookup?id=256990"
    assert refs.resolve_property("https://www.realestate.com.au/property/lookup?id=256990") == "/property/lookup?id=256990"
    with pytest.raises(ValueError):
        refs.resolve_property("1 Buena Vista Ave Mosman")


def test_resolve_suburb_and_directory_and_auction():
    assert refs.resolve_suburb("Mosman, NSW 2088") == "/nsw/mosman-2088/"
    assert refs.resolve_suburb("mosman-nsw-2088") == "/nsw/mosman-2088/"
    assert refs.resolve_suburb("https://www.realestate.com.au/nsw/mosman-2088/") == "/nsw/mosman-2088/"
    with pytest.raises(ValueError):
        refs.resolve_suburb("Mosman")
    assert refs.resolve_directory_location("Mosman, NSW 2088") == "mosman-nsw-2088"
    assert refs.resolve_directory_location("https://www.realestate.com.au/find-agent/mosman-nsw-2088?page=2") == "mosman-nsw-2088"
    assert refs.resolve_directory_location("Sydney - Greater Region, NSW") == "sydney+-+greater+region,+nsw"
    assert refs.resolve_auction_location("NSW") == "/auction-results/nsw"
    assert refs.resolve_auction_location("Mosman, NSW 2088") == "/auction-results/mosman-nsw-2088"
    assert refs.resolve_auction_location("https://www.realestate.com.au/auction-results/vic") == "/auction-results/vic"
    with pytest.raises(ValueError):
        refs.resolve_auction_location("Sydney")


def test_search_location_and_path():
    assert refs.resolve_search_location("Mosman, NSW 2088") == {"location": "mosman,+nsw+2088"}
    assert refs.resolve_search_location("2088") == {"location": "2088"}
    assert refs.resolve_search_location("Mosman, NSW 2088; Cremorne, NSW 2090") == {"location": "mosman,+nsw+2088;+cremorne,+nsw+2090"}
    parsed = refs.resolve_search_location(
        "https://www.realestate.com.au/sold/property-house-in-bondi,+nsw+2026/list-3?activeSort=solddate")
    assert parsed == {"link": {"channel": "sold", "filters": "property-house-in-bondi,+nsw+2026", "page": 3,
                               "query": {"activeSort": "solddate"}}}
    with pytest.raises(ValueError):
        refs.resolve_search_location("https://www.realestate.com.au/agent/x-1")
    assert refs.search_path("buy", location="mosman,+nsw+2088", page=2) == "/buy/in-mosman,+nsw+2088/list-2"
    path = refs.search_path("rent", location="richmond,+vic+3121", page=1, property_types=["unit+apartment"],
                            beds_min=2, beds_max=3, baths_min=1, cars_min=1, price_min=500, price_max=900,
                            land_min=300, keywords=["pool", "garage"], sort="price_asc", surrounding=False,
                            excludes=["exclude_deposit_taken", "exclude_under_contract"])
    assert path.startswith("/rent/property-unit+apartment-with-2-bedrooms-between-500-900-size-300-any-in-richmond,+vic+3121/list-1?")
    query = path.split("?", 1)[1]
    for piece in ("activeSort=price-asc", "includeSurrounding=false", "keywords=pool,garage", "maxBeds=3",
                  "numBaths=1", "numParkingSpaces=1", "misc=ex-deposit-taken,ex-under-contract"):
        assert piece in query
    # a pasted link keeps its filters, the page is replaced
    assert refs.search_path("buy", link=parsed["link"], page=5) == "/sold/property-house-in-bondi,+nsw+2026/list-5?activeSort=solddate"
    bare = refs.resolve_search_location("https://www.realestate.com.au/rent/")
    assert refs.search_path("buy", link=bare["link"], page=2) == "/rent/list-2"


# ---- value helpers ----------------------------------------------------------------------------

def test_value_helpers():
    assert P.money("$2,750,000") == 2750000
    assert P.money("$520 per week") == 520
    assert P.money("$7.95m") == 7950000
    assert P.money("Contact agent") is None
    assert P.money("$3,000 Monthly") == 3000 and P.money("$2.5 million") == 2500000
    assert P.price_range("$780,000 - $850,000") == (780000, 850000)
    assert P.price_range("Price Guide: $1.9 - $2.0 million") == (1900000, 2000000)
    assert P.price_range("$900,000 - $1.1M") == (900000, 1100000)
    assert P.date("25 Aug 2026") == "2026-08-25"
    assert P.date("Wed 28 Oct 2026") == "2026-10-28"
    assert P.date("21 September, 2026") == "2026-09-21"
    assert P.date("2026-07-31") == "2026-07-31"
    assert P.date("Sold") is None
    assert P.image({"templatedUrl": "https://i2.au.reastatic.net/{size}/abc/image.jpg"}) == \
        "https://i2.au.reastatic.net/1144x888/abc/image.jpg"
    assert P.image({"url": "https://i2.au.reastatic.net/{width}x{height}/abc/image.jpg", "templated": True}) == \
        "https://i2.au.reastatic.net/1144x888/abc/image.jpg"
    assert P.link({"canonical": {"href": "https://www.realestate.com.au/agency/x-ABCDEF?cid={cid}"}}) == \
        "https://www.realestate.com.au/agency/x-ABCDEF"
    assert P.text("Hello<br/><br/>World &amp; co") == "Hello\n\nWorld & co"


# ---- search pages ------------------------------------------------------------------------------

def test_search_buy_page():
    r = P.search_results(fixture("search_buy_mosman_p1.html"))
    assert r["channel"] == "buy" and r["total_count"] == 476 and r["total_pages"] == 20 and r["has_next"]
    assert r["localities"][0]["display"] == "Mosman, NSW 2088" and r["localities"][0]["type"] == "suburb"
    assert len(r["results"]) == 25 and r["surrounding_count"] == 315
    card = r["results"][0]
    assert card["id"] == "152216904" and card["link"].endswith("/property-house-nsw-mosman-152216904")
    assert card["property_type"] == "House" and card["bedrooms"] == 6 and card["land_size"] == {"value": 2668.0, "unit": "m²"}
    assert card["agency"]["id"] == "OUZQDC" and card["agents"][0]["name"] == "Michael Coombs"
    assert card["inspections"][0]["starts_at"].startswith("2026-10-31T13:30")
    assert card["media"]["main_image"].startswith("https://i2.au.reastatic.net/1144x888/")
    assert card["price"]["currency"] == "AUD" and card["price"]["amount"] is None
    auction = next(c["auction"] for c in r["results"] if c["auction"])
    assert auction["at"].startswith("2026-11-14") and auction["label"]


def test_search_project_and_filters():
    r = P.search_results(fixture("search_buy_mosman_p2.html"))
    assert r["page"] == 2
    project = next(c for c in r["results"] if c.get("is_project"))
    assert project["id"] == "600045596" and project["price"]["from"] == 1800000 and project["developer"]["type"] == "Developer"
    r = P.search_results(fixture("search_buy_filters_house_3bed_cars.html"))
    assert r["filters"] == {"propertyTypes": ["house"], "bedroomsRange": {"minimum": "3"}, "minimumCars": 2,
                            "minimumBathroom": 2, "surroundingSuburbs": True}
    r = P.search_results(fixture("search_buy_multi_locality.html"))
    assert [l["display"] for l in r["localities"]] == ["Mosman, NSW 2088", "Cremorne, NSW 2090"]
    assert r["sort"] == "price-desc" and r["filters"] is None


def test_search_rent_sold_past_end_unknown():
    r = P.search_results(fixture("search_rent_richmond_p1.html"))
    card = r["results"][0]
    assert r["channel"] == "rent" and card["price"] == {"display": "$520 per week", "amount": 520, "from": 520, "to": 520,
                                                       "currency": "AUD", "period": "week", "note": None}
    assert card["bond"] == {"display": "$2,259", "amount": 2259} and card["available_from"] == "2026-11-21"
    r = P.search_results(fixture("search_sold_bondi_p1.html"))
    assert r["channel"] == "sold" and r["total_pages"] == 80 and r["results"][0]["date_sold"] == "2026-10-29"
    assert r["results"][0]["status"] == "Sold"
    r = P.search_results(fixture("search_buy_past_end_p81.html"))
    assert r["results"] == [] and r["total_count"] == 0 and r["has_next"] is False
    r = P.search_results(fixture("search_buy_unknown_location.html"))
    assert r["localities"] and r["localities"][0]["display"] != "nowhere"
    r = P.search_results(fixture("search_buy_region_sydney_p1.html"))
    assert r["total_count"] == 602 and r["localities"][0]["display"] == "Sydney, NSW"


# ---- listing pages -------------------------------------------------------------------------------

def test_listing_buy_details():
    d = P.listing_details(fixture("listing_buy_152216904.html"))
    assert d["id"] == "152216904" and d["status"] == "For sale" and d["address"]["latitude"] == -33.84119704
    assert d["title"].startswith("A landmark estate") and d["description"].startswith("Opportunities of this scale")
    assert d["agents"][0]["phone"] == "0407980443" and d["agents"][1]["phone"] == "0402280447"
    assert d["agency"]["description"].startswith("The team at Atlas")
    assert d["features"]["top"] == ["Balcony", "Built-in wardrobes", "Dishwasher", "Ensuites: 1"]
    assert d["features"]["categories"][0] == {"title": "About the property",
                                             "items": [{"id": "landSize", "label": "Land size: 2,668m²"}]}
    assert d["nbn"]["connection_type"] == "HFC" and d["nbn"]["download"] == "¹Download: 2000 Mbps"
    assert d["highlights"][0]["headline"] == "Expansive 2,668sqm estate"
    assert d["inspections"][0]["time"] == "1:30 pm–2:00 pm" and d["inspections"][0]["type"] == "INSPECTION"
    assert d["media"]["videos"] == ["https://www.youtube.com/watch?v=bjeZjKpw_fw"] and len(d["media"]["floorplans"]) == 1
    assert d["construction_status"] == "established" and d["is_new_construction"] is False
    assert len(d["related_listings"]) == 3 and d["related_listings"][0]["link"]
    assert d["enquiry_link"].endswith("/contact-agent/listing/152216904")


def test_listing_sold_and_rent_details():
    d = P.listing_details(fixture("listing_sold_151817252.html"))
    assert d["channel"] == "sold" and d["price"]["amount"] == 2750000 and d["date_sold"] == "2026-08-25"
    assert d["page_views"] == {"count": 5486, "as_of": "2026-08-25"}
    assert d["property_page_link"] == "https://www.realestate.com.au/property/8b-castlefield-st-bondi-nsw-2026/"
    assert d["recent_sales"]["items"][0]["id"] == "152175356" and d["recent_sales"]["items"][0]["price"]["amount"] == 3300000
    d = P.listing_details(fixture("listing_rent_440365388.html"))
    assert d["channel"] == "rent" and d["price"]["period"] == "week" and d["bond"]["amount"] == 2259
    assert d["can_apply_online"] is False and d["agents"][0]["phone"] == "0452413634"
    d = P.listing_details(fixture("listing_redirected_152300000.html"))
    assert d["channel"] == "sold" and d["id"] == "152300000"


def test_project_details():
    d = P.listing_details(fixture("project_600045596.html"))
    assert d["is_project"] and d["name"] == "The Manors of Mosman Retirement Village"
    assert d["address"]["latitude"] == -33.82396061 and d["price"]["to"] == 4695000
    assert len(d["child_listings"]) == 10 and d["child_listings"][0]["id"] == "152550052"
    assert d["project_team"][0] == {"role": "Developer", "name": "Aveo Group", "description": d["project_team"][0]["description"]}
    assert d["faq"][0]["question"].startswith("How many bedrooms")


# ---- agents / agencies -------------------------------------------------------------------------------

def test_agents_search():
    a = P.agents_search(fixture("agents_search_mosman_p1.html"))
    assert a["location"]["slug"] == "mosman-nsw-2088" and a["total_count"] == 164 and a["total_pages"] == 7
    assert len(a["results"]) == 24 and len(a["surrounding_suburbs"]) == 10
    row = a["results"][0]
    assert row["id"] == "58466" and row["link"].endswith("/agent/david-murphy-58466")
    assert row["sales"]["sold_count"] == 103 and row["sales"]["by_property_type"]["house"]["median_sold_price"] == 4360000
    assert row["compliments"][0] == {"tag": "Professional", "count": 44} and row["agency"]["id"] == "PCSWUZ"
    past = P.agents_search(fixture("agents_search_mosman_p99.html"))
    assert past["results"] == [] and past["page"] == 99 and past["total_count"] == 165
    region = P.agents_search(fixture("agents_search_region_sydney.html"))
    assert region["total_count"] == 273 and region["location"]["display"] == "Sydney, NSW"


def test_agent_profile():
    g = P.agent_profile(fixture("agent_58466.html"))
    assert g["id"] == "58466" and g["phone"] == "0425312481" and g["in_industry_since"] == 1997
    assert g["sales"]["count"] == 104 and g["sales"]["by_property_type"]["townhouse"]["median_days_on_site"] == 107
    assert len(g["reviews"]) == 68 and g["reviews"][0]["listing"]["id"] == "151725208" and g["reviews"][0]["published_at"] == "2026-07-31"
    assert g["listings"]["sold"]["total_count"] == 103 and len(g["listings"]["sold"]["items"]) == 98
    sold = g["listings"]["sold"]["items"][0]
    assert sold["link"].endswith("/sold/property-apartment-nsw-mosman-150576004") and sold["status_date"] == "2026-04-01"
    assert sold["price"]["amount"] == 1405000 and sold["address"]["latitude"] == -33.82493207
    assert g["listings"]["for_sale"]["total_count"] == 14 and g["agency"]["id"] == "PCSWUZ"


def test_agency_profile():
    y = P.agency_profile(fixture("agency_PCSWUZ.html"))
    assert y["id"] == "PCSWUZ" and y["phone"] == "02 9968 2088" and y["website"] == "http://www.davidmurphy.com.au"
    assert y["address"]["full"] == "40 Cabramatta Road, Mosman, NSW 2088"
    assert y["rating"] == 5 and y["reviews_count"] == 84
    assert len(y["reviews"]["from_sellers"]) == 66 and len(y["reviews"]["from_buyers"]) == 18
    assert y["performance"]["last_12_months"]["sales"]["count"] == 113
    assert y["performance"]["by_suburb"]["sales"][0] == {"suburb": "Mosman", "state": "NSW", "postcode": "2088", "count": 74}
    assert y["performance"]["all_time_note"].startswith("Murphy Residential have sold 1227")
    assert len(y["agents"]) == 12 and y["agents"][0]["sold_as_lead_agent"] == 60
    assert y["listing_counts"] == {"for_sale": 15, "for_rent": 3, "sold": 114, "leased": 89}
    assert y["listings"]["sold"]["total_count"] == 113 and len(y["listings"]["sold"]["items"]) == 108
    assert len(y["spotlight_listings"]) == 5 and y["spotlight_listings"][0]["next_inspection"]


def test_agencies_search():
    s = P.agencies_search(fixture("agencies_search_mosman_p1.html"))
    assert s["total_count"] == 49 and s["total_pages"] == 5 and len(s["results"]) == 12
    group = s["results"][0]
    assert group["group_id"] == "13D8A80W" and group["is_franchise"] and group["reviews_count"] == 638
    office = group["offices"][0]
    assert office["id"] == "ABCMOS" and office["address"]["full"] == "102 Glover Street, Mosman, NSW 2088"
    assert office["performance"]["sales"]["count"] == 97 and office["recent_listings"]["channel"] == "sold"
    assert office["recent_listings"]["items"][0]["id"] == "148886964"
    single = next(g for g in s["results"] if g["name"] == "Murphy Residential")
    assert single["group_id"] is None and single["primary_agency_id"] == "PCSWUZ"
    assert [o["id"] for o in single["offices"]] == ["PCSWUZ"]
    assert single["offices"][0]["address"]["full"] == "40 Cabramatta Road, Mosman, NSW 2088"
    assert single["offices"][0]["link"].endswith("/agency/murphy-residential-PCSWUZ")
    assert single["offices"][0]["recent_listings"]["items"][0]["id"] == "152303708"
    assert all(g["offices"] for g in s["results"])


# ---- suburb / property / auctions ------------------------------------------------------------------------

def test_suburb_profile():
    m = P.suburb_profile(fixture("suburb_mosman_2088.html"))
    assert m["suburb"] == "Mosman" and m["region"] == "Lower North Shore" and len(m["surrounding_suburbs"]) == 10
    house = m["median_price"]["buy"]["house"]["all"]
    assert house["value"] == 5265000 and house["volume"] == 186 and house["change_percent"] == -10.57
    assert len(house["trend"]) == 60 and house["trend"][0]["value"] == 4950000
    assert m["median_price"]["rent"]["unit"]["2"]["value"]
    assert m["rental_yield"]["house"]["all"]["value"] == 2.3
    assert m["supply_demand"]["buy"]["house"]["all"] == {"supply": 59, "demand": 3918}
    assert m["bounds"]["north_east"]["latitude"] == pytest.approx(-33.8033, abs=1e-3)


def test_property_profile_listed_and_unlisted():
    p = P.property_profile(fixture("property_1_buena_vista_ave_listed.html"))
    assert p["id"] == "256990" and p["slug"] == "1-buena-vista-ave-mosman-nsw-2088" and p["status"] == "For sale"
    assert p["current_listing_id"] == "152216904" and p["bedrooms"] == 6 and p["land_size"]["value"] == 2668
    assert p["features"]["swimmingPool"] is True
    assert p["valuation"] == {"sale": None, "rental": None}      # withheld while listed
    assert p["timeline"][0] == {"date": "1995-04-13", "event": "sold", "price": {"display": "$2,600,000", "amount": 2600000, "currency": "AUD"},
                                "agency": None, "agency_id": None, "listing_id": None, "main_image": None, "images_count": None}
    assert p["listings"][0]["lead_agent"]["phone"] == "0407980443" and p["listings"][0]["lead_agent"]["median_sale_price"] == 7950000
    assert p["government_overlays"]["heritage"] == ["House (Item - General)"] and p["government_overlays"]["lot_plan"] == "1 956163"
    assert len(p["boundary"][0]) >= 4 and len(p["neighbours"]) == 5 and len(p["local_agents"]) == 5
    assert p["local_market"]["buy"]["total_count"] == 39 and p["local_market"]["sold"]["listings"][0]["link"]
    assert p["demographics"]["highlights"][0] == {"title": "Most households are", "value": "Families"}
    assert p["media"]["images_count"] == 54 and len(p["media"]["images"]) == 54 and len(p["media"]["floorplans"]) == 2
    u = P.property_profile(fixture("property_55_tasmania_cir_unlisted.html"))
    assert u["status"] == "Off market" and u["current_listing_id"] is None and u["listings"] == []
    assert u["valuation"]["sale"]["low"] == 1920000 and u["valuation"]["sale"]["high"] == 2980000
    assert u["valuation"]["sale"]["as_of"] == "2026-09-21"
    assert u["valuation_insights"]["change_since_last_sale_percent"] == 45.6
    assert len(u["timeline"]) == 3 and u["timeline"][2]["price"]["amount"] == 420000


def test_auction_results():
    s = P.auction_results(fixture("auctions_state_nsw.html"))
    assert s["week"] == {"from": "2026-10-19", "to": "2026-10-25"} and s["state"]["code"] == "nsw"
    assert s["statistics"]["clearance_rate_percent"] == 34 and s["statistics"]["sold_prior"] == {"count": 143, "percent": 17}
    assert len(s["suburbs"]) == 805 and s["suburbs"][0]["slug"] == "aberdare-nsw-2325" and s["results"] is None
    v = P.auction_results(fixture("auctions_state_vic.html"))
    assert v["state"]["code"] == "vic" and v["statistics"]["scheduled"]
    m = P.auction_results(fixture("auctions_suburb_mosman.html"))
    assert m["suburb"]["slug"] == "mosman-nsw-2088" and m["suburbs"] is None and len(m["results"]) == 3
    row = m["results"][0]
    assert row["outcome"] == "Sold at auction" and row["price"]["amount"] is None
    assert row["listing"]["link"] == "https://www.realestate.com.au/sold/property-apartment-nsw-mosman-151104888"
    assert row["listing"]["agency"]["name"] == "Raine & Horne - Mosman" and row["listing"]["agents"][0]["name"]


# ---- open JSON hosts ------------------------------------------------------------------------------------

def test_suggestions_and_schools():
    samples = fixture("suggest_samples.json")
    rows = P.suggestions(samples["mixed"])
    assert rows[0]["type"] == "suburb" and rows[0]["slug"] == "richmond-vic-3121" and rows[0]["search_location"] == "Richmond, VIC 3121"
    assert P.suggestions(samples["state"])[0] == {"type": "state", "display": "New South Wales", "id": "AU-NSW", "atlas_id": None,
                                                  "name": None, "state": None, "postcode": None, "search_location": "New South Wales"}
    assert P.suggestions(samples["region"])[0]["name"] == "Lower North Shore"
    assert P.suggestions(samples["empty"]) == []
    schools = P.schools(fixture("schools_closest_mosman.json"))
    assert {k: len(v) for k, v in schools.items()} == {"primary": 5, "secondary": 5, "all": 5}
    assert schools["primary"][0]["distance_m"] == 692 and schools["primary"][0]["sector"] == "Independent"


# ---- not found / blocked pages ---------------------------------------------------------------------------

def test_pages_without_state():
    for name in ("not_found_404.html", "kasada_bootstrap_429.html"):
        html = fixture(name)
        assert P.state(html) is None
        for parse in (P.search_results, P.listing_details, P.agents_search, P.agent_profile, P.agencies_search,
                      P.agency_profile, P.suburb_profile, P.property_profile, P.auction_results):
            assert parse(html) is None
    assert "KPSDK" in fixture("kasada_bootstrap_429.html")


def test_parsers_never_crash_on_partial_input():
    for parse in (P.listing_card, P.project_card, P.listing_details, P.suggestions, P.schools):
        assert parse({}) in (None, [], {"primary": [], "secondary": [], "all": []}) or isinstance(parse({}), dict)
        assert parse(None) in (None, [])
    assert P.listing_card({"__typename": "BuyResidentialListing", "id": "1"})["id"] == "1"
