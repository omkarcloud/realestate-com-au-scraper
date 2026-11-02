"""Cache TTL per /realestate-com-au/* endpoint (cache.py, keyed on the
validated params). Every upstream page costs one slot of a Kasada identity
that serves ~65-110 pages before the site refuses it (realestate_com_au/
fetch.py), so a cache hit is also a saved mint; the TTLs follow how fast
each page moves on the site. properties/details and properties/schools
share ONE cached listing page parse (api._listing_record), so schools by
listing id never pays a second page fetch.
"""
from datetime import timedelta

# Search results: new listings and price changes land all day; an hour keeps
# a client paging through results on one snapshot.
SEARCH_CACHE = timedelta(hours=1)
# A listing page: price, status and inspection times move a few times a week.
LISTING_CACHE = timedelta(hours=6)
# The property-address page: sale history and attributes move when a sale
# settles (weeks); the "currently listed" status rides the daily refresh.
PROPERTY_CACHE = timedelta(hours=24)
# Agent / agency directories reorder with each sale; profiles move slowly.
AGENTS_SEARCH_CACHE = timedelta(hours=12)
AGENT_CACHE = timedelta(hours=24)
AGENCY_CACHE = timedelta(hours=24)
# Suburb market profiles are monthly PropTrack series.
SUBURB_CACHE = timedelta(hours=24)
# Auction results are published once a week (the weekend's results on the
# following Wednesday night); a day never serves a stale week.
AUCTIONS_CACHE = timedelta(hours=24)
# Autocomplete and schools: reference data on open hosts (no identity slot);
# cached anyway so a client's keystroke replay costs nothing upstream.
AUTOCOMPLETE_CACHE = timedelta(hours=24)
SCHOOLS_CACHE = timedelta(hours=24)
