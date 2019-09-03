#!/bin/sh
DEBUG="$(uci -q get storage.srv.debug | egrep '(1|yes|on)')"
UUID="$(uci -q get storage.srv.uuid)"
RAID="$(uci -q get storage.srv.raid)"
FROM_SCRATCH=""
[ -n "$RAID" ] || RAID=single
SRV_MNT_PNT="/srv"

cleanup() {
    umount -fl /tmp/storage_plugin_formating
    rm -f /tmp/storage_state
    rm -f /tmp/formating
}

trap cleanup EXIT TERM

die() {
    echo -e "disk: $DISK\nmkfs: $RES\nuuid: $UUID\nsrv: $SRV\nsrv_dev: $SRV_DEV\nsrv_uuid: $SRV_UUID" >&2
    create_notification -s error "_($1)"
    exit 2
}

set_state() {
    echo "$1" > /tmp/storage_state
}

# Unmount everything we might need
umount_drive() {
   umount -fl "$1" > /dev/null 2>&1
   if expr "$1" : '.*[a-z]$' > /dev/null; then
       for i in "$1"[0-9]; do
           umount -fl "$1" > /dev/null 2>&1
       done
   fi
}

# Reload partition table if needed
reload_partitions() {
   if expr "$1" : '.*[a-z]$' > /dev/null; then
       partx -d "$1"
   fi
}

# Try to format the drive
format_drive() {
   set_state "Fromating the drive"
   RES="$(mkfs.btrfs -f -L srv "$1" 2>&1)"
   [ "$?" = 0 ] || die ")_(Formatting drive failed, try unpluging it and repluging it in again.)

_(Technical details:)_($RES"

   reload_partitions "$1"

   # Try to get UUID
   UUID="$(echo "$RES" | sed -n 's|Filesystem UUID: \([0-9a-f-]*\)|\1|p')"
   [ -n "$UUID" ] || UUID="$(blkid "$1" -s UUID -o value)"
   [ -n "$UUID" ] || die "Can't get UUID of your newly formatted drive."

   # Prepare snapshot on the drive
   mkdir -p /tmp/storage_plugin_formating
   mount -t btrfs "$1" /tmp/storage_plugin_formating || die "Can't mount newly formatted drive."
   btrfs subvol create /tmp/storage_plugin_formating/@ || die "Can't create @ submodule."
   umount /tmp/storage_plugin_formating
   rmdir /tmp/storage_plugin_formating
}

# Does the disk have srv UUID
has_uuid() {
   [ "$(blkid "$1" -s UUID -o value)" = "$UUID" ]
   return $?
}

# Decide how much we want to debug
[ -z "$DEBUG" ] || set -x
if [ "x-d" = "x$1" ]; then
   export FORKED=1
   shift
else
   rm -f /tmp/storage_debug
   [ -z "$DEBUG" ] || exec 2>> /tmp/storage_debug
fi

# Check syntax
if [ "$#" -lt 1 ]; then
    echo "$0 disk"
    exit 1
fi

# Some locking and also storing desired drives
if [ -f /tmp/formating ]; then
    DISK="none"
    die "Another formatting job currently in progress, not switching to new drive."
fi
echo "$@" | sed 's| |\n|g' | sed 's|^\([^/]\)|/dev/\1|' > /tmp/formating

# Run in background by default not to block Foris
if [ -z "$FORKED" ]; then
    export FORKED=1
    "$0" "$@" &
    exit 0
else
    sleep 1
fi
set `cat /tmp/formating`

# Are we are starting from scratch
if [ -z "$UUID" ]; then
   umount_drive "$1"
   format_drive "$1"
   FROM_SCRATCH="yes"
   shift

   # Commit configuration
   SRV="$(stat -c %m /srv/)"
   SRV_DEV=""
   SRV_UUID=""
   if [ -n "$(cat /proc/mounts | grep '^ubi[^[:blank:]]* '"$SRV"' .*')" ] || \
      [ -n "$(cat /proc/mounts | grep '^[^[:blank:]]* /srv tmpfs.*')" ]; then
       SRV_UUID="rootfs"
   else
       [ -z "$SRV" ] || SRV_DEV="$(cat /proc/mounts | sed -n 's|^\(/dev/[^[:blank:]]*\) '"$SRV"' .*|\1|p')"
       [ -z "$SRV_DEV" ] || SRV_UUID="$(blkid "$SRV_DEV" -s UUID -o value)"
   fi
   [ -n "$SRV_UUID" ] || die "Can't find your current srv location"
   uci set storage.srv.uuid="$UUID"
   uci set storage.srv.old_uuid="$SRV_UUID"
   uci commit storage
fi

# Make sure we have /srv mounted somewhere
if [ "$(stat -c %m /srv/)" = "$(stat -c %m /)" ]; then
   SRV_MNT_PNT="/tmp/storage_plugin_formating"
   mkdir -p "$SRV_MNT_PNT"
   DEV="$(blkid -U "$UUID")"
   [ -n "$DEV" ] || die "Can't find device with UUID $UUID"
   mount -t btrfs -o subvol=@ "$DEV" "$SRV_MNT_PNT" || die "Can't mount $DEV"
fi

CHANGED=""
# Add newly added drives
for disk in "$@"; do
   if ! has_uuid "$disk"; then
      umount_drive "$disk"
      set_state "Adding drive $disk to the storage"
      RES="$(btrfs device add "$disk" "$SRV_MNT_PNT" 2>&1)"
      [ "$?" = 0 ] || die ")_(Adding drive $disk failed.)

_(Technical details:)
_($RES"
      CHANGED="yes"
   fi
done

# Remove no longer wanted drives
for disk in $(btrfs device usage "$SRV_MNT_PNT" | sed -n 's|^\(/dev/[^,]*\),.*|\1|p'); do
   if ! grep -q "^$disk" /tmp/formating; then
      set_state "Removing drive $disk from the storage"
      RES="$(btrfs device delete "$disk" "$SRV_MNT_PNT" 2>&1)"
      [ "$?" = 0 ] || die ")_(Removing drive $disk failed.)

_(Technical details:)
_($RES"
      CHANGED="yes"
   fi
done

# Rebalance/convert if needed
if [ "$RAID" = single ]; then
   if btrfs device usage "$SRV_MNT_PNT" | grep -q RAID; then
      set_state "Converting to JBOD configuration"
      RES="$(btrfs fi balance start -dconvert=single -mconvert=dup "$SRV_MNT_PNT" 2>&1)"
      [ "$?" = 0 ] || die ")_(Converting raid profile failed.)

_(Technical details:)
_($RES"
      CHANGED=""
   fi
elif [ "$RAID" = raid1 ]; then
   if btrfs device usage "$SRV_MNT_PNT" | grep -q Data,single || btrfs device usage "$SRV_MNT_PNT" | grep -q Metadata,DUP; then
      set_state "Converting to RAID1 configuration"
      RES="$(btrfs fi balance start -dconvert=raid1 -mconvert=raid1 "$SRV_MNT_PNT" 2>&1)"
      [ "$?" = 0 ] || die ")_(Converting raid profile failed.)

_(Technical details:)
_($RES"
      CHANGED=""
   fi
fi
if [ -n "$CHANGED" ]; then
   set_state "Redistributing data across devices"
   RES="$(btrfs fi balance start --full-balance "$SRV_MNT_PNT" 2>&1)"
   [ "$?" = 0 ] || die ")_(Redistributing data failed.)

_(Technical details:)
_($RES"

fi

# Unmount srv if needed
[ "$SRV_MNT_PNT" = /srv ] || umount -fl "$SRV_MNT_PNT"

if [ -n "$FROM_SCRATCH" ]; then
   TEXT="Your new disk for storing data has been setup successfully. All you need to do now is to reboot your router for changes to take effect. Be aware that if you have some local data stored on your current storage, those will get moved during reboot, so your next reboot might take quite some time."
   create_notification -s restart "_($TEXT)"
else
   create_notification -s restart "_(Your storage setup was updated as requested. Checkout the current state in Storage tab in Foris web UI.)"
fi
rm -f /tmp/formating
