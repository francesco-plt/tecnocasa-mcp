import asyncio
import time
import unittest

from tecnocasa_mcp.client import (
    BATCH_SIZE,
    ENRICH_CONCURRENCY,
    MAX_SEARCH_LIMIT,
    SEARCH_SORT_MAP,
    TecnocasaClient,
    build_search_params,
    sort_listings,
)


class SearchParamsTests(unittest.TestCase):
    def test_server_side_filters_and_sort(self):
        params = build_search_params(
            city_id=13800324507779,
            province="MI",
            contract="sale",
            sector="residential",
            district_ids=[10060, 10061],
            min_price=300000,
            max_price=600000,
            min_sqm=45,
            max_sqm=120,
            min_rooms=2,
            max_rooms=3,
            agency_id="micc4",
            sort="price_asc",
            limit=40,
        )
        values = dict(params)
        self.assertEqual(values["contract"], "acquis")
        self.assertEqual(values["sector"], "res")
        self.assertEqual(values["city"], 13800324507779)
        self.assertEqual(values["districts"], "10060|10061")
        self.assertEqual(values["min_price"], 300000)
        self.assertEqual(values["max_price"], 600000)
        self.assertEqual(values["min_surface"], 45)
        self.assertEqual(values["max_surface"], 120)
        self.assertEqual(values["min_rooms"], 2)
        self.assertEqual(values["max_rooms"], 3)
        self.assertEqual(values["agency"], "micc4")
        self.assertEqual(values["sort"], "Prezzo|ASC")
        self.assertEqual(values["limit"], 40)
        # Bathrooms are not supported by /api/estates/search.
        self.assertNotIn("min_bathrooms", values)

    def test_optional_params_are_omitted(self):
        values = dict(build_search_params(city_id=1, sort="relevance", limit=20))
        self.assertNotIn("province", values)
        self.assertNotIn("districts", values)
        self.assertNotIn("sort", values)
        self.assertNotIn("agency", values)
        self.assertEqual(values["limit"], 20)

    def test_limit_is_capped(self):
        values = dict(build_search_params(city_id=1, limit=MAX_SEARCH_LIMIT + 500))
        self.assertEqual(values["limit"], MAX_SEARCH_LIMIT)

    def test_sort_map_covers_all_mappers(self):
        self.assertEqual(SEARCH_SORT_MAP["price_desc"], "Prezzo|DESC")
        self.assertEqual(SEARCH_SORT_MAP["sqm_asc"], "MQ|ASC")
        self.assertEqual(SEARCH_SORT_MAP["rooms_asc"], "Camere|ASC")
        self.assertNotIn("relevance", SEARCH_SORT_MAP)

    def test_sort_listings_rooms_asc(self):
        listings = [
            {"id": 1, "rooms_value": 3},
            {"id": 2, "rooms_value": None},
            {"id": 3, "rooms_value": 1},
        ]
        self.assertEqual(
            [item["id"] for item in sort_listings(listings, "rooms_asc")], [3, 1, 2]
        )


class CacheTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = TecnocasaClient()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_concurrent_calls_share_one_fetch(self):
        calls = 0

        async def factory():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.05)
            return "value"

        results = await asyncio.gather(
            *(self.client._cached("same-key", 60, factory) for _ in range(6))
        )
        self.assertEqual(results, ["value"] * 6)
        self.assertEqual(calls, 1)

    async def test_cached_value_is_reused(self):
        calls = 0

        async def factory():
            nonlocal calls
            calls += 1
            return calls

        self.assertEqual(await self.client._cached("k", 60, factory), 1)
        self.assertEqual(await self.client._cached("k", 60, factory), 1)
        self.assertEqual(calls, 1)

    async def test_expired_value_is_served_while_refreshing(self):
        calls = 0

        async def factory():
            nonlocal calls
            calls += 1
            if calls == 1:
                return "fresh"
            await asyncio.sleep(10)
            return "refreshed"

        self.assertEqual(await self.client._cached("stale", 0, factory), "fresh")
        started = time.monotonic()
        value = await self.client._cached("stale", 0, factory)
        elapsed = time.monotonic() - started
        # The refresh is scheduled in the background; give it a turn.
        await asyncio.sleep(0)
        self.assertEqual(value, "fresh")
        self.assertLess(elapsed, 0.5)
        self.assertEqual(calls, 2)


class SummaryCacheTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = TecnocasaClient()
        self.calls: list[list[int]] = []

    async def asyncTearDown(self):
        await self.client.close()

    async def test_summaries_fetch_only_missing_ids(self):
        async def fake_details(ids, section="estate"):
            ids = list(ids)
            self.calls.append(ids)
            return [{"id": value, "title": f"listing {value}"} for value in ids]

        self.client.details = fake_details  # type: ignore[method-assign]

        first = await self.client.summaries([1, 2, 1])
        second = await self.client.summaries([2, 3])

        self.assertEqual([item["id"] for item in first], [1, 2])
        self.assertEqual([item["id"] for item in second], [2, 3])
        self.assertEqual(self.calls, [[1, 2], [3]])

    async def test_large_id_list_is_batched(self):
        async def fake_details(ids, section="estate"):
            ids = list(ids)
            self.calls.append(ids)
            return [{"id": value} for value in ids]

        self.client.details = fake_details  # type: ignore[method-assign]
        ids = list(range(1, BATCH_SIZE * 2 + 1))

        result = await self.client.summaries(ids)

        self.assertEqual([item["id"] for item in result], ids)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(self.calls[0]), BATCH_SIZE)


class EnrichPageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = TecnocasaClient()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_enrich_preserves_order(self):
        async def fake_get_listing(property_id, summary=None):
            await asyncio.sleep(0.01)
            return {**summary, "enriched": True}

        self.client.get_listing = fake_get_listing  # type: ignore[method-assign]
        items = [{"id": value} for value in range(1, 9)]

        result = await self.client._enrich_page(items, budget=2.0)

        self.assertEqual([item["id"] for item in result], [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertTrue(all(item["enriched"] for item in result))

    async def test_enrich_respects_time_budget(self):
        async def slow_get_listing(property_id, summary=None):
            await asyncio.sleep(5)
            return {**summary, "enriched": True}

        self.client.get_listing = slow_get_listing  # type: ignore[method-assign]
        items = [{"id": value} for value in range(1, 4)]

        started = time.monotonic()
        result = await self.client._enrich_page(items, budget=0.05)
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 1.0)
        self.assertEqual([item["id"] for item in result], [1, 2, 3])
        self.assertTrue(all("detail_error" in item for item in result))

    async def test_enrich_bounds_concurrency(self):
        active = 0
        peak = 0

        async def fake_get_listing(property_id, summary=None):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0.02)
                return {**summary, "enriched": True}
            finally:
                active -= 1

        self.client.get_listing = fake_get_listing  # type: ignore[method-assign]
        items = [{"id": value} for value in range(1, 21)]

        await self.client._enrich_page(items, budget=2.0)

        self.assertLessEqual(peak, ENRICH_CONCURRENCY)
        self.assertGreater(peak, 1)


if __name__ == "__main__":
    unittest.main()
