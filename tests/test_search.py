import numpy as np
import pytest

from backend.app.search import rank_segments


def test_cosine_rank_order():
    assert rank_segments(np.array([1., 0.]), np.array([[0., 1.], [1., 0.], [-1., 0.]]), 3) == [
        (1, 1.), (0, 0.), (2, -1.)]


def test_dimension_mismatch_rejected():
    with pytest.raises(ValueError, match="dimension"):
        rank_segments(np.ones(2), np.ones((3, 4)), 2)


def test_nonfinite_vector_rejected():
    with pytest.raises(ValueError, match="finite"):
        rank_segments(np.array([np.nan, 1.]), np.ones((1, 2)), 1)
