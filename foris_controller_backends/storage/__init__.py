import logging
import subprocess
import re
import os

from foris_controller_backends.uci import UciBackend, get_option_named

logger = logging.getLogger(__name__)


class SettingsUci(object):
    def get_srv(self):

        with UciBackend() as backend:
            try:
                data = backend.read("storage")
                uuid = get_option_named(data, "storage", "srv", "uuid")
            except:
                uuid = ""
        old_device = ""
        proc = subprocess.Popen(['stat', '-c', '%m', '/srv'], stdout=subprocess.PIPE)
        mnt = proc.communicate()[0].strip()
        rex = re.compile('^(/dev/[^ ]*|ubi[^ ]*) {} .*'.format(mnt))
        with open('/proc/mounts', 'r') as f:
            for ln in f:
                grp = rex.match(ln)
                if grp:
                    old_device = grp.group(1)
                    break
        if(old_device == ""):
            raise LookupError("Can't find device that mounts as '{}' and thus can't decide what provides /srv!".format(mnt))
        if old_device == "/":
            old_uuid = "rootfs"
        else:
            proc = subprocess.Popen(['blkid', old_device], stdout=subprocess.PIPE)
            blkid = proc.communicate()[0].strip()
            rex = re.compile('^/dev/([^:]*):.* UUID="([^"]*)".* TYPE="([^"]*)".*')
            grp = rex.match(blkid)
            if grp:
                old_uuid = grp.group(2)
            else:
                raise LookupError("Can't get UUID for device '{}' from '{}'!".format(old_device, blkid))
        return { 'uuid': uuid,
                 'old_uuid': old_uuid,
                 'old_device': old_device,
                 'formating': os.path.isfile('/tmp/formating') }

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
