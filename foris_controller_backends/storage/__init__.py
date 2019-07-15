import logging
import subprocess
import re
import os
import shlex

from foris_controller_backends.uci import UciBackend, get_option_named
from foris_controller_backends.cmdline import BaseCmdLine
from foris_controller_backends.files import BaseFile, inject_file_root
from foris_controller.exceptions import (
    FailedToParseFileContent, FailedToParseCommandOutput, BackendCommandFailed
)

logger = logging.getLogger(__name__)


class SettingsUci(BaseCmdLine, BaseFile):
    def get_srv(self):

        with UciBackend() as backend:
            data = backend.read("storage")

        old_uuid = ""
        uuid = get_option_named(data, "storage", "srv", "uuid", "")
        # get mountpoint of /srv
        srv_mount_point = self._trigger_and_parse(
            ['stat', '-c', '%m', '/srv'], r"\s*(.*)\s*"
        )

        try:
            old_device = self._read_and_parse(
                "/proc/mounts",
                r'^(/dev/[^ ]*|ubi[^ ]*) {} .*'.format(srv_mount_point)
            )
        except FailedToParseFileContent:
            old_device = "none"
            old_uuid = "broken"

        if srv_mount_point == "/":
            old_uuid = "rootfs"
        elif old_uuid == "":
            # use blkid to obtain old uuid
            cmd = ['blkid', old_device]
            try:
                blkid, old_uuid = self._trigger_and_parse(
                    cmd,
                    r'^/dev/([^:]*):.* UUID="([^"]*)".* TYPE="([^"]*)".*',
                    (0, 2),
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

        return {
            'uuid': uuid,
            'old_uuid': old_uuid,
            'old_device': old_device,
            'formating': os.path.isfile(inject_file_root('/tmp/formating')),
            'nextcloud_installed': os.path.isfile(inject_file_root('/srv/www/nextcloud/index.php')),
            'nextcloud_configuring': os.path.isfile(inject_file_root('/tmp/nextcloud_configuring')),
            'nextcloud_configured': os.path.isfile(inject_file_root('/srv/www/nextcloud/config/config.php'))
        }

    def update_srv(self, srv):

        with UciBackend() as backend:
            backend.set_option("storage", "srv", "uuid", srv['uuid'])
            backend.set_option("storage", "srv", "old_uuid", srv['old_uuid'])

        return True

class SoftwareManager(BaseCmdLine, BaseFile):
    def configure_nextcloud(self, creds):
        data = self._run_command_and_check_retval(
            ["nextcloud_install", "--batch", creds['credentials']['login'], creds['credentials']['password']],
            0
        )
        return { 'result': data }

class DriveManager(BaseCmdLine, BaseFile):
    def get_drives(self):
        ret = []
        drive_dir = '/sys/class/block'

        for dev in os.listdir(inject_file_root(drive_dir)):
            # skip some device
            if not dev.startswith("sd"):
                continue

            retval, stdout, _ = self._run_command('blkid', "/dev/%s" % dev)
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
            size = "{0:,.1f}".format(size).replace(',', ' ') if size > 0.0 else "0"

            # build description
            description = " - ".join([e for e in [label, vendor] if e])
            description = " ".join([e for e in [description, model] if e])
            description = "%s (%s GiB)" % (description, size) if description \
                else "Size %s GiB" % size

            ret.append({"dev": dev, "description": description, "fs": fs, "uuid": uuid})
        return {"drives": ret}

    def prepare_srv_drive(self, srv):
        self._run_command_and_check_retval(
            ["/usr/libexec/format_and_set_srv.sh", "/dev/%s" % srv['drive']],
            0
        )
        return {}
