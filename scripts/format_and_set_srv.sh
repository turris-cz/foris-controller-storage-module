#!/bin/sh
die() {
    echo -e "mkfs: $RES\nuuid: $UUID\nsrv: $SRV\nsrv_dev: $SRV_DEV\nsrv_uuid: $SRV_UUID" > /tmp/storage_debug
    create_notification -s error "$1" "$1"
    exit 2
}

if [ -z "$1" ]; then
    echo "$0 disk"
    exit 1
fi

# Making sure that Foris will return fast and we wouldn't block it
if [ -z "$FORKED" ]; then
    export FORKED=1
    "$0" "$1" &
    exit 0
else
    sleep 2
fi

DISK="$1"
umount -fl "$1"
RES="$(mkfs.ext4 -q -F -F -L srv -U random -e continue "$1" 2>&1 || echo FAILFAILFAIL)"
[ -z "$(echo "$RES" | grep FAILFAILFAIL)" ] || die "Formating drive $1 failed, try unpluging it and repluging it in again."
UUID="$(echo "$RES" | sed -n 's|Filesystem UUID: \([0-9a-f-]*\)|\1|p')"
[ -n "$UUID" ] || UUID="$(blkid "$1" | sed -n 's|.* UUID="\([0-9a-f-]*\)" .*|\1|p')"
[ -n "$UUID" ] || die "Can't get UUID of your newly formated drive"
SRV="$(stat -c %m /srv/)"
SRV_DEV=""
[ -z "$SRV" ] || SRV_DEV="$(cat /proc/mounts | sed -n 's|^\(/dev/[^[:blank:]]*\) '"$SRV"' .*|\1|p')"
SRV_UUID=""
[ -z "$SRV_DEV" ] || SRV_UUID="$(blkid "$SRV_DEV" | sed -n 's|.* UUID="\([0-9a-f-]*\)" .*|\1|p')"
[ -n "$SRV_UUID" ] || die "Can't find your current srv location"
uci set storage.srv.uuid="$UUID"
uci set storage.srv.old_uuid="$SRV_UUID"
uci commit storage
TEXT="Your new disk for storing data has been setup successfully. All you need to do now is to reboot your router for changes to take effect. Be aware that if you have some local data stored on your current storage, those will get moved during reboot, so your next reboot might take quite some time."
create_notification -s restart "$TEXT" "$TEXT"
