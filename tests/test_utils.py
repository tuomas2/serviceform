import pytest
from serviceform.serviceform.utils import shuffle_person_data


@pytest.mark.xfail(reason='broken functionality (shall be deprecated or fixed later)')
def test_shuffle(serviceform):
    # just check that this does not crash...
    shuffle_person_data(serviceform)
