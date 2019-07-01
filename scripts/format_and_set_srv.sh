#!/bin/sh
DISK="$1"
DEBUG="$(uci -q get storage.srv.debug | egrep '(1|yes|on)')"

die() {
    echo -e "disk: $DISK\nmkfs: $RES\nuuid: $UUID\nsrv: $SRV\nsrv_dev: $SRV_DEV\nsrv_uuid: $SRV_UUID" >&2
    create_notification -s error "_($1)"
    [ "`cat /tmp/formating`" \!= "$DISK" ] || rm -f /tmp/formating
    exit 2
}

if [ -z "$DISK" ]; then
    echo "$0 disk"
    exit 1
fi

[ -z "$DEBUG" ] || set -x
[ -z "$DEBUG" ] || exec 2>> /tmp/storage_debug

# Making sure that Foris will return fast and we wouldn't block it
if [ -z "$FORKED" ]; then
    export FORKED=1
    if [ -f /tmp/formating ]; then
        DISK="none"
        die "Another formatting job currently in progress, not switching to new drive."
    fi
    echo "$DISK" > /tmp/formating
    "$0" "$DISK" &
    exit 0
else
    sleep 2
fi

# Unmount everything we might need
umount -fl "$DISK" > /dev/null 2>&1
if expr "$DISK" : '.*[a-z]$' > /dev/null; then
    for i in "$DISK"[0-9]; do
        umount -fl "$DISK" > /dev/null 2>&1
    done
fi

# Try formating the drive
RES="$(mkfs.btrfs -f -L srv "$DISK" 2>&1 || echo FAILFAILFAIL)"
[ -z "$(echo "$RES" | grep FAILFAILFAIL)" ] || die ")_(Formatting drive failed, try unpluging it and repluging it in again.

Technical details:)_(
$(echo "$RES" | grep -v FAILFAILFAIL)"
if expr "$DISK" : '.*[a-z]$' > /dev/null; then
    partx -d "$DISK"
fi

# Try to get UUID
UUID="$(echo "$RES" | sed -n 's|Filesystem UUID: \([0-9a-f-]*\)|\1|p')"
[ -n "$UUID" ] || UUID="$(blkid "$DISK" | sed -n 's|.* UUID="\([0-9a-f-]*\)" .*|\1|p')"
[ -n "$UUID" ] || die "Can't get UUID of your newly formatted drive."

# Prepare snapshot on the drive
mkdir -p /tmp/storage_plugin_formating
mount -t btrfs "$DISK" /tmp/storage_plugin_formating || die "Can't mount newly formatted drive."
btrfs subvol create /tmp/storage_plugin_formating/@ || die "Can't create @ submodule."
umount /tmp/storage_plugin_formating
rmdir /tmp/storage_plugin_formating

# Commit configuration
SRV="$(stat -c %m /srv/)"
SRV_DEV=""
SRV_UUID=""
if [ -n "$(cat /proc/mounts | grep '^ubi[^[:blank:]]* '"$SRV"' .*')" ] || \
   [ -n "$(cat /proc/mounts | grep '^tmpfs /srv .*')" ]; then
    SRV_UUID="rootfs"
else
    [ -z "$SRV" ] || SRV_DEV="$(cat /proc/mounts | sed -n 's|^\(/dev/[^[:blank:]]*\) '"$SRV"' .*|\1|p')"
    [ -z "$SRV_DEV" ] || SRV_UUID="$(blkid "$SRV_DEV" | sed -n 's|.* UUID="\([0-9a-f-]*\)" .*|\1|p')"
fi
[ -n "$SRV_UUID" ] || die "Can't find your current srv location"
uci set storage.srv.uuid="$UUID"
uci set storage.srv.old_uuid="$SRV_UUID"
uci commit storage
TEXT="Your new disk for storing data has been setup successfully. All you need to do now is to reboot your router for changes to take effect. Be aware that if you have some local data stored on your current storage, those will get moved during reboot, so your next reboot might take quite some time."
create_notification -s restart "_($TEXT)"
[ "`cat /tmp/formating`" \!= "$DISK" ] || rm -f /tmp/formating
