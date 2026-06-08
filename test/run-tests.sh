#!/bin/bash
# Run the virtual_pins regression tests against a Klipper checkout.
#
# Usage:
#   ./test/run-tests.sh [KLIPPER_DIR] [extra test_klippy.py args...]
#
# The Klipper checkout is resolved from (in order): the first argument, the
# KLIPPER_DIR environment variable, or the default "../klipper". The module is
# installed into that checkout, an atmega2560 dictionary is built (and cached),
# and Klipper's own scripts/test_klippy.py is run against test/klippy/*.test.
#
# Examples:
#   ./test/run-tests.sh                 # uses ../klipper
#   ./test/run-tests.sh ~/klipper       # explicit path
#   KLIPPER_DIR=/opt/klipper ./test/run-tests.sh -v
#   ./test/run-tests.sh --rebuild-dict  # force a fresh dictionary build

set -eu

# Resolve repository directory (parent of this script's dir)
SCRIPT_DIR="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
REPO_DIR="$( cd -- "${SCRIPT_DIR}/.." >/dev/null 2>&1 ; pwd -P )"

# Optional first positional argument: path to the Klipper checkout
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then
    KLIPPER_DIR="$1"
    shift
fi
KLIPPER_DIR="${KLIPPER_DIR:-${REPO_DIR}/../klipper}"

# Optional --rebuild-dict flag (consumed here, not passed to test_klippy.py)
REBUILD_DICT=0
ARGS=()
for arg in "$@"; do
    if [ "${arg}" = "--rebuild-dict" ]; then
        REBUILD_DICT=1
    else
        ARGS+=("${arg}")
    fi
done

if [ ! -f "${KLIPPER_DIR}/klippy/klippy.py" ]; then
    echo "run-tests: '${KLIPPER_DIR}' is not a Klipper checkout" >&2
    echo "run-tests: pass the path as the first argument or set KLIPPER_DIR" >&2
    exit 1
fi
KLIPPER_DIR="$( cd -- "${KLIPPER_DIR}" >/dev/null 2>&1 ; pwd -P )"

DICT_DIR="${REPO_DIR}/test/dict"
DICT_FILE="${DICT_DIR}/atmega2560.dict"
PYTHON="${PYTHON:-python3}"

# Install (symlink) virtual_pins.py into the Klipper checkout
echo "run-tests: installing virtual_pins into ${KLIPPER_DIR}"
KLIPPER_DIR="${KLIPPER_DIR}" bash "${REPO_DIR}/install.sh"

# Build the MCU dictionary if missing (or when forced). The build is directed
# into a throwaway directory (overriding the Makefile's OUT and KCONFIG_CONFIG)
# so the Klipper checkout's own .config and out/ build are left untouched.
if [ "${REBUILD_DICT}" = "1" ] || [ ! -f "${DICT_FILE}" ]; then
    echo "run-tests: building atmega2560 dictionary"
    mkdir -p "${DICT_DIR}"
    BUILD_DIR="$(mktemp -d)"
    cp "${KLIPPER_DIR}/test/configs/atmega2560.config" "${BUILD_DIR}/.config"
    (
        cd "${KLIPPER_DIR}"
        make OUT="${BUILD_DIR}/out/" KCONFIG_CONFIG="${BUILD_DIR}/.config" \
            olddefconfig
        make OUT="${BUILD_DIR}/out/" KCONFIG_CONFIG="${BUILD_DIR}/.config"
    )
    cp "${BUILD_DIR}/out/klipper.dict" "${DICT_FILE}"
    rm -rf "${BUILD_DIR}"
fi

# Run the regression tests from within the Klipper checkout
echo "run-tests: running test_klippy.py"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "${TMPDIR}"' EXIT
cd "${KLIPPER_DIR}"
"${PYTHON}" scripts/test_klippy.py -d "${DICT_DIR}" -t "${TMPDIR}" \
    "${ARGS[@]}" "${REPO_DIR}"/test/klippy/*.test
