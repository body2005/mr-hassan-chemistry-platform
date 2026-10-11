from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "Learning Website"
    assert response.json()["environment"] == "test"


def test_readiness_check() -> None:
    response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json()["status"] in {"ready", "degraded"}
    assert set(response.json()) == {"status"}
    assert client.get("/api/v1/ready/details").status_code == 401
    assert client.get("/api/v1/metrics").status_code == 401


def test_root_points_to_discovery_endpoints() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "Learning Website"
