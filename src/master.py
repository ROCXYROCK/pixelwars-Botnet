import socket
import threading
import json
import random
import os
from PIL import Image
from queue import Queue
import toml
import argparse

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

# Lade das Bild und erstelle Arbeitspakete basierend auf festem PPS-Wert
def load_image_to_work_queue(image_path):
    image = Image.open(image_path).convert('RGB')
    img_width, img_height = image.size

    # Berechne eine zufällige Startposition
    start_x = random.randint(0, CANVAS_WIDTH - img_width)
    start_y = random.randint(0, CANVAS_HEIGHT - img_height)
    print(f"Starting position on canvas: (x={start_x}, y={start_y})")

    # Paketgröße berechnen basierend auf festem PPS-Wert
    packet_size = int(40 * PPS)
    print(f"Packet size calculated based on fixed PPS: {packet_size}")

    # Erstelle Pixel-Daten mit angepassten Koordinaten
    pixels = []
    for y in range(img_height):
        for x in range(img_width):
            r, g, b = image.getpixel((x, y))
            color = f'{r:02x}{g:02x}{b:02x}'
            pixels.append((start_x + x, start_y + y, color))

    # Teile Pixel in Pakete der Größe `packet_size`
    work_packets = [pixels[i:i + packet_size] for i in range(0, len(pixels), packet_size)]
    for packet in work_packets:
        work_queue.put(packet)

    print(f"Loaded {len(pixels)} pixels into {work_queue.qsize()} work packets.")

# Arbeiterverbindungen bearbeiten
def handle_worker(conn, addr):
    print(f"Worker connected from {addr}")

    while not work_queue.empty():
        try:
            # Hole das nächste Arbeitspaket
            work_packet = work_queue.get_nowait()

            # Sende das Arbeitspaket an den Worker
            conn.sendall(json.dumps(work_packet).encode())
            print(f"Sent work packet to {addr}")

            # Warte auf das 'ack' Signal vom Worker
            ack = conn.recv(1024).decode()
            if ack != "ack":
                print(f"Did not receive acknowledgment from {addr}, re-sending packet.")
                work_queue.put(work_packet)  # Packet back to queue
                continue

            # Warte auf die 'done' Nachricht des Workers
            response = conn.recv(1024).decode()
            if response == "done":
                print(f"Worker {addr} finished a packet.")
                work_queue.task_done()
            else:
                print(f"Unexpected response from {addr}: {response}")
                work_queue.put(work_packet)  # Packet back to queue if error occurs

            if work_queue.empty():
                print(f"No more work packets for {addr}")
                break

        except Exception as e:
            print(f"Error handling worker {addr}: {e}")
            work_queue.put(work_packet)  # Packet back to queue on exception
            continue

    conn.close()
    print(f"Worker {addr} disconnected")

# Starte den Master-Server
def start_master(image_path):
    # Initialisiere Arbeitspakete für das angegebene Bild
    load_image_to_work_queue(image_path)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((SRC_HOST, SRC_PORT))
    server.listen(5)
    print(f"Master server listening on {SRC_HOST}:{SRC_PORT}")

    # Akzeptiere Worker-Verbindungen
    while not work_queue.empty():
        conn, addr = server.accept()
        worker_thread = threading.Thread(target=handle_worker, args=(conn, addr))
        worker_thread.start()

    server.close()
    print("All work packets processed.")

# Starte den Master mit dem übergebenen Bildpfad
start_master(args.image_path)
