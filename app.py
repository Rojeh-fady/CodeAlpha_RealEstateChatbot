"""
PrimeEstate AI Assistant
========================
CodeAlpha Cloud Computing Internship - Task 4: "Making an AI-Powered Chatbot".

A high-end real-estate concierge chatbot built with Python + Streamlit.

* 100% free: no API keys, tokens, or external services of any kind.
* Intent recognition: weighted regex pattern matching + entity extraction
  (budget, location, property type, bedrooms, dates, times, income, loan terms).
* Dynamic responses: answers are computed from the property catalogue
  (price statistics, matching scores, mortgage maths), not canned strings.
* Property recommendation widget, sidebar filters, quick actions, lead capture.

Run locally:  streamlit run app.py
"""

from __future__ import annotations

import csv
import html
import inspect
import io
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import streamlit as st

# =============================================================================
# 1. CONFIGURATION
# =============================================================================

APP_NAME = "PrimeEstate AI Assistant"
CONTACT_EMAIL = os.getenv("PRIMEESTATE_CONTACT_EMAIL", "advisory@primeestate.example")
CONTACT_PHONE = os.getenv("PRIMEESTATE_CONTACT_PHONE", "+1 (555) 010-2030")
OFFICE_HOURS = "Monday-Saturday, 09:00-18:00"
LEADS_FILE = Path(os.getenv("PRIMEESTATE_LEADS_FILE", "leads.csv"))
MAX_INPUT_CHARS = 500

DEFAULT_RATE = 6.5  # % annual interest used for illustrations
DEFAULT_DOWN = 20.0  # % down payment
DEFAULT_YEARS = 25
MAX_DTI = 0.35  # max share of monthly income spent on the mortgage
CLOSING_COST_PCT = 3.0  # indicative closing costs, % of price

DISCLAIMER = (
    "_Figures are indicative planning estimates, not a loan offer, valuation, "
    "or financial/legal advice._"
)

# =============================================================================
# 2. PROPERTY CATALOGUE
# =============================================================================

TYPES = ("Apartment", "Villa", "Duplex")
TYPE_EMOJI = {"Apartment": "🏢", "Villa": "🏡", "Duplex": "🏘️"}


@dataclass(frozen=True)
class Property:
    pid: str
    name: str
    ptype: str
    location: str
    price: int
    area: int  # square metres
    beds: int
    baths: int
    parking: int
    rental_yield: float  # gross, % per year
    handover: str
    highlights: tuple
    aliases: tuple  # lowercase phrases that identify this listing in chat


PROPERTIES: tuple = (
    Property("PE-101", "Marina Crown Residences 2204", "Apartment", "Downtown Marina",
             780_000, 142, 2, 3, 2, 6.4, "Ready",
             ("Panoramic marina views from the 22nd floor", "Full smart-home automation",
              "Concierge, infinity pool and private gym"),
             ("marina crown",)),
    Property("PE-102", "The Meridian Skyline Suite", "Apartment", "Skyline District",
             1_250_000, 210, 3, 4, 2, 5.6, "Q2 2027",
             ("Corner suite with 270° skyline views", "Private elevator lobby and smart-home system",
              "Residents' sky lounge, spa and cinema"),
             ("meridian",)),
    Property("PE-103", "Harbor Point Loft", "Apartment", "Harbor Point",
             540_000, 98, 1, 2, 1, 6.8, "Ready",
             ("Double-height loft with floor-to-ceiling glazing", "Direct private-berth marina access",
              "Rooftop terrace and 24/7 concierge"),
             ("harbor point loft", "harbour point loft")),
    Property("PE-104", "Riverside Terrace 5B", "Apartment", "Riverside",
             395_000, 88, 2, 2, 1, 7.1, "Ready",
             ("Landscaped riverfront terrace", "Walk to cafés, galleries and the tram line",
              "Shared pool and fitness studio"),
             ("riverside terrace",)),
    Property("PE-201", "Palm Hills Signature Villa", "Villa", "Palm Hills",
             3_450_000, 620, 5, 6, 4, 4.1, "Ready",
             ("Gated plot with private pool and landscaped garden", "Home cinema and smart-home system",
              "Golf-course frontage and 24/7 security"),
             ("palm hills signature", "signature villa")),
    Property("PE-202", "Greenfield Courtyard Villa", "Villa", "Greenfield Estates",
             2_150_000, 440, 4, 5, 3, 4.4, "Q4 2027",
             ("Central courtyard garden with heated pool", "Staff quarters and 4-car garage",
              "Minutes from international schools"),
             ("greenfield courtyard", "courtyard villa")),
    Property("PE-203", "Harbor Point Waterfront Villa", "Villa", "Harbor Point",
             4_900_000, 780, 6, 7, 5, 3.9, "Ready",
             ("120 m of private beachfront and a private jetty", "Infinity pool, spa and home gym",
              "Private elevator and smart-home system"),
             ("harbor point waterfront", "harbour point waterfront", "waterfront villa")),
    Property("PE-204", "Riverside Garden Villa", "Villa", "Riverside",
             1_680_000, 360, 4, 4, 2, 4.7, "Q2 2027",
             ("Large private garden with outdoor kitchen", "Solar-ready roof and EV charging",
              "Quiet cul-de-sac next to riverside parks"),
             ("riverside garden villa", "riverside garden")),
    Property("PE-301", "Skyline Sky Duplex", "Duplex", "Skyline District",
             1_890_000, 320, 4, 4, 2, 5.3, "Ready",
             ("Two-level sky residence with double-height lounge", "Private rooftop terrace with plunge pool",
              "Direct metro-interchange access"),
             ("skyline sky duplex", "sky duplex")),
    Property("PE-302", "Marina Twin-Level Duplex", "Duplex", "Downtown Marina",
             1_320_000, 250, 3, 3, 2, 5.8, "Q1 2027",
             ("Marina views on both levels", "Private elevator and smart-home system",
              "Resort-style pool and concierge"),
             ("marina twin", "twin-level", "twin level")),
    Property("PE-303", "Greenfield Garden Duplex", "Duplex", "Greenfield Estates",
             960_000, 230, 3, 3, 2, 5.0, "Ready",
             ("Private garden and BBQ terrace", "Clubhouse, pool and kids' play area",
              "Cycling trails and parks on your doorstep"),
             ("greenfield garden",)),
    Property("PE-304", "Palm Hills Penthouse Duplex", "Duplex", "Palm Hills",
             2_750_000, 410, 4, 5, 3, 4.5, "Q4 2027",
             ("Full-floor penthouse duplex with 360° views", "Private rooftop pool and sun deck",
              "Private elevator, spa and 24/7 security"),
             ("palm hills penthouse", "penthouse duplex")),
)
PROPERTY_INDEX = {p.pid: p for p in PROPERTIES}

LOCATIONS: dict = {
    "Downtown Marina": {
        "aliases": ("downtown marina", "downtown", "marina", "city center", "city centre"),
        "summary": "The waterfront business and lifestyle core: marina promenade, fine dining and the financial district a short walk away.",
        "connectivity": "5 min to the CBD · 20 min to the international airport",
    },
    "Skyline District": {
        "aliases": ("skyline district", "skyline"),
        "summary": "Landmark towers and corporate headquarters with rooftop lounges and the metro interchange at your doorstep.",
        "connectivity": "Metro interchange on site · 15 min to the CBD",
    },
    "Harbor Point": {
        "aliases": ("harbor point", "harbour point", "harbor", "harbour"),
        "summary": "An exclusive peninsula of waterfront homes with a yacht club, private berths and beach access.",
        "connectivity": "25 min to the CBD · private marina and jetty access",
    },
    "Palm Hills": {
        "aliases": ("palm hills", "palm"),
        "summary": "A gated hillside enclave with golf-course frontage, international schools and round-the-clock security.",
        "connectivity": "20 min to the CBD · 10 min to international schools",
    },
    "Greenfield Estates": {
        "aliases": ("greenfield estates", "greenfield", "greenfields"),
        "summary": "A low-density family community with parks, cycling trails and a private clubhouse.",
        "connectivity": "30 min to the CBD · dedicated school-bus network",
    },
    "Riverside": {
        "aliases": ("riverside",),
        "summary": "A walkable riverfront neighbourhood of cafés, galleries and weekend markets, and the best entry point for first-time buyers.",
        "connectivity": "12 min to the CBD · tram line on site",
    },
}
LOCATION_NAMES = list(LOCATIONS)

BUDGET_STEPS = [
    250_000, 400_000, 500_000, 600_000, 750_000, 900_000, 1_000_000, 1_250_000,
    1_500_000, 2_000_000, 2_500_000, 3_000_000, 3_500_000, 4_000_000, 5_000_000,
    7_500_000, 10_000_000,
]

VIEWING_SLOTS = [
    "09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "01:00 PM",
    "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM",
]
GENERAL_LABEL = "General enquiry (not sure yet)"
PURPOSES = ["Buy to live in", "Invest / rent out", "Corporate purchase", "Just exploring"]

# =============================================================================
# 3. SMALL HELPERS
# =============================================================================


def fmt_money(v: float) -> str:
    """$1,250,000 style."""
    return f"${v:,.0f}"


def fmt_short(v: float) -> str:
    """$1.25M / $780K style."""
    if v >= 1_000_000:
        return "$" + f"{v / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"
    if v >= 1_000:
        return f"${v / 1_000:,.0f}K"
    return f"${v:,.0f}"


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def md_table(headers: list, rows: list) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "|" + "|".join(["---"] * len(headers)) + "|"
    body = ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join([head, sep, *body])


def md_escape(text: str) -> str:
    """Neutralise Markdown/LaTeX control characters in user-supplied text."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|<>~$])", r"\\\1", text)


def esc_dollar(text: str) -> str:
    """Streamlit renders $...$ as LaTeX; escape bare dollar signs."""
    return re.sub(r"(?<!\\)\$", r"\\$", text)


def csv_safe(value: Any) -> str:
    """Prevent spreadsheet formula injection in exported CSV files."""
    s = str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def prop_label(p: Property) -> str:
    return f"{p.name} · {p.location} · {fmt_short(p.price)}"


PROPERTY_OPTIONS = [GENERAL_LABEL] + [prop_label(p) for p in PROPERTIES]


def next_business_day(d: date) -> date:
    while d.weekday() == 6:  # viewings are not offered on Sundays
        d += timedelta(days=1)
    return d


def monthly_payment(principal: float, annual_rate_pct: float, years: int) -> float:
    n = years * 12
    r = annual_rate_pct / 100 / 12
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def max_price_from_income(monthly_income: float, down_pct: float, rate: float, years: int) -> float:
    payment = monthly_income * MAX_DTI
    n = years * 12
    r = rate / 100 / 12
    loan = payment * n if r == 0 else payment * (1 - (1 + r) ** -n) / r
    return loan / (1 - down_pct / 100)


def snap_budget(lo: float, hi: float) -> tuple:
    lows = [s for s in BUDGET_STEPS if s <= lo]
    highs = [s for s in BUDGET_STEPS if s >= hi]
    return (max(lows) if lows else BUDGET_STEPS[0], min(highs) if highs else BUDGET_STEPS[-1])


def group_stats(props: list) -> dict:
    if not props:
        return {"n": 0, "min": 0, "max": 0, "ppsm": 0, "yield": 0, "area": 0, "price": 0}
    return {
        "n": len(props),
        "min": min(p.price for p in props),
        "max": max(p.price for p in props),
        "ppsm": sum(p.price for p in props) / sum(p.area for p in props),
        "yield": sum(p.rental_yield for p in props) / len(props),
        "area": sum(p.area for p in props) / len(props),
        "price": sum(p.price for p in props) / len(props),
    }


# =============================================================================
# 4. ENTITY EXTRACTION (regex NLP)
# =============================================================================

_MONEY_RE = re.compile(
    r"(?P<cur>[$€£]|usd\b|eur\b)?\s*"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
    r"(?P<suf>billion|bn|million|mn|thousand|k|m)?"
    r"(?![\w%])"
    r"(?!\s*(?:years?|yrs?|yr|percent|per\s*cent|sq|sqm|m2|m²|beds?|bedrooms?|br|baths?|months?|days?|%))",
    re.I,
)
_MULT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}

_TYPE_PATTERNS = {
    "Apartment": re.compile(r"\b(apartments?|flats?|condos?|condominiums?|studios?|lofts?)\b", re.I),
    "Villa": re.compile(r"\b(villas?|mansions?|detached|standalone|houses?)\b", re.I),
    "Duplex": re.compile(r"\b(duplex(?:es)?|townhouses?|maisonettes?|two[- ]level|penthouses?)\b", re.I),
}
_WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
_WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
             "friday": 4, "saturday": 5, "sunday": 6}
_MONTHS = {"january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
           "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
           "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "october": 10,
           "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12}
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DATE_MD = re.compile(rf"\b(?P<mon>{_MONTH_ALT})\.?\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\b", re.I)
_DATE_DM = re.compile(rf"\b(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<mon>{_MONTH_ALT})\b", re.I)


@dataclass
class Entities:
    ptypes: list = field(default_factory=list)
    locations: list = field(default_factory=list)
    min_price: Any = None
    max_price: Any = None
    amount: Any = None
    beds: Any = None
    down_pct: Any = None
    rate: Any = None
    years: Any = None
    income: Any = None
    property_ids: list = field(default_factory=list)
    date: Any = None
    slot: Any = None
    extreme: Any = None  # "low" | "high"

    @property
    def has_search_signal(self) -> bool:
        return bool(self.ptypes or self.locations or self.beds
                    or self.min_price is not None or self.max_price is not None)


def money_values(text: str) -> list:
    """Return every monetary amount found in `text` as a float."""
    out = []
    for m in _MONEY_RE.finditer(text):
        raw = m.group("num")
        suf = (m.group("suf") or "").lower()
        if suf in ("k", "m") and m.start("suf") - m.end("num") > 0:
            continue  # "10 m from the beach" is metres, not millions
        if raw.startswith("0") and not raw.startswith("0.") and not m.group("cur"):
            continue  # phone numbers and codes
        value = float(raw.replace(",", "")) * _MULT.get(suf, 1)
        if m.group("cur") or suf or value >= 10_000:
            out.append(value)
    return out


def extract_income(t: str) -> Any:
    if not re.search(r"\b(income|salary|earn|earns|earning|take[- ]home)\b", t):
        return None
    vals = money_values(t)
    if not vals:
        return None
    v = vals[0]
    monthly = re.search(r"\b(month|monthly|per month|a month|/mo)\b", t)
    annual = re.search(r"\b(year|yearly|annual|annually|per year|a year|p\.a\.)\b", t)
    if annual or (not monthly and v >= 40_000):
        return v / 12
    return v


def extract_percentages(t: str) -> tuple:
    down = rate = None
    for m in re.finditer(r"(\d{1,2}(?:\.\d+)?)\s*(?:%|percent|per\s*cent)", t):
        value = float(m.group(1))
        after = t[m.end(): m.end() + 14]
        before = t[max(0, m.start() - 20): m.start()]
        if re.search(r"down|deposit|upfront|initial", after):
            down = value
        elif re.search(r"interest|rate|apr", after):
            rate = value
        elif re.search(r"interest|rate|apr", before):
            rate = value
        elif re.search(r"down|deposit|upfront|initial", before):
            down = value
    return down, rate


def extract_date(t: str, today: date) -> Any:
    found = None
    if re.search(r"\bday after tomorrow\b", t):
        found = today + timedelta(days=2)
    elif re.search(r"\btomorrow\b", t):
        found = today + timedelta(days=1)
    elif re.search(r"\b(today|tonight)\b", t):
        found = today
    if found is None:
        for name, idx in _WEEKDAYS.items():
            if re.search(rf"\b{name}\b", t):
                found = today + timedelta(days=(idx - today.weekday()) % 7 or 7)
                break
    if found is None and re.search(r"\bnext week\b", t):
        found = today + timedelta(days=7)
    if found is None:
        m = _DATE_MD.search(t) or _DATE_DM.search(t)
        if m:
            try:
                found = date(today.year, _MONTHS[m.group("mon").lower()], int(m.group("day")))
                if found < today:
                    found = found.replace(year=today.year + 1)
            except ValueError:
                found = None
    return found


def extract_slot(t: str) -> Any:
    hour = None
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", t)
    if m:
        hour = int(m.group(1)) % 12 + (12 if m.group(3) == "pm" else 0)
    else:
        m = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", t)
        if m:
            hour = int(m.group(1))
        elif "morning" in t:
            hour = 10
        elif "noon" in t or "lunch" in t:
            hour = 12
        elif "afternoon" in t:
            hour = 14
        elif "evening" in t:
            hour = 17
    if hour is None:
        return None
    return VIEWING_SLOTS[min(max(hour, 9), 17) - 9]


def extract_entities(text: str, today: date | None = None) -> Entities:
    today = today or date.today()
    t = text.lower()
    e = Entities()

    e.ptypes = [name for name, rx in _TYPE_PATTERNS.items() if rx.search(t)]
    for loc, info in LOCATIONS.items():
        if any(re.search(rf"\b{re.escape(a)}\b", t) for a in info["aliases"]):
            e.locations.append(loc)

    positions = []
    for p in PROPERTIES:
        hits = [t.find(a) for a in (*p.aliases, p.name.lower()) if a in t]
        if hits:
            positions.append((min(hits), p.pid))
    e.property_ids = [pid for _, pid in sorted(positions)]

    e.income = extract_income(t)
    if e.income is None:
        vals = [v for v in money_values(t) if v >= 50_000]
        if vals:
            e.amount = vals[0]
        if len(vals) >= 2:
            e.min_price, e.max_price = sorted(vals[:2])
        elif len(vals) == 1:
            v = vals[0]
            if re.search(r"\b(under|below|less than|up to|upto|max(?:imum)?|within|no more than|at most|not exceeding|capped at)\b", t):
                e.max_price = v
            elif re.search(r"\b(over|above|at least|min(?:imum)?|more than|starting (?:at|from))\b", t) \
                    and not re.search(r"\bover\s+\d+\s*(?:years?|yrs?)\b", t):
                e.min_price = v
            else:
                e.max_price = v

    m = re.search(r"\b(\d{1,2}|one|two|three|four|five|six)[\s-]*(?:bed(?:room)?s?|br|bhk|bd)\b", t)
    if m:
        raw = m.group(1)
        e.beds = _WORD_NUM.get(raw) or int(raw)

    e.down_pct, e.rate = extract_percentages(t)
    m = re.search(r"\b(\d{1,2})\s*(?:years?|yrs?|yr)\b", t)
    if m and 1 <= int(m.group(1)) <= 40:
        e.years = int(m.group(1))

    e.date = extract_date(t, today)
    e.slot = extract_slot(t)

    if re.search(r"\b(cheapest|lowest|most affordable|entry[- ]level|least expensive|starter)\b", t):
        e.extreme = "low"
    elif re.search(r"\b(most expensive|highest|top[- ]end|ultra|flagship|priciest|most luxurious)\b", t):
        e.extreme = "high"
    return e


# =============================================================================
# 5. INTENT RECOGNITION (weighted regex patterns)
# =============================================================================


def _p(*pairs: tuple) -> list:
    return [(re.compile(rx, re.I), w) for rx, w in pairs]


INTENT_PATTERNS: dict = {
    "greeting": _p((r"^\s*(hi|hello|hey|hiya|howdy|salam|good\s+(morning|afternoon|evening))\b", 4),
                   (r"\b(hello|hey|greetings)\b", 2)),
    "farewell": _p((r"\b(bye|goodbye|see you|farewell|talk (?:to you )?later|that'?s all)\b", 4)),
    "thanks": _p((r"\b(thanks?|thank you|thx|much appreciated|cheers)\b", 4)),
    "help": _p((r"\b(help|what can you do|what do you do|capabilities|features|how does this work|menu|guide me)\b", 3),
               (r"\bwho are you\b", 3)),
    "affirm": _p((r"^\s*(yes|yeah|yep|sure|ok(?:ay)?|please(?: do)?|go ahead|sounds good|let'?s do it|definitely)\b[\s.!]*$", 5)),
    "booking": _p((r"\b(book|schedule|arrange|reserve|organi[sz]e|set up|plan|request)\b.{0,40}\b(viewings?|visits?|tours?|appointments?|site|showings?|inspections?)\b", 6),
                  (r"\b(viewings?|visits?|tours?|appointments?|showings?|inspections?)\b", 3),
                  (r"\bsee (it|the (property|unit|villa|apartment|duplex|place|house)) (in person|live)\b", 4),
                  (r"\bi(?:'d| would) like to (see|visit|view)\b", 4)),
    "budget_estimate": _p((r"\b(afford|affordab\w+|what can i buy)\b", 4),
                          (r"\bhow much (can|could|should) i (spend|borrow|afford|buy)\b", 6),
                          (r"\bbudget\b", 2),
                          (r"\b(income|salary|earn\w*)\b", 3),
                          (r"\bestimat\w+\b.{0,20}\b(budget|afford)\b", 3)),
    "financing": _p((r"\b(mortgages?|loans?|financing|finance|financed|instal+ments?|repayments?|down ?payments?|deposit|amorti[sz]ation|interest rates?|apr|lenders?|bank)\b", 4),
                    (r"\b(monthly|per month)\b.{0,15}\b(payments?|cost|instal+ments?)\b", 4),
                    (r"\bpayment plans?\b", 4),
                    (r"\bpre-?approv\w+\b", 4),
                    (r"\bpayments?\b", 2)),
    "compare": _p((r"\b(compare|comparison|versus|vs\.?|difference between|better than|which is better)\b", 5)),
    "investment": _p((r"\b(invest\w*|roi|yield|rental income|rent(?:ing)? (?:it )?out|rentals?|return on|capital (?:growth|gains?)|appreciation|resale|buy[- ]to[- ]let|passive income)\b", 6)),
    "legal_fees": _p((r"\b(fees?|tax(?:es)?|stamp duty|registration|legal|lawyers?|contracts?|ownership|freehold|leasehold|title deeds?|documents?|paperwork|closing costs?|foreign(?:er)? buyers?|residency|visa|commission)\b", 4)),
    "contact": _p((r"\b(agents?|advisors?|advisers?|consultants?|representatives?|human)\b", 3),
                  (r"\b(contact|call me|phone|whatsapp|email|reach)\b", 3),
                  (r"\b(speak|talk) (to|with)\b", 4),
                  (r"\b(office|opening) hours\b", 4)),
    "pricing": _p((r"\b(price|prices|pricing|cost|costs|how much|per (?:sqm|sq ?m|square (?:meter|metre|foot|feet))|expensive|cheapest|priciest)\b", 4)),
    "amenities": _p((r"\b(amenit\w+|facilit\w+|gym|pool|swimming|spa|sauna|parking|garage|security|concierge|smart[- ]?home|garden|terrace|balcony|rooftop|elevator|lift|views?|beach|furnish\w+|pets?|kids?|school|cinema)\b", 4)),
    "location": _p((r"\b(locations?|neighbou?rhoods?|areas?|districts?|where|nearby|commute|connectivity|close to|near)\b", 4)),
    "property_match": _p((r"\b(match|matches|recommend\w*|suggest\w*|find me|looking for|show me|i (?:want|need|am after)|search|best (?:property|properties|options?)|options|listings?|properties|portfolio|inventory)\b", 4),
                         (r"\b(bed(?:room)?s?|br)\b", 2)),
    "villa": _p((r"\b(villas?|mansions?|detached|standalone|houses?)\b", 4)),
    "duplex": _p((r"\b(duplex(?:es)?|townhouses?|maisonettes?|two[- ]level|penthouses?)\b", 4)),
    "apartment": _p((r"\b(apartments?|flats?|condos?|condominiums?|studios?|lofts?)\b", 4)),
}

# Higher in the list wins a score tie.
INTENT_PRIORITY = [
    "booking", "budget_estimate", "financing", "compare", "investment", "legal_fees",
    "contact", "pricing", "amenities", "location", "property_match", "villa", "duplex",
    "apartment", "help", "thanks", "farewell", "greeting", "affirm",
]
MIN_INTENT_SCORE = 2


def classify(text: str) -> tuple:
    """Return (intent, scores). Intent is 'fallback' when nothing scores."""
    scores = {}
    for intent, patterns in INTENT_PATTERNS.items():
        s = sum(w for rx, w in patterns if rx.search(text))
        if s:
            scores[intent] = s
    if not scores:
        return "fallback", scores
    best = max(scores.values())
    if best < MIN_INTENT_SCORE:
        return "fallback", scores
    for intent in INTENT_PRIORITY:
        if scores.get(intent) == best:
            return intent, scores
    return "fallback", scores


# =============================================================================
# 6. PROPERTY MATCHING ENGINE
# =============================================================================


@dataclass
class Match:
    prop: Property
    score: int
    exact: bool
    reasons: list
    gaps: list


def filters_to_prefs(filters: dict) -> dict:
    lo, hi = filters.get("budget", (BUDGET_STEPS[0], BUDGET_STEPS[-1]))
    return {
        "types": list(filters.get("types", [])),
        "locations": list(filters.get("locations", [])),
        "min_price": lo if lo > BUDGET_STEPS[0] else None,
        "max_price": hi if hi < BUDGET_STEPS[-1] else None,
        "beds": int(filters.get("beds", 0) or 0),
    }


def merge_prefs(ents: Entities, filters: dict) -> dict:
    prefs = filters_to_prefs(filters)
    if ents.ptypes:
        prefs["types"] = list(ents.ptypes)
    if ents.locations:
        prefs["locations"] = list(ents.locations)
    if ents.min_price is not None or ents.max_price is not None:
        prefs["min_price"], prefs["max_price"] = ents.min_price, ents.max_price
    if ents.beds:
        prefs["beds"] = ents.beds
    return prefs


def describe_prefs(prefs: dict) -> str:
    parts = []
    if prefs.get("types"):
        parts.append(" / ".join(prefs["types"]))
    if prefs.get("beds"):
        parts.append(f"{prefs['beds']}+ bedrooms")
    if prefs.get("locations"):
        parts.append("in " + ", ".join(prefs["locations"]))
    lo, hi = prefs.get("min_price"), prefs.get("max_price")
    if lo is not None and hi is not None:
        parts.append(f"{fmt_short(lo)}-{fmt_short(hi)}")
    elif hi is not None:
        parts.append(f"up to {fmt_short(hi)}")
    elif lo is not None:
        parts.append(f"from {fmt_short(lo)}")
    return " · ".join(parts) if parts else "all listings"


def match_properties(prefs: dict, sort: str | None = None) -> list:
    """Score every property against the preferences (0-100) and rank them."""
    results = []
    for p in PROPERTIES:
        earned = possible = 0.0
        reasons, gaps = [], []

        types = prefs.get("types") or []
        if types:
            possible += 30
            if p.ptype in types:
                earned += 30
                reasons.append(p.ptype)
            else:
                gaps.append(f"It is a {p.ptype}")

        locs = prefs.get("locations") or []
        if locs:
            possible += 25
            if p.location in locs:
                earned += 25
                reasons.append(f"Located in {p.location}")
            else:
                gaps.append(f"It is in {p.location}")

        lo, hi = prefs.get("min_price"), prefs.get("max_price")
        if lo is not None or hi is not None:
            possible += 30
            if hi is not None and p.price > hi:
                over = (p.price / hi - 1) * 100
                gaps.append(f"{over:.0f}% above your budget")
                if p.price <= hi * 1.15:
                    earned += 15
            elif lo is not None and p.price < lo:
                gaps.append("Below your minimum price")
                if p.price >= lo * 0.85:
                    earned += 15
            else:
                earned += 30
                reasons.append("Within your budget")

        beds = prefs.get("beds") or 0
        if beds:
            possible += 15
            if p.beds >= beds:
                earned += 15
                reasons.append(f"{p.beds} bedrooms")
            else:
                gaps.append(f"Only {p.beds} bedrooms")
                if p.beds == beds - 1:
                    earned += 6

        if possible == 0:
            score, reasons = 100, ["Featured listing"]
        else:
            score = round(earned / possible * 100)
        results.append(Match(p, score, not gaps, reasons, gaps))

    sign = -1 if sort == "high" else 1
    results.sort(key=lambda r: (-r.score, sign * r.prop.price))
    return results


# =============================================================================
# 7. RESPONSE GENERATOR
# =============================================================================


@dataclass
class Reply:
    text: str
    cards: list = field(default_factory=list)  # [(pid, score or None)]
    widget: Any = None  # "booking"
    suggestions: list = field(default_factory=list)
    filter_updates: dict = field(default_factory=dict)
    prefill: dict = field(default_factory=dict)
    intent: str = "fallback"


def new_context() -> dict:
    return {"last_intent": None, "focus_pid": None, "pending_offer": None, "fallbacks": 0}


def _filter_updates(ents: Entities) -> dict:
    u: dict = {}
    if ents.ptypes:
        u["types"] = list(ents.ptypes)
    if ents.locations:
        u["locations"] = list(ents.locations)
    if ents.min_price is not None or ents.max_price is not None:
        lo = ents.min_price if ents.min_price is not None else BUDGET_STEPS[0]
        hi = ents.max_price if ents.max_price is not None else BUDGET_STEPS[-1]
        u["budget"] = snap_budget(lo, hi)
    if ents.beds:
        u["beds"] = min(int(ents.beds), 6)
    return u


def _top_cards(matches: list, n: int = 3) -> list:
    return [(m.prop.pid, m.score) for m in matches[:n]]


def _greeting_word() -> str:
    h = datetime.now().hour
    return "Good morning" if h < 12 else "Good afternoon" if h < 18 else "Good evening"


MAIN_SUGGESTIONS = [
    "Show me the best property matches for my filters",
    "Estimate my monthly mortgage payment",
    "Which properties have the best rental yield?",
    "I'd like to schedule a viewing",
]


def _h_greeting(text, ents, ctx, filters, today) -> Reply:
    return Reply(
        f"{_greeting_word()}! I'm the **{APP_NAME}**, your concierge for premium residential real estate.\n\n"
        "I can **match you with properties**, **estimate your budget and monthly payments**, "
        "explain our **locations**, and **book a private viewing**.\n\n"
        "Try something like: *“a 4-bedroom villa in Palm Hills under $4M”* or pick a quick action below.",
        suggestions=MAIN_SUGGESTIONS,
    )


def _h_help(text, ents, ctx, filters, today) -> Reply:
    return Reply(
        "Here is what I can do for you:\n\n"
        "- 🏢 **Find & match properties**: *“3-bedroom duplex in Skyline under $2M”*\n"
        "- 💰 **Estimate your budget**: *“What can I afford on a $9,000 monthly income?”*\n"
        "- 💳 **Calculate mortgages**: *“Mortgage for $2M with 30% down at 5.5% over 20 years”*\n"
        "- 📍 **Explain locations**: *“Tell me about Harbor Point”*\n"
        "- 📈 **Rank investments**: *“Best rental yield in Riverside”*\n"
        "- ⚖️ **Compare**: *“Apartment vs duplex”* or *“Compare Meridian and Marina Crown”*\n"
        "- 🧾 **Explain fees & paperwork**: *“What are the closing costs?”*\n"
        "- 📅 **Book a viewing** or **talk to an advisor**\n\n"
        "The sidebar filters and my answers stay in sync, so you can refine either way.",
        suggestions=MAIN_SUGGESTIONS,
    )


def _h_thanks(text, ents, ctx, filters, today) -> Reply:
    return Reply("You're very welcome! Is there anything else I can help you with, "
                 "such as a viewing or a payment estimate?",
                 suggestions=["I'd like to schedule a viewing", "Estimate my monthly mortgage payment"])


def _h_farewell(text, ents, ctx, filters, today) -> Reply:
    return Reply("Thank you for visiting PrimeEstate. Whenever you are ready, I'm here, "
                 "and our advisors are available " + OFFICE_HOURS + ". Have a wonderful day! 👋")


def _h_affirm(text, ents, ctx, filters, today) -> Reply:
    offer = ctx.get("pending_offer")
    if offer == "booking":
        return _h_booking(text, ents, ctx, filters, today)
    return Reply("Happy to go ahead. What would you like to explore next?", suggestions=MAIN_SUGGESTIONS)


def _h_fallback(text, ents, ctx, filters, today) -> Reply:
    msg = ("I want to be sure I get this right, and I didn't quite catch that. "
           "I can help with **property search**, **budget & mortgage estimates**, **locations**, "
           "**investment yields**, **fees**, and **viewings**.\n\n"
           "Try asking e.g. *“Show me villas under $3M”* or *“How much is a 2-bedroom apartment?”*")
    if ctx.get("fallbacks", 0) >= 1:
        msg += (f"\n\nIf you prefer, a human advisor can help directly: **{CONTACT_PHONE}** "
                f"or **{CONTACT_EMAIL}** ({OFFICE_HOURS}).")
    return Reply(msg, suggestions=["What can you do?", "I'd like to speak to an agent",
                                   "Show me the best property matches for my filters"])


def _h_search(text, ents, ctx, filters, today) -> Reply:
    prefs = merge_prefs(ents, filters)
    results = match_properties(prefs, ents.extreme)
    exact = [m for m in results if m.exact]
    desc = describe_prefs(prefs)

    if exact:
        shown = exact[:3]
        lines = [f"I found **{plural(len(exact), 'property')}** matching *{desc}*"
                 + (f". Here are the top {len(shown)}:" if len(exact) > len(shown) else ":")]
        for m in shown:
            lines.append(f"- **{m.prop.name}** ({fmt_money(m.prop.price)}) — " + ", ".join(m.reasons))
        if len(exact) > len(shown):
            lines.append("\nOpen the **Property Matches** tab to see all of them.")
    else:
        shown = [m for m in results if m.score > 0][:3] or results[:3]
        lines = [f"I couldn't find an exact match for *{desc}*, but these are the **closest alternatives**:"]
        for m in shown:
            note = "; ".join(m.gaps[:2]) if m.gaps else "close fit"
            lines.append(f"- **{m.prop.name}** ({fmt_money(m.prop.price)}) — {m.score}% match · {note}")
        lines.append("\nWant to widen the budget or location? Just tell me what you're flexible on.")

    top = shown[0].prop
    ctx["focus_pid"] = top.pid
    ctx["pending_offer"] = "booking"
    lines.append(f"\nWould you like to **book a private viewing** of *{top.name}*?")
    return Reply(
        "\n".join(lines), cards=_top_cards(shown), filter_updates=_filter_updates(ents),
        suggestions=[f"Book a viewing for {top.name}",
                     f"Estimate the monthly payment for {top.name}",
                     f"Tell me more about {top.name}",
                     "Compare apartment vs villa vs duplex"],
    )


def _h_property_detail(text, ents, ctx, filters, today) -> Reply:
    p = PROPERTY_INDEX[ents.property_ids[0]]
    ctx["focus_pid"] = p.pid
    ctx["pending_offer"] = "booking"
    rent = p.price * p.rental_yield / 100
    lines = [
        f"**{p.name}** — {p.ptype} in **{p.location}**",
        f"- **Price:** {fmt_money(p.price)} ({fmt_money(p.price / p.area)} per m²)",
        f"- **Layout:** {p.beds} bedrooms · {p.baths} bathrooms · {p.area} m² · {plural(p.parking, 'parking space')}",
        f"- **Handover:** {p.handover}",
        f"- **Estimated gross rental yield:** {p.rental_yield}% (≈ {fmt_money(rent)} per year)",
        "- **Highlights:** " + "; ".join(p.highlights),
        "",
        "Shall I arrange a private viewing?",
    ]
    return Reply("\n".join(lines), cards=[(p.pid, None)],
                 suggestions=[f"Book a viewing for {p.name}",
                              f"Estimate the monthly payment for {p.name}",
                              f"Tell me about {p.location}",
                              "Show me the best property matches for my filters"])


def _h_booking(text, ents, ctx, filters, today) -> Reply:
    pid = ents.property_ids[0] if ents.property_ids else ctx.get("focus_pid")
    prefill: dict = {}
    notes = []
    if pid:
        p = PROPERTY_INDEX[pid]
        prefill["property"] = pid
        ctx["focus_pid"] = pid
        notes.append(f"property: **{p.name}**")
    if ents.date:
        d = next_business_day(max(ents.date, today))
        prefill["date"] = d
        label = d.strftime("%A, %d %B %Y")
        if d != ents.date:
            label += " (the closest available day; viewings run Monday to Saturday)"
        notes.append(f"date: **{label}**")
    if ents.slot:
        prefill["slot"] = ents.slot
        notes.append(f"time: **{ents.slot}**")
    ctx["pending_offer"] = None
    intro = "Excellent choice. Private viewings are hosted by a senior advisor " \
            f"**{OFFICE_HOURS.replace('-18:00', ', last viewing 17:00')}** and typically last 45 minutes."
    if notes:
        intro += "\n\nI've pre-filled " + ", ".join(notes) + "."
    intro += "\n\nComplete the short form below and an advisor will confirm within one business day."
    return Reply(intro, widget="booking", prefill=prefill,
                 suggestions=["Estimate my monthly mortgage payment", "What are the closing costs?"])


def _h_contact(text, ents, ctx, filters, today) -> Reply:
    return Reply(
        "Our advisory desk is happy to help:\n\n"
        f"- 📞 **Phone / WhatsApp:** {CONTACT_PHONE}\n"
        f"- ✉️ **Email:** {CONTACT_EMAIL}\n"
        f"- 🕘 **Hours:** {OFFICE_HOURS}\n\n"
        "Or leave your details below and an advisor will call you back.",
        widget="booking", prefill={"property": None},
        suggestions=["Show me the best property matches for my filters", "What are the closing costs?"],
    )


def _price_reference(ents, ctx) -> tuple:
    """Pick the purchase price for a mortgage illustration: (price, label)."""
    if ents.property_ids:
        p = PROPERTY_INDEX[ents.property_ids[0]]
        return p.price, p.name
    if ents.amount:
        return ents.amount, None
    if ctx.get("focus_pid"):
        p = PROPERTY_INDEX[ctx["focus_pid"]]
        return p.price, p.name
    if ents.max_price:
        return ents.max_price, None
    return 1_000_000, None


def _h_financing(text, ents, ctx, filters, today) -> Reply:
    price, label = _price_reference(ents, ctx)
    explicit = bool(ents.property_ids or ents.amount or ctx.get("focus_pid") or ents.max_price)
    down = ents.down_pct if ents.down_pct is not None else DEFAULT_DOWN
    down = min(max(down, 5), 90)
    rate = ents.rate if ents.rate is not None else DEFAULT_RATE
    years = ents.years or DEFAULT_YEARS
    loan = price * (1 - down / 100)
    pay = monthly_payment(loan, rate, years)
    interest = pay * years * 12 - loan
    closing = price * CLOSING_COST_PCT / 100
    down_amt = price - loan

    title = f"**Mortgage estimate** for **{fmt_money(price)}**" + (f" ({label})" if label else "")
    if not explicit:
        title += " *(illustrative price; tell me yours for an exact figure)*"
    table = md_table(["Item", "Amount"], [
        ["Purchase price", fmt_money(price)],
        [f"Down payment ({down:g}%)", fmt_money(down_amt)],
        ["Loan amount", fmt_money(loan)],
        ["Interest rate / term", f"{rate:g}% / {years} years"],
        ["**Monthly payment**", f"**{fmt_money(pay)}**"],
        ["Total interest over the term", fmt_money(interest)],
        [f"Est. closing costs (~{CLOSING_COST_PCT:g}%)", fmt_money(closing)],
        ["**Cash needed upfront**", f"**{fmt_money(down_amt + closing)}**"],
    ])
    alt = " · ".join(f"{y} yrs → **{fmt_money(monthly_payment(loan, rate, y))}**/mo" for y in (15, 20, 30) if y != years)
    income_needed = pay / MAX_DTI
    text_out = (f"{title}\n\n{table}\n\n**Other terms at {rate:g}%:** {alt}\n\n"
                f"Lenders typically look for the payment to stay under {MAX_DTI * 100:.0f}% of income, "
                f"i.e. roughly **{fmt_money(income_needed)}/month** of gross income.\n\n{DISCLAIMER}")
    ctx["last_price"] = price
    return Reply(text_out, suggestions=[
        "What can I afford on a $9,000 monthly income?",
        "Mortgage for $2M with 30% down at 5.5% over 20 years",
        "I'd like to schedule a viewing"])


def _h_budget(text, ents, ctx, filters, today) -> Reply:
    down = ents.down_pct if ents.down_pct is not None else DEFAULT_DOWN
    rate = ents.rate if ents.rate is not None else DEFAULT_RATE
    years = ents.years or DEFAULT_YEARS

    if ents.income:
        cap = max_price_from_income(ents.income, down, rate, years)
        ents.max_price = cap
        prefs = merge_prefs(ents, filters)
        prefs["min_price"] = None
        results = match_properties(prefs, ents.extreme)
        exact = [m for m in results if m.exact]
        shown = (exact or results)[:3]
        loan = cap * (1 - down / 100)
        pay = monthly_payment(loan, rate, years)
        lines = [
            f"With a gross income of **{fmt_money(ents.income)}/month**, a {down:g}% down payment, "
            f"{rate:g}% interest and a {years}-year term, a comfortable ceiling "
            f"(payment ≤ {MAX_DTI * 100:.0f}% of income) is about **{fmt_money(cap)}**.",
            f"- Monthly payment at that price: **{fmt_money(pay)}**",
            f"- Down payment needed: **{fmt_money(cap * down / 100)}** (plus ≈ {fmt_money(cap * CLOSING_COST_PCT / 100)} closing costs)",
            "",
        ]
        if exact:
            lines.append(f"**{plural(len(exact), 'property')}** fit that budget. Top picks:")
        else:
            lines.append("Nothing sits under that ceiling yet, so here are the closest options:")
        for m in shown:
            lines.append(f"- **{m.prop.name}**: {fmt_money(m.prop.price)} · {m.prop.location}")
        lines.append(f"\n{DISCLAIMER}")
        ctx["focus_pid"] = shown[0].prop.pid
        ctx["pending_offer"] = "booking"
        return Reply("\n".join(lines), cards=_top_cards(shown), suggestions=[
            f"Book a viewing for {shown[0].prop.name}", "Estimate my monthly mortgage payment",
            "Show me the best property matches for my filters"],
            filter_updates=_filter_updates(ents))

    if ents.max_price is not None or ents.min_price is not None:
        return _h_search(text, ents, ctx, filters, today)

    rows = []
    for t in TYPES:
        s = group_stats([p for p in PROPERTIES if p.ptype == t])
        rows.append([f"{TYPE_EMOJI[t]} {t}", fmt_money(s["min"]), fmt_money(s["max"])])
    return Reply(
        "Let's find your ideal budget. Tell me **either**:\n\n"
        "- your **budget**, e.g. *“I have $1.5M to spend”*, or\n"
        "- your **monthly income**, e.g. *“I earn $9,000 a month”*.\n\n"
        "For reference, our current price bands are:\n\n"
        + md_table(["Type", "From", "To"], rows)
        + "\n\nYou can also set the budget slider in the sidebar.",
        suggestions=["I have $1.5M to spend", "What can I afford on a $9,000 monthly income?",
                     "Estimate my monthly mortgage payment"],
    )


def _h_pricing(text, ents, ctx, filters, today) -> Reply:
    prefs = merge_prefs(ents, filters)
    pool = [p for p in PROPERTIES
            if (not prefs["types"] or p.ptype in prefs["types"])
            and (not prefs["locations"] or p.location in prefs["locations"])
            and (not prefs["beds"] or p.beds >= prefs["beds"])]
    if not pool:
        pool = list(PROPERTIES)
        note = "I have no listings for that exact combination, so here is the overall picture:\n\n"
    else:
        scope = describe_prefs({k: prefs[k] for k in ("types", "locations", "beds")} | {"min_price": None, "max_price": None})
        note = f"Pricing overview for *{scope}*:\n\n"
    rows = []
    for t in TYPES:
        s = group_stats([p for p in pool if p.ptype == t])
        if s["n"]:
            rows.append([f"{TYPE_EMOJI[t]} {t}", s["n"], f"{fmt_money(s['min'])} – {fmt_money(s['max'])}",
                         fmt_money(s["ppsm"])])
    overall = group_stats(pool)
    text_out = note + md_table(["Type", "Listings", "Price range", "Avg. per m²"], rows)
    text_out += (f"\n\nAcross these listings the average is **{fmt_money(overall['price'])}** "
                 f"(**{fmt_money(overall['ppsm'])}/m²**).")
    ordered = sorted(pool, key=lambda p: p.price, reverse=(ents.extreme == "high"))
    cards = []
    if ents.extreme or ents.ptypes or ents.locations:
        cards = [(p.pid, None) for p in ordered[:3]]
        which = "most exclusive" if ents.extreme == "high" else "most accessible"
        text_out += f"\n\nThe {which} options are shown below."
        ctx["focus_pid"] = ordered[0].pid
        ctx["pending_offer"] = "booking"
    return Reply(text_out, cards=cards, filter_updates=_filter_updates(ents), suggestions=[
        "What can I afford on a $9,000 monthly income?", "Estimate my monthly mortgage payment",
        "Show me the best property matches for my filters"])


def _h_location(text, ents, ctx, filters, today) -> Reply:
    if not ents.locations:
        rows = []
        for name, info in LOCATIONS.items():
            props = [p for p in PROPERTIES if p.location == name]
            s = group_stats(props)
            rows.append([f"**{name}**", s["n"], f"{fmt_short(s['min'])} – {fmt_short(s['max'])}", fmt_money(s["ppsm"])])
        return Reply(
            "We curate homes across **six prime locations**:\n\n"
            + md_table(["Location", "Listings", "Price range", "Avg. per m²"], rows)
            + "\n\nName a location (e.g. *“Tell me about Palm Hills”*) for its lifestyle profile and listings.",
            suggestions=[f"Tell me about {n}" for n in LOCATION_NAMES[:4]])
    blocks = []
    for name in ents.locations[:2]:
        info = LOCATIONS[name]
        props = [p for p in PROPERTIES if p.location == name]
        s = group_stats(props)
        types = ", ".join(sorted({p.ptype for p in props}))
        blocks.append(f"**📍 {name}**\n{info['summary']}\n"
                      f"- **Connectivity:** {info['connectivity']}\n"
                      f"- **Our listings:** {plural(s['n'], 'home')} ({types}) · "
                      f"{fmt_short(s['min'])}–{fmt_short(s['max'])} · avg {fmt_money(s['ppsm'])}/m²\n"
                      f"- **Avg. rental yield:** {s['yield']:.1f}%")
    ents_for_search = Entities(ptypes=ents.ptypes, locations=ents.locations)
    prefs = merge_prefs(ents_for_search, {})
    results = [m for m in match_properties(prefs) if m.exact]
    ctx["focus_pid"] = results[0].prop.pid if results else ctx.get("focus_pid")
    ctx["pending_offer"] = "booking"
    return Reply("\n\n".join(blocks) + "\n\nHere are the homes available there:",
                 cards=_top_cards(results), filter_updates={"locations": list(ents.locations)},
                 suggestions=[f"Book a viewing for {results[0].prop.name}" if results else "I'd like to schedule a viewing",
                              "Which properties have the best rental yield?", "Show me the best property matches for my filters"])


AMENITY_KEYWORDS = {
    "pool": "pool", "swimming": "pool", "gym": "gym", "spa": "spa", "sauna": "sauna",
    "parking": "parking", "garage": "garage", "security": "security", "concierge": "concierge",
    "smart": "smart-home", "garden": "garden", "terrace": "terrace", "balcony": "terrace",
    "rooftop": "rooftop", "elevator": "elevator", "lift": "elevator", "beach": "beach",
    "view": "view", "views": "view", "cinema": "cinema", "kids": "kids", "school": "school",
}


def _h_amenities(text, ents, ctx, filters, today) -> Reply:
    t = text.lower()
    wanted = []
    for word, key in AMENITY_KEYWORDS.items():
        if re.search(rf"\b{word}s?\b", t) and key not in wanted:
            wanted.append(key)
    prefs = merge_prefs(ents, filters)

    def has(p: Property, key: str) -> bool:
        blob = " ".join(p.highlights).lower()
        if key == "parking":
            return p.parking >= 2
        return key.replace("-", " ") in blob or key.replace("-", "") in blob

    if wanted:
        pool = [m for m in match_properties(prefs) if m.exact] or match_properties(prefs)
        found = [m for m in pool if all(has(m.prop, k) for k in wanted)] or \
                [m for m in pool if any(has(m.prop, k) for k in wanted)]
        label = ", ".join(wanted)
        if found:
            shown = found[:3]
            lines = [f"**{plural(len(found), 'listing')}** offer **{label}**:"]
            for m in shown:
                lines.append(f"- **{m.prop.name}** ({m.prop.location}): " + "; ".join(m.prop.highlights))
            ctx["focus_pid"] = shown[0].prop.pid
            ctx["pending_offer"] = "booking"
            return Reply("\n".join(lines), cards=_top_cards(shown), suggestions=[
                f"Book a viewing for {shown[0].prop.name}", "Show me the best property matches for my filters"])
        return Reply(f"None of our current listings highlight **{label}** within your filters. "
                     "Try widening the budget or location, or ask an advisor about upcoming launches.",
                     suggestions=["I'd like to speak to an agent"])
    return Reply(
        "Every PrimeEstate home is vetted for lifestyle quality. Typical amenities include:\n\n"
        "- 🏊 Private or resort-style pools and spas\n- 🛎️ 24/7 concierge and security\n"
        "- 🏠 Smart-home automation and private elevators\n- 🌿 Gardens, terraces and rooftop decks\n"
        "- 🚗 Secure parking (1–5 spaces depending on the home)\n- 🎓 Proximity to schools, metro and marinas\n\n"
        "Ask for something specific, e.g. *“Which homes have a private pool?”* or *“sea views”*.",
        suggestions=["Which homes have a private pool?", "Show me properties with smart-home and sea views"])


def _h_investment(text, ents, ctx, filters, today) -> Reply:
    prefs = merge_prefs(ents, filters)
    pool = [m.prop for m in match_properties(prefs) if m.exact] or list(PROPERTIES)
    ranked = sorted(pool, key=lambda p: -p.rental_yield)[:3]
    rows = [[f"**{p.name}**", p.location, fmt_money(p.price), f"{p.rental_yield}%",
             fmt_money(p.price * p.rental_yield / 100)] for p in ranked]
    ctx["focus_pid"] = ranked[0].pid
    ctx["pending_offer"] = "booking"
    avg = {t: group_stats([p for p in PROPERTIES if p.ptype == t])["yield"] for t in TYPES}
    return Reply(
        "Top income-generating picks" + (f" for *{describe_prefs(prefs)}*" if describe_prefs(prefs) != "all listings" else "") + ":\n\n"
        + md_table(["Property", "Location", "Price", "Gross yield", "Est. annual rent"], rows)
        + "\n\n**Average gross yield by type:** "
        + " · ".join(f"{TYPE_EMOJI[t]} {t} {v:.1f}%" for t, v in avg.items())
        + "\n\nCompact apartments yield the most, while villas typically offer stronger long-term capital value. "
        + "Yields are gross (before service charges, vacancy and tax). " + DISCLAIMER,
        cards=[(p.pid, None) for p in ranked], filter_updates=_filter_updates(ents),
        suggestions=[f"Book a viewing for {ranked[0].name}", "Compare apartment vs villa vs duplex",
                     "Estimate my monthly mortgage payment"])


def _h_compare(text, ents, ctx, filters, today) -> Reply:
    if len(ents.property_ids) >= 2:
        a, b = (PROPERTY_INDEX[i] for i in ents.property_ids[:2])
        rows = [
            ["Type", a.ptype, b.ptype], ["Location", a.location, b.location],
            ["Price", fmt_money(a.price), fmt_money(b.price)],
            ["Size", f"{a.area} m²", f"{b.area} m²"],
            ["Price per m²", fmt_money(a.price / a.area), fmt_money(b.price / b.area)],
            ["Bedrooms / baths", f"{a.beds} / {a.baths}", f"{b.beds} / {b.baths}"],
            ["Parking", a.parking, b.parking],
            ["Gross rental yield", f"{a.rental_yield}%", f"{b.rental_yield}%"],
            ["Handover", a.handover, b.handover],
        ]
        cheaper = a if a.price < b.price else b
        better_yield = a if a.rental_yield > b.rental_yield else b
        ctx["focus_pid"] = a.pid
        ctx["pending_offer"] = "booking"
        return Reply(
            md_table(["", f"**{a.name}**", f"**{b.name}**"], rows)
            + f"\n\n**{cheaper.name}** is the more accessible purchase, while **{better_yield.name}** "
              "offers the stronger rental yield.",
            cards=[(a.pid, None), (b.pid, None)],
            suggestions=[f"Book a viewing for {a.name}", f"Book a viewing for {b.name}"])
    types = ents.ptypes if len(ents.ptypes) >= 2 else list(TYPES)
    rows = []
    for t in types:
        s = group_stats([p for p in PROPERTIES if p.ptype == t])
        beds = [p.beds for p in PROPERTIES if p.ptype == t]
        rows.append([f"{TYPE_EMOJI[t]} **{t}**", s["n"], f"{fmt_short(s['min'])} – {fmt_short(s['max'])}",
                     f"{s['area']:.0f} m²", fmt_money(s["ppsm"]), f"{s['yield']:.1f}%", f"{min(beds)}–{max(beds)}"])
    return Reply(
        "Here is how the property types compare across our current listings:\n\n"
        + md_table(["Type", "Listings", "Price range", "Avg. size", "Avg. per m²", "Avg. yield", "Bedrooms"], rows)
        + "\n\n- **Apartments**: lowest entry price, best yields, low maintenance.\n"
          "- **Villas**: maximum space, privacy and long-term land value.\n"
          "- **Duplexes**: villa-like space and terraces with apartment-style services.\n\n"
          "You can also compare two specific homes, e.g. *“Compare Meridian and Marina Crown”*.",
        suggestions=["Show me villas under $3M", "Show me the best duplex options", "Which properties have the best rental yield?"])


def _h_legal(text, ents, ctx, filters, today) -> Reply:
    return Reply(
        "Buying with PrimeEstate is straightforward. **Indicative** purchase costs:\n\n"
        + md_table(["Item", "Typical planning range", "Notes"], [
            ["Registration / transfer fee", "≈ 2–4% of price", "Paid at title transfer; confirmed per property"],
            ["Legal & conveyancing", "≈ 0.5–1% of price", "Independent lawyer recommended"],
            ["Valuation & mortgage registration", "≈ 0.25–1% of loan", "Only if you finance"],
            ["Reservation deposit", "≈ 5–10% of price", "Credited against the purchase price"],
            ["Community service charges", "Quoted per community", "Ask your advisor for the latest schedule"],
        ])
        + "\n\n**Documents to prepare:** valid passport or national ID · proof of funds or bank statements · "
          "mortgage pre-approval letter (if financing) · signed reservation form.\n\n"
          "Ownership structure (freehold or leasehold) and eligibility for non-resident buyers are confirmed for each property by our legal team. "
        + DISCLAIMER,
        suggestions=["Estimate my monthly mortgage payment", "I'd like to speak to an agent", "I'd like to schedule a viewing"])


HANDLERS: dict = {
    "greeting": _h_greeting, "help": _h_help, "thanks": _h_thanks, "farewell": _h_farewell,
    "affirm": _h_affirm, "fallback": _h_fallback, "property_match": _h_search, "apartment": _h_search,
    "villa": _h_search, "duplex": _h_search, "property_detail": _h_property_detail,
    "booking": _h_booking, "contact": _h_contact, "financing": _h_financing,
    "budget_estimate": _h_budget, "pricing": _h_pricing, "location": _h_location,
    "amenities": _h_amenities, "investment": _h_investment, "compare": _h_compare,
    "legal_fees": _h_legal,
}

_DETAIL_OVERRIDES = {"fallback", "property_match", "pricing", "amenities", "location",
                     "investment", "apartment", "villa", "duplex"}


def refine_intent(intent: str, ents: Entities) -> str:
    if ents.property_ids and intent in _DETAIL_OVERRIDES:
        return "property_detail"
    if ents.income and intent in {"fallback", "property_match", "pricing", "greeting", "financing"}:
        return "budget_estimate"
    if intent == "fallback" and ents.has_search_signal:
        return "property_match"
    return intent


def generate_reply(text: str, ctx: dict, filters: dict, today: date | None = None) -> Reply:
    """Main entry point of the chatbot brain (pure Python, no Streamlit)."""
    today = today or date.today()
    clean = " ".join(text.split())[:MAX_INPUT_CHARS]
    ents = extract_entities(clean, today)
    intent, _ = classify(clean)
    intent = refine_intent(intent, ents)
    reply = HANDLERS.get(intent, _h_fallback)(clean, ents, ctx, filters, today)
    reply.intent = intent
    ctx["last_intent"] = intent
    ctx["fallbacks"] = ctx.get("fallbacks", 0) + 1 if intent == "fallback" else 0
    if intent not in ("affirm", "fallback") and reply.widget is None and "pending_offer" not in ctx:
        ctx["pending_offer"] = None
    return reply


# =============================================================================
# 8. LEAD CAPTURE
# =============================================================================

LEAD_FIELDS = ["reference", "created_at", "name", "email", "phone", "purpose",
               "property", "viewing_date", "viewing_time", "notes"]
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_PHONE_RE = re.compile(r"^\+?[\d\s().-]{7,25}$")


def validate_lead(name: str, email: str, phone: str, when: date, consent: bool, today: date | None = None) -> list:
    today = today or date.today()
    errors = []
    if len(name.strip()) < 2 or not re.search(r"[^\W\d_]", name):
        errors.append("Please enter your full name.")
    if not _EMAIL_RE.match(email.strip()):
        errors.append("Please enter a valid email address.")
    digits = re.sub(r"\D", "", phone)
    if not _PHONE_RE.match(phone.strip()) or not 7 <= len(digits) <= 15:
        errors.append("Please enter a valid phone number (7–15 digits).")
    if when < today:
        errors.append("The viewing date cannot be in the past.")
    elif when.weekday() == 6:
        errors.append("Viewings are not available on Sundays. Please choose Monday to Saturday.")
    if not consent:
        errors.append("Please tick the consent box so an advisor may contact you.")
    return errors


def save_lead(lead: dict) -> bool:
    """Append a lead to the CSV file. Returns False if the disk is read-only."""
    try:
        LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)
        is_new = not LEADS_FILE.exists()
        with LEADS_FILE.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=LEAD_FIELDS)
            if is_new:
                writer.writeheader()
            writer.writerow({k: csv_safe(lead.get(k, "")) for k in LEAD_FIELDS})
        return True
    except OSError:
        return False


def leads_to_csv(leads: list) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=LEAD_FIELDS)
    writer.writeheader()
    for lead in leads:
        writer.writerow({k: csv_safe(lead.get(k, "")) for k in LEAD_FIELDS})
    return buf.getvalue()


# =============================================================================
# 9. STREAMLIT UI
# =============================================================================

_STRETCH = ({"width": "stretch"} if "width" in inspect.signature(st.button).parameters
            else {"use_container_width": True})

CSS = """
<style>
.block-container {padding-top: 1.4rem; max-width: 1100px;}
.pe-hero {background: linear-gradient(135deg, #0B1F3A 0%, #17375F 60%, #C8A24A 140%);
  border-radius: 18px; padding: 22px 28px; margin-bottom: 14px; color: #fff;}
.pe-hero h1 {margin: 0; font-size: 1.7rem; color: #fff; padding: 0;}
.pe-hero p {margin: 4px 0 0 0; color: #E8D9AE; font-size: 0.95rem;}
.pe-card {border: 1px solid rgba(200,162,74,.55); border-radius: 14px; padding: 14px 16px;
  background: rgba(128,128,128,.07); margin-bottom: 8px; height: 100%;}
.pe-top {display: flex; justify-content: space-between; align-items: center; font-size: .8rem; opacity: .85;}
.pe-badge {background: #C8A24A; color: #0B1F3A; border-radius: 999px; padding: 2px 10px; font-weight: 700; font-size: .75rem;}
.pe-title {font-weight: 700; font-size: 1.02rem; margin: 6px 0 0 0; line-height: 1.25;}
.pe-loc {font-size: .85rem; opacity: .8; margin-bottom: 4px;}
.pe-price {font-size: 1.35rem; font-weight: 800; color: #B8892B; margin: 4px 0;}
.pe-specs {font-size: .85rem; margin-bottom: 6px;}
.pe-card ul {margin: 6px 0 8px 16px; padding: 0; font-size: .82rem;}
.pe-foot {font-size: .78rem; opacity: .75; border-top: 1px dashed rgba(128,128,128,.4); padding-top: 6px;}
[data-testid="stChatMessage"] {border-radius: 16px; padding: 10px 14px;}
.pe-ts {font-size: .7rem; opacity: .55;}
</style>
"""


def card_html(p: Property, score: Any = None) -> str:
    badge = f'<span class="pe-badge">{score}% match</span>' if score is not None else ""
    items = "".join(f"<li>{html.escape(h)}</li>" for h in p.highlights)
    return (
        '<div class="pe-card">'
        f'<div class="pe-top"><span>{TYPE_EMOJI[p.ptype]} {p.ptype}</span>{badge}</div>'
        f'<div class="pe-title">{html.escape(p.name)}</div>'
        f'<div class="pe-loc">📍 {html.escape(p.location)}</div>'
        f'<div class="pe-price">&#36;{p.price:,}</div>'
        f'<div class="pe-specs">🛏 {p.beds} · 🛁 {p.baths} · 📐 {p.area} m² · 🚗 {p.parking}</div>'
        f"<ul>{items}</ul>"
        f'<div class="pe-foot">Est. yield {p.rental_yield}% · Handover {html.escape(p.handover)}</div>'
        "</div>"
    )


# ---- session state & callbacks ------------------------------------------------


def make_message(role: str, content: str, **extra: Any) -> dict:
    return {"role": role, "content": content, "ts": datetime.now().strftime("%H:%M"),
            "cards": [], "widget": None, "suggestions": [], **extra}


def welcome_message() -> dict:
    r = _h_greeting("", Entities(), new_context(), {}, date.today())
    return make_message("assistant", r.content if hasattr(r, "content") else r.text, suggestions=r.suggestions)


def default_filters() -> dict:
    return {"f_budget": (BUDGET_STEPS[0], BUDGET_STEPS[-1]), "f_locations": [], "f_types": [], "f_beds": 0}


def init_state() -> None:
    ss = st.session_state
    if "messages" not in ss:
        ss.messages = [welcome_message()]
    ss.setdefault("ctx", new_context())
    ss.setdefault("leads", [])
    ss.setdefault("pending_prompt", None)
    for k, v in default_filters().items():
        ss.setdefault(k, v)


def queue_prompt(text: str) -> None:
    st.session_state.pending_prompt = text


def reset_filters() -> None:
    for k, v in default_filters().items():
        st.session_state[k] = v


def clear_chat() -> None:
    st.session_state.messages = [welcome_message()]
    st.session_state.ctx = new_context()


def current_filters() -> dict:
    ss = st.session_state
    raw_b = ss.f_budget
    b_tuple = tuple(raw_b) if isinstance(raw_b, (list, tuple)) else (250000, raw_b)
    return {
        "budget": b_tuple,
        "locations": list(ss.f_locations),
        "types": list(ss.f_types),
        "beds": ss.f_beds
    }

def apply_filter_updates(u: dict) -> None:
    ss = st.session_state
    if "types" in u:
        ss.f_types = [t for t in u["types"] if t in TYPES]
    if "locations" in u:
        ss.f_locations = [x for x in u["locations"] if x in LOCATIONS]
    if "budget" in u:
        ss.f_budget = tuple(u["budget"])
    if "beds" in u:
        ss.f_beds = u["beds"]


def apply_prefill(prefill: dict) -> None:
    ss = st.session_state
    if "property" in prefill:
        pid = prefill["property"]
        ss.lead_property = prop_label(PROPERTY_INDEX[pid]) if pid else GENERAL_LABEL
    if "date" in prefill:
        ss.lead_date = prefill["date"]
    if "slot" in prefill:
        ss.lead_slot = prefill["slot"]


def handle_user_message(text: str) -> None:
    ss = st.session_state
    text = " ".join(text.split())[:MAX_INPUT_CHARS]
    if not text:
        return
    ss.messages.append(make_message("user", text))
    reply = generate_reply(text, ss.ctx, current_filters())
    apply_filter_updates(reply.filter_updates)
    apply_prefill(reply.prefill)
    ss.messages.append(make_message("assistant", reply.text, cards=reply.cards,
                                    widget=reply.widget, suggestions=reply.suggestions))


# ---- renderers --------------------------------------------------------------------


def render_cards(cards: list, key_prefix: str, buttons: bool = False) -> None:
    if not cards:
        return
    cols = st.columns(len(cards))
    for col, (pid, score) in zip(cols, cards):
        p = PROPERTY_INDEX[pid]
        with col:
            st.markdown(card_html(p, score), unsafe_allow_html=True)
            if buttons:
                st.button("📅 Book a viewing", key=f"{key_prefix}_book_{pid}", on_click=queue_prompt,
                          args=(f"Book a viewing for {p.name}",), **_STRETCH)


def render_lead_form() -> None:
    ss = st.session_state
    today = date.today()
    ss.setdefault("lead_property", GENERAL_LABEL)
    ss.setdefault("lead_purpose", PURPOSES[0])
    ss.setdefault("lead_slot", VIEWING_SLOTS[1])
    if "lead_date" not in ss or ss.lead_date < today:
        ss.lead_date = next_business_day(today + timedelta(days=1))
    if ss.lead_property not in PROPERTY_OPTIONS:
        ss.lead_property = GENERAL_LABEL

    with st.form("lead_form"):
        st.markdown("##### 📅 Request a private viewing")
        c1, c2 = st.columns(2)
        name = c1.text_input("Full name *", key="lead_name", max_chars=80)
        email = c2.text_input("Email *", key="lead_email", max_chars=120)
        phone = c1.text_input("Phone / WhatsApp *", key="lead_phone", max_chars=25)
        purpose = c2.selectbox("I'm looking to…", PURPOSES, key="lead_purpose")
        prop = st.selectbox("Property of interest", PROPERTY_OPTIONS, key="lead_property")
        when = c1.date_input("Preferred date", min_value=today, key="lead_date")
        slot = c2.selectbox("Preferred time", VIEWING_SLOTS, key="lead_slot")
        notes = st.text_area("Anything we should know? (optional)", key="lead_notes", max_chars=500, height=90)
        consent = st.checkbox("I agree to be contacted by PrimeEstate about this request.", key="lead_consent")
        submitted = st.form_submit_button("Confirm request", type="primary")

    if not submitted:
        return
    errors = validate_lead(name, email, phone, when, consent, today)
    if errors:
        for err in errors:
            st.error(err)
        return

    lead = {
        "reference": f"PE-{when:%y%m%d}-{uuid.uuid4().hex[:4].upper()}",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "name": name.strip(), "email": email.strip(), "phone": phone.strip(),
        "purpose": purpose, "property": prop, "viewing_date": when.isoformat(),
        "viewing_time": slot, "notes": notes.strip(),
    }
    saved = save_lead(lead)
    ss.leads.append(lead)
    ss.ctx["pending_offer"] = None
    confirmation = (
        f"✅ **Request confirmed, {md_escape(lead['name'].split()[0])}!**\n\n"
        + md_table(["Detail", "Value"], [
            ["Reference", f"`{lead['reference']}`"],
            ["Property", md_escape(prop)],
            ["Date & time", f"{when:%A, %d %B %Y} at {slot}"],
            ["Contact", f"{md_escape(lead['email'])} · {md_escape(lead['phone'])}"],
        ])
        + "\n\nAn advisor will confirm by email or phone within one business day. "
          "You can review your requests in the **My Requests** tab."
        + ("" if saved else "\n\n_Note: the server could not persist your request to disk; it is kept for this session only._")
    )
    ss.messages.append(make_message("assistant", confirmation, suggestions=[
        "Estimate my monthly mortgage payment", "Show me the best property matches for my filters"]))
    st.rerun()


def render_chat() -> None:
    msgs = st.session_state.messages
    last = len(msgs) - 1
    for i, m in enumerate(msgs):
        with st.chat_message(m["role"], avatar="🏙️" if m["role"] == "assistant" else "🙋"):
            st.markdown(esc_dollar(m["content"]))
            render_cards(m.get("cards", []), f"m{i}", buttons=(i == last and m["role"] == "assistant"))
            if i == last and m["role"] == "assistant":
                if m.get("widget") == "booking":
                    render_lead_form()
                sugg = m.get("suggestions", [])[:4]
                if sugg:
                    cols = st.columns(len(sugg))
                    for j, (col, s) in enumerate(zip(cols, sugg)):
                        col.button(s, key=f"chip_{i}_{j}", on_click=queue_prompt, args=(s,), **_STRETCH)
            st.markdown(f'<span class="pe-ts">{m["ts"]}</span>', unsafe_allow_html=True)


def render_matches_tab() -> None:
    prefs = filters_to_prefs(current_filters())
    results = match_properties(prefs)
    exact = [m for m in results if m.exact]
    st.markdown(f"#### 🏢 Property matches · *{esc_dollar(describe_prefs(prefs))}*")
    if exact:
        st.success(f"{plural(len(exact), 'property')} match your filters.")
        shown = exact
    else:
        st.warning("No exact matches. Showing the closest alternatives; try widening the budget or location.")
        shown = [m for m in results if m.score > 0][:3] or results[:3]
    for start in range(0, len(shown), 3):
        row = shown[start:start + 3]
        render_cards([(m.prop.pid, m.score if prefs_active(prefs) else None) for m in row], f"tab{start}", buttons=True)
    with st.expander("📊 Table view"):
        st.dataframe([{
            "Property": m.prop.name, "Type": m.prop.ptype, "Location": m.prop.location,
            "Price (USD)": m.prop.price, "Beds": m.prop.beds, "Area (m²)": m.prop.area,
            "Yield %": m.prop.rental_yield, "Match %": m.score,
        } for m in shown], hide_index=True)


def prefs_active(prefs: dict) -> bool:
    return bool(prefs["types"] or prefs["locations"] or prefs["beds"]
                or prefs["min_price"] is not None or prefs["max_price"] is not None)


def render_requests_tab() -> None:
    leads = st.session_state.leads
    st.markdown("#### 📋 My viewing requests")
    if not leads:
        st.info("No requests yet. Ask me to *“book a viewing”* and your confirmed requests will appear here.")
        return
    st.dataframe([{k: l[k] for k in LEAD_FIELDS if k != "notes"} for l in leads], hide_index=True)
    st.download_button("⬇️ Download as CSV", leads_to_csv(leads), "primeestate_requests.csv", "text/csv")


def transcript() -> str:
    lines = [f"{APP_NAME} transcript ({datetime.now():%Y-%m-%d %H:%M})", ""]
    for m in st.session_state.messages:
        who = "Assistant" if m["role"] == "assistant" else "You"
        lines.append(f"[{m['ts']}] {who}: {m['content']}")
        lines.append("")
    return "\n".join(lines)


QUICK_ACTIONS = [
    ("🏢 Best matches", "Show me the best property matches for my filters"),
    ("📅 Book a viewing", "I'd like to schedule a viewing"),
    ("💳 Mortgage estimate", "Estimate my monthly mortgage payment"),
    ("📍 Explore locations", "Tell me about the locations"),
    ("📈 Investment picks", "Which properties have the best rental yield?"),
    ("🤝 Talk to an advisor", "I'd like to speak to an agent"),
]


def render_sidebar() -> None:
    sb = st.sidebar
    sb.markdown("## 🏙️ PrimeEstate")
    sb.caption("Premium residential real estate")
    sb.markdown("### 🔎 Property filters")
    sb.select_slider("Budget range (USD)", options=BUDGET_STEPS, key="f_budget", format_func=fmt_short)
    sb.multiselect("Location", LOCATION_NAMES, key="f_locations", placeholder="Any location")
    sb.multiselect("Property type", list(TYPES), key="f_types", placeholder="Any type")
    sb.selectbox("Minimum bedrooms", [0, 1, 2, 3, 4, 5, 6], key="f_beds",
                 format_func=lambda n: "Any" if n == 0 else f"{n}+")
    prefs = filters_to_prefs(current_filters())
    n_match = sum(1 for m in match_properties(prefs) if m.exact)
    sb.metric("Matching properties", f"{n_match} / {len(PROPERTIES)}")
    sb.button("↺ Reset filters", on_click=reset_filters, **_STRETCH)

    sb.markdown("### ⚡ Quick actions")
    for i, (label, prompt) in enumerate(QUICK_ACTIONS):
        sb.button(label, key=f"qa_{i}", on_click=queue_prompt, args=(prompt,), **_STRETCH)

    sb.markdown("### 💬 Conversation")
    sb.button("🧹 New conversation", on_click=clear_chat, **_STRETCH)
    sb.download_button("⬇️ Download transcript", transcript(), "primeestate_chat.txt", "text/plain", **_STRETCH)
    sb.divider()
    sb.caption(f"📞 {CONTACT_PHONE}  \n✉️ {CONTACT_EMAIL}  \n🕘 {OFFICE_HOURS}")


def render_hero() -> None:
    st.markdown(
        f'<div class="pe-hero"><h1>🏙️ {APP_NAME}</h1>'
        "<p>Property matching · budget estimates · private viewings, powered by an on-device NLP intent engine. "
        "No API keys. No data leaves this app.</p></div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="🏙️", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()

    typed = st.chat_input("Ask about properties, budgets, financing or viewings…", max_chars=MAX_INPUT_CHARS)
    queued, st.session_state.pending_prompt = st.session_state.pending_prompt, None
    prompt = queued or typed
    if prompt:
        handle_user_message(prompt)

    render_sidebar()
    render_hero()
    tab_chat, tab_matches, tab_requests = st.tabs(["💬 Assistant", "🏢 Property matches", "📋 My requests"])
    with tab_chat:
        render_chat()
    with tab_matches:
        render_matches_tab()
    with tab_requests:
        render_requests_tab()
    st.caption("PrimeEstate AI Assistant is a demo built for the CodeAlpha Cloud Computing internship. "
               "Listings and contact details are illustrative. Estimates are not financial or legal advice.")


if __name__ == "__main__":
    main()
