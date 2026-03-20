from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
import re

app = Flask(__name__)
CORS(app)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    )
}

CTA_WORDS = [
    "call", "quote", "book", "contact", "enquire", "enquiry",
    "get started", "request", "schedule", "appointment"
]

def normalize_url(url):
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url

def get_domain(url):
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url

def fetch_once(url):
    start = time.time()
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=12,
        allow_redirects=True
    )
    elapsed = time.time() - start

    content_type = response.headers.get("Content-Type", "").lower()
    if "text/html" not in content_type:
        raise ValueError("URL did not return an HTML page")

    response.raise_for_status()
    return response, elapsed

def safe_request(url):
    errors = []

    try:
        return fetch_once(url)
    except Exception as e:
        errors.append(f"{url} -> {type(e).__name__}: {e}")

    if url.startswith("https://"):
        fallback_url = "http://" + url[len("https://"):]
        try:
            return fetch_once(fallback_url)
        except Exception as e:
            errors.append(f"{fallback_url} -> {type(e).__name__}: {e}")

    raise RuntimeError(" | ".join(errors))

def extract_page_data(html):
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    meta_description_tag = soup.find(
        "meta",
        attrs={"name": re.compile(r"^description$", re.I)}
    )
    meta_description = (
        meta_description_tag.get("content", "").strip()
        if meta_description_tag else ""
    )

    viewport_tag = soup.find(
        "meta",
        attrs={"name": re.compile(r"^viewport$", re.I)}
    )

    h1_tag = soup.find("h1")
    h1_text = h1_tag.get_text(" ", strip=True) if h1_tag else ""

    body_text = soup.get_text(" ", strip=True).lower()
    images = soup.find_all("img")
    buttons_and_links = soup.find_all(["a", "button"])

    cta_matches = []
    for element in buttons_and_links:
        text = element.get_text(" ", strip=True).lower()
        if text and any(word in text for word in CTA_WORDS):
            cta_matches.append(text)

    return {
        "title": title,
        "meta_description": meta_description,
        "has_viewport": viewport_tag is not None,
        "has_h1": bool(h1_text),
        "h1_text": h1_text,
        "image_count": len(images),
        "cta_matches": cta_matches,
        "text_length": len(body_text)
    }

def score_website(url, response_time, page_data, html_size):
    score = 50
    issues = []
    priorities = []

    if url.startswith("https://"):
        score += 10
    else:
        issues.append("Website is not using HTTPS")
        priorities.append("Secure the site with HTTPS")

    if page_data["title"] and len(page_data["title"]) >= 10:
        score += 10
    else:
        issues.append("Weak or missing page title")
        priorities.append("Improve the page title for clarity and trust")

    if page_data["meta_description"] and len(page_data["meta_description"]) >= 50:
        score += 10
    else:
        issues.append("Missing or weak meta description")
        priorities.append("Add a stronger meta description")

    if page_data["has_viewport"]:
        score += 10
    else:
        issues.append("Missing mobile viewport tag")
        priorities.append("Improve mobile compatibility")

    if page_data["has_h1"]:
        score += 10
    else:
        issues.append("Missing clear main heading")
        priorities.append("Add a strong homepage headline")

    if len(page_data["cta_matches"]) > 0:
        score += 10
    else:
        issues.append("Weak or missing call-to-action")
        priorities.append("Add stronger CTA buttons and links")

    if response_time < 1.5:
        score += 10
    elif response_time < 3:
        score += 5
    else:
        issues.append("Slow response time")
        priorities.append("Improve page speed")

    if html_size > 800000:
        score -= 8
        issues.append("Page appears heavy in size")
        priorities.append("Reduce heavy assets and improve load speed")

    if page_data["image_count"] == 0:
        issues.append("Very limited visual content")
        priorities.append("Add stronger visual hierarchy")

    if page_data["text_length"] < 400:
        issues.append("Low content depth or weak messaging")
        priorities.append("Improve service explanation and trust signals")

    score = max(45, min(95, score))

    if score >= 75:
        lost_customers = "4–8 per month"
        extra_clients = "2–4 extra clients/month"
        summary = "Your website has a decent base, but it could guide visitors more clearly toward calling, booking, or enquiring."
        business_impact = [
            "Some visitors may hesitate before contacting you",
            "Your call-to-action could be stronger",
            "There are likely easy conversion wins available"
        ]
    elif score >= 60:
        lost_customers = "8–14 per month"
        extra_clients = "3–6 extra clients/month"
        summary = "Your homepage likely has noticeable conversion friction that could reduce calls, bookings, and enquiries."
        business_impact = [
            "Visitors may leave before taking action",
            "Mobile users may not see the next step clearly",
            "The page likely feels functional but not conversion-focused"
        ]
    else:
        lost_customers = "12–18 per month"
        extra_clients = "4–9 extra clients/month"
        summary = "Your homepage likely has avoidable friction and may be losing enquiries before visitors ever take the next step."
        business_impact = [
            "Visitors may leave early due to weak clarity",
            "Trust may feel lower on first impression",
            "The page likely needs a stronger action path"
        ]

    if len(priorities) < 3:
        fallback_priorities = [
            "Clarify the first screen message",
            "Strengthen the main call-to-action",
            "Improve mobile readability",
        ]
        for item in fallback_priorities:
            if item not in priorities:
                priorities.append(item)
            if len(priorities) == 3:
                break

    return {
        "score": score,
        "issues": issues[:4],
        "priorities": priorities[:3],
        "summary": summary,
        "lost_customers": lost_customers,
        "extra_clients": extra_clients,
        "business_impact": business_impact,
        "domain": get_domain(url),
        "response_time_ms": round(response_time * 1000),
        "html_size_kb": round(html_size / 1024),
        "cta_found": len(page_data["cta_matches"]) > 0
    }

@app.route("/scan", methods=["POST"])
def scan():
    try:
        data = request.get_json(silent=True) or {}
        raw_url = data.get("url", "").strip()

        if not raw_url:
            return jsonify({
                "success": False,
                "error": "Missing URL"
            }), 400

        url = normalize_url(raw_url)
        response, response_time = safe_request(url)

        final_url = response.url
        html = response.text
        html_size = len(response.content)

        page_data = extract_page_data(html)
        result = score_website(final_url, response_time, page_data, html_size)

        return jsonify({
            "success": True,
            "url": final_url,
            "result": result
        })

    except requests.exceptions.Timeout as e:
        return jsonify({
            "success": False,
            "error": f"Timeout: {str(e)}"
        }), 504

    except requests.exceptions.ConnectionError as e:
        return jsonify({
            "success": False,
            "error": f"Connection error: {str(e)}"
        }), 502

    except requests.exceptions.HTTPError as e:
        return jsonify({
            "success": False,
            "error": f"Website returned an HTTP error: {e.response.status_code}"
        }), 502

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Scanner failed: {str(e)}"
        }), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "ok": True,
        "message": "ForgeLocal scanner is running"
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True)
