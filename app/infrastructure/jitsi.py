import uuid
from app.domain.interfaces import ICallGateway

class JitsiGateway(ICallGateway):
    async def create_call_room(self, channel_type: str, user_id: str, recipient_id: str) -> str:
        print(f"Creating {channel_type} call for {user_id} and {recipient_id}")
        return f"call-room-{channel_type}-{uuid.uuid4()}"
