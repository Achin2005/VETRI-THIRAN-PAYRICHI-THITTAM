"""All AI logic: prompts, Gemini calls, JSON parsing, shopping links."""
import os, re, json, urllib.parse
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not KEY:
    raise ValueError("Set GEMINI_API_KEY in your .env file")
genai.configure(api_key=KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

STORES = {
    "amazon": "https://www.amazon.in/s?k={}",
    "flipkart": "https://www.flipkart.com/search?q={}",
    "ikea": "https://www.ikea.com/in/en/search/?q={}",
    "meesho": "https://www.meesho.com/search?q={}",
    "swiggy": "https://www.swiggy.com/search?query={}",
    "zomato": "https://www.zomato.com/search?q={}",
    "bookmyshow": "https://in.bookmyshow.com/search?q={}",
    "oyo": "https://www.oyorooms.com/search/?location={}",
    "google": "https://www.google.com/search?q={}",
    "bluestone": "https://www.bluestone.com/search.html?query={}",
    "tanishq": "https://www.tanishq.co.in/search?q={}",
    "caratlane": "https://www.caratlane.com/search?q={}",
}
PARTY_STORES = {
    "venue": ["oyo", "google"], "catering": ["swiggy", "zomato"],
    "decoration": ["amazon", "flipkart", "meesho"],
    "entertainment": ["bookmyshow", "amazon"],
}
SCHEMA = """Reply with ONLY valid JSON, no markdown:
{"total_budget": 0, "remaining_budget": 0,
 "sections": [{"title": "", "allocation": 0,
   "items": [{"name": "", "description": "", "price": 0, "quantity": 1, "search_terms": ""}]}],
 "tips": ["", ""]}
All prices are in Indian Rupees (INR). Total of all item prices x quantity must NOT exceed the budget."""


def links(term, stores):
    q = urllib.parse.quote_plus(term)
    return {s: STORES[s].format(q) for s in stores}


def ask(prompt, img=None):
    resp = model.generate_content([prompt, img] if img else prompt)
    m = re.search(r"\{.*\}", resp.text, re.S)
    return json.loads(m.group(0))


def finish(data, pick):
    for sec in data.get("sections", []):
        for it in sec.get("items", []):
            it["links"] = links(it.get("search_terms") or it.get("name", ""), pick(sec))
    return data


def safe(fn, inp, *a):
    try:
        return fn(inp, *a)
    except Exception as e:  # fallback so the UI never crashes
        return {"error": f"Could not generate a plan ({e}). Check your API key / internet and try again."}


def _home(i):
    p = f"""You are a home interior budget planner for India. Budget: ₹{i['total_budget']}.
Needs: {i['lights']} lights, {i['fans']} ceiling fans, {i['furniture']} furniture pieces, {i['tables']} dining tables.
Rooms: {', '.join(i['rooms']) or 'any'}. Extra notes: {i['notes'] or 'none'}.
Use sections like Lighting, Ceiling fans, Furniture. Suggest Indian-market products/brands. {SCHEMA}"""
    return finish(ask(p), lambda s: ["amazon", "flipkart", "ikea"])


def _party(i):
    p = f"""You are a party budget planner for India. Budget: ₹{i['total_budget']}, {i['guests']} guests,
event: {i['party_type']}, venue: {i['venue']}. Needs: {', '.join(i['needs']) or 'all'}. Notes: {i['notes'] or 'none'}.
Split the budget across sections named exactly from: Venue, Catering, Decoration, Entertainment (only the needed ones)
plus a small Contingency. {SCHEMA}"""
    return finish(ask(p), lambda s: PARTY_STORES.get(s["title"].lower(), ["amazon", "flipkart", "google"]))


def _jewelry(i, path=None):
    p = f"""You are a jewelry stylist for India. Budget: ₹{i['total_budget']}. Occasion: {i['occasion']}.
Style preferences: {i['preferences'] or 'none'}.
{'An outfit photo is attached: match colors and style.' if path else ''}
Use one section titled "Jewelry picks". {SCHEMA}
Also add a top-level key "outfit": short description of outfit colors/style (empty string if no photo)."""
    img = Image.open(path) if path else None
    return finish(ask(p, img), lambda s: ["amazon", "flipkart", "bluestone", "tanishq", "caratlane"])


def home(i): return safe(_home, i)
def party(i): return safe(_party, i)
def jewelry(i, path=None): return safe(_jewelry, i, path)
