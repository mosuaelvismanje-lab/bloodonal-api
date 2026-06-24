class InMemoryIdempotencyStore:
    def __init__(self):
        self._store = set()

    async def exists(self, key: str) -> bool:
        return key in self._store

    async def save(self, key: str):
        self._store.add(key)