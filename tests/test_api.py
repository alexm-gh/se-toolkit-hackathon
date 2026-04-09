import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.main import app
from app.database import get_db, Base
import os

# Load database credentials from .env.secret
def _load_db_credentials():
    """Parse .env.secret to extract database credentials."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env.secret")
    credentials = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    credentials[key.strip()] = value.strip()
    return credentials

_credentials = _load_db_credentials()
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    f"postgresql+asyncpg://{_credentials.get('POSTGRES_USER', 'ttmm_user')}:{_credentials.get('POSTGRES_PASSWORD', 'ttmm_password')}@localhost:5432/ttmm_test"
)

@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_profile(client):
    profile_data = {
        "name": "Alice",
        "level": "intermediate",
        "available_time": [
            {"day": "Monday", "start_time": "09:00", "end_time": "11:00"}
        ],
        "desired_place": ["4th dorm", "Sport complex"],
        "contact_info": {"telegram": "@alice", "phone": "+1234567890"},
        "additional_info": {"preferred_hand": "right"}
    }
    response = await client.post("/api/v1/profiles", json=profile_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alice"
    assert data["level"] == "intermediate"
    assert "contact_info" not in data  # Should be hidden


@pytest.mark.asyncio
async def test_get_profile(client):
    # Create profile first
    profile_data = {
        "name": "Bob",
        "level": "beginner",
        "available_time": [],
        "desired_place": ["anywhere"],
        "contact_info": {"email": "bob@example.com"},
        "additional_info": {}
    }
    create_resp = await client.post("/api/v1/profiles", json=profile_data)
    profile_id = create_resp.json()["id"]
    
    # Get profile
    response = await client.get(f"/api/v1/profiles/{profile_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Bob"
    assert "contact_info" not in data


@pytest.mark.asyncio
async def test_list_profiles(client):
    # Create two profiles
    for name in ["Charlie", "David"]:
        await client.post("/api/v1/profiles", json={
            "name": name,
            "level": "advanced",
            "available_time": [],
            "desired_place": [],
            "contact_info": {"test": "test"}
        })
    
    response = await client.get("/api/v1/profiles")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_update_profile(client):
    profile_data = {
        "name": "Eve",
        "level": "beginner",
        "available_time": [],
        "desired_place": [],
        "contact_info": {}
    }
    create_resp = await client.post("/api/v1/profiles", json=profile_data)
    profile_id = create_resp.json()["id"]
    
    # Update profile
    response = await client.put(f"/api/v1/profiles/{profile_id}", json={
        "level": "intermediate",
        "desired_place": ["Sport complex"]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["level"] == "intermediate"
    assert data["desired_place"] == ["Sport complex"]


@pytest.mark.asyncio
async def test_delete_profile(client):
    profile_data = {
        "name": "Frank",
        "level": "professional",
        "available_time": [],
        "desired_place": [],
        "contact_info": {}
    }
    create_resp = await client.post("/api/v1/profiles", json=profile_data)
    profile_id = create_resp.json()["id"]
    
    # Delete profile
    response = await client.delete(f"/api/v1/profiles/{profile_id}")
    assert response.status_code == 204
    
    # Verify deletion
    get_resp = await client.get(f"/api/v1/profiles/{profile_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_match_request_flow(client):
    # Create two profiles
    sender_resp = await client.post("/api/v1/profiles", json={
        "name": "Sender",
        "level": "intermediate",
        "available_time": [],
        "contact_info": {"telegram": "@sender"}
    })
    sender_id = sender_resp.json()["id"]
    
    receiver_resp = await client.post("/api/v1/profiles", json={
        "name": "Receiver",
        "level": "intermediate",
        "available_time": [],
        "contact_info": {"telegram": "@receiver"}
    })
    receiver_id = receiver_resp.json()["id"]
    
    # Send match request
    request_resp = await client.post("/api/v1/match-requests", json={
        "sender_id": sender_id,
        "receiver_id": receiver_id
    })
    assert request_resp.status_code == 201
    request_data = request_resp.json()
    request_id = request_data["id"]
    
    # Check received requests
    received_resp = await client.get(f"/api/v1/match-requests/received/{receiver_id}")
    assert received_resp.status_code == 200
    assert len(received_resp.json()) == 1
    
    # Respond to request
    respond_resp = await client.post(f"/api/v1/match-requests/{request_id}/respond", json={
        "approved": True,
        "user_id": receiver_id
    })
    assert respond_resp.status_code == 200
    assert respond_resp.json()["status"] == "approved"
    
    # Get contacts
    contacts_resp = await client.get(f"/api/v1/match-requests/{request_id}/contacts?user_id={sender_id}")
    assert contacts_resp.status_code == 200
    contacts_data = contacts_resp.json()
    assert "sender_contact" in contacts_data
    assert "receiver_contact" in contacts_data


@pytest.mark.asyncio
async def test_contact_privacy(client):
    """Test that contacts are never exposed in public profiles"""
    profile_data = {
        "name": "Grace",
        "level": "advanced",
        "available_time": [],
        "desired_place": [],
        "contact_info": {"secret": "data"},
        "additional_info": {"public": "info"}
    }
    create_resp = await client.post("/api/v1/profiles", json=profile_data)
    data = create_resp.json()
    
    assert "contact_info" not in data
    assert data["additional_info"] == {"public": "info"}
    
    # Also test in list
    list_resp = await client.get("/api/v1/profiles")
    for profile in list_resp.json():
        assert "contact_info" not in profile
