import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from time import sleep
from typing import Dict, List, Optional, Tuple, Union, cast

import docker
import requests.exceptions
from docker import DockerClient
from docker.errors import APIError, DockerException, NotFound, ImageNotFound
from docker.models.images import Image
from docker.models.volumes import Volume
from requests import ReadTimeout
from rich.status import Status

from mandalore.config.ConstantConfig import ConstantConfig
from mandalore.config.DataCache import DataCache
from mandalore.config.EnvInfo import EnvInfo
from mandalore.config.UserConfig import UserConfig
from mandalore.console.TUI import MandaloreTUI
from mandalore.console.cli.ParametersManager import ParametersManager
from mandalore.exceptions.MandaloreExceptions import ObjectNotFound
from mandalore.model.MandaloreContainer import MandaloreContainer
from mandalore.model.MandaloreContainerTemplate import MandaloreContainerTemplate
from mandalore.model.MandaloreImage import MandaloreImage
from mandalore.model.MetaImages import MetaImages
from mandalore.utils.ExeLog import logger, console, ExeLog
from mandalore.utils.MetaSingleton import MetaSingleton
from mandalore.utils.WebUtils import WebUtils


# SDK Documentation : https://docker-py.readthedocs.io/en/stable/index.html


class DockerUtils(metaclass=MetaSingleton):

    def __init__(self) -> None:
        """Utility class between mandalore and the Docker SDK"""
        try:
            # Connect Docker SDK to the local docker instance.
            # Docker connection setting is loaded from the user environment variables.
            self.__client: DockerClient = docker.from_env()
            # Check if the docker daemon is serving linux container
            self.__daemon_info = self.__client.info()
            if self.__daemon_info.get("OSType", "linux").lower() != "linux":
                logger.critical(
                    f"Docker daemon is not serving linux container ! Docker OS Type is: {self.__daemon_info.get('OSType', 'linux')}")
            EnvInfo.initData(self.__daemon_info)
        except DockerException as err:
            if 'ConnectionRefusedError' in str(err):
                logger.critical(f"Unable to connect to docker (from env config). Is docker running on your machine? Exiting.{os.linesep}"
                                f"    Check documentation for help: {ConstantConfig.documentation}")
            elif 'FileNotFoundError' in str(err):
                logger.critical(f"Unable to connect to docker. Is docker installed on your machine? Exiting.{os.linesep}"
                                f"    Check documentation for help: {ConstantConfig.documentation}")
            elif 'PermissionError' in str(err):
                logger.critical(f"Docker is installed on your host but you don't have the permission to interact with it. Exiting.{os.linesep}"
                                f"    Check documentation for help: {ConstantConfig.documentation}")
            else:
                logger.error(err)
                logger.critical(
                    "Unable to connect to docker (from env config). Is docker operational and accessible? on your machine? "
                    "Exiting.")
        except (ReadTimeout, requests.exceptions.ConnectionError):
            logger.critical("Docker daemon seems busy, Mandalore receives timeout response. Try again later.")
        self.__images: Optional[List[MandaloreImage]] = None
        self.__containers: Optional[List[MandaloreContainer]] = None

    def clearCache(self) -> None:
        """Remove class's images and containers data cache
        Only needed if the list has to be updated in the same runtime at a later moment"""
        self.__containers = None
        self.__images = None

    def getDockerInfo(self) -> dict:
        """Fetch info from docker daemon"""
        return self.__daemon_info

    # # # Container Section # # #

    def listContainers(self) -> List[MandaloreContainer]:
        """List available docker containers.
        Return a list of MandaloreContainer"""
        if self.__containers is None:
            self.__containers = []
            try:
                docker_containers = self.__client.containers.list(all=True, filters={"name": "mandalore-"})
            except APIError as err:
                logger.debug(err)
                logger.critical(err.explanation)
                # Not reachable, critical logging will exit
                return  # type: ignore
            except ReadTimeout:
                logger.critical("Received a timeout error, Docker is busy... Unable to list containers, retry later.")
                return  # type: ignore
            for container in docker_containers:
                self.__containers.append(MandaloreContainer(container))
        return self.__containers

    def createContainer(self, model: MandaloreContainerTemplate, temporary: bool = False) -> MandaloreContainer:
        """Create a Mandalore container from an MandaloreContainerTemplate configuration.
        Return an MandaloreContainer if the creation was successful."""
        logger.info("Creating new mandalore container")
        model.prepare()
        logger.debug(model)
        # Preload docker volume before container creation
        for volume in model.config.getVolumes():
            if volume.get('Type', '?') == "volume":
                docker_volume = self.__loadDockerVolume(volume_path=volume['Source'], volume_name=volume['Target'])
                if docker_volume is None:
                    logger.warning(f"Error while creating docker volume '{volume['Target']}'")
        entrypoint, command = model.config.getEntrypointCommand()
        logger.debug(f"Entrypoint: {entrypoint}")
        logger.debug(f"Cmd: {command}")
        # The 'create' function must be called to create a container without starting it
        # in order to hot patch the entrypoint.sh with wrapper features (the container will be started after postCreateSetup)
        docker_create_function = self.__client.containers.create
        docker_args = {"image": model.image.getDockerRef(),
                       "entrypoint": entrypoint,
                       "command": command,
                       "detach": True,
                       "name": model.container_name,
                       "hostname": model.config.hostname,
                       "extra_hosts": model.config.getExtraHost(),
                       "devices": model.config.getDevices(),
                       "environment": model.config.getEnvs(),
                       "labels": model.config.getLabels(),
                       "network_mode": model.config.getNetworkMode(),
                       "ports": model.config.getPorts(),
                       "privileged": model.config.getPrivileged(),
                       "cap_add": model.config.getCapabilities(),
                       "sysctls": model.config.getSysctls(),
                       "shm_size": model.config.shm_size,
                       "stdin_open": model.config.interactive,
                       "tty": model.config.tty,
                       "mounts": model.config.getVolumes(),
                       "userns_mode": "host",
                       "working_dir": model.config.getWorkingDir()}
        if temporary:
            # Only the 'run' function support the "remove" parameter
            docker_create_function = self.__client.containers.run
            docker_args["remove"] = temporary
            docker_args["auto_remove"] = temporary
        try:
            container = docker_create_function(**docker_args)
        except APIError as err:
            message = err.explanation.decode('utf-8').replace('[', '\\[') if type(err.explanation) is bytes else err.explanation
            if message is not None:
                message = message.replace('[', '\\[')
                logger.error(f"Docker error received: {message}")
            logger.debug(err)
            model.rollback()
            try:
                container = self.__client.containers.list(all=True, filters={"name": model.container_name})
                if container is not None and len(container) > 0:
                    for c in container:
                        if c.name == model.container_name:  # Search for exact match
                            container[0].remove()
                            logger.debug("Container removed")
            except Exception:
                pass
            logger.critical("Error while creating mandalore container. Exiting.")
            # Not reachable, critical logging will exit
            return  # type: ignore
        if container is not None:
            logger.success("Mandalore container successfully created!")
        else:
            logger.critical("Unknown error while creating mandalore container. Exiting.")
            # Not reachable, critical logging will exit
            return  # type: ignore
        return MandaloreContainer(container, model)

    def cloneContainer(self, source: MandaloreContainer, image: MandaloreImage, container_name: str) -> MandaloreContainer:
        """Create a new container from another Mandalore image, with the exact same configuration as the source container
        (host config, mounts, network, devices, user environment variables, labels and command).
        Variables and labels inherited from the previous image are not copied so the new image defaults apply.
        Raise APIError if docker refuses the creation."""
        source_container = source.getDockerObject()
        source_container.reload()
        config: Dict = source_container.attrs.get("Config") or {}
        host_config: Dict = dict(source_container.attrs.get("HostConfig") or {})
        previous_image_config: Dict = {}
        try:
            previous_image_config = source_container.image.attrs.get("Config") or {}
        except (ImageNotFound, NotFound):
            logger.warning("The previous image of this container no longer exists, every environment variable is kept as is.")
        image_envs = set(previous_image_config.get("Env") or [])
        envs = [env for env in config.get("Env") or [] if env not in image_envs]
        image_labels: Dict = previous_image_config.get("Labels") or {}
        labels = {k: v for k, v in (config.get("Labels") or {}).items() if image_labels.get(k) != v}
        entrypoint = config.get("Entrypoint") if config.get("Entrypoint") != previous_image_config.get("Entrypoint") else None
        command = config.get("Cmd") if config.get("Cmd") != previous_image_config.get("Cmd") else None

        # The wrapper may have been moved / reinstalled since the container creation: refresh the spawn.sh mount source
        spawn_path = str(ConstantConfig.spawn_context_path_obj)
        spawn_target = "/.mandalore/spawn.sh"
        for mount in host_config.get("Mounts") or []:
            if mount.get("Target") == spawn_target:
                mount["Source"] = spawn_path
        if host_config.get("Binds"):
            binds = []
            for bind in host_config["Binds"]:
                if f":{spawn_target}" in bind:
                    bind = spawn_path + bind[bind.index(f":{spawn_target}"):]
                binds.append(bind)
            host_config["Binds"] = binds

        # Exposed ports are required for the port bindings
        ports: List[Union[int, Tuple[int, str]]] = []
        for port_key in (host_config.get("PortBindings") or {}).keys():
            port, _, proto = str(port_key).partition('/')
            if port.isdigit():
                ports.append((int(port), proto or "tcp"))

        logger.debug(f"Cloning container {source_container.name} as {container_name} using image {image.getDockerRef()}")
        response = self.__client.api.create_container(image=image.getDockerRef(),
                                                      name=container_name,
                                                      hostname=config.get("Hostname"),
                                                      domainname=config.get("Domainname") or None,
                                                      user=config.get("User") or None,
                                                      environment=envs,
                                                      labels=labels,
                                                      entrypoint=entrypoint,
                                                      command=command,
                                                      working_dir=config.get("WorkingDir") or None,
                                                      tty=config.get("Tty", True),
                                                      stdin_open=config.get("OpenStdin", True),
                                                      detach=True,
                                                      ports=ports if len(ports) > 0 else None,
                                                      host_config=host_config)
        self.clearCache()
        return MandaloreContainer(self.__client.containers.get(response["Id"]))

    def getContainer(self, tag: str) -> MandaloreContainer:
        """Get an MandaloreContainer from tag name."""
        try:
            # Fetch potential container match from DockerSDK
            container = self.__client.containers.list(all=True, filters={"name": f"mandalore-{tag}"})
        except APIError as err:
            logger.debug(err)
            logger.critical(err.explanation)
            # Not reachable, critical logging will exit
            return  # type: ignore
        # Check if there is at least 1 result. If no container was found, raise ObjectNotFound.
        if container is None or len(container) == 0:
            # Handle case-insensitive OS
            if EnvInfo.isWindowsHost() or EnvInfo.isMacHost():
                # First try to fetch the container as-is (for retroactive support with old container with uppercase characters)
                # If the user's input didn't match any container, try to force the name in lowercase if not already tried
                lowered_tag = tag.lower()
                if lowered_tag != tag:
                    return self.getContainer(lowered_tag)
            raise ObjectNotFound
        # Filter results with exact name matching
        for c in container:
            if c.name == f"mandalore-{tag}":
                # When the right container is found, select it and stop the search
                return MandaloreContainer(c)
        # When there is some close container's name,
        # docker may return some results but none of them correspond to the request.
        # In this case, ObjectNotFound is raised
        raise ObjectNotFound

    # # # Volumes Section # # #

    def __loadDockerVolume(self, volume_path: str, volume_name: str) -> Volume:
        """Load or create a docker volume for mandalore containers
        (must be created before the container, SDK limitation)
        Return the docker volume object"""
        try:
            os.makedirs(volume_path, exist_ok=True)
        except PermissionError:
            logger.error("Unable to create the volume folder on the filesystem locally.")
            logger.critical(f"Insufficient permission to create the folder: {volume_path}")
        try:
            # Check if volume already exist
            volume = self.__client.volumes.get(volume_name)
            path = volume.attrs.get('Options', {}).get('device', '')
            if path != volume_path:
                try:
                    self.__client.api.remove_volume(name=volume_name)
                    raise NotFound('Volume must be reloaded')
                except APIError as e:
                    if e.status_code == 409:
                        logger.warning("The path of the volume specified by the user is not the same as in the existing docker volume. "
                                       "The user path will be [red]ignored[/red] as long as the docker volume already exists.")
                        logger.verbose("The volume is already used by some container and cannot be automatically removed.")
                        logger.debug(e.explanation)
                    else:
                        raise NotFound('Volume must be reloaded')
                except ReadTimeout:
                    logger.error(f"Received a timeout error, Docker is busy... Volume {volume_name} cannot be automatically removed. Please, retry later the following command:{os.linesep}"
                                 f"    [orange3]docker volume rm {volume_name}[/orange3]")
        except NotFound:
            try:
                # Creating a docker volume bind to a host path
                # Docker volume are more easily shared by container
                # Docker volume can load data from container image on host's folder creation
                volume = self.__client.volumes.create(volume_name, driver="local",
                                                      driver_opts={'o': 'bind',
                                                                   'device': volume_path,
                                                                   'type': 'none'})
            except APIError as err:
                logger.error(f"Error while creating docker volume '{volume_name}'.")
                logger.debug(err)
                logger.critical(err.explanation)
                raise RuntimeError
            except ReadTimeout:
                logger.critical(f"Received a timeout error, Docker is busy... Volume {volume_name} cannot be created.")
                raise RuntimeError
        except APIError as err:
            logger.critical(f"Unexpected error by Docker SDK : {err}")
            raise RuntimeError
        except ReadTimeout:
            logger.critical("Received a timeout error, Docker is busy... Unable to enumerate volume, retry later.")
            raise RuntimeError
        return volume

    # # # Image Section # # #

    def listImages(self, include_version_tag: bool = False, include_locked: bool = False) -> List[MandaloreImage]:
        """List available docker images.
        Return a list of MandaloreImage"""
        if self.__images is None:
            logger.verbose("Loading every Mandalore images")
            with console.status(f"Loading Mandalore images from registry", spinner_style="blue") as s:
                remote_images = self.__listRemoteImages(s)
                logger.verbose("Retrieve [green]local[/green] Mandalore images")
                s.update(status=f"Retrieving [green]local[/green] Mandalore images")
                local_images = self.__listLocalImages()
                self.__images = MandaloreImage.mergeImages(remote_images, local_images, s)
            logger.verbose("Images fetched")
        result = self.__images
        assert result is not None
        # Caching latest images
        DataCache().update_image_cache([img for img in result if not img.isVersionSpecific()])
        if not (logger.isEnabledFor(ExeLog.VERBOSE) or include_locked):
            # ToBeRemoved images are only shown in verbose mode
            result = [i for i in result if not i.isLocked()]
        if not include_version_tag:
            # Version specific images not installed are excluded by default
            result = [img for img in result if not img.isVersionSpecific() or img.isInstall()]
        return result

    def listInstalledImages(self) -> List[MandaloreImage]:
        """List installed docker images.
        Return a list of MandaloreImage"""
        images = self.listImages()
        # Selecting only installed image
        return [img for img in images if img.isInstall()]

    def getImage(self, tag: str) -> MandaloreImage:
        """Get an MandaloreImage from tag name."""
        # Fetch every images available
        images = self.listImages(include_version_tag=True, include_locked=True)
        match: Optional[MandaloreImage] = None
        # Find a match
        for i in images:
            if i.getName() == tag:
                # If there is a locked image keep it as default
                if i.isLocked():
                    match = i
                else:
                    # Return the first non-outdated image
                    return i
        # If there is any match without lock (outdated) status, return the last outdated image found.
        if match is not None:
            return match
        # If there is no match at all, raise ObjectNotFound to handle the error
        raise ObjectNotFound

    def getInstalledImage(self, tag: str) -> MandaloreImage:
        """Get an already installed MandaloreImage from tag name."""
        try:
            if self.__images is None:
                try:
                    docker_local_image = self.__client.images.get(f"{ConstantConfig.IMAGE_NAME}:{tag}")
                    # DockerSDK image get is an exact matching, no need to add more check
                except APIError as err:
                    if err.status_code == 404:
                        # try to find it in recovery mode
                        logger.verbose("Unable to find your image. Trying to find in recovery mode.")
                        recovery_images = self.__findLocalRecoveryImages(include_untag=True)
                        match = []
                        for img in recovery_images:
                            if MandaloreImage.parseAliasTagName(img) == tag:
                                match.append(MandaloreImage(docker_image=img))
                        if len(match) == 1:
                            return match[0]
                        elif len(match) > 1:
                            return cast(MandaloreImage, MandaloreTUI.selectFromTable(match))
                        raise ObjectNotFound
                    else:
                        logger.critical(f"Error on image loading: {err}")
                        return  # type: ignore
                except ReadTimeout:
                    logger.critical("Received a timeout error, Docker is busy... Unable to list images, retry later.")
                    return  # type: ignore
                return MandaloreImage(docker_image=docker_local_image).autoLoad()
            else:
                for img in self.__images:
                    if img.getName() == tag:
                        if not img.isInstall() or not img.isUpToDate():
                            # Refresh local image status in case of installation/upgrade operations
                            self.__findImageMatch(img)
                        return img
        except ObjectNotFound:
            logger.critical(f"The desired image is not installed or do not exist ({ConstantConfig.IMAGE_NAME}:{tag}). Exiting.")
        return  # type: ignore

    def __listLocalImages(self, tag: Optional[str] = None) -> List[Image]:
        """List local docker images already installed.
        Return a list of docker images objects"""
        logger.debug("Fetching local image tags, digests (and other attributes)")
        try:
            image_name = ConstantConfig.IMAGE_NAME + ("" if tag is None else f":{tag}")
            images = self.__client.images.list(image_name, filters={"dangling": False})
        except APIError as err:
            logger.debug(err)
            logger.critical(err.explanation)
            # Not reachable, critical logging will exit
            return  # type: ignore
        except ReadTimeout:
            logger.critical("Received a timeout error, Docker is busy... Unable to list local images, retry later.")
            return  # type: ignore
        # Filter out image non-related to the right repository
        result = []
        ids = set()
        for img in images:
            # len tags = 0 handle mandalore <none> images (nightly image lost their tag after update)
            if len((img.attrs.get('RepoTags') or [])) == 0 or \
                    ConstantConfig.IMAGE_NAME in [repo_tag.rsplit(':', 1)[0] for repo_tag in (img.attrs.get("RepoTags") or [])]:
                result.append(img)
                ids.add(img.id)

        # Try to find lost Mandalore images
        recovery_images = self.__findLocalRecoveryImages()
        for img in recovery_images:
            # Docker can keep track of 2 images maximum with RepoTag or RepoDigests, after it's hard to track origin without labels, so this recovery option is "best effort"
            if img.id in ids:
                # Skip image from other repo and image already found
                logger.debug(f"Duplicate found in recovery mode! {img}")
                continue
            else:
                result.append(img)
                ids.add(img.id)
        return result

    def __findLocalRecoveryImages(self, include_untag: bool = False) -> List[Image]:
        """This method try to recovery untagged docker images.
        Set include_untag option to recover images with a valid RepoDigest (no not dangling) but without tag."""
        try:
            # Try to find lost Mandalore images
            recovery_images = self.__client.images.list(filters={"dangling": True})
            if include_untag:
                recovery_images += self.__client.images.list(ConstantConfig.IMAGE_NAME, filters={"dangling": False})
        except APIError as err:
            logger.debug(f"Error occurred in recovery mode: {err}")
            return []
        except ReadTimeout:
            logger.critical("Received a timeout error, Docker is busy... Unable to enumerate lost images, retry later.")
            return  # type: ignore
        result = []
        id_list = set()
        for img in recovery_images:
            # Docker can keep track of 2 images maximum with RepoTag or RepoDigests, after it's hard to track origin without labels, so this recovery option is "best effort"
            repo_tags = img.attrs.get('RepoTags')
            repo_digest = img.attrs.get('RepoDigests')
            if repo_tags is not None and len(repo_tags) > 0 or (not include_untag and repo_digest is not None and len(repo_digest) > 0) or img.id in id_list:
                # Skip image from other repo and image already found
                continue
            if img.labels.get('org.mandalore.app', '') == "Mandalore":
                result.append(img)
                id_list.add(img.id)
        return result

    @staticmethod
    def __selectRemoteTags(tags: List[str]) -> List[str]:
        """Select the registry tags worth inspecting: every 'latest' tag (no version, e.g. full, light, nightly)
        and the most recent version-specific tag of each image (e.g. full-3.1.2), used to resolve the latest version number.
        In verbose mode, the 3 most recent versions of each image are inspected."""
        latest_tags: List[str] = []
        versions: Dict[str, List[str]] = {}
        for tag in tags:
            if tag.startswith("sha256-"):
                # Signatures / attestations stored as tags
                continue
            if tag.startswith("staging-"):
                # Per-arch images waiting to be assembled into a multi-arch image (see mandalore-images/publish.sh)
                continue
            if MetaImages.tagNameParsing(tag):
                versions.setdefault(tag.split('-')[0], []).append(tag)
            else:
                latest_tags.append(tag)
        keep = 3 if logger.isEnabledFor(ExeLog.VERBOSE) else 1

        def version_key(tag_name: str) -> Tuple[int, ...]:
            return tuple(int(x) for x in re.findall(r"\d+", MetaImages.tagNameParsing(tag_name)))

        result = list(latest_tags)
        for version_tags in versions.values():
            result += sorted(version_tags, key=version_key, reverse=True)[:keep]
        return result

    @classmethod
    def __listRemoteImages(cls, status: Status) -> List[MetaImages]:
        """List remote images available on the registry.
        Return a list of MetaImages"""
        logger.debug(f"Fetching remote image tags, digests and sizes from {ConstantConfig.IMAGE_NAME}")
        if logger.isEnabledFor(ExeLog.VERBOSE):
            status.update(status=f"Fetching registry information from [green]{ConstantConfig.IMAGE_NAME}[/green]")
        tags = WebUtils.listRegistryTags()
        if tags is None:
            logger.verbose("Skipping online queries.")
            return []
        selected_tags = cls.__selectRemoteTags(tags)
        logger.debug(f"Inspecting remote tags: {', '.join(selected_tags)}")
        remote_results: List[MetaImages] = []
        # Each tag requires several registry requests: inspect them concurrently
        with ThreadPoolExecutor(max_workers=8) as executor:
            for data in executor.map(WebUtils.getRemoteImageData, selected_tags):
                if data is not None and len(data.get("images", [])) > 0:
                    remote_results.append(MetaImages(data))
        return remote_results

    def __findImageMatch(self, remote_image: MandaloreImage) -> None:
        """From a Remote MandaloreImage, try to find a local match (using Remote DigestID).
        This method is useful if the image repository name is also lost"""
        remote_id = remote_image.getLatestRemoteId()
        if not remote_id:
            logger.debug("Latest remote id is not available... Falling back to the current remote id.")
            remote_id = remote_image.getRemoteId()
        try:
            docker_image = self.__client.images.get(f"{ConstantConfig.IMAGE_NAME}@{remote_id}")
        except ImageNotFound:
            raise ObjectNotFound
        except ReadTimeout:
            logger.critical("Received a timeout error, Docker is busy... Unable to find a specific image, retry later.")
            raise RuntimeError
        remote_image.resetDockerImage()
        remote_image.setDockerObject(docker_image)

    def downloadImage(self, image: MandaloreImage, install_mode: bool = False) -> bool:
        """Download/pull an MandaloreImage"""
        if ParametersManager().offline_mode:
            logger.critical("It's not possible to download a docker image in offline mode ...")
            return False
        # Switch to install mode if the selected image is not already installed
        install_mode = install_mode or not image.isInstall()
        logger.info(f"{'Installing' if install_mode else 'Updating'} mandalore image : {image.getName()}")
        name = image.updateCheck()
        if name is not None:
            logger.info(f"Pulling compressed image, starting a [cyan1]~{image.getDownloadSize()}[/cyan1] download :satellite:")
            logger.info(f"Once downloaded and uncompressed, the image will take [cyan1]~{image.getRealSizeRaw()}[/cyan1] on disk :floppy_disk:")
            logger.debug(f"Downloading {ConstantConfig.IMAGE_NAME}:{name} ({image.getArch()})")
            try:
                MandaloreTUI.downloadDockerLayer(
                    self.__client.api.pull(repository=ConstantConfig.IMAGE_NAME,
                                           tag=name,
                                           stream=True,
                                           decode=True,
                                           platform="linux/" + image.getArch()))
                logger.success(f"Image successfully {'installed' if install_mode else 'updated'}")
                # Remove old image
                if not install_mode and image.isInstall() and UserConfig().auto_remove_images:
                    self.removeImage(image, upgrade_mode=not install_mode)
                return True
            except APIError as err:
                if err.status_code == 500:
                    logger.error(f"Error: {err.explanation}")
                    logger.error(f"Error while contacting docker registry. Aborting.")
                elif err.status_code == 404:
                    logger.critical(f"The image has not been found on the docker registry: {err.explanation}")
                else:
                    logger.debug(f"Error: {err}")
                    logger.critical(f"An error occurred while downloading this image: {err.explanation}")
            except ReadTimeout:
                logger.critical(f"Received a timeout error, Docker is busy... Unable to download {name} image, retry later.")
        return False

    def downloadVersionTag(self, image: MandaloreImage) -> Union[MandaloreImage, str]:
        """Pull a docker image for a specific version tag and return the corresponding MandaloreImage"""
        if ParametersManager().offline_mode:
            logger.critical("It's not possible to download a docker image in offline mode ...")
            return ""
        try:
            image = self.__client.images.pull(repository=ConstantConfig.IMAGE_NAME,
                                              tag=image.getLatestVersionName(),
                                              platform="linux/" + image.getArch())
            return MandaloreImage(docker_image=image, isUpToDate=True)
        except APIError as err:
            if err.status_code == 500:
                return f"error while contacting docker registry: {err.explanation}"
            elif err.status_code == 404:
                return f"matching tag doesn't exist: {err.explanation}"
            else:
                logger.debug(f"Error: {err}")
                return f"en unknown error occurred while downloading this image : {err.explanation}"
        except ReadTimeout:
            logger.critical(f"Received a timeout error, Docker is busy... Unable to download an image tag, retry later the following command:{os.linesep}"
                            f"    [orange3]docker pull --platform linux/{image.getArch()} {ConstantConfig.IMAGE_NAME}:{image.getLatestVersionName()}[/orange3].")
            return  # type: ignore

    def removeImage(self, image: MandaloreImage, upgrade_mode: bool = False) -> bool:
        """Remove an MandaloreImage from disk"""
        tag = image.removeCheck()
        if tag is None:  # Skip removal if image is not installed locally.
            return False
        with console.status(f"Removing {'previous ' if upgrade_mode else ''}image [green]{image.getName()}[/green]...", spinner_style="blue"):
            try:
                if not image.isVersionSpecific() and image.getInstalledVersionName() != image.getName() and not upgrade_mode:
                    # Docker can't remove multiple images at the same tag, version specific tag must be remove first
                    logger.debug(f"Removing image {image.getFullVersionName()}")
                    if not self.__remove_image(image.getFullVersionName()):
                        logger.critical(f"An error occurred while removing this image : {image.getFullVersionName()}")
                logger.debug(f"Removing image {image.getLocalId()} ({image.getFullVersionName() if upgrade_mode else image.getFullName()})")
                if self.__remove_image(image.getLocalId()):
                    logger.verbose(f"Removing {'previous ' if upgrade_mode else ''}image [green]{image.getName()}[/green]...")
                    logger.success(f"{'Previous d' if upgrade_mode else 'D'}ocker image successfully removed.")
                    return True
            except APIError as err:
                # Handle docker API error code
                logger.verbose(err.explanation)
                if err.status_code == 409:
                    if upgrade_mode:
                        logger.error(f"The '{image.getName()}' image cannot be deleted yet, "
                                     "all containers using this old image must be deleted first.")
                    else:
                        logger.error(f"The '{image.getName()}' image cannot be deleted because "
                                     f"it is currently used by a container. Aborting.")
                elif err.status_code == 404:
                    logger.error(f"This image doesn't exist locally {image.getLocalId()} ({image.getFullName()}). Aborting.")
                else:
                    logger.critical(f"An error occurred while removing this image : {err}")
        return False

    def __remove_image(self, image_name: str) -> bool:
        """
        Handle docker image removal with timeout support
        :param image_name: Name of the docker image to remove
        :return: True is removal successful and False otherwise
        """
        try:
            self.__client.images.remove(image_name, force=False, noprune=False)
            return True
        except (ReadTimeout, requests.exceptions.ConnectionError):
            logger.warning("The deletion of the image has timeout. Docker is still processing the removal, please wait.")
            max_retry = 10
            wait_time = 5
            for i in range(5):
                try:
                    _ = self.__client.images.get(image_name)
                    # DockerSDK image getter is an exact matching, no need to add more check
                except APIError as err:
                    if err.status_code == 404:
                        return True
                    else:
                        logger.debug(f"Unexpected error after timeout: {err}")
                except (ReadTimeout, requests.exceptions.ConnectionError):
                    wait_time = wait_time + wait_time * i
                    logger.info(f"Docker timeout again ({i + 1}/{max_retry}). Next retry in {wait_time} seconds...")
                    sleep(wait_time)  # Wait x seconds before retry
            logger.error(f"The deletion of the image '{image_name}' has timeout, the deletion may be incomplete.")
        return False

    def buildImage(self, tag: str, build_profile: Optional[str], build_dockerfile: Optional[str], dockerfile_path: str) -> None:
        """Build a docker image from source"""
        if ParametersManager().offline_mode:
            logger.critical("It's not possible to build a docker image in offline mode. The build process need access to internet ...")
            raise RuntimeError
        logger.info(f"Building mandalore image : {tag}")
        if build_profile is None or build_dockerfile is None:
            build_profile = "full"
            build_dockerfile = "Dockerfile"
        logger.info("Starting build. Please wait, this will be long.")
        logger.verbose(f"Creating build context from [gold]{dockerfile_path}[/gold] with "
                       f"[green][b]{build_profile}[/b][/green] profile ({ParametersManager().arch}).")
        if EnvInfo.arch != ParametersManager().arch:
            logger.warning("Building an image for a different host architecture can cause unexpected problems and slowdowns!")
        try:
            # path is the directory full path where Dockerfile is.
            # tag is the name of the final build
            # dockerfile is the Dockerfile filename
            MandaloreTUI.buildDockerImage(
                self.__client.api.build(path=dockerfile_path,
                                        dockerfile=build_dockerfile,
                                        tag=f"{ConstantConfig.IMAGE_NAME}:{tag}",
                                        buildargs={"TAG": f"{build_profile}",
                                                   "VERSION": "local",
                                                   "BUILD_DATE": datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')},
                                        platform="linux/" + ParametersManager().arch,
                                        rm=True,
                                        forcerm=True,
                                        pull=True,
                                        decode=True))
            logger.success(f"Mandalore image successfully built")
        except APIError as err:
            logger.debug(f"Error: {err}")
            if err.status_code == 500:
                logger.error(f"Error: {err.explanation}")
                logger.error("Error while contacting docker hub. You probably don't have internet. Aborting.")
                logger.debug(f"Error: {err}")
            else:
                logger.critical(f"An error occurred while building this image : {err}")
        except ReadTimeout:
            logger.critical("Received a timeout error, Docker is busy... Unable to build the local image, retry later.")
            raise RuntimeError
