"""Unit tests for src/inference.py.

All model artifacts are mocked via conftest.py (session-level patches),
so these tests run without any .pkl or .sav files on disk.
"""

import pytest

import src.inference as inference


class TestGetPredictionInterval:
    def test_symmetric_interval(self):
        est = {"z_score": 1.96, "residual_std": 10.0}
        lower, upper = inference.get_prediction_interval(50.0, est)
        margin = 1.96 * 10.0
        assert lower == pytest.approx(50.0 - margin)
        assert upper == pytest.approx(50.0 + margin)

    def test_zero_std_returns_point_estimate(self):
        est = {"z_score": 1.96, "residual_std": 0.0}
        lower, upper = inference.get_prediction_interval(50.0, est)
        assert lower == pytest.approx(50.0)
        assert upper == pytest.approx(50.0)

    def test_wider_std_widens_interval(self):
        _, upper_narrow = inference.get_prediction_interval(50.0, {"z_score": 1.96, "residual_std": 5.0})
        _, upper_wide   = inference.get_prediction_interval(50.0, {"z_score": 1.96, "residual_std": 20.0})
        assert upper_wide > upper_narrow

    def test_higher_prediction_shifts_interval_up(self):
        est = {"z_score": 1.96, "residual_std": 10.0}
        lower_a, _ = inference.get_prediction_interval(30.0, est)
        lower_b, _ = inference.get_prediction_interval(80.0, est)
        assert lower_b > lower_a


class TestPredictPrice:
    def test_returns_all_expected_keys(self, sample_property):
        result = inference.predict_price(sample_property)
        assert {"predicted_price", "lower_bound", "upper_bound", "features_used"} <= result.keys()

    def test_lower_bound_non_negative(self, sample_property):
        result = inference.predict_price(sample_property)
        assert result["lower_bound"] >= 0

    def test_upper_bound_above_lower_bound(self, sample_property):
        result = inference.predict_price(sample_property)
        assert result["upper_bound"] >= result["lower_bound"]

    def test_features_used_is_positive_integer(self, sample_property):
        result = inference.predict_price(sample_property)
        assert isinstance(result["features_used"], int)
        assert result["features_used"] > 0

    def test_prices_rounded_to_two_decimals(self, sample_property):
        result = inference.predict_price(sample_property)
        for key in ("predicted_price", "lower_bound", "upper_bound"):
            assert round(result[key], 2) == result[key]

    def test_empty_description(self, sample_property):
        sample_property.description = ""
        result = inference.predict_price(sample_property)
        assert result["predicted_price"] is not None

    def test_none_description(self, sample_property):
        sample_property.description = None
        result = inference.predict_price(sample_property)
        assert result["predicted_price"] is not None

    def test_unknown_sub_area_falls_back_to_mean(self, sample_property):
        sample_property.sub_area = "completely_unknown_area_xyz_99"
        result = inference.predict_price(sample_property)
        assert result is not None
        assert result["predicted_price"] is not None

    def test_all_amenities_off(self, sample_property):
        for field in ("clubhouse", "school", "hospital", "mall", "park", "pool", "gym"):
            setattr(sample_property, field, 0)
        result = inference.predict_price(sample_property)
        assert result["predicted_price"] is not None

    def test_all_amenities_on(self, sample_property):
        for field in ("clubhouse", "school", "hospital", "mall", "park", "pool", "gym"):
            setattr(sample_property, field, 1)
        result = inference.predict_price(sample_property)
        assert result["predicted_price"] is not None

    def test_large_area(self, sample_property):
        sample_property.area = 10_000.0
        result = inference.predict_price(sample_property)
        assert result["features_used"] > 0

    def test_description_with_special_chars(self, sample_property):
        sample_property.description = "3BHK; flat! [great view] — near mall/hospital"
        result = inference.predict_price(sample_property)
        assert result["predicted_price"] is not None


class TestGetModelInfo:
    def test_returns_all_required_keys(self):
        info = inference.get_model_info()
        assert "model_type"           in info
        assert "vectorizer_vocab_size" in info
        assert "interval_margin"      in info

    def test_vocab_size_positive_integer(self):
        info = inference.get_model_info()
        assert isinstance(info["vectorizer_vocab_size"], int)
        assert info["vectorizer_vocab_size"] > 0

    def test_interval_margin_is_positive_float(self):
        info = inference.get_model_info()
        assert isinstance(info["interval_margin"], float)
        assert info["interval_margin"] > 0
