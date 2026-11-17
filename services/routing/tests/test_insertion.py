import pytest

from routing.domain.insertion import Insertion, cheapest_insertion

Point = tuple[int, int]


def matrix(start: Point, accepted: list[Point], new: Point, destination: Point) -> list[list[int]]:
    points = [start, *accepted, new, destination]
    return [[abs(a[0] - b[0]) + abs(a[1] - b[1]) for b in points] for a in points]


def test_the_first_rider_goes_first() -> None:
    durations = matrix((0, 0), [], (4, 3), (10, 0))

    assert cheapest_insertion(durations, 0) == Insertion(0, 6)


def test_a_pickup_beside_the_route_fits_between_its_neighbours() -> None:
    durations = matrix((0, 0), [(3, 0), (8, 0)], (6, 1), (10, 0))

    assert cheapest_insertion(durations, 2) == Insertion(1, 2)


def test_a_pickup_near_the_start_goes_before_the_others() -> None:
    durations = matrix((0, 0), [(3, 0), (8, 0)], (1, 1), (10, 0))

    assert cheapest_insertion(durations, 2) == Insertion(0, 2)


def test_a_pickup_near_the_destination_goes_last() -> None:
    durations = matrix((0, 0), [(3, 0), (8, 0)], (9, 1), (10, 0))

    assert cheapest_insertion(durations, 2) == Insertion(2, 2)


def test_a_tie_goes_to_the_earliest_position() -> None:
    durations = matrix((0, 0), [(4, 0)], (4, 2), (8, 0))

    assert cheapest_insertion(durations, 1) == Insertion(0, 4)


def test_a_full_trip_finds_the_place_in_the_middle() -> None:
    accepted = [(x, 0) for x in (2, 4, 6, 8, 10, 12)]
    durations = matrix((0, 0), accepted, (7, 1), (14, 0))

    assert cheapest_insertion(durations, 6) == Insertion(3, 2)


def test_the_added_time_is_never_negative() -> None:
    durations = [[0, 1, 10], [1, 0, 1], [10, 1, 0]]

    assert cheapest_insertion(durations, 0) == Insertion(0, 0)


def test_a_negative_count_is_refused() -> None:
    with pytest.raises(ValueError, match="negative"):
        cheapest_insertion([[0]], -1)


@pytest.mark.parametrize(
    "durations",
    [
        [[0, 1], [1, 0]],
        [[0, 1, 2], [1, 0, 1], [2, 1]],
    ],
)
def test_a_matrix_of_the_wrong_shape_is_refused(durations: list[list[int]]) -> None:
    with pytest.raises(ValueError, match="3x3"):
        cheapest_insertion(durations, 0)
