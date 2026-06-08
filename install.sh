#!/bin/bash

KLIPPER_DIR="${KLIPPER_DIR:-${HOME}/klipper}"

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

# Only update the git exclude list when KLIPPER_DIR is a git checkout
if [ -d "${KLIPPER_DIR}/.git/info" ]; then
    EXCLUDE_FILE="${KLIPPER_DIR}/.git/info/exclude"
    if ! grep -q "klippy/extras/virtual_pins.py" "${EXCLUDE_FILE}" 2>/dev/null; then
        echo "klippy/extras/virtual_pins.py" >> "${EXCLUDE_FILE}"
    fi
fi

echo "virtual_pins: installation successful."
