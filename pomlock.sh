#!/bin/bash
# Configure with: pomlock --config-file /path/to/config

# Default configuration
CONFIG_FILE="${HOME}/.config/pomlock.conf"
LOG_FILE="${HOME}/.local/share/pomlock/time.log"
declare -A PRESETS=(
    ["standard"]="25 5 5 4"  # 25/5/5x4
    ["extended"]="40 3 10 3" # 40/10/20x3
    ["custom"]=""            # User-provided
)

# Load configuration
load_config() {
    source "$CONFIG_FILE" 2>/dev/null || {
        echo "Using default configuration"
        WORK_DURATION=36
        SHORT_BREAK=6
        LONG_BREAK=12
        CYCLES_BEFORE_LONG=3
        ENABLE_INPUT=false
        OVERLAY_OPTS="--font-size 48 --color white --bg-color black --opacity 0.8"
    }
}

load_config

# Parse arguments
OVERLAY_OPTS=()
while [[ $# -gt 0 ]]; do
    case $1 in
    --font-size | --color | --bg-color | --opacity | --notify)
        OVERLAY_OPTS+=("$1" "$2")
        shift 2
        ;;
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
    -c | --config-file)
        CONFIG_FILE="$2"
        shift 2
        ;;
    -l | --log-file)
        LOG_FILE="$2"
        shift 2
        ;;
    --enable-input)
        ENABLE_INPUT=true
        shift
        ;;
    *)
        break
        ;;
    esac
done

log_entry() {
    local event_type=$1
    local duration=$2
    echo -e "$(date -u +"%Y-%m-%dT%H:%M:%SZ")\t$event_type\t$duration\t$cycle_count" >>"$LOG_FILE"
}

readonly kbd_enable_pattern='.*↳.*(AT Translated Set 2 keyboard|SONiX USB DEVICE|SONiX USB DEVICE Keyboard)[[:space:]]*id=[[:digit:]]*[[:space:]]*\[slave[[:space:]]*keyboard[[:space:]]*\([[:digit:]]*\)\]'
readonly kbd_disable_pattern='(AT Translated Set 2 keyboard|SONiX USB DEVICE| SONiX USB DEVICE Keyboard)[[:space:]]*id=[[:digit:]]*[[:space:]]*\[floating[[:space:]]*slave\]'
readonly mouse_enable_pattern='.*↳.*(Mouse|Trackpad|TouchPad)[[:space:]]*id=[[:digit:]]*[[:space:]]*\[slave[[:space:]]*pointer[[:space:]]*\([[:digit:]]*\)\]'
readonly mouse_disable_pattern='.*(Mouse|Trackpad|TouchPad)[[:space:]]*id=[[:digit:]]*[[:space:]]*\[floating[[:space:]]*slave\]'

find_device_status() {
    case "$1" in
    keyboard)
        pattern="/∼/ && /$kbd_detach_pattern/ && !/Virtual|Mouse|XTEST/"
        ;;
    mouse)
        pattern="/∼/ && /$mouse_detach_pattern/ "
        ;;
    esac

    xinput list | awk '
        BEGIN { status = "attached" }
        # Match detached devices (∼ line) that are SONiX keyboard-related
        '"$pattern"' {
            status = "detached"
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

    echo "Enabling $1 with: xinput enable ${ids[*]}"
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

    echo "Disabling $1 with: xinput disable ${ids[*]}"
    for id in "${ids[@]}"; do
        xinput disable "$id"
    done
}

# Device control functions
disable_devices() {
    if ! $ENABLE_INPUT; then
        disable_device keyboard
        disable_device mouse
    fi
}

enable_devices() {
    if ! $ENABLE_INPUT; then
        enable_device keyboard
        enable_device mouse
    fi
}

# Main loop with logging
log_entry "Session started - Work: ${WORK_DURATION}m, Break: ${SHORT_BREAK}m"

while true; do
    # Work period
    echo "Session started - Work: ${WORK_DURATION}m, Break: ${SHORT_BREAK}m"
    sleep $((WORK_DURATION * 60))
    log_entry "Work period completed"

    # Break logic
    ((cycle_count++))
    if [ $cycle_count -ge "$CYCLES_BEFORE_LONG" ]; then
        break_duration=$LONG_BREAK
        cycle_count=0
        echo "Long break started"
        log_entry "Long break started"
    else
        break_duration=$SHORT_BREAK
        echo "Short break started"
        log_entry "Short break started"
    fi

    # Block input and show overlay
    disable_devices
    python ./pomlock-overlay.py "$((break_duration * 60))" "${OVERLAY_ARGS[@]}"
    # /usr/lib/pomlock/pomlock-overlay.py "$break_duration" "${OVERLAY_ARGS[@]}"

    echo "Break completed"
    log_entry "Break completed"

    # Restore input
    enable_devices
    pkill -f pomlock-overlay.py
done
