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

# Argumentparser für CLI-Eingaben
parser = argparse.ArgumentParser(description="Worker to process pixels from master.")
parser.add_argument("--master_host", type=str, default=MASTER_HOST, help="Master server host address.")
parser.add_argument("--master_port", type=int, default=MASTER_PORT, help="Master server port.")
args = parser.parse_args()

# Set a pixel on the canvas
def set_pixel(x, y, color):
    params = {'x': x, 'y': y, 'color': color}
    response = requests.put(f"{BASE_URL}{SET_ENDPOINT}", params=params, headers={'accept': 'application/json'})
    return response.status_code == 201

# Connect to the Master and request work packets
def connect_to_master():
    delay = 1 / 5  # Fester PPS-Delay

    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((args.master_host, args.master_port))
                print("Connected to master, requesting work...")

                while True:
                    # Empfange Daten und verarbeite JSON mit Fehlerbehandlung
                    data = ""
                    while True:
                        chunk = s.recv(1024).decode("utf-8")
                        if not chunk:
                            break
                        data += chunk
                        if len(chunk) < 1024:
                            break

                    if not data:
                        print("No data received, disconnecting...")
                        break

                    try:
                        work_packet = json.loads(data)
                    except json.JSONDecodeError:
                        print("JSON decode error, requesting packet again...")
                        continue

                    print(f"Received work packet with {len(work_packet)} pixels.")

                    # Verarbeite jedes Pixel im Arbeitspaket
                    for x, y, color in work_packet:
                        if not set_pixel(x, y, color):
                            print(f"Failed to set pixel at ({x}, {y}) with color {color}")
                        time.sleep(delay)

                    # Sende ACK-Nachricht an den Master
                    s.sendall("acknowledge".encode("utf-8"))
                    print("Work packet completed and acknowledged to master.")

            except ConnectionRefusedError:
                print("Master not available, retrying in 5 seconds...")
                time.sleep(5)

# Run the worker
connect_to_master()
