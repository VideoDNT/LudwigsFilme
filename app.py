from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
import csv
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from io import StringIO

app = FastAPI()

BASE = "https://katalog.stadtbibliothek-weimar.de"
START = BASE + "/webOPACClient/start.do"
SEARCH = BASE + "/webOPACClient/search.do"


# 🔍 Suche im OPAC
def search_opac(title):
    session = requests.Session()

    try:
        # 1. Session starten
        session.get(START, timeout=10)
        session.get(SEARCH, timeout=10)

        # 2. Suche senden
        params = {
            "methodToCall": "submit",
            "searchCategories[0]": "-1",
            "searchString[0]": title,
            "submitSearch": "Suchen"
        }

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        r = session.get(SEARCH, params=params, headers=headers, timeout=10)

        soup = BeautifulSoup(r.text, "html.parser")

        # 🔥 Nur echte Treffer (Titel) holen
        hits = soup.select(".recordtitle a")

        best_score = 0
        best_match = None

        for h in hits:
            text = h.get_text(strip=True)

            score = fuzz.partial_ratio(title.lower(), text.lower())

            if score > best_score:
                best_score = score
                best_match = text

        # 🔥 Nur gute Treffer akzeptieren
        if best_score > 70:
            return True, best_match, best_score
        else:
            return False, best_match, best_score

    except Exception as e:
        return False, str(e), 0


# 🌐 Startseite
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body style="font-family:sans-serif; padding:20px;">
        <h2>📚 Watchlist → Bibliothek</h2>
        
        <form action="/check" enctype="multipart/form-data" method="post">
            <input name="file" type="file"><br><br>
            <button type="submit">Prüfen</button>
        </form>
    </body>
    </html>
    """


# 📊 CSV prüfen
@app.post("/check", response_class=HTMLResponse)
async def check(file: UploadFile = File(...)):
    content = await file.read()

    try:
        csv_text = content.decode("utf-8")
    except:
        csv_text = content.decode("utf-8-sig")

    reader = csv.DictReader(StringIO(csv_text))

    html = """
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body style="font-family:sans-serif; padding:20px;">
    <h2>Ergebnisse</h2>
    <ul>
    """

    for row in reader:
        title = row.get("Name") or ""
        if not title:
            continue

        found, match, score = search_opac(title)

        if found:
            status = f"✅ gefunden ({match})"
        else:
            status = f"❌ nicht gefunden (Score {score})"

        html += f"<li><b>{title}</b> — {status}</li>"

    html += """
    </ul>
    <br><a href="/">Zurück</a>
    </body>
    </html>
    """

    # 🔥 WICHTIG: Cache deaktivieren → Fix für dein Problem
    return HTMLResponse(
        content=html,
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache"
        }
    )
