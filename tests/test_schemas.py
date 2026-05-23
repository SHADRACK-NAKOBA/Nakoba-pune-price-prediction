"""Unit tests for src/schemas.py — pure Pydantic validation, no model I/O."""

import pytest
from pydantic import ValidationError

from src.schemas import HealthResponse, ModelInfoResponse, PriceResponse, PropertyInput


class TestPropertyInput:
    def test_valid_full_input(self):
        prop = PropertyInput(
            property_type=2, area=1200.0, sub_area="kothrud",
            description="nice flat near park",
            clubhouse=1, school=1, hospital=0, mall=0, park=1, pool=0, gym=1,
        )
        assert prop.property_type == 2
        assert prop.area == 1200.0
        assert prop.sub_area == "kothrud"

    def test_optional_description_defaults_to_empty_string(self):
        prop = PropertyInput(
            property_type=3, area=800.0, sub_area="baner",
            clubhouse=0, school=0, hospital=0, mall=0, park=0, pool=0, gym=0,
        )
        assert prop.description == ""

    def test_missing_property_type_raises(self):
        with pytest.raises(ValidationError):
            PropertyInput(
                area=900.0, sub_area="wakad",
                clubhouse=0, school=0, hospital=0, mall=0, park=0, pool=0, gym=0,
            )

    def test_missing_area_raises(self):
        with pytest.raises(ValidationError):
            PropertyInput(
                property_type=2, sub_area="wakad",
                clubhouse=0, school=0, hospital=0, mall=0, park=0, pool=0, gym=0,
            )

    def test_invalid_area_type_raises(self):
        with pytest.raises(ValidationError):
            PropertyInput(
                property_type=2, area="not-a-number", sub_area="baner",
                clubhouse=0, school=0, hospital=0, mall=0, park=0, pool=0, gym=0,
            )

    def test_all_amenity_flags_present(self):
        prop = PropertyInput(
            property_type=2, area=1000.0, sub_area="kothrud",
            clubhouse=1, school=1, hospital=1, mall=1, park=1, pool=1, gym=1,
        )
        flags = [prop.clubhouse, prop.school, prop.hospital, prop.mall,
                 prop.park, prop.pool, prop.gym]
        assert all(f == 1 for f in flags)

    def test_amenity_flags_are_integers(self):
        prop = PropertyInput(
            property_type=1, area=600.0, sub_area="hadapsar",
            clubhouse=1, school=0, hospital=1, mall=0, park=1, pool=0, gym=0,
        )
        assert isinstance(prop.clubhouse, int)
        assert isinstance(prop.gym, int)

    def test_zero_amenities(self):
        prop = PropertyInput(
            property_type=1, area=500.0, sub_area="kothrud",
            clubhouse=0, school=0, hospital=0, mall=0, park=0, pool=0, gym=0,
        )
        total = sum([prop.clubhouse, prop.school, prop.hospital,
                     prop.mall, prop.park, prop.pool, prop.gym])
        assert total == 0


class TestPriceResponse:
    def test_valid_response(self):
        r = PriceResponse(
            predicted_price=75.5, lower_bound=44.2,
            upper_bound=106.8, features_used=115,
        )
        assert r.predicted_price == 75.5
        assert r.features_used == 115

    def test_missing_features_used_raises(self):
        with pytest.raises(ValidationError):
            PriceResponse(predicted_price=75.5, lower_bound=44.2, upper_bound=106.8)

    def test_float_values_accepted(self):
        r = PriceResponse(
            predicted_price=50.123456, lower_bound=18.64,
            upper_bound=81.36, features_used=115,
        )
        assert isinstance(r.predicted_price, float)


class TestHealthResponse:
    def test_valid_health_response(self):
        h = HealthResponse(status="API is healthy and running.")
        assert "healthy" in h.status

    def test_missing_status_raises(self):
        with pytest.raises(ValidationError):
            HealthResponse()

    def test_custom_status_message(self):
        h = HealthResponse(status="OK")
        assert h.status == "OK"


class TestModelInfoResponse:
    def test_valid_model_info(self):
        info = ModelInfoResponse(
            model_type="VotingRegressor",
            vectorizer_vocab_size=500,
            interval_margin=31.35,
        )
        assert info.model_type == "VotingRegressor"
        assert info.vectorizer_vocab_size == 500
        assert info.interval_margin == pytest.approx(31.35)

    def test_missing_vocab_size_raises(self):
        with pytest.raises(ValidationError):
            ModelInfoResponse(model_type="VotingRegressor", interval_margin=31.35)

    def test_integer_vocab_size(self):
        info = ModelInfoResponse(
            model_type="VotingRegressor",
            vectorizer_vocab_size=1024,
            interval_margin=15.0,
        )
        assert isinstance(info.vectorizer_vocab_size, int)
