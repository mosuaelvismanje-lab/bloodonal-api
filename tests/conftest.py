import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from main import app
from app.api.dependencies import get_current_user, get_db


# ======================================================
# TEST USER FACTORY (SAFE + ISOLATED)
# ======================================================
class TestUser:
    def __init__(self, uid: str):
        self.uid = uid


@pytest.fixture
def user_factory():
    def _create(uid: str):
        return TestUser(uid)
    return _create


# ======================================================
# CURRENT USER OVERRIDE FACTORY
# ======================================================
def override_get_current_user_factory(user: TestUser):
    async def _override():
        return user
    return _override


# ======================================================
# CLEAN FAKE DB (NO SQLA / NO ASYNC MOCK BUGS)
# ======================================================
class FakeResult:
    def scalar_one_or_none(self):
        return 0


class FakeDB:
    async def execute(self, *args, **kwargs):
        return FakeResult()

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def refresh(self, *args, **kwargs):
        pass


async def override_get_db():
    yield FakeDB()


# ======================================================
# 🔥 CRITICAL FIX: REMOVE CUSTOM EVENT LOOP
# pytest-asyncio handles this internally now
# ======================================================
# ❌ DO NOT define event_loop fixture anymore
# This was causing:
# AttributeError: FixtureDef has no attribute 'unittest'


# ======================================================
# TEST CLIENT (PER TEST USER, FULLY ISOLATED)
# ======================================================
@pytest_asyncio.fixture
async def client(user_factory, request):
    """
    Supports per-test user override via:
    @pytest.mark.parametrize("client", ["user_id"], indirect=True)
    """

    # Default user if not overridden
    uid = getattr(request, "param", "test_user_default")
    test_user = user_factory(uid)

    # Apply overrides
    app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_user)
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    # Cleanup (VERY IMPORTANT)
    app.dependency_overrides.clear()