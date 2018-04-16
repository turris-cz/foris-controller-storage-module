#!/bin/sh
DISK="$1"

die() {
    echo -e "mkfs: $RES\nuuid: $UUID\nsrv: $SRV\nsrv_dev: $SRV_DEV\nsrv_uuid: $SRV_UUID" > /tmp/storage_debug
    create_notification -s error "_($1)"
    [ "`cat /tmp/formating`" \!= "$DISK" ] || rm -f /tmp/formating
    exit 2
}

if [ -z "$1" ]; then
    echo "$0 disk"
    exit 1
fi

# Making sure that Foris will return fast and we wouldn't block it
if [ -z "$FORKED" ]; then
    export FORKED=1
    if [ -f /tmp/formating ]; then
        DISK="none"
        die "Another formatting job currently in progress, not switching to new drive."
    fi
    echo "$DISK" > /tmp/formating
    "$0" "$1" &
    exit 0
else
    sleep 2
fi

DISK="$1"
umount -fl "$1"
if expr "$1" : '^.*[a-z]$' > /dev/null; then
    for i in "$1"[0-9]; do
        umount -fl "$i" || true
    done
fi
RES="$(mkfs.ext4 -q -F -F -L srv -U random -e continue "$1" 2>&1 || echo FAILFAILFAIL)"
[ -z "$(echo "$RES" | grep FAILFAILFAIL)" ] || die "Formatting drive failed, try unpluging it and repluging it in again."
UUID="$(echo "$RES" | sed -n 's|Filesystem UUID: \([0-9a-f-]*\)|\1|p')"
[ -n "$UUID" ] || UUID="$(blkid "$1" | sed -n 's|.* UUID="\([0-9a-f-]*\)" .*|\1|p')"
[ -n "$UUID" ] || die "Can't get UUID of your newly formatted drive."
SRV="$(stat -c %m /srv/)"
SRV_DEV=""
SRV_UUID=""
if [ -n "$(cat /proc/mounts | grep '^\(ubi[^[:blank:]]*\) '"$SRV"' .*')" ]; then
    SRV_UUID="rootfs"
else
    [ -z "$SRV" ] || SRV_DEV="$(cat /proc/mounts | sed -n 's|^\(/dev/[^[:blank:]]*\) '"$SRV"' .*|\1|p')"
    [ -z "$SRV_DEV" ] || SRV_UUID="$(blkid "$SRV_DEV" | sed -n 's|.* UUID="\([0-9a-f-]*\)" .*|\1|p')"
fi
[ -n "$SRV_UUID" ] || die "Can't find your current srv location"
uci set storage.srv.uuid="$UUID"
uci set storage.srv.old_uuid="$SRV_UUID"
uci commit storage
if expr "$1" : '^.*[a-z]$' > /dev/null; then
    partx -d "$1"
fi
TEXT="Your new disk for storing data has been setup successfully. All you need to do now is to reboot your router for changes to take effect. Be aware that if you have some local data stored on your current storage, those will get moved during reboot, so your next reboot might take quite some time."
create_notification -s restart "_($TEXT)"
[ "`cat /tmp/formating`" \!= "$DISK" ] || rm -f /tmp/formating
