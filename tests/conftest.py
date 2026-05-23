"""
Session-level test configuration.

inference.py loads six model artifacts at import time via joblib.load and
pickle.load.  If the files are absent (CI, fresh clone without dvc pull)
the import raises FileNotFoundError and the entire test suite fails.

Strategy:
  1. Download NLTK corpora first (idempotent, cached after first run).
  2. Patch builtins.open, joblib.load, pickle.load, and nltk.download at
     module level so the patches are active *before* any test module is
     collected — which is when Python first imports src.inference.
  3. Import src.inference while the patches are live.
  4. Patch word_tokenize and pos_tag inside the already-imported module so
     predict_price() never makes NLTK corpus calls during tests.
"""

import builtins
from unittest.mock import MagicMock, patch

import nltk
import numpy as np
import pytest

# ── Step 1: ensure NLTK data is present (no-op when already cached) ──────────
for _pkg in ("punkt", "punkt_tab", "averaged_perceptron_tagger",
             "averaged_perceptron_tagger_eng", "stopwords"):
    nltk.download(_pkg, quiet=True)

# ── Step 2: build mock artifacts ─────────────────────────────────────────────

_REAL_OPEN = builtins.open

_MOCK_MODEL = MagicMock(name="voting_regressor")
_MOCK_MODEL.predict.return_value = np.array([50.0])
_MOCK_MODEL.__class__.__name__ = "VotingRegressor"

_MOCK_VEC = MagicMock(name="count_vectorizer")
_MOCK_VEC.transform.return_value.toarray.return_value = np.zeros((1, 100))
_MOCK_VEC.vocabulary_ = {f"w{i}": i for i in range(100)}

_FEATURE_NAMES = [f"s{i}" for i in range(15)] + [f"t{i}" for i in range(100)]
_INTERVAL_EST  = {"z_score": 1.96, "residual_std": 16.0}
_SUB_AREA_MAP  = {"kothrud": 65.0, "baner": 72.0, "wakad": 68.0, "hadapsar": 58.0}
_AMENITIES_MAP = {i: float(45 + i * 6) for i in range(8)}


def _model_open(path, *args, **kwargs):
    """Intercept open() for model/ paths; pass everything else through."""
    if isinstance(path, str) and path.startswith("model/"):
        m = MagicMock()
        m.name = path
        m.__enter__ = lambda s: m
        m.__exit__ = MagicMock(return_value=False)
        return m
    return _REAL_OPEN(path, *args, **kwargs)


def _pickle_side_effect(file_obj):
    """Return the right mock artifact based on the file path stored in .name."""
    name = getattr(file_obj, "name", "")
    if "count_vectorizer"          in name: return _MOCK_VEC
    if "sub_area_price_map"        in name: return _SUB_AREA_MAP
    if "amenities_score_price_map" in name: return _AMENITIES_MAP
    if "interval_est"              in name: return _INTERVAL_EST
    if "all_feature_names"         in name: return _FEATURE_NAMES
    return {}


# ── Step 3: activate patches before any test module is imported ───────────────
patch("builtins.open", side_effect=_model_open).start()
patch("joblib.load",   return_value=_MOCK_MODEL).start()
patch("pickle.load",   side_effect=_pickle_side_effect).start()
patch("nltk.download", return_value=True).start()

# ── Step 4: import inference while patches are live ───────────────────────────
import src.inference as _inference  # noqa: E402

# ── Step 5: patch NLTK functions in the already-imported module ───────────────
patch.object(_inference, "word_tokenize",
             return_value=["spacious", "2bhk", "apartment"]).start()
patch.object(_inference, "pos_tag",
             return_value=[("spacious", "JJ"), ("2bhk", "NN"),
                           ("apartment", "NN")]).start()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_property():
    """A valid PropertyInput ready to pass into predict_price()."""
    from src.schemas import PropertyInput
    return PropertyInput(
        property_type=2,
        area=1000.0,
        sub_area="kothrud",
        description="spacious 2bhk apartment with great view near park",
        clubhouse=1, school=1, hospital=0, mall=1, park=1, pool=0, gym=1,
    )


@pytest.fixture
def mock_artifacts():
    """Expose the shared mock objects for direct assertions."""
    return {
        "model":         _MOCK_MODEL,
        "vectorizer":    _MOCK_VEC,
        "feature_names": _FEATURE_NAMES,
        "interval_est":  _INTERVAL_EST,
        "sub_area_map":  _SUB_AREA_MAP,
        "amenities_map": _AMENITIES_MAP,
    }
