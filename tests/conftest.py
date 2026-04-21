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
# FAKE DB (NO SQLA DEPENDENCY)
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
# FIXED CLIENT FIXTURE (NO event_loop FIXTURE!)
# ======================================================
@pytest_asyncio.fixture
async def client(user_factory, request):
    """
    Per-test user injection via request.param
    """

    uid = getattr(request, "param", "test_user_default")
    test_user = user_factory(uid)

    # override FastAPI dependencies
    app.dependency_overrides[get_current_user] = override_get_current_user_factory(test_user)
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        # attach user for assertions (IMPORTANT FIX)
        ac.test_user = test_user
        yield ac

    # cleanup
    app.dependency_overrides.clear()