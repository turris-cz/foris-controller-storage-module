#!/bin/sh
. /lib/functions.sh
config_load storage

config_get_bool DBG srv debug 0
config_get UUID srv uuid
config_get RAID srv raid single

FROM_SCRATCH=""
SRV_MNT_PNT="/srv"
# Decide how much we want to debug
[ "$DBG" = 0 ] || set -x
if [ "x-d" = "x$1" ]; then
   export FORKED=1
   set -x
   shift
else
   rm -f /tmp/storage_debug
   [ "$DBG" = 0 ] || exec 2>> /tmp/storage_debug
fi

cleanup() {
    umount -fl /tmp/storage_plugin/tmpdir 2> /dev/null
    rm -rf /tmp/storage_plugin
}

die() {
    if [ -n "$2" ]; then
        create_notification -s error "_($1)

_(Technical details:) $2"
    else
        create_notification -s error "_($1)"
    fi
    exit 2
}

set_state() {
    echo "$1" > /tmp/storage_plugin/state
}

# Try to unmount everything that might be mounted
# This is best effort, so ignore all errors not to confuse people and to ease debugging
umount_drive() {
   umount -fl "$1" 2> /dev/null
   # If argument is whole drive unmount partitions as well
   if expr "$1" : '.*[a-z]$' > /dev/null; then
       for part in "$1"[0-9]; do
           umount -fl "$part" 2> /dev/null
       done
   fi
}

# Reload partition table if argument is whole drive, not a partition
reload_partitions() {
   if expr "$1" : '.*[a-z]$' > /dev/null; then
       partx -d "$1"
   fi
}

# Try to format the drive and get UUID of it
format_drive() {
   local disk="$1"
   umount_drive "$disk"

   set_state "Fromating the drive"
   RES="$(mkfs.btrfs -f -L srv "$disk" 2>&1)" ||\
       die "Formatting drive failed, try unpluging it and repluging it in again." "$RES"

   reload_partitions "$disk"

   # Try to get UUID
   UUID="$(echo "$RES" | sed -n 's|.*UUID:[[:blank:]]*\([0-9a-f-]*\)|\1|p')"
   [ -n "$UUID" ] || UUID="$(blkid -c /dev/null "$disk" -s UUID -o value)"
   [ -n "$UUID" ] || die "Can't get UUID of your newly formatted drive."

   # Prepare snapshot on the drive
   mkdir -p /tmp/storage_plugin/tmpdir
   mount -t btrfs "$disk" /tmp/storage_plugin/tmpdir || die "Can't mount newly formatted drive."
   btrfs subvol create /tmp/storage_plugin/tmpdir/@ || die "Can't create @ submodule."
   umount /tmp/storage_plugin/tmpdir
   rmdir /tmp/storage_plugin/tmpdir
}

# Does the disk have srv UUID
has_uuid() {
   [ "$(blkid -c /dev/null "$1" -s UUID -o value)" = "$UUID" ]
}

# Check syntax
if [ "$#" -lt 1 ]; then
    echo "Usage: $0 DISK..." >&2
    exit 1
fi

# Some locking and also storing desired drives
mkdir /tmp/storage_plugin 2>/dev/null || die "Another instance is already running."
if [ -f /tmp/storage_plugin/formating ]; then
    die "Another formatting job currently in progress, not switching to new drive."
fi
# Make sure drives are stored with absolute paths
echo "$@" | sed 's| |\n|g' | sed 's|^\([^/]\)|/dev/\1|' > /tmp/storage_plugin/formating

# Cleanup only if we are the right instance
trap cleanup EXIT TERM

# Run in background by default not to block Foris
if [ -z "$FORKED" ]; then
    export FORKED=1
    "$0" "$@" < /dev/null > /dev/null 2>&1 &
    exit 0
else
    sleep 1
fi

# Reset arguments to make sure we have absolute paths to drives
set $(cat /tmp/storage_plugin/formating)

# Are we are starting from scratch
if [ -z "$UUID" ]; then
   format_drive "$1"
   FROM_SCRATCH="yes"
   shift

   # Commit configuration
   SRV="$(stat -c %m /srv/)"
   SRV_DEV=""
   SRV_UUID=""
   if grep -q '^ubi[^[:blank:]]* '"$SRV"' .*' /proc/mounts || \
      grep -q '^[^[:blank:]]* /srv tmpfs.*' /proc/mounts; then
       SRV_UUID="rootfs"
   else
       [ -z "$SRV" ] || SRV_DEV="$(sed -n 's|^\(/dev/[^[:blank:]]*\) '"$SRV"' .*|\1|p' /proc/mounts)"
       [ -z "$SRV_DEV" ] || SRV_UUID="$(blkid -c /dev/null "$SRV_DEV" -s UUID -o value)"
   fi
   [ -n "$SRV_UUID" ] || die "Can't find your current srv location"
   uci set storage.srv.uuid="$UUID"
   uci set storage.srv.old_uuid="$SRV_UUID"
   uci commit storage
fi

# Make sure we have /srv mounted somewhere
if [ "$(stat -c %m /srv/)" = "$(stat -c %m /)" ]; then
   SRV_MNT_PNT="/tmp/storage_plugin/tmpdir"
   mkdir -p "$SRV_MNT_PNT"
   DEV="$(blkid -c /dev/null -U "$UUID")"
   [ -n "$DEV" ] || die "Can't find device with UUID $UUID"
   mount -t btrfs -o subvol=@ "$DEV" "$SRV_MNT_PNT" || die "Can't mount $DEV"
fi

CHANGED=""
# Add newly added drives
for disk in "$@"; do
   if ! has_uuid "$disk"; then
      umount_drive "$disk"
      set_state "Adding drive $disk to the storage"
      RES="$(btrfs device add "$disk" "$SRV_MNT_PNT" 2>&1)" ||\
          die "Adding drive $disk failed." "$RES"
      CHANGED="yes"
   fi
done

# Remove no longer wanted drives
for disk in $(btrfs device usage "$SRV_MNT_PNT" | sed -n 's|^\(/dev/[^,]*\),.*|\1|p'); do
   if ! grep -q "^$disk" /tmp/storage_plugin/formating; then
      set_state "Removing drive $disk from the storage"
      RES="$(btrfs device delete "$disk" "$SRV_MNT_PNT" 2>&1)" ||\
          die "Removing drive $disk failed." "$RES"
      CHANGED="yes"
   fi
done

# Rebalance/convert if needed
if [ "$RAID" = single ]; then
   # Check is some data/metadata are still in RAID configuration
   if btrfs device usage "$SRV_MNT_PNT" | grep -q RAID; then
      set_state "Converting to JBOD configuration"
      RES="$(btrfs balance start -dconvert=single -mconvert=dup "$SRV_MNT_PNT" 2>&1)" ||\
          die "Converting raid profile failed." "$RES"
      CHANGED=""
   fi
elif [ "$RAID" = raid1 ]; then
   # Check is some data/metadata are still not in RAID configuration
   if btrfs device usage "$SRV_MNT_PNT" | grep -q -E '(Data,single|Metadata,DUP)'; then
      set_state "Converting to RAID1 configuration"
      RES="$(btrfs balance start -dconvert=raid1 -mconvert=raid1 "$SRV_MNT_PNT" 2>&1)"||\
          die "Converting raid profile failed." "$RES"
      CHANGED=""
   fi
fi
if [ -n "$CHANGED" ]; then
   # If some drives were added/removed, do rebalance to redistribute the data
   set_state "Redistributing data across devices"
   RES="$(btrfs balance start --full-balance "$SRV_MNT_PNT" 2>&1)" ||\
       die "Redistributing data failed." "$RES"
fi

# Unmount temporally mounted srv if there is a such
[ "$SRV_MNT_PNT" = /srv ] || umount -fl "$SRV_MNT_PNT"

if [ -n "$FROM_SCRATCH" ]; then
   TEXT="Your new disk for storing data has been setup successfully. All you need to do now is to reboot your router for changes to take effect. Be aware that if you have some local data stored on your current storage, those will get moved during reboot, so your next reboot might take quite some time."
   create_notification -s restart "_($TEXT)"
else
   create_notification -s restart "_(Your storage setup was updated as requested. Checkout the current state in Storage tab in Foris web UI.)"
fi
rm -f /tmp/formating
