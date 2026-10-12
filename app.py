"""
app.py — Wanderlust AI Travel Planner
Premium Production-Grade UI
Run: streamlit run app.py
"""

from pathlib import Path
import re
import tomllib
from datetime import date, datetime, timedelta

import requests
import streamlit as st
from icalendar import Calendar, Event
from agno.agent import Agent
from agno.models.groq import Groq


# ═══════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Wanderlust — AI Travel Planner",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ═══════════════════════════════════════════════════════════════════
#  LOAD SECRETS
# ═══════════════════════════════════════════════════════════════════

SECRETS_FILE = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"

if not SECRETS_FILE.is_file():
    st.error("Configuration file not found. Create `.streamlit/secrets.toml`.")
    st.stop()

try:
    with SECRETS_FILE.open("rb") as file:
        secrets = tomllib.load(file)

    GROQ_API_KEY = str(secrets.get("GROQ_API_KEY", "")).strip()
    TAVILY_API_KEY = str(secrets.get("TAVILY_API_KEY", "")).strip()
    AVIATIONSTACK_API_KEY = str(secrets.get("AVIATIONSTACK_API_KEY", "")).strip()
    GROQ_MODEL = str(secrets.get("GROQ_MODEL", "openai/gpt-oss-20b")).strip()

except Exception as exc:
    st.error(f"Unable to read secrets.toml: {exc}")
    st.stop()

if not GROQ_API_KEY or not TAVILY_API_KEY:
    st.error("GROQ_API_KEY and TAVILY_API_KEY are required in secrets.toml.")
    st.stop()


# ═══════════════════════════════════════════════════════════════════
#  BACKEND
# ═══════════════════════════════════════════════════════════════════

def search_travel_info(query: str) -> str:
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 5,
                "include_answer": True,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.Timeout:
        raise RuntimeError("Tavily search timed out.")
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        raise RuntimeError(f"Tavily API failed (HTTP {code}).")
    except requests.exceptions.RequestException:
        raise RuntimeError("Could not connect to Tavily.")

    if data.get("error"):
        raise RuntimeError(f"Tavily error: {data['error']}")

    output = []
    if data.get("answer"):
        output.append(f"Summary: {data['answer']}")
    for item in data.get("results", []):
        output.append(
            f"Title: {item.get('title', '')}\n"
            f"URL: {item.get('url', '')}\n"
            f"Content: {item.get('content', '')}"
        )
    return "\n\n".join(output) or "No results."


def search_flights(airport_code: str) -> str:
    if not AVIATIONSTACK_API_KEY or not airport_code:
        return "Flight search not requested."
    try:
        response = requests.get(
            "https://api.aviationstack.com/v1/flights",
            params={
                "access_key": AVIATIONSTACK_API_KEY,
                "arr_iata": airport_code.strip().upper(),
                "limit": 5,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException:
        return "Flight info unavailable."

    if data.get("error"):
        return "Flight API error."
    flights = data.get("data", [])
    if not flights:
        return "No flights returned."

    results = []
    for f in flights:
        airline = (f.get("airline") or {}).get("name", "Unknown")
        number = (f.get("flight") or {}).get("iata", "N/A")
        dep = f.get("departure") or {}
        arr = f.get("arrival") or {}
        results.append(
            f"Airline: {airline}\n"
            f"Flight: {number}\n"
            f"Departure: {dep.get('airport', '?')} @ {dep.get('scheduled', '?')}\n"
            f"Arrival: {arr.get('airport', '?')} @ {arr.get('scheduled', '?')}"
        )
    return "\n\n".join(results)


def generate_itinerary(destination, start_date, num_days, num_travelers, budget, preferences, airport_code):
    web_info = search_travel_info(
        f"Travel guide for {destination}: attractions, restaurants, "
        "accommodation, local transport, safety tips"
    )
    flight_info = search_flights(airport_code)

    agent = Agent(
        name="AI Travel Planner",
        model=Groq(id=GROQ_MODEL, api_key=GROQ_API_KEY),
        instructions=[
            "You are a professional travel planning assistant.",
            "Create a practical day-by-day travel itinerary.",
            "Use the supplied web search results.",
            "Never invent live prices, availability, routes, distances.",
            "Clearly label estimates.",
            "Respect the user's budget and preferences.",
            "Use clear English with Markdown.",
        ],
        markdown=True,
    )

    prompt = f"""
Create a detailed, practical travel itinerary.

TRIP DETAILS
Destination: {destination}
Start date: {start_date}
Duration: {num_days} days
Travelers: {num_travelers} people
Total budget: ${budget} USD
Arrival airport: {airport_code or "Not provided"}
Preferences: {preferences}

WEB SEARCH
{web_info}

FLIGHTS
{flight_info}

REQUIREMENTS
1. Short trip overview
2. Accommodation options
3. Local transport
4. Day-by-day plan (label as "Day N:")
5. Restaurants & food
6. Major attractions + hidden gems
7. Budget breakdown
8. Travel tips & safety
9. Clean Markdown with headings
"""
    try:
        result = agent.run(prompt)
    except Exception as exc:
        error_text = str(exc)
        if "model_not_found" in error_text.lower():
            raise RuntimeError(f"Model '{GROQ_MODEL}' unavailable.")
        if "401" in error_text or "authentication" in error_text.lower():
            raise RuntimeError("Groq auth failed.")
        if "429" in error_text or "rate_limit" in error_text.lower():
            raise RuntimeError("Rate limit reached.")
        raise RuntimeError(f"Groq error: {error_text}")

    content = getattr(result, "content", None)
    if not content:
        raise RuntimeError("Empty itinerary.")
    return str(content)


def create_calendar(itinerary: str, start_date: date) -> bytes:
    calendar = Calendar()
    calendar.add("prodid", "-//Wanderlust//")
    calendar.add("version", "2.0")

    days = re.findall(
        r"Day\s+(\d+)[:\s]+(.*?)(?=Day\s+\d+|$)",
        itinerary,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not days:
        days = [("1", itinerary)]

    for number, content in days:
        trip_day = start_date + timedelta(days=int(number) - 1)
        event = Event()
        event.add("summary", f"Day {number} — Itinerary")
        event.add("description", content.strip())
        event.add("dtstart", trip_day)
        event.add("dtend", trip_day + timedelta(days=1))
        event.add("dtstamp", datetime.now())
        calendar.add_component(event)

    return calendar.to_ical()


# ═══════════════════════════════════════════════════════════════════
#  PREMIUM CSS
# ═══════════════════════════════════════════════════════════════════

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Space+Grotesk:wght@400;500;600;700&display=swap');

/* ═══════════ RESET & GLOBAL ═══════════ */
*, *::before, *::after { box-sizing: border-box; }

html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
[data-testid="stToolbar"],
.main, .block-container,
section.main > div {
    background: #06080f !important;
    font-family: 'Inter', sans-serif !important;
    color: #e2e8f0 !important;
}

header[data-testid="stHeader"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
#MainMenu, footer { visibility: hidden !important; }

.block-container {
    padding: 2rem 3rem 4rem !important;
    max-width: 1500px !important;
}

/* ═══════════ ANIMATED AURORA BACKGROUND ═══════════ */
.stApp::before {
    content: '';
    position: fixed;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background:
        radial-gradient(circle at 20% 30%, rgba(59,130,246,0.12) 0%, transparent 40%),
        radial-gradient(circle at 80% 70%, rgba(168,85,247,0.10) 0%, transparent 40%),
        radial-gradient(circle at 50% 50%, rgba(16,185,129,0.06) 0%, transparent 50%);
    animation: aurora 20s ease-in-out infinite;
    z-index: 0;
    pointer-events: none;
}
@keyframes aurora {
    0%, 100% { transform: translate(0, 0) rotate(0deg); }
    33% { transform: translate(3%, -3%) rotate(3deg); }
    66% { transform: translate(-3%, 3%) rotate(-3deg); }
}

.stApp > * { position: relative; z-index: 1; }

/* ═══════════ SIDEBAR ═══════════ */
section[data-testid="stSidebar"] {
    display: block !important;
    visibility: visible !important;
    transform: translateX(0) !important;
    min-width: 300px !important;
    width: 300px !important;
    left: 0 !important;
    margin-left: 0 !important;
    background: linear-gradient(180deg, #06080f 0%, #0a1020 100%) !important;
    border-right: 1px solid rgba(59,130,246,0.12) !important;
}
section[data-testid="stSidebar"] > div:first-child {
    padding: 1.75rem 1.5rem 3rem 1.5rem !important;
    background: transparent !important;
    overflow-y: auto !important;
    height: 100vh !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"],
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
    background: transparent !important;
    padding: 0 0 2rem 0 !important;
    overflow: visible !important;
}
button[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"] {
    display: none !important;
}

/* ═══════════ BRAND ═══════════ */
.brand {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0 0.25rem 1.5rem;
    border-bottom: 1px solid rgba(59,130,246,0.1);
    margin-bottom: 1.5rem;
}
.brand-logo {
    width: 42px; height: 42px;
    background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 50%, #ec4899 100%);
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.3rem;
    box-shadow: 0 8px 24px rgba(99,102,241,0.45), inset 0 1px 0 rgba(255,255,255,0.2);
    flex-shrink: 0;
}
.brand-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.3rem;
    font-weight: 700;
    background: linear-gradient(135deg, #ffffff 0%, #94a3b8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.02em;
    line-height: 1;
    margin-bottom: 0.2rem;
}
.brand-tag {
    font-size: 0.68rem;
    color: #64748b;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-weight: 500;
}

/* ═══════════ SIDEBAR SECTIONS ═══════════ */
.sb-section {
    font-size: 0.66rem;
    font-weight: 700;
    color: #475569;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin: 1.5rem 0 0.75rem;
    padding-left: 0.25rem;
}
.sb-chip {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    background: linear-gradient(135deg, rgba(13,20,32,0.9) 0%, rgba(10,16,32,0.9) 100%);
    border: 1px solid rgba(59,130,246,0.08);
    border-radius: 10px;
    padding: 0.6rem 0.85rem;
    margin-bottom: 0.4rem;
    font-size: 0.82rem;
    color: #94a3b8;
    transition: all 0.2s;
}
.sb-chip:hover {
    border-color: rgba(59,130,246,0.3);
    background: linear-gradient(135deg, rgba(20,30,50,0.9) 0%, rgba(15,25,45,0.9) 100%);
    color: #cbd5e1;
    transform: translateX(2px);
}
.sb-dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 10px #10b981, 0 0 4px #10b981;
    flex-shrink: 0;
}

/* ═══════════ HERO — FULLY COVERED ═══════════ */
.hero {
    position: relative;
    border-radius: 24px;
    overflow: hidden;
    margin-bottom: 3rem;
    height: 500px;
    width: 100% !important;
    max-width: 100% !important;
    display: block !important;
    border: 1px solid rgba(59,130,246,0.15);
    box-shadow: 0 30px 60px -20px rgba(0,0,0,0.8);
    background: #0a0f1a;
    isolation: isolate;
}

.hero-bg {
    position: absolute !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    width: 100% !important;
    height: 100% !important;
    max-width: none !important;
    max-height: none !important;
    object-fit: cover !important;
    object-position: center center !important;
    filter: brightness(0.42) saturate(1.15);
    display: block !important;
    margin: 0 !important;
    padding: 0 !important;
}

.hero-overlay {
    position: absolute;
    inset: 0;
    background:
        linear-gradient(135deg, rgba(6,8,15,0.88) 0%, rgba(6,8,15,0.35) 50%, rgba(6,8,15,0.88) 100%),
        radial-gradient(circle at 30% 20%, rgba(59,130,246,0.28) 0%, transparent 55%),
        radial-gradient(circle at 70% 80%, rgba(168,85,247,0.22) 0%, transparent 55%);
    z-index: 1;
}

.hero-content {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 2;
    text-align: center;
    padding: 3rem 2rem;
    width: 100%;
    max-width: 900px;
}

.hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: rgba(59,130,246,0.1);
    border: 1px solid rgba(59,130,246,0.35);
    color: #60a5fa !important;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    padding: 0.5rem 1.15rem;
    border-radius: 30px;
    margin-bottom: 1.5rem;
    backdrop-filter: blur(10px);
    box-shadow: 0 0 30px rgba(59,130,246,0.2);
}

.hero-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 4rem;
    font-weight: 700;
    line-height: 1.05;
    margin: 0 0 1rem;
    letter-spacing: -0.04em;
    color: #ffffff;
}

.hero-title .gradient {
    background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 50%, #f472b6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.hero-sub {
    color: #94a3b8;
    font-size: 1.1rem;
    max-width: 620px;
    margin: 0 auto;
    line-height: 1.65;
}

/* ═══════════ SECTION ═══════════ */
.sec {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin: 2.5rem 0 1.5rem;
}
.sec-num {
    width: 38px; height: 38px;
    background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
    color: #fff;
    border-radius: 11px;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.9rem;
    font-weight: 800;
    box-shadow: 0 8px 20px rgba(99,102,241,0.4);
    flex-shrink: 0;
}
.sec-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.4rem;
    font-weight: 700;
    color: #f1f5f9;
    letter-spacing: -0.02em;
    line-height: 1;
}
.sec-sub {
    font-size: 0.85rem;
    color: #64748b;
    margin-top: 0.25rem;
}

/* ═══════════ DESTINATION STRIP ═══════════ */
.dest-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 0.85rem;
    margin-bottom: 2rem;
}
.dest-card {
    position: relative;
    height: 120px;
    border-radius: 14px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
    border: 1px solid rgba(59,130,246,0.1);
}
.dest-card:hover {
    transform: translateY(-6px) scale(1.02);
    border-color: rgba(59,130,246,0.5);
    box-shadow: 0 20px 40px -10px rgba(59,130,246,0.4);
}
.dest-card img {
    width: 100%; height: 100%;
    object-fit: cover;
    filter: brightness(0.5);
    transition: filter 0.3s;
}
.dest-card:hover img { filter: brightness(0.7); }
.dest-label {
    position: absolute;
    bottom: 10px; left: 0; right: 0;
    text-align: center;
    color: #fff;
    font-size: 0.82rem;
    font-weight: 600;
    text-shadow: 0 2px 6px rgba(0,0,0,0.8);
}

/* ═══════════ FORM INPUTS ═══════════ */
.stTextInput input,
.stTextArea textarea,
.stNumberInput input,
.stDateInput input {
    background: rgba(13,20,32,0.85) !important;
    border: 1px solid rgba(59,130,246,0.15) !important;
    border-radius: 12px !important;
    color: #e2e8f0 !important;
    font-size: 0.94rem !important;
    padding: 0.75rem 1rem !important;
    transition: all 0.2s !important;
}
.stTextInput input:focus,
.stTextArea textarea:focus,
.stNumberInput input:focus,
.stDateInput input:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.18) !important;
    background: rgba(13,20,32,1) !important;
}
.stTextInput input::placeholder,
.stTextArea textarea::placeholder {
    color: #475569 !important;
}
.stTextArea textarea { min-height: 110px !important; }

/* ═══════════ LABELS ═══════════ */
.stTextInput label,
.stTextArea label,
.stNumberInput label,
.stDateInput label {
    color: #94a3b8 !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    margin-bottom: 0.5rem !important;
}

/* ═══════════ BUTTONS — GLOWING NEON ═══════════ */
div[data-testid="stFormSubmitButton"] > button,
div[data-testid="stButton"] > button {
    background: linear-gradient(135deg, #3b82f6 0%, #6366f1 50%, #8b5cf6 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 14px !important;
    padding: 1rem 2.5rem !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.02em !important;
    width: 100% !important;
    box-shadow:
        0 10px 30px rgba(99,102,241,0.45),
        0 0 40px rgba(139,92,246,0.25) !important;
    transition: all 0.25s cubic-bezier(0.4,0,0.2,1) !important;
    position: relative;
    overflow: hidden;
}
div[data-testid="stFormSubmitButton"] > button:hover,
div[data-testid="stButton"] > button:hover {
    transform: translateY(-2px) scale(1.005) !important;
    box-shadow:
        0 15px 40px rgba(99,102,241,0.6),
        0 0 60px rgba(139,92,246,0.4) !important;
    background: linear-gradient(135deg, #4f8eff 0%, #7c74f7 50%, #a17af8 100%) !important;
}
div[data-testid="stFormSubmitButton"] > button:active,
div[data-testid="stButton"] > button:active {
    transform: translateY(0) scale(1) !important;
}

/* ═══════════ METRIC CARDS ═══════════ */
.metrics {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.25rem;
    margin: 1.75rem 0;
}
.m-card {
    background: linear-gradient(135deg, rgba(13,20,32,0.9) 0%, rgba(10,16,32,0.9) 100%);
    border: 1px solid rgba(59,130,246,0.12);
    border-radius: 16px;
    padding: 1.5rem;
    position: relative;
    overflow: hidden;
    transition: all 0.3s;
}
.m-card:hover {
    border-color: rgba(59,130,246,0.35);
    transform: translateY(-2px);
    box-shadow: 0 15px 35px -10px rgba(59,130,246,0.3);
}
.m-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 3px; height: 100%;
    background: linear-gradient(180deg, #3b82f6 0%, #8b5cf6 50%, #ec4899 100%);
}
.m-label {
    font-size: 0.68rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 700;
    margin-bottom: 0.5rem;
}
.m-value {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.5rem;
    font-weight: 700;
    color: #f1f5f9;
    letter-spacing: -0.02em;
    line-height: 1.1;
}
.m-value.green {
    color: #10b981;
    text-shadow: 0 0 20px rgba(16,185,129,0.5);
}

/* ═══════════ RESULT CARD ═══════════ */
.result-card {
    background: linear-gradient(135deg, rgba(13,20,32,0.95) 0%, rgba(10,16,32,0.95) 100%);
    border: 1px solid rgba(59,130,246,0.15);
    border-radius: 20px;
    padding: 2.5rem;
    color: #cbd5e1;
    line-height: 1.85;
    font-size: 0.95rem;
    position: relative;
    overflow: hidden;
}
.result-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 4px; height: 100%;
    background: linear-gradient(180deg, #3b82f6 0%, #8b5cf6 50%, #ec4899 100%);
}
.result-card h1 {
    font-family: 'Space Grotesk', sans-serif;
    color: #f1f5f9 !important;
    font-size: 1.6rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin: 2rem 0 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid rgba(59,130,246,0.15);
}
.result-card h2 {
    font-family: 'Space Grotesk', sans-serif;
    color: #f1f5f9 !important;
    font-size: 1.3rem;
    font-weight: 700;
    margin: 1.75rem 0 0.75rem;
    letter-spacing: -0.01em;
}
.result-card h3 {
    color: #60a5fa !important;
    font-size: 1.05rem;
    font-weight: 600;
    margin: 1.25rem 0 0.5rem;
}
.result-card p, .result-card li { color: #cbd5e1 !important; }
.result-card strong { color: #f1f5f9 !important; font-weight: 700; }
.result-card ul, .result-card ol { padding-left: 1.5rem; }
.result-card code {
    background: rgba(59,130,246,0.15) !important;
    color: #93c5fd !important;
    padding: 0.15em 0.45em;
    border-radius: 5px;
    font-size: 0.88em;
}
.result-card table {
    border-collapse: collapse;
    width: 100%;
    margin: 1.25rem 0;
    border-radius: 10px;
    overflow: hidden;
}
.result-card th {
    background: rgba(59,130,246,0.1);
    color: #93c5fd;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 0.75rem 1rem;
    text-align: left;
    border-bottom: 1px solid rgba(59,130,246,0.2);
}
.result-card td {
    padding: 0.75rem 1rem;
    color: #cbd5e1;
    border-bottom: 1px solid rgba(59,130,246,0.06);
}
.result-card hr {
    border: none;
    border-top: 1px solid rgba(59,130,246,0.15);
    margin: 2rem 0;
}

/* ═══════════ DOWNLOAD BUTTON ═══════════ */
div[data-testid="stDownloadButton"] > button {
    background: rgba(13,20,32,0.9) !important;
    color: #e2e8f0 !important;
    border: 1px solid rgba(59,130,246,0.25) !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    padding: 0.75rem 1.5rem !important;
    transition: all 0.2s !important;
}
div[data-testid="stDownloadButton"] > button:hover {
    border-color: #3b82f6 !important;
    background: rgba(20,30,50,0.9) !important;
    color: #60a5fa !important;
    transform: translateY(-1px);
}

/* ═══════════ ALERTS ═══════════ */
.stAlert {
    background: rgba(13,20,32,0.9) !important;
    border: 1px solid rgba(59,130,246,0.2) !important;
    border-radius: 12px !important;
}
.stAlert p, .stAlert div { color: #cbd5e1 !important; }

/* ═══════════ STATUS WIDGET ═══════════ */
[data-testid="stStatusWidget"] {
    background: rgba(13,20,32,0.9) !important;
    border: 1px solid rgba(59,130,246,0.2) !important;
    border-radius: 14px !important;
}
[data-testid="stStatusWidget"] * { color: #e2e8f0 !important; }

/* ═══════════ SPINNER ═══════════ */
.stSpinner > div { border-top-color: #3b82f6 !important; }

/* ═══════════ DIVIDER ═══════════ */
hr {
    border-color: rgba(59,130,246,0.12) !important;
    margin: 2.5rem 0 !important;
}

/* ═══════════ LINKS ═══════════ */
a, a:visited {
    color: #60a5fa !important;
    text-decoration: none;
}
a:hover { color: #93c5fd !important; }

/* ═══════════ NUMBER INPUT BUTTONS ═══════════ */
button[data-testid="stNumberInputStepUp"],
button[data-testid="stNumberInputStepDown"] {
    background: rgba(30,41,59,0.9) !important;
    color: #e2e8f0 !important;
    border-color: rgba(59,130,246,0.2) !important;
}
button[data-testid="stNumberInputStepUp"]:hover,
button[data-testid="stNumberInputStepDown"]:hover {
    background: rgba(51,65,85,0.9) !important;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
    <div class="brand">
        <div class="brand-logo">✈️</div>
        <div>
            <div class="brand-name">Wanderlust</div>
            <div class="brand-tag">AI Travel Planner</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.text_input(
        "User ID",
        value="user_Afzal",
        help="Session ID — keeps your travel history",
    )

    st.markdown('<div class="sb-section">Powered By</div>', unsafe_allow_html=True)
    for tech in [
        f"Groq · {GROQ_MODEL}",
        "Tavily Web Search",
        "AviationStack",
        "Agno Agent",
    ]:
        st.markdown(
            f'<div class="sb-chip"><span class="sb-dot"></span>{tech}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="sb-section">Pipeline</div>', unsafe_allow_html=True)
    for i, step in enumerate(
        ["Web Search", "Flight Lookup", "AI Itinerary", "Calendar Export"], 1
    ):
        st.markdown(
            f'<div class="sb-chip"><span class="sb-dot"></span>{i}. {step}</div>',
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════
#  HERO
# ═══════════════════════════════════════════════════════════════════

st.markdown("""
<div class="hero">
    <img class="hero-bg"
         src="https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=1920&q=90"
         alt="travel"/>
    <div class="hero-overlay"></div>
    <div class="hero-content">
        <div class="hero-badge">✦ AI-Powered Travel Planning</div>
        <div class="hero-title">Plan your next<br/><span class="gradient">journey</span></div>
        <div class="hero-sub">Personalized day-by-day itineraries powered by live web search and advanced AI — with calendar export.</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
#  DESTINATION STRIP
# ═══════════════════════════════════════════════════════════════════

st.markdown("""
<div class="dest-grid">
    <div class="dest-card">
        <img src="https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=400&q=70" />
        <div class="dest-label">🇯🇵 Tokyo</div>
    </div>
    <div class="dest-card">
        <img src="https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=400&q=70" />
        <div class="dest-label">🇫🇷 Paris</div>
    </div>
    <div class="dest-card">
        <img src="https://images.unsplash.com/photo-1508009603885-50cf7c579365?w=400&q=70" />
        <div class="dest-label">🇹🇭 Bangkok</div>
    </div>
    <div class="dest-card">
        <img src="https://images.unsplash.com/photo-1552832230-c0197dd311b5?w=400&q=70" />
        <div class="dest-label">🇮🇹 Rome</div>
    </div>
    <div class="dest-card">
        <img src="https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=400&q=70" />
        <div class="dest-label">🇦🇪 Dubai</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
#  INPUT FORM
# ═══════════════════════════════════════════════════════════════════

st.markdown("""
<div class="sec">
    <div class="sec-num">1</div>
    <div>
        <div class="sec-title">Trip Details</div>
        <div class="sec-sub">Tell us about your journey</div>
    </div>
</div>
""", unsafe_allow_html=True)

with st.form("travel_form"):

    destination = st.text_input(
        "Destination",
        placeholder="Where do you want to go? e.g. Goa, Paris, Tokyo",
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date.today(),
            min_value=date.today(),
        )

    with col2:
        num_days = st.number_input(
            "Duration (days)",
            min_value=1, max_value=30, value=5,
        )

    with col3:
        num_travelers = st.number_input(
            "Travelers",
            min_value=1, max_value=20, value=2,
        )

    with col4:
        budget = st.number_input(
            "Budget (USD)",
            min_value=100, max_value=100000, value=1500, step=100,
        )

    airport_code = st.text_input(
        "Arrival Airport (optional)",
        placeholder="e.g. BOM, DEL, GOI",
    )

    preferences = st.text_area(
        "Travel Preferences",
        placeholder=(
            "Describe your ideal trip — interests, pace, must-sees, "
            "food preferences, who's traveling, etc."
        ),
        height=110,
    )

    submitted = st.form_submit_button(
        "✦ Generate Itinerary",
        use_container_width=True,
    )


# ═══════════════════════════════════════════════════════════════════
#  HANDLE SUBMISSION
# ═══════════════════════════════════════════════════════════════════

if submitted:
    if not destination.strip():
        st.warning("Please enter a destination.")
    else:
        with st.status("✦ Generating your itinerary...", expanded=True) as status:
            st.write("🔍 Searching the web for travel info...")
            try:
                itinerary = generate_itinerary(
                    destination=destination.strip(),
                    start_date=start_date,
                    num_days=int(num_days),
                    num_travelers=int(num_travelers),
                    budget=int(budget),
                    preferences=preferences.strip() or "General sightseeing",
                    airport_code=airport_code.strip(),
                )
                st.write("✅ Itinerary generated!")
                st.session_state["itinerary"] = itinerary
                st.session_state["trip_date"] = start_date
                st.session_state["destination"] = destination.strip()
                status.update(label="✅ Complete", state="complete", expanded=False)
            except Exception as exc:
                status.update(label="❌ Failed", state="error", expanded=True)
                st.error(f"Unable to generate itinerary: {exc}")


# ═══════════════════════════════════════════════════════════════════
#  DISPLAY RESULT
# ═══════════════════════════════════════════════════════════════════

if st.session_state.get("itinerary"):

    st.markdown("""
    <div class="sec">
        <div class="sec-num">2</div>
        <div>
            <div class="sec-title">Your Itinerary</div>
            <div class="sec-sub">Ready to explore</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="metrics">
        <div class="m-card">
            <div class="m-label">Destination</div>
            <div class="m-value">{st.session_state.get('destination', '—')}</div>
        </div>
        <div class="m-card">
            <div class="m-label">Start Date</div>
            <div class="m-value">{st.session_state.get('trip_date', '—')}</div>
        </div>
        <div class="m-card">
            <div class="m-label">Status</div>
            <div class="m-value green">✓ Ready</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        f"<div class='result-card'>{st.session_state['itinerary']}</div>",
        unsafe_allow_html=True,
    )

    calendar_data = create_calendar(
        st.session_state["itinerary"],
        st.session_state.get("trip_date", date.today()),
    )

    st.markdown("<br>", unsafe_allow_html=True)
    dl_col, info_col = st.columns([1, 3])
    with dl_col:
        st.download_button(
            "⬇ Download .ics",
            data=calendar_data,
            file_name="itinerary.ics",
            mime="text/calendar",
            use_container_width=True,
        )
    with info_col:
        st.markdown(
            "<div style='color:#64748b;font-size:0.85rem;padding-top:0.85rem;'>"
            "Import into Google Calendar, Outlook, or Apple Calendar"
            "</div>",
            unsafe_allow_html=True,
        )

        