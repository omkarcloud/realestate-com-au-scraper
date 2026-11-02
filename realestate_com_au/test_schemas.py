"""Offline tests for the /realestate-com-au/* request schemas.

    python -m pytest realestate_com_au/test_schemas.py -q
"""
import os
import sys

import pytest
from marshmallow import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from realestate_com_au import schemas  # noqa: E402


def test_search_schema_defaults_and_mapping():
    loaded = schemas.PropertiesSearchSchema().load({"location": " Mosman, NSW 2088 "})
    assert loaded["location"] == {"location": "mosman,+nsw+2088"}
    assert loaded["channel"] == "buy" and loaded["page"] == 1 and loaded["property_type"] is None
    loaded = schemas.PropertiesSearchSchema().load({
        "location": "2088", "channel": "Rent", "property_type": "Apartment, unit,house", "beds_min": "2",
        "beds_max": "3", "price_min": "500", "price_max": "900", "sort": "price_asc", "surrounding": "no",
        "exclude_deposit_taken": "1", "keywords": "pool, garage", "page": "3"})
    assert loaded["channel"] == "rent" and loaded["property_type"] == ["apartment", "unit", "house"]
    assert loaded["beds_min"] == 2 and loaded["price_max"] == 900.0 and loaded["surrounding"] is False
    assert loaded["exclude_deposit_taken"] is True and loaded["keywords"] == ["pool", "garage"] and loaded["page"] == 3
    link = "https://www.realestate.com.au/sold/in-bondi,+nsw+2026/list-2?activeSort=solddate"
    assert schemas.PropertiesSearchSchema().load({"location": link})["location"]["link"]["channel"] == "sold"


@pytest.mark.parametrize("query,field", [
    ({}, "location"),
    ({"location": "x", "channel": "lease"}, "channel"),
    ({"location": "x", "property_type": "castle"}, "property_type"),
    ({"location": "x", "beds_min": "3", "beds_max": "2"}, "beds_max"),
    ({"location": "x", "price_min": "900", "price_max": "500"}, "price_max"),
    ({"location": "x", "page": "81"}, "page"),
    ({"location": "x", "sort": "cheapest"}, "sort"),
    ({"location": "https://example.com/buy/in-x/list-1"}, "location"),
    ({"location": "x", "url": "y"}, "url"),
])
def test_search_schema_rejects(query, field):
    with pytest.raises(ValidationError) as e:
        schemas.PropertiesSearchSchema().load(query)
    assert field in e.value.messages


def test_record_schemas():
    assert schemas.ListingSchema().load({"listing": "https://www.realestate.com.au/property-house-nsw-mosman-152216904"}) == \
        {"listing": "152216904"}
    assert schemas.PropertySchema().load({"property": "1-buena-vista-ave-mosman-nsw-2088"}) == \
        {"property": "/property/1-buena-vista-ave-mosman-nsw-2088/"}
    assert schemas.AgentSchema().load({"agent": "https://www.realestate.com.au/agent/david-murphy-58466"}) == {"agent": "58466"}
    assert schemas.AgencySchema().load({"agency": "pcswuz"}) == {"agency": "PCSWUZ"}
    assert schemas.SuburbSchema().load({"suburb": "Mosman, NSW 2088"}) == {"suburb": "/nsw/mosman-2088/"}
    assert schemas.AuctionsSchema().load({"location": "VIC"}) == {"location": "/auction-results/vic"}
    assert schemas.AgentsSearchSchema().load({"location": "Mosman, NSW 2088", "page": "2"}) == \
        {"location": "mosman-nsw-2088", "page": 2}
    assert schemas.AgenciesSearchSchema().load({"location": "mosman-nsw-2088"}) == {"location": "mosman-nsw-2088", "page": 1}
    for schema, field, value in ((schemas.ListingSchema, "listing", "abc"), (schemas.PropertySchema, "property", "1 Buena"),
                                 (schemas.AgentSchema, "agent", "x"), (schemas.AgencySchema, "agency", "123"),
                                 (schemas.SuburbSchema, "suburb", "Mosman"), (schemas.AuctionsSchema, "location", "Sydney"),
                                 (schemas.ListingSchema, "listing", "")):
        with pytest.raises(ValidationError) as e:
            schema().load({field: value})
        assert field in e.value.messages
    with pytest.raises(ValidationError):
        schemas.ListingSchema().load({"listing": "152216904", "id": "152216904"})


def test_schools_schema():
    loaded = schemas.SchoolsSchema().load({"location": "-33.84, 151.24"})
    assert loaded == {"location": {"latitude": -33.84, "longitude": 151.24}, "limit": 5}
    loaded = schemas.SchoolsSchema().load({"location": "https://www.realestate.com.au/property-152216904", "limit": "10"})
    assert loaded == {"location": {"listing": "152216904"}, "limit": 10}
    for bad in ("Mosman", "95,10", ""):
        with pytest.raises(ValidationError):
            schemas.SchoolsSchema().load({"location": bad})


def test_autocomplete_schema():
    loaded = schemas.LocationsAutocompleteSchema().load({"query": "mos", "types": "Suburb,address"})
    assert loaded == {"query": "mos", "types": ["suburb", "address"], "limit": 10}
    with pytest.raises(ValidationError):
        schemas.LocationsAutocompleteSchema().load({"query": "mos", "types": "school"})
    with pytest.raises(ValidationError):
        schemas.LocationsAutocompleteSchema().load({"query": "mos", "limit": "21"})
