import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Optional, Dict, List, Tuple
from urllib.parse import urlparse, urljoin

import requests
from requests import Response

from mandalore.console.cli.ParametersManager import ParametersManager
from mandalore.exceptions.MandaloreExceptions import CancelOperation
from mandalore.config.ConstantConfig import ConstantConfig
from mandalore.utils.ExeLog import logger


class WebUtils:
    """Web requests helpers: GitHub API and OCI distribution compliant container registry (ghcr.io, Docker Hub, ...)"""
    # Registry media types
    MEDIA_INDEX_TYPES = ("application/vnd.oci.image.index.v1+json",
                         "application/vnd.docker.distribution.manifest.list.v2+json")
    MEDIA_IMAGE_TYPES = ("application/vnd.oci.image.manifest.v1+json",
                         "application/vnd.docker.distribution.manifest.v2+json")
    __ACCEPT_MANIFESTS = ", ".join(MEDIA_INDEX_TYPES + MEDIA_IMAGE_TYPES)
    # Some registries use a dedicated host for authentication: credentials can be sent to these hosts too
    __AUTH_HOSTS_ALIASES: Dict[str, Tuple[str, ...]] = {"registry-1.docker.io": ("auth.docker.io",)}

    __registry_token: Optional[str] = None
    __registry_lock = threading.Lock()
    __registry_unreachable_logged = False

    # ---------------------------------------------------------------------------------------------------------------
    # GitHub
    # ---------------------------------------------------------------------------------------------------------------

    @classmethod
    def getLatestWrapperRelease(cls) -> str:
        """Fetch from GitHub release the latest Mandalore wrapper version"""
        if ParametersManager().offline_mode:
            raise CancelOperation
        url: str = f"https://api.github.com/repos/{ConstantConfig.GITHUB_REPO}/releases/latest"
        response = cls.__runRequest(url, "Github")
        if response is None:
            raise CancelOperation
        if response.status_code in (401, 403, 404):
            # Private repository or no release published yet: the update check is silently postponed
            logger.verbose(f"Unable to fetch the latest Mandalore release from GitHub (HTTP {response.status_code}). "
                           f"The repository may be private or has no release yet.")
            raise CancelOperation
        if response.status_code != 200:
            logger.debug(f"Unexpected response from GitHub API ({response.status_code}) on {url}")
            raise CancelOperation
        latest_tag = response.json().get("tag_name")
        if latest_tag is None:
            logger.warning("Unable to parse the latest Mandalore wrapper version from github API.")
            raise CancelOperation
        return latest_tag

    # ---------------------------------------------------------------------------------------------------------------
    # Container registry
    # ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    def __registryUrl(path: str) -> str:
        return f"https://{ConstantConfig.DOCKER_REGISTRY}/v2/{ConstantConfig.IMAGE_REPOSITORY}/{path}"

    @classmethod
    def __getDockerCredentials(cls) -> Optional[Tuple[str, str]]:
        """Load the registry credentials stored by 'docker login' (config file or credential helper), if any.
        Return a (username, secret) tuple or None."""
        registry = ConstantConfig.DOCKER_REGISTRY
        docker_config_dir = os.getenv("DOCKER_CONFIG")
        config_path = Path(docker_config_dir) if docker_config_dir else ConstantConfig.user_home / ".docker"
        try:
            with open(config_path / "config.json", "r") as config_file:
                config = json.load(config_file)
        except (OSError, ValueError):
            return None
        # Plain auth stored in the config file
        auth = config.get("auths", {}).get(registry, {}).get("auth")
        if auth:
            try:
                username, _, secret = base64.b64decode(auth).decode("utf-8").partition(":")
                if secret:
                    return username, secret
            except (ValueError, UnicodeDecodeError):
                logger.debug(f"Unable to decode docker credentials for {registry}")
        # Credential helper (e.g. Docker Desktop, pass, secretservice)
        helper = config.get("credHelpers", {}).get(registry) or config.get("credsStore")
        if helper:
            helper_bin = shutil.which(f"docker-credential-{helper}")
            if helper_bin is None:
                return None
            try:
                result = subprocess.run([helper_bin, "get"], input=registry.encode(), capture_output=True, timeout=10)
                if result.returncode == 0:
                    data = json.loads(result.stdout.decode("utf-8"))
                    if data.get("Secret"):
                        return data.get("Username", ""), data["Secret"]
            except (OSError, ValueError, subprocess.SubprocessError) as e:
                logger.debug(f"Unable to query docker credential helper '{helper}': {e}")
        return None

    @classmethod
    def __authenticate(cls, challenge: str) -> Optional[str]:
        """Answer a registry 'WWW-Authenticate: Bearer ...' challenge and return a bearer token.
        Docker credentials are used when available (required for private images), otherwise an anonymous token is requested."""
        if not challenge.lower().startswith("bearer "):
            logger.debug(f"Unsupported registry authentication challenge: {challenge}")
            return None
        params = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
        realm = params.get("realm")
        if not realm:
            return None
        query: Dict[str, str] = {"scope": f"repository:{ConstantConfig.IMAGE_REPOSITORY}:pull"}
        if params.get("service"):
            query["service"] = params["service"]
        auth = None
        # Credentials are only sent to the registry itself (or its known authentication host)
        realm_host = urlparse(realm).hostname or ""
        allowed_hosts = (ConstantConfig.DOCKER_REGISTRY,) + cls.__AUTH_HOSTS_ALIASES.get(ConstantConfig.DOCKER_REGISTRY, ())
        if urlparse(realm).scheme == "https" and realm_host in allowed_hosts:
            credentials = cls.__getDockerCredentials()
            if credentials is not None:
                logger.debug(f"Using docker credentials to authenticate on {ConstantConfig.DOCKER_REGISTRY}")
                auth = credentials
        response = cls.__runRequest(realm, "Registry authentication", params=query, auth=auth)
        if response is None or response.status_code != 200:
            if response is not None:
                logger.debug(f"Registry authentication failed ({response.status_code}): {response.text[:200]}")
            return None
        try:
            data = response.json()
        except ValueError:
            return None
        return data.get("token") or data.get("access_token")

    @classmethod
    def __registryRequest(cls, url: str, method: str = "GET", accept: Optional[str] = None) -> Optional[Response]:
        """Send a request to the container registry, handling the bearer token authentication."""
        if ParametersManager().offline_mode:
            return None
        headers: Dict[str, str] = {}
        if accept:
            headers["Accept"] = accept
        token = cls.__registry_token
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = cls.__runRequest(url, "Container registry", headers=headers, method=method)
        if response is not None and response.status_code == 401:
            with cls.__registry_lock:
                # Another thread may have already refreshed the token
                if cls.__registry_token is None or cls.__registry_token == token:
                    cls.__registry_token = cls.__authenticate(response.headers.get("www-authenticate", ""))
                token = cls.__registry_token
            if token:
                headers["Authorization"] = f"Bearer {token}"
                response = cls.__runRequest(url, "Container registry", headers=headers, method=method)
        return response

    @classmethod
    def __logRegistryUnavailable(cls, status_code: int) -> None:
        """Log (once) that the registry cannot be queried. The image status will be unknown."""
        if cls.__registry_unreachable_logged:
            return
        cls.__registry_unreachable_logged = True
        if status_code in (401, 403, 404):
            logger.warning(f"Unable to list Mandalore images from [green]{ConstantConfig.IMAGE_NAME}[/green] (HTTP {status_code}): "
                           f"the image may not be published yet, or the package is private. "
                           f"For a private package, authenticate first with: [orange3]docker login {ConstantConfig.DOCKER_REGISTRY}[/orange3]")
        else:
            logger.warning(f"The container registry {ConstantConfig.DOCKER_REGISTRY} returned an unexpected response (HTTP {status_code}).")

    @classmethod
    def listRegistryTags(cls) -> Optional[List[str]]:
        """List every tag of the Mandalore image repository. Return None if the registry cannot be queried."""
        if ParametersManager().offline_mode:
            return None
        tags: List[str] = []
        url: Optional[str] = cls.__registryUrl("tags/list?n=1000")
        max_pages = 20
        while url is not None and max_pages > 0:
            max_pages -= 1
            response = cls.__registryRequest(url, accept="application/json")
            if response is None:
                return None
            if response.status_code != 200:
                cls.__logRegistryUnavailable(response.status_code)
                return None
            try:
                tags += response.json().get("tags") or []
            except ValueError:
                logger.debug("Invalid JSON received from the registry tags list")
                return None
            # Handle pagination (RFC5988 Link header)
            url = None
            next_link = response.links.get("next", {}).get("url")
            if next_link:
                url = urljoin(f"https://{ConstantConfig.DOCKER_REGISTRY}", next_link)
        return tags

    @classmethod
    def __getManifest(cls, reference: str, accept: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Fetch a manifest (by tag or digest). Return the parsed manifest and its digest."""
        response = cls.__registryRequest(cls.__registryUrl(f"manifests/{reference}"), accept=accept or cls.__ACCEPT_MANIFESTS)
        if response is None or response.status_code != 200:
            if response is not None:
                logger.debug(f"Unable to fetch manifest '{reference}' from the registry (HTTP {response.status_code})")
            return None, None
        digest = response.headers.get("docker-content-digest")
        if not digest:
            digest = "sha256:" + hashlib.sha256(response.content).hexdigest()
        try:
            manifest = json.loads(response.content.decode("utf-8"))
        except ValueError:
            return None, digest
        if not manifest.get("mediaType"):
            # mediaType is optional in OCI manifests, deduce it from the response header
            manifest["mediaType"] = response.headers.get("content-type", "").split(";")[0]
        return manifest, digest

    @classmethod
    def __getConfigBlob(cls, config_digest: str) -> Optional[Dict[str, Any]]:
        response = cls.__registryRequest(cls.__registryUrl(f"blobs/{config_digest}"), accept="application/json")
        if response is None or response.status_code != 200:
            return None
        try:
            return json.loads(response.content.decode("utf-8"))
        except ValueError:
            return None

    @staticmethod
    def __isRealImage(entry: Dict[str, Any]) -> bool:
        """Filter out non-image entries of an image index (e.g. buildx attestation manifests)."""
        platform = entry.get("platform", {})
        if platform.get("os", "linux") == "unknown" or platform.get("architecture", "") == "unknown":
            return False
        if entry.get("annotations", {}).get("vnd.docker.reference.type") == "attestation-manifest":
            return False
        return True

    @staticmethod
    def __manifestSize(manifest: Dict[str, Any]) -> int:
        """Compressed size of an image (sum of its layers)"""
        return sum(int(layer.get("size", 0)) for layer in manifest.get("layers", [])) + int(manifest.get("config", {}).get("size", 0))

    @classmethod
    def getRemoteImageData(cls, tag: str) -> Optional[Dict[str, Any]]:
        """Collect the metadata of a remote image tag: {name, digest, images: [{architecture, variant, digest, size}]}"""
        manifest, digest = cls.__getManifest(tag)
        if manifest is None or digest is None:
            return None
        images: List[Dict[str, Any]] = []
        media_type = manifest.get("mediaType")
        if media_type in cls.MEDIA_INDEX_TYPES:
            for entry in manifest.get("manifests", []):
                if not cls.__isRealImage(entry):
                    continue
                platform = entry.get("platform", {})
                sub_manifest, _ = cls.__getManifest(entry.get("digest", ""), accept=entry.get("mediaType"))
                images.append({"architecture": platform.get("architecture", "amd64"),
                               "variant": platform.get("variant"),
                               "os": platform.get("os", "linux"),
                               "digest": entry.get("digest"),
                               "size": cls.__manifestSize(sub_manifest) if sub_manifest else 0})
        elif media_type in cls.MEDIA_IMAGE_TYPES:
            config = cls.__getConfigBlob(manifest.get("config", {}).get("digest", "")) or {}
            images.append({"architecture": config.get("architecture", "amd64"),
                           "variant": config.get("variant"),
                           "os": config.get("os", "linux"),
                           "digest": digest,
                           "size": cls.__manifestSize(manifest)})
        else:
            logger.debug(f"Unsupported manifest media type for tag '{tag}': {media_type}")
            return None
        return {"name": tag, "digest": digest, "images": images}

    @classmethod
    def getMetaDigestId(cls, tag: str) -> Optional[str]:
        """Get the digest id of a specific image tag from the registry (multi-arch index digest when available)"""
        if ParametersManager().offline_mode:
            return None
        response = cls.__registryRequest(cls.__registryUrl(f"manifests/{tag}"), method="HEAD", accept=cls.__ACCEPT_MANIFESTS)
        if response is None or response.status_code != 200:
            return None
        return response.headers.get("docker-content-digest") or response.headers.get("etag")

    @classmethod
    def getRemoteVersion(cls, tag: str) -> Optional[str]:
        """Get image version (org.mandalore.version label) of a specific image tag from the registry."""
        if ParametersManager().offline_mode:
            return None
        manifest, _ = cls.__getManifest(tag)
        if manifest is None:
            return None
        if manifest.get("mediaType") in cls.MEDIA_INDEX_TYPES:
            # Every arch share the same labels: use the first real image
            entries = [e for e in manifest.get("manifests", []) if cls.__isRealImage(e)]
            if len(entries) == 0:
                return None
            manifest, _ = cls.__getManifest(entries[0].get("digest", ""), accept=entries[0].get("mediaType"))
            if manifest is None:
                return None
        config_digest = manifest.get("config", {}).get("digest")
        if not config_digest:
            return None
        config = cls.__getConfigBlob(config_digest)
        if config is None:
            return None
        return config.get("config", {}).get("Labels", {}).get("org.mandalore.version")

    # ---------------------------------------------------------------------------------------------------------------
    # Generic
    # ---------------------------------------------------------------------------------------------------------------

    @classmethod
    def runJsonRequest(cls, url: str, service_name: str, headers: Optional[Dict] = None, method: str = "GET", data: Any = None, retry_count: int = 2) -> Any:
        """Fetch a web page from url and parse the result as json."""
        if ParametersManager().offline_mode:
            return None
        response = cls.__runRequest(url, service_name, headers, method, data, retry_count)
        if response is not None and response.status_code == 200:
            return json.loads(response.content.decode("utf-8"))
        elif response is not None:
            logger.error(f"Error during web request to {service_name} ({response.status_code}) on {url}")
        return None

    @staticmethod
    def __getProxies() -> Optional[Dict[str, str]]:
        proxies = {}
        http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
        if http_proxy:
            proxies['http'] = http_proxy
        https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
        if https_proxy:
            proxies['https'] = https_proxy
        no_proxy = os.environ.get('NO_PROXY') or os.environ.get('no_proxy')
        if no_proxy:
            proxies['no_proxy'] = no_proxy
        return proxies if len(proxies) > 0 else None

    @classmethod
    def __runRequest(cls, url: str, service_name: str, headers: Optional[Dict] = None, method: str = "GET", data: Any = None,
                     retry_count: int = 2, params: Optional[Dict[str, str]] = None, auth: Optional[Tuple[str, str]] = None) -> Optional[Response]:
        """Fetch a web page from url and catch / log different use cases.
        Url: web page to quest
        Service_name: service display name for logging purpose
        Retry_count: number of retry allowed."""
        # In case of API timeout, allow retrying 1 more time
        for i in range(retry_count):
            if ParametersManager().offline_mode:
                return None
            try:
                logger.debug(f"Fetching information from {url}")
                return requests.request(method=method, url=url, timeout=(10, 20), verify=ParametersManager().verify, headers=headers,
                                        data=data, params=params, auth=auth, proxies=cls.__getProxies())
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout):
                logger.verbose(f"{service_name} time out, retrying ({i + 1}/{retry_count}) ...")
                time.sleep(1)
            except requests.exceptions.HTTPError as e:
                if e.response is not None:
                    logger.error(f"Response error: {e.response.content.decode('utf-8', errors='replace')}")
                else:
                    logger.error(f"Response error: {e}")
                return None
            except requests.exceptions.ConnectionError as err:
                logger.debug(f"Error: {err}")
                error_re = re.search(r"\[Errno [-\d]+]\s?([^']*)('\))+\)*", str(err))
                error_msg = ""
                if error_re:
                    error_msg = f" ({error_re.group(1)})"
                logger.error(f"Connection Error: you probably have no internet.{error_msg}")
                # Switch to offline mode
                ParametersManager().offline_mode = True
                return None
            except requests.exceptions.RequestException as err:
                logger.error(f"Unknown connection error: {err}")
                return None
        logger.error(f"[green]{service_name}[/green] request has [red]timed out[/red]. Do you have a slow internet connection, or is the remote service slow/down? Retry later.")
        return None
