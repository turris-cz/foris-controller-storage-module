#!/bin/sh
. /lib/functions.sh

config_load "storage"
config_get uuid "srv" "uuid"
config_get_bool upload_dirs "srv" "lighttpd_upload_dirs" "1"

# We check here for:
# * if storage is configured
# * if /srv is actually mounted (the srv init not failed)
# * Upload dirs have to be enabled in the configuration
if [ -n "$uuid" ] && [ "$(stat -c '%m' /srv)" = "/srv" ] && [ "$upload_dirs" = "1" ]; then
	dir="/srv/.lighttpd-tmp"
	mkdir -p -m 0700 "$dir"
	echo "server.upload-dirs := ( \"$dir\" )"
	echo "server.stream-request-body := 1"
	echo "server.stream-response-body := 1"
else
	echo "server.stream-request-body := 2"
	echo "server.stream-response-body := 2"
fi
