import socket
import threading
import json
import random
import os
from PIL import Image
from queue import Queue
import toml
import argparse
from icecream import ic
from datetime import datetime

# Icecream mit Zeitstempel konfigurieren
ic.configureOutput(prefix=lambda: f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | ")

# Lade Konfiguration aus config.toml
config = toml.load("cfg/config.toml")

# Konfigurationseinstellungen aus der TOML-Datei
SRC_HOST = "0.0.0.0"
SRC_PORT = config["Src"]["PORT"]
FILES_DIR = config["Files"]["dir"]

# Statische Werte für Canvas-Größe und PPS
CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080
PPS = 5

# Queue für Arbeitspakete
work_queue = Queue()

# Argumentparser für CLI-Eingaben
parser = argparse.ArgumentParser(description="Image processing master server.")
parser.add_argument("image_path", type=str, help="Path to the image file to process.")
args = parser.parse_args()

# Validierungsfunktion für Farben im Hex-Format mit zufälliger Farbe bei ungültigen Werten
def format_color(r, g, b):
    """Format RGB values as a hex string in 'rrggbb' format or return a random color if invalid."""
    if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
        return f'{r:02x}{g:02x}{b:02x}'
    else:
        # Generiere eine zufällige Farbe im Hex-Format
        random_color = f'{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}'
        ic(f"Invalid color values detected: ({r}, {g}, {b}). Using random color '{random_color}'.")
        return random_color

# Lade das Bild und erstelle Arbeitspakete für Progressive Rendering
def load_image_to_work_queue(image_path):
    image = Image.open(image_path).convert('RGB')
    img_width, img_height = image.size

    # Berechne eine zufällige Startposition
    start_x = random.randint(0, CANVAS_WIDTH - img_width)
    start_y = random.randint(0, CANVAS_HEIGHT - img_height)
    ic(f"Starting position on canvas: (x={start_x}, y={start_y})")

    # Paketgröße berechnen basierend auf festem PPS-Wert
    packet_size = int(40 * PPS)
    ic(f"Packet size calculated based on fixed PPS: {packet_size}")

    # Progressive Rendering in mehreren Schritten
    for step in range(5, 0, -1):  # Schrittweite reduzieren: 3, 2, 1
        pixels = []
        for y in range(0, img_height, step):  # Schrittweise Abstände
            for x in range(0, img_width, step):
                r, g, b = image.getpixel((x, y))
                color = format_color(r, g, b)
                pixels.append((start_x + x, start_y + y, color))

        # Teile Pixel in Pakete der Größe `packet_size`
        work_packets = [pixels[i:i + packet_size] for i in range(0, len(pixels), packet_size)]
        for packet in work_packets:
            work_queue.put(packet)

        ic(f"Loaded {len(pixels)} pixels into {work_queue.qsize()} work packets for step {step}.")

# Arbeiterverbindungen bearbeiten
def handle_worker(conn, addr):
    ic(f"Worker connected from {addr}")

    while not work_queue.empty():
        try:
            # Hole das nächste Arbeitspaket
            work_packet = work_queue.get_nowait()

            # Sende das Arbeitspaket an den Worker
            conn.sendall(json.dumps(work_packet).encode())
            ic(f"Sent work packet to {addr}")

            # Warte auf das 'ack' Signal vom Worker
            ack = conn.recv(1024).decode()
            if ack != "ack":
                ic(f"Did not receive acknowledgment from {addr}, re-sending packet.")
                work_queue.put(work_packet)  # Packet back to queue
                continue

            # Warte auf die 'done' Nachricht des Workers
            response = conn.recv(1024).decode()
            if response == "done":
                ic(f"Worker {addr} finished a packet.")
                work_queue.task_done()
            else:
                ic(f"Unexpected response from {addr}: {response}")
                work_queue.put(work_packet)  # Packet back to queue if error occurs

            if work_queue.empty():
                ic(f"No more work packets for {addr}")
                break

        except Exception as e:
            ic(f"Error handling worker {addr}: {e}")
            work_queue.put(work_packet)  # Packet back to queue on exception
            break

    conn.close()
    ic(f"Worker {addr} disconnected")

# Starte den Master-Server
def start_master(image_path):
    # Initialisiere Arbeitspakete für das angegebene Bild
    load_image_to_work_queue(image_path)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((SRC_HOST, SRC_PORT))
    server.listen(5)
    ic(f"Master server listening on {SRC_HOST}:{SRC_PORT}")

    # Akzeptiere Worker-Verbindungen
    while not work_queue.empty():
        conn, addr = server.accept()
        worker_thread = threading.Thread(target=handle_worker, args=(conn, addr))
        worker_thread.start()

    server.close()
    ic("All work packets processed.")

# Starte den Master mit dem übergebenen Bildpfad
start_master(args.image_path)
