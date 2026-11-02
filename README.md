# 🏡 Realestate Com Au Scraper

Realestate Com Au Scraper is a **free and open-source** scraper that gets you **unlimited** detailed realestate.com.au data for free.

## ✨ What Can I Get?

- 🏡 **Full details on 240K+ homes for sale** — price, photos, floorplans, inspections, auctions & agent mobiles
- 🔍 **Search for sale, for rent & 7.9M+ sold records** — every filter the site has: price, beds, land, keywords
- 📈 **Every suburb's market data** — median prices with 5-year trends, rental yield & auction clearance rates
- 🧑‍💼 **Agents & agencies** — mobiles, every review, sales stats & sold listings

## 🌉 Example: A Full realestate.com.au Listing

```json
{
  "id": "152396892",
  "link": "https://www.realestate.com.au/property-house-nsw-point+piper-152396892",
  "status": "For sale",
  "property_type": "House",
  "title": "Dream Home Opportunity with World-Class Harbour Bridge and Opera House View",
  "address": {
    "full": "96 Wolseley Road, Point Piper, NSW 2027",
    "latitude": -33.86573755,
    "longitude": 151.24933402
  },
  "price": { "display": "Expressions of Interest Buyers guide $50,000,000", "amount": 50000000, "currency": "AUD" },
  "bedrooms": 5,
  "bathrooms": 4,
  "parking_spaces": 2,
  "highlights": [
    { "headline": "Iconic harbour panorama", "detail": "180-degree views of the Harbour Bridge and Opera House" },
    { "headline": "Absolute waterfront estate", "detail": "800sqm parcel with harbourside pool and landscaped gardens" }
  ],
  "agents": [
    { "name": "James Dunn", "phone": "0404387777", "link": "https://www.realestate.com.au/agent/james-dunn-3966632", "rating": 5, "reviews_count": 40 }
  ],
  "agency": { "id": "TCMLHR", "name": "Sydney Sotheby's International Realty - Double Bay", "rating": 5, "reviews_count": 1996 },
  "inspections": [
    { "starts_at": "2026-11-07T11:00:00+11:00", "ends_at": "2026-11-07T11:45:00+11:00", "label": "Saturday 7 November" }
  ],
  "media": {
    "main_image": "https://i2.au.reastatic.net/1144x888/48a85f65e9b96e6d42b6e99f7985d49d9ee03f3076602949fee1d9fa9a106b73/image.jpg",
    "floorplans": ["https://i2.au.reastatic.net/1144x888/9674c59f8c33b2ee2a9e0109c05b9430609bcf7d7241640d779e1b1f3df04501/image.jpg"]
  },
  "nbn": { "connection_type": "HFC", "download": "¹Download: 2000 Mbps" },
  "page_views": { "count": 8388, "as_of": "2026-11-01" }
}
```

*Trimmed for readability.*

## 🚀 Unlimited Free realestate.com.au Data — Get It in 60 Seconds

1️⃣ Clone and install:
```bash
git clone https://github.com/omkarcloud/realestate-com-au-scraper
cd realestate-com-au-scraper
python -m pip install -r requirements.txt
```

2️⃣ Start the API:
```bash
python run.py
```

3️⃣ Get your first data:
```bash
curl "http://localhost:8000/properties/details?listing=152396892"
```

```json
{
  "id": "152396892",
  "link": "https://www.realestate.com.au/property-house-nsw-point+piper-152396892",
  "channel": "buy",
  "status": "For sale",
  "property_type": "House",
  "address": {
    "short": "96 Wolseley Road",
    "full": "96 Wolseley Road, Point Piper, NSW 2027",
    "suburb": "Point Piper",
    "state": "NSW",
    "postcode": "2027"
  },
  "price": { "display": "Expressions of Interest Buyers guide $50,000,000", "amount": 50000000, "currency": "AUD" },
  "bedrooms": 5,
  "bathrooms": 4,
  "parking_spaces": 2,
  "agents": [
    { "id": "4078460", "name": "Michael Dunn", "job_title": "Sales Agent", "phone": "0419888815" }
  ],
  "agency": { "id": "TCMLHR", "name": "Sydney Sotheby's International Realty - Double Bay" }
}
```

All 11 endpoints are now live at `http://localhost:8000`.

realestate.com.au sits behind Kasada, so the first request opens Google Chrome on your machine for ~10 seconds to pass it — have Chrome installed. Every request after that runs over plain HTTP. From a home or office connection you need nothing else. On a cloud server, set `REALESTATE_COM_AU_PROXY` to a residential proxy (`http://user:pass@host:port`) — Australian works best.

## 📚 Endpoints

11 endpoints cover everything you need.

| Endpoint | Path | Returns |
|---|---|---|
| Property Details | `/properties/details` | Everything about one listing in a single call |
| Autocomplete Locations | `/locations/autocomplete` | Suburbs, regions, postcodes, streets and addresses as you type |
| Search Properties | `/properties/search` | Buy, rent or sold homes, 25 per page, every site filter |
| Property History | `/properties/history` | Every past sale, value estimate, land size and council overlays |
| Nearby Schools | `/properties/schools` | Closest primary and secondary schools with distance |
| Suburb Profile | `/suburbs/profile` | Median prices with 5-year trends, rental yield, supply and demand |
| Auction Results | `/auctions/results` | Weekly clearance rate by state, every result by suburb |
| Search Agents | `/agents/search` | Every agent in a suburb with sales stats and reviews |
| Agent Details | `/agents/details` | Mobile, bio, every review, sold and for-sale listings |
| Search Agencies | `/agencies/search` | Every agency in a suburb with offices, stats and ratings |
| Agency Details | `/agencies/details` | Phone, team, 12-month performance, buyer and seller reviews |

## 🔍 Exploring Parameters

The same API is published on RapidAPI, and its playground is the easiest place to try parameters and see raw responses. Once a request looks right, run it locally for **unlimited free** data.

1. [Subscribe to the free plan](https://rapidapi.com/OmkarCloud/api/best-realestate-com-au-scraper-free-1000-calls/pricing) — 1,000 calls/month, no credit card.
2. [Try the endpoints in the playground](https://rapidapi.com/OmkarCloud/api/best-realestate-com-au-scraper-free-1000-calls/playground) — every param is pre-filled, so you see real data in one click.
3. Copy the generated code and replace `https://best-realestate-com-au-scraper-free-1000-calls.p.rapidapi.com` with `http://localhost:8000`. It will now run against your local API.

```python
import requests

# generated by the playground, host swapped for the local API
response = requests.get(
    "http://localhost:8000/properties/search",
    params={"location": "Bondi Beach, NSW 2026", "channel": "sold", "sort": "sold_date"},
)
print(response.json())
```

## 💬 Have Questions? We Have Answers.

You're a developer — we know how hard completing a project can be. So we offer full support: just message us and we'll reply ✅ with a solution within 1 working day.

[![Message Us on WhatsApp about Realestate Com Au Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/whatsapp-us.png)](https://api.whatsapp.com/send?phone=918178804274&text=I%20need%20help%20using%20the%20Realestate%20Com%20Au%20Scraper%20API.)

[![Ask Us by Email about Realestate Com Au Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/ask-on-email.png)](mailto:happy.to.help@omkar.cloud?subject=Help%20with%20Realestate%20Com%20Au%20Scraper%20API&body=I%20need%20help%20using%20the%20Realestate%20Com%20Au%20Scraper%20API.)

## ⚡ Popular Scrapers by Omkar Cloud

- [**Google Maps Scraper (3,100+ GitHub Stars)**](https://github.com/omkarcloud/google-maps-scraper) — type "dentists in New York", get every business as a ready-to-call lead list: phones, emails, websites & reviews. Up to 100K free leads/month.
- [**G2 Scraper**](https://www.omkar.cloud/tools/g2-scraper) — G2 product details, ratings & AI-found contacts
- [**Website Email Contact Scraper**](https://www.omkar.cloud/tools/website-email-contact-scraper) — emails, phones & socials from any website
- [**AliExpress Scraper**](https://www.omkar.cloud/tools/aliexpress-scraper-api) — live product details, SKU variants, stock & shipping
- [**Booking Scraper**](https://www.omkar.cloud/tools/booking-scraper) — Booking.com hotels: prices, ratings, rooms & amenities
- [**Etsy Scraper**](https://www.omkar.cloud/tools/etsy-scraper) — Etsy products: prices, discounts, shops & variations

## ⭐ Love It? [Star It ⭐!](https://github.com/omkarcloud/realestate-com-au-scraper)

Star the repo ⭐ and become my star hero!

It's just 1 click, but it means the world to me.

[![Star us on GitHub](https://raw.githubusercontent.com/omkarcloud/google-maps-scraper/master/screenshots/star-us.png)](https://github.com/omkarcloud/realestate-com-au-scraper)
