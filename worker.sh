#!/bin/bash

# Name der virtuellen Umgebung
VENV_NAME="venv-worker"

# Pakete, die installiert werden sollen (hier als Beispiel numpy und requests)
PACKAGES=("toml" "requests")

# Virtuelle Umgebung erstellen
echo "Erstelle virtuelle Umgebung: $VENV_NAME"
python3 -m venv $VENV_NAME

# Virtuelle Umgebung aktivieren
echo "Aktiviere die virtuelle Umgebung"
source $VENV_NAME/bin/activate

# Installiere Pakete
echo "Installiere Pakete: ${PACKAGES[*]}"
pip install "${PACKAGES[@]}"

echo "Pakete installiert und virtuelle Umgebung ist aktiviert."
echo "Um die virtuelle Umgebung zu deaktivieren, benutze 'deactivate'."

python3 src/worker.py