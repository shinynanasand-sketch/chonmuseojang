from services.auth import assert_operator_owns_village, scoped_village_id


def test_scoped_village_id_returns_operator_village(sample_operator_a):
    assert scoped_village_id(sample_operator_a) == "V001"


def test_assert_operator_owns_village_allows_own_village(sample_operator_a):
    assert assert_operator_owns_village(sample_operator_a, "V001") is True


def test_assert_operator_owns_village_denies_other_village(sample_operator_a):
    assert assert_operator_owns_village(sample_operator_a, "V002") is False


def test_operator_api_requires_authentication(test_client):
    response = test_client.get("/api/operator/dashboard")
    assert response.status_code in (401, 403)
