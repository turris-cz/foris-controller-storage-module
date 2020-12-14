import logging
import os
import shlex

from foris_controller_backends.uci import UciBackend, get_option_named, store_bool, parse_bool
from foris_controller_backends.cmdline import BaseCmdLine
from foris_controller_backends.files import BaseFile, inject_file_root, path_exists
from foris_controller.exceptions import (
    FailedToParseFileContent,
    FailedToParseCommandOutput,
    BackendCommandFailed,
    UciException,
)

logger = logging.getLogger(__name__)


class SettingsUci(BaseCmdLine, BaseFile):
    def get_state(self):

        with UciBackend() as backend:
            data = backend.read("storage")

        old_uuid = ""
        uuid = get_option_named(data, "storage", "srv", "uuid", "")
        raid = get_option_named(data, "storage", "srv", "raid", "custom")
        persistent_logs = parse_bool(get_option_named(data, "storage", "srv", "syslog", "1"))
        # get mountpoint of /srv
        srv_mount_point = self._trigger_and_parse(["stat", "-c", "%m", "/srv"], r"\s*(.*)\s*")

        try:
            old_device = self._read_and_parse(
                "/proc/mounts", r"^(/dev/[^ ]*|ubi[^ ]*) {} .*".format(srv_mount_point)
            )
        except FailedToParseFileContent:
            old_device = "none"
            old_uuid = "broken"

        if srv_mount_point == "/":
            old_uuid = "rootfs"
        # Read devices only if needed and only if there is no disk operation in progress
        elif old_uuid == "" and not os.path.isfile(
            inject_file_root("/tmp/storage_plugin/formating")
        ):
            # use blkid to obtain old uuid
            cmd = ["blkid", old_device]
            try:
                blkid, old_uuid = self._trigger_and_parse(
                    cmd, r'^/dev/([^:]*):.* UUID="([^"]*)".* TYPE="([^"]*)".*', (0, 2)
                )
            except (FailedToParseCommandOutput) as exc:
                raise LookupError(
                    "Can't get UUID for device '{}' from '{}'!".format(old_device, exc.message)
                )
            except (BackendCommandFailed) as exc:
                raise LookupError(
                    "Can't get UUID for device '{}'. Command '{}' has failed! ({})".format(
                        old_device, " ".join(cmd), exc
                    )
                )

        state = "none"
        if os.path.isfile(inject_file_root("/tmp/storage_plugin/state")):
            with open(inject_file_root("/tmp/storage_plugin/state")) as fl:
                state = fl.readline().strip()

        return {
            "uuid": uuid,
            "old_uuid": old_uuid,
            "old_device_desc": old_device,
            "blocked": os.path.isfile(inject_file_root("/tmp/storage_plugin/formating")),
            "state": state,
            "raid": raid,
            "persistent_logs": persistent_logs,
        }

    def get_srv(self):
        """ Function is depracated, kept for compatibility with Foris. """
        state = self.get_state()

        return {
            "uuid": state["uuid"],
            "old_uuid": state["old_uuid"],
            "old_device": state["old_device_desc"],
            "formating": state["blocked"],
            "state": state["state"],
            "persistent_logs": state["persistent_logs"]
        }

    def update_srv(self, srv):
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


class DriveManager(BaseCmdLine, BaseFile):
    def _find_blkid_bin(self) -> str:
        """ finds fullpath to blkid binary """
        for dirpath in [e for e in os.environ.get("PATH", "").split(":") if e.startswith("/")] + [
            "/usr/sbin"
        ]:
            path = os.path.join(dirpath, "blkid")
            if path_exists(path):
                return path

        return "/usr/sbin/blkid"  # default path

    def get_drives(self):
        ret = []
        # Would block during formating
        if os.path.isfile(inject_file_root("/tmp/storage_plugin/formating")):
            return {"drives": ret}

        drive_dir = "/sys/class/block"

        for dev in os.listdir(inject_file_root(drive_dir)):
            # skip some device
            if not dev.startswith("sd"):
                continue

            # is device mounted somewhere
            mount = ""
            try:
                mount = self._read_and_parse(
                    "/proc/mounts", r"^/dev/{} (/[^ ]*) .*".format(dev)
                )
            except FailedToParseFileContent:
                pass

            # skip devices mounted as root
            if mount == "/":
                continue

            retval, stdout, _ = self._run_command(self._find_blkid_bin(), "/dev/%s" % dev)
            if retval == 0:
                # found using blkid
                # parse blockid output
                # remove "/dev/...:"
                stdout = stdout.decode("utf-8")
                _, variables = stdout.split(":", 1)

                # -> ['TYPE=brtfs', ...]
                parsed = shlex.split(variables)

                # -> {"TYPE": "btrfs", ...}
                parsed = dict([e.split("=", 1) for e in parsed if "=" in e])

                uuid = parsed.get("UUID", "")
                fs = parsed.get("TYPE", "")

                # prepare description data
                label = parsed.get("LABEL", "")
            else:
                fs = ""
                uuid = ""
                label = ""
            try:
                vendor = self._file_content("/sys/class/block/%s/device/vendor" % dev).strip()
            except IOError:
                vendor = ""
            try:
                model = self._file_content("/sys/class/block/%s/device/model" % dev).strip()
            except IOError:
                model = ""
            size = int(self._file_content("/sys/class/block/%s/size" % dev).strip())
            size = size / float(2 * (1024 ** 2))
            size = "{0:,.1f}".format(size).replace(",", " ") if size > 0.0 else "0"

            # build description
            description = " - ".join([e for e in [label, vendor] if e])
            description = " ".join([e for e in [description, model] if e])
            description = (
                "%s (%s GiB)" % (description, size) if description else "Size %s GiB" % size
            )

            ret.append({"dev": dev, "description": description, "fs": fs, "uuid": uuid})
        return {"drives": ret}

    def prepare_srv_drive(self, srv):
        if srv.get("raid", False):
            with UciBackend() as backend:
                backend.set_option("storage", "srv", "raid", srv["raid"])
        retval, _, _ = self._run_command("/usr/libexec/format_and_set_srv.sh", *srv["drives"])
        return {"result": retval == 0}
