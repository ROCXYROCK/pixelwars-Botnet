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
PROGRESS_FILE = config["Files"]["progress"]

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

# Speichere den Fortschritt in einer Datei
def save_progress(last_pixel_index, start_x, start_y):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({
            'last_pixel_index': last_pixel_index,
            'start_x': start_x,
            'start_y': start_y
        }, f)
    print(f"Progress saved with last pixel index: {last_pixel_index} and starting coordinates: ({start_x}, {start_y})")

# Lade den Fortschritt aus der Datei, falls vorhanden
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            progress = json.load(f)
        last_pixel_index = progress.get('last_pixel_index', 0)
        start_x = progress.get('start_x', 0)
        start_y = progress.get('start_y', 0)
        print(f"Progress loaded with last pixel index: {last_pixel_index} and starting coordinates: ({start_x}, {start_y})")
        return last_pixel_index, start_x, start_y
    return 0, 0, 0

# Lade das Bild und erstelle Arbeitspakete mit einem festen PPS, ausgehend vom gespeicherten Fortschritt
def load_image_to_work_queue(image_path, start_index=0, start_x=0, start_y=0):
    image = Image.open(image_path).convert('RGB')
    img_width, img_height = image.size

    # Berechne eine zufällige Startposition, falls keine Fortsetzung notwendig ist
    if start_x == 0 and start_y == 0:
        start_x = random.randint(0, CANVAS_WIDTH - img_width)
        start_y = random.randint(0, CANVAS_HEIGHT - img_height)
        save_progress(0, start_x, start_y)
    print(f"Starting position on canvas: (x={start_x}, y={start_y})")

    # Paketgröße berechnen basierend auf festem PPS-Wert
    packet_size = int(40 * PPS)
    print(f"Packet size calculated based on fixed PPS: {packet_size}")

    # Erstelle Pixel-Daten mit angepassten Koordinaten, ab dem letzten gespeicherten Fortschritt
    pixels = []
    for y in range(img_height):
        for x in range(img_width):
            r, g, b = image.getpixel((x, y))
            if (r, g, b) != (0, 0, 0):  # Ignoriere schwarze Pixel
                color = f'{r:02x}{g:02x}{b:02x}'
                pixels.append((start_x + x, start_y + y, color))

    # Nur Pixel ab `start_index` einschließen
    pixels = pixels[start_index:]

    # Teile Pixel in Pakete der Größe `packet_size`
    work_packets = [pixels[i:i + packet_size] for i in range(0, len(pixels), packet_size)]
    for packet in work_packets:
        work_queue.put(packet)

    print(f"Loaded {len(pixels)} pixels into {work_queue.qsize()} work packets, starting from index {start_index}.")

# Arbeiterverbindungen bearbeiten
def handle_worker(conn, addr, start_index=0, start_x=0, start_y=0):
    print(f"Worker connected from {addr}")
    pixel_index = start_index

    while not work_queue.empty():
        try:
            # Hole das nächste Arbeitspaket
            work_packet = work_queue.get_nowait()

            # Speichere den Fortschritt sofort nach dem Senden des Pakets
            pixel_index += len(work_packet)
            save_progress(pixel_index, start_x, start_y)

            # Sende das Arbeitspaket an den Worker
            conn.sendall(json.dumps(work_packet).encode())  
            print(f"Sent work packet to {addr}")

            # Warte auf die Fertigmeldung des Workers
            response = conn.recv(1024).decode()
            if response == "done":
                print(f"Worker {addr} finished a packet.")
                work_queue.task_done()
            else:
                print(f"Unexpected response from {addr}: {response}")

            if work_queue.empty():
                print(f"No more work packets for {addr}")
                if os.path.exists(PROGRESS_FILE):
                    os.remove(PROGRESS_FILE)  # Fortschrittsdatei nach Abschluss löschen
                break

        except Exception as e:
            print(f"Error handling worker {addr}: {e}")
            break

    conn.close()
    print(f"Worker {addr} disconnected")

# Starte den Master-Server und lade gespeicherten Fortschritt, falls vorhanden
def start_master(image_path):
    last_pixel_index, start_x, start_y = load_progress()
    
    # Initialisiere Arbeitspakete ab dem letzten gespeicherten Pixelindex und den Koordinaten
    load_image_to_work_queue(image_path, start_index=last_pixel_index, start_x=start_x, start_y=start_y)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((SRC_HOST, SRC_PORT))
    server.listen(5)
    print(f"Master server listening on {SRC_HOST}:{SRC_PORT}")

    # Akzeptiere Worker-Verbindungen
    while not work_queue.empty():
        conn, addr = server.accept()
        worker_thread = threading.Thread(target=handle_worker, args=(conn, addr, last_pixel_index, start_x, start_y))
        worker_thread.start()

    server.close()
    print("All work packets processed.")

# Starte den Master mit dem übergebenen Bildpfad
start_master(args.image_path)
