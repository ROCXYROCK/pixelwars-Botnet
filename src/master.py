import socket
import threading
import json
import random
import os
from PIL import Image
from queue import Queue
import requests
import toml
import argparse

# Lade Konfiguration aus config.toml
config = toml.load("cfg/config.toml")

# Konfigurationseinstellungen aus der TOML-Datei
DIST_HOST = config["Dist"]["HOST"]
DIST_PORT = config["Dist"]["PORT"]
PPS_ENDPOINT = config["Dist"]["pps"]
SRC_HOST = "0.0.0.0"
SRC_PORT = config["Src"]["PORT"]
FILES_DIR = config["Files"]["dir"]
PROGRESS_FILE = config["Files"]["progress"]

# API base URL
BASE_URL = f"{DIST_HOST}{DIST_PORT}" if DIST_PORT else DIST_HOST

# Queue for work packages
work_queue = Queue()

# Argumentparser für CLI-Eingaben
parser = argparse.ArgumentParser(description="Image processing master server.")
parser.add_argument("image_path", type=str, help="Path to the image file to process.")
args = parser.parse_args()

# Get the size of the canvas
def get_canvas_size():
    response = requests.get(f"{BASE_URL}/canvas/size", headers={'accept': 'application/json'})
    if response.status_code == 200:
        size = response.json()
        canvas_width = size['x']
        canvas_height = size['y']
        print(f"Canvas size obtained: width={canvas_width}, height={canvas_height}")
        return canvas_width, canvas_height
    else:
        print(f"Failed to get canvas size. Status code: {response.status_code}")
        raise Exception('Failed to get canvas size')

# Get pixels per second (PPS) from server
def get_pps():
    response = requests.get(f"{BASE_URL}{PPS_ENDPOINT}", headers={'accept': 'application/json'})
    if response.status_code == 200:
        pps = float(response.json())
        print(f"PPS rate limit obtained: {pps}")
        return pps
    else:
        print(f"Failed to get PPS rate limit. Status code: {response.status_code}")
        raise Exception('Failed to get PPS rate limit')

# Save progress to a file
def save_progress(last_pixel_index, start_x, start_y):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({
            'last_pixel_index': last_pixel_index,
            'start_x': start_x,
            'start_y': start_y
        }, f)
    print(f"Progress saved with last pixel index: {last_pixel_index} and starting coordinates: ({start_x}, {start_y})")

# Load progress from file if exists
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

# Load image and create work packages based on PPS, starting from the saved progress
def load_image_to_work_queue(image_path, start_index=0, start_x=0, start_y=0):
    image = Image.open(image_path).convert('RGB')
    img_width, img_height = image.size

    # Get canvas size and calculate a random position if not resuming
    canvas_width, canvas_height = get_canvas_size()
    if start_x == 0 and start_y == 0:
        start_x = random.randint(0, canvas_width - img_width)
        start_y = random.randint(0, canvas_height - img_height)
        save_progress(0, start_x, start_y)
    print(f"Starting position on canvas: (x={start_x}, y={start_y})")

    # Get the PPS and calculate the packet size as 40 times the PPS
    pps = get_pps()
    packet_size = int(40 * pps)
    print(f"Dynamically calculated packet size based on PPS: {packet_size}")

    # Prepare pixel data with adjusted coordinates, starting from last saved progress
    pixels = []
    for y in range(img_height):
        for x in range(img_width):
            r, g, b = image.getpixel((x, y))
            if (r, g, b) != (0, 0, 0):  # Ignore black pixels
                color = f'{r:02x}{g:02x}{b:02x}'
                pixels.append((start_x + x, start_y + y, color))

    # Only include pixels starting from `start_index`
    pixels = pixels[start_index:]

    # Split pixels into packets of `packet_size`
    work_packets = [pixels[i:i + packet_size] for i in range(0, len(pixels), packet_size)]
    for packet in work_packets:
        work_queue.put(packet)

    print(f"Loaded {len(pixels)} pixels into {work_queue.qsize()} work packets, starting from index {start_index}.")

# Handle Worker Connection
def handle_worker(conn, addr, start_index=0, start_x=0, start_y=0):
    print(f"Worker connected from {addr}")
    pixel_index = start_index

    while not work_queue.empty():
        try:
            # Get the next work packet
            work_packet = work_queue.get_nowait()

            # Save progress immediately after sending the packet
            pixel_index += len(work_packet)
            save_progress(pixel_index, start_x, start_y)

            # Send the work packet to the worker
            conn.sendall(json.dumps(work_packet).encode())  
            print(f"Sent work packet to {addr}")

            # Wait for worker completion
            response = conn.recv(1024).decode()
            if response == "done":
                print(f"Worker {addr} finished a packet.")
                work_queue.task_done()
            else:
                print(f"Unexpected response from {addr}: {response}")

            if work_queue.empty():
                print(f"No more work packets for {addr}")
                if os.path.exists(PROGRESS_FILE):
                    os.remove(PROGRESS_FILE)  # Clear progress upon completion
                break

        except Exception as e:
            print(f"Error handling worker {addr}: {e}")
            break

    conn.close()
    print(f"Worker {addr} disconnected")

# Start the master server and load saved progress if available
def start_master(image_path):
    last_pixel_index, start_x, start_y = load_progress()
    
    # Initialize work packets starting from last saved pixel index and coordinates
    load_image_to_work_queue(image_path, start_index=last_pixel_index, start_x=start_x, start_y=start_y)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((SRC_HOST, SRC_PORT))
    server.listen(5)
    print(f"Master server listening on {SRC_HOST}:{SRC_PORT}")

    # Accept worker connections
    while not work_queue.empty():
        conn, addr = server.accept()
        worker_thread = threading.Thread(target=handle_worker, args=(conn, addr, last_pixel_index, start_x, start_y))
        worker_thread.start()

    server.close()
    print("All work packets processed.")

# Run the master with the CLI-specified image path
start_master(args.image_path)
