import socket
import threading
import json
import random
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

# Statische Werte für Canvas-Größe und PPS
CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080
PPS = 5

# Queue für Arbeitspakete
work_queue = Queue()

# Argumentparser für CLI-Eingaben
parser = argparse.ArgumentParser(description="Pixel pattern master server.")
parser.add_argument("--image_path", type=str, default=None, help="Path to the image file to process (optional).")
parser.add_argument("--pattern", type=str, default="random", help="Pixel pattern to generate (stripes, checkerboard, random).")
args = parser.parse_args()

# Validierungsfunktion für Farben im Hex-Format
def format_color(r, g, b):
    """Format RGB values as a hex string in 'rrggbb' format."""
    return f'{r:02x}{g:02x}{b:02x}'

# Generiere zufällige Pixel
def generate_random_pixels(canvas_width, canvas_height, packet_size):
    
    """
    Generates a traceable pattern across the canvas, such as a spiral or zig-zag path.
    """
    pixels = []
    x, y = canvas_width // 2, canvas_height // 2  # Start in der Mitte des Canvas
    direction = 0  # 0: rechts, 1: runter, 2: links, 3: hoch
    steps = 1      # Anzahl der Schritte pro Richtung
    step_change = 0  # Kontrolliert, wann die Schrittweite erhöht wird

    for _ in range(canvas_width * canvas_height):
        # Füge den aktuellen Punkt hinzu
        color = format_color(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        pixels.append((x, y, color))

        # Bewege in die aktuelle Richtung
        if direction == 0:  # Rechts
            x += 1
        elif direction == 1:  # Runter
            y += 1
        elif direction == 2:  # Links
            x -= 1
        elif direction == 3:  # Hoch
            y -= 1

        # Reduzierte Schritte für diese Richtung
        steps -= 1
        if steps == 0:  # Richtung wechseln, wenn Schritte aufgebraucht sind
            direction = (direction + 1) % 4
            step_change += 1
            if step_change % 2 == 0:  # Schrittweite alle zwei Richtungswechsel erhöhen
                steps = (step_change // 2) + 1
            else:
                steps = step_change // 2

        # Begrenze die Position innerhalb des Canvas
        x = max(0, min(canvas_width - 1, x))
        y = max(0, min(canvas_height - 1, y))

    # Teile die Pixel in Pakete auf
    work_packets = [pixels[i:i + packet_size] for i in range(0, len(pixels), packet_size)]
    for packet in work_packets:
        work_queue.put(packet)

    ic(f"Generated {len(pixels)} traceable pattern pixels into {work_queue.qsize()} packets.")


# Generiere Pixelmuster und lade sie in die Work Queue
def generate_pixel_pattern(pattern_type, canvas_width, canvas_height, packet_size, step=1):
    """Generates pixel patterns and loads them into the work queue."""
    pixels = []

    if pattern_type == "stripes":
        for x in range(0, canvas_width, step * 10):
            for y in range(0, canvas_height, step):
                color = format_color(255, 0, 0) if (x // 10) % 2 == 0 else format_color(0, 255, 0)  # Alternating red/green
                pixels.append((x, y, color))

    elif pattern_type == "checkerboard":
        for y in range(0, canvas_height, step * 10):
            for x in range(0, canvas_width, step * 10):
                color = format_color(0, 0, 255) if (x // 10 + y // 10) % 2 == 0 else format_color(255, 255, 0)  # Blue/Yellow
                pixels.append((x, y, color))

    elif pattern_type == "random":
        generate_random_pixels(canvas_width, canvas_height, packet_size)
        return

    else:
        ic(f"Unknown pattern type: {pattern_type}")
        return

    # Teile die Pixel in Pakete auf
    work_packets = [pixels[i:i + packet_size] for i in range(0, len(pixels), packet_size)]
    for packet in work_packets:
        work_queue.put(packet)

    ic(f"Generated {len(pixels)} pixels into {work_queue.qsize()} packets for pattern {pattern_type}.")

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
def start_master():
    packet_size = int(40 * PPS)

    if args.image_path:
        ic(f"Processing image: {args.image_path}")
        # Hier könntest du eine Funktion aufrufen, die Bild-Pixel generiert und in die Queue einfügt
        pass  # Placeholder für Bildverarbeitung
    else:
        ic("No image provided, generating random pixels.")
        generate_pixel_pattern(args.pattern, CANVAS_WIDTH, CANVAS_HEIGHT, packet_size)

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

# Starte den Master
start_master()
