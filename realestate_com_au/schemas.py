"""Marshmallow request schemas for every /realestate-com-au/* route.

ONE param per input (tripadvisor QueryOrIdField convention, never a sibling
`url` / `id` pair); every record param also accepts the site link for the
same record (resolvers in realestate_com_au/refs.py):

    location   properties/search: free text ("Mosman, NSW 2088", "2088",
               "Sydney - Greater Region, NSW", "NSW"; several joined by ";")
               OR a pasted search link (its own filters carry through)
    listing    a listing id (152216904) OR a listing link
    property   an address slug (1-buena-vista-ave-mosman-nsw-2088), the
               autocomplete's address id, OR a /property/<slug>/ link
    agent      a salesperson id (58466) OR an /agent/... link
    agency     an agency id (PCSWUZ) OR an /agency/... link
    suburb     "Mosman, NSW 2088" / mosman-nsw-2088 OR a /nsw/mosman-2088/ link
    place      agents/agencies search: the same suburb forms, a region, OR a
               /find-agent/... link
    location   auctions/results: a state code, a suburb, OR the results link
"""
from marshmallow import ValidationError, validates_schema

from realestate_com_au import refs
from schema_fields import (BaseSchema, ChoiceField, CommaListField, Flag, LimitField, PageField, PositiveInt,
                           Price, QueryField, RefField, StrippedString)

SEARCH_MAX_PAGE = 80        # the site serves at most 80 pages (2,000 results) per search
DIRECTORY_MAX_PAGE = 200


class SearchLocationField(RefField):
    resolver = staticmethod(refs.resolve_search_location)


class ListingRefField(RefField):
    resolver = staticmethod(refs.resolve_listing)


class PropertyRefField(RefField):
    resolver = staticmethod(refs.resolve_property)


class AgentRefField(RefField):
    resolver = staticmethod(refs.resolve_agent)


class AgencyRefField(RefField):
    resolver = staticmethod(refs.resolve_agency)


class SuburbRefField(RefField):
    resolver = staticmethod(refs.resolve_suburb)


class DirectoryLocationField(RefField):
    resolver = staticmethod(refs.resolve_directory_location)


class AuctionLocationField(RefField):
    resolver = staticmethod(refs.resolve_auction_location)


class LocationsAutocompleteSchema(BaseSchema):
    query = QueryField(max_length=100, metadata={
        "description": "start of a suburb, region, postcode, state, street or street address"})
    types = CommaListField(allowed=list(refs.SUGGESTION_TYPES), upper=False, metadata={
        "description": "comma list of suggestion types to return: suburb, region, postcode, state, street, address "
                       "(default: all)"})
    limit = LimitField(default=10, max_size=20, metadata={"description": "suggestions to return (max 20)"})


class PropertiesSearchSchema(BaseSchema):
    location = SearchLocationField(metadata={
        "description": "suburb ('Mosman, NSW 2088'), postcode ('2088'), region ('Sydney - Greater Region, NSW') "
                       "or state ('NSW'); several joined by ';'. A pasted realestate.com.au search link works too "
                       "and keeps its own filters"})
    channel = ChoiceField(list(refs.CHANNELS), load_default="buy", metadata={
        "description": "buy (for sale, default), rent or sold"})
    property_type = CommaListField(allowed=list(refs.PROPERTY_TYPES), upper=False, metadata={
        "description": "comma list of house, apartment, unit, townhouse, villa, land, acreage, rural, retirement, "
                       "block_of_units"})
    beds_min = PositiveInt(max_value=5, metadata={"description": "minimum bedrooms (1-5)"})
    beds_max = PositiveInt(max_value=5, metadata={"description": "maximum bedrooms (1-5)"})
    baths_min = PositiveInt(max_value=5, metadata={"description": "minimum bathrooms (1-5)"})
    cars_min = PositiveInt(max_value=5, metadata={"description": "minimum parking spaces (1-5)"})
    price_min = Price(metadata={"description": "minimum price in AUD (weekly rent for channel=rent)"})
    price_max = Price(metadata={"description": "maximum price in AUD (weekly rent for channel=rent)"})
    land_min = Price(metadata={"description": "minimum land size in m²"})
    land_max = Price(metadata={"description": "maximum land size in m²"})
    keywords = CommaListField(upper=False, max_items=10, metadata={
        "description": "comma list of words the listing must mention (pool, garage, ocean view...)"})
    sort = ChoiceField(list(refs.SORTS), metadata={
        "description": "relevance (default), newest, price_asc, price_desc, sold_date (sold channel)"})
    surrounding = Flag(metadata={
        "description": "include listings from surrounding suburbs (the site's default, true); false = the named "
                       "place only"})
    exclude_under_contract = Flag(metadata={"description": "true: drop listings already under contract / offer"})
    exclude_no_price = Flag(metadata={"description": "true: drop listings without a displayed price"})
    exclude_auctions = Flag(metadata={"description": "true: drop auction listings"})
    exclude_private_sales = Flag(metadata={"description": "true: drop private-sale listings"})
    exclude_deposit_taken = Flag(metadata={"description": "true (rent): drop rentals with a deposit taken"})
    page = PageField(max_page=SEARCH_MAX_PAGE, metadata={"description": "1-based page of 25 results (max 80)"})

    @validates_schema
    def _ranges(self, data, **kwargs):
        for low, high in (("beds_min", "beds_max"), ("price_min", "price_max"), ("land_min", "land_max")):
            if data.get(low) is not None and data.get(high) is not None and data[low] > data[high]:
                raise ValidationError(f"Must not be below {low}.", high)


class ListingSchema(BaseSchema):
    listing = ListingRefField(metadata={"description": "listing id (152216904) or a realestate.com.au listing link"})


class PropertySchema(BaseSchema):
    property = PropertyRefField(metadata={
        "description": "address slug (1-buena-vista-ave-mosman-nsw-2088), an address id from locations/autocomplete, "
                       "or a realestate.com.au property page link"})


class SchoolsSchema(BaseSchema):
    location = StrippedString(required=True, metadata={
        "description": "a listing id / listing link (the schools around that property), or 'latitude,longitude'"})
    limit = LimitField(default=5, max_size=20, metadata={"description": "schools per type (max 20)"})

    @validates_schema
    def _location_form(self, data, **kwargs):
        value = data.get("location") or ""
        match = refs.LATLNG_RE.match(value)
        if match:
            lat, lng = float(match.group(1)), float(match.group(2))
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValidationError("Latitude must be -90..90 and longitude -180..180.", "location")
            data["location"] = {"latitude": lat, "longitude": lng}
            return
        try:
            data["location"] = {"listing": refs.resolve_listing(value)}
        except ValueError:
            raise ValidationError("Must be 'latitude,longitude', a listing id or a realestate.com.au listing link.",
                                  "location")


class AgentsSearchSchema(BaseSchema):
    location = DirectoryLocationField(metadata={
        "description": "suburb ('Mosman, NSW 2088' or mosman-nsw-2088), a region ('Sydney - Greater Region, NSW') "
                       "or a realestate.com.au find-agent link"})
    page = PageField(max_page=DIRECTORY_MAX_PAGE, metadata={"description": "1-based page of 24 agents"})


class AgentSchema(BaseSchema):
    agent = AgentRefField(metadata={"description": "agent id (58466) or a realestate.com.au agent link"})


class AgenciesSearchSchema(BaseSchema):
    location = DirectoryLocationField(metadata={
        "description": "suburb ('Mosman, NSW 2088' or mosman-nsw-2088), a region, or a realestate.com.au "
                       "find-agency link"})
    page = PageField(max_page=DIRECTORY_MAX_PAGE, metadata={"description": "1-based page of 12 agency groups"})


class AgencySchema(BaseSchema):
    agency = AgencyRefField(metadata={"description": "agency id (PCSWUZ) or a realestate.com.au agency link"})


class SuburbSchema(BaseSchema):
    suburb = SuburbRefField(metadata={
        "description": "suburb as 'Mosman, NSW 2088' (or mosman-nsw-2088), or a realestate.com.au suburb profile link"})


class AuctionsSchema(BaseSchema):
    location = AuctionLocationField(metadata={
        "description": "state code (nsw, vic, qld, wa, sa, tas, act, nt) for the week's statistics and per-suburb "
                       "counts, or a suburb ('Mosman, NSW 2088') for its individual results; a realestate.com.au "
                       "auction-results link works too"})
