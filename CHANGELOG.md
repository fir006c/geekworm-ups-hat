# Change Log

## [Unreleased]
- Added support for the Geekworm / Suptronics X1200 UPS HAT (Raspberry Pi 5), selected with the new `board` app option.
- Board specific GPIO layouts are now described by board profiles in the daemon, so more HATs can be added later.
- **Breaking:** renamed the app slug to `geekworm-daemon` (folder `ha-addon-geekworm`, image `ha-addon-geekworm`),
  the integration domain to `geekworm_ups` and the REST endpoint to `/api/ups`. Entity ids now follow the
  device name (e.g. `sensor.geekworm_x1200_ups_hat_battery_level`). Remove the old app and integration before installing.
- Replaced the "X728" label in the icon and logo with a generic "UPS HAT" label.
- Added integration translations: German, Spanish, French, Dutch, Polish, Portuguese and Russian.
- Releases now include `geekworm_ups.zip` for the Home Assistant Marketplace and HACS (`zip_release` enabled in `hacs.json`).
- README: install steps for the Marketplace (Home Assistant 2026.11+) and HACS (2026.10 and older).

## [1.0.4] - 2026-10-26
- Fixed options-flow compatibility and updated connection checks to use Home Assistant's shared HTTP session and timeout handling.
- Updated the README's Home Assistant installation badge links.
- Disabled Pylint's `abstract-method` warning in the development container configuration.

## [1.0.3] - 2026-09-12
- Added support for Geekworm X728 hardware versions 2.4 and 2.5.
- Updated the add-on configuration and Docker image for Home Assistant 2026.9.

## [1.0.2] - 2026-06-05
- Fixed the hardware-version sensor's diagnostic entity category.

## [1.0.1] - 2026-05-26
- Corrected the battery voltage and capacity sensor icons.
- Updated the README terminology from Home Assistant add-on to app.

## [1.0.0] - 2026-05-21
- First release version.
