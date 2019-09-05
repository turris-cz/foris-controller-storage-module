#!/usr/bin/env bats

setup() {
	for i in $(seq 0 3); do
		truncate -s 1G /tmp/storage-test-drive-$i
		losetup /dev/loop$i /tmp/storage-test-drive-$i
	done
	# Mock OpenWRT
	echo "#!/bin/sh" > /lib/functions.sh
	cat >> /lib/functions.sh << EOF
		config_load() { :; }
		create_notification() { :; }
		config_get() { :; }
		config_get_bool() { :; }
		uci() {
			if [ "\$1" = set ] && expr "\$2" : storage.srv.uuid; then
				echo "\$2" | sed 's|storage.srv.uuid|UUID|' >> /lib/functions.sh
			fi
		}
EOF
}

teardown() {
	umount -fl /tmp/storage-test-mount 2> /dev/null
	rm -rf /tmp/storage-test-mount
	for i in $(seq 0 3); do
		losetup -d /dev/loop$i
		rm -f /tmp/storage-test-drive-$i
	done
	rm -f /lib/functions.sh
	rm -f /tmp/storage_debug
}

get_df() {
	mkdir -p /tmp/storage-test-mount
	mount -t btrfs -o subvol=@ "$1" /tmp/storage-test-mount || return 2
	df -BM -P /tmp/storage-test-mount | sed -n 's|.*[[:blank:]]\([0-9]*\)M[[:blank:]][^M]*$|\1|p'
	umount -fl /tmp/storage-test-mount
}

@test "Format one drive" {
	format_and_set_srv.sh -d /dev/loop0
	run get_df /dev/loop0
	[ "$status" -eq 0 ]
	[ "$output" -gt 500 ]
}

@test "Format multiple drives in JBOD mode" {
	echo "RAID=single" >> /lib/functions.sh
	format_and_set_srv.sh -d /dev/loop0 /dev/loop1
	run get_df /dev/loop0
	[ "$status" -eq 0 ]
	[ "$output" -gt 1500 ]
}

@test "Format multiple drives in RADI1 mode" {
	echo "RAID=raid1" >> /lib/functions.sh
	format_and_set_srv.sh -d /dev/loop0 /dev/loop1
	run get_df /dev/loop0
	[ "$status" -eq 0 ]
	[ "$output" -lt 1500 ]
	[ "$output" -gt 500 ]
}

@test "Make sure that data survives various reconfigurations" {
	TEST_PATTERN="Testing whether drives are working"
	format_and_set_srv.sh -d /dev/loop0 /dev/loop1
	run get_df /dev/loop0
	[ "$status" -eq 0 ]
	[ "$output" -gt 1500 ]
	mount -t btrfs -o subvol=@ /dev/loop0 /tmp/storage-test-mount
	echo "$TEST_PATTERN" > /tmp/storage-test-mount/testfile
	format_and_set_srv.sh -d /dev/loop0 /dev/loop1 /dev/loop2 /dev/loop3
	format_and_set_srv.sh -d /dev/loop2 /dev/loop3
	[ "$(cat /tmp/storage-test-mount/testfile)" = "$TEST_PATTERN" ]
	format_and_set_srv.sh -d /dev/loop0 /dev/loop1
	[ "$(cat /tmp/storage-test-mount/testfile)" = "$TEST_PATTERN" ]
	umount /tmp/storage-test-mount
}

@test "Degrading to one drive fails in RAID1, works in single" {
	echo "RAID=raid1" >> /lib/functions.sh
	format_and_set_srv.sh -d /dev/loop0 /dev/loop1
	run format_and_set_srv.sh -d /dev/loop0
	[ "$status" -ne 0 ]
	echo "RAID=single" >> /lib/functions.sh
	format_and_set_srv.sh -d /dev/loop0
}
