# Klipper virtual_pins module

[![Project Maintenance](https://img.shields.io/maintenance/yes/2025.svg)](https://github.com/pedrolamas/klipper-virtual-pins 'GitHub Repository')
[![License](https://img.shields.io/github/license/pedrolamas/klipper-virtual-pins.svg)](https://github.com/pedrolamas/klipper-virtual-pins/blob/master/LICENSE 'License')

[![Follow pedrolamas.com on Bluesky](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fpublic.api.bsky.app%2Fxrpc%2Fapp.bsky.actor.getProfile%2F%3Factor%3Dpedrolamas.com&query=%24.followersCount&style=social&logo=bluesky&label=Follow%20%40pedrolamas.com)](https://bsky.app/profile/pedrolamas.com)
[![Follow pedrolamas on Mastodon](https://img.shields.io/mastodon/follow/109365776481898704?label=Follow%20@pedrolamas%20on%20Mastodon&domain=https%3A%2F%2Fhachyderm.io&style=social)](https://hachyderm.io/@pedrolamas)

`Klipper Virtual Pins` is a [Klipper](https://github.com/Klipper3d/klipper) helper module that allows usage of virtual (simulated) pins.

This module allows configurable pins to be set to `virtual_pin:<id>` as a way to mitigate the limited number of available pins provided by the MCUs.

**Note:** `virtual_pins` will be able to simulate most pins, with the major exception of steppers `step_pin` and `dir_pin` (please use MCU pins for these).

## Install

Clone this repository from git and run the install script:

```sh
cd ~
git clone https://github.com/pedrolamas/klipper-virtual-pins.git
./klipper-virtual-pins/install.sh
```

## Usage

First, add an empty `[virtual_pins]` section to your `printer.cfg` to enable the `virtual_pins`:

```ini
[virtual_pins]
```

After that, use `virtual_pin:` prefix followed by a random identifier (example `virtual_pin:test`)

Here's a fully working `printer.cfg` snippet:

```ini
[virtual_pins]

[output_pin test]
pin: virtual_pin:test_pin
pwm: True
cycle_time: 0.1
```

## Commands

### SET_VIRTUAL_PIN

`SET_VIRTUAL_PIN PIN=config_name VALUE=<value> [DELAY=<delay>]`: Set the pin to the given `VALUE`. `VALUE` should be 0 or 1 for "digital" output pins. For PWM pins, set to a value between 0.0 and 1.0.
You can also specify a `DELAY` duration for the value to be updated. Any `SET_VIRTUAL_PIN` call to the same pin will reset any pending delay.

`SET_VIRTUAL_PIN PIN=config_name TEMPLATE=<template_name> [<param_x>=<literal>]`: If `TEMPLATE` is specified then it assigns a display_template to the given pin. For example, if one defined a `[display_template my_pin_template]` config section then one could assign `TEMPLATE=my_pin_template` here. The display_template should produce a string containing a floating point number with the desired value. The template will be continuously evaluated and the pin will be automatically set to the resulting value. One may set display_template parameters to use during template evaluation (parameters will be parsed as Python literals). If `TEMPLATE` is an empty string then this command will clear any previous template assigned to the pin (one can then use `SET_VIRTUAL_PIN` commands to manage the values directly).

## Credits and Acknowledgements

- [Klipper](https://github.com/Klipper3d/klipper) by [Kevin O'Connor](https://github.com/KevinOConnor)

## License

MIT
