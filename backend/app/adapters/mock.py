from __future__ import annotations

from app.adapters.base import TargetAdapter, TargetResponse
from app.adapters.http import HTTPAdapter


class MockAdapter(TargetAdapter):
    """Adapter targeting the bundled mock vulnerable AI target.

    Configure via target.meta:
      url        - mock target base url (default http://127.0.0.1:8001)
      profile    - optional profile to activate on the mock target
    """

    name = "mock"

    def __init__(self, target):
        super().__init__(target)
        meta = target.meta or {}
        base = meta.get("url", "http://127.0.0.1:8001")
        if str(base).endswith("/chat"):
            target.url = str(base)
        else:
            target.url = f"{base}/chat"
        if meta.get("profile"):
            target.headers = {"X-Mock-Profile": str(meta["profile"])}
        self._http = HTTPAdapter(target)

    async def validate(self) -> list[str]:
        return await self._http.validate()

    async def send_message(
        self, payload: str, *, conversation: list[dict] | None = None
    ) -> TargetResponse:
        template = dict(self._http.target.request_template or {})
        if not template:
            template = {"message": ""}
            self._http.target.request_template = template
        self._http.target.payload_path = "message"
        self._http.target.response_path = "answer"
        return await self._http.send_message(payload, conversation=conversation)

    async def reset_session(self) -> bool:
        return True