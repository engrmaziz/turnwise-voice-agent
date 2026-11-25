"""HMAC redaction for log fields that can carry caller PII.

Hashes are stable for the life of the key so a single call can be correlated
without the raw value leaving the process. A missing key is random per process:
logs stay redacted, and operators can see that restarts will not join.
"""

import hashlib
import hmac
import secrets
from collections.abc import Mapping, MutableMapping

import structlog

from server.config import Settings

_NON_SCALAR = "redacted-non-scalar"


class PiiRedactor:
    """structlog processor that hashes configured field names and drops payloads."""

    def __init__(self, settings: Settings) -> None:
        configured = settings.pii_hash_key
        if configured is None:
            self._key = secrets.token_bytes(32)
            self._ephemeral = True
        else:
            self._key = configured.get_secret_value().encode("utf-8")
            self._ephemeral = False
        self._fields = settings.pii_field_names
        self._warned = False

    @property
    def ephemeral(self) -> bool:
        return self._ephemeral

    def hash_value(self, value: str) -> str:
        digest = hmac.new(self._key, value.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"hmac-sha256:{digest}"

    def warn_if_ephemeral(self) -> None:
        if self._ephemeral and not self._warned:
            self._warned = True
            structlog.get_logger("server.pii").warning(
                "pii_hash_key_unset",
                detail="hashes will not correlate across restarts",
            )

    def processor(
        self,
        logger: object,
        method_name: str,
        event_dict: MutableMapping[str, object],
    ) -> MutableMapping[str, object]:
        del logger, method_name
        if "payload" in event_dict:
            # Payloads are pipeline data and may contain names or numbers under
            # keys the field list does not know about.
            event_dict["payload"] = "omitted"
        for field in self._fields:
            if field not in event_dict:
                continue
            event_dict[field] = self._redact(event_dict[field])
        return event_dict

    def _redact(self, value: object) -> str:
        if isinstance(value, str):
            return self.hash_value(value)
        if isinstance(value, bool | int | float):
            return self.hash_value(str(value))
        if isinstance(value, Mapping):
            return _NON_SCALAR
        return _NON_SCALAR
