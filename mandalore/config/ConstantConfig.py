from pathlib import Path

__version__ = "4.3.12"


class ConstantConfig:
    """Constant parameters information"""
    # Mandalore Version
    version: str = __version__

    # Mandalore documentation link
    documentation: str = "https://github.com/ghecko/mandalore-docs/wiki"
    # OS Dir full root path of mandalore project
    src_root_path_obj: Path = Path(__file__).parent.parent.parent.resolve()
    # Path of the entrypoint.sh
    entrypoint_context_path_obj: Path = src_root_path_obj / "mandalore/utils/imgsync/entrypoint.sh"
    # Path of the spawn.sh
    spawn_context_path_obj: Path = src_root_path_obj / "mandalore/utils/imgsync/spawn.sh"
    # Mandalore config directory
    mandalore_config_path: Path = Path().home() / ".mandalore"
    # Docker Desktop for mac config file
    docker_desktop_mac_config_path = Path().home() / "Library/Group Containers/group.com.docker"
    docker_desktop_windows_config_short_path = "AppData/Roaming/Docker"
    docker_desktop_windows_config_path = Path().home() / docker_desktop_windows_config_short_path
    # Install mode, check if Mandalore has been git cloned or installed using pip package
    git_source_installation: bool = (src_root_path_obj / '.git').is_dir()
    pip_installed: bool = src_root_path_obj.name == "site-packages"
    pipx_installed: bool = "/pipx/venvs/" in src_root_path_obj.as_posix()
    # Dockerhub Mandalore images repository
    DOCKER_HUB: str = "hub.docker.com"  # Don't handle docker login operations
    DOCKER_REGISTRY: str = "registry-1.docker.io"  # Don't handle docker login operations
    IMAGE_NAME: str = "lksec/mandalore"
    GITHUB_REPO: str = "lksec/mandalore"
    # Docker volume names (no docker volume used at this moment)
    # Resources repository
    MANDALORE_IMAGES_REPO: str = "https://github.com/ghecko/mandalore-images.git"
    MANDALORE_RESOURCES_REPO: str = "https://github.com/ghecko/mandalore-resources.git"
