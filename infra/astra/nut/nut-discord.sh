#!/bin/bash

WEBHOOK_URL="https://discord.com/api/webhooks/CHANGE_ME"

# NUT passes the notification message as the first argument
MESSAGE="$1"
EVENT_TYPE="${NOTIFYTYPE:-UNKNOWN}"

# Assign decimal color codes based on event severity
COLOR=16777215
case "$EVENT_TYPE" in
    "ONLINE" | "COMMOK")
        COLOR=3066993 ;; # Green
    "ONBATT" | "COMMBAD"| "NOCOMM" | "CAL")
        COLOR=16753920 ;; # Orange
    "LOWBATT" | "FSD" | "SHUTDOWN" | "REPLBATT" | "NOPARENT")
        COLOR=15158332 ;; # Red
    "UNKNOWN")
        COLOR=9936031 ;; # Grey
esac

# Heredoc to build JSON payload without external dependencies
PAYLOAD=$(cat <<EOF
{
    "username": "Eaton 3S 550 FR",
    "avatar_url": "https://www.taktek.cz/eaton-logo.png",
    "embeds": [{
        "title": "UPS Status Update",
        "description": "${MESSAGE}",
        "color": ${COLOR},
        "fields": [
            {"name": "Trigger", "value": "${EVENT_TYPE}", "inline": true}
        ]
    }]
}
EOF
)

curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$WEBHOOK_URL" > /dev/null
