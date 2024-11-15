# 🖼️ Pixelwar Botnet 🎨

**Pixelwar Botnet** ist ein leistungsstarkes, verteiltes System für das pixelweise Rendering von Bildern auf einer zentralen Leinwand-API. Mit einer dynamischen Master-Worker-Architektur können Sie mühelos Pixel platzieren und in Echtzeit auf der Leinwand zeichnen. Ideal für großformatige Kunstwerke, bei denen Sie die Arbeit flexibel auf viele Worker verteilen möchten! 🎉💻

---

## 🚀 Funktionen

- **Master-Worker-Architektur**: Der Master teilt das Bild in verarbeitbare Pakete und verteilt sie an verbundene Worker.
- **Dynamische Skalierung**: Fügen Sie beliebig viele Worker hinzu, um die Rendergeschwindigkeit zu steigern.
- **Rate-Limit-Anpassung**: Die Worker passen ihr Tempo an die API-Rate-Limits an und vermeiden dadurch Sperren oder Verzögerungen.
- **Automatisches Fortschrittsspeichern**: Bei einem Neustart setzt der Master genau dort an, wo er aufgehört hat – keine verlorenen Pixel mehr!

---

## 🌐 Architekturübersicht

Das **Pixelwar Botnet** basiert auf einer verteilten Master-Worker-Architektur:

- **Master-Server** 🧠: Der Master verwaltet das gesamte Bild und teilt es in Arbeitspakete (Pixelblöcke) auf. Er hält den Fortschritt aufrecht und verteilt die Arbeit an die Worker, die verbunden sind.
  
- **Worker-Clients** 🖌️: Jeder Worker holt sich Pakete vom Master, passt die Verzögerung je nach API-Limit an und platziert die Pixel auf der Leinwand.

---

## 📦 Arbeitspakete und API-Rate-Limitierung

- **Pixelmuster**: Der Master kann verschiedene Muster generieren, die an die Worker verteilt werden:
  - `stripes`: Vertikale Streifenmuster.
  - `checkerboard`: Schachbrettmuster.
  - `random`: Zufällige Pixel in verschiedenen Farben.

- **Paketgröße**: Basierend auf dem API-Rate-Limit (PPS) wird die Paketgröße automatisch angepasst:
  ```plaintext
  Paketgröße = 40 * PPS 
  ```

- **Verzögerungsanpassung**: Worker holen sich das Pixels-per-Second-Limit (PPS) alle 10 Sekunden neu und passen die Wartezeit dynamisch an.

---

## ⚙️ Konfiguration: `config.toml`

Alle wichtigen Einstellungen sind zentral in `config.toml` gespeichert. Hier finden Sie API-Details, Netzwerk-Parameter und Verzeichnisinformationen.

```toml
[Dist]
HOST = "https://pixels.security-day.hs-offenburg.de"  # Basis-URL der API
PORT = ""                                             # API-Port (optional)

pps = "/canvas/pps"                                   # Endpunkt für PPS-Abfrage
set = "/canvas/pixel"                                 # Endpunkt zum Platzieren der Pixel

[Src]
HOST = "localhost"                                    # Hostadresse des Masters
PORT = 5555                                           # Port des Masters

[Files]
dir = "/pics"                                         # Verzeichnis für Bilddateien
progress = "/data/progress.json"                      # Fortschrittsdatei zur Wiederaufnahme   
```


### Anpassungsmöglichkeiten ✨

- **[Dist]**: Konfigurieren Sie die API-URL und die relevanten Endpunkte.
- **[Src]**: Hier legen Sie die Netzwerkparameter des Masters fest.
- **[Files]**: Pfad zu Bilddateien und Fortschrittsdatei.

---

## 🛠️ Anleitung: Master und Worker starten

### Voraussetzungen

- **Docker**: [Installieren Sie Docker](https://docs.docker.com/get-docker/)


### Master ausführen

1. **Master-Image** erstellen

```bash
   docker build -t master_image -f Docker/master .
 ```

2. **Master-Container** ausführen 🌐

```bash
   docker run -d -p 5555:5555 --name master master_image
 ```

### Worker ausführen

1. **Worker-Image** erstellen

```bash
   docker build -t worker_image -f Docker/worker .
 ```

 2. **Worker-Container** ausführen 🌐

 ```bash
   docker run -d --name worker1 worker_image
 ```
---

Hierbei kann die Option --pattern verwendet werden, um das Muster für die Pixel zu wählen:

    stripes: Vertikale Streifenmuster.
    checkerboard: Schachbrettmuster.
    random: Zufällige Pixelmuster.

Standardmäßig wird checkerboard verwendet, wenn keine Option angegeben wird

---

### ⚡ Ablauf im Detail

**Master-Server**: Teilt das Bild in Arbeitspakete und sendet diese an die Worker. Fortschritte werden gespeichert, um bei einem Neustart problemlos fortzusetzen.

    
**Worker-Clients**: Die Worker verbinden sich mit dem Master, holen Arbeitspakete ab und platzieren Pixel auf der Leinwand. Die Verzögerung wird alle 10 Sekunden dynamisch angepasst, um die Rate-Limits der API einzuhalten.

### 🖼️ Konfigurationsbeispiel
Falls Sie eine andere API-URL oder alternative Endpunkte verwenden möchten, ändern Sie einfach der `[Dist]`-Konfiguration in `config.toml`:

```toml
[Dist]
HOST = "https://alternative-canvas-api.com"
PORT = "8080"
pps = "/api/pps_rate"
set = "/api/set_pixel"
```
---

## 🔄 Anpassungsmöglichkeiten und Tipps

- **Worker-Anzahl skalieren**: Mehr Worker erhöhen die Geschwindigkeit der Pixelplatzierung.
- **PPS-Rate beobachten**: Durch Anpassungen am `pps`-Endpunkt kann die Verzögerung effizient an die API-Beschränkungen angepasst werden.
- **Fortschrittsdatei**: Verwenden Sie die Fortschrittsdatei, um bei Unterbrechungen nahtlos weiterzumachen.

---
## 🔧 Weitere Anpassungen und Optimierungen

- **API-URL und Ports anpassen**: Im `config.toml` lassen sich die API-Host- und Port-Einstellungen sowie die Endpunkte anpassen. Dies erlaubt eine flexible Nutzung der Anwendung mit verschiedenen APIs und Servern.
- **Dynamische Verzögerung für Worker**: Die Worker passen die Verzögerung alle 10 Sekunden an die aktuellen API-Ratenbeschränkungen (PPS) an, um die Performance zu optimieren.
- **Skalierung der Worker**: Durch Hinzufügen weiterer Worker-Instanzen wird die Geschwindigkeit der Pixelplatzierung erhöht – ideal, wenn große Bilder schnell auf die Leinwand gebracht werden sollen.
  
---

## 🌟 Haben Sie Fragen oder möchten zur Weiterentwicklung beitragen?

Bitte öffnen Sie ein Issue oder senden Sie uns eine Pull-Request! Mit Ihrer Hilfe können wir das Pixelwar Botnet weiter verbessern und gemeinsam an der kreativen Leinwand arbeiten.

Viel Spaß und viel Erfolg beim Aufbau Ihrer Pixelwelt! 🎉💻✨

---

**Lust auf Pixelkunst?** 
🎨🌍 Dieses System macht es möglich, die gesamte Leinwand gemeinsam zu gestalten! Einfach Worker hinzufügen und los geht’s – sehen Sie zu, wie Ihr Bild in Echtzeit zum Leben erwacht.

---
