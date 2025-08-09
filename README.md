## README.md
Gym Group Python API
This script is a fork of the Gym Group Python API originally written by joestanding. It has been enhanced to be more efficient and resilient for continuous use, particularly in environments like Home Assistant.

## Overview
This Python script interacts with The Gym Group's private API to retrieve the current occupancy of a specified home gym. It's designed to be run as a service or sensor, providing a real-time (or near real-time) count of how many people are in your gym.

## Key Features
Efficient API Interaction: The script now caches session information, avoiding the need to log in on every execution.

Request Caching: To reduce API calls, the script stores the last-known occupancy value and only requests new data after a set period.

Automatic Re-authentication: The script can automatically detect an expired session and re-login without manual intervention.

Robust Error Handling: It includes a retry mechanism for transient network issues and a graceful fallback to a cached value if a data fetch fails.

## Installation & Usage
Clone the Repository:

Bash

git clone [your repository URL]
cd [your repository name]
Install Dependencies:
This script requires the requests and PyYAML libraries. You can install them using pip:

Bash

pip install requests PyYAML
Configure Credentials:
You must create a secrets.yaml file in the same directory as the script. This file will store your Gym Group login details.

secrets.yaml should look like this:

YAML

gym_group_username: "your_username"
gym_group_password: "your_password"
Note: If you are using this with Home Assistant, ensure the secrets_path variable in the script is correctly set to your Home Assistant configuration directory.

Run the Script:
You can run the script from your terminal:

Bash

python your_script_name.py
The script will print the current gym occupancy to standard output. Any errors will be printed to standard error.

## Contributing
I welcome contributions to this project. If you have suggestions or improvements, please submit a pull request. This script was forked from the original work of joestanding.
