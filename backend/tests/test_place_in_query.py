"""A city named in the request is searched instead of the user's own location. Author: Saamarth Attray"""
from app.commander import SwarmCommander
from app.contract import CreateSwarmRequest, LatLng
from app.intent import extract_place


def test_extracts_a_named_city_state_or_zip():
    assert extract_place("Find a CVS in LA that has children's Tylenol") == "Los Angeles, CA"
    assert extract_place("pharmacy in Los Angeles with amoxicillin") == "Los Angeles"
    assert extract_place("Find insulin near Austin, TX right now") == "Austin, TX"
    assert extract_place("pharmacy in 90001 with Tylenol") == "90001"
    assert extract_place("pharmacy with amoxicillin in stock in Blacksburg") == "Blacksburg"


def test_ordinary_phrases_are_not_places():
    assert extract_place("Find a pharmacy that has children's amoxicillin in stock right now") is None
    assert extract_place("a plumber in an hour") is None
    assert extract_place("pharmacy within 5 miles that has Tylenol") is None


async def test_named_place_overrides_the_users_location():
    class Places:
        async def geocode(self, text):
            return LatLng(lat=34.05, lng=-118.24), "Los Angeles, CA, USA"

    cmd = SwarmCommander.__new__(SwarmCommander)
    cmd.places = Places()
    found = await cmd._named_place(CreateSwarmRequest(query="Find CVS pharmacy in LA with Tylenol", lat=37.2, lng=-80.4))
    assert found and found[0].lat == 34.05
    cmd.places = object()   # no geocoder (mock places): the user's own location is used
    assert await cmd._named_place(CreateSwarmRequest(query="Find CVS pharmacy in LA with Tylenol")) is None


def test_trips_and_bare_abbreviations_name_a_place():
    assert extract_place("I'm going to LA next week, find a CVS with amoxicillin") == "Los Angeles, CA"
    assert extract_place("visiting Austin on Friday, find an Indian restaurant with a table for 2") == "Austin"
    assert extract_place("LA CVS pharmacy with amoxicillin") == "Los Angeles, CA"
    assert extract_place("find la pharmacie with aspirin") is None   # lower-case "la" is just a word


async def test_a_named_place_that_cannot_be_found_never_falls_back_to_the_users_city():
    import pytest

    from app.commander import PlaceNotFound

    class Places:
        async def geocode(self, text):
            return None

    cmd = SwarmCommander.__new__(SwarmCommander)
    cmd.places = Places()
    with pytest.raises(PlaceNotFound):
        await cmd._named_place(CreateSwarmRequest(query="Find CVS pharmacy in Atlantis with Tylenol", lat=37.2, lng=-80.4))


async def test_the_model_can_find_a_place_the_rules_missed_but_only_if_it_is_really_in_the_request():
    class Places:
        async def geocode(self, text):
            return LatLng(lat=34.05, lng=-118.24), "Los Angeles, CA, USA"

    class Llm:
        def __init__(self, answer):
            self.answer = answer

        async def complete_json(self, system, user):
            return self.answer

    cmd = SwarmCommander.__new__(SwarmCommander)
    cmd.places = Places()
    cmd.llm = Llm({"mention": "the City of Angels", "place": "Los Angeles, CA"})
    req = CreateSwarmRequest(query="my flight lands in the City of Angels, find a CVS with Tylenol", lat=37.2, lng=-80.4)
    assert (await cmd._named_place(req))[0].lat == 34.05
    cmd.llm = Llm({"mention": "Paris", "place": "Paris, France"})   # invented: not in the request
    assert await cmd._named_place(CreateSwarmRequest(query="find a CVS with Tylenol", lat=37.2, lng=-80.4)) is None


def test_default_number_of_calls_is_ten():
    from app.config import Settings

    assert Settings().max_targets == 10