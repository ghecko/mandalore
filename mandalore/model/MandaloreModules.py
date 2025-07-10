from pathlib import Path
from typing import Optional, Union

from mandalore.config.ConstantConfig import ConstantConfig
from mandalore.config.UserConfig import UserConfig
from mandalore.console.MandalorePrompt import Confirm
from mandalore.console.cli.ParametersManager import ParametersManager
from mandalore.exceptions.MandaloreExceptions import CancelOperation
from mandalore.utils.ExeLog import logger
from mandalore.utils.GitUtils import GitUtils
from mandalore.utils.MetaSingleton import MetaSingleton


class MandaloreModules(metaclass=MetaSingleton):
    """Singleton class dedicated to the centralized management of the project modules"""

    def __init__(self) -> None:
        """Init project git modules to None until their first call"""
        # Git modules
        self.__git_wrapper: Optional[GitUtils] = None
        self.__git_source: Optional[GitUtils] = None
        self.__git_resources: Optional[GitUtils] = None

        # Git loading mode
        self.__wrapper_fast_loaded = False

    def getWrapperGit(self, fast_load: bool = False) -> GitUtils:
        """GitUtils local singleton getter.
        Set fast_load to True to disable submodule init/update."""
        # If the module have been previously fast loaded and must be reuse later in standard mode, it can be recreated
        if self.__git_wrapper is None or (not fast_load and self.__wrapper_fast_loaded):
            self.__wrapper_fast_loaded = fast_load
            self.__git_wrapper = GitUtils(skip_submodule_update=fast_load)
        return self.__git_wrapper

    def getSourceGit(self, fast_load: bool = False, skip_install: bool = False) -> GitUtils:
        """GitUtils source submodule singleton getter.
        Set fast_load to True to disable submodule init/update.
        Set skip_install to skip to installation process of the modules if not available.
        if skip_install is NOT set, the CancelOperation exception is raised if the installation failed."""
        if self.__git_source is None:
            self.__git_source = GitUtils(UserConfig().mandalore_images_path, "images",
                                         skip_submodule_update=fast_load)
        if not self.__git_source.isAvailable and not skip_install:
            self.__init_images_repo()
        return self.__git_source

    def getResourcesGit(self, fast_load: bool = False, skip_install: bool = False) -> GitUtils:
        """GitUtils resource repo/submodule singleton getter.
        Set fast_load to True to disable submodule init/update.
        Set skip_install to skip to installation process of the modules if not available.
        if skip_install is NOT set, the CancelOperation exception is raised if the installation failed."""
        if self.__git_resources is None:
            self.__git_resources = GitUtils(UserConfig().mandalore_resources_path, "resources", "",
                                            skip_submodule_update=fast_load)
        if not self.__git_resources.isAvailable and not skip_install and UserConfig().enable_mandalore_resources:
            self.__init_resources_repo()
        return self.__git_resources

    def __init_images_repo(self) -> None:
        """Initialization procedure of mandalore images module.
        Raise CancelOperation if the initialization failed."""
        if ParametersManager().offline_mode:
            logger.error("It's not possible to install 'Mandalore Images' in offline mode. Skipping the operation.")
            raise CancelOperation
        # If git wrapper is ready and mandalore images location is the corresponding submodule, running submodule update
        # if not, git clone resources
        if ConstantConfig.git_source_installation and self.getWrapperGit(fast_load=True).isAvailable:
            # When resources are load from git submodule, git objects are stored in the root .git directory
            if self.getWrapperGit(fast_load=True).submoduleSourceUpdate("mandalore-images"):
                self.__git_source = None
                self.getSourceGit()
            else:
                # Error during install, raise error to avoid update process
                raise CancelOperation
        else:
            assert self.__git_source is not None
            if not self.__git_source.clone(ConstantConfig.MANDALORE_IMAGES_REPO):
                # Error during install, raise error to avoid update process
                raise CancelOperation

    def __init_resources_repo(self) -> None:
        """Initialization procedure of mandalore resources module.
        Raise CancelOperation if the initialization failed."""
        if ParametersManager().offline_mode:
            logger.error("It's not possible to install 'Mandalore resources' in offline mode. Skipping the operation.")
            raise CancelOperation
        if Confirm("Do you want to download mandalore resources? (~1G)", True):
            # If git wrapper is ready and mandalore resources location is the corresponding submodule, running submodule update
            # if not, git clone resources
            if UserConfig().mandalore_resources_path == ConstantConfig.src_root_path_obj / 'mandalore-resources' and \
                    self.getWrapperGit().isAvailable:
                # When resources are load from git submodule, git objects are stored in the root .git directory
                self.__warningExcludeFolderAV(ConstantConfig.src_root_path_obj)
                if self.getWrapperGit().submoduleSourceUpdate("mandalore-resources"):
                    self.__git_resources = None
                    self.getResourcesGit()
                else:
                    # Error during install, raise error to avoid update process
                    raise CancelOperation
            else:
                self.__warningExcludeFolderAV(UserConfig().mandalore_resources_path)
                assert self.__git_resources is not None
                if not self.__git_resources.clone(ConstantConfig.MANDALORE_RESOURCES_REPO):
                    # Error during install, raise error to avoid update process
                    raise CancelOperation
        else:
            # User cancel installation, skip update update
            raise CancelOperation

    def isMandaloreResourcesReady(self) -> bool:
        """Update Mandalore-resources from git (submodule)"""
        return self.getResourcesGit(fast_load=True).isAvailable

    @staticmethod
    def __warningExcludeFolderAV(directory: Union[str, Path]) -> None:
        """Generic procedure to warn the user that not antivirus compatible files will be downloaded and that
        the destination folder should be excluded from the scans to avoid any problems"""
        logger.warning(f"If you are using an [orange3][g]Anti-Virus[/g][/orange3] on your host, you should exclude the folder {directory} before starting the download.")
        while not Confirm(f"Are you ready to start the download?", True):
            pass
