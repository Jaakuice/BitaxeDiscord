#!/usr/bin/env python3

import requests
import json
from datetime import datetime
import sys

def fetch_and_save_data(file_path, previous_best_diff, previous_core_voltage_actual, min_core_voltage_alert_threshold):
    api_url = 'http://**ENTER YOUR BITAXE IP**/api/system/info'

    try:
        response = requests.get(api_url)
        data = response.json()

        desired_fields = ["power", "voltage", "current", "fanSpeed", "temp",
                          "hashRate", "bestDiff", "coreVoltage",
                          "coreVoltageActual", "frequency", "sharesAccepted",
                          "sharesRejected", "uptimeSeconds"]

        extracted_data = {field: data.get(field) for field in desired_fields}
        extracted_data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M")

        with open(file_path, 'a') as file:
            json.dump(extracted_data, file)
            file.write('\n')

        # Check for changes in bestDiff value and other checks...

    except Exception as e:
        print(f'Error fetching or saving data: {e}')

    # After completing the task, exit the script
    sys.exit()

if __name__ == "__main__":
    # Set your file path and initial values for global variables
    data_file_path = '**ENTER YOUR FILE PATH TO DATA** /data.json'
    initial_previous_best_diff = None
    initial_previous_core_voltage_actual = None
    initial_min_core_voltage_alert_threshold = 0  # Set your threshold

    # Call the function with initial values
    fetch_and_save_data(data_file_path, initial_previous_best_diff, initial_previous_core_voltage_actual, initial_min_core_voltage_alert_threshold)
