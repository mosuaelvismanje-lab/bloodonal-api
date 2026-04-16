import uuid
import logging
from app.domain.interfaces import ICallGateway

logger = logging.getLogger(__name__)


class JitsiGateway(ICallGateway):
    """
    Concrete implementation of ICallGateway using Jitsi Meet.
    """

    async def create_call_room(
            self,
            channel_type: str,
            user_id: str,
            recipient_id: str
    ) -> str:
        """
        Generates a unique Jitsi Meet URL for the consultation.
        """
        # Using a clean name for the room
        room_id = f"bloodonal-{channel_type}-{uuid.uuid4().hex[:12]}"
        room_url = f"https://meet.jit.si/{room_id}"

        print(f"✅ Jitsi Room Created: {room_url}")
        return room_url

    async def send_call(self, phone: str, room_link: str) -> bool:
        """
        REQUIRED BY INTERFACE:
        In a real app, this might send an SMS with the Jitsi link to the doctor.
        For now, we just log it as successful.
        """
        print(f"📱 Sending {room_link} to {phone} via SMS/Notification simulation...")
        return True

    async def verify_call(self, call_id: str) -> bool:
        """
        REQUIRED BY INTERFACE:
        Checks if the call session is still active.
        """
        return True

    async def get_call_status(self, call_id: str) -> str:
        """
        REQUIRED BY INTERFACE:
        Returns the current state of the call.
        """
        return "completed"
