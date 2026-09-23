"""Root filesystem construction for Buster OS.

Lays out a standard Linux tree (merged /usr), populates base users and
configuration, installs Debian package payloads with a faithful dpkg status
database (configuration is finalized by dpkg on first boot), and installs
the Buster system layer on top.

IMPORTANT — authoritative metadata overlay
    The final release tarball is serialized from an in-memory metadata
    overlay that is populated with each file's type, mode and link target
    **directly from the package payload tar members** (and from Buster's own
    writers). The staging filesystem is only a byte store and may not be able
    to represent Unix modes (e.g. Windows, where everything reports 0666);
    Unix file mode bits are therefore never re-derived from staging-tree stat
    calls. This is what keeps executables executable in the produced artifact
    no matter which machine runs the build.
"""

import logging
import os
import shutil
import stat
import tarfile
from typing import Iterable, Optional

from buster.osbuild import identity
from buster.version import get_version

log = logging.getLogger("buster.osbuild.rootfs")

DPKG_SCHEMA_DIRS = [
    "var/lib/dpkg/updates",
    "var/lib/dpkg/info",
    "var/lib/dpkg/parts",
    "var/lib/apt/lists/partial",
    "var/cache/apt/archives/partial",
    "var/lib/dpkg/triggers",
]

BASE_DIRS = {
    "etc": 0o755, "usr": 0o755, "usr/bin": 0o755, "usr/lib": 0o755,
    "usr/sbin": 0o755, "usr/share": 0o755, "opt": 0o755, "srv": 0o755,
    "var": 0o755, "var/lib": 0o755, "var/log": 0o755, "var/cache": 0o755,
    "var/tmp": 0o1777, "run": 0o755, "tmp": 0o1777, "home": 0o755,
    "root": 0o700, "media": 0o755, "mnt": 0o755, "dev": 0o755,
    "proc": 0o755, "sys": 0o755, "etc/apt": 0o755, "etc/apt/trusted.gpg.d": 0o755,
    "etc/profile.d": 0o755, "etc/logrotate.d": 0o755,
    "usr/local": 0o755, "usr/local/bin": 0o755, "usr/local/lib": 0o755,
    "dev/pts": 0o755, "dev/shm": 0o1777,
}


class Rootfs:
    """Mutable rootfs tree being constructed."""

    def __init__(self, root: str, arch: str):
        self.root = os.path.abspath(root)
        self.arch = arch
        # Authoritative metadata overlay: rel path -> (kind, mode)
        # kind in {"dir", "file", "symlink", "hardlink"}
        self.modes: dict[str, tuple] = {}
        # Link targets: rel path -> (kind, linkname) for symlink/hardlink
        self.links: dict[str, tuple] = {}
        # Bytes for payload members the host cannot write to disk at all
        # (e.g. Windows-invalid filenames containing "::"). Emitted verbatim.
        self.extra_members: list[tuple] = []

    # -- path helpers ----------------------------------------------------

    def _path(self, rel: str) -> str:
        target = os.path.abspath(os.path.join(self.root, rel.lstrip("/")))
        if target != self.root and not target.startswith(self.root + os.sep):
            raise ValueError(f"path escapes rootfs: {rel}")
        return target

    @staticmethod
    def _normalize(rel: str) -> str:
        """Normalize a pre-merged-/usr package path into the /usr layout."""
        rel = rel.strip("/")
        parts = rel.split("/")
        if parts and parts[0] in ("bin", "sbin", "lib", "lib64"):
            parts = ["usr"] + parts
        return "/".join(parts)

    def _record(self, rel: str, kind: str, mode: int = 0o644,
                linkname: str = "") -> None:
        # ``rel`` is a FINAL (already normalized) path. Package payload paths
        # are normalized by install_payload before being recorded.
        rel = rel.strip("/").replace("\\", "/")
        mode = stat.S_IMODE(int(mode))
        if kind in ("symlink", "hardlink"):
            self.modes[rel] = (kind, 0o777 if kind == "symlink" else mode)
            self.links[rel] = (kind, linkname)
        else:
            self.modes[rel] = (kind, mode)

    # -- layout ---------------------------------------------------------

    def build_layout(self) -> None:
        for rel, mode in BASE_DIRS.items():
            os.makedirs(self._path(rel), exist_ok=True)
            self._chmod(rel, mode)
            self._record(rel, "dir", mode)
        # merged /usr symlinks (as in Debian bookworm usrmerge)
        symlink_map = {
            "bin": "usr/bin", "sbin": "usr/sbin", "lib": "usr/lib",
        }
        if self.arch == "amd64":
            symlink_map.setdefault("lib64", "usr/lib64")
        for link, target in symlink_map.items():
            self._record(link, "symlink", 0o777, target)
            link_path = self._path(link)
            if not os.path.lexists(link_path):
                try:
                    os.symlink(target, link_path)
                except OSError:
                    # Non-posix build host: a real dir keeps the staging tree
                    # usable; the artifact still records this as the symlink.
                    os.makedirs(link_path, exist_ok=True)

    def _chmod(self, rel: str, mode: int) -> None:
        try:
            os.chmod(self._path(rel), stat.S_IMODE(mode))
        except OSError:
            pass  # best-effort on non-posix hosts

    # -- package payload extraction -----------------------------------

    def install_payload(self, pkg_name: str, tar: tarfile.TarFile) -> list[str]:
        """Extract one package's data.tar payload; returns normalized paths."""
        installed: list[str] = []
        for member in tar.getmembers():
            clean = member.name.lstrip("./")
            rel = self._normalize(clean)
            if not rel:
                continue
            mode = stat.S_IMODE(getattr(member, "mode", 0o644))
            target = self._path(rel)

            if member.isdir():
                os.makedirs(target, exist_ok=True)
                self._record(rel, "dir", mode)
                installed.append("/" + rel.rstrip("/"))
            elif member.issym():
                os.makedirs(os.path.dirname(target), exist_ok=True)
                self._record(rel, "symlink", 0o777, member.linkname)
                if os.path.lexists(target):
                    try:
                        os.unlink(target)
                    except OSError:
                        pass
                try:
                    os.symlink(member.linkname, target)
                except OSError:
                    pass  # artifact produced from the overlay, not disk
                installed.append("/" + rel)
            elif member.islnk():
                self._record(rel, "hardlink", 0o777, member.linkname)
                installed.append("/" + rel)
            elif member.isfile():
                os.makedirs(os.path.dirname(target), exist_ok=True)
                self._record(rel, "file", mode)
                try:
                    with open(target, "wb") as handle:
                        shutil.copyfileobj(tar.extractfile(member), handle)
                    self._chmod(rel, mode)
                except OSError:
                    # Unwritable on this host (e.g. Windows ``::`` in names):
                    # keep payload bytes for verbatim emission in the artifact.
                    inner = tar.extractfile(member)
                    if inner is not None:
                        self.extra_members.append(("file", "/" + rel, mode,
                                                   inner.read()))
                installed.append("/" + rel)
        return installed

    # -- authoritative tar serialization -------------------------------

    def pack_tree(self, tar: tarfile.TarFile, uid: int = 0, gid: int = 0) -> None:
        """Serialize the full rootfs from the metadata overlay.

        File modes come from the overlay (populated from package payloads and
        Buster's own writers), never from staging-filesystem stat calls.
        """
        emitted: set[str] = set()
        root_abs = self.root

        def add_dir(rel: str, mode: int) -> None:
            if not rel or rel == "." or rel in emitted:
                return
            info = tarfile.TarInfo(rel.rstrip("/"))
            info.type = tarfile.DIRTYPE
            info.mode = stat.S_IMODE(mode or 0o755)
            info.uid, info.gid = uid, gid
            tar.addfile(info)
            emitted.add(rel.rstrip("/"))

        def add_link(rel: str) -> None:
            if rel in emitted:
                return
            kind, linkname = self.links.get(rel, (None, ""))
            info = tarfile.TarInfo(rel)
            info.uid, info.gid = uid, gid
            if kind == "hardlink":
                info.type = tarfile.LNKTYPE
                info.linkname = linkname
            else:
                info.type = tarfile.SYMTYPE
                info.linkname = linkname
            info.mode = 0o777
            tar.addfile(info)
            emitted.add(rel)

        def add_file(rel: str, disk_path: str) -> None:
            if rel in emitted:
                return
            kind, mode = self.modes.get(rel, ("file", 0o644))
            info = tarfile.TarInfo(rel)
            info.type = tarfile.REGTYPE
            info.mode = stat.S_IMODE(mode or 0o644)
            info.uid, info.gid = uid, gid
            info.size = os.path.getsize(disk_path)
            with open(disk_path, "rb") as handle:
                tar.addfile(info, handle)
            emitted.add(rel)

        # depth-first: emit every parent dir before its contents
        for dirpath, dirnames, filenames in os.walk(root_abs):
            rel = os.path.relpath(dirpath, root_abs).replace(os.sep, "/")
            if rel == ".":
                rel = ""
            if rel:
                kind, mode = self.modes.get(rel, ("dir", 0o755))
                add_dir(rel, mode)

            dirnames.sort()
            filenames.sort()
            removable = []
            for name in dirnames:
                child = os.path.join(dirpath, name)
                child_rel = (rel + "/" + name) if rel else name
                if child_rel in self.links:
                    add_link(child_rel)
                    removable.append(name)  # do not descend into a link
                else:
                    kind, mode = self.modes.get(child_rel, ("dir", 0o755))
                    add_dir(child_rel, mode)
            for name in removable:
                dirnames.remove(name)

            for name in filenames:
                child = os.path.join(dirpath, name)
                child_rel = (rel + "/" + name) if rel else name
                if child_rel in self.links:
                    add_link(child_rel)
                else:
                    add_file(child_rel, child)

        # links that exist only in metadata (host could not create them)
        for rel in sorted(self.links):
            add_link(rel)

        # payload bytes the host could not write to disk (invalid names)
        for kind, name, mode, payload in self.extra_members:
            clean = name.lstrip("/")
            if clean in emitted:
                continue
            info = tarfile.TarInfo(clean)
            info.type = tarfile.REGTYPE
            info.mode = stat.S_IMODE(mode or 0o644)
            info.uid, info.gid = uid, gid
            info.size = len(payload)
            tar.addfile(info, __import__("io").BytesIO(payload))
            emitted.add(clean)

    # -- dpkg database ---------------------------------------------------

    def write_dpkg_state(self, selected: Iterable, contents: dict) -> None:
        """Write /var/lib/dpkg/status and per-package info files."""
        for rel in DPKG_SCHEMA_DIRS:
            os.makedirs(self._path(rel), exist_ok=True)
            self._record(rel, "dir", 0o755)
        self._write_metadata("var/lib/dpkg/arch", self.arch + "\n", 0o644)
        for rel in ("var/lib/dpkg/diversions", "var/lib/dpkg/statoverride"):
            if not os.path.lexists(self._path(rel)):
                self._write_metadata(rel, "", 0o644)

        status_path = self._path("var/lib/dpkg/status")
        with open(status_path, "w", encoding="utf-8") as handle:
            for record in selected:
                content = contents.get(record.package)
                if content is None:
                    continue
                control = content.control or {}
                handle.write(self._status_stanza(record, control))
                self._write_info(record.package, content, control)
        self._record("var/lib/dpkg/status", "file", 0o644)

    @staticmethod
    def _status_stanza(record, control: dict) -> str:
        lines = [
            f"Package: {record.package}",
            f"Version: {record.version}",
            f"Architecture: {record.architecture}",
            "Status: install ok installed",
            f"Priority: {control.get('Priority', record.priority or 'optional')}",
            f"Section: {control.get('Section', record.section or '')}",
            f"Installed-Size: {int(control.get('Installed-Size', '0') or 0)}",
            f"Maintainer: {control.get('Maintainer', 'unknown')}",
            f"Description: {control.get('Description', record.package)}",
        ]
        if control.get("Depends"):
            lines.append(f"Depends: {control['Depends']}")
        if control.get("Pre-Depends"):
            lines.append(f"Pre-Depends: {control['Pre-Depends']}")
        if control.get("Provides"):
            lines.append(f"Provides: {control['Provides']}")
        if control.get("Multi-Arch"):
            lines.append(f"Multi-Arch: {control['Multi-Arch']}")
        lines.append("")
        return "\n".join(lines) + "\n"

    def _write_info(self, pkg: str, content, control: dict) -> None:
        info = self._path(f"var/lib/dpkg/info/{pkg}")
        list_path = info + ".list"
        with open(list_path, "w", encoding="utf-8") as handle:
            for path in content.payload_files:
                handle.write("/" + path.lstrip("/") + "\n")
        self._record(f"var/lib/dpkg/info/{pkg}.list", "file", 0o644)
        if content.conffiles:
            with open(info + ".conffiles", "w", encoding="utf-8") as handle:
                handle.write("\n".join(conf for conf in content.conffiles) + "\n")
            self._record(f"var/lib/dpkg/info/{pkg}.conffiles", "file", 0o644)

    # -- base system files ---------------------------------------------

    def write_base_config(self, distro: str, mirror: str, security_mirror: str,
                          hostname: str = "busteros") -> None:
        def put(rel: str, text: str, mode: int = 0o644):
            self._write_metadata(rel, text, mode)

        put("etc/hostname", hostname + "\n")
        put("etc/hosts", identity.hosts(hostname))
        put("etc/nsswitch.conf", identity.nsswitch_conf())
        put("etc/fstab", identity.fstab())
        put("etc/apt/sources.list", identity.apt_sources(
            self.arch, mirror.rstrip("/"), distro, security_mirror.rstrip("/")))
        put("etc/default/locale", "LANG=C.UTF-8\nLC_ALL=C.UTF-8\n")
        put("etc/timezone", "Etc/UTC\n")
        put("etc/environment",
            'PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"\n')
        put("etc/skel/.profile", "# Buster OS user profile\n")

    def write_passwd_db(self) -> None:
        self.write_passwd()
        self.write_group()
        self.write_shadow()

    def write_passwd(self) -> None:
        users = [
            ("root", "x", "0", "0", "Buster OS superuser", "/root", "/bin/bash"),
            ("daemon", "x", "1", "1", "daemon", "/usr/sbin", "/usr/sbin/nologin"),
            ("bin", "x", "2", "2", "bin", "/bin", "/usr/sbin/nologin"),
            ("sys", "x", "3", "3", "sys", "/dev", "/usr/sbin/nologin"),
            ("sync", "x", "4", "65534", "sync", "/bin", "/bin/sync"),
            ("games", "x", "5", "60", "games", "/usr/games", "/usr/sbin/nologin"),
            ("man", "x", "6", "12", "man", "/var/cache/man", "/usr/sbin/nologin"),
            ("lp", "x", "7", "7", "lp", "/var/spool/lpd", "/usr/sbin/nologin"),
            ("mail", "x", "8", "8", "mail", "/var/mail", "/usr/sbin/nologin"),
            ("news", "x", "9", "9", "news", "/var/spool/news", "/usr/sbin/nologin"),
            ("uucp", "x", "10", "10", "uucp", "/var/spool/uucp", "/usr/sbin/nologin"),
            ("proxy", "x", "13", "13", "proxy", "/bin", "/usr/sbin/nologin"),
            ("www-data", "x", "33", "33", "www-data", "/var/www", "/usr/sbin/nologin"),
            ("backup", "x", "34", "34", "backup", "/var/backups", "/usr/sbin/nologin"),
            ("list", "x", "38", "38", "Mailing List Manager", "/var/list", "/usr/sbin/nologin"),
            ("irc", "x", "39", "39", "ircd", "/run/ircd", "/usr/sbin/nologin"),
            ("_apt", "x", "100", "65534", "", "/nonexistent", "/usr/sbin/nologin"),
            ("buster", "x", "1000", "1000", "Buster OS service user", "/home/buster", "/bin/bash"),
        ]
        lines = [":".join(u) for u in users]
        remaining = "\n".join(lines) + "\n"
        self._write_metadata("etc/passwd", remaining, 0o644)

    def write_group(self) -> None:
        groups = [
            ("root", "x", "0"), ("daemon", "x", "1"), ("bin", "x", "2"),
            ("sys", "x", "3"), ("adm", "x", "4"), ("tty", "x", "5"),
            ("disk", "x", "6"), ("lp", "x", "7"), ("mail", "x", "8"),
            ("news", "x", "9"), ("uucp", "x", "10"), ("man", "x", "12"),
            ("proxy", "x", "13"), ("kmem", "x", "15"), ("dialout", "x", "20"),
            ("fax", "x", "21"), ("voice", "x", "22"), ("cdrom", "x", "24"),
            ("floppy", "x", "25"), ("tape", "x", "26"), ("sudo", "x", "27"),
            ("audio", "x", "29"), ("dip", "x", "30"), ("www-data", "x", "33"),
            ("backup", "x", "34"), ("operator", "x", "37"), ("list", "x", "38"),
            ("irc", "x", "39"), ("src", "x", "40"), ("shadow", "x", "42"),
            ("utmp", "x", "43"), ("video", "x", "44"), ("sasl", "x", "45"),
            ("plugdev", "x", "46"), ("staff", "x", "50"), ("games", "x", "60"),
            ("users", "x", "100"), ("nogroup", "x", "65534"),
            ("buster", "x", "1000"),
        ]
        lines = [":".join(g) for g in groups]
        self._write_metadata("etc/group", "\n".join(lines) + "\n", 0o644)

    def write_shadow(self) -> None:
        r = self._path("etc/passwd")
        shadow = [("root", "!x", "19701", "0", "99999", "7", "", "", ""), ("daemon", "!", "", "", "", "", "", "", "")]
        if os.path.isfile(r):
            with open(r, encoding="utf-8") as handle:
                for line in handle:
                    name = line.split(":", 1)[0]
                    if name and name not in {s[0] for s in shadow}:
                        shadow.append((name, "!", "", "", "", "", "", "", ""))
        lines = [":".join(s) for s in shadow]
        self._write_metadata("etc/shadow", "\n".join(lines) + "\n", 0o640)

    # -- Buster system layer --------------------------------------------

    def install_buster(self, source_dir: str, version: str = None,
                       install_path: str = "/var/lib/buster") -> None:
        """Copy the Buster python runtime into the OS and wire system files."""
        version = version or get_version()
        lib_dir = self._path("opt/buster/lib")
        os.makedirs(lib_dir, exist_ok=True)
        self._record("opt/buster/lib", "dir", 0o755)
        src = os.path.join(source_dir, "buster")
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(lib_dir, "buster"),
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            self._record_tree("opt/buster/lib/buster")

        dist_packages = self._find_dist_packages()
        os.makedirs(dist_packages, exist_ok=True)
        self._record(dist_packages.replace(self.root, "").lstrip("/\\").replace("\\", "/"),
                     "dir", 0o755)
        self._write_metadata(
            self._rel_of(dist_packages) + "/buster.pth", "/opt/buster/lib\n", 0o644)

        self._write_buster_services()
        self._write_buster_config(install_path)
        self._write_buster_identity(version)

        for rel in [
            "var/lib/buster/state", "var/lib/buster/memory",
            "var/cache/buster", "var/log/buster", "run/buster",
            "opt/buster/bin", "home/buster", "srv/buster",
        ]:
            os.makedirs(self._path(rel), exist_ok=True)
            self._record(rel, "dir", 0o755)

        self._write_text("usr/bin/buster",
                         "#!/bin/sh\nexec /usr/bin/python3 -m buster.cli \"$@\"\n", 0o755)
        self._write_text("usr/bin/busterctl",
                         "#!/bin/sh\nexport BUSTER_INSTALL=/var/lib/buster\nexec /usr/bin/python3 -m buster.system.busterctl \"$@\"\n", 0o755)

        self._write_text("etc/profile.d/buster.sh", identity.buster_profile_sh())
        self._write_text("etc/logrotate.d/buster",
                         "/var/log/buster/*.log {\n    weekly\n    rotate 4\n    compress\n    missingok\n    notifempty\n}\n")

    def _find_dist_packages(self) -> str:
        return self._path("usr/lib/python3/dist-packages")

    def _rel_of(self, path: str) -> str:
        return os.path.relpath(path, self.root).replace(os.sep, "/")

    def _record_tree(self, rel: str) -> None:
        base = self._path(rel)
        for dirpath, dirnames, filenames in os.walk(base):
            rel_dir = self._rel_of(dirpath)
            self._record(rel_dir, "dir", 0o755)
            for name in filenames:
                self._record(self._rel_of(os.path.join(dirpath, name)), "file", 0o644)

    def _write_buster_services(self) -> None:
        self._write_text("etc/systemd/system/buster.service", identity.systemd_unit())
        self._write_text("etc/init.d/buster", identity.sysvinit_script(), 0o755)

    def _write_buster_config(self, install_path: str) -> None:
        cfg_dir = self._path("etc/buster")
        os.makedirs(cfg_dir, exist_ok=True)
        self._record("etc/buster", "dir", 0o755)
        self._write_metadata("etc/buster/config.json",
                             identity.buster_config_json(install_path=install_path))
        self._write_metadata("etc/buster/buster.env", f"BUSTER_INSTALL={install_path}\n")

    def _write_buster_identity(self, version: str) -> None:
        meta_dir = self._path("usr/share/buster")
        os.makedirs(meta_dir, exist_ok=True)
        self._record("usr/share/buster", "dir", 0o755)
        self._write_metadata("usr/share/buster/VERSION", version + "\n")
        self._write_metadata("usr/share/buster/identity.json",
                             identity.identity_json(version, self.arch,
                                                    "debian", "bookworm"))

    def write_os_release(self, version: str = None) -> None:
        version = version or get_version()
        usr_lib = self._path("usr/lib/os-release")
        os.makedirs(os.path.dirname(usr_lib), exist_ok=True)
        with open(usr_lib, "w", encoding="utf-8") as handle:
            handle.write(identity.os_release(version))
        self._record("usr/lib/os-release", "file", 0o644)
        osrc = self._path("etc/os-release")
        if os.path.lexists(osrc):
            try:
                os.unlink(osrc)
            except OSError:
                pass
        try:
            os.symlink("../usr/lib/os-release", osrc)
            self._record("etc/os-release", "symlink", 0o777, "../usr/lib/os-release")
        except OSError:
            shutil.copyfile(usr_lib, osrc)
            self._record("etc/os-release", "file", 0o644)
        self._write_metadata("etc/issue", identity.issue(version), 0o644)

    # -- shared writers (record authoritative modes) --------------------

    def _write_metadata(self, rel: str, text: str, mode: int = 0o644) -> None:
        target = self._path(rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(text)
        self._chmod(rel, mode)
        self._record(rel, "file", mode)

    def _write_text(self, rel: str, text: str, mode: int = 0o644) -> None:
        self._write_metadata(rel, text, mode)

    def write_binary(self, rel: str, data: bytes, mode: int = 0o644) -> None:
        """Write a binary file, recording its authoritative Unix mode."""
        target = self._path(rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(data)
        self._chmod(rel, mode)
        self._record(rel, "file", mode)