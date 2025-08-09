## README.md

# Gym Group Python API (HA-friendly fork)

This fork builds on the original project by **@joestanding** and focuses on being efficient, resilient, and friendly for continuous use — especially with **Home Assistant**.

## What it does

Fetches the **currentCapacity** (people count) for your **home gym** from The Gym Group’s private mobile API and prints **only a number** to stdout — ideal for HA `command_line` sensors.

## Key improvements

- **Numeric-only output** for HA: stdout is only the people count; errors go to stderr.
- **15-minute caching (TTL)**: avoids unnecessary API calls.
- **Session reuse**: cookies + user IDs persisted; **login only when needed** (on 401/403).
- **ETag support**: sends `If-None-Match` to allow `304 Not Modified`.
- **Silent retries**: quick retry/backoff for transient 429/5xx/timeouts.
- **Graceful fallback**: if the API hiccups, returns **last known value**.

## Installation

bash
git clone https://github.com/brutus6/gymgroup-api.git
cd gymgroup-api
pip install -r requirements.txt   # or: pip install requests PyYAML


## Usage with Home Assistant

Example command_line sensor in configuration.yaml:

command_line:
  - sensor:
      name: "Gym Occupancy Raw"
      command: "python3 /config/gymapi.py"
      unit_of_measurement: "people"
      scan_interval: 900
      value_template: "{{ value | int(0) }}"

## Configuration

Create a secrets.yaml file in your Home Assistant config directory with:

gym_group_username: "your_email@example.com"
gym_group_password: "your_pin_or_password"

Update the secrets_path variable in the script if it’s not in /config/secrets.yaml.

## Contributing

I welcome contributions to this project. If you have suggestions or improvements, please submit a pull request. This script was forked from the original work of  **@joestanding**.

