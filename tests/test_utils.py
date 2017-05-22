from serviceform.serviceform.utils import shuffle_person_data


def test_shuffle(serviceform):
    # just check that this does not crash...
    shuffle_person_data(serviceform)
