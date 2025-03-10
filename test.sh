#!/bin/bash
#-----------------------------------------------------
# usage()
#
# ARGS: All commandline arguments passed to shell.
#
# Checks if option is either status, detach or attach
# Exits program if improper usage
#
# RETURNS: Nothing
#-----------------------------------------------------
# usage() {
#     USAGE="$0 [status | detach | attach ]"
#     echo $#
#     if [ $# -ne 1 ]; then
#         echo "$USAGE"
#         exit 1
#     fi
# }
# usage $*

CONFIG_FILE="${HOME}/.config/pomlock.conf"

declare -A PRESETS=(
    ["standard"]="1500 300 300 4"  # 25/5/5x4
    ["extended"]="2400 600 1200 3" # 40/10/20x3
    ["custom"]=""                  # User-provided
)

load_config() {
    source "$CONFIG_FILE" 2>/dev/null || {
        # echo "Using default configuration"
        WORK_DURATION=3600
        SHORT_BREAK=600
        LONG_BREAK=1200
        CYCLES_BEFORE_LONG=3
        ENABLE_INPUT=false
        OVERLAY_OPTS="--font-size 48 --color white --bg-color black --opacity 0.8"
    }
}

load_config

while [[ $# -gt 0 ]]; do
    case $1 in
    -p | --preset)
        if [[ ! "${PRESETS[$2]}" ]]; then
            echo "Custom preset inputted"
            IFS=' ' read -ra PRESET_VALUES <<<"$2"
        else
            IFS=' ' read -ra PRESET_VALUES <<<"${PRESETS[$2]}"
        fi
        WORK_DURATION="${PRESET_VALUES[0]}"
        SHORT_BREAK="${PRESET_VALUES[1]}"
        LONG_BREAK="${PRESET_VALUES[2]}"
        CYCLES_BEFORE_LONG="${PRESET_VALUES[3]}"
        echo "Values: $WORK_DURATION, $SHORT_BREAK, $LONG_BREAK, $CYCLES_BEFORE_LONG"
        shift 2
        ;;
    --enable-input)
        ENABLE_INPUT=true
        shift
        ;;
    esac
done

# echo "Work duration: $WORK_DURATION"
# echo "Short break duration: $SHORT_BREAK"
# echo "Long break duration: $LONG_BREAK"
# echo "Cycles before long break: $CYCLES_BEFORE_LONG"

# KEYBOARD_ID="$(xinput list | grep -iE 'keyboard' | grep -iE 'slave|slave.*keyboard' | grep -iv 'virtual' | head -n1 | awk -F'=' '{print $2}' | cut -d'[' -f1 | xargs)"
# KEYBOARD_ID="$(xinput list |
#     grep -iE 'slave|slave.*keyboard' |
#     grep -ivE 'virtual|xtest|pointer|power' |
#     head -n1 |
#     awk -F'=' '{print $2}' |
#     cut -d'[' -f1 |
#     xargs)"
# echo "Keyboard ID: $KEYBOARD_ID"
# MOUSE_ID="$(xinput list | grep -iE 'mouse|touchpad' | grep -iE 'slave|slave.*pointer' | grep -iv 'keyboard' | head -n1 | awk -F'=' '{print $2}' | cut -d'[' -f1 | xargs)"
# if ! $ENABLE_INPUT; then
#     echo "$MOUSE_ID,hello"
#     xinput disable "$KEYBOARD_ID"
#     xinput disable "$MOUSE_ID"
# else
#     xinput enable "$KEYBOARD_ID"
#     xinput enable "$MOUSE_ID"
# fi

readonly kbd_enable_pattern='.*↳.*(AT Translated Set 2 keyboard|SONiX USB DEVICE|SONiX USB DEVICE Keyboard)[[:space:]]*id=[[:digit:]]*[[:space:]]*\[slave[[:space:]]*keyboard[[:space:]]*\([[:digit:]]*\)\]'
readonly kbd_disable_pattern='(AT Translated Set 2 keyboard|SONiX USB DEVICE| SONiX USB DEVICE Keyboard)[[:space:]]*id=[[:digit:]]*[[:space:]]*\[floating[[:space:]]*slave\]'
readonly mouse_enable_pattern='.*↳.*(Mouse|Trackpad|TouchPad)[[:space:]]*id=[[:digit:]]*[[:space:]]*\[slave[[:space:]]*pointer[[:space:]]*\([[:digit:]]*\)\]'
readonly mouse_disable_pattern='.*(Mouse|Trackpad|TouchPad)[[:space:]]*id=[[:digit:]]*[[:space:]]*\[floating[[:space:]]*slave\]'

find_device_status() {
    case "$1" in
    keyboard)
        pattern="/∼/ && /$kbd_disable_pattern/ && !/Virtual|Mouse|XTEST/"
        ;;
    mouse)
        pattern="/∼/ && /$mouse_disable_pattern/ "
        ;;
    esac

    xinput list | awk '
        BEGIN { status = "enabled" }
        # Match detached devices (∼ line) that are SONiX keyboard-related
        '"$pattern"' {
            status = "disabled"
            exit 0  # Exit immediately on first match
        }
        END { print status }
    '
}

enable_device() {
    if [ "$(find_device_status "$1")" == "enabled" ]; then
        echo "$1 already enabled. No action taken."
        return 0
    fi

    case "$1" in
    keyboard)
        pattern="/$kbd_disable_pattern/"
        ;;
    mouse)
        pattern="/$mouse_disable_pattern/"
        ;;
    *)
        echo "Usage: enable_device [keyboard|mouse]"
        return 1
        ;;
    esac

    local ids=()
    mapfile -t ids < <(xinput list | awk '
        '"$pattern"' {
            if (match($0, /id=([0-9]+)/, arr)) {
                print arr[1]
            }
        }
    ')

    echo "Executing command: xinput enable ${ids[*]}"
    for id in "${ids[@]}"; do
        xinput enable "$id"
    done
}
disable_device() {
    if [ "$(find_device_status "$1")" == "disabled" ]; then
        echo "$1 already disabled. No action taken."
        return 0
    fi

    case "$1" in
    keyboard)
        pattern="/$kbd_enable_pattern/"
        ;;
    mouse)
        pattern="/$mouse_enable_pattern/"
        ;;
    *)
        echo "Usage: disable_device [keyboard|mouse]"
        return 1
        ;;
    esac

    local ids=()
    mapfile -t ids < <(xinput list | awk '
        '"$pattern"' {
            if (match($0, /id=([0-9]+)/, arr)) {
                print arr[1]
            }
        }
    ')

    echo "Executing command: xinput disable ${ids[*]}"
    for id in "${ids[@]}"; do
        xinput disable "$id"
    done
}

enable_device keyboard
enable_device mouse
