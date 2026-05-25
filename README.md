# 🍺 Bierradar

Eine kleine Web-App, die zeigt, in welchem Getränke- oder Lebensmittelmarkt
rund um Breuna gerade ein bestimmtes Bier im Angebot ist. Im Veltins-Look,
mobil-optimiert, läuft kostenlos über GitHub Pages.

Beobachtete Biere: **Veltins**, **Erdinger Weißbier**, **Mönchshof Hell**,
**Hasseröder**.

---

## Wie es funktioniert

Die App liest die Angebote **vollautomatisch** aus – niemand muss etwas von
Hand eintragen.

1. Ein Skript (`scraper/scrape.py`) fragt **einmal täglich automatisch**
   (per GitHub Actions) das Prospekt-Portal **marktguru.de** ab.
   marktguru sammelt die Angebotsprospekte praktisch aller deutschen
   Supermärkte und Getränkemärkte.
2. Das Skript sucht dort nach den vier Biersorten – für mehrere
   Postleitzahlen rund um Breuna (Breuna, Volkmarsen, Warburg, Wolfhagen).
3. Die Treffer landen in `data/angebote.json`.
4. Die Web-App (`index.html`) zeigt diese Angebote schön aufbereitet an –
   mit Markt, Preis und „gültig bis".

> **Warum marktguru und nicht REWE/EDEKA direkt?**
> Die Webseiten der großen Handelsketten sind technisch gegen automatische
> Zugriffe abgesichert und lassen sich von einer GitHub Page aus nicht
> zuverlässig auslesen. marktguru bündelt die Prospekte all dieser Märkte
> an einer Stelle und ist deutlich besser zugänglich. So bekommt der
> Bierradar mit **einer einzigen Quelle** die Angebote der ganzen Umgebung.

---

## Einrichtung (einmalig, ca. 5 Minuten)

1. **GitHub-Konto** anlegen (falls noch nicht vorhanden) auf github.com.
2. Ein **neues Repository** anlegen, z. B. `bierradar`.
3. Alle Dateien aus diesem Ordner ins Repository hochladen
   (per Drag & Drop auf der GitHub-Webseite reicht).
4. Im Repository auf **Settings → Pages** gehen.
   Unter „Source" **Deploy from a branch** wählen, Branch **main**,
   Ordner **/ (root)**, speichern.
5. Nach ein, zwei Minuten ist die App erreichbar unter:
   `https://DEIN-BENUTZERNAME.github.io/bierradar/`
6. Den **Scraper aktivieren**: Reiter **Actions** öffnen, die Workflows
   einmal bestätigen. Danach läuft der Scraper täglich automatisch.
   Tipp: Im Reiter „Actions" kann man den Lauf über „Run workflow" auch
   sofort manuell anstoßen, um die App gleich zu füllen.

Den Link kannst du an deine Freunde schicken. Auf dem Handy lässt sich die
Seite über „Zum Startbildschirm hinzufügen" wie eine echte App ablegen.

---

## Anpassen

Alle Einstellungen stecken in zwei Dateien im Ordner `data/`:

**`data/config.json`** – die Orte / Postleitzahlen, in denen gesucht wird.
Neue Postleitzahl einfach in die Liste ergänzen, dann deckt der Bierradar
auch dort die Angebote ab. Aktuell: Breuna, Volkmarsen, Warburg, Wolfhagen
(zusammen rund 20 km um Breuna).

**`data/biere.json`** – die beobachteten Biersorten. Weitere Sorten lassen
sich ergänzen. Pro Bier gibt es:
- `suchbegriffe` – was bei marktguru gesucht wird
- `aliase` – Stichwörter (klein), mit denen geprüft wird, ob ein gefundenes
  Angebot wirklich zum Bier passt

Nach dem Speichern auf GitHub läuft der Scraper automatisch neu.

---

## Wenn keine Angebote mehr erscheinen

Sollte die App dauerhaft leer bleiben, im Reiter **Actions** den letzten
Lauf öffnen und die Meldungen ansehen. Häufigster Fall: marktguru hat seine
Webseite umgebaut und die automatische Schlüssel-Erkennung muss angepasst
werden. Die betreffende Stelle ist in `scraper/scrape.py` in der Funktion
`hole_api_schluessel()` kommentiert.

---

## Projektaufbau

```
bierradar/
├── index.html              Die App-Seite
├── manifest.json           Damit die App aufs Handy gelegt werden kann
├── assets/
│   ├── style.css           Design (Veltins-Look)
│   ├── app.js              App-Logik
│   └── favicon.svg         Symbol
├── data/
│   ├── config.json         ➜ Orte / Postleitzahlen
│   ├── biere.json          ➜ Biersorten
│   └── angebote.json       (automatisch erzeugt – nicht bearbeiten)
├── scraper/
│   ├── scrape.py           Das Auslese-Skript (Quelle: marktguru.de)
│   └── requirements.txt
└── .github/workflows/
    └── scrape.yml          Der tägliche Automatik-Lauf
```

---

*Bierradar ist ein privates Projekt. Keine offizielle Seite einer Brauerei,
eines Marktes oder von marktguru. Angaben ohne Gewähr – maßgeblich ist
immer der Aushang im Markt.*
