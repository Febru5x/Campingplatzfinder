"""Update-Lauf: bestehende Regionen auffrischen – OHNE KI, ohne Agent.

Was passiert (alles rein mechanisch, reproduzierbar):
  1. OSM-Grundliste NEU holen (neue/entfernte/umbenannte Plaetze)   [s01]
  2. Wasserlage neu berechnen (frische Overpass-Daten)             [s02]
  3. Flurstuecke: nur neue Plaetze + aelter als 90 Tage            [s03]
  4. Luftbilder: nur fehlende + aelter als 180 Tage (neue Befliegung) [s04]
  5. Websites neu scrapen (Preise, Bestand, Kontakt)               [s05]
  6. B-Plaene/Gebaeude/Marktpreise/Bestandsalter (Top-Plaetze)     [s11-14]
  7. Gewaesserflaechen, Namen, Klassifizierung, Modernitaet        [s18,20,17,19]
  8. Scores + Rechenbeispiele, Excel/Karten/Dossiers               [s06,07,08]

NICHT enthalten (bewusst, braucht einen KI-Agenten bzw. echten Browser):
  - s15 KI-Bildsichtung (Multimodal-Sichtung der Luftbilder)
  - Portal-Scrapes Booking/Airbnb (s13-Rohdaten; Browser-Session).
    Vorhandene Rohdaten werden weiterverwendet; Preise aendern sich
    langsamer als die Struktur. Bei Bedarf manuell aktualisieren.
  Bestehende KI-Sichtungen bleiben in der DB erhalten.

Aufruf (manuell oder per Windows-Aufgabenplanung alle X Wochen):
  python -m pipeline.refresh alle
  python -m pipeline.refresh sachsen thueringen

Umgebungsvariable CAMPING_REFRESH=1 wird intern gesetzt: s01/s02
ignorieren dann ihre Caches, s04 laedt alte Bilder neu.
"""
import os
import sys
import time

os.environ["CAMPING_REFRESH"] = "1"

from . import (s01_grundliste, s02_wasser, s03_grundstueck, s04_luftbild,
               s05_website, s06_bewertung, s07_export, s08_dossiers,
               s11_bplan, s12_bestandsalter, s13_marktpreise, s14_gebaeude,
               s17_datenqualitaet, s18_gewaesserflaeche, s19_website_modern,
               s20_namen)

REGIONS = ["seenplatte", "brandenburg", "sachsen", "sachsen_anhalt", "thueringen"]


def refresh_region(reg):
    t0 = time.time()
    print("\n########## REFRESH %s ##########" % reg, flush=True)
    steps = [
        ("s01 Grundliste (live)", lambda: s01_grundliste.run(reg)),
        ("s02 Wasserlage (live)", lambda: s02_wasser.run(reg)),
        ("s03 Flurstuecke", lambda: s03_grundstueck.run(reg, workers=4)),
        ("s04 Luftbilder (neue/alte)", lambda: s04_luftbild.run(reg, workers=4)),
        ("s05 Websites", lambda: s05_website.run(reg, workers=6)),
        ("s11 B-Plaene", lambda: s11_bplan.run(reg, top=30)),
        ("s12 Bestandsalter", lambda: s12_bestandsalter.run(reg, top=30)),
        ("s14 Gebaeude", lambda: s14_gebaeude.run(reg, top=40)),
        ("s13 Marktpreise (vorhandene Rohdaten)", lambda: s13_marktpreise.run(reg)),
        ("s18 Gewaesserflaechen", lambda: s18_gewaesserflaeche.run(reg)),
        ("s20 Namen", lambda: s20_namen.run(reg)),
        ("s17 Klassifizierung", lambda: s17_datenqualitaet.run(reg)),
        ("s19 Website-Modernitaet", lambda: s19_website_modern.run(reg)),
        ("s06 Bewertung", lambda: s06_bewertung.run(reg)),
        ("s07 Export", lambda: s07_export.run(reg)),
        ("s08 Dossiers", lambda: s08_dossiers.run(reg, 20)),
    ]
    for label, fn in steps:
        t = time.time()
        print("\n== %s ==" % label, flush=True)
        try:
            fn()
        except Exception as ex:
            print("FEHLER in %s: %s (weiter mit naechstem Schritt)" % (label, ex))
        print("   (%.1f min)" % ((time.time() - t) / 60), flush=True)
    print("\n########## %s fertig (%.1f min) ##########" % (reg, (time.time() - t0) / 60))


if __name__ == "__main__":
    args = sys.argv[1:] or ["alle"]
    regs = REGIONS if "alle" in args else args
    for reg in regs:
        refresh_region(reg)
    print("\nAlle Regionen aktualisiert. Veroeffentlichen mit: tools\\publish.ps1")