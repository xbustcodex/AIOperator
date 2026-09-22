"""Hashing / entropy / identifier capability (stdlib only)."""

import hashlib
import secrets
import uuid

from buster.capabilities.base import Capability, CapabilityContext, CapabilityResult


class CryptoCapability(Capability):
    """``crypto.hash``, ``crypto.uuid``, ``crypto.random``."""

    name = "crypto"
    actions_list = ["crypto.hash", "crypto.uuid", "crypto.random"]
    _MODE_ORDER = {"md5": 1, "sha1": 2, "sha256": 3}

    @property
    def actions(self) -> list[str]:
        return self.actions_list

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        extra = ctx.extra or {}
        if ctx.action == "crypto.uuid":
            return CapabilityResult.ok({"uuid": str(uuid.uuid4())})
        if ctx.action == "crypto.random":
            size = int(extra.get("size", 16))
            return CapabilityResult.ok({
                "bytes": secrets.token_hex(size),
                "size": size,
            })
        if ctx.action == "crypto.hash":
            return CapabilityResult.ok(self._hash(extra))
        return CapabilityResult.fail(f"Unsupported action '{ctx.action}'")

    @staticmethod
    def _hash(extra: dict) -> dict:
        mode = extra.get("mode", "sha256").lower()
        data = extra.get("data")
        file_path = extra.get("file")
        if file_path:
            with open(file_path, "rb") as handle:
                digest = _digest_bytes(mode, handle.read())
        elif data is not None:
            digest = _digest_bytes(mode, str(data).encode("utf-8"))
        else:
            raise ValueError("crypto.hash requires 'data' or 'file'")
        return {"mode": mode, "hex": digest, "length": len(digest)}


def _digest_bytes(mode: str, raw: bytes) -> str:
    hasher = hashlib.new(mode)
    hasher.update(raw)
    return hasher.hexdigest()