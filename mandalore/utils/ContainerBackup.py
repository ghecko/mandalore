import io
import posixpath
import tarfile
import tempfile
from typing import List, Optional, Tuple

from docker.errors import APIError, NotFound
from docker.models.containers import Container

from mandalore.utils.ExeLog import logger


class ContainerBackup:
    """Transfer user data that lives outside the workspace from a container to another (used by the upgrade process)."""

    # Text files merged line by line: the new image content is kept and the previous container's lines are appended
    MERGE_FILES: Tuple[str, ...] = (
        "/root/.zsh_history",
        "/root/.bash_history",
        "/root/.python_history",
        "/root/.local/share/hashcat/hashcat.potfile",
        "/root/.john/john.pot",
    )
    # Files / directories copied as is (overwriting the new image content)
    COPY_PATHS: Tuple[str, ...] = (
        "/root/.nxc/workspaces",
        "/root/.nxc/logs",
        "/opt/tools/Responder/Responder.db",
        "/opt/tools/Responder/logs",
    )
    # Skip any single path bigger than this limit
    MAX_SIZE = 1024 * 1024 * 1024

    @classmethod
    def describe(cls) -> str:
        return "shell & python history, hashcat / john potfiles, NetExec & Responder data, custom /etc/hosts entries"

    @classmethod
    def transfer(cls, source: Container, target: Container) -> List[str]:
        """Copy the user data from the source container to the (running) target container.
        Return the list of restored paths. Errors are logged and never raised."""
        restored: List[str] = []
        for path in cls.MERGE_FILES:
            try:
                if cls.__mergeTextFile(source, target, path):
                    restored.append(path)
            except (APIError, tarfile.TarError, OSError) as e:
                logger.warning(f"Unable to restore [magenta]{path}[/magenta]: {e}")
        for path in cls.COPY_PATHS:
            try:
                if cls.__copyPath(source, target, path):
                    restored.append(path)
            except (APIError, tarfile.TarError, OSError) as e:
                logger.warning(f"Unable to restore [magenta]{path}[/magenta]: {e}")
        try:
            if cls.__mergeHosts(source, target):
                restored.append("/etc/hosts")
        except (APIError, tarfile.TarError, OSError) as e:
            logger.warning(f"Unable to restore custom [magenta]/etc/hosts[/magenta] entries: {e}")
        return restored

    @classmethod
    def __getArchive(cls, container: Container, path: str) -> Optional[tempfile.SpooledTemporaryFile]:
        """Download a path from a container as a tar archive. Return None if the path doesn't exist or is too big."""
        try:
            stream, stat = container.get_archive(path)
        except NotFound:
            return None
        if int(stat.get("size", 0)) > cls.MAX_SIZE:
            logger.warning(f"Skipping [magenta]{path}[/magenta]: too big to be transferred automatically.")
            return None
        archive = tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024)
        for chunk in stream:
            archive.write(chunk)
        archive.seek(0)
        return archive

    @classmethod
    def __readTextFile(cls, container: Container, path: str) -> Optional[Tuple[tarfile.TarInfo, bytes]]:
        archive = cls.__getArchive(container, path)
        if archive is None:
            return None
        with archive, tarfile.open(fileobj=archive, mode="r|") as tar:
            for member in tar:
                if member.isfile():
                    extracted = tar.extractfile(member)
                    if extracted is not None:
                        return member, extracted.read()
        return None

    @staticmethod
    def __ensureParent(target: Container, path: str) -> None:
        target.exec_run(["mkdir", "-p", posixpath.dirname(path)])

    @classmethod
    def __mergeTextFile(cls, source: Container, target: Container, path: str) -> bool:
        old = cls.__readTextFile(source, path)
        if old is None or len(old[1].strip()) == 0:
            return False
        new = cls.__readTextFile(target, path)
        if new is not None and new[1] == old[1]:
            return False
        old_lines = old[1].splitlines(keepends=True)
        if new is None:
            content = old[1]
            info = old[0]
        else:
            new_lines = new[1].splitlines(keepends=True)
            known = set(line.rstrip(b"\r\n") for line in new_lines)
            content = new[1]
            if len(content) > 0 and not content.endswith(b"\n"):
                content += b"\n"
            content += b"".join(line if line.endswith(b"\n") else line + b"\n"
                                for line in old_lines if line.rstrip(b"\r\n") not in known)
            info = new[0]
        info.name = posixpath.basename(path)
        info.size = len(content)
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as tar:
            tar.addfile(info, io.BytesIO(content))
        cls.__ensureParent(target, path)
        target.put_archive(posixpath.dirname(path), buffer.getvalue())
        logger.verbose(f"Restored (merged) [magenta]{path}[/magenta]")
        return True

    @classmethod
    def __copyPath(cls, source: Container, target: Container, path: str) -> bool:
        archive = cls.__getArchive(source, path)
        if archive is None:
            return False
        with archive:
            cls.__ensureParent(target, path)
            target.put_archive(posixpath.dirname(path), archive.read())
        logger.verbose(f"Restored [magenta]{path}[/magenta]")
        return True

    @classmethod
    def __mergeHosts(cls, source: Container, target: Container) -> bool:
        """/etc/hosts is managed by docker (bind mount): custom entries are appended from inside the new container."""
        old = cls.__readTextFile(source, "/etc/hosts")
        new = cls.__readTextFile(target, "/etc/hosts")
        if old is None or new is None:
            return False
        hostnames = {source.attrs.get("Config", {}).get("Hostname", ""), target.attrs.get("Config", {}).get("Hostname", "")} - {""}
        known = set(line.strip() for line in new[1].decode("utf-8", errors="replace").splitlines())
        custom = []
        for line in old[1].decode("utf-8", errors="replace").splitlines():
            entry = line.strip()
            if not entry or entry.startswith("#") or entry in known:
                continue
            # Skip docker generated entries of the container itself (IP may change)
            if any(h in entry.split() for h in hostnames):
                continue
            custom.append(entry)
        if len(custom) == 0:
            return False
        result = target.exec_run(["sh", "-c", 'printf "%s\\n" "$MANDALORE_HOSTS" >> /etc/hosts'],
                                 environment={"MANDALORE_HOSTS": "\n".join(custom)})
        if result.exit_code != 0:
            raise OSError(result.output.decode("utf-8", errors="replace").strip())
        logger.verbose(f"Restored {len(custom)} custom [magenta]/etc/hosts[/magenta] entries")
        return True
