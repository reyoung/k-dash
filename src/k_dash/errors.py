"""Internal operational errors.

The v1 design deliberately does not promise a stable public exception hierarchy,
but keeping stage/context fields makes diagnostics actionable and testable.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class KDashError(RuntimeError):
    def __init__(self, message: str, *, stage: str, context: Mapping[str, Any] | None = None):
        self.stage = stage
        self.context = dict(context or {})
        suffix = "" if not self.context else " " + " ".join(
            f"{key}={value!r}" for key, value in sorted(self.context.items())
        )
        super().__init__(f"[{stage}] {message}{suffix}")


class ContractError(KDashError):
    pass


class RegistryConfigNotFound(KDashError):
    pass


class RegistryAccessFailure(KDashError):
    pass


class ArtifactNotFound(KDashError):
    pass


class ArtifactIntegrityError(KDashError):
    pass


class OfflineCacheMiss(KDashError):
    pass


class TargetDetectionError(KDashError):
    pass
