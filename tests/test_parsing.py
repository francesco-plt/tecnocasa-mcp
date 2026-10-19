import json
import unittest

from tecnocasa_mcp.client import (
    card_to_listing,
    dedupe_listings,
    filter_listings,
    normalize_autocomplete,
    normalize_summary,
    parse_bathrooms,
    parse_estate_html,
    parse_microsite_agency,
    parse_microsite_cards,
    parse_number,
    parse_rooms,
    parse_surface,
    sort_listings,
    split_subtitle,
)


class ParsingTests(unittest.TestCase):
    def test_parse_number_italian_formats(self):
        self.assertEqual(parse_number("€ 395.000"), 395000)
        self.assertEqual(parse_number("€ 1.200,50"), 1200.5)
        self.assertEqual(parse_number("50.00"), 50.0)
        self.assertEqual(parse_number("12.345"), 12345)
        self.assertIsNone(parse_number("n/a"))

    def test_parse_property_fields(self):
        self.assertEqual(parse_surface("50 Mq"), 50)
        self.assertEqual(parse_surface("mq 120 ca."), 120)
        self.assertEqual(parse_surface("mq 50 ca."), 50)
        self.assertEqual(parse_rooms("2 locali"), 2)
        self.assertEqual(parse_rooms("1 locale"), 1)
        self.assertEqual(parse_bathrooms("1 bagno"), 1)
        self.assertEqual(parse_bathrooms("2 bagni"), 2)

    def test_normalize_autocomplete(self):
        data = {
            "districts": [
                {
                    "type": "districts",
                    "id": 10060,
                    "city_id": 13800324507779,
                    "province_id": "MI",
                    "name": "porta venezia, indipendenza",
                    "placeholder": "Milano - <strong>Porta Venezia</strong>, Indipendenza",
                }
            ]
        }
        candidates = normalize_autocomplete(data)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["type"], "district")
        self.assertEqual(candidates[0]["id"], 10060)
        self.assertIn("Porta Venezia", candidates[0]["label"])

    def test_normalize_summary(self):
        item = {
            "id": 1,
            "title": "Bilocale in vendita",
            "subtitle": "Milano, Via Frisi",
            "price": "€ 395.000",
            "surface": "50 Mq",
            "rooms": "2 locali",
            "bathrooms": "1 bagno",
            "agency": {"id": "micc4"},
            "images": [{"url": {"card": "https://example.com/card.jpg"}}],
        }
        result = normalize_summary(item)
        self.assertEqual(result["price_value"], 395000)
        self.assertEqual(result["surface_value"], 50)
        self.assertEqual(result["rooms_value"], 2)
        self.assertEqual(result["bathrooms_value"], 1)
        self.assertEqual(result["agency_id"], "micc4")
        self.assertEqual(result["image"], "https://example.com/card.jpg")

    def test_filters_and_sort(self):
        listings = [
            {
                "id": 1,
                "title": "Bilocale",
                "price_value": 300000,
                "surface_value": 50,
                "rooms_value": 2,
                "agency_id": "a",
            },
            {
                "id": 2,
                "title": "Box",
                "price_value": 50000,
                "surface_value": 15,
                "rooms_value": None,
                "agency_id": "b",
            },
            {
                "id": 3,
                "title": "Trilocale",
                "price_value": 450000,
                "surface_value": 80,
                "rooms_value": 3,
                "agency_id": "a",
            },
        ]
        filtered = filter_listings(
            listings, min_price=100000, max_price=500000, min_rooms=2
        )
        self.assertEqual([x["id"] for x in filtered], [1, 3])
        self.assertEqual(
            [x["id"] for x in sort_listings(filtered, "price_desc")], [3, 1]
        )

    def test_parse_estate_html(self):
        payload = {
            "id": 61279557,
            "price": "€ 395.000",
            "surface": "50 Mq",
            "rooms": "2 locali",
            "agency": {"id": "micc4", "name": "Studio Piave Srl"},
            "features": {"elevator_immo": "Sì", "bedrooms": 1},
            "data": [{"label": "Indirizzo", "valore": "Via Frisi, 3"}],
        }
        escaped = json.dumps(payload, ensure_ascii=False).replace('"', "&quot;")
        page = f'<estate-show-v1 :estate="{escaped}"></estate-show-v1>'
        result = parse_estate_html(page)
        self.assertEqual(result["id"], 61279557)
        self.assertEqual(result["agency"]["name"], "Studio Piave Srl")

    def test_parse_microsite_cards(self):
        page = """
        <html><head><title>Studio Piave Srl - Milano | Agenzia Tecnocasa</title>
        <link rel="canonical" href="https://milano34.tecnocasa.it/milano/porta-venezia-quadrilatero/">
        </head><body>
        <div class="estate-card" immobileId="61279557" agenziaId="micc4">
          <a href="/milano/appartamenti-in-vendita-61279557" class="hover-link"></a>
          <div class="estate-card-current-price">€ 395.000</div>
          <h3 class="estate-card-title">Bilocale in vendita</h3>
          <h4 class="estate-card-subtitle">Milano, Via Frisi - Porta Venezia</h4>
          <div class="estate-card-data">50 mq 2 locali</div>
        </div>
        </body></html>
        """
        cards, meta = parse_microsite_cards(
            page, "https://milano34.tecnocasa.it/milano/porta-venezia-quadrilatero/"
        )
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["id"], 61279557)
        self.assertEqual(cards[0]["agency_id"], "micc4")
        self.assertEqual(cards[0]["price_value"], 395000)
        self.assertEqual(meta["agency_name"], "Studio Piave Srl")

    def test_split_subtitle(self):
        self.assertEqual(
            split_subtitle("Milano, Via Kramer 31 - Porta Venezia"),
            ("Milano, Via Kramer 31", "Porta Venezia"),
        )
        self.assertEqual(
            split_subtitle("Milano, Via Kramer"), ("Milano, Via Kramer", None)
        )
        self.assertEqual(split_subtitle(None), ("", None))

    def test_card_to_listing(self):
        card = {
            "id": 61285237,
            "title": "Bilocale in affitto",
            "subtitle": "Milano, Via Rosolino Pilo - Porta Venezia",
            "price": "€ 1.100 / mese",
            "price_value": 1100,
            "surface_value": 45,
            "rooms_value": 2,
            "agency_id": "micc9",
            "detail_url": "https://milano59.tecnocasa.it/milano/appartamenti-in-affitto-61285237",
            "card_text": "2 locali 45 Mq 1 bagno",
        }
        listing = card_to_listing(card, "milano59.tecnocasa.it")
        self.assertEqual(listing["area"], "Porta Venezia")
        self.assertEqual(listing["address"], "Milano, Via Rosolino Pilo")
        self.assertEqual(listing["bathrooms_value"], 1)
        self.assertEqual(listing["microsite_url"], "https://milano59.tecnocasa.it")

    def test_dedupe_listings(self):
        listings = [
            {"id": 1, "price_value": 100},
            {"id": 2, "price_value": 200},
            {"id": 1, "price_value": 100},
            {"id": None, "detail_url": "https://x/1"},
            {"id": None, "detail_url": "https://x/1"},
        ]
        result = dedupe_listings(listings)
        self.assertEqual([item["id"] for item in result], [1, 2, None])

    def test_filter_listings_by_area(self):
        listings = [
            {
                "id": 1,
                "subtitle": "Milano, Via Rosolino Pilo - Porta Venezia",
                "area": "Porta Venezia",
            },
            {"id": 2, "subtitle": "Milano, Via Kramer", "area": None},
            {
                "id": 3,
                "subtitle": "Milano, Via Vitruvio - Buenos Aires",
                "area": "Buenos Aires",
            },
        ]
        filtered = filter_listings(listings, areas=["porta venezia", "Indipendenza"])
        self.assertEqual([item["id"] for item in filtered], [1])
        self.assertEqual(len(filter_listings(listings, areas=["milano"])), 3)
        self.assertEqual(len(filter_listings(listings)), 3)

    def test_parse_microsite_agency(self):
        page = """
        <html><body>
          <h2>Studio Zurigo  Snc</h2>
          <a href="tel:0287383685">tel</a>
          <a href="mailto:micq4@tecnocasa.it">mail</a>
          <a href="mailto:tecnocasa@tecnocasa.com">other</a>
        </body></html>
        """
        agency = parse_microsite_agency(page)
        self.assertEqual(agency["name"], "Studio Zurigo Snc")
        self.assertEqual(agency["phone"], "0287383685")
        self.assertEqual(agency["email"], "micq4@tecnocasa.it")


if __name__ == "__main__":
    unittest.main()
