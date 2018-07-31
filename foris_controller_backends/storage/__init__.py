import logging
import subprocess
import re
import os

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

        uuid = get_option_named(data, "storage", "srv", "uuid", "")
        # get mountpoint of /srv
        srv_mount_point = self._trigger_and_parse(
            ['/usr/bin/stat', '-c', '%m', '/srv'], r"\s*(.*)\s*"
        )

        try:
            old_device = self._read_and_parse(
                "/proc/mounts",
                r'^(/dev/[^ ]*|ubi[^ ]*) {} .*'.format(srv_mount_point)
            )
        except FailedToParseFileContent:
            raise LookupError(
                "Can't find device that mounts as '{}' and thus can't decide what provides /srv!"
                .format(srv_mount_point)
            )

        if srv_mount_point == "/":
            old_uuid = "rootfs"
        else:
            # use blkid to obtain old uuid
            try:
                blkid, old_uuid = self._trigger_and_parse(
                    ['/usr/sbin/blkid', old_device],
                    r'^/dev/([^:]*):.* UUID="([^"]*)".* TYPE="([^"]*)".*',
                    (0, 2),
                )
            except (BackendCommandFailed, FailedToParseCommandOutput) as exc:
                raise LookupError(
                    "Can't get UUID for device '{}' from '{}'!".format(old_device, exc.message)
                )

        return {
            'uuid': uuid,
            'old_uuid': old_uuid,
            'old_device': old_device,
            'formating': os.path.isfile(inject_file_root('/tmp/formating'))
        }

    def update_srv(self, srv):

        with UciBackend() as backend:
            backend.set_option("storage", "srv", "uuid", srv['uuid'])
            backend.set_option("storage", "srv", "old_uuid", srv['old_uuid'])

        return True

class DriveManager(object):
    def get_drives(self):
        proc = subprocess.Popen(['sh', '-c', 'busybox', 'grep', '-l', '1', '/sys/class/block/*/removable'], stdout=subprocess.PIPE)
        stdout_value = proc.communicate()[0]
        ret = []
        blk_rex = re.compile('^(mmcblk.*|mtd.*)$')
        uuid_rex = re.compile('^/dev/([^:]*):.* UUID="([^"]*)".*')
        label_rex = re.compile('^/dev/([^:]*):.* LABEL="([^"]*)".*')
        type_rex = re.compile('^/dev/([^:]*):.* TYPE="([^"]*)".*')
        for dev in os.listdir('/sys/class/block'):
            grp = blk_rex.match(dev)
            if not grp:
                proc = subprocess.Popen(['blkid', "/dev/{}".format(dev)], stdout=subprocess.PIPE)
                blkid = proc.communicate()[0].strip()
                grp = uuid_rex.match(blkid)
                uuid = ''
                if grp:
                    uuid = grp.group(2)
                grp = type_rex.match(blkid)
                fs = ''
                if grp:
                    fs = grp.group(2)
                grp = label_rex.match(blkid)
                tmp = ''
                if grp:
                    description = grp.group(2)
                else:
                    description = ''
                tmp = ''
                try:
                    fl = open("/sys/class/block/{}/device/vendor".format(dev), 'r')
                except:
                    fl = False
                if fl:
                    tmp = fl.read().strip()
                if tmp:
                    if description:
                        description = '{} - {}'.format(description, tmp)
                    else:
                        description = tmp
                tmp = ''
                try:
                    fl = open("/sys/class/block/{}/device/model".format(dev), 'r')
                except:
                    fl = False
                if fl:
                    tmp = fl.read().strip()
                if tmp:
                    if description:
                        description = '{} {}'.format(description, tmp)
                    else:
                        description = tmp
                tmp = ''
                try:
                    fl = open("/sys/class/block/{}/size".format(dev), 'r')
                except:
                    fl = False
                if fl:
                    tmp = fl.read().strip()
                if tmp:
                    size = int(tmp) / (2 * 1024 * 1024)
                    if(size > 1000):
                        tmp = '{} {}'.format(size / 1000, size % 1000)
                    else:
                        tmp = str(size)
                    if description:
                        description = '{} ({} GiB)'.format(description, tmp)
                    else:
                        description = 'Size {} GiB'.format(tmp)
                ret = ret + [ { "dev": dev, "description": description, "fs": fs, "uuid": uuid } ]
        return { "drives": ret }

    def prepare_srv_drive(self, srv):
        subprocess.Popen(["/usr/libexec/format_and_set_srv.sh", "/dev/{}".format(srv['drive'])])
        return {  }
