"""Container registry client tests, using mocked HTTP responses (no network access)."""
import json
from typing import Any, Dict, List, Optional
from unittest import mock

import pytest
import requests

from mandalore.config.ConstantConfig import ConstantConfig
from mandalore.console.cli.ParametersManager import ParametersManager
from mandalore.model.MetaImages import MetaImages
from mandalore.utils.WebUtils import WebUtils

REGISTRY = f"https://{ConstantConfig.DOCKER_REGISTRY}"
BASE = f"{REGISTRY}/v2/{ConstantConfig.IMAGE_REPOSITORY}"
OCI_INDEX = "application/vnd.oci.image.index.v1+json"
OCI_MANIFEST = "application/vnd.oci.image.manifest.v1+json"


def make_response(status: int = 200, body: Any = None, headers: Optional[Dict[str, str]] = None) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(body).encode() if body is not None else b""
    response.headers.update(headers or {})
    return response


CHALLENGE = {"www-authenticate": f'Bearer realm="{REGISTRY}/token",service="{ConstantConfig.DOCKER_REGISTRY}",scope="repository:{ConstantConfig.IMAGE_REPOSITORY}:pull"'}

INDEX = {
    "mediaType": OCI_INDEX,
    "manifests": [
        {"mediaType": OCI_MANIFEST, "digest": "sha256:amd", "platform": {"architecture": "amd64", "os": "linux"}},
        {"mediaType": OCI_MANIFEST, "digest": "sha256:arm", "platform": {"architecture": "arm64", "os": "linux", "variant": "v8"}},
        {"mediaType": OCI_MANIFEST, "digest": "sha256:att", "platform": {"architecture": "unknown", "os": "unknown"},
         "annotations": {"vnd.docker.reference.type": "attestation-manifest"}},
    ],
}
IMAGE_MANIFEST = {"mediaType": OCI_MANIFEST, "config": {"digest": "sha256:cfg", "size": 100},
                  "layers": [{"size": 1000}, {"size": 2000}]}
CONFIG = {"architecture": "amd64", "os": "linux", "config": {"Labels": {"org.mandalore.version": "3.1.2"}}}


class FakeRegistry:
    """Minimal OCI distribution registry requiring a bearer token."""

    def __init__(self, tags: List[str], private: bool = False) -> None:
        self.tags = tags
        self.private = private
        self.calls: List[str] = []
        self.token_requests: List[Dict[str, Any]] = []

    def __call__(self, method: str, url: str, headers: Optional[Dict[str, str]] = None, params=None, auth=None, **kwargs) -> requests.Response:
        self.calls.append(f"{method} {url}")
        headers = headers or {}
        if url == f"{REGISTRY}/token":
            self.token_requests.append({"params": params, "auth": auth})
            if self.private and auth is None:
                return make_response(401, {"errors": []})
            return make_response(200, {"token": "tok"})
        if headers.get("Authorization") != "Bearer tok":
            return make_response(401, {"errors": []}, CHALLENGE)
        if url.startswith(f"{BASE}/tags/list"):
            if "last=" not in url and len(self.tags) > 2:
                return make_response(200, {"tags": self.tags[:2]}, {"Link": f'</v2/{ConstantConfig.IMAGE_REPOSITORY}/tags/list?n=2&last={self.tags[1]}>; rel="next"'})
            return make_response(200, {"tags": self.tags[2:] if "last=" in url else self.tags})
        if url == f"{BASE}/manifests/full":
            return make_response(200, INDEX, {"docker-content-digest": "sha256:index-full", "content-type": OCI_INDEX})
        if url == f"{BASE}/manifests/full-3.1.2":
            return make_response(200, INDEX, {"docker-content-digest": "sha256:index-full", "content-type": OCI_INDEX})
        if url == f"{BASE}/manifests/light":
            return make_response(200, IMAGE_MANIFEST, {"docker-content-digest": "sha256:single-light", "content-type": OCI_MANIFEST})
        if url in (f"{BASE}/manifests/sha256:amd", f"{BASE}/manifests/sha256:arm"):
            return make_response(200, IMAGE_MANIFEST, {"content-type": OCI_MANIFEST})
        if url == f"{BASE}/blobs/sha256:cfg":
            return make_response(200, CONFIG)
        return make_response(404, {"errors": []})


@pytest.fixture(autouse=True)
def reset_state(monkeypatch, tmp_path):
    # Isolate from the user docker credentials and reset the cached token
    monkeypatch.setenv("DOCKER_CONFIG", str(tmp_path))
    monkeypatch.setattr(WebUtils, "_WebUtils__registry_token", None)
    monkeypatch.setattr(WebUtils, "_WebUtils__registry_unreachable_logged", False)
    ParametersManager().offline_mode = False


def test_list_tags_with_token_and_pagination():
    registry = FakeRegistry(["full", "full-3.1.1", "full-3.1.2", "light"])
    with mock.patch("requests.request", side_effect=registry):
        assert WebUtils.listRegistryTags() == ["full", "full-3.1.1", "full-3.1.2", "light"]
    assert registry.token_requests[0]["params"]["scope"] == f"repository:{ConstantConfig.IMAGE_REPOSITORY}:pull"
    assert registry.token_requests[0]["auth"] is None


def test_index_image_data_skips_attestations():
    registry = FakeRegistry([])
    with mock.patch("requests.request", side_effect=registry):
        data = WebUtils.getRemoteImageData("full")
    assert data is not None
    assert data["digest"] == "sha256:index-full"
    assert [i["architecture"] for i in data["images"]] == ["amd64", "arm64"]
    assert data["images"][0]["size"] == 3100
    meta = MetaImages(data)
    assert meta.multi_arch and meta.meta_id == "sha256:index-full"
    assert meta.list_arch == {"amd64", "arm64/v8"}
    assert meta.is_latest


def test_single_manifest_image_data():
    registry = FakeRegistry([])
    with mock.patch("requests.request", side_effect=registry):
        data = WebUtils.getRemoteImageData("light")
    assert data is not None
    meta = MetaImages(data)
    assert not meta.multi_arch
    assert meta.meta_id == "sha256:single-light"
    assert meta.list_arch == {"amd64"}


def test_remote_version_from_index():
    registry = FakeRegistry([])
    with mock.patch("requests.request", side_effect=registry):
        assert WebUtils.getRemoteVersion("full") == "3.1.2"


def test_private_registry_degrades_quietly():
    registry = FakeRegistry(["full"], private=True)
    with mock.patch("requests.request", side_effect=registry):
        assert WebUtils.listRegistryTags() is None
        assert WebUtils.getRemoteImageData("full") is None


def test_docker_credentials_only_sent_to_registry(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"auths": {ConstantConfig.DOCKER_REGISTRY: {"auth": "dXNlcjpzZWNyZXQ="}}}))
    registry = FakeRegistry(["full"], private=True)
    with mock.patch("requests.request", side_effect=registry):
        assert WebUtils.listRegistryTags() == ["full"]
    assert registry.token_requests[0]["auth"] == ("user", "secret")

    # A challenge pointing to another host must not receive the credentials
    evil = dict(CHALLENGE)
    evil["www-authenticate"] = 'Bearer realm="https://evil.example/token",service="x"'
    captured = []

    def fake(method, url, headers=None, params=None, auth=None, **kwargs):
        if url.startswith("https://evil.example"):
            captured.append(auth)
            return make_response(200, {"token": "nope"})
        return make_response(401, {}, evil)

    WebUtils._WebUtils__registry_token = None  # type: ignore[attr-defined]
    with mock.patch("requests.request", side_effect=fake):
        WebUtils.listRegistryTags()
    assert captured == [None]
