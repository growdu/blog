import pytest

from pyv import easing


@pytest.mark.parametrize("fn", [easing.linear, easing.ease_out_cubic, easing.ease_in_out])
def test_endpoints(fn):
    assert fn(0.0) == pytest.approx(0.0, abs=1e-6)
    assert fn(1.0) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("fn", [easing.linear, easing.ease_out_cubic, easing.ease_in_out])
def test_out_of_range_is_clamped(fn):
    assert fn(-3.0) == pytest.approx(0.0, abs=1e-6)
    assert fn(9.0) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("fn", [easing.linear, easing.ease_out_cubic, easing.ease_in_out])
def test_monotonic_increasing(fn):
    values = [fn(i / 20) for i in range(21)]
    assert all(b >= a - 1e-9 for a, b in zip(values, values[1:]))
