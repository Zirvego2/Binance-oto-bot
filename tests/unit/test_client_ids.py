from shared.client_ids import generate_client_algo_id, generate_client_order_id, generate_signal_id


def test_client_order_id_unique_and_within_length_limit():
    ids = {generate_client_order_id() for _ in range(200)}
    assert len(ids) == 200
    assert all(len(i) <= 36 for i in ids)


def test_client_algo_id_unique_and_within_length_limit():
    ids = {generate_client_algo_id("sl") for _ in range(200)}
    assert len(ids) == 200
    assert all(len(i) <= 36 for i in ids)
    assert all(i.startswith("algo_sl_") for i in ids)


def test_signal_id_unique():
    ids = {generate_signal_id() for _ in range(200)}
    assert len(ids) == 200
