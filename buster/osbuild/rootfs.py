"""Root filesystem construction for Buster OS.

Lays out a standard Linux tree (merged /usr), populates base users and
configuration, installs Debian package payloads with a faithful dpkg status
database (configuration is finalized by dpkg on first boot), and installs
the Buster system layer on top.
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
    "proc": 0o755, "sys": 0o755, "bin": 0o755, "sbin": 0o755, "lib": 0o755,
    "lib64": 0o755, "etc/apt": 0o755, "etc/apt/trusted.gpg.d": 0o755,
    "etc/profile.d": 0o755, "etc/logrotate.d": 0o755,
    "usr/local": 0o755, "usr/local/bin": 0o755, "usr/local/lib": 0o755,
    "dev/pts": 0o755, "dev/shm": 0o1777,
}


class Rootfs:
    """Mutable rootfs tree being constructed."""

    def __init__(self, root: str, arch: str):
        self.root = os.path.abspath(root)
        self.arch = arch
        # Members the build host could not represent on disk (invalid
        # Windows filenames, symlinks without privilege). They are emitted
        # into the artifact tar verbatim with their true Unix names.
        self.extra_members: list[tuple] = []

    def _path(self, rel: str) -> str:
        target = os.path.abspath(os.path.join(self.root, rel.lstrip("/")))
        if not target.startswith(self.root + os.sep) and target != self.root:
            raise ValueError(f"path escapes rootfs: {rel}")
        return target

    # -- layout ---------------------------------------------------------

    def build_layout(self) -> None:
        for rel, mode in BASE_DIRS.items():
            os.makedirs(self._path(rel), exist_ok=True)
            self._chmod(rel, mode)
        # merged /usr symlinks (as in Debian bookworm usrmerge)
        symlink_map = {
            "bin": "usr/bin", "sbin": "usr/sbin", "lib": "usr/lib",
            "library64": "usr/lib64",
        }
        if self.arch == "amd64":
            symlink_map["lib64"] = "usr/lib64"  # for 64-bit loader
        for link, target in symlink_map.items():
            link_path = self._path(link)
            if not os.path.lexists(link_path):
                try:
                    os.symlink(target, link_path)
                except OSError:
                    # Symlink creation may be unavailable on non-posix build hosts;
                    # fall back to a real directory so the tree remains usable.
                    os.makedirs(link_path, exist_ok=True)
                    log.debug("symlink %s -> %s unavailable; used directory", link, target)

    def _chmod(self, rel: str, mode: int) -> None:
        try:
            os.chmod(self._path(rel), mode)
        except OSError:
            pass  # best-effort on non-posix hosts

    # -- package payload extraction -----------------------------------

    def install_payload(self, pkg_name: str, tar: tarfile.TarFile) -> list[str]:
        """Extract one package's data.tar payload; returns file list."""
        installed: list[str] = []
        for member in tar.getmembers():
            clean = member.name.lstrip("./")
            if not clean:
                continue
            target = self._path(clean)
            if member.isdir():
                # directories would conflict with layout; ensure exists
                if not os.path.isdir(target):
                    os.makedirs(target, exist_ok=True)
                installed.append("/" + clean.rstrip("/"))
            elif member.issym():
                if not os.path.isdir(os.path.dirname(target)):
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                if os.path.lexists(target):
                    try:
                        os.unlink(target)
                    except OSError:
                        pass
                try:
                    os.symlink(member.linkname, target)
                except OSError:
                    # Non-posix host: emit the symlink into the artifact tar
                    # with its true name/link so the rootfs stays genuine.
                    self.extra_members.append(("symlink", "/" + clean,
                                               getattr(member, "mode", 0o777),
                                               member.linkname))
                installed.append("/" + clean)
            elif member.isfile():
                os.makedirs(os.path.dirname(target), exist_ok=True)
                try:
                    with open(target, "wb") as handle:
                        shutil.copyfileobj(tar.extractfile(member), handle)
                    try:
                        mode = member.mode
                        if mode:
                            os.chmod(target, stat.S_IMODE(mode))
                    except OSError:
                        pass
                except OSError:
                    # Unwritable on this host (e.g. Windows ``::`` in names):
                    # keep the payload in the artifact tar with a true name.
                    inner = tar.extractfile(member)
                    if inner is not None:
                        self.extra_members.append(
                            ("file", "/" + clean, getattr(member, "mode", 0o644),
                             inner.read()))
                installed.append("/" + clean)
        return installed

    def pack_extra_members(self, tar: tarfile.TarFile) -> None:
        """Emit members the host could not write to disk into a tar (artifact)."""
        for entry in self.extra_members:
            kind, name, mode, payload = entry
            clean = name.lstrip("/")
            if kind == "symlink":
                info = tarfile.TarInfo(clean)
                info.type = tarfile.SYMTYPE
                info.linkname = payload
                info.mode = 0o777 & (mode or 0o777)
                tar.addfile(info)
            else:
                info = tarfile.TarInfo(clean)
                info.size = len(payload)
                info.mode = stat.S_IMODE(mode or 0o644)
                info.type = tarfile.REGTYPE
                tar.addfile(info, __import__("io").BytesIO(payload))

    # -- dpkg database ---------------------------------------------------

    def write_dpkg_state(self, selected: Iterable, contents: dict) -> None:
        """Write /var/lib/dpkg/status and per-package info files."""
        for rel in DPKG_SCHEMA_DIRS:
            os.makedirs(self._path(rel), exist_ok=True)
        arch_file = self._path("var/lib/dpkg/arch")
        with open(arch_file, "w", encoding="utf-8") as handle:
            handle.write(self.arch + "\n")
        for rel in ("var/lib/dpkg/diversions", "var/lib/dpkg/statoverride"):
            if not os.path.lexists(self._path(rel)):
                with open(self._path(rel), "w", encoding="utf-8") as handle:
                    handle.write("")

        status_path = self._path("var/lib/dpkg/status")
        with open(status_path, "w", encoding="utf-8") as handle:
            for record in selected:
                content = contents.get(record.package)
                if content is None:
                    continue
                control = content.control or {}
                handle.write(self._status_stanza(record, control))
                self._write_info(record.package, content, control)

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
        if content.conffiles:
            with open(info + ".conffiles", "w", encoding="utf-8") as handle:
                handle.write("\n".join(conf for conf in content.conffiles) + "\n")

    # -- base system files ---------------------------------------------

    def write_base_config(self, distro: str, mirror: str, security_mirror: str,
                          hostname: str = "busteros") -> None:
        def put(rel: str, text: str, mode: int = 0o644):
            target = self._path(rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(text)
            try:
                os.chmod(target, stat.S_IMODE(mode))
            except OSError:
                pass

        put("etc/hostname", hostname + "\n")
        put("etc/hosts", identity.hosts(hostname))
        put("etc/nsswitch.conf", identity.nsswitch_conf())
        put("etc/fstab", identity.fstab(), 0o644)
        put("etc/apt/sources.list", identity.apt_sources(
            self.arch, mirror.rstrip("/"), distro, security_mirror.rstrip("/")))
        put("etc/default/locale", "LANG=C.UTF-8\nLC_ALL=C.UTF-8\n")
        put("etc/timezone", "Etc/UTC\n")
        put("etc/environment", f"PATH=\"/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\"\n")
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
        with open(self._path("etc/passwd"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

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
        with open(self._path("etc/group"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    def write_shadow(self) -> None:
        shadow = [
            ("root", "!x", "19701", "0", "99999", "7", "", "", ""),
            ("daemon", "!", "", "", "", "", "", "", ""),
            ("secret", "!", "19701", "0", "99999", "7", "", "", ""),
        ]
        # derive remaining users from /etc/passwd with locked password
        r = self._path("etc/passwd")
        if os.path.isfile(r):
            with open(r, encoding="utf-8") as handle:
                for line in handle:
                    name = line.split(":", 1)[0]
                    if name and name not in {s[0] for s in shadow}:
                        shadow.append((name, "!", "", "", "", "", "", "", ""))
        lines = [":".join(s) for s in shadow]
        with open(self._path("etc/shadow"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    # -- Buster system layer --------------------------------------------

    def install_buster(self, source_dir: str, version: str = None,
                       install_path: str = "/var/lib/buster") -> None:
        """Copy the Buster python runtime into the OS and wire system files."""
        version = version or get_version()
        lib_dir = self._path("opt/buster/lib")
        os.makedirs(lib_dir, exist_ok=True)
        src = os.path.join(source_dir, "buster")
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(lib_dir, "buster"),
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

        # python .pth so `python3 -m buster` works system-wide
        dist_packages = self._find_dist_packages()
        pth = os.path.join(dist_packages, "buster.pth")
        os.makedirs(dist_packages, exist_ok=True)
        with open(pth, "w", encoding="utf-8") as handle:
            handle.write("/opt/buster/lib\n")

        self._write_buster_services()
        self._write_buster_config(install_path)
        self._write_buster_identity(version)

        for rel in [
            "var/lib/buster/state", "var/lib/buster/memory",
            "var/cache/buster", "var/log/buster", "run/buster",
            "opt/buster/bin", "home/buster", "srv/buster",
        ]:
            os.makedirs(self._path(rel), exist_ok=True)

        # CLI wrappers
        self._write_exec("usr/bin/buster", "#!/bin/sh\nexec /usr/bin/python3 -m buster.cli \"$@\"\n")
        self._write_exec("usr/bin/busterctl",
                         "#!/bin/sh\nexport BUSTER_INSTALL=/var/lib/buster\nexec /usr/bin/python3 -m buster.system.busterctl \"$@\"\n")

        # environment + logrotate
        self._write_text("etc/profile.d/buster.sh", identity.buster_profile_sh())
        self._write_text("etc/logrotate.d/buster",
                         "/var/log/buster/*.log {\n    weekly\n    rotate 4\n    compress\n    missingok\n    notifempty\n}\n")

    def _find_dist_packages(self) -> str:
        for candidate in ("usr/lib/python3/dist-packages",):
            if os.path.isdir(self._path(candidate)) or True:
                return self._path(candidate)
        return self._path("usr/lib/python3/dist-packages")

    def _write_buster_services(self) -> None:
        self._write_text("etc/systemd/system/buster.service", identity.systemd_unit())
        init = self._path("etc/init.d/buster")
        os.makedirs(os.path.dirname(init), exist_ok=True)
        with open(init, "w", encoding="utf-8") as handle:
            handle.write(identity.sysvinit_script())
        try:
            os.chmod(init, 0o755)
        except OSError:
            pass

    def _write_buster_config(self, install_path: str) -> None:
        cfg_dir = self._path("etc/buster")
        os.makedirs(cfg_dir, exist_ok=True)
        with open(os.path.join(cfg_dir, "config.json"), "w", encoding="utf-8") as handle:
            handle.write(identity.buster_config_json(install_path=install_path))
        with open(os.path.join(cfg_dir, "buster.env"), "w", encoding="utf-8") as handle:
            handle.write(f"BUSTER_INSTALL={install_path}\n")

    def _write_buster_identity(self, version: str) -> None:
        meta = self._path("usr/share/buster")
        os.makedirs(meta, exist_ok=True)
        with open(os.path.join(meta, "VERSION"), "w", encoding="utf-8") as handle:
            handle.write(version + "\n")
        with open(os.path.join(meta, "identity.json"), "w", encoding="utf-8") as handle:
            handle.write(identity.identity_json(
                version, self.arch, "debian", "bookworm"))

    def write_os_release(self, version: str = None) -> None:
        version = version or get_version()
        usr_lib = self._path("usr/lib/os-release")
        os.makedirs(os.path.dirname(usr_lib), exist_ok=True)
        with open(usr_lib, "w", encoding="utf-8") as handle:
            handle.write(identity.os_release(version))
        osrc = self._path("etc/os-release")
        if os.path.lexists(osrc):
            try:
                os.unlink(osrc)
            except OSError:
                pass
        try:
            os.symlink("../usr/lib/os-release", osrc)
        except OSError:
            # fallback: duplicate the file so identity is still present
            shutil.copyfile(usr_lib, osrc)
        with open(self._path("etc/issue"), "w", encoding="utf-8") as handle:
            handle.write(identity.issue(version))

    # -- helpers ----------------------------------------------------------

    def _write_text(self, rel: str, text: str, mode: int = 0o644) -> None:
        target = self._path(rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(text)
        try:
            os.chmod(target, stat.S_IMODE(mode))
        except OSError:
            pass

    def _write_exec(self, rel: str, text: str) -> None:
        self._write_text(rel, text, 0o755)