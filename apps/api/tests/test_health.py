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
    assert response.json()["dependencies"]["database"] == "ok"


def test_root_points_to_discovery_endpoints() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "Learning Website"
