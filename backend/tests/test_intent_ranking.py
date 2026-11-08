"""Intent parsing, mock directory, and ranking. Author: Saamarth Attray"""
import pytest

from app.contract import ExtractedResult, LatLng, Target
from app.intent import heuristic_intent
from app.places import MockPlaces, brand_key, haversine_miles
from app.ranking import Candidate, rank


@pytest.mark.parametrize(
    "query,category,kind,item",
    [
        ("Find a pharmacy within 5 miles that has children's amoxicillin in stock right now", "pharmacy", "product", "children's amoxicillin"),
        ("I need children's amoxicillin tonight, find a pharmacy that has it in stock", "pharmacy", "product", "children's amoxicillin"),
        ("Who has a PS5 in stock near me, cheapest wins", "electronics", "product", "PS5"),
        ("My water heater burst, find a plumber who can come tonight", "plumber", "service", "an urgent plumber visit"),
        ("Earliest DMV appointment for REAL ID", "dmv", "appointment", "a same-day appointment"),
    ],
)
def test_heuristic_intent(query, category, kind, item):
    intent = heuristic_intent(query, 10, None)
    assert (intent.category, intent.kind, intent.item) == (category, kind, item)


def test_radius_and_priority_extraction():
    assert heuristic_intent("pharmacy within 3 miles with ibuprofen", 10, None).radius_miles == 3
    assert heuristic_intent("cheapest ps5 around", 10, None).priority == "price"
    assert heuristic_intent("closest pharmacy with insulin", 10, None).priority == "distance"
    assert heuristic_intent("cheapest ps5 around", 10, "speed").priority == "speed"


async def test_mock_places_is_deterministic_sorted_and_within_radius():
    intent = heuristic_intent("pharmacy with ibuprofen", 8, None)
    origin = LatLng(lat=38.9, lng=-77.0)
    a = await MockPlaces().search(intent, origin, 8, 18)
    b = await MockPlaces().search(intent, origin, 8, 18)
    assert [t.model_dump() for t in a] == [t.model_dump() for t in b]
    assert [t.distance_miles for t in a] == sorted(t.distance_miles for t in a)
    assert all(t.distance_miles <= 8 for t in a)
    assert all(t.phone.startswith("+1202555") for t in a)  # fictional 555 numbers only
    assert any(t.open_now is False for t in a)
    for t in a:
        assert abs(haversine_miles(origin.lat, origin.lng, t.lat, t.lng) - t.distance_miles) < 0.25


def test_brand_key():
    assert brand_key("CVS Pharmacy #123") == "cvs"
    assert brand_key("Walgreens") == "walgreens"
    assert brand_key("Main Street Drugs") == "main street"


def _cand(cid, price, dist, hold=True, avail="yes", wait=None):
    return Candidate(cid, Target(id=cid, name=cid, lat=0, lng=0, distance_miles=dist),
                     ExtractedResult(available=avail, price=price, can_hold=hold, wait_minutes=wait))


def test_ranking_balances_and_excludes_negatives():
    intent = heuristic_intent("pharmacy with ibuprofen", 10, None)
    cands = [_cand("far_cheap", 5, 9), _cand("near_pricey", 20, 1), _cand("no", None, 1, avail="no")]
    ranked, best, criteria = rank(cands, intent)
    assert {r.call_id for r in ranked} == {"far_cheap", "near_pricey"}
    assert best == ranked[0].call_id and [r.rank for r in ranked] == [1, 2]
    assert criteria


def test_priority_changes_the_winner():
    cands = [_cand("far_cheap", 5, 9), _cand("near_pricey", 20, 1)]
    price_intent = heuristic_intent("cheapest ibuprofen pharmacy", 10, None)
    dist_intent = heuristic_intent("closest ibuprofen pharmacy", 10, None)
    assert rank(cands, price_intent)[1] == "far_cheap"
    assert rank(cands, dist_intent)[1] == "near_pricey"


def test_ranking_empty_when_no_matches():
    intent = heuristic_intent("pharmacy with ibuprofen", 10, None)
    assert rank([_cand("x", None, 1, avail="no")], intent)[1] is None
