import pytest
from .app import create_app
from .models import db

@pytest.fixture
def client(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}"})
    with app.test_client() as client:
        yield client
    with app.app_context(): db.drop_all()

def register(client, email="family@example.com"):
    return client.post("/api/auth/register", json={"name": "Asha Family", "email": email, "password": "safe-password"})

def make_trip(client):
    return client.post("/api/trips", json={"origin": "Hyderabad", "destination": "Warangal", "startDate": "2027-01-10", "endDate": "2027-01-11", "budget": "12000", "currency": "INR"})

def test_auth_hash_and_owner_isolation(client):
    assert register(client).status_code == 201
    trip = make_trip(client).get_json()
    assert client.post(f"/api/trips/{trip['id']}/plan", json={}).status_code == 200
    client.post("/api/auth/logout")
    register(client, "other@example.com")
    assert client.get(f"/api/trips/{trip['id']}").status_code == 404

def test_plan_budget_versions_checklist_chat(client):
    register(client)
    trip = make_trip(client).get_json()
    plan = client.post(f"/api/trips/{trip['id']}/plan", json={}).get_json()
    assert plan["isEstimate"] and len(plan["days"]) == 2
    assert client.post(f"/api/trips/{trip['id']}/validate", json={}).status_code == 200
    assert len(client.get(f"/api/trips/{trip['id']}/versions").get_json()) == 1
    rescue = client.post(f"/api/trips/{trip['id']}/optimize-budget", json={"budget": "5000"}).get_json()
    assert rescue["budget"] == "5000" and len(client.get(f"/api/trips/{trip['id']}/versions").get_json()) == 2
    checklist = client.get(f"/api/trips/{trip['id']}/checklist").get_json()
    checklist[0]["done"] = True
    assert client.patch(f"/api/trips/{trip['id']}/checklist", json={"items": checklist}).get_json()[0]["done"]
    assert len(client.post(f"/api/trips/{trip['id']}/chat", json={"message": "Make it relaxed"}).get_json()) == 2
    assert client.delete(f"/api/trips/{trip['id']}").status_code == 200
    assert client.get(f"/api/trips/{trip['id']}/versions").status_code == 404

def test_validates_trip_and_requires_auth(client):
    assert client.get("/api/trips").status_code == 401
    register(client)
    bad = make_trip(client)
    assert bad.status_code == 201
    invalid = client.post("/api/trips", json={"origin":"A","destination":"B","startDate":"2027-01-12","endDate":"2027-01-10","budget":"-2"})
    assert invalid.status_code == 400

def test_place_catalog_uses_distinct_real_names_and_unpriced_estimates(client):
    register(client)
    results = client.get("/api/places/search?destination=Kerala").get_json()["results"]
    names = [place["name"] for place in results]
    assert len(names) >= 10 and len(names) == len(set(names))
    assert all(place["cost"] is None for place in results)
    assert client.get("/api/places/search?destination=Atlantis").get_json()["results"] == []

def test_family_interests_and_pace_shape_generated_plan(client):
    register(client)
    client.put("/api/family-profile", json={"adultsCount": 2, "childrenAgeRanges": ["5–8"], "interests": ["Nature"], "travelPace": "relaxed"})
    trip = make_trip(client).get_json()
    plan = client.post(f"/api/trips/{trip['id']}/plan", json={}).get_json()
    assert plan["personalization"]["travelPace"] == "relaxed"
    assert plan["personalization"]["interestsUsed"] == ["nature"]
    assert all(len(day["items"]) <= 1 for day in plan["days"])
    assert plan["days"][0]["items"][0]["title"] == "Pakhal Lake"
