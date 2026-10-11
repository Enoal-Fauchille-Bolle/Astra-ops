#!/usr/bin/env bash
# Administration menu for the Eaton 3S UPS (NUT).
# Installed as /usr/local/bin/nut-tui on Astra, run by hand:
#   ssh -t astra nut-tui
#
# The menu calls upsc, upscmd and upsrw. No password is stored: upscmd and upsrw ask for it on
# the keyboard (hidden input) when an action needs it. Reading the state needs no account.
#
# Optional variables:
#   NUT_HOST  machine hosting the UPS (default: localhost)
#   NUT_USER  NUT administration account (default: enoal)
#
# Left out of the menu on purpose: load.off, load.off.delay, shutdown.stayoff, shutdown.return
# and driver.killpower. They cut the power of Astra and Pulsar, and the administration account
# has no right to run them anyway.

set -u

UPS="eaton3s@${NUT_HOST:-localhost}"
NUT_USER="${NUT_USER:-enoal}"
TITLE="Eaton 3S UPS"

for cmd in whiptail upsc upscmd upsrw; do
    command -v "$cmd" >/dev/null || { echo "Command not found: $cmd" >&2; exit 1; }
done

# Reads a UPS variable; prints "?" when it is missing.
nut_get() {
    local value
    value=$(upsc "$UPS" "$1" 2>/dev/null) && [ -n "$value" ] && echo "$value" || echo "?"
}

pause() {
    echo
    read -r -p "Press Enter to go back to the menu... " _
}

# Turns the NUT status (for example "OL CHRG") into plain words.
describe_status() {
    local word out=""
    for word in $1; do
        case "$word" in
            OL) out+="on mains power, " ;;
            OB) out+="ON BATTERY (power cut), " ;;
            LB) out+="LOW BATTERY, " ;;
            CHRG) out+="battery charging, " ;;
            DISCHRG) out+="battery discharging, " ;;
            RB) out+="battery needs replacing, " ;;
            OVER) out+="overload, " ;;
            *) out+="$word, " ;;
        esac
    done
    echo "${out%, }"
}

show_status() {
    local status runtime
    status=$(nut_get ups.status)
    runtime=$(nut_get battery.runtime)
    [[ "$runtime" =~ ^[0-9]+$ ]] && runtime="$((runtime / 60)) min" || runtime="?"
    whiptail --title "$TITLE: state" --msgbox "\
Status             : $(describe_status "$status") ($status)
Battery            : $(nut_get battery.charge) %
Estimated runtime  : $runtime
Connected load     : $(nut_get ups.load) % (about $(nut_get ups.realpower) W)
Beeper             : $(nut_get ups.beeper.status)

Low battery threshold (NUT)      : $(nut_get battery.charge.low) %
Transfer voltage high / low      : $(nut_get input.transfer.high) V / $(nut_get input.transfer.low) V
Shutdown delay / restart delay   : $(nut_get ups.delay.shutdown) s / $(nut_get ups.delay.start) s" 18 74
}

beeper_menu() {
    local choice
    choice=$(whiptail --title "$TITLE: beeper" --menu \
        "Current beeper: $(nut_get ups.beeper.status)\nThe NUT password of \"$NUT_USER\" is asked next." 15 74 3 \
        beeper.mute "Mute the beeper temporarily (until the next event)" \
        beeper.disable "Disable the beeper" \
        beeper.enable "Enable the beeper again" \
        3>&1 1>&2 2>&3) || return 0
    clear
    echo "Command sent: $choice"
    upscmd -u "$NUT_USER" "$UPS" "$choice" 2>&1 | grep -v '^Init SSL'
    pause
}

# Settings that can be changed, with their label. ups.delay.shutdown and ups.delay.start are
# not listed: upsrw changes them in memory only, and the automatic shutdown reads offdelay and
# ondelay from ups.conf (see README.md in this directory).
declare -A SETTING_LABEL=(
    [input.transfer.high]="High transfer voltage (V)"
    [input.transfer.low]="Low transfer voltage (V)"
)

settings_menu() {
    local var current new items=() choice
    for var in input.transfer.high input.transfer.low; do
        items+=("$var" "${SETTING_LABEL[$var]}: $(nut_get "$var")")
    done
    choice=$(whiptail --title "$TITLE: settings" --menu \
        "Choose the setting to change." 12 74 2 "${items[@]}" 3>&1 1>&2 2>&3) || return 0

    current=$(nut_get "$choice")
    new=$(whiptail --title "${SETTING_LABEL[$choice]}" --inputbox \
        "Current value: $current\nNew value (whole number):" 10 60 "$current" \
        3>&1 1>&2 2>&3) || return 0

    if ! [[ "$new" =~ ^[0-9]+$ ]]; then
        whiptail --title "Value rejected" --msgbox "\"$new\" is not a whole number." 8 50
        return 0
    fi
    [ "$new" = "$current" ] && { whiptail --msgbox "Same value, nothing to do." 8 40; return 0; }

    whiptail --title "Confirmation" --yesno \
        "${SETTING_LABEL[$choice]}\n\n  $current  →  $new\n\nThe NUT password of \"$NUT_USER\" is asked next.\nApply?" 14 64 || return 0
    clear
    upsrw -s "$choice=$new" -u "$NUT_USER" "$UPS" 2>&1 | grep -v '^Init SSL'
    echo "Value read back: $(nut_get "$choice")"
    pause
}

while true; do
    choice=$(whiptail --title "$TITLE" --menu "$UPS: $(describe_status "$(nut_get ups.status)")" 16 74 4 \
        1 "Show the UPS state" \
        2 "Beeper" \
        3 "Settings (transfer voltages)" \
        0 "Quit" \
        3>&1 1>&2 2>&3) || break
    case "$choice" in
        1) show_status ;;
        2) beeper_menu ;;
        3) settings_menu ;;
        *) break ;;
    esac
done
clear
