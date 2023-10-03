#!/bin/sh
. /lib/functions.sh

config_load "storage"
config_get uuid "srv" "uuid"
config_get_bool syslog "srv" "syslog" "0"

# Ignore if storage is not configured
[ -n "$uuid" ] || return 0
# /srv has to be mounted
[ "$(stat -c '%m' /srv)" = "/srv" ] || return 0
# Syslog has to be enabled for /srv
[ "$syslog" = "1" ] || return 0

echo "destination(srv_messages)"
