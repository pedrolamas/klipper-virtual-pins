#!/bin/bash

KLIPPER_DIR="${HOME}/klipper"

VIRTUAL_PINS_DIR="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

if [ ! -d "$KLIPPER_DIR" ]; then
    echo "virtual_pins: klipper doesn't exist"
    exit 1
fi

echo "virtual_pins: linking klippy to virtual_pins.py."

if [ -e "${KLIPPER_DIR}/klippy/extras/virtual_pins.py" ]; then
    rm "${KLIPPER_DIR}/klippy/extras/virtual_pins.py"
fi
ln -s "${VIRTUAL_PINS_DIR}/virtual_pins.py" "${KLIPPER_DIR}/klippy/extras/virtual_pins.py"

if ! grep -q "klippy/extras/virtual_pins.py" "${KLIPPER_DIR}/.git/info/exclude"; then
    echo "klippy/extras/virtual_pins.py" >> "${KLIPPER_DIR}/.git/info/exclude"
fi

echo "virtual_pins: installation successful."
