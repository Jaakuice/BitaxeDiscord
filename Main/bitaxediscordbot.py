#!/usr/bin/env python3

import requests
import json
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt
import numpy as np 
import urllib.request
import discord
from discord.ext import tasks, commands
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dateutil import parser
import asyncio
import time
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import configparser
import re

# Load configuration from config.ini
config = configparser.ConfigParser()
config.read('**ENTER YOUR FILE PATH TO CONFIG**/config.ini')

# Get values from the configuration
TOKEN = config.get('Bot', 'TOKEN')
file_path = config.get('File', 'file_path')
MAX_FILE_SIZE_MB = config.getint('File', 'MAX_FILE_SIZE_MB')
PRUNE_THRESHOLD_MB = config.getint('File', 'PRUNE_THRESHOLD_MB')
user_set_voltage_threshold = config.getint('File', 'user_set_voltage_threshold')
user_temp_threshold = config.getint('File', 'user_temp_threshold')
user_fan_threshold = config.getint('File', 'user_fan_threshold')
CONFIG_FILE_PATH = '**ENTER YOUR FILE PATH TO CONFIG**/config.ini'

# Discord Bot Setup
intents = discord.Intents.all()
intents.messages = True
intents.guilds = True
intents.reactions = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    global notification_channel
    print(f'We have logged in as {bot.user.name}')

    # Set the bot's activity (status)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="the Bitaxe"))

    # Get the default channel for notifications
    notification_channel = bot.get_channel(bot.guilds[0].text_channels[0].id)

    # Start the file monitoring loop
    file_monitor.start()

    # Print a message in the chat
    if notification_channel:
        await notification_channel.send("🚀 Bitaxe Bot is ready! Let's mine some blocks! 🌟 !helpful for commands")

    print('Bot is ready!')

# Define a variable to store the channel for notifications
notification_channel = None

@tasks.loop(seconds=45)  # Set the interval as needed
async def file_monitor():
    await notify_diff_change()  # Use await to properly call the asynchronous function
    await check_core_voltage_alert()  # Check for coreVoltageActual alert
    await check_high_temp_alert()  # Check for high temperature alert
    await check_low_fan_speed(entries)  # Check for low fan speed
    await notify_rejected_shares_change()  # Add this line to check for rejected shares change

# Function to notify Discord on bestDiff change
async def notify_diff_change():
    entries = []

    with open(file_path, 'r') as file:
        for line in file:
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError:
                print(f"Error decoding JSON: {line}")

    if len(entries) < 2:
        # Not enough entries for comparison
        return

    latest_entry = entries[-1]
    previous_entry = entries[-2]

    latest_diff = latest_entry.get('bestDiff')
    previous_diff = previous_entry.get('bestDiff')

    print(f'Latest Diff: {latest_diff}, Previous Diff: {previous_diff}')

    if latest_diff is not None and previous_diff is not None and latest_diff != previous_diff:
        # Get the default channel to send the notification
        default_channel = bot.get_channel(bot.guilds[0].text_channels[0].id)

        # Send Discord notification to the default channel
        if default_channel:
            message = f"**🎉 New Best Difficulty achieved: {latest_diff}** (old diff: {previous_diff}) 🚀💪🔥"
            await default_channel.send(message)
            print(message)

async def check_core_voltage_alert():
    entries = get_all_entries(file_path)

    if not entries:
        return

    latest_entry = entries[-1]
    core_voltage_actual = latest_entry.get('coreVoltageActual')

    if core_voltage_actual is not None and core_voltage_actual < user_set_voltage_threshold:
        # Send Discord notification about low coreVoltageActual
        if notification_channel:
            message = f"⚠️ **Low Core Voltage Alert!** Current Core Voltage: {core_voltage_actual} mV (Threshold: {user_set_voltage_threshold} mV ⚠️)"
            await notification_channel.send(message)
            print(message)

async def check_high_temp_alert():
    entries = get_all_entries(file_path)

    if not entries:
        return

    latest_entry = entries[-1]
    temperature = latest_entry.get('temp')

    if temperature is not None and temperature > user_temp_threshold:
        # Send Discord notification about high temperature
        if notification_channel:
            message = f"⚠️ **High Temperature Alert!** Current Temperature: {temperature} °C (Threshold: {user_temp_threshold} °C ⚠️)"
            await notification_channel.send(message)
            print(message)

# Function to check low fan speed
async def check_low_fan_speed(entries):
    latest_entry = entries[-1] if entries else None
    if latest_entry:
        fan_speed = latest_entry.get('fanSpeed', 0)
        if fan_speed < user_fan_threshold:
            message = f"⚠️ **Low Fan Speed Alert!** Current Fan Speed is {fan_speed}. (Threshold: {user_fan_threshold}) ⚠️"
            await notification_channel.send(message)
            print(message)

# Function to notify Discord on rejected shares change
async def notify_rejected_shares_change():
    entries = get_all_entries(file_path)

    if len(entries) < 2:
        # Not enough entries for comparison
        return

    latest_entry = entries[-1]
    previous_entry = entries[-2]

    latest_rejected_shares = latest_entry.get('sharesRejected', 0)
    previous_rejected_shares = previous_entry.get('sharesRejected', 0)

    print(f'Latest Rejected Shares: {latest_rejected_shares}, Previous Rejected Shares: {previous_rejected_shares}')

    if latest_rejected_shares > previous_rejected_shares:
        # Get the default channel to send the notification
        default_channel = bot.get_channel(bot.guilds[0].text_channels[0].id)

        # Send Discord notification to the default channel
        if default_channel:
            message = f"**❌ Rejected Shares Increase: {latest_rejected_shares} shares** (Previous: {previous_rejected_shares}) ❌"
            await default_channel.send(message)
            print(message)

# Function to parse user input for timeframe
def parse_timeframe(input_str):
    match = re.match(r'(\d+)([mdh])', input_str)
    if match:
        value, unit = int(match.group(1)), match.group(2)
        if unit == 'm':
            return value
        elif unit == 'h':
            return value * 60
        elif unit == 'd':
            return value * 24 * 60
    else:
        return None

# Function to prune entries based on file size
def prune_entries_by_size(file_path, max_file_size_mb=450):  # Adjust the max_file_size_mb as needed
    if os.path.exists(file_path):
        # Check the size of the file
        file_size = os.path.getsize(file_path)

        # If the file size exceeds the limit, prune entries
        if file_size > max_file_size_mb * 1024 * 1024:
            records = []
            with open(file_path, 'r') as file:
                records = [json.loads(line) for line in file]

            # Keep a percentage of the most recent entries to reach the desired file size
            records_to_keep = int(0.9 * len(records))  # Adjust the percentage as needed

            # Write back the pruned records
            with open(file_path, 'w') as file:
                for record in records[-records_to_keep:]:
                    json.dump(record, file)
                    file.write('\n')

            print('Entries pruned based on file size successfully.')

# Function to retrieve the latest entry from the database
def get_latest_entry(file_path):
    records = []
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            for line in file:
                try:
                    record = json.loads(line)
                    records.append(record)
                except json.JSONDecodeError as e:
                    print(f'Error decoding JSON: {e}')

    return records[-1] if records else {}

# Function to retrieve entries within a specified timeframe
def get_entries_within_timeframe(file_path, start_time):
    entries_within_timeframe = []

    with open(file_path, 'r') as file:
        for line in file:
            try:
                entry = json.loads(line)
                timestamp = datetime.strptime(entry['timestamp'], "%Y-%m-%d %H:%M")
                
                if timestamp >= start_time:
                    entries_within_timeframe.append(entry)
            except json.JSONDecodeError:
                print(f"Error decoding JSON: {line}")

    print("Entries within timeframe:")
    print(entries_within_timeframe)

    return entries_within_timeframe

# Function to calculate average hashrate
def calculate_average_hashrate(entries, duration=None):
    if duration:
        entries_within_duration = [entry for entry in entries if parse_timestamp(entry['timestamp']) >= (datetime.now() - duration)]
    else:
        entries_within_duration = entries

    if not entries_within_duration:
        return 0  # or any default value you prefer

    total_hashrate = sum(entry.get('hashRate', 0) for entry in entries_within_duration)  # Assuming 'hashRate' is the key in your entries
    average_hashrate = total_hashrate / len(entries_within_duration)
    
    return round(average_hashrate, 2)

def calculate_av_hashrate(entries, duration=None):
    if duration:
        entries_within_duration = [entry for entry in entries if parse_timestamp(entry['timestamp']) >= (datetime.now() - duration)]
    else:
        entries_within_duration = entries

    if not entries_within_duration:
        return 0  # or any default value you prefer

    total_hashrate = sum(entry.get('hashRate', 0) for entry in entries_within_duration)  # Assuming 'hashRate' is the key in your entries
    average_hashrate = total_hashrate / len(entries_within_duration)
    
    return round(average_hashrate, 2)

def calculate_av_efficiency(entries, duration=None):
    if duration:
        entries_within_duration = [entry for entry in entries if parse_timestamp(entry['timestamp']) >= (datetime.now() - duration)]
    else:
        entries_within_duration = entries

    if not entries_within_duration:
        return 0  # or any default value you prefer

    total_power = sum(entry.get('power', 0) for entry in entries_within_duration)  # Assuming 'power' is the key in your entries
    total_hashrate = sum(entry.get('hashRate', 0) for entry in entries_within_duration)  # Assuming 'hashRate' is the key in your entries

    avg_efficiency = total_power / (total_hashrate / 1000) if total_hashrate != 0 else 0
    
    return round(avg_efficiency, 2)

def get_all_entries(file_path):
    try:
        entries = []
        with open(file_path, 'r') as file:
            for line in file:
                entry = json.loads(line)
                entries.append(entry)
        return entries
    except FileNotFoundError:
        print(f'Error: Database file not found at {file_path}')
        return []
    except json.JSONDecodeError:
        print(f'Error: Invalid JSON format in the database file at {file_path}')
        return []
    except Exception as e:
        print(f'An unexpected error occurred: {str(e)}')
        return []

# Example usage
entries = get_all_entries(file_path)

# Now, 'entries' contains a list of dictionaries, where each dictionary represents an entry from your data.


# Discord Bot Setup

@bot.event
async def on_guild_join(guild):
    # Find the first text channel in the server
    default_channel = next((channel for channel in guild.channels if isinstance(channel, discord.TextChannel)), None)

    if default_channel:
        welcome_message = "Hello! I've been added to this server. Thank you for having me!"
        await default_channel.send(welcome_message)

# Function to show the latest entry
@bot.command()
async def latest(ctx):
    latest_entry = get_latest_entry(file_path)

    # Format the data with each value on a separate line, using bold and more emojis
    formatted_data = (
        f'**Latest Entry** 📊\n'
        f'**Timestamp:** {latest_entry["timestamp"]} ⌛\n'
        f'**Hashrate:** {latest_entry["hashRate"]} Gh/s ⛏️\n'
        f'**Temperature:** {latest_entry["temp"]} °C 🌡️\n'
        f'**Voltage:** {latest_entry["voltage"]} V ⚡\n'
        f'**Fan Speed:** {latest_entry["fanSpeed"]} RPM 🌀\n'
        f'**Shares Accepted:** {latest_entry["sharesAccepted"]} ✅\n'
        f'**Shares Rejected:** {latest_entry["sharesRejected"]} ❌\n'
        f'**Power:** {latest_entry["power"]} W 💡\n'
        f'**Current:** {latest_entry["current"]} A 🔌\n'
        f'**Best Difficulty:** {latest_entry["bestDiff"]} 💪\n'
        f'**Core Voltage:** {latest_entry["coreVoltage"]} V ⚙️\n'
        f'**Actual Core Voltage:** {latest_entry["coreVoltageActual"]} V ⚙️\n'
        f'**Frequency:** {latest_entry["frequency"]} MHz 📡\n'
        f'**Uptime:** {latest_entry["uptimeSeconds"]} seconds ⏰\n'
    )

    await ctx.send(formatted_data)

# Function to check file size
@bot.command()
async def file_size(ctx):
    try:
        # Get the file size in bytes
        size_in_bytes = os.path.getsize(file_path)

        # Convert bytes to megabytes
        size_in_mb = size_in_bytes / (1024 ** 2)

        # Include information about the maximum file size
        await ctx.send(f'The current size of the data file is {size_in_mb:.2f} MB📂. Pruning will begin at {PRUNE_THRESHOLD_MB} MB.⚙️')

        # Check if pruning is needed
        if size_in_mb > MAX_FILE_SIZE_MB:
            # Calculate the difference between the current size and the maximum size
            size_difference = size_in_mb - MAX_FILE_SIZE_MB

            await ctx.send(f'Pruning is needed. The file size exceeds the maximum limit by {size_difference:.2f} MB.')

            # Prune entries to reduce the file size
            prune_entries_by_size(file_path, max_file_size_mb=MAX_FILE_SIZE_MB)

            # Get the updated file size
            size_in_bytes = os.path.getsize(file_path)
            size_in_mb = size_in_bytes / (1024 ** 2)

            await ctx.send(f'Pruning completed. The new size of the data file is {size_in_mb:.2f} MB.')

    except FileNotFoundError:
        await ctx.send('Error: Data file not found.')

@bot.command()
async def set_size(ctx, new_max_size: int = None, new_prune_threshold: int = None):
    global MAX_FILE_SIZE_MB, PRUNE_THRESHOLD_MB

    if new_max_size is None or new_prune_threshold is None:
        await ctx.send(
            f".\n"
            f"Invalid input. Please provide positive values in MB.\n"
            f"Example usage: `!set_file_size (Max Size MB) (Pruning starts @ MB)`\n"
            f"Example usage: `!set_file_size 500 450`\n"
        )
        return

    # Validate input values
    if new_max_size <= 0 or new_prune_threshold <= 0:
        await ctx.send("Invalid input. Please provide positive values.")
        return

    # Display the proposed changes for confirmation
    confirmation_message = (
        f"Proposed changes:\n"
        f"Maximum file size: {new_max_size} MB\n"
        f"Pruning threshold: {new_prune_threshold} MB\n\n"
        f"Do you want to apply these changes? (yes/no)"
    )

    # Send the confirmation message
    await ctx.send(confirmation_message)

    try:
        # Wait for a response from the user
        confirmation = await bot.wait_for(
            'message',
            timeout=30,
            check=lambda message: message.author == ctx.author and message.channel == ctx.channel
        )

        # Check the user's response
        if confirmation.content.lower() == 'yes':
            # Update global variables
            MAX_FILE_SIZE_MB = new_max_size
            PRUNE_THRESHOLD_MB = new_prune_threshold

            # Update the configuration file
            config.set('File', 'MAX_FILE_SIZE_MB', str(new_max_size))
            config.set('File', 'PRUNE_THRESHOLD_MB', str(new_prune_threshold))
            with open('CONFIG_FILE_PATH', 'w') as config_file:
                config.write(config_file)

            # Provide confirmation to the user
            success_message = (
                f"Changes applied successfully. New settings:\n"
                f"Maximum file size: {MAX_FILE_SIZE_MB} MB\n"
                f"Pruning threshold: {PRUNE_THRESHOLD_MB} MB"
            )
            await ctx.send(success_message)
        else:
            await ctx.send("Changes were not applied.")

    except asyncio.TimeoutError:
        await ctx.send("Confirmation timed out. Changes were not applied.")

@bot.command()
async def set_volt(ctx, threshold: int):
    global user_set_voltage_threshold

    if threshold <= 0:
        await ctx.send("Invalid input. Please provide a positive threshold value.")
        return

    print(f"Before change: {user_set_voltage_threshold}")

    # Display the proposed change for confirmation
    confirmation_message = (
        f"Proposed change:\n"
        f"User-set voltage threshold: {threshold}\n\n"
        f"Do you want to apply this change? (yes/no)"
    )

    # Send the confirmation message
    await ctx.send(confirmation_message)

    try:
        # Wait for a response from the user
        confirmation = await bot.wait_for(
            'message',
            timeout=30,
            check=lambda message: message.author == ctx.author and message.channel == ctx.channel
        )

        # Check the user's response
        if confirmation.content.lower() == 'yes':
            # Update the global variable
            user_set_voltage_threshold = threshold

            print(f"After change: {user_set_voltage_threshold}")

            # Update the configuration file
            config.set('File', 'user_set_voltage_threshold', str(threshold))
            with open('CONFIG_FILE_PATH', 'w') as config_file:
                config.write(config_file)

            # Provide confirmation to the user
            success_message = f"Change applied successfully. New user-set voltage threshold: {user_set_voltage_threshold}"
            await ctx.send(success_message)
        else:
            await ctx.send("Change was not applied.")

    except asyncio.TimeoutError:
        await ctx.send("Confirmation timed out. Change was not applied.")

@bot.command()
async def set_temp(ctx, threshold: int):
    global user_temp_threshold

    if threshold <= 0:
        await ctx.send("Invalid input. Please provide a positive threshold value.")
        return

    # Display the proposed change for confirmation
    confirmation_message = (
        f"Proposed change:\n"
        f"User-set temperature threshold: {threshold} °C\n\n"
        f"Do you want to apply this change? (yes/no)"
    )

    # Send the confirmation message
    await ctx.send(confirmation_message)

    try:
        # Wait for a response from the user
        confirmation = await bot.wait_for(
            'message',
            timeout=30,
            check=lambda message: message.author == ctx.author and message.channel == ctx.channel
        )

        # Check the user's response
        if confirmation.content.lower() == 'yes':
            # Update the global variable
            user_temp_threshold = threshold

            # Update the configuration file
            config.set('File', 'user_temp_threshold', str(threshold))
            with open('CONFIG_FILE_PATH', 'w') as config_file:
                config.write(config_file)

            # Provide confirmation to the user
            success_message = f"Change applied successfully. New user-set temperature threshold: {user_temp_threshold} °C"
            await ctx.send(success_message)
        else:
            await ctx.send("Change was not applied.")

    except asyncio.TimeoutError:
        await ctx.send("Confirmation timed out. Change was not applied.")

# Command to set user_fan_threshold
@bot.command()
async def set_fan(ctx, threshold: int):
    global user_fan_threshold

    if threshold < 0:
        await ctx.send("Invalid input. Please provide a positive threshold value.")
        return

    # Display the proposed change for confirmation
    confirmation_message = (
        f"Proposed change:\n"
        f"User-set fan speed threshold: {threshold}\n\n"
        f"Do you want to apply this change? (yes/no)"
    )

    # Send the confirmation message
    await ctx.send(confirmation_message)

    try:
        # Wait for a response from the user
        confirmation = await bot.wait_for(
            'message',
            timeout=30,
            check=lambda message: message.author == ctx.author and message.channel == ctx.channel
        )

        # Check the user's response
        if confirmation.content.lower() == 'yes':
            # Update the global variable
            user_fan_threshold = threshold

            # Update the configuration file
            config.set('File', 'user_fan_threshold', str(threshold))
            with open(CONFIG_FILE_PATH, 'w') as config_file:
                config.write(config_file)

            # Provide confirmation to the user
            success_message = f"Change applied successfully. New user-set fan speed threshold: {user_fan_threshold}"
            await ctx.send(success_message)
        else:
            await ctx.send("Change was not applied.")

    except asyncio.TimeoutError:
        await ctx.send("Confirmation timed out. Change was not applied.")

# Function to show help information
@bot.command()
async def helpful(ctx):
    help_message =   """
    .
    .
    🤖 **Bitaxe Discord Bot Commands** 🚀

    📜 **Available Commands**:

    ➡️ **!latest**
    Displays the *latest entry* from the data file.

    ➡️ **!file_size**
    Shows the current size of the data file and performs *pruning* if necessary.

    ➡️ **!set_size [new_max_size] [new_prune_threshold]**
    Sets the *maximum file size* and *pruning threshold*. Example: `!set_size 500 450`

    ➡️ **!set_volt [threshold]**
    Sets the user-defined *voltage threshold*. Example: `!set_volt 10`

    ➡️ **!set_temp [threshold]**
    Sets the user-defined *temperature threshold*. Example: `!set_temp 75`

    ➡️ **!set_fan [threshold]**
    Sets the user-defined *fan speed threshold*. Example: `!set_fan 3000`

    ➡️ **!best**
    Shows the current *Best Difficulty Value*.

    ➡️ **!average**
    Calculates and displays *average hashrates* over various timeframes using available data.
    Missing data is not included in the calculations.

    ➡️ **!hash**
    Displays the *total hashrate* based on available data.
    Assumes all missing data to be zero.

    ➡️ **!plot [days] [smoothing]**
    Generates and displays a *plot of hashrate over time* with user-specified *timeframe and smoothing*.
    Example: `!plot 7d 2h`

    💡 **Alerts**:

    ➡️ **Notify of New Best Difficulty**
    Notifies about a change in Best Difficulty.

    ➡️ **"coreVoltageActual" Alert**
    Checks and notifies about low core voltage.

    ➡️ **"temp" Alert**
    Checks and notifies about high temperature.

    ➡️ **"fanSpeed" Alert**
    Checks and notifies about low fan speed.

    ➡️ **Notify of Rejected Shares**
    Notifies about an increase in rejected shares.

    😀**!about**💸

    """
    await ctx.send(help_message)

# Function to show help information
@bot.command()
async def averageinfo(ctx):
    help_message =   """
    .
    .
    ➡️ **!average**
    Calculates and displays *average hashrates* over various timeframes using available data.
    Missing data is not included in the calculations.

    ➡️ **!hash**
    Displays the *total hashrate* based on available data.
    Assumes all missing data to be zero.

    **Example**:
    Suppose a user has 6 hours of hashing data at 500 Gh/s at the beginning of the week
    and at the end of the week, with a significant amount of missing data in between.
    The !average command will show an average of 500 Gh/s based on the available data,
    while the !hash command will assume any missing data to be zero, which would show an
    average of 17.86Gh/s
    """
    await ctx.send(help_message)

@bot.command()
async def best(ctx):
    # Load the latest entry from the database
    latest_entry = get_latest_entry(file_path)
    best_diff_value = latest_entry.get('bestDiff', 'N/A')
    
    await ctx.send(f'**Current Best Difficulty Value:** {best_diff_value} 🚀💪🔥')

@bot.command()
async def average(ctx):
    try:
        # Retrieve entries within specific timeframes
        entries_within_1m = get_entries_within_timeframe(file_path, datetime.now() - timedelta(minutes=1))
        entries_within_5m = get_entries_within_timeframe(file_path, datetime.now() - timedelta(minutes=5))
        entries_within_1h = get_entries_within_timeframe(file_path, datetime.now() - timedelta(hours=1))
        entries_within_24h = get_entries_within_timeframe(file_path, datetime.now() - timedelta(days=1))
        entries_within_week = get_entries_within_timeframe(file_path, datetime.now() - timedelta(weeks=1))
        entries_within_month = get_entries_within_timeframe(file_path, datetime.now() - timedelta(days=30))
        entries_within_year = get_entries_within_timeframe(file_path, datetime.now() - timedelta(days=365))

        # Calculate averages for each timeframe
        avg_1m = calculate_average_hashrate(entries_within_1m)
        avg_5m = calculate_average_hashrate(entries_within_5m)
        avg_1h = calculate_average_hashrate(entries_within_1h)
        avg_24h = calculate_average_hashrate(entries_within_24h)
        avg_week = calculate_average_hashrate(entries_within_week)
        avg_month = calculate_average_hashrate(entries_within_month)
        avg_year = calculate_average_hashrate(entries_within_year)
        overall_avg = calculate_average_hashrate(entries_within_year)

        # Calculate average power for each timeframe (replace with actual power data)
        power_data = [entry.get('power', 0) for entry in entries_within_year]
        avg_power_1m = sum(power_data[-1:]) / len(power_data[-1:]) if power_data else 0
        avg_power_5m = sum(power_data[-5:]) / len(power_data[-5:]) if power_data else 0
        avg_power_1h = sum(power_data[-60:]) / len(power_data[-60:]) if power_data else 0
        avg_power_24h = sum(power_data[-1440:]) / len(power_data[-1440:]) if power_data else 0
        avg_power_week = sum(power_data[-10080:]) / len(power_data[-10080:]) if power_data else 0
        avg_power_month = sum(power_data[-43200:]) / len(power_data[-43200:]) if power_data else 0
        avg_power_year = sum(power_data) / len(power_data) if power_data else 0
        overall_avg_power = sum(power_data) / len(power_data) if power_data else 0

        # Calculate efficiency for each timeframe
        efficiency_1m = avg_power_1m / (avg_1m / 1000) if avg_1m != 0 else 0
        efficiency_5m = avg_power_5m / (avg_5m / 1000) if avg_5m != 0 else 0
        efficiency_1h = avg_power_1h / (avg_1h / 1000) if avg_1h != 0 else 0
        efficiency_24h = avg_power_24h / (avg_24h / 1000) if avg_24h != 0 else 0
        efficiency_week = avg_power_week / (avg_week / 1000) if avg_week != 0 else 0
        efficiency_month = avg_power_month / (avg_month / 1000) if avg_month != 0 else 0
        efficiency_year = avg_power_year / (avg_year / 1000) if avg_year != 0 else 0
        overall_efficiency = overall_avg_power / (overall_avg / 1000) if overall_avg != 0 else 0

        # Find the earliest timestamp in the data
        earliest_timestamp = min(entry['timestamp'] for entry in entries_within_year)

        # Calculate the total time in seconds
        total_seconds = (datetime.now() - parser.parse(earliest_timestamp)).total_seconds()

        # Calculate total days and remaining seconds
        total_days, remaining_seconds = divmod(total_seconds, 24 * 3600)

        # Calculate total hours and remaining seconds
        total_hours, _ = divmod(remaining_seconds, 3600)

        # Build a single string with different lines
        result_message = (
            f".\n"
            f'📊 Data covers a total of {int(total_days)} days and {int(total_hours)} hours. Gaps in data aren\'t included! Use !averageinfo for a better understanding.\n'
            f'**1️⃣ 1m Average:** {avg_1m} Gh/s (⚡ **Efficiency:** {efficiency_1m:.2f} W/Th)\n'
            f'**5️⃣ 5m Average:** {avg_5m} Gh/s (⚡ **Efficiency:** {efficiency_5m:.2f} W/Th)\n'
            f'**⏰ 1h Average:** {avg_1h} Gh/s (⚡ **Efficiency:** {efficiency_1h:.2f} W/Th)\n'
            f'**🌅 24h Average:** {avg_24h} Gh/s (⚡ **Efficiency:** {efficiency_24h:.2f} W/Th)\n'
            f'**📅 Weekly Average:** {avg_week} Gh/s (⚡ **Efficiency:** {efficiency_week:.2f} W/Th)\n'
            f'**🗓 Monthly Average:** {avg_month} Gh/s (⚡ **Efficiency:** {efficiency_month:.2f} W/Th)\n'
            f'**🕒 Yearly Average:** {avg_year} Gh/s (⚡ **Efficiency:** {efficiency_year:.2f} W/Th)\n'
            f'**🚀 Overall Average:** {overall_avg} Gh/s (⚡ **Efficiency:** {overall_efficiency:.2f} W/Th)'
        )

        # Send the single message with different lines
        await ctx.send(result_message)

    except FileNotFoundError:
        await ctx.send('Error: Database file not found.')
    except ValueError:
        await ctx.send('Error: Invalid date format in the database entries.')
    except Exception as e:
        await ctx.send(f'An unexpected error occurred: {str(e)}')

@bot.command()
async def hash(ctx):
    try:
        # Define the timeframe for each average
        timeframes = {'1m': 1, '5m': 5, '1h': 60, '24h': 1440, 'week': 10080, 'month': 43200, 'year': 525600}

        # Preliminary message indicating processing
        processing_message = "⏳ Calculating averages. This may take a moment. ⏳"
        await ctx.send(processing_message)

        # Accumulate results for each timeframe
        results = []

        # Add an empty first line
        results.append('**Hashrates**')

        for key, value in timeframes.items():
            # Retrieve entries within the specified timeframe
            entries_within_timeframe = get_entries_within_timeframe(file_path, datetime.now() - timedelta(minutes=int(value)))

            # Ensure the number of entries is exactly the specified value, filling in missing entries with zero hashrate
            if len(entries_within_timeframe) < value:
                # If there are missing entries, create zeroed entries to fill the gap
                missing_entries = [{'timestamp': (datetime.now() - timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M"), 'hashrate': 0, 'power': 0} for i in range(len(entries_within_timeframe), value)]
                entries_within_timeframe.extend(missing_entries)

            # Calculate average power for the current timeframe (replace with actual power data)
            power_data = [entry.get('power', 0) for entry in entries_within_timeframe]
            avg_power = sum(power_data) / max(len(power_data), 1)  # Use max to avoid division by zero

            # Calculate average hashrate for the current timeframe
            avg_hashrate = calculate_av_hashrate(entries_within_timeframe)

            # Calculate efficiency for the current timeframe
            efficiency = avg_power / (avg_hashrate / 1000) if avg_hashrate != 0 else 0

            # Count the total number of entries within the timeframe
            total_entries = len(entries_within_timeframe)

            # Count the number of non-zero hashrate entries
            non_zero_entries = sum(1 for entry in entries_within_timeframe if entry.get('hashRate', 0) > 0)

            # Calculate the percentage of non-zero hashrate entries
            percentage_used = (non_zero_entries / total_entries) * 100 if total_entries > 0 else 0

            # Determine color based on the percentage range
            if percentage_used >= 95:
                color = ":green_square:"
            elif percentage_used >= 75:
                color = ":orange_square:"
            else:
                color = ":red_square:"

            # Accumulate the results with emojis and entry counts
            results.append(f'**{key.capitalize()} Average:** {round(avg_hashrate, 2)} Gh/s (⚡ **Efficiency:** {round(efficiency, 2)} W/Th) | 📊 **Data available:** ({color} {round(percentage_used, 2)}%)')

        # Send the accumulated results as a single message with emojis
        await ctx.send('\n'.join(results))

    except FileNotFoundError:
        await ctx.send('Error: Database file not found.')
    except ValueError:
        await ctx.send('Error: Invalid date format in the database entries.')
    except Exception as e:
        await ctx.send(f'An unexpected error occurred: {str(e)}')

# Command to generate and display a plot of hashrate over time with user-specified timeframe and smoothing
@bot.command()
async def plot(ctx, days=None, smoothing=None):
    if days is None or smoothing is None:
        await ctx.send('Please provide both days and smoothing parameters. Example: `!plot 7d 2h`')
        return

    logo_url = 'https://github.com/Jaakuice/BitaxeDiscord/blob/main/images/logo.png?raw=true'
    logo_path = '**ENTER YOUR FILE PATH TO LOGO**/logo.png'

    # Download the logo image if it doesn't exist locally
    if not os.path.isfile(logo_path):
        urllib.request.urlretrieve(logo_url, logo_path)

    # Set dark mode style
    plt.style.use('dark_background')

    # Convert time variables to timedelta
    try:
        days = int(days[:-1])
        if smoothing.endswith("m"):
            smoothing_minutes = int(smoothing[:-1])
            smoothing_label = f'{smoothing_minutes} minute{"s" if smoothing_minutes > 1 else ""}'
        elif smoothing.endswith("h"):
            smoothing_minutes = int(smoothing[:-1]) * 60
            smoothing_label = f'{int(smoothing[:-1])} hour{"s" if int(smoothing[:-1]) > 1 else ""}'
        else:
            raise ValueError("Invalid smoothing format. Please use 'm' for minutes or 'h' for hours.")
    except ValueError:
        await ctx.send('Invalid timeframe or smoothing format. Example: `!plot 7d 2h`')
        return

    # Retrieve entries within the specified timeframe
    start_date = datetime.now() - timedelta(days=days)
    # Assuming get_entries_within_timeframe and file_path are defined elsewhere
    entries = get_entries_within_timeframe(file_path, start_date)

    if not entries:
        await ctx.send(f'No entries found within the last {days} days.')
        return

    # Extract timestamps and hashrate values
    timestamps = [entry['timestamp'] for entry in entries]
    hashrates = [entry['hashRate'] for entry in entries]

    # Calculate the moving average with a user-specified window size
    window_size = smoothing_minutes
    smoothed_hashrates = np.convolve(hashrates, np.ones(window_size)/window_size, mode='valid')

    fig, ax = plt.subplots()

    # Find the index of the maximum and minimum values in the smoothed hashrates
    max_index = np.argmax(smoothed_hashrates)
    min_index = np.argmin(smoothed_hashrates)

    # Plot the raw hashrate line
    ax.plot(timestamps, hashrates, label='Raw Hash', linestyle='-', color='blue')

    # Plot the smoothed hashrate line with only highest and lowest labels
    ax.plot(timestamps[window_size - 1:], smoothed_hashrates, label=f'{smoothing_label} Hash', linestyle='-', color='orange')
    ax.annotate(f'{smoothed_hashrates[max_index]:.2f}', (timestamps[window_size-1:][max_index], smoothed_hashrates[max_index]),
                textcoords="offset points", xytext=(0, 10), ha='center', fontsize=8, color='white')
    ax.annotate(f'{smoothed_hashrates[min_index]:.2f}', (timestamps[window_size-1:][min_index], smoothed_hashrates[min_index]),
                textcoords="offset points", xytext=(0, 10), ha='center', fontsize=8, color='white')

    ax.set_title(f'Hashrate Over the Last {days} Days with {smoothing_label} Smoothing')
    ax.set_xlabel('Timestamp')
    ax.set_ylabel('Hashrate')
    ax.tick_params(axis='x', rotation=45)
    # Set xticks to display only 6 timestamps
    xticks = np.linspace(0, len(timestamps)-1, 6, dtype=int)
    ax.set_xticks(xticks)
    ax.set_xticklabels([timestamps[i] for i in xticks], rotation=45)

    ax.grid(axis='y', linestyle='--', alpha=0.7)

    ax.legend()
    
    # Add the logo to the plot
    logo_image = plt.imread(logo_path)
    imagebox = OffsetImage(logo_image, zoom=0.2, resample=True, alpha=0.5)
    ab = AnnotationBbox(imagebox, (0.09, 0.15), frameon=False, xycoords='axes fraction', boxcoords="axes fraction")
    ax.add_artist(ab)

    plt.tight_layout()

    # Save the plot as an image file
    plot_filename = 'hashrate_plot.png'
    plt.savefig(plot_filename)

    # Send the plot image to the Discord channel
    with open(plot_filename, 'rb') as file:
        await ctx.send(file=discord.File(file, 'hashrate_plot.png'))

    # Remove the temporary plot image file
    os.remove(plot_filename)
    os.remove(logo_path)

@bot.command(name='about')
async def about(ctx):
    # Your about message
    about_message = "I'm just an average pleb interested in bitcoin. Feel free to donate! 🌟🌐"

    # Image URL
    image_url = "https://github.com/Jaakuice/BitaxeDiscord/blob/main/images/ln.png?raw=true"

    # Send the text message
    await ctx.send(about_message)

    # Send the image separately
    await ctx.send(image_url)

async def start_bot():
    await bot.start(TOKEN)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        file_monitor.stop()  # Stop the file monitoring loop
        loop.run_until_complete(bot.logout())
    finally:
        loop.close()