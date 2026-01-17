import uuid
from app.domain.interfaces import IChatGateway

class DummyChatGateway(IChatGateway):
    async def create_chat_room(self, user_id: str, recipient_id: str) -> str:
        # In a real-world scenario, this would create a room
        # in a service like Sendbird, Pusher, or your own backend.
        print(f"Creating chat room for {user_id} and {recipient_id}")
        return f"chat-room-{uuid.uuid4()}"
