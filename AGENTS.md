# AGENTS.md

This file provides guidance for working with code in this repository.

## What this is

A single-file [Klipper](https://github.com/Klipper3d/klipper) extra (`virtual_pins.py`) that registers a `virtual_pin` pin chip. It lets any config pin be set to `virtual_pin:<id>` so simulated pins can stand in for scarce real MCU pins. Everything except a stepper's `step_pin`/`dir_pin` can be emulated. `install.sh` symlinks `virtual_pins.py` into a Klipper checkout's `klippy/extras/`.

## Testing

Tests are Klipper "klippy" regression cases under `test/klippy/` (`.cfg` + `.test` pairs) run by Klipper's own `scripts/test_klippy.py`. `test/run-tests.sh` installs the module into a Klipper checkout, builds (and caches) an atmega2560 dictionary, then runs the suite.

From the repo root, with a Klipper checkout as a sibling directory (`../klipper`):

```bash
bash test/run-tests.sh            # defaults to ../klipper
bash test/run-tests.sh PATH_TO_KLIPPER
bash test/run-tests.sh --rebuild-dict   # force a fresh dictionary
```

This needs `bash` plus the Python build deps Klipper requires (`build-essential`, `libffi-dev`, and the `klippy-requirements.txt` / `tests-requirements.txt` packages). On a host that lacks them (or to keep things isolated), run the same script in a container. The cached dict (`test/dict/atmega2560.dict`) means no AVR toolchain is needed:

```bash
docker run --rm \
  -v "$PWD:/repo" \
  -v "$PWD/../klipper:/klipper" \
  -e KLIPPER_DIR=/klipper \
  python:3.13-slim \
  bash -c '
set -e
apt-get update -qq >/dev/null && apt-get install -y -qq build-essential libffi-dev >/dev/null
pip install -q -r /klipper/scripts/klippy-requirements.txt
pip install -q -r /klipper/scripts/tests-requirements.txt
rm -f /klipper/klippy/extras/virtual_pins.py   # drop any stale symlink from a prior install
bash /repo/test/run-tests.sh /klipper
'
```

`run-tests.sh` always runs the entire `test/klippy/*.test` glob (and `test_klippy.py` stops at the first failing case). To run one case in isolation, after `install.sh` invoke it directly from the Klipper checkout, pointing back at this repo's test dirs (sibling layout shown):

```bash
python3 scripts/test_klippy.py -d ../klipper-virtual-pins/test/dict \
  ../klipper-virtual-pins/test/klippy/NAME.test
```

A `.test` file declares `DICTIONARY` + `CONFIG` then a sequence of g-code lines; a config that should fail to load is named `fail_*` and its `.test` asserts the expected error.

## Architecture

The central idea: `VirtualPins` registers itself as a pin *chip* (`register_chip('virtual_pin', self)`), and Klipper reaches it through **two different contracts** that must both be honored:

1. **As a pin factory.** `ppins.setup_pin(type, ...)` routes to `VirtualPins.setup_pin`, which returns a per-type object: `DigitalOutVirtualPin`, `PwmVirtualPin`, `AdcVirtualPin`, `EndstopVirtualPin`, `DigitalInVirtualPin`. Each stores a single normalized `_value` (0..1) plus its inversion, and exposes `get_status` for the printer's status API. A pin name is locked to its first-used type (reusing it as another type raises).

2. **As a stand-in MCU.** `ppins.lookup_pin()` hands consumers `pin_params['chip']` — the `VirtualPins` instance itself — which modules like `buttons`, `bus.py` (SPI/I2C helpers), the `display` drivers, `pwm_cycle_time`, and `pwm_tool` then drive **as if it were an MCU object**. So `VirtualPins` mirrors a subset of `klippy/mcu.py`'s `MCU` interface. This is the main maintenance surface: when Klipper master changes that interface, the chip may need new stubs. Default conventions for the stubs:
   - Clockless: `seconds_to_clock`, `print_time_to_clock`, `clock_to_print_time`, `estimated_print_time`, `get_query_slot` all return `0`; `clock32_to_clock64` is identity.
   - "Everything is supported as a no-op": `lookup_command`/`try_lookup_command` return a no-op `VirtualCommand` (or `VirtualButtonCommand`); `lookup_query_command` returns `VirtualCommandQuery`; `check_valid_response` is `True`. Returning `None`/raising here would push callers (e.g. `bus.py`) onto legacy/deprecation paths and emit spurious warnings.
   - Benign constants on the normalized scale: `get_constants` → `{}`, `get_constant_float` → `1.` (suits `PWM_MAX`), `get_enumerations` → `{}`, `min_schedule_time` → `0.100`, `max_nominal_duration` → `3.0`.

   Crucially, a pin's `get_mcu()` returns the **real** `mcu` object (looked up at construction), not the chip — so duration/scheduling checks delegate to real hardware while pin I/O stays virtual.

`config_callbacks` run on `klippy:connect`; `post_init_callbacks` run on `klippy:ready` (matching real MCU ordering).

### Button emulation
There is no firmware, so `add_config_cmd` parses the `config_buttons` / `buttons_add` / `buttons_query` command strings Klipper's `buttons.py` would have sent to an MCU, and a reactor timer (`_poll_buttons`) samples the referenced virtual pins ~every 10 ms, delivering a synthesized `buttons_state` response through `register_serial_response`. It reports **raw** pin states because `buttons.py` applies inversion itself.

### Endstop homing
`EndstopVirtualPin.home_start` arms a reactor timer that polls `query_endstop` until the value matches the requested trigger state. In file-output mode (`is_fileoutput()`) the reactor isn't pumped during the drip move, so `home_wait` mirrors the stock MCU endstop and reports a successful trigger.

### Setting values
Pins are driven by the `SET_VIRTUAL_PIN PIN=<name> ...` g-code (registered per pin). It accepts either a `VALUE` (with optional `DELAY`, scheduled via a reactor timer) or a `TEMPLATE` naming a `[display_template]` whose rendered float continuously updates the pin. Initial values come from the `[virtual_pins] start_values:` config map.

## Maintenance notes

CI (`.github/workflows/test.yml`) runs the suite against **Klipper master** on push/PR and on a daily cron, specifically to catch breakage from upstream interface drift. When tests fail only on the cron, the cause is usually a changed `klippy/mcu.py` MCU method — add/adjust the corresponding stub in `VirtualPins`. Regenerate the cached dictionary (`--rebuild-dict`) only when the atmega2560 message format changes.
