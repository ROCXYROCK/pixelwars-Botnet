import socket
import json
import requests
import time
import toml
import argparse

# Lade Konfiguration aus config.toml
config = toml.load("cfg/config.toml")

# Konfigurationseinstellungen aus der TOML-Datei
DIST_HOST = config["Dist"]["HOST"]
DIST_PORT = config["Dist"]["PORT"]
PPS_ENDPOINT = config["Dist"]["pps"]
SET_ENDPOINT = config["Dist"]["set"]
MASTER_HOST = config["Src"]["HOST"]
MASTER_PORT = config["Src"]["PORT"]

# API base URL
BASE_URL = f"{DIST_HOST}{DIST_PORT}" if DIST_PORT else DIST_HOST

# Argumentparser für CLI-Eingaben, um Master-Adresse und -Port zu überschreiben
parser = argparse.ArgumentParser(description="Worker to process pixels from master.")
parser.add_argument("--master_host", type=str, default=MASTER_HOST, help="Master server host address.")
parser.add_argument("--master_port", type=int, default=MASTER_PORT, help="Master server port.")
args = parser.parse_args()

# Set a pixel on the canvas with retry handling for connectivity issues
def set_pixel(x, y, color, retries=3):
    params = {'x': x, 'y': y, 'color': color}
    for attempt in range(retries):
        response = requests.put(f"{BASE_URL}{SET_ENDPOINT}", params=params, headers={'accept': 'application/json'})
        if response.status_code == 201:
            return True
        else:
            print(f"Failed to set pixel at ({x}, {y}) with color {color}. Attempt {attempt + 1} of {retries}. Status code: {response.status_code}")
            time.sleep(0.5)  # Short delay before retry
    return False  # Skip pixel after retries

# Get the current pixels per second (PPS) rate limit
def get_pps():
    try:
        response = requests.get(f"{BASE_URL}{PPS_ENDPOINT}", headers={'accept': 'application/json'})
        if response.status_code == 200:
            pps = float(response.json())
            print(f"PPS rate limit obtained: {pps}")
            return pps
        else:
            print(f"Failed to get PPS rate limit. Status code: {response.status_code}")
            return 1  # Default PPS if request fails
    except Exception as e:
        print(f"Error obtaining PPS: {e}")
        return 1

# Connect to the Master and request work packets
# Connect to the Master and request work packets
# Custom exception to break out of all loops
class ReconnectException(Exception):
    pass

# Connect to the Master and request work packets
def connect_to_master():
    # Initial PPS and delay
    pps = get_pps()
    delay = 1 / pps if pps > 0 else 1
    last_check = time.time()

    while True:  # Outer loop for reconnecting
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((args.master_host, args.master_port))
                print("Connected to master, requesting work...")

                while True:  # Middle loop for receiving data packets
                    # Check every 10 seconds to update PPS and delay
                    if time.time() - last_check >= 10:
                        pps = get_pps()
                        delay = 1 / pps if pps > 0 else 1
                        last_check = time.time()
                        print(f"Updated delay to {delay:.3f} seconds based on new PPS.")

                    # Receive data in chunks and assemble it
                    data = ""
                    while True:  # Inner loop for assembling the data
                        chunk = s.recv(1024).decode()
                        if not chunk:
                            break
                        data += chunk
                        if len(chunk) < 1024:  # Break if no more data is expected
                            break

                    if not data:
                        print("No data received, disconnecting...")
                        raise ReconnectException  # Force reconnect

                    try:
                        print(f"Data: {data}")
                        work_packet = json.loads(data)
                        print(f"Received work packet with {len(work_packet)} pixels.")
                        print(work_packet)
                    except json.JSONDecodeError:
                        print("Received invalid JSON data. Disconnecting and reconnecting...")
                        raise ReconnectException  # Force reconnect

                    # Send acknowledgment for received packet
                    s.sendall("ack".encode())
                    print("Acknowledged receipt of work packet.")

                    # Process each pixel in the work packet
                    for x, y, color in work_packet:
                        if not set_pixel(x, y, color):
                            print(f"Skipping pixel at ({x}, {y}) due to repeated errors.")
                        time.sleep(delay)  # Wait according to the current delay

                    # Notify master that this packet is complete
                    s.sendall("done".encode())
                    print("Work packet completed and reported to master.")

        except ReconnectException:
            print("Reconnecting to master due to an error...")
            time.sleep(5)
        except ConnectionRefusedError:
            print("Master not available, retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print(f"Unexpected error: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)



# Run the worker
connect_to_master()
