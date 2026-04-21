import pytest
import pytest_asyncio
import asyncio
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
# FIXED CURRENT USER OVERRIDE
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
# EVENT LOOP FIX
# ======================================================
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ======================================================
# TEST CLIENT FIX (PER TEST USER)
# ======================================================
@pytest_asyncio.fixture(scope="function")
async def client(user_factory, request):
    """
    request.param allows per-test user override
    """

    # default users per test
    uid = getattr(request, "param", "nurse_test_user_789")
    test_user = user_factory(uid)

    app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_user)
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()