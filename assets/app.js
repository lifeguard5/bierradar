/* =====================================================================
   Bierradar – App-Logik
   Laedt data/angebote.json (vom marktguru-Scraper erzeugt) + data/biere.json
   und zeigt die aktuellen Bierangebote der Umgebung.
   Bewusst ohne Framework: laedt schnell, laeuft ueberall.
   ===================================================================== */

(function () {
  "use strict";

  let aktiverFilter = "alle";   // "alle" oder eine bier_id
  let angebote = [];
  let biere = [];
  let quelle = "";

  const elListe  = document.getElementById("ergebnisliste");
  const elFilter = document.getElementById("filterleiste");
  const elStand  = document.getElementById("standzeile");
  const elInfo   = document.getElementById("info-inhalt");

  ladeDaten();

  async function ladeDaten() {
    elListe.innerHTML =
      '<div class="lade-puls"><span></span><span></span><span></span></div>';
    try {
      const buster = "?v=" + Date.now();
      const [angRes, bierRes] = await Promise.all([
        fetch("data/angebote.json" + buster),
        fetch("data/biere.json" + buster),
      ]);
      if (!angRes.ok || !bierRes.ok) throw new Error("Datei nicht erreichbar");

      const angDaten  = await angRes.json();
      const bierDaten = await bierRes.json();

      angebote = angDaten.angebote || [];
      quelle   = angDaten.quelle || "";
      biere    = bierDaten.biere || [];

      zeigeStand(angDaten.stand, angDaten.fehler);
      baueFilter();
      zeigeInfo(angDaten);
      zeigeListe();
    } catch (e) {
      elStand.textContent = "Angebote konnten nicht geladen werden.";
      elStand.classList.add("fehler");
      elListe.innerHTML = leererZustand(
        "\uD83D\uDCE1",
        "Keine Verbindung",
        "Die Angebotsdaten sind gerade nicht erreichbar. Bitte spaeter erneut versuchen."
      );
      console.error(e);
    }
  }

  // --- Stand-Anzeige -------------------------------------------------
  function zeigeStand(stand, fehler) {
    if (!stand) {
      elStand.textContent = "Stand unbekannt";
      return;
    }
    const d = new Date(stand);
    const datum = d.toLocaleDateString("de-DE",
      { day: "2-digit", month: "2-digit", year: "numeric" });
    const zeit = d.toLocaleTimeString("de-DE",
      { hour: "2-digit", minute: "2-digit" });
    let text = "Letzte Aktualisierung: " + datum + " um " + zeit + " Uhr";
    if (fehler && fehler.length) {
      text += "  \u00B7  einige Abfragen unvollst\u00E4ndig";
    }
    elStand.textContent = text;
  }

  // --- Filterleiste --------------------------------------------------
  function baueFilter() {
    elFilter.innerHTML = "";
    elFilter.appendChild(chip("alle", "Alle Biere", angebote.length));
    biere.forEach(function (b) {
      const anzahl = angebote.filter(function (a) {
        return a.bier_id === b.id;
      }).length;
      elFilter.appendChild(chip(b.id, b.name, anzahl));
    });
  }

  function chip(id, text, anzahl) {
    const el = document.createElement("button");
    el.className = "filter-chip" + (id === aktiverFilter ? " aktiv" : "");
    el.innerHTML = text + '<span class="anzahl">' + anzahl + "</span>";
    el.addEventListener("click", function () {
      aktiverFilter = id;
      baueFilter();
      zeigeListe();
    });
    return el;
  }

  // --- Ergebnisliste -------------------------------------------------
  function zeigeListe() {
    const gefiltert = aktiverFilter === "alle"
      ? angebote
      : angebote.filter(function (a) { return a.bier_id === aktiverFilter; });

    if (gefiltert.length === 0) {
      elListe.innerHTML = leererZustand(
        "\uD83C\uDF7A",
        "Kein Angebot gefunden",
        aktiverFilter === "alle"
          ? "Aktuell ist keines der beobachteten Biere im Angebot. Schau morgen wieder vorbei!"
          : "Fuer diese Sorte ist gerade kein Angebot bekannt. Andere Sorte probieren?"
      );
      return;
    }

    // nach Markt sortiert, guenstigster Preis zuerst innerhalb des Markts
    gefiltert.sort(function (a, b) {
      const m = a.markt_name.localeCompare(b.markt_name, "de");
      if (m !== 0) return m;
      return preisZahl(a.preis) - preisZahl(b.preis);
    });

    elListe.innerHTML = "";
    gefiltert.forEach(function (a, i) {
      elListe.appendChild(karte(a, i));
    });
  }

  function karte(a, index) {
    const el = document.createElement("div");
    el.className = "karte";
    el.style.animationDelay = (index * 0.04) + "s";

    const preis = a.preis
      ? '<span class="karte-preis">' + escHtml(a.preis) + " \u20AC</span>"
      : "";

    const titel = a.titel && a.titel !== a.bier_name
      ? '<div class="karte-titel">' + bereinige(a.titel) + "</div>"
      : "";

    const gueltig = formatGueltig(a.gueltig_bis);
    const gueltigZeile = gueltig
      ? '<span class="karte-gueltig">' + gueltig + "</span>"
      : "";

    el.innerHTML =
      '<div class="karte-streifen"></div>' +
      '<div class="karte-inhalt">' +
        '<div class="karte-kopf">' +
          '<span class="karte-bier">' + escHtml(a.bier_name) + "</span>" +
          preis +
        "</div>" +
        '<div class="karte-markt">' + escHtml(a.markt_name) + "</div>" +
        '<div class="karte-ort">' + escHtml(a.markt_ort || "") + "</div>" +
        titel +
        '<div class="karte-fuss">' +
          '<span class="badge badge-auto">Aktuelles Angebot</span>' +
          gueltigZeile +
        "</div>" +
      "</div>";
    return el;
  }

  // --- Infobereich ---------------------------------------------------
  function zeigeInfo(daten) {
    const anzahlMaerkte = neueMenge(angebote.map(function (a) {
      return a.markt_name;
    })).length;

    let html =
      '<p>Der Bierradar durchsucht automatisch die Angebotsprospekte ' +
      'der Supermaerkte und Getraenkemaerkte rund um Breuna.</p>';
    html +=
      '<div class="info-zeile"><span>Aktuelle Angebote</span><strong>' +
      angebote.length + "</strong></div>";
    html +=
      '<div class="info-zeile"><span>Maerkte mit Treffern</span><strong>' +
      anzahlMaerkte + "</strong></div>";
    if (quelle) {
      html +=
        '<div class="info-zeile"><span>Datenquelle</span><strong>' +
        escHtml(quelle) + "</strong></div>";
    }
    if (daten.fehler && daten.fehler.length) {
      html +=
        '<p class="info-warnung">Hinweis: ' + daten.fehler.length +
        " Abfrage(n) waren beim letzten Lauf nicht erfolgreich. " +
        "Die Liste kann daher unvollstaendig sein.</p>";
    }
    elInfo.innerHTML = html;
  }

  // --- Hilfsfunktionen ----------------------------------------------
  function formatGueltig(roh) {
    if (!roh) return "";
    const d = new Date(roh);
    if (isNaN(d.getTime())) return "";
    const heute = new Date();
    heute.setHours(0, 0, 0, 0);
    const tage = Math.round((d - heute) / 86400000);
    if (tage < 0) return "";
    if (tage === 0) return "nur noch heute";
    if (tage === 1) return "noch bis morgen";
    if (tage <= 7) return "noch " + tage + " Tage";
    return "gueltig bis " + d.toLocaleDateString("de-DE",
      { day: "2-digit", month: "2-digit" });
  }

  function preisZahl(p) {
    if (!p) return 9999;
    const n = parseFloat(String(p).replace(",", "."));
    return isNaN(n) ? 9999 : n;
  }

  function neueMenge(arr) {
    const gesehen = {};
    const raus = [];
    arr.forEach(function (x) {
      if (x && !gesehen[x]) { gesehen[x] = true; raus.push(x); }
    });
    return raus;
  }

  function leererZustand(symbol, titel, text) {
    return (
      '<div class="leer">' +
      '<div class="leer-symbol">' + symbol + "</div>" +
      '<div class="leer-titel">' + titel + "</div>" +
      '<div class="leer-text">' + text + "</div>" +
      "</div>"
    );
  }

  function escHtml(s) {
    return String(s || "").replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function bereinige(s) {
    return escHtml(String(s || "").replace(/\s+/g, " ").trim());
  }
})();
