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


def clean_title(text):
    # 🔥 NUR das entfernen, sonst nichts verändern
    text = text.replace("¬", "")
    text = text.replace("[Bildtonträger]", "")
    text = text.replace("(Bildtonträger)", "")
    return text.strip()


def search_opac(title):
    session = requests.Session()

    try:
        session.get(START, timeout=10)
        session.get(SEARCH, timeout=10)

        print("\n==============================")
        print("Suche:", title)

        params = {
            "methodToCall": "submit",
            "searchCategories[0]": "-1",
            "searchString[0]": title,
            "submitSearch": "Suchen"
        }

        headers = {"User-Agent": "Mozilla/5.0"}

        r = session.get(SEARCH, params=params, headers=headers, timeout=10)

        soup = BeautifulSoup(r.text, "html.parser")

        hits = soup.select("h2.recordtitle a")

        print("Gefundene Treffer:", len(hits))

        best_match = None
        best_score = 0

        for hit in hits:
            hit_title = hit.get_text(strip=True)
            hit_title = hit_title.replace("¬", "")

            # 🔥 weiterhin nur DVDs zulassen
            if "bildtonträger" not in hit_title.lower():
                continue

            # 🔥 HIER Änderung: bereinigte Titel vergleichen
            clean_input = clean_title(title).lower()
            clean_hit = clean_title(hit_title).lower()

            score = fuzz.ratio(clean_input, clean_hit)

            print(f"→ {hit_title} (Score: {score})")

            if score > best_score:
                best_score = score
                best_match = hit_title

        if best_match and best_score > 65:
            return {
                "found": True,
                "title": best_match
            }

        return {"found": False}

    except Exception as e:
        print("Fehler:", e)
        return {"found": False}


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


@app.post("/check", response_class=HTMLResponse)
async def check(file: UploadFile = File(...)):
    content = await file.read()

    try:
        csv_text = content.decode("utf-8")
    except:
        csv_text = content.decode("utf-8-sig")

    reader = csv.DictReader(StringIO(csv_text))

    html = "<h2>Ergebnisse</h2><ul>"

    for row in reader:
        title = row.get("Name") or ""
        if not title:
            continue

        result = search_opac(title)

        if result["found"]:
            status = f"✅ gefunden: {result['title']}"
        else:
            status = "❌ nicht gefunden"

        html += f"<li>{title} — {status}</li>"

    html += "</ul><br><a href='/'>Zurück</a>"

    return html