[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

# HACS-husqvarna_automower_ble - Custom integration for Husqvarna Bluetooth automowers

This is a **fork** of the official [Home Assistant Husqvarna Automower BLE integration](https://www.home-assistant.io/integrations/husqvarna_automower_ble/).

It extends the functionality of the original integration and adds some new features.

It is based on the BLE implementation available at [HusqvarnaAutoMower-BLE](https://github.com/Marbanz/HusqvarnaAutoMower-BLE).

---

## Features

- **Control your mower**: Start mowing, pause, dock, or park indefinitely.
- **Monitor mower status**: Battery level, charging status, mower state, activity, and errors.
- **Track mower statistics**: Total runtime, cutting time, charging time, and more.
- **Custom services**: Use Home Assistant services to control additional functions.

---

## Installation

### Using Marketplace

1. Add this repository to the Marketplace as a custom repository:
   - Go to **Settings > Marketplace**.
   - Click the three dots in the top-right corner and select **Custom Repositories**.
   - Paste the repository URL:  
     `https://github.com/Marbanz/HACS-husqvarna_automower_ble`
   - Choose **Integration** as the category and click **Add**.
2. Search for **Husqvarna Automower BLE** in the list and install the integration.
3. Restart Home Assistant to load the integration.

---

## Configuration

### Automatic Discovery

1. Your mower may be automatically discovered.
2. Go to **Settings > Integrations** and look for the **Husqvarna Automower BLE** integration.
3. Click **Configure** and follow the prompts to set up the mower.
4. Before submitting, put your mower in pairing mode

### Manual Configuration

1. If the mower is not discovered automatically, you can add it manually:
   - Go to **Settings > Integrations**.
   - Click **Add Integration** and search for **Husqvarna Automower BLE**.
2. Enter the mower's **MAC address** and **PIN**:
   - **MAC Address**: If not autodiscovered, retrieve it from the official app or mower settings.
   - **PIN**: See the **PIN Codes** section below for details.
3. Before submitting:
   - Power off your mower.
   - Power it back on to enable Bluetooth pairing mode (active for ~2 minutes).
4. Click **Submit** to complete the setup.

---

## PIN Codes

Some mowers, such as Gardena and other brands that use Husqvarna internal boards, require a PIN to be controlled with Bluetooth. This PIN is the same one you enter using the mower's buttons, which correspond to digits as follows:

- **On/Off Power button** = `1`
- **Go/Schedule button** = `2`
- **Go button** = `3`
- **Park button** = `4`

Refer to your mower's operator manual for the default PIN (`1234`).

![image](https://github.com/user-attachments/assets/10c75863-a634-4686-bc4c-15bb128dcad9)

---

## Usage

### Controlling the Mower

Once the integration is set up, an automower entity is created in Home Assistant. You can:

- Start mowing
- Pause mowing
- Dock the mower

These actions can be performed via the Home Assistant UI.

### Additional Sensors

The integration creates several sensors to monitor the mower's status and performance:

- **Battery Level**: Displays the current battery percentage.
- **Charging Status**: Indicates whether the mower is charging.
- **Mode**: Shows the current operating mode of the mower.
- **State**: Displays the mower's current state.
- **Activity**: Indicates the mower's activity.
- **Error Code**: Provides error details if the mower encounters an issue.
- **Next Start Time**: Displays the next scheduled mowing time.
- **Statistics**: Tracks total runtime, cutting time, charging time, and more.

### Custom Services

The integration provides additional custom services to enhance control over your mower:

- **Park indefinitely**: This service allows you to park the mower at its docking station without resuming its schedule until manually instructed.
- **Resume schedule**: Use this service to resume the mower's predefined schedule after it has been paused or parked.

These services can be accessed via **Actions** in the Home Assistant UI or can be used in **automations** for advanced control.

---

## Troubleshooting

### Bluetooth Pairing Issues

- Ensure the mower is powered on and in Bluetooth pairing mode (active for ~2 minutes after powering on).
- If pairing fails, try restarting the mower and repeating the setup process.
- Move closer to the mower to ensure a strong Bluetooth signal.
- If you are using an ESPHome Bluetooth Proxy and pairing fails, try resetting the proxy before retrying.
