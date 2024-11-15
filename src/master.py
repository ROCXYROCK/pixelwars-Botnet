import socket
import threading
import json
import random
from queue import Queue
import toml
from icecream import ic
from datetime import datetime
from PIL import Image
import sys

# Icecream mit Zeitstempel konfigurieren
ic.configureOutput(prefix=lambda: f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | ")

# Konfigurationseinstellungen
SRC_HOST = "0.0.0.0"
SRC_PORT = 5555

# Statische Werte für Canvas-Größe und PPS
CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080
PPS = 5

# Queue für Arbeitspakete
work_queue = Queue()

# Validierungsfunktion für Farben im Hex-Format
def format_color(r, g, b):
    """Format RGB values as a hex string in 'rrggbb' format."""
    return f'{r:02x}{g:02x}{b:02x}'

# Generiere Pixel aus einem Bild
def generate_pixels_from_image(image_path, packet_size):
    """
    Loads an image and generates pixels based on its RGB values.
    """
    try:
        image = Image.open(image_path)
        image = image.resize((CANVAS_WIDTH, CANVAS_HEIGHT))  # Passe die Bildgröße an das Canvas an
        pixels = []
        for y in range(image.height):
            for x in range(image.width):
                r, g, b = image.getpixel((x, y))[:3]
                color = format_color(r, g, b)
                pixels.append((x, y, color))
        
        # Teile die Pixel in Pakete auf
        work_packets = [pixels[i:i + packet_size] for i in range(0, len(pixels), packet_size)]
        for packet in work_packets:
            work_queue.put(packet)

        ic(f"Generated {len(pixels)} pixels from image into {work_queue.qsize()} packets.")
    except Exception as e:
        ic(f"Failed to process image {image_path}: {e}")

# Arbeiterverbindungen bearbeiten
def handle_worker(conn, addr):
    ic(f"Worker connected from {addr}")

    while not work_queue.empty():
        try:
            work_packet = work_queue.get_nowait()
            conn.sendall(json.dumps(work_packet).encode())
            ic(f"Sent work packet to {addr}")

            ack = conn.recv(1024).decode()
            if ack != "ack":
                ic(f"Did not receive acknowledgment from {addr}, re-sending packet.")
                work_queue.put(work_packet)
                continue

            response = conn.recv(1024).decode()
            if response == "done":
                ic(f"Worker {addr} finished a packet.")
                work_queue.task_done()
            else:
                ic(f"Unexpected response from {addr}: {response}")
                work_queue.put(work_packet)

            if work_queue.empty():
                ic(f"No more work packets for {addr}")
                break

        except Exception as e:
            ic(f"Error handling worker {addr}: {e}")
            work_queue.put(work_packet)
            break

    conn.close()
    ic(f"Worker {addr} disconnected")

# Starte den Master-Server
def start_master(image_path):
    packet_size = int(40 * PPS)

    if image_path:
        ic(f"Processing image: {image_path}")
        generate_pixels_from_image(image_path, packet_size)
    else:
        ic("No image provided. Exiting.")
        return

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((SRC_HOST, SRC_PORT))
    server.listen(5)
    ic(f"Master server listening on {SRC_HOST}:{SRC_PORT}")

    while not work_queue.empty():
        conn, addr = server.accept()
        worker_thread = threading.Thread(target=handle_worker, args=(conn, addr))
        worker_thread.start()

    server.close()
    ic("All work packets processed.")

# Prüfe, ob der Bildpfad übergeben wurde
if len(sys.argv) != 2:
    print("Usage: python3 master_server.py path/to/image.png")
    sys.exit(1)

image_path = sys.argv[1]

# Starte den Master
start_master(image_path)
