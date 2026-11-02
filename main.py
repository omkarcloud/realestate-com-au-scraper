"""Use the scraper straight from Python — no server needed.

    python main.py

Every function returns the same JSON the API does; results are written to
output/*.json. The first call opens Google Chrome for ~10 seconds to pass
Kasada; the rest run over plain HTTP.
"""
import json
import os

from realestate_com_au import api, refs

os.makedirs("output", exist_ok=True)


def save(name, data):
    path = os.path.join("output", name)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


if __name__ == "__main__":
    # a listing id or any realestate.com.au listing link
    save("listing_152396892.json", api.property_details(listing="152396892"))

    # 25 homes per page; buy, rent or sold, with the site's own filters
    save("search_bondi_beach.json", api.properties_search(
        location=refs.resolve_search_location("Bondi Beach, NSW 2026"), channel="buy", page=1))

    # median prices with 5-year trends, rental yield, supply and demand
    save("suburb_bondi_beach.json", api.suburb_profile(suburb=refs.resolve_suburb("Bondi Beach, NSW 2026")))
