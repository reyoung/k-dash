"""Small direct OCI Distribution API client with bearer/basic auth."""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import requests

from .artifact import OCI_MANIFEST, parse_json_blob, verify_descriptor
from .canonical import digest_bytes
from .errors import ArtifactIntegrityError, ArtifactNotFound, RegistryAccessFailure
from .model import RegistryConfig

ACCEPT_MANIFESTS = ", ".join((OCI_MANIFEST, "application/vnd.docker.distribution.manifest.v2+json"))


@dataclass(frozen=True)
class PulledArtifact:
    digest: str
    manifest: dict[str, Any]
    manifest_bytes: bytes
    config: dict[str, Any]
    config_bytes: bytes
    layers: tuple[bytes, ...]


class OCIClient:
    def __init__(self, config: RegistryConfig, kernel: str, *, timeout: float = 30.0):
        self.config = config
        self.repository = "/".join(part for part in (config.repository_prefix, kernel) if part)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "k-dash/0.1"
        self._basic = self._resolve_basic_auth(config)
        self._bearer: str | None = None

    @staticmethod
    def _resolve_basic_auth(config: RegistryConfig) -> tuple[str, str] | None:
        auth = config.auth
        if auth.get("type") == "anonymous":
            return None
        if auth.get("type") == "basic":
            username = auth.get("username") or os.environ.get(str(auth.get("username_env", "")))
            password = auth.get("password") or os.environ.get(str(auth.get("password_env", "")))
            if not isinstance(username, str) or not isinstance(password, str):
                raise RegistryAccessFailure("basic credentials are incomplete", stage="registry-auth", context={"registry": config.name})
            return username, password
        config_path = Path(auth.get("config_path", "~/.docker/config.json")).expanduser()
        try:
            docker_config = json.loads(config_path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise RegistryAccessFailure(
                "Docker credential config cannot be read",
                stage="registry-auth",
                context={"registry": config.name, "path": str(config_path)},
            ) from error
        host = urlparse(config.url).netloc
        auths = docker_config.get("auths", {})
        encoded = None
        for key in (host, f"https://{host}", f"http://{host}"):
            if isinstance(auths.get(key), dict) and auths[key].get("auth"):
                encoded = auths[key]["auth"]
                break
        if not encoded:
            raise RegistryAccessFailure(
                "Docker credential helper entries are not supported without resolved auth",
                stage="registry-auth",
                context={"registry": config.name},
            )
        try:
            username, password = base64.b64decode(encoded).decode().split(":", 1)
        except (ValueError, UnicodeDecodeError) as error:
            raise RegistryAccessFailure("invalid Docker auth entry", stage="registry-auth", context={"registry": config.name}) from error
        return username, password

    @property
    def verify(self) -> bool | str:
        return self.config.ca_bundle or self.config.verify_tls

    def _url(self, suffix: str) -> str:
        return f"{self.config.url}/v2/{self.repository}/{suffix.lstrip('/')}"

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        headers = dict(kwargs.pop("headers", {}))
        if self._bearer:
            headers["Authorization"] = f"Bearer {self._bearer}"
        try:
            response = self.session.request(
                method,
                url,
                headers=headers,
                auth=None if self._bearer else self._basic,
                verify=self.verify,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as error:
            raise RegistryAccessFailure(
                "registry request failed",
                stage="registry-access",
                context={"registry": self.config.name, "method": method},
            ) from error
        if response.status_code == 401 and "bearer " in response.headers.get("WWW-Authenticate", "").lower():
            self._authorize(response.headers["WWW-Authenticate"])
            headers["Authorization"] = f"Bearer {self._bearer}"
            try:
                response = self.session.request(
                    method, url, headers=headers, verify=self.verify, timeout=self.timeout, **kwargs
                )
            except requests.RequestException as error:
                raise RegistryAccessFailure(
                    "authorized registry request failed", stage="registry-access", context={"registry": self.config.name}
                ) from error
        return response

    def _authorize(self, challenge: str) -> None:
        values = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
        realm = values.get("realm")
        if not realm:
            raise RegistryAccessFailure("invalid bearer challenge", stage="registry-auth", context={"registry": self.config.name})
        params = {key: values[key] for key in ("service", "scope") if key in values}
        try:
            response = self.session.get(realm, params=params, auth=self._basic, verify=self.verify, timeout=self.timeout)
        except requests.RequestException as error:
            raise RegistryAccessFailure("token request failed", stage="registry-auth", context={"registry": self.config.name}) from error
        if response.status_code // 100 != 2:
            raise RegistryAccessFailure(
                "registry authentication rejected",
                stage="registry-auth",
                context={"registry": self.config.name, "status": response.status_code},
            )
        token_data = response.json()
        token = token_data.get("token") or token_data.get("access_token")
        if not isinstance(token, str):
            raise RegistryAccessFailure("token response is incomplete", stage="registry-auth", context={"registry": self.config.name})
        self._bearer = token

    def get_manifest(self, reference: str) -> tuple[str, bytes, dict[str, Any]]:
        response = self._request(
            "GET", self._url(f"manifests/{quote(reference, safe=':@')}"), headers={"Accept": ACCEPT_MANIFESTS}
        )
        if response.status_code == 404:
            raise ArtifactNotFound(
                "artifact does not exist", stage="registry-manifest", context={"registry": self.config.name, "reference": reference}
            )
        if response.status_code // 100 != 2:
            raise RegistryAccessFailure(
                "manifest request was rejected",
                stage="registry-access",
                context={"registry": self.config.name, "status": response.status_code},
            )
        computed = digest_bytes(response.content)
        advertised = response.headers.get("Docker-Content-Digest")
        if advertised and advertised != computed:
            raise ArtifactIntegrityError("manifest digest mismatch", stage="registry-manifest")
        return advertised or computed, response.content, parse_json_blob(response.content, stage="registry-manifest")

    def get_blob(self, digest: str) -> bytes:
        response = self._request("GET", self._url(f"blobs/{quote(digest, safe=':')}"))
        if response.status_code == 404:
            raise ArtifactIntegrityError("referenced blob is missing", stage="registry-blob", context={"digest": digest})
        if response.status_code // 100 != 2:
            raise RegistryAccessFailure(
                "blob request was rejected", stage="registry-access", context={"registry": self.config.name, "status": response.status_code}
            )
        if digest_bytes(response.content) != digest:
            raise ArtifactIntegrityError("blob digest mismatch", stage="registry-blob", context={"digest": digest})
        return response.content

    def pull(self, reference: str, *, artifact_type: str) -> PulledArtifact:
        digest, manifest_bytes, manifest = self.get_manifest(reference)
        if manifest.get("mediaType") != OCI_MANIFEST or manifest.get("artifactType") != artifact_type:
            raise ArtifactIntegrityError("unexpected artifact type", stage="registry-manifest")
        descriptor = manifest.get("config")
        layers = manifest.get("layers")
        if not isinstance(descriptor, dict) or not isinstance(layers, list) or not layers:
            raise ArtifactIntegrityError("artifact descriptors are incomplete", stage="registry-manifest")
        config_bytes = self.get_blob(descriptor["digest"])
        verify_descriptor(descriptor, config_bytes, stage="registry-config")
        layer_payloads: list[bytes] = []
        for layer_descriptor in layers:
            payload = self.get_blob(layer_descriptor["digest"])
            verify_descriptor(layer_descriptor, payload, stage="registry-layer")
            layer_payloads.append(payload)
        return PulledArtifact(
            digest=digest,
            manifest=manifest,
            manifest_bytes=manifest_bytes,
            config=parse_json_blob(config_bytes, stage="registry-config"),
            config_bytes=config_bytes,
            layers=tuple(layer_payloads),
        )

    def _blob_exists(self, digest: str) -> bool:
        response = self._request("HEAD", self._url(f"blobs/{quote(digest, safe=':')}"))
        if response.status_code == 404:
            return False
        if response.status_code // 100 != 2:
            raise RegistryAccessFailure(
                "blob existence check failed", stage="registry-access", context={"registry": self.config.name, "status": response.status_code}
            )
        return True

    def push_blob(self, payload: bytes) -> str:
        digest = digest_bytes(payload)
        if self._blob_exists(digest):
            return digest
        response = self._request("POST", self._url("blobs/uploads/"), headers={"Content-Length": "0"})
        if response.status_code not in {202, 201}:
            raise RegistryAccessFailure(
                "blob upload could not start", stage="registry-push", context={"registry": self.config.name, "status": response.status_code}
            )
        location = urljoin(self.config.url + "/", response.headers.get("Location", ""))
        separator = "&" if "?" in location else "?"
        upload = self._request(
            "PUT",
            f"{location}{separator}digest={quote(digest, safe=':')}",
            data=payload,
            headers={"Content-Type": "application/octet-stream", "Content-Length": str(len(payload))},
        )
        if upload.status_code not in {201, 202}:
            raise RegistryAccessFailure(
                "blob upload failed", stage="registry-push", context={"registry": self.config.name, "status": upload.status_code}
            )
        return digest

    def push_manifest(self, reference: str, manifest_bytes: bytes) -> str:
        response = self._request(
            "PUT",
            self._url(f"manifests/{quote(reference, safe=':@')}"),
            data=manifest_bytes,
            headers={"Content-Type": OCI_MANIFEST, "Content-Length": str(len(manifest_bytes))},
        )
        if response.status_code not in {201, 202}:
            raise RegistryAccessFailure(
                "manifest upload failed", stage="registry-push", context={"registry": self.config.name, "status": response.status_code}
            )
        return response.headers.get("Docker-Content-Digest", digest_bytes(manifest_bytes))

    def push(self, reference: str, config_bytes: bytes, layers: list[bytes], manifest_bytes: bytes) -> str:
        self.push_blob(config_bytes)
        for layer in layers:
            self.push_blob(layer)
        return self.push_manifest(reference, manifest_bytes)
