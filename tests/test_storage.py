#
# foris-controller-storage-module
# Copyright (C) 2018-2023 CZ.NIC, z.s.p.o. (http://www.nic.cz/)
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

from .conftest import CMDLINE_SCRIPT_ROOT

from foris_controller_testtools.fixtures import FILE_ROOT_PATH
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


SDA_JSON = (
    '{"name": "sda", "path": "/dev/sda",'
    ' "uuid": "11111111-1111-1111-1111-111111111111",'
    ' "size": 8178892800, "vendor": "Generic ", "model": "Flash Disk",'
    ' "label": "srv", "fstype": "btrfs", "mountpoints": ["/srv"]}'
)
NVME_JSON = (
    '{"name": "nvme0n1", "path": "/dev/nvme0n1",'
    ' "uuid": "22222222-2222-2222-2222-222222222222",'
    ' "size": 7817134080, "vendor": null, "model": null,'
    ' "label": null, "fstype": "btrfs", "mountpoints": [null]}'
)


@pytest.fixture(scope="function")
def lsblk_cmd(request):
    content = """\
        #!/bin/sh
        DEVICE=""
        for arg in "$@"; do
            case "$arg" in
                -*) ;;
                /dev/*) DEVICE="$arg" ;;
            esac
        done
        if [ "$DEVICE" = "/dev/sda" ]; then
            echo '{{"blockdevices": [{sda}]}}'
        elif [ "$DEVICE" = "/dev/nvme0n1" ]; then
            echo '{{"blockdevices": [{nvme}]}}'
        elif [ -n "$DEVICE" ]; then
            echo '{{"blockdevices": []}}'
        else
            echo '{{"blockdevices": [{sda}, {nvme}]}}'
        fi
    """.format(sda=SDA_JSON, nvme=NVME_JSON)
    with FileFaker(CMDLINE_SCRIPT_ROOT, "/usr/bin/lsblk", True, textwrap.dedent(content)) as f:
        yield f


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
    lsblk_cmd,
    formatting_file,
):
    _, srv_mount = stat_cmd
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
    lsblk_cmd,
    formatting_file,
):
    _, srv_mount = stat_cmd
    res = infrastructure.process_message(
        {"module": "storage", "action": "get_state", "kind": "request"}
    )

    assert res["data"].keys() >= {"blocked"}

    if infrastructure.backend_name != "mock":
        assert res["data"]["blocked"] is formatting_file


def test_get_drives(
    file_root_init, uci_configs_init, infrastructure, lsblk_cmd
):
    res = infrastructure.process_message(
        {"module": "storage", "action": "get_drives", "kind": "request"}
    )
    assert "data" in res
    assert "drives" in res["data"]
    if infrastructure.backend_name != "mock":
        # Devices from lsblk_cmd
        assert {"sda", "nvme0n1"} == {e["dev"] for e in res["data"]["drives"]}


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
    lsblk_cmd,
    formatting_file,
    state
):
    _, srv_mount = stat_cmd

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
