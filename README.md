# Bitaxe Discord Bot

This Discord bot monitors and reports various metrics related to a Bitaxe API.

## Features

- **Latest Entry**: Displays the latest entry from the data file.
- **File Size**: Shows the current size of the data file and performs pruning if necessary.
- **Set Size**: Allows users to set the maximum file size and pruning threshold.
- **Set Voltage, Temperature, Fan Thresholds**: Users can set custom thresholds for voltage, temperature, and fan speed.
- **Best Difficulty**: Displays the current Best Difficulty Value.
- **Average Hashrates**: Calculates and displays average hashrates over various timeframes.
- **Total Hashrate**: Displays the total hashrate based on available data.
- **Plot Generation**: Generates and displays a plot of hashrate over time with user-specified timeframe and smoothing.
- **Alerts**: Notifies users about changes in Best Difficulty, low core voltage, high temperature, low fan speed, and rejected shares.

## Commands

- `!latest`: Display the latest entry.
- `!file_size`: Show the current size of the data file and perform pruning if necessary.
- `!set_size [new_max_size] [new_prune_threshold]`: Set the maximum file size and pruning threshold.
- `!set_volt [threshold]`: Set the user-defined voltage threshold.
- `!set_temp [threshold]`: Set the user-defined temperature threshold.
- `!set_fan [threshold]`: Set the user-defined fan speed threshold.
- `!best`: Show the current Best Difficulty Value.
- `!average`: Calculate and display average hashrates over various timeframes.
- `!hash`: Display the total hashrate based on available data.
- `!plot [days] [smoothing]`: Generate and display a plot of hashrate over time.

## Alerts

- Notify of New Best Difficulty
- "coreVoltageActual" Alert
- "temp" Alert
- "fanSpeed" Alert
- Notify of Rejected Shares

## Usage

1. Clone the repository: `git clone https://github.com/your-username/bitaxe-discord-bot.git`
2. Install dependencies: `pip install -r requirements.txt`
3. Configure the bot token in `config.ini`.
4. Run the bot: `python bot.py`

## Configuration

- Bot token and other settings can be configured in `config.ini`.

## Contributing

Contributions are welcome! If you have suggestions, improvements, or bug fixes, feel free to open an issue or submit a pull request.

## License

This project is licensed under the [MIT License](LICENSE).
