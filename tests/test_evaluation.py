from data_analyst.evaluation import equivalent_rows, percentile


def test_result_equivalence_tolerates_small_float_difference():
    assert equivalent_rows([{"value": 1.0000001}], [{"value": 1.0}])


def test_result_equivalence_detects_mismatch():
    assert not equivalent_rows([{"value": 2}], [{"value": 1}])


def test_percentile():
    assert percentile([1, 2, 3, 4], 0.95) == 4
