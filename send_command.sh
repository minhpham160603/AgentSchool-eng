#!/bin/bash
# Write an observer command to observer_cmd.json in the current directory.

COMMAND_FILE="observer_cmd.json"

usage() {
    cat <<EOF
Usage: $0 <command> [options]

Commands:
  pause                 Pause after the current round
  resume                Resume the simulation
  status                Print the current simulation state
  exit                  Stop the simulation
  intervene [message]   Send a teaching-plan intervention note
  rollback <turn> [class]
                        Restore a saved teacher checkpoint
  -h, --help            Show this help

Examples:
  $0 pause
  $0 status
  $0 intervene "Add a short group discussion"
  $0 rollback 12
  $0 rollback 8 2
EOF
}

if [ $# -lt 1 ]; then
    usage >&2
    exit 2
fi

COMMAND=$1
if [ "$COMMAND" = "-h" ] || [ "$COMMAND" = "--help" ]; then
    usage
    exit 0
fi

case "$COMMAND" in
    pause|resume|status|exit)
        printf '{\n  "command": "%s"\n}\n' "$COMMAND" > "$COMMAND_FILE"
        echo "✅ Sent $COMMAND command"
        ;;

    intervene)
        INSTRUCTION=${2:-Add an interactive activity}
        python - "$INSTRUCTION" > "$COMMAND_FILE" <<'PY'
import json
import sys

print(json.dumps({
    "command": "intervene",
    "intervention": {
        "type": "adjust_plan",
        "instruction": sys.argv[1],
    },
}, indent=2))
PY
        echo "✅ Sent intervention: $INSTRUCTION"
        ;;

    rollback)
        TURN=${2:-}
        CLASS=${3:-}
        if ! [[ "$TURN" =~ ^[0-9]+$ ]]; then
            echo "❌ Usage: $0 rollback <positive turn> [positive class]" >&2
            exit 2
        fi
        if [ -n "$CLASS" ] && ! [[ "$CLASS" =~ ^[0-9]+$ ]]; then
            echo "❌ Class must be a positive integer" >&2
            exit 2
        fi
        if ! PAYLOAD=$(python - "$TURN" "$CLASS" <<'PY'
import json
import sys

turn = int(sys.argv[1], 10)
class_value = int(sys.argv[2], 10) if sys.argv[2] else None
if turn < 1:
    raise SystemExit("Turn must be a positive integer")
if class_value is not None and class_value < 1:
    raise SystemExit("Class must be a positive integer")

rollback = {"turn": turn}
if class_value is not None:
    rollback["class"] = class_value
print(json.dumps({"command": "rollback", "rollback": rollback}, indent=2))
PY
        )
        then
            exit 2
        fi
        printf '%s\n' "$PAYLOAD" > "$COMMAND_FILE"
        echo "✅ Sent rollback command: turn=$TURN class=${CLASS:-current}"
        ;;

    *)
        echo "❌ Unknown command: $COMMAND" >&2
        usage >&2
        exit 2
        ;;
esac

echo
echo "Command payload:"
python -m json.tool "$COMMAND_FILE"
