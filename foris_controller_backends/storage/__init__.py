import json
import typing
import logging
import os

from foris_controller_backends.uci import UciBackend, get_option_named, parse_bool, store_bool
from foris_controller_backends.cmdline import BaseCmdLine
from foris_controller_backends.files import inject_file_root
from foris_controller.exceptions import UciException

logger = logging.getLogger(__name__)


class SettingsUci(BaseCmdLine):
    def get_state(self):
        """ Get storage state

        Successor of deprecated get_settings()
        """
        with UciBackend() as backend:
            data = backend.read("storage")

        uuid = get_option_named(data, "storage", "srv", "uuid", "")
        raid = get_option_named(data, "storage", "srv", "raid", "custom")
        persistent_logs = parse_bool(get_option_named(data, "storage", "srv", "syslog", "1"))
        # get mountpoint of /srv
        srv_mount_point = self._trigger_and_parse(["stat", "-c", "%m", "/srv"], r"\s*(.*)\s*")

        result = DriveManager().get_device_at_mountpoint(srv_mount_point)
        if result is not None:
            old_device, old_uuid = result
        else:
            old_device = "none"
            old_uuid = "broken"

        if srv_mount_point == "/":
            old_uuid = "rootfs"
        elif old_uuid == "" and not os.path.isfile(inject_file_root("/tmp/storage_plugin/formating")):
            raise LookupError(f"Can't get UUID for device '{old_device}'!")

        state = "none"
        if os.path.isfile(inject_file_root("/tmp/storage_plugin/state")):
            with open(inject_file_root("/tmp/storage_plugin/state")) as fl:
                state = fl.readline().strip()

        return {
            "uuid": uuid,
            "old_uuid": old_uuid,
            "using_external": old_uuid not in ("rootfs", "broken"),
            "is_broken": old_uuid == "broken",
            "current_device": old_device,
            "blocked": os.path.isfile(inject_file_root("/tmp/storage_plugin/formating")),
            "state": state,
            "raid": raid,
            "persistent_logs": persistent_logs,
        }

    def get_settings(self):
        """ Get storage settings

        Deprecated function, kept for compatibility with Foris
        Use get_state() in new code
        """
        state = self.get_state()

        return {
            "uuid": state["uuid"],
            "old_uuid": state["old_uuid"],
            "old_device": state["current_device"],
            "formating": state["blocked"],
            "state": state["state"],
            "persistent_logs": state["persistent_logs"]
        }

    def update_srv(self, srv):
        """ Update settings for /srv mountpoint """
        try:
            with UciBackend() as backend:
                backend.add_section("storage", "srv", "srv")
                backend.set_option("storage", "srv", "uuid", srv["uuid"])
            return {"result": True}

        except UciException:
            return {"result": False}

    def update_settings(self, data):
        try:
            with UciBackend() as backend:
                backend.add_section("storage", "srv", "srv")
                backend.set_option("storage", "srv", "syslog", store_bool(data["persistent_logs"]))
            return {"result": True}
        except UciException:
            return {"result": False}


class DriveManager(BaseCmdLine):
    def _run_lsblk(self, device: typing.Optional[str] = None) -> list:
        cmd = [
            "/usr/bin/lsblk",
            "-o", "NAME,PATH,UUID,SIZE,VENDOR,MODEL,LABEL,FSTYPE,MOUNTPOINTS",
            "--bytes", "--json", "--list",
        ]
        if device:
            cmd += ["--nodeps", "/dev/%s" % device]
        retval, stdout, _ = self._run_command(*cmd)
        if retval != 0:
            return []
        try:
            return json.loads(stdout.decode("utf-8")).get("blockdevices", [])
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Failed to parse lsblk output")
            return []

    def get_device_at_mountpoint(self, mountpoint: str) -> typing.Optional[typing.Tuple[str, str]]:
        """Return (device_path, uuid) for the device mounted at mountpoint, or None if not found."""
        for d in self._run_lsblk():
            mountpoints = d.get("mountpoints") or []
            if isinstance(mountpoints, str):
                mountpoints = [mountpoints]
            if mountpoint in [m for m in mountpoints if m]:
                return d.get("path", "none"), d.get("uuid") or ""
        return None

    def get_drives(self):
        # Would block during formating
        if os.path.isfile(inject_file_root("/tmp/storage_plugin/formating")):
            return {"drives": []}

        ret = []
        for d in self._run_lsblk():
            name = d.get("name", "")
            if not name.startswith("sd") and not name.startswith("nvme"):
                continue

            # skip devices mounted as root
            mountpoints = d.get("mountpoints") or []
            if isinstance(mountpoints, str):
                mountpoints = [mountpoints]
            if "/" in mountpoints:
                continue

            uuid = d.get("uuid") or ""

            # We are interested for devices with uuid
            if not uuid:
                continue

            fs = d.get("fstype") or ""
            label = d.get("label") or ""
            vendor = (d.get("vendor") or "").strip()
            model = (d.get("model") or "").strip()
            size_bytes = d.get("size") or 0
            size = size_bytes / (1024.0 ** 3)
            size = "{0:,.1f}".format(size).replace(",", " ") if size > 0.0 else "0"

            description = " - ".join([e for e in [label, vendor] if e])
            description = " ".join([e for e in [description, model] if e])
            description = (
                "%s (%s GiB)" % (description, size) if description else "Size %s GiB" % size
            )

            ret.append({"dev": name, "description": description, "fs": fs, "uuid": uuid})
        return {"drives": ret}

    def prepare_srv_drive(self, srv):
        if srv.get("raid", False):
            with UciBackend() as backend:
                backend.set_option("storage", "srv", "raid", srv["raid"])
        retval, _, _ = self._run_command("/usr/libexec/format_and_set_srv.sh", *srv["drives"])
        return {"result": retval == 0}
