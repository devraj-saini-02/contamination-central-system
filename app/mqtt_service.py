import asyncio
import logging
from typing import Awaitable, Callable, Optional

import asyncio_mqtt as aiomqtt
from pydantic import BaseModel

from app.config import Settings

logger = logging.getLogger(__name__)

RECONNECT_DELAY_S = 3
MessageHandler = Callable[[str, bytes], Awaitable[None]]


class MqttService:
    """Persistent MQTT connection with reconnect-on-drop. Subscribes to the fixed set of
    inbound topics (protocol §2.1) and dispatches each message to `on_message`; also exposes
    `publish()` for the same connection so REST handlers (e.g. POST /models/push) and the
    ingestion handlers share one client rather than opening a second connection."""

    def __init__(self, settings: Settings, subscriptions: list[tuple[str, int]], on_message: MessageHandler):
        self._settings = settings
        self._subscriptions = subscriptions
        self._on_message = on_message
        self._client: Optional[aiomqtt.Client] = None
        self._stopped = False

    async def run(self) -> None:
        while not self._stopped:
            try:
                async with aiomqtt.Client(
                    hostname=self._settings.mqtt_broker_host,
                    port=self._settings.mqtt_broker_port,
                    username=self._settings.mqtt_username or None,
                    password=self._settings.mqtt_password or None,
                    client_id="central-system-cc",
                ) as client:
                    self._client = client
                    for topic, qos in self._subscriptions:
                        await client.subscribe(topic, qos=qos)
                    logger.info("MQTT connected, subscribed to %s", [t for t, _ in self._subscriptions])
                    async with client.messages() as messages:
                        async for message in messages:
                            try:
                                await self._on_message(str(message.topic), message.payload)
                            except Exception:
                                logger.exception("error handling message on %s", message.topic)
            except aiomqtt.MqttError as e:
                self._client = None
                logger.warning("MQTT connection lost (%s), reconnecting in %ss", e, RECONNECT_DELAY_S)
                await asyncio.sleep(RECONNECT_DELAY_S)

    def stop(self) -> None:
        self._stopped = True

    async def publish(self, topic: str, payload: BaseModel | str | bytes, qos: int = 1, retain: bool = False) -> None:
        if self._client is None:
            raise RuntimeError("MQTT client not connected yet")
        body = payload.model_dump_json() if isinstance(payload, BaseModel) else payload
        await self._client.publish(topic, body, qos=qos, retain=retain)
