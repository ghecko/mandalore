from mandalore.console.cli.MandaloreCompleter import HybridContainerImageCompleter, VoidCompleter, BuildProfileCompleter, ImageCompleter
from mandalore.console.cli.actions.Command import Command, Option, GroupArg
from mandalore.console.cli.actions.GenericParameters import ContainerCreation, ContainerSpawnShell, ContainerMultiSelector, ContainerSelector, ImageSelector, ImageMultiSelector, ContainerStart
from mandalore.manager.MandaloreManager import MandaloreManager
from mandalore.utils.ExeLog import logger


class Start(Command, ContainerCreation, ContainerSpawnShell):
    """Automatically create, start / resume and enter an Mandalore container"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerCreation.__init__(self, self.groupArgs)
        ContainerSpawnShell.__init__(self, self.groupArgs)

        self._usages = {
            "Start interactively a container": "mandalore start",
            "Create a [blue]demo[/blue] container using [bright_blue]full[/bright_blue] image": "mandalore start [blue]demo[/blue] [bright_blue]full[/bright_blue]",
            "Spawn a shell from [blue]demo[/blue] container": "mandalore start [blue]demo[/blue]",
            "Create a container [blue]test[/blue] with a custom shared workspace": "mandalore start [blue]test[/blue] [bright_blue]full[/bright_blue] -w [magenta]./project/pentest/[/magenta]",
            "Create a container [blue]test[/blue] sharing the current working directory": "mandalore start [blue]test[/blue] [bright_blue]full[/bright_blue] -cwd",
            "Create a container [blue]htb[/blue] with a VPN": "mandalore start [blue]htb[/blue] [bright_blue]full[/bright_blue] --vpn [magenta]~/vpn/[/magenta][bright_magenta]lab_Dramelac.ovpn[/bright_magenta]",
            "Create a container [blue]app[/blue] with custom volume": "mandalore start [blue]app[/blue] [bright_blue]full[/bright_blue] -V [bright_magenta]/var/app/[/bright_magenta]:[bright_magenta]/app/[/bright_magenta]",
            "Create a container [blue]app[/blue] with custom volume in [blue]ReadOnly[/blue]": "mandalore start [blue]app[/blue] [bright_blue]full[/bright_blue] -V [bright_magenta]/var/app/[/bright_magenta]:[bright_magenta]/app/[/bright_magenta]:[blue]ro[/blue]",
            "Get a [blue]tmux[/blue] shell": "mandalore start --shell [blue]tmux[/blue]",
            "Share a specific [blue]hardware device[/blue] [bright_black](e.g. Proxmark)[/bright_black]": "mandalore start -d /dev/ttyACM0",
            "Share every [blue]USB device[/blue] connected to the host": "mandalore start -d /dev/bus/usb/",
        }

    def __call__(self, *args, **kwargs):
        return MandaloreManager.start


class Stop(Command, ContainerMultiSelector):
    """Stop an Mandalore container"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerMultiSelector.__init__(self, self.groupArgs)

        self._usages = {
            "Stop interactively one or more containers": "mandalore stop",
            "Stop [blue]demo[/blue]": "mandalore stop [blue]demo[/blue]"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running stop module")
        return MandaloreManager.stop


class Restart(Command, ContainerSelector, ContainerSpawnShell):
    """Restart an Mandalore container"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerSelector.__init__(self, self.groupArgs)
        ContainerSpawnShell.__init__(self, self.groupArgs)

        self._usages = {
            "Restart interactively one containers": "mandalore restart",
            "Restart [blue]demo[/blue]": "mandalore restart [blue]demo[/blue]"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running restart module")
        return MandaloreManager.restart


class Install(Command, ImageSelector):
    """Install or build Mandalore image"""

    def __init__(self) -> None:
        Command.__init__(self)
        ImageSelector.__init__(self, self.groupArgs)

        # Create container build arguments
        self.build_profile = Option("build_profile",
                                    metavar="BUILD_PROFILE",
                                    nargs="?",
                                    action="store",
                                    help="Select the build profile used to create a local image.",
                                    completer=BuildProfileCompleter)
        self.build_log = Option("--build-log",
                                dest="build_log",
                                metavar="LOGFILE_PATH",
                                action="store",
                                help="Write image building logs to a file.")
        self.build_path = Option("--build-path",
                                 dest="build_path",
                                 metavar="DOCKERFILES_PATH",
                                 action="store",
                                 help=f"Path to the dockerfiles and sources.")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.build_profile, "required": False},
                                       {"arg": self.build_log, "required": False},
                                       {"arg": self.build_path, "required": False},
                                       title="[bold cyan]Build[/bold cyan] [blue]specific options[/blue]"))

        self._usages = {
            "Install or build interactively an mandalore image": "mandalore install",
            "Install or update the [bright_blue]full[/bright_blue] image": "mandalore install [bright_blue]full[/bright_blue]",
            "Build interactively a local image named [blue]myimage[/blue]": "mandalore install [blue]myimage[/blue]",
            "Build the [blue]myimage[/blue] image based on the [bright_blue]full[/bright_blue] profile and log the operation": "mandalore install [blue]myimage[/blue] [bright_blue]full[/bright_blue] --build-log /tmp/build.log",
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running install module")
        return MandaloreManager.install


class Update(Command, ImageSelector):
    """Update an Mandalore image"""

    def __init__(self) -> None:
        Command.__init__(self)
        ImageSelector.__init__(self, self.groupArgs)

        self.skip_git = Option("--skip-git",
                               dest="skip_git",
                               action="store_true",
                               help="Skip git updates (wrapper, image sources and mandalore resources).")
        self.skip_images = Option("--skip-images",
                                  dest="skip_images",
                                  action="store_true",
                                  help="Skip images updates (mandalore docker images).")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.skip_git, "required": False},
                                       {"arg": self.skip_images, "required": False},
                                       title="[bold cyan]Update[/bold cyan] [blue]specific options[/blue]"))

        self._usages = {
            "Install or update interactively an mandalore image": "mandalore update",
            "Install or update the [bright_blue]full[/bright_blue] image": "mandalore update [bright_blue]full[/bright_blue]"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running update module")
        return MandaloreManager.update


class Upgrade(Command, ContainerMultiSelector):
    """Upgrade Mandalore [default not bold]container(s)[/default not bold] to the latest installed image"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerMultiSelector.__init__(self, self.groupArgs)

        self.force_mode = Option("-F", "--force",
                                 dest="force_mode",
                                 action="store_true",
                                 help="Upgrade container without interactive user confirmation (the image is not updated from the registry).")
        self.upgrade_image = Option("--image",
                                    dest="upgrade_image",
                                    action="store",
                                    metavar="IMAGE",
                                    help="Upgrade the container to another installed Mandalore image (default: the container's current image name).",
                                    completer=ImageCompleter)
        self.remove_old = Option("--remove-old",
                                 dest="remove_old",
                                 action="store_true",
                                 help="Remove the previous container after a successful upgrade instead of keeping it renamed "
                                      "(the workspace is never deleted).")

        self.groupArgs.append(GroupArg({"arg": self.force_mode, "required": False},
                                       {"arg": self.upgrade_image, "required": False},
                                       {"arg": self.remove_old, "required": False},
                                       title="[bold cyan]Upgrade[/bold cyan] [blue]specific options[/blue]"))

        self._usages = {
            "Upgrade interactively one or more containers": "mandalore upgrade",
            "Upgrade the [blue]demo[/blue] container": "mandalore upgrade [blue]demo[/blue]",
            "Upgrade every container and remove the previous ones": "mandalore upgrade --all --remove-old",
            "Move the [blue]demo[/blue] container to the [bright_blue]light[/bright_blue] image": "mandalore upgrade [blue]demo[/blue] --image [bright_blue]light[/bright_blue]",
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running upgrade module")
        return MandaloreManager.upgrade


class Uninstall(Command, ImageMultiSelector):
    """Remove Mandalore [default not bold]image(s)[/default not bold]"""

    def __init__(self) -> None:
        Command.__init__(self)
        ImageMultiSelector.__init__(self, self.groupArgs)

        self.force_mode = Option("-F", "--force",
                                 dest="force_mode",
                                 action="store_true",
                                 help="Remove image without interactive user confirmation.")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.force_mode, "required": False},
                                       title="[bold cyan]Uninstall[/bold cyan] [blue]specific options[/blue]"))

        self._usages = {
            "Uninstall interactively one or more mandalore images": "mandalore uninstall",
            "Uninstall the [bright_blue]dev[/bright_blue] image": "mandalore uninstall [bright_blue]dev[/bright_blue]",
            "Uninstall every installed image": "mandalore uninstall --all"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running uninstall module")
        return MandaloreManager.uninstall


class Remove(Command, ContainerMultiSelector):
    """Remove Mandalore [default not bold]container(s)[/default not bold]"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerMultiSelector.__init__(self, self.groupArgs)

        self.force_mode = Option("-F", "--force",
                                 dest="force_mode",
                                 action="store_true",
                                 help="Remove container without interactive user confirmation.")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.force_mode, "required": False},
                                       title="[bold cyan]Remove[/bold cyan] [blue]specific options[/blue]"))

        self._usages = {
            "Remove interactively one or more containers": "mandalore remove",
            "Remove the [blue]demo[/blue] container": "mandalore remove [blue]demo[/blue]",
            "Remove every container": "mandalore remove --all"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running remove module")
        return MandaloreManager.remove


class Exec(Command, ContainerCreation, ContainerStart):
    """Execute a command on an Mandalore container"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerCreation.__init__(self, self.groupArgs)
        ContainerStart.__init__(self, self.groupArgs)

        # Overwrite default selectors
        for group in self.groupArgs.copy():
            # Find group containing default selector to remove them
            for parameter in group.options:
                if parameter.get('arg') == self.containertag or parameter.get('arg') == self.imagetag:
                    # Removing default GroupArg selector
                    self.groupArgs.remove(group)
                    break
        # Removing default selector objects
        self.containertag = None
        self.imagetag = None

        self.selector = Option("selector",
                               metavar="CONTAINER or IMAGE",
                               nargs='?',
                               action="store",
                               help="Tag used to target an Mandalore container (by default) or an image (if --tmp is set).",
                               completer=HybridContainerImageCompleter)

        # Custom parameters
        self.exec = Option("exec",
                           metavar="COMMAND",
                           nargs="+",
                           action="store",
                           help="Execute a single command in the mandalore container.",
                           completer=VoidCompleter)
        self.daemon = Option("-b", "--background",
                             action="store_true",
                             dest="daemon",
                             help="Executes the command in background as a daemon "
                                  "(default: [red not italic]False[/red not italic])")
        self.tmp = Option("--tmp",
                          action="store_true",
                          dest="tmp",
                          help="Creates a dedicated and temporary container to execute the command "
                               "(default: [red not italic]False[/red not italic])")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.selector, "required": False},
                                       {"arg": self.exec, "required": False},
                                       {"arg": self.daemon, "required": False},
                                       {"arg": self.tmp, "required": False},
                                       title="[bold cyan]Exec[/bold cyan] [blue]specific options[/blue]"))

        self._usages = {
            "Execute the command [magenta]bloodhound[/magenta] in the container [blue]demo[/blue]":
                "mandalore exec [blue]demo[/blue] [magenta]bloodhound[/magenta]",
            "Execute the command [magenta]'nmap -h'[/magenta] with console output":
                "mandalore exec -v [blue]demo[/blue] [magenta]'nmap -h'[/magenta]",
            "Execute a command in [green]background[/green] within the [blue]demo[/blue] container":
                "mandalore exec [green]-b[/green] [blue]demo[/blue] [magenta]bloodhound[/magenta]",
            "Execute the command [magenta]bloodhound[/magenta] in a temporary container based on the [bright_blue]full[/bright_blue] image":
                "mandalore exec --tmp [bright_blue]full[/bright_blue] [magenta]bloodhound[/magenta]",
            "Execute a command in [green]background[/green] with a temporary container":
                "mandalore exec [green]-b[/green] --tmp [bright_blue]full[/bright_blue] [magenta]bloodhound[/magenta]",
            "Execute the command [magenta]wireshark[/magenta] with [orange3]network admin[/orange3] privileged":
                "mandalore exec [green]-b[/green] --tmp --disable-my-resources --cap [orange3]NET_ADMIN[/orange3] [bright_blue]full[/bright_blue] [magenta]wireshark[/magenta]",
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running exec module")
        return MandaloreManager.exec


class Info(Command, ContainerSelector):
    """Show info on containers and images (local & remote)"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerSelector.__init__(self, self.groupArgs)

        self._usages = {
            "Print containers and images essentials information": "mandalore info",
            "Print the detailed configuration of the [blue]demo[/blue] container": "mandalore info [blue]demo[/blue]",
            "Print verbose information": "mandalore info [yellow3]-v[/yellow3]",
            "Print advanced information": "mandalore info [yellow3]-vv[/yellow3]",
            "Print debug information": "mandalore info [yellow3]-vvv[/yellow3]"
        }

    def __call__(self, *args, **kwargs):
        return MandaloreManager.info


class Version(Command):
    """Print current Mandalore version"""

    def __call__(self, *args, **kwargs):
        return lambda: None
