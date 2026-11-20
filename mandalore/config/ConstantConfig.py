import os
import sys
from pathlib import Path
from typing import Optional, Tuple

__version__ = "4.3.12"


def _get_invoking_user_home() -> Path:
    """Return the home directory of the user who launched Mandalore.
    When Mandalore is run with sudo, Path.home() returns root's home: resolve the real user's home instead."""
    if sys.platform != "win32" and os.geteuid() == 0:
        sudo_uid = os.getenv("SUDO_UID")
        if sudo_uid is not None and sudo_uid.isdigit() and int(sudo_uid) != 0:
            try:
                import pwd
                return Path(pwd.getpwuid(int(sudo_uid)).pw_dir)
            except (KeyError, ImportError):
                pass
    return Path.home()


def _get_config_path(user_home: Path) -> Tuple[Path, Optional[Path]]:
    """Select the Mandalore config directory.
    Return the selected path and, when a legacy directory in root's home is kept, that legacy path (to warn the user)."""
    user_dir = user_home / ".mandalore"
    root_dir = Path.home() / ".mandalore"
    if user_dir != root_dir and not user_dir.exists() and root_dir.is_dir():
        # Previous versions stored data in /root/.mandalore when launched with sudo.
        # Existing containers mount workspaces from this directory: keep using it until the user migrates it.
        return root_dir, root_dir
    return user_dir, None


class ConstantConfig:
    """Constant parameters information"""
    # Mandalore Version
    version: str = __version__

    # Mandalore GitHub owner / project links
    GITHUB_OWNER: str = "ghecko"
    GITHUB_REPO: str = f"{GITHUB_OWNER}/mandalore"
    GITHUB_URL: str = f"https://github.com/{GITHUB_REPO}"
    ISSUES_URL: str = f"{GITHUB_URL}/issues"
    # Mandalore documentation link
    documentation: str = f"https://{GITHUB_OWNER}.github.io/mandalore-docs/"
    # OS Dir full root path of mandalore project
    src_root_path_obj: Path = Path(__file__).parent.parent.parent.resolve()
    # Path of the entrypoint.sh
    entrypoint_context_path_obj: Path = src_root_path_obj / "mandalore/utils/imgsync/entrypoint.sh"
    # Path of the spawn.sh
    spawn_context_path_obj: Path = src_root_path_obj / "mandalore/utils/imgsync/spawn.sh"
    # Home of the user running Mandalore (the real user when launched with sudo)
    user_home: Path = _get_invoking_user_home()
    # Mandalore config directory (legacy_config_path is set when a legacy /root/.mandalore directory is still in use)
    mandalore_config_path, legacy_config_path = _get_config_path(user_home)
    # Docker Desktop for mac config file
    docker_desktop_mac_config_path = user_home / "Library/Group Containers/group.com.docker"
    docker_desktop_windows_config_short_path = "AppData/Roaming/Docker"
    docker_desktop_windows_config_path = user_home / docker_desktop_windows_config_short_path
    # Install mode, check if Mandalore has been git cloned or installed using pip package
    git_source_installation: bool = (src_root_path_obj / '.git').is_dir()
    pip_installed: bool = src_root_path_obj.name == "site-packages"
    pipx_installed: bool = "/pipx/venvs/" in src_root_path_obj.as_posix()
    # Container registry hosting Mandalore images (any OCI distribution compliant registry)
    DOCKER_REGISTRY: str = "ghcr.io"
    # Image repository path inside the registry (used for registry API paths and token scopes)
    IMAGE_REPOSITORY: str = f"{GITHUB_OWNER}/mandalore"
    # Full docker image name (used for docker pull / tag / local image lookups)
    IMAGE_NAME: str = f"{DOCKER_REGISTRY}/{IMAGE_REPOSITORY}"
    # Resources repository
    MANDALORE_IMAGES_REPO: str = f"https://github.com/{GITHUB_OWNER}/mandalore-images.git"
    MANDALORE_RESOURCES_REPO: str = f"https://github.com/{GITHUB_OWNER}/mandalore-resources.git"
