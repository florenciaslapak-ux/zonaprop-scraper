import re
import json
import time
import random
from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import tempfile
import os

app = Flask(__name__)
CORS(app)

HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Referer": "https://www.zonaprop.com.ar/",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Accept-Language": "es-AR,es;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.zonaprop.com.ar/",
    },
]


def fetch_page(url):
    headers = random.choice(HEADERS_LIST)
    session = requests.Session()
    # First visit the homepage to get cookies
    try:
        session.get("https://www.zonaprop.com.ar/", headers=headers, timeout=15)
        time.sleep(random.uniform(1.5, 3.0))
    except Exception:
        pass
    response = session.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.text


def extract_property_data(html, url):
    soup = BeautifulSoup(html, "html.parser")

    # Try to extract JSON-LD structured data first
    json_ld = None
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") in ("RealEstateListing", "Product", "Offer"):
                json_ld = data
                break
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") in ("RealEstateListing", "Product"):
                        json_ld = item
                        break
        except Exception:
            pass

    # --- Title ---
    title = ""
    for sel in ["h1", ".title-container h1", ".titleProperty", "[data-qa='POSTING_TITLE']"]:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            title = el.get_text(strip=True)
            break
    if not title and json_ld:
        title = json_ld.get("name", "")

    # --- Price ---
    price = ""
    for sel in [
        "[data-qa='POSTING_PRICE']",
        ".price-operation",
        ".firstPrice",
        ".price",
        "span.price",
    ]:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            price = el.get_text(strip=True)
            break

    # --- Address / Location ---
    address = ""
    for sel in [
        "[data-qa='POSTING_LOCATION']",
        ".title-location",
        ".location-address",
        "h2.title-location",
    ]:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            address = el.get_text(strip=True)
            break
    if not address and json_ld:
        addr = json_ld.get("address", {})
        if isinstance(addr, dict):
            address = ", ".join(filter(None, [
                addr.get("streetAddress", ""),
                addr.get("addressLocality", ""),
                addr.get("addressRegion", ""),
            ]))

    # --- Description ---
    description = ""
    for sel in [
        "[data-qa='POSTING_DESCRIPTION']",
        ".description-container",
        "#reactDescription",
        ".posting-description",
    ]:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            description = el.get_text(separator="\n", strip=True)
            break

    # --- Features / Characteristics ---
    features = []
    for sel in [
        "[data-qa='POSTING_FEATURES_ITEM']",
        ".section-icon-features li",
        ".posting-features li",
        ".characteristics li",
    ]:
        items = soup.select(sel)
        if items:
            for item in items:
                text = item.get_text(strip=True)
                if text:
                    features.append(text)
            break

    # Also grab general features section
    general_features = []
    for sel in [
        "[data-qa='POSTING_AMENITIES_ITEM']",
        ".general-section li",
        ".amenities li",
    ]:
        items = soup.select(sel)
        if items:
            for item in items:
                text = item.get_text(strip=True)
                if text:
                    general_features.append(text)
            break

    # --- Images ---
    images = []
    # Try og:image and meta images first
    for meta in soup.find_all("meta", property=re.compile(r"og:image")):
        src = meta.get("content", "")
        if src and src not in images:
            images.append(src)

    # Gallery images
    for sel in [
        "img[data-qa='POSTING_IMAGE']",
        ".gallery-slider img",
        ".photo-slider img",
        "img.lazyload",
        ".media-viewer img",
    ]:
        for img in soup.select(sel):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if src and "http" in src and src not in images:
                images.append(src)

    # Deduplicate and filter out tiny/tracking images
    images = [img for img in images if not any(x in img.lower() for x in ["placeholder", "logo", "icon", "sprite", "blank"])]
    images = list(dict.fromkeys(images))[:30]  # max 30 images

    # --- Property type ---
    prop_type = ""
    for sel in ["[data-qa='POSTING_TYPE']", ".title-type-sup", ".breadcrumb li:last-child"]:
        el = soup.select_one(sel)
        if el:
            prop_type = el.get_text(strip=True)
            break

    return {
        "title": title,
        "price": price,
        "address": address,
        "description": description,
        "features": features,
        "general_features": general_features,
        "images": images,
        "prop_type": prop_type,
        "source_url": url,
    }


def generate_html(data):
    images_html = ""
    for i, img_url in enumerate(data["images"]):
        images_html += f'<img src="{img_url}" alt="Imagen {i+1}" onerror="this.style.display=\'none\'" loading="lazy">\n'

    features_html = ""
    if data["features"]:
        features_html += '<ul class="feature-list">'
        for f in data["features"]:
            features_html += f"<li>{f}</li>"
        features_html += "</ul>"

    general_features_html = ""
    if data["general_features"]:
        general_features_html += '<div class="amenities"><h3>Comodidades</h3><ul class="feature-list amenities-list">'
        for f in data["general_features"]:
            general_features_html += f"<li>{f}</li>"
        general_features_html += "</ul></div>"

    desc_html = ""
    if data["description"]:
        paragraphs = [p for p in data["description"].split("\n") if p.strip()]
        desc_html = "".join(f"<p>{p}</p>" for p in paragraphs)

    price_html = f'<div class="price">{data["price"]}</div>' if data["price"] else ""
    address_html = f'<div class="address">📍 {data["address"]}</div>' if data["address"] else ""
    type_html = f'<span class="badge">{data["prop_type"]}</span>' if data["prop_type"] else ""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{data['title'] or 'Propiedad'}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: 'Georgia', 'Times New Roman', serif;
      background: #F7F5F0;
      color: #1A1A1A;
      line-height: 1.7;
    }}

    .hero {{
      background: #1A1A2E;
      color: #F7F5F0;
      padding: 48px 40px 36px;
      border-bottom: 4px solid #C8A96A;
    }}

    .hero-inner {{
      max-width: 960px;
      margin: 0 auto;
    }}

    .badge {{
      display: inline-block;
      font-family: 'Arial', sans-serif;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      color: #C8A96A;
      border: 1px solid #C8A96A;
      padding: 4px 12px;
      margin-bottom: 18px;
    }}

    h1 {{
      font-size: clamp(1.6rem, 3vw, 2.4rem);
      font-weight: 400;
      line-height: 1.25;
      letter-spacing: -0.01em;
      margin-bottom: 16px;
      color: #F7F5F0;
    }}

    .address {{
      font-family: 'Arial', sans-serif;
      font-size: 14px;
      color: #A89B8A;
      margin-bottom: 20px;
    }}

    .price {{
      font-family: 'Arial', sans-serif;
      font-size: 2rem;
      font-weight: 700;
      color: #C8A96A;
      letter-spacing: -0.02em;
    }}

    .content {{
      max-width: 960px;
      margin: 0 auto;
      padding: 40px 40px 80px;
    }}

    /* Gallery */
    .gallery {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 8px;
      margin-bottom: 48px;
    }}

    .gallery img {{
      width: 100%;
      height: 220px;
      object-fit: cover;
      display: block;
      cursor: pointer;
      transition: opacity 0.2s;
    }}

    .gallery img:first-child {{
      grid-column: 1 / -1;
      height: 420px;
    }}

    .gallery img:hover {{ opacity: 0.88; }}

    /* Lightbox */
    .lightbox {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.92);
      z-index: 1000;
      align-items: center;
      justify-content: center;
    }}
    .lightbox.open {{ display: flex; }}
    .lightbox img {{
      max-width: 90vw;
      max-height: 90vh;
      object-fit: contain;
    }}
    .lightbox-close {{
      position: fixed;
      top: 20px; right: 28px;
      color: #fff;
      font-size: 36px;
      cursor: pointer;
      font-family: Arial, sans-serif;
      line-height: 1;
      opacity: 0.8;
    }}
    .lightbox-close:hover {{ opacity: 1; }}
    .lightbox-prev, .lightbox-next {{
      position: fixed;
      top: 50%; transform: translateY(-50%);
      color: #fff;
      font-size: 48px;
      cursor: pointer;
      font-family: Arial, sans-serif;
      opacity: 0.7;
      user-select: none;
      padding: 0 16px;
    }}
    .lightbox-prev {{ left: 8px; }}
    .lightbox-next {{ right: 8px; }}
    .lightbox-prev:hover, .lightbox-next:hover {{ opacity: 1; }}

    /* Sections */
    section {{ margin-bottom: 40px; }}

    h2 {{
      font-size: 1rem;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      font-family: 'Arial', sans-serif;
      color: #6B5B45;
      padding-bottom: 10px;
      border-bottom: 2px solid #E0D8CC;
      margin-bottom: 20px;
    }}

    h3 {{
      font-size: 0.85rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      font-family: 'Arial', sans-serif;
      color: #6B5B45;
      margin-bottom: 14px;
    }}

    .description p {{
      margin-bottom: 14px;
      font-size: 1.05rem;
      color: #2D2D2D;
    }}

    .feature-list {{
      list-style: none;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 8px 24px;
    }}

    .feature-list li {{
      font-family: 'Arial', sans-serif;
      font-size: 14px;
      color: #3A3A3A;
      padding: 8px 0;
      border-bottom: 1px solid #E8E2D8;
    }}

    .feature-list li::before {{
      content: '—';
      color: #C8A96A;
      margin-right: 8px;
    }}

    .amenities {{ margin-top: 24px; }}
    .amenities-list {{ grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); }}

    .disclaimer {{
      background: #EDE9E0;
      border-left: 3px solid #C8A96A;
      padding: 14px 18px;
      font-family: 'Arial', sans-serif;
      font-size: 13px;
      color: #6B5B45;
      margin-bottom: 40px;
      border-radius: 0 4px 4px 0;
    }}

    footer {{
      text-align: center;
      font-family: 'Arial', sans-serif;
      font-size: 12px;
      color: #A89B8A;
      padding: 24px;
      border-top: 1px solid #E0D8CC;
    }}
  </style>
</head>
<body>

<div class="hero">
  <div class="hero-inner">
    {type_html}
    <h1>{data['title'] or 'Propiedad en venta'}</h1>
    {address_html}
    {price_html}
  </div>
</div>

<div class="content">

  <div class="disclaimer">
    ℹ️ Esta ficha fue generada automáticamente desde ZonaProp. Los datos de contacto con la inmobiliaria no están incluidos intencionalmente.
  </div>

  {"<section class='gallery'>" + images_html + "</section>" if data['images'] else ""}

  {"<section><h2>Descripción</h2><div class='description'>" + desc_html + "</div></section>" if desc_html else ""}

  {"<section><h2>Características</h2>" + features_html + general_features_html + "</section>" if features_html or general_features_html else ""}

</div>

<footer>Generado desde ZonaProp — Ficha sin datos de contacto</footer>

<!-- Lightbox -->
<div class="lightbox" id="lightbox" onclick="closeLightbox(event)">
  <span class="lightbox-close" onclick="closeLB()">&times;</span>
  <span class="lightbox-prev" onclick="event.stopPropagation(); changeImg(-1)">&#8249;</span>
  <img id="lb-img" src="" alt="">
  <span class="lightbox-next" onclick="event.stopPropagation(); changeImg(1)">&#8250;</span>
</div>

<script>
  const imgs = [...document.querySelectorAll('.gallery img')];
  let cur = 0;
  imgs.forEach((img, i) => img.addEventListener('click', () => {{ cur = i; openLB(img.src); }}));
  function openLB(src) {{
    document.getElementById('lb-img').src = src;
    document.getElementById('lightbox').classList.add('open');
  }}
  function closeLB() {{ document.getElementById('lightbox').classList.remove('open'); }}
  function closeLightbox(e) {{ if (e.target.id === 'lightbox') closeLB(); }}
  function changeImg(dir) {{
    cur = (cur + dir + imgs.length) % imgs.length;
    document.getElementById('lb-img').src = imgs[cur].src;
  }}
  document.addEventListener('keydown', e => {{
    if (e.key === 'Escape') closeLB();
    if (e.key === 'ArrowLeft') changeImg(-1);
    if (e.key === 'ArrowRight') changeImg(1);
  }});
</script>

</body>
</html>"""


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/scrape", methods=["POST"])
def scrape():
    body = request.get_json()
    url = (body or {}).get("url", "").strip()

    if not url:
        return jsonify({"error": "Por favor ingresá una URL."}), 400

    if "zonaprop.com" not in url:
        return jsonify({"error": "Solo se aceptan links de ZonaProp."}), 400

    try:
        html = fetch_page(url)
        data = extract_property_data(html, url)

        if not data["title"] and not data["images"]:
            return jsonify({"error": "No se pudo extraer información de la propiedad. ZonaProp puede haber bloqueado la solicitud. Intentá de nuevo en unos segundos."}), 422

        result_html = generate_html(data)

        # Save to temp file
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8")
        tmp.write(result_html)
        tmp.close()

        return jsonify({
            "success": True,
            "title": data["title"],
            "address": data["address"],
            "price": data["price"],
            "images_count": len(data["images"]),
            "features_count": len(data["features"]) + len(data["general_features"]),
            "html_content": result_html,
            "tmp_path": tmp.name,
        })

    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else "?"
        if code == 403:
            return jsonify({"error": f"ZonaProp bloqueó la solicitud (403). Esperá unos segundos e intentá de nuevo."}), 503
        return jsonify({"error": f"Error HTTP {code} al acceder a ZonaProp."}), 502
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Sin conexión a internet o ZonaProp no responde."}), 503
    except Exception as e:
        return jsonify({"error": f"Error inesperado: {str(e)}"}), 500


@app.route("/download")
def download():
    path = request.args.get("path", "")
    if not path or not os.path.exists(path) or not path.endswith(".html"):
        return "Archivo no encontrado", 404
    return send_file(path, as_attachment=True, download_name="propiedad.html", mimetype="text/html")


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    print(f"\n✅ Servidor iniciado en puerto {port}\n")
    app.run(debug=False, host="0.0.0.0", port=port)
