# Klipper virtual_pins module

[![Project Maintenance](https://img.shields.io/maintenance/yes/2024.svg)](https://github.com/pedrolamas/klipper-virtual-pins 'GitHub Repository')
[![License](https://img.shields.io/github/license/pedrolamas/klipper-virtual-pins.svg)](https://github.com/pedrolamas/klipper-virtual-pins/blob/master/LICENSE 'License')

[![Follow pedrolamas on Twitter](https://img.shields.io/twitter/follow/pedrolamas?label=Follow%20@pedrolamas%20on%20Twitter&style=social)](https://twitter.com/pedrolamas)
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

## Credits and Acknowledgements

- [Klipper](https://github.com/Klipper3d/klipper) by [Kevin O'Connor](https://github.com/KevinOConnor)

## License

MIT
