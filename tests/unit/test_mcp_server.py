import json
import os

import pytest

from app.mcp_server import (
    calculate_fees,
    estimate_price_by_category,
    fetch_vinted_listings,
    fetch_wallapop_listings,
    fuzzy_cache_lookup,
    get_ebay_oauth_token,
    scrape_single_link_price,
    search_ebay_api,
    search_market_prices,
)


def test_calculate_fees():
    # eBay fees should be ~11.5% + 0.35€
    ebay_fee = calculate_fees("ebay", 100.0, 0.0)
    assert ebay_fee == 11.85  # 11.50 + 0.35

    # Vinted fee should be 0 for sellers
    vinted_fee = calculate_fees("vinted", 50.0, 5.0)
    assert vinted_fee == 0.0

    # Subito fee should be 0.0 for sellers
    subito_fee = calculate_fees("subito", 200.0, 0.0)
    assert subito_fee == 0.0

    # Facebook Marketplace fee should be 0.0 with 0.0 shipping
    fb_fee_local = calculate_fees("facebook", 100.0, 0.0)
    assert fb_fee_local == 0.0

    # Facebook Marketplace fee should be 5% (min 0.40) with shipping > 0
    fb_fee_shipped = calculate_fees("facebook", 100.0, 5.0)
    assert fb_fee_shipped == 5.25  # 5% of 105.0 = 5.25

    # TikTok Shop fee should be 5% + 0.30
    tiktok_fee = calculate_fees("tiktok", 100.0, 0.0)
    assert tiktok_fee == 5.30  # 5% of 100.0 = 5.00 + 0.30 = 5.30


@pytest.mark.asyncio
async def test_search_market_prices_cached():
    # Test fallback to cache for PS5
    res_str = await search_market_prices("playstation 5", "IT")
    res = json.loads(res_str)

    assert res["product_query"] == "playstation 5"
    assert res["country"] == "IT"
    assert res["currency"] == "EUR"
    assert "statistics" in res
    assert res["statistics"]["total_listings_analyzed"] > 0
    assert res["scam_risk"] == "low"


@pytest.mark.asyncio
async def test_search_market_prices_scam_risk():
    # Test Rolex high scam risk detection
    res_str = await search_market_prices("rolex datejust luxury watch", "IT")
    res = json.loads(res_str)

    assert res["scam_risk"] == "high"
    assert res["trust_score"] < 70


def test_fuzzy_cache_lookup():
    # Matching exact
    data = fuzzy_cache_lookup("playstation 5")
    assert data is not None
    assert data["brand"] == "Sony"

    # Matching partiel avec variante (ps5 => playstation 5)
    data2 = fuzzy_cache_lookup("iPhone 15 pro max 256GB")
    assert data2 is not None
    assert data2["brand"] == "Apple"

    # Aucun match pour un produit totalement inconnu
    data3 = fuzzy_cache_lookup("chaise de bureau ergonomique")
    assert data3 is None


def test_estimate_price_by_category():
    # Sans price hint, doit retourner la moyenne catégorielle
    price_iphone = estimate_price_by_category("iphone 15 pro")
    assert 200 <= price_iphone <= 1400

    # Avec price hint, le résultat doit être ancré autour du prix d'achat
    price_with_hint = estimate_price_by_category("iphone 15", purchase_price_hint=900.0)
    assert 600 <= price_with_hint <= 900  # 75-95% de 900

    # Produit inconnu doit utiliser la fourchette default
    price_unknown = estimate_price_by_category("truc random", purchase_price_hint=0.0)
    assert 50 <= price_unknown <= 500


@pytest.mark.asyncio
async def test_search_market_prices_with_hint():
    # Un produit inconnu avec un hint de prix doit retourner un prix proche du hint
    res_str = await search_market_prices(
        "Sony WH-1000XM5 headphones", "FR", purchase_price_hint=300.0
    )
    res = json.loads(res_str)
    assert "statistics" in res
    avg = res["statistics"]["average_price"]
    # Le prix moyen doit être dans une fourchette réaliste (pas 150€ fixe)
    assert avg > 100.0  # Pas la valeur arbitraire de 150€ pour un casque haut de gamme


@pytest.mark.asyncio
async def test_scrape_single_link_price():
    # Test resolving details from an eBay URL
    res_str = await scrape_single_link_price(
        "https://www.ebay.it/itm/Sony-PlayStation-5-Slim-1TB-/1234567890"
    )
    res = json.loads(res_str)

    assert "PlayStation" in res["title"] or "playstation" in res["title"].lower()
    assert res["price"] > 0.0
    assert res["currency"] == "EUR"
    assert res["brand"] == "Sony"
    assert res["condition"] == "Excellent"
    assert "PlayStation" in res["description"]
    assert res["target_country"] == "IT"
    assert res["resell_platform"] == "ebay"


@pytest.mark.asyncio
async def test_fetch_vinted_listings():
    # On teste avec un produit connu (PlayStation 5)
    results = await fetch_vinted_listings("PlayStation 5", "FR")
    # En environnement de test ou si bloqué par Vinted, Vinted peut renvoyer une liste vide,
    # on s'assure juste que l'appel ne plante pas et que le type retourné est bien une liste
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_fetch_wallapop_listings():
    # Wallapop est généralement plus permissif
    results = await fetch_wallapop_listings("iphone", "ES")
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_search_ebay_api_credentials():
    client_id = os.environ.get("EBAY_CLIENT_ID")
    client_secret = os.environ.get("EBAY_CLIENT_SECRET")

    if not client_id or not client_secret:
        pytest.skip(
            "eBay API credentials not found in environment, skipping live test."
        )

    token = await get_ebay_oauth_token()
    assert token is not None, "Failed to retrieve eBay OAuth token"

    results = await search_ebay_api("Guess Watch", "IT", token)
    assert isinstance(results, list), "eBay API should return a list"
    assert len(results) > 0, "eBay API should return listings for 'Guess Watch'"
    assert "price" in results[0], "Listings should contain a price"
