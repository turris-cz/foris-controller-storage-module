#
# foris-controller-storage-module
# Copyright (C) 2018-2021 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA
#

import pytest
import textwrap

from .conftest import file_root, CMDLINE_SCRIPT_ROOT

from foris_controller_testtools.fixtures import (
    infrastructure,
    uci_configs_init,
    file_root_init,
    FILE_ROOT_PATH,
)

from foris_controller_testtools.utils import FileFaker


@pytest.fixture(params=["/", "/srv"], ids=["srv_not_mounted", "srv_mounted"], scope="function")
def stat_cmd(request):
    content = (
        """\
        #!/bin/sh
        echo %s
    """
        % request.param
    )
    with FileFaker(CMDLINE_SCRIPT_ROOT, "/usr/bin/stat", True, textwrap.dedent(content)) as f:
        yield f, request.param


MOUNTS = {
    "mounts1": """\
/dev/mmcblk0p1 / btrfs rw,noatime,ssd,space_cache,commit=5,subvolid=886,subvol=/@ 0 0
proc /proc proc rw,noatime 0 0
sysfs /sys sysfs rw,noatime 0 0
none /sys/fs/cgroup cgroup rw,relatime,cpuset,cpu,cpuacct,blkio,memory,devices,freezer,net_cls,pids 0 0
tmpfs /tmp tmpfs rw,nosuid,nodev,noatime 0 0
tmpfs /dev tmpfs rw,relatime,size=512k,mode=755 0 0
devpts /dev/pts devpts rw,relatime,mode=600,ptmxmode=000 0 0
debugfs /sys/kernel/debug debugfs rw,noatime 0 0
mountd(pid3648) /tmp/run/mountd autofs rw,relatime,fd=5,pgrp=3644,timeout=60,minproto=5,maxproto=5,indirect 0 0
""",
    "mounts2": """\
/dev/mmcblk0p1 / btrfs rw,noatime,ssd,space_cache,commit=5,subvolid=886,subvol=/@ 0 0
proc /proc proc rw,noatime 0 0
sysfs /sys sysfs rw,noatime 0 0
none /sys/fs/cgroup cgroup rw,relatime,cpuset,cpu,cpuacct,blkio,memory,devices,freezer,net_cls,pids 0 0
tmpfs /tmp tmpfs rw,nosuid,nodev,noatime 0 0
tmpfs /dev tmpfs rw,relatime,size=512k,mode=755 0 0
devpts /dev/pts devpts rw,relatime,mode=600,ptmxmode=000 0 0
debugfs /sys/kernel/debug debugfs rw,noatime 0 0
mountd(pid3648) /tmp/run/mountd autofs rw,relatime,fd=5,pgrp=3644,timeout=60,minproto=5,maxproto=5,indirect 0 0
/dev/sda /srv btrfs rw,relatime,space_cache,subvolid=5,subvol=/ 0 0
""",
    "mounts3": """\
/dev/mmcblk0p1 / btrfs rw,noatime,ssd,space_cache,commit=5,subvolid=886,subvol=/@ 0 0
proc /proc proc rw,noatime 0 0
sysfs /sys sysfs rw,noatime 0 0
none /sys/fs/cgroup cgroup rw,relatime,cpuset,cpu,cpuacct,blkio,memory,devices,freezer,net_cls,pids 0 0
tmpfs /tmp tmpfs rw,nosuid,nodev,noatime 0 0
tmpfs /dev tmpfs rw,relatime,size=512k,mode=755 0 0
devpts /dev/pts devpts rw,relatime,mode=600,ptmxmode=000 0 0
debugfs /sys/kernel/debug debugfs rw,noatime 0 0
mountd(pid3648) /tmp/run/mountd autofs rw,relatime,fd=5,pgrp=3644,timeout=60,minproto=5,maxproto=5,indirect 0 0
/dev/sdb /srv btrfs rw,relatime,space_cache,subvolid=5,subvol=/ 0 0
""",
}


@pytest.fixture(scope="function")
def blkid_sda_ok_cmd(request):
    content = """\
        #!/bin/sh
        if [ "$1" != "/dev/sda" ] ; then
            exit 1
        elif [ "$2" = "-s" ] && [ "$3" = UUID ] && [ "$4" = "-o" ] && [ "$5" = "value" ]; then
            echo "fb002a7a-7504-4f08-882b-09eebb2b26e6"
        else
            echo '/dev/sda: LABEL="srv" UUID="fb002a7a-7504-4f08-882b-09eebb2b26e6" UUID_SUB="20ce89eb-6720-4d40-8b48-c114153b1202" TYPE="btrfs"'
            echo '/dev/sdb: LABEL="s\\"=:v" UUID="fb002a7a-7504-4f08-882b-eeeeeeeeeeee" UUID_SUB="20ce89eb-6720-4d40-8b48-eeeeeeeeeeee" TYPE="btrfs"'
        fi
    """
    with FileFaker(CMDLINE_SCRIPT_ROOT, "/usr/sbin/blkid", True, textwrap.dedent(content)) as f:
        yield f


@pytest.fixture(params=MOUNTS.keys(), scope="function")
def mounts_file(request):
    with FileFaker(FILE_ROOT_PATH, "/proc/mounts", False, MOUNTS[request.param]) as f:
        yield f, request.param


@pytest.fixture(params=[True, False], ids=["formatting_yes", "formatting_no"], scope="function")
def formatting_file(request):
    if request.param:
        with FileFaker(FILE_ROOT_PATH, "/tmp/storage_plugin/formating", False, ""):
            yield request.param
    else:
        yield request.param


@pytest.fixture(scope="function")
def prepare_srv_drive_sh_cmd(request):
    content = """\
        #!/bin/sh
        exit 0
    """
    with FileFaker(
        CMDLINE_SCRIPT_ROOT, "/usr/libexec/format_and_set_srv.sh", True, textwrap.dedent(content)
    ) as f:
        yield f


def test_get_settings(
    file_root_init,
    uci_configs_init,
    infrastructure,
    stat_cmd,
    mounts_file,
    blkid_sda_ok_cmd,
    formatting_file,
):
    _, srv_mount = stat_cmd
    _, mounts_file_id = mounts_file
    res = infrastructure.process_message(
        {"module": "storage", "action": "get_settings", "kind": "request"}
    )

    assert res["data"].keys() >= {"formating"}

    if infrastructure.backend_name != "mock":
        assert res["data"]["formating"] is formatting_file


def test_get_state(
    file_root_init,
    uci_configs_init,
    infrastructure,
    stat_cmd,
    mounts_file,
    blkid_sda_ok_cmd,
    formatting_file,
):
    _, srv_mount = stat_cmd
    _, mounts_file_id = mounts_file
    res = infrastructure.process_message(
        {"module": "storage", "action": "get_state", "kind": "request"}
    )

    assert res["data"].keys() >= {"blocked"}

    if infrastructure.backend_name != "mock":
        assert res["data"]["blocked"] is formatting_file


def test_get_drives(
    file_root_init, uci_configs_init, infrastructure, blkid_sda_ok_cmd, mounts_file
):
    res = infrastructure.process_message(
        {"module": "storage", "action": "get_drives", "kind": "request"}
    )
    assert "data" in res
    assert "drives" in res["data"]


def test_prepare_srv_drive(
    file_root_init, uci_configs_init, infrastructure, prepare_srv_drive_sh_cmd
):
    res = infrastructure.process_message(
        {
            "module": "storage",
            "action": "prepare_srv_drive",
            "kind": "request",
            "data": {"drives": ["sda"]},
        }
    )
    assert "errors" not in res


def test_update_srv(
    file_root_init, uci_configs_init, infrastructure, prepare_srv_drive_sh_cmd
):
    res = infrastructure.process_message(
        {
            "module": "storage",
            "action": "update_srv",
            "kind": "request",
            "data": {"uuid": "fb002a7a-7504-4f08-882b-09eebb2b26e6"},
        }
    )
    assert "data" in res
    assert "result" in res["data"]
    assert res["data"]["result"]


@pytest.mark.parametrize("state", [True, False])
def test_update_settings(
    file_root_init,
    uci_configs_init,
    infrastructure,
    stat_cmd,
    mounts_file,
    blkid_sda_ok_cmd,
    formatting_file,
    state
):
    _, srv_mount = stat_cmd
    _, mounts_file_id = mounts_file

    res = infrastructure.process_message(
        {
            "module": "storage",
            "action": "update_settings",
            "data": {
                "persistent_logs": state
            }
        }
    )

    assert "errors" not in res.keys()
    assert res["data"]["result"]

    res2 = infrastructure.process_message(
        {"module": "storage", "action": "get_settings", "kind": "request"}
    )

    assert "errors" not in res2.keys()
    assert res2["data"]["persistent_logs"] is state
