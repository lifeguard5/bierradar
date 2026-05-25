/* =====================================================================
   Bierradar – App-Logik
   Laedt data/angebote.json + data/biere.json und zeigt die Bierangebote.
   Bewusst ohne Framework gehalten: laedt schnell, laeuft ueberall.
   ===================================================================== */

(function () {
  "use strict";

  // aktiver Filter: "alle" oder eine bier_id
  let aktiverFilter = "alle";
  let angebote = [];
  let biere = [];
  let marktStatus = [];

  const elListe   = document.getElementById("ergebnisliste");
  const elFilter  = document.getElementById("filterleiste");
  const elStand   = document.getElementById("standzeile");
  const elMarkt   = document.getElementById("marktstatus-inhalt");

  // --- Start ---------------------------------------------------------
  ladeDaten();

  async function ladeDaten() {
    elListe.innerHTML =
      '<div class="lade-puls"><span></span><span></span><span></span></div>';
    try {
      // Cache umgehen, damit immer der frische Scraper-Stand kommt
      const buster = "?v=" + Date.now();
      const [angRes, bierRes] = await Promise.all([
        fetch("data/angebote.json" + buster),
        fetch("data/biere.json" + buster),
      ]);
      if (!angRes.ok || !bierRes.ok) throw new Error("Datei nicht erreichbar");

      const angDaten  = await angRes.json();
      const bierDaten = await bierRes.json();

      angebote    = angDaten.angebote || [];
      marktStatus = angDaten.markt_status || [];
      biere       = bierDaten.biere || [];

      zeigeStand(angDaten.stand);
      baueFilter();
      zeigeMarktStatus();
      zeigeListe();
    } catch (e) {
      elStand.textContent = "Angebote konnten nicht geladen werden.";
      elStand.classList.add("fehler");
      elListe.innerHTML = leererZustand(
        "📡",
        "Keine Verbindung",
        "Die Angebotsdaten sind gerade nicht erreichbar. Bitte später erneut versuchen."
      );
      console.error(e);
    }
  }

  // --- Stand-Anzeige -------------------------------------------------
  function zeigeStand(stand) {
    if (!stand) {
      elStand.textContent = "Stand unbekannt";
      return;
    }
    const d = new Date(stand);
    const datum = d.toLocaleDateString("de-DE", {
      day: "2-digit", month: "2-digit", year: "numeric",
    });
    const zeit = d.toLocaleTimeString("de-DE", {
      hour: "2-digit", minute: "2-digit",
    });
    elStand.textContent = "Letzte Aktualisierung: " + datum + " um " + zeit + " Uhr";
  }

  // --- Filterleiste --------------------------------------------------
  function baueFilter() {
    elFilter.innerHTML = "";

    // "Alle"-Chip
    elFilter.appendChild(
      chip("alle", "Alle Biere", angebote.length)
    );

    // ein Chip pro Biersorte
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
    el.innerHTML =
      text + '<span class="anzahl">' + anzahl + "</span>";
    el.addEventListener("click", function () {
      aktiverFilter = id;
      baueFilter();
      zeigeListe();
    });
    return el;
  }

  // --- Ergebnisliste -------------------------------------------------
  function zeigeListe() {
    const gefiltert =
      aktiverFilter === "alle"
        ? angebote
        : angebote.filter(function (a) {
            return a.bier_id === aktiverFilter;
          });

    if (gefiltert.length === 0) {
      elListe.innerHTML = leererZustand(
        "🍺",
        "Kein Angebot gefunden",
        aktiverFilter === "alle"
          ? "Aktuell ist keines der beobachteten Biere im Angebot. Schau morgen wieder vorbei!"
          : "Für diese Sorte ist gerade kein Angebot bekannt. Andere Sorte probieren?"
      );
      return;
    }

    // nach Bier gruppieren wirkt aufgeraeumt; hier einfach: nach Markt sortiert
    gefiltert.sort(function (a, b) {
      return a.markt_name.localeCompare(b.markt_name, "de");
    });

    elListe.innerHTML = "";
    gefiltert.forEach(function (a, i) {
      elListe.appendChild(karte(a, i));
    });
  }

  function karte(a, index) {
    const el = document.createElement("a");
    el.className = "karte";
    el.href = a.markt_url || "#";
    el.target = "_blank";
    el.rel = "noopener";
    el.style.animationDelay = (index * 0.04) + "s";

    const preis = a.preis
      ? '<span class="karte-preis">' + a.preis + " €</span>"
      : "";

    const titel = a.titel && a.titel !== a.bier_name
      ? '<div class="karte-titel">„' + bereinige(a.titel) + '"</div>'
      : "";

    const badge =
      a.quelle === "manuell"
        ? '<span class="badge badge-manuell">Eingetragen</span>'
        : '<span class="badge badge-auto">Automatisch erkannt</span>';

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
          badge +
          '<span class="karte-pfeil">Zum Markt &rsaquo;</span>' +
        "</div>" +
      "</div>";
    return el;
  }

  // --- Marktstatus ---------------------------------------------------
  function zeigeMarktStatus() {
    if (!marktStatus.length) {
      elMarkt.innerHTML =
        '<div class="markt-zeile"><span class="markt-zeile-info">' +
        "Noch keine Statusdaten vorhanden.</span></div>";
      return;
    }
    elMarkt.innerHTML = "";
    marktStatus.forEach(function (m) {
      const zeile = document.createElement("div");
      zeile.className = "markt-zeile";

      let punktKlasse = "punkt-manuell";
      let info = "wird von Hand gepflegt";
      if (m.status === "ok") {
        punktKlasse = "punkt-ok";
        info = m.treffer + " Treffer";
      } else if (m.status === "fehler") {
        punktKlasse = "punkt-fehler";
        info = "automatisch nicht lesbar";
      }

      zeile.innerHTML =
        '<span class="markt-punkt ' + punktKlasse + '"></span>' +
        '<span class="markt-zeile-name">' + escHtml(m.name) + "</span>" +
        '<span class="markt-zeile-info">' + info + "</span>";
      elMarkt.appendChild(zeile);
    });
  }

  // --- Hilfsfunktionen ----------------------------------------------
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

  // Scraper-Textausschnitte koennen rohen Text enthalten – etwas glaetten
  function bereinige(s) {
    return escHtml(String(s || "").replace(/\s+/g, " ").trim());
  }
})();
