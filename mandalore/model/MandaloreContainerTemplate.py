import os
import re
from typing import Optional

from rich.prompt import Prompt

from mandalore.config.EnvInfo import EnvInfo
from mandalore.model.ContainerConfig import ContainerConfig
from mandalore.model.MandaloreImage import MandaloreImage
from mandalore.utils.ExeLog import logger


class MandaloreContainerTemplate:
    """Mandalore template class used to create a new container"""

    def __init__(self, name: Optional[str], config: ContainerConfig, image: MandaloreImage, hostname: Optional[str] = None, new_container: bool = True):
        # Only names of new containers are validated (existing containers are loaded as-is)
        if name is not None and new_container:
            name = name.strip()
            if not self.isValidName(name):
                logger.critical(f"Invalid container name '{name}': only letters, digits, '_', '.' and '-' are allowed.")
        while name is None or (new_container and not self.isValidName(name)):
            if name is not None:
                logger.error("Invalid container name: only letters, digits, '_', '.' and '-' are allowed.")
            name = Prompt.ask("[bold blue][?][/bold blue] Enter the name of your new mandalore container", default="default").strip()
        if (EnvInfo.isWindowsHost() or EnvInfo.isMacHost()) and not name.startswith("mandalore-"):
            # Force container as lowercase because the filesystem of windows / mac are case-insensitive => https://github.com/ThePorgs/Exegol/issues/167
            name = name.lower()
        self.container_name: str = name if name.startswith("mandalore-") else f'mandalore-{name}'
        self.name: str = name.replace('mandalore-', '')
        self.image: MandaloreImage = image
        self.config: ContainerConfig = config
        if hostname:
            self.config.hostname = hostname
            if new_container:
                self.config.addEnv(ContainerConfig.MandaloreEnv.mandalore_name.value, self.container_name)
        else:
            self.config.hostname = self.container_name

    @staticmethod
    def isValidName(name: str) -> bool:
        """Check that a container name is accepted by docker (once prefixed with 'mandalore-')"""
        short_name = name[len("mandalore-"):] if name.startswith("mandalore-") else name
        return re.fullmatch(r"[a-zA-Z0-9_.-]+", short_name) is not None

    def __str__(self) -> str:
        """Default object text formatter, debug only"""
        return f"{self.name} - {self.image.getName()}{os.linesep}{self.config}"

    def prepare(self) -> None:
        """Prepare the model before creating the docker container"""
        self.config.prepareShare(self.name)

    def rollback(self) -> None:
        """Rollback change in case of container creation fail."""
        self.config.rollback_preparation(self.name)

    def getDisplayName(self) -> str:
        """Getter of the container's name for TUI purpose"""
        if self.container_name != self.config.hostname:
            return f"{self.name} [bright_black]({self.config.hostname})[/bright_black]"
        return self.name

    def getTextStatus(self) -> str:
        return ""
