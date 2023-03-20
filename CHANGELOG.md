# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

## [0.10.2] - 2023-03-23
### Fixed
- init: Fix the notification on error

## [0.10.1] - 2022-10-18
### Fixed
- init: Fix the condition so router wouldn't end up with tmpfs mounted on top of
  btrfs in case of failure.

## [0.10.0] - 2021-09-27
### Added
- Scripts that use storage for Lighttpd temporally files

## [0.9.0] - 2021-09-01
### Changed
- Increase persistent logs size to 100 MB in logrotate config
- Refactor srv init script
- Restart `rainbow` service instead of hardcoded set to white in srv init script

### Fixed
- Handle missing /srv directory in srv init script
- Prevent to manipulate programmable LEDs on routers without `rainbow` command in srv init script

## [0.8.1] - 2021-04-20
### Fixed
- add btrfs device scan
- support 'jbod' and 'raid0' in uci settings

## [0.8] - 2021-01-21
### Fixed
- Fix regression by bringing back some attributes that were removed in latest API cleanup (`old_uuid`, `is_broken`)

## [0.7] - 2021-01-19
### Changed
- cleanup and refactoring in module API (remove `old_uuid`, `old_device_desc`; add `using_external`)
- more strict json schema constraints
- ignore device that is used as rootfs

## [0.6] - 2020-12-04
### Added
- add option to set persistent logs

### Changed
- Migrate CHANGELOG to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) style

## [0.5] - 2020-09-22
### Removed
- remove nextcloud code from storage

## [0.4.2] - 2020-04-07
### Changed
- improve notifications
- simplify first setup

### Fixed
- fix behaviour with lost disk

## [0.4.1] - 2019-12-02
### Fixed
- fix schema to work with empty old_uuid

## [0.4] - 2019-11-22
### Changed
- Changes in API to better support new features, should be backward compatible.

## [0.3.1] - 2019-10-11

- prepared new cleaner API
- fix few minor issues
- optional undocumented mounting of different subvolume

## [0.3.0] - 2019-09-13
### Added
- initial raid support

## [0.2.100] - 2019-07-15
### Fixed
- fix hard-coded paths

## [0.2.99] - 2019-06-29
### Added
- initial Nextcloud support

## [0.2.5] - 2019-04-29

- blikd: parsing fix
- setup.py: dependency updates

## [0.2.4] - 2018-10-26

- setup.py: cleanup + PEP508 updated

## [0.2.3] - 2018-10-26

- make sure we don't use flash when mounting fails

## [0.2.2] - 2018-09-20

- support for drives which are not shown in blkid

## [0.2.1] - 2018-08-23

- More error-prone cleanup after migration

## [0.2] - 2018-08-13

- python3 compatibility
- a bigger cleanup

## [0.1] - 2018-07-30
### Added
- initial version
