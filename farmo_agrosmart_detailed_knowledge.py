"""
AgroSmart AI - Offline Smart Farming Assistant

Core text answers and the farm-profit calculator run locally without API keys.
Optional voice recognition uses SpeechRecognition and may require internet.

Install the optional voice packages:
    pip install SpeechRecognition sounddevice numpy
"""

import difflib
import os
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import queue
from collections import deque

import numpy as np
import speech_recognition as sr

try:
    import sounddevice as sd      # replaces PyAudio (ships its own PortAudio on Windows/macOS)
except (ImportError, OSError):    # OSError: PortAudio library missing (some Linux setups)
    sd = None


# ---------- SETTINGS ----------
AI_MODEL = "claude-sonnet-5-5"   # change if you prefer another Claude model
LISTEN_TIMEOUT = 8               # seconds to wait for speech to start
PHRASE_LIMIT = 25                # max seconds of one spoken question
SAMPLE_RATE = 16000              # Hz, mono, 16-bit - what Google recognition expects
BLOCK_SECONDS = 0.05             # size of each audio chunk read from the mic
MIN_ENERGY = 250                 # floor for the speech-detection threshold
LISTEN_ATTEMPTS = 2              # automatic retry if nothing was understood

# ---------- COLORS ----------
BG = "#eef8f4"
DARK = "#1e293b"
GREEN = "#16a34a"
GREEN_DARK = "#15803d"
WHITE = "#ffffff"
MUTED = "#64748b"
PURPLE = "#5b4bea"
RED = "#dc2626"


# =====================================================================
#  KNOWLEDGE BASE  (English + Tamil)
# =====================================================================
KB = []


def _add(eid, kind, name_en, name_ta, keywords, en, ta):
    KB.append({
        "id": eid, "kind": kind, "name": {"en": name_en, "ta": name_ta},
        "kw": [k.lower() for k in keywords], "en": en, "ta": ta,
    })


# ---- crops ----
_add("tomato", "crop", "Tomato", "தக்காளி",
     ["tomato", "tomatoes", "தக்காளி"],
     ["Grow in well-drained soil, stake the plants and water at the base (drip is ideal) so leaves stay dry.",
      "Common problems: early/late blight (spots and browning), leaf curl virus spread by whitefly, fruit borer and bacterial wilt.",
      "Rotate with non-solanaceous crops (not tomato, brinjal, chilli or potato) for 2-3 seasons to cut soil-borne disease.",
      "Fertilize by soil test. Too much nitrogen gives leaves but fewer fruits; even watering helps prevent blossom-end rot.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["நல்ல வடிகால் உள்ள மண்ணில் பயிரிடுங்கள்; செடிகளுக்கு குச்சி கட்டி, இலைகளை நனைக்காமல் வேரில் நீர் பாய்ச்சுங்கள் (சொட்டுநீர் சிறந்தது).",
      "பொதுவான பிரச்சனைகள்: இலை கருகல் (ஏர்லி/லேட் ப்ளைட்), வெள்ளை ஈ மூலம் பரவும் இலை சுருட்டை வைரஸ், காய்த்துளைப்பான், பாக்டீரியா வாடல்.",
      "தக்காளி, கத்திரி, மிளகாய், உருளை ஆகியவற்றை தொடர்ந்து பயிரிடாமல் 2-3 பருவங்களுக்கு பயிர் சுழற்சி செய்யுங்கள்.",
      "மண் பரிசோதனைப்படி உரமிடுங்கள்; அதிக தழைச்சத்து இலையை மட்டும் வளர்க்கும்; சீரான நீர் காய் அடிப்பகுதி அழுகலைக் குறைக்கும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])


_add("tomato_flower_drop", "topic", "Tomato flower drop", "தக்காளிப் பூ உதிர்வு",
     ["tomato flowers falling", "flowers falling from tomato plants", "tomato flower drop",
      "tomato blossoms dropping", "tomato flowers dropping", "tomato flowers fall",
      "flowers falling tomato", "tomato not setting fruit", "tomato flowers but no fruit",
      "தக்காளிப் பூ உதிர்வு", "தக்காளி பூக்கள் உதிர்கின்றன"],
     ["Tomato flowers commonly drop when temperatures are too hot or too cold; hot days and warm nights can prevent pollen from working properly.",
      "Uneven watering, drought, waterlogged roots, excess nitrogen fertilizer (many leaves but few fruits), and poor pollination can also cause flower drop. Thrips or other pests may contribute.",
      "What to try: keep soil moisture even (not soggy), mulch to reduce moisture swings, avoid heavy nitrogen feeding, and follow a locally recommended tomato fertilizer schedule. During very hot weather, provide suitable afternoon shade if practical and keep plants well ventilated.",
      "Check the pattern: if many flowers drop during a heat wave, temperature is a likely cause; if plants are lush and leafy with few fruits, excess nitrogen may be involved; if soil alternates between very dry and wet, watering stress may be involved.",
      "Do not spray pesticides just because flowers fall. First inspect leaves, buds and flowers for pests, and use only locally approved products when a pest is identified. For a more specific suggestion, provide your location, daytime/night temperatures if known, watering routine, and fertilizer used.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["தக்காளியில் அதிக வெப்பம் அல்லது அதிக குளிரால் பூக்கள் உதிரலாம். குறிப்பாக பகல் வெப்பமும் இரவு வெப்பமும் அதிகமாக இருந்தால் மகரந்தம் சரியாகச் செயல்படாமல் போகலாம்.",
      "ஒழுங்கற்ற நீர்ப்பாசனம், வறட்சி, வேர் பகுதியில் நீர் தேங்குதல், அதிக தழைச்சத்து உரம் (இலைகள் அதிகம்; காய்கள் குறைவு), மகரந்தச் சேர்க்கை குறைவு ஆகியவையும் காரணமாகலாம். திரிப்ஸ் போன்ற பூச்சிகளும் பாதிக்கலாம்.",
      "என்ன செய்யலாம்: மண்ணின் ஈரத்தைச் சீராக வைத்துக் கொள்ளுங்கள்; நீர் தேங்க விடாதீர்கள். ஈரப்பதம் மாறுபடுவதை குறைக்க மூடாக்கு இடலாம். அதிக தழைச்சத்து உரத்தைத் தவிர்த்து, உள்ளூர் பரிந்துரைப்படி உரமிடுங்கள். கடும் வெப்பத்தில் சாத்தியமானால் மதிய நேரத்தில் லேசான நிழல் கொடுத்து காற்றோட்டம் இருக்கச் செய்யுங்கள்.",
      "அறிகுறியைப் பாருங்கள்: வெப்ப அலைக்குப் பிறகு பல பூக்கள் உதிர்ந்தால் வெப்பம் காரணமாக இருக்கலாம்; இலைகள் செழித்து காய்கள் குறைந்தால் அதிக தழைச்சத்து காரணமாக இருக்கலாம்; மண் மாறி மாறி மிகவும் காய்ந்தும் ஈரமாகியும் இருந்தால் நீர்ப்பாசன அழுத்தம் காரணமாக இருக்கலாம்.",
      "பூ உதிர்வதற்காக மட்டும் பூச்சிக்கொல்லி தெளிக்க வேண்டாம். முதலில் இலை, மொட்டு, பூக்களில் பூச்சி உள்ளதா பாருங்கள். குறிப்பிட்ட ஆலோசனைக்கு உங்கள் பகுதி, தெரிந்தால் பகல்/இரவு வெப்பநிலை, நீர்ப்பாசன முறை, பயன்படுத்திய உரம் ஆகியவற்றைச் சொல்லுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("rice", "crop", "Rice / Paddy", "நெல்",
     ["rice", "paddy", "samba", "kuruvai", "thaladi", "navarai", "நெல்", "அரிசி", "சம்பா", "குறுவை", "தாளடி", "நவரை"],
     ["Typical Tamil Nadu seasons: Kuruvai (~Jun-Sep), Samba (~Aug-Jan), Thaladi (~Sep/Oct-Jan/Feb), Navarai (~Dec-Apr). Dates vary by district and variety.",
      "Keep shallow water (2-5 cm) in early growth. Alternate wetting and drying can save water where water control is good.",
      "Watch for blast (diamond-shaped leaf spots), brown spot, bacterial leaf blight, stem borer, brown planthopper and leaf folder. Excess nitrogen raises blast and planthopper risk.",
      "Split nitrogen into 2-3 doses based on soil test or leaf colour chart, and keep the field weed-free early on.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["தமிழகப் பருவங்கள்: குறுவை (சுமார் ஜூன்-செப்.), சம்பா (ஆக.-ஜன.), தாளடி (செப்./அக்.-ஜன./பிப்.), நவரை (டிச.-ஏப்.). மாவட்டம், ரகத்தைப் பொறுத்து தேதிகள் மாறும்.",
      "ஆரம்ப வளர்ச்சியில் 2-5 செ.மீ ஆழ நீர் வைக்கவும்; நீர் மேலாண்மை வசதி இருந்தால் மாற்று ஈரம்-உலர்வு முறை நீரைச் சேமிக்கும்.",
      "குலை நோய் (வைர வடிவ புள்ளிகள்), பழுப்புப் புள்ளி, இலைக் கருகல், தண்டு துளைப்பான், பழுப்பு தத்துப்பூச்சி, இலை மடக்குப் புழு ஆகியவற்றைக் கவனியுங்கள். அதிக தழைச்சத்து குலை நோய், தத்துப்பூச்சி அபாயத்தை அதிகரிக்கும்.",
      "தழைச்சத்தை 2-3 முறை பிரித்து இடவும் (மண் பரிசோதனை / இலை வண்ண அட்டை அடிப்படையில்); ஆரம்பத்தில் களையின்றி வைக்கவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])

_add("groundnut", "crop", "Groundnut", "நிலக்கடலை",
     ["groundnut", "ground nut", "peanut", "நிலக்கடலை", "மணிலா"],
     ["Prefers well-drained sandy loam; waterlogging causes pod rot.",
      "Gypsum at flowering/pegging (around 40-45 days) is commonly recommended for pod filling; follow soil test and local advice.",
      "Watch for leaf spot, rust, collar rot, leaf miner and aphids. Avoid moisture stress at flowering and pod formation.",
      "Harvest at maturity and dry pods thoroughly before storage to avoid aflatoxin.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["நல்ல வடிகால் உள்ள மணற்பாங்கான களிமண் ஏற்றது; நீர் தேங்கினால் காய்கள் அழுகும்.",
      "பூக்கும்/காய் பிடிக்கும் காலத்தில் (சுமார் 40-45 நாள்) ஜிப்சம் இடுவது பொதுவாகப் பரிந்துரைக்கப்படுகிறது; மண் பரிசோதனை/உள்ளூர் ஆலோசனைப்படி செய்யுங்கள்.",
      "இலைப்புள்ளி, துரு, கழுத்து அழுகல், இலை சுரங்கப்புழு, அசுவினி ஆகியவற்றைக் கவனியுங்கள்; பூக்கும் மற்றும் காய் உருவாகும் நிலையில் நீர் பற்றாக்குறை கூடாது.",
      "முதிர்ச்சியில் அறுவடை செய்து, சேமிக்கும் முன் காய்களை நன்கு உலர்த்தவும் (அஃப்ளாடாக்சின் தவிர்க்க).",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])

_add("sugarcane", "crop", "Sugarcane", "கரும்பு",
     ["sugarcane", "sugar cane", "கரும்பு"],
     ["Use disease-free setts from healthy seed cane and treat them as locally recommended.",
      "Needs regular irrigation, especially during tillering and grand growth; drip with fertigation improves water-use efficiency.",
      "Watch for red rot (red internal tissue, sour smell), early shoot borer, internode borer and woolly aphid. Remove and destroy affected clumps.",
      "Trash mulching conserves moisture; timely earthing-up reduces lodging.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["நோயற்ற, ஆரோக்கியமான விதைக் கரணைகளைப் பயன்படுத்துங்கள்; உள்ளூர் பரிந்துரைப்படி கரணை நேர்த்தி செய்யுங்கள்.",
      "தூர் பிடிக்கும் மற்றும் வேகமாக வளரும் நிலைகளில் தொடர்ந்து நீர் தேவை; சொட்டுநீர் உரப்பாசனம் நீர் பயன்பாட்டுத் திறனை உயர்த்தும்.",
      "செவ்வழுகல் (தண்டுக்குள் சிவப்பு நிறம், புளிப்பு மணம்), இளங்குருத்துப் புழு, கணுப்புழு, கம்பளி அசுவினி ஆகியவற்றைக் கவனியுங்கள்; பாதித்த தூர்களை அகற்றி அழிக்கவும்.",
      "சருகு மூடாக்கு ஈரத்தைப் பாதுகாக்கும்; உரிய நேரத்தில் மண் அணைப்பது சாய்வதைக் குறைக்கும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])

_add("banana", "crop", "Banana", "வாழை",
     ["banana", "plantain", "வாழை"],
     ["Use healthy tissue-culture plants in well-drained land; avoid waterlogging.",
      "Needs steady moisture; drip irrigation and mulching are recommended.",
      "Watch for Panama (Fusarium) wilt - yellowing of older leaves and split pseudostem - plus Sigatoka leaf spot, rhizome weevil and nematodes. Do not move soil or suckers out of infected plots.",
      "Remove excess suckers and dry leaves, and prop heavy bunches against wind.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["ஆரோக்கியமான திசு வளர்ப்புக் கன்றுகளை வடிகால் உள்ள நிலத்தில் நடவும்; நீர் தேங்கக் கூடாது.",
      "சீரான ஈரப்பதம் அவசியம்; சொட்டுநீர் மற்றும் மூடாக்கு பரிந்துரைக்கப்படுகிறது.",
      "பனாமா வாடல் (கீழ் இலைகள் மஞ்சளாதல், தண்டு பிளவு), சிகடோகா இலைப்புள்ளி, கிழங்கு கூன்வண்டு, நூற்புழுக்களைக் கவனியுங்கள்; பாதித்த தோட்டத்தின் மண்/கன்றுகளை வேறு இடத்துக்கு எடுத்துச் செல்லாதீர்கள்.",
      "கூடுதல் பக்கக் கன்றுகள், உலர்ந்த இலைகளை அகற்றி, காற்றில் சாயாமல் தார்களுக்கு முட்டுக் கொடுக்கவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])

_add("cotton", "crop", "Cotton", "பருத்தி",
     ["cotton", "பருத்தி"],
     ["Choose well-drained land and sow at the locally recommended time.",
      "Scout weekly for pink bollworm, whitefly, aphids, jassids and mealybug; pheromone traps help monitor bollworm.",
      "Avoid excess nitrogen and avoid water stress at flowering and boll formation; ensure drainage.",
      "Use IPM, rotate crops and destroy crop residue after harvest to cut pink bollworm carry-over.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["நல்ல வடிகால் உள்ள நிலம்; உள்ளூர் பரிந்துரைப்படி உரிய பருவத்தில் விதைக்கவும்.",
      "இளஞ்சிவப்பு காய்ப்புழு, வெள்ளை ஈ, அசுவினி, தத்துப்பூச்சி, மாவுப்பூச்சி ஆகியவற்றை வாரந்தோறும் கண்காணியுங்கள்; காய்ப்புழுவைக் கண்காணிக்க இனக்கவர்ச்சிப் பொறி உதவும்.",
      "அதிக தழைச்சத்தையும், பூக்கும்/காய் உருவாகும் காலத்தில் நீர் பற்றாக்குறையையும் தவிர்க்கவும்; நீர் தேங்காமல் பார்த்துக் கொள்ளவும்.",
      "ஒருங்கிணைந்த பூச்சி மேலாண்மை, பயிர் சுழற்சி, அறுவடைக்குப் பின் பயிர்க் கழிவுகளை அழித்தல் ஆகியவை இளஞ்சிவப்பு காய்ப்புழுவைக் குறைக்கும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])

_add("maize", "crop", "Maize", "மக்காச்சோளம்",
     ["maize", "corn", "மக்காச்சோளம்", "மக்காசோளம்"],
     ["Fall armyworm is a major pest: ragged leaf holes and sawdust-like droppings in the whorl. Scout early and contact your agriculture officer promptly.",
      "Needs good drainage. Water is most critical at tasseling/silking and grain filling.",
      "Split nitrogen doses; weed control in the first 30-45 days is critical.",
      "Harvest when kernels are hard and husks dry; dry grain to about 13-14% moisture before storage.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["படைப்புழு முக்கிய பூச்சி: இலைகளில் ஒழுங்கற்ற துளைகள், குருத்தில் மரத்தூள் போன்ற கழிவு. ஆரம்பத்திலேயே கண்காணித்து வேளாண் அலுவலரை உடனே அணுகுங்கள்.",
      "நல்ல வடிகால் தேவை; ஆண்பூ/பட்டு வெளிவரும் மற்றும் மணி பிடிக்கும் நிலைகளில் நீர் மிக முக்கியம்.",
      "தழைச்சத்தைப் பிரித்து இடவும்; முதல் 30-45 நாட்களில் களை கட்டுப்பாடு முக்கியம்.",
      "மணிகள் கடினமாகி உறை உலர்ந்ததும் அறுவடை செய்து, சேமிக்கும் முன் தானியத்தை சுமார் 13-14% ஈரப்பதம் வரை உலர்த்தவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])

_add("chilli", "crop", "Chilli", "மிளகாய்",
     ["chilli", "chili", "chillies", "மிளகாய்"],
     ["Common problems: leaf curl (thrips, mites, whitefly/virus), fruit rot/anthracnose (sunken dark spots) and damping-off in nurseries. Use well-drained nursery beds and healthy seed.",
      "Irrigate regularly without waterlogging; heat or water stress can cause flower and fruit drop.",
      "Rotate crops, remove infected fruits and pick regularly.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["இலை சுருட்டை (இலைப்பேன், சிலந்தி, வெள்ளை ஈ/வைரஸ்), காய் அழுகல்/ஆந்த்ராக்னோஸ் (கரும் குழி புள்ளிகள்), நாற்றங்காலில் நாற்றழுகல் ஆகியவை பொதுவானவை; வடிகால் உள்ள நாற்றங்கால், ஆரோக்கிய விதை பயன்படுத்துங்கள்.",
      "நீர் தேங்காமல் தொடர்ந்து பாசனம் செய்யுங்கள்; வெப்பம் அல்லது நீர் அழுத்தத்தால் பூ/காய் உதிரலாம்.",
      "பயிர் சுழற்சி செய்யுங்கள்; பாதித்த காய்களை அகற்றி, தொடர்ந்து பறிக்கவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])

_add("coconut", "crop", "Coconut", "தென்னை",
     ["coconut", "coconuts", "தென்னை", "தேங்காய்"],
     ["Watch for red palm weevil, rhinoceros beetle, eriophyid mite (white triangular patches on nuts), bud rot and root (wilt) disease.",
      "Use basin or drip irrigation, mulch with husk, and apply regular organic manure plus nutrients (potash is commonly advised).",
      "Keep the crown clean and remove dead fronds; report sudden crown wilting to the agriculture/horticulture officer quickly.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["செம்பனை மூக்குவண்டு, காண்டாமிருக வண்டு, எரியோபைட் சிலந்தி (காய்களில் வெண்ணிற முக்கோணத் திட்டுகள்), குருத்தழுகல், வேர்வாடல் ஆகியவற்றைக் கவனியுங்கள்.",
      "பாத்தி/சொட்டுநீர் பாசனம்; தேங்காய் மட்டையால் மூடாக்கு; தொடர்ந்து இயற்கை எருவுடன் தேவையான சத்துகள் (குறிப்பாக பொட்டாஷ்) இடுவது பொதுவாகப் பரிந்துரைக்கப்படுகிறது.",
      "குருத்துப் பகுதியைச் சுத்தமாக வைத்து, காய்ந்த மட்டைகளை அகற்றுங்கள்; குருத்து திடீரென வாடினால் உடனே வேளாண்/தோட்டக்கலை அலுவலரிடம் தெரிவியுங்கள்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])

_add("millets", "crop", "Millets (Ragi, Cholam, Kambu)", "சிறுதானியங்கள்",
     ["millet", "millets", "ragi", "finger millet", "sorghum", "cholam", "kambu", "bajra",
      "கேழ்வரகு", "ராகி", "சோளம்", "கம்பு", "சிறுதானிய"],
     ["Hardy, low-water crops suited to rainfed farming; use local varieties and correct spacing.",
      "Watch for blast in ragi, downy mildew in pearl millet and shoot fly in sorghum. Use certified, treated seed, resistant varieties and timely sowing.",
      "Need less fertilizer than rice; use organic manure plus soil-test advice, and intercrop with pulses.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["வறட்சியைத் தாங்கும், குறைந்த நீரில் வளரும் பயிர்கள்; மானாவாரிக்கு ஏற்றவை. உள்ளூர் ரகங்கள், சரியான இடைவெளியைப் பின்பற்றுங்கள்.",
      "கேழ்வரகில் குலை நோய், கம்பில் டவுனி மில்டியூ நோய், சோளத்தில் தண்டு ஈ ஆகியவற்றைக் கவனியுங்கள்; சான்று பெற்ற நேர்த்தி செய்த விதை, எதிர்ப்பு ரகங்கள், உரிய நேர விதைப்பு பயன்படுத்துங்கள்.",
      "அரிசியை விடக் குறைவான உரம் போதும்; இயற்கை எரு மற்றும் மண் பரிசோதனைப்படி இடவும்; பயறு வகைகளுடன் ஊடுபயிர் செய்யலாம்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])

# ---- additional vegetables, fruits and field crops ----
_add("brinjal", "crop", "Brinjal / Eggplant", "கத்திரிக்காய்",
     ["brinjal", "eggplant", "aubergine", "கத்திரி", "கத்திரிக்காய்"],
     ["Use healthy seedlings and well-drained soil; keep plants evenly watered.", "Monitor shoot and fruit borer: wilted shoot tips and holes in fruits. Remove and destroy affected shoots/fruits; use pheromone traps where recommended.", "Rotate with crops outside the tomato family and avoid excessive nitrogen.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["ஆரோக்கியமான நாற்றுகளை வடிகால் உள்ள மண்ணில் நடவு செய்து சீராக நீர் பாய்ச்சுங்கள்.", "தண்டு மற்றும் காய்த்துளைப்பானைக் கண்காணிக்கவும்; வாடிய நுனித்தண்டுகள், துளையுள்ள காய்களை அகற்றி அழிக்கவும். பரிந்துரைக்கப்பட்டால் இனக்கவர்ச்சிப் பொறி பயன்படுத்தவும்.", "தக்காளி குடும்பமல்லாத பயிர்களுடன் சுழற்சி செய்யுங்கள்; அதிக தழைச்சத்தைத் தவிர்க்கவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("okra", "crop", "Okra / Lady's Finger", "வெண்டைக்காய்",
     ["okra", "lady's finger", "bhindi", "வெண்டை", "வெண்டைக்காய்"],
     ["Sow in warm weather in well-drained soil; harvest young pods regularly.", "Watch for yellow vein mosaic virus, whitefly, jassids and fruit borer. Remove severely diseased plants and manage whiteflies early.", "Avoid waterlogging and follow local soil-test fertilizer advice.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["வெப்பமான காலத்தில் வடிகால் உள்ள மண்ணில் விதைத்து, இளங்காய்களைத் தொடர்ந்து பறிக்கவும்.", "மஞ்சள் நரம்பு தேமல் வைரஸ், வெள்ளை ஈ, தத்துப்பூச்சி, காய்த்துளைப்பானைக் கவனியுங்கள். கடுமையாகப் பாதித்த செடிகளை அகற்றி, வெள்ளை ஈயை ஆரம்பத்திலேயே கட்டுப்படுத்துங்கள்.", "நீர் தேங்குவதைத் தவிர்த்து, மண் பரிசோதனைப்படி உரமிடுங்கள்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("onion", "crop", "Onion", "வெங்காயம்",
     ["onion", "onions", "வெங்காயம்", "சின்ன வெங்காயம்", "shallot"],
     ["Use healthy seedlings or sets and a loose, well-drained soil; avoid waterlogging.", "Thrips cause silvery streaks and leaf drying; purple blotch causes purple lesions. Monitor early and seek local advice if damage spreads.", "Reduce irrigation as bulbs mature; cure bulbs in shade with good airflow before storage.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["ஆரோக்கியமான நாற்று/கிழங்குகளைப் பயன்படுத்தி, இலகுவான வடிகால் மண்ணில் நடவும்; நீர் தேங்கக்கூடாது.", "இலைப்பேன் வெள்ளி நிறக் கோடுகளையும் இலை உலர்வையும் உண்டாக்கும்; ஊதா புள்ளி நோயில் ஊதா காயங்கள் தோன்றும். ஆரம்பத்திலேயே கண்காணித்து, பாதிப்பு அதிகரித்தால் உள்ளூர் ஆலோசனை பெறுங்கள்.", "கிழங்கு முதிரும்போது பாசனத்தைக் குறைத்து, சேமிப்புக்கு முன் நிழலில் காற்றோட்டத்துடன் உலர்த்தவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("potato", "crop", "Potato", "உருளைக்கிழங்கு",
     ["potato", "potatoes", "உருளைக்கிழங்கு"],
     ["Plant certified, healthy seed tubers in loose, well-drained soil and earth up around plants.", "Late blight can spread quickly in cool, humid weather; look for water-soaked dark leaf patches and act promptly with local agricultural advice.", "Keep tubers covered from sunlight and cure/dry them before suitable storage.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["சான்றளிக்கப்பட்ட ஆரோக்கிய விதைக் கிழங்குகளை இலகுவான வடிகால் மண்ணில் நடவு செய்து, செடிகளைச் சுற்றி மண் அணைக்கவும்.", "குளிர், ஈரமான காலத்தில் லேட் ப்ளைட் வேகமாகப் பரவும்; இலைகளில் நீர் நனைந்ததுபோன்ற கரும்புள்ளிகள் தோன்றினால் உடனே வேளாண் ஆலோசனை பெறுங்கள்.", "கிழங்குகள் சூரிய ஒளியில் பச்சையாகாமல் மூடி வைத்து, சரியான சேமிப்புக்கு முன் உலர்த்தவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("garlic", "crop", "Garlic", "பூண்டு",
     ["garlic", "பூண்டு"],
     ["Use healthy cloves and well-drained soil; plant cloves at locally recommended spacing.", "Avoid excess irrigation and waterlogging. Monitor thrips and leaf diseases.", "Harvest when leaves yellow and begin drying; cure bulbs in a dry, airy shaded place.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["ஆரோக்கியமான பூண்டுப் பற்களை வடிகால் உள்ள மண்ணில் பரிந்துரைக்கப்பட்ட இடைவெளியில் நடவும்.", "அதிக பாசனத்தையும் நீர் தேங்குவதையும் தவிர்க்கவும்; இலைப்பேன் மற்றும் இலை நோய்களைக் கண்காணிக்கவும்.", "இலைகள் மஞ்சளாகி உலரத் தொடங்கும்போது அறுவடை செய்து, நிழலான காற்றோட்ட இடத்தில் உலர்த்தவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("cucumber", "crop", "Cucumber", "வெள்ளரிக்காய்",
     ["cucumber", "cucumbers", "வெள்ளரி", "வெள்ளரிக்காய்"],
     ["Grow in warm conditions with fertile, well-drained soil and steady moisture.", "Watch for fruit flies, aphids and powdery/downy mildew. Remove damaged fruits and avoid wetting foliage late in the day.", "Pick fruits frequently while tender; rotate away from cucurbit crops.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["வெப்பமான சூழலில் வளமான வடிகால் மண்ணிலும் சீரான ஈரத்துடனும் வளர்க்கவும்.", "காய்ப்பழ ஈ, அசுவினி, மாவுப்பூஞ்சை/டவுனி மில்டியூ நோய்களைக் கவனிக்கவும். சேதமடைந்த காய்களை அகற்றி, மாலை நேரத்தில் இலைகளை நனைப்பதைத் தவிர்க்கவும்.", "இளமையாக இருக்கும்போதே அடிக்கடி பறித்து, பூசணி குடும்பப் பயிர்களுடன் தொடர்ந்து பயிரிடாதீர்கள்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("pumpkin", "crop", "Pumpkin", "பூசணி",
     ["pumpkin", "squash", "பூசணி"],
     ["Provide space for vines, full sunlight and well-drained soil; water near the roots.", "Monitor fruit fly, aphids and powdery mildew; remove rotting fruits and keep fruits off persistently wet soil where possible.", "Harvest when the rind is firm and mature; cure and store in a dry, ventilated place.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["கொடிகள் பரவ இடம், முழு சூரிய ஒளி, வடிகால் மண் வழங்கி வேர்ப்பகுதியில் நீர் பாய்ச்சுங்கள்.", "காய்ப்பழ ஈ, அசுவினி, மாவுப்பூஞ்சை நோயைக் கண்காணிக்கவும்; அழுகிய காய்களை அகற்றி, காய்கள் ஈரமான மண்ணில் நீண்ட நேரம் படாமல் பார்த்துக்கொள்ளுங்கள்.", "தோல் உறுதியடைந்து முதிர்ந்ததும் அறுவடை செய்து, உலர்ந்த காற்றோட்ட இடத்தில் வைக்கவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("bitter_gourd", "crop", "Bitter Gourd", "பாகற்காய்",
     ["bitter gourd", "bitter melon", "பாகற்காய்"],
     ["Use a trellis, warm weather and well-drained soil; maintain even moisture.", "Fruit fly is a common problem. Collect fallen and infested fruits and dispose of them safely; use traps as locally recommended.", "Harvest tender fruits regularly and rotate away from cucurbits.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["பந்தல் அமைத்து, வெப்பமான சூழலிலும் வடிகால் மண்ணிலும் வளர்த்து சீரான ஈரம் பராமரிக்கவும்.", "காய்ப்பழ ஈ பொதுவான பிரச்சனை; விழுந்த மற்றும் பாதித்த காய்களைச் சேகரித்து பாதுகாப்பாக அழிக்கவும்; உள்ளூர் பரிந்துரைப்படி பொறிகளைப் பயன்படுத்தவும்.", "இளங்காய்களைத் தொடர்ந்து பறித்து, பூசணி குடும்பப் பயிர்களுடன் சுழற்சி செய்யுங்கள்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("bottle_gourd", "crop", "Bottle Gourd", "சுரைக்காய்",
     ["bottle gourd", "bottlegourd", "சுரைக்காய்"],
     ["Grow on a sturdy trellis with well-drained soil and regular watering.", "Check for fruit fly, aphids and mildew; remove damaged fruits and improve airflow.", "Harvest fruits while young and tender; avoid waterlogging.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["வலுவான பந்தலில் வடிகால் மண்ணிலும் சீரான பாசனத்துடனும் வளர்க்கவும்.", "காய்ப்பழ ஈ, அசுவினி, பூஞ்சை நோய்களைக் கவனித்து, சேதமடைந்த காய்களை அகற்றி காற்றோட்டம் ஏற்படுத்தவும்.", "இளமையாக இருக்கும்போதே அறுவடை செய்து, நீர் தேங்குவதைத் தவிர்க்கவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("ridge_gourd", "crop", "Ridge Gourd", "பீர்க்கங்காய்",
     ["ridge gourd", "ridged gourd", "பீர்க்கை", "பீர்க்கங்காய்"],
     ["Provide a trellis, sunlight and well-drained soil; water consistently during flowering and fruiting.", "Monitor fruit fly, red pumpkin beetle and mildew; remove damaged plant parts.", "Pick young fruits often and rotate crops.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["பந்தல், சூரிய ஒளி, வடிகால் மண் வழங்கி பூக்கும் மற்றும் காய்க்கும் காலத்தில் சீராக நீர் பாய்ச்சுங்கள்.", "காய்ப்பழ ஈ, சிவப்பு பூசணி வண்டு, பூஞ்சை நோய்களைக் கண்காணித்து பாதித்த பகுதிகளை அகற்றவும்.", "இளங்காய்களை அடிக்கடி பறித்து பயிர் சுழற்சி செய்யுங்கள்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("snake_gourd", "crop", "Snake Gourd", "புடலங்காய்",
     ["snake gourd", "புடலங்காய்"],
     ["Grow on a trellis in warm weather with fertile, well-drained soil.", "Monitor fruit fly and sucking pests; remove infested fruits and avoid excessive nitrogen.", "Keep moisture steady and harvest at the preferred tender stage.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["வெப்பமான காலத்தில் வளமான வடிகால் மண்ணில் பந்தல் அமைத்து வளர்க்கவும்.", "காய்ப்பழ ஈ மற்றும் சாறு உறிஞ்சும் பூச்சிகளைக் கண்காணித்து பாதித்த காய்களை அகற்றி, அதிக தழைச்சத்தைத் தவிர்க்கவும்.", "சீரான ஈரத்தைப் பராமரித்து, இளமையான நிலையில் அறுவடை செய்யுங்கள்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("cabbage", "crop", "Cabbage", "முட்டைக்கோஸ்",
     ["cabbage", "முட்டைக்கோஸ்"],
     ["Use healthy seedlings in cool conditions and fertile, well-drained soil; maintain steady moisture.", "Inspect leaf undersides for caterpillars, diamondback moth and aphids. Use netting or approved integrated pest management where suitable.", "Harvest firm heads before they split; rotate with non-brassica crops.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["குளிர்ச்சியான சூழலில் ஆரோக்கிய நாற்றுகளை வளமான வடிகால் மண்ணில் நடவு செய்து சீரான ஈரம் வைக்கவும்.", "இலை அடிப்பகுதியில் புழுக்கள், வைரமுதுகு அந்துப்பூச்சி, அசுவினி உள்ளதா பார்க்கவும். பொருத்தமான இடங்களில் வலை அல்லது ஒருங்கிணைந்த பூச்சி மேலாண்மை பயன்படுத்தவும்.", "தலைகள் உறுதியானதும் பிளவதற்கு முன் அறுவடை செய்து, முட்டைக்கோஸ் குடும்பமல்லாத பயிர்களுடன் சுழற்சி செய்யுங்கள்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("cauliflower", "crop", "Cauliflower", "காலிஃபிளவர்",
     ["cauliflower", "காலிஃபிளவர்"],
     ["Grow suitable varieties in the recommended season; avoid heat stress and keep soil evenly moist.", "Monitor caterpillars and black rot; use healthy seedlings and remove diseased plants.", "Harvest when the curd is compact and white, before it loosens.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["பரிந்துரைக்கப்பட்ட பருவத்தில் ஏற்ற ரகங்களை வளர்த்து, வெப்ப அழுத்தத்தைத் தவிர்த்து மண் ஈரத்தைச் சீராக வைத்திருக்கவும்.", "புழுக்கள் மற்றும் கருப்பு அழுகல் நோயைக் கண்காணித்து, ஆரோக்கிய நாற்றுகளைப் பயன்படுத்தி நோயுற்ற செடிகளை அகற்றவும்.", "பூத்தொகுதி இறுக்கமாகவும் வெண்மையாகவும் இருக்கும்போது தளர்வதற்கு முன் அறுவடை செய்யவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("carrot", "crop", "Carrot", "கேரட்",
     ["carrot", "carrots", "கேரட்"],
     ["Use loose, stone-free soil for straight roots; sow directly and thin seedlings.", "Keep moisture even to reduce cracking; avoid fresh manure just before sowing.", "Harvest when roots reach the variety's suitable size.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["நேரான வேர்கள் உருவாகக் கற்கள் இல்லாத இலகு மண்ணைப் பயன்படுத்தி நேரடியாக விதைத்து நாற்றுகளை இடைவெளிப்படுத்தவும்.", "வேர் பிளவதைத் தவிர்க்க ஈரத்தைச் சீராக வைத்துக் கொள்ளுங்கள்; விதைப்பதற்கு முன் புதிய தொழுவுரம் அதிகமாக இடாதீர்கள்.", "ரகத்திற்கேற்ற அளவு வந்ததும் அறுவடை செய்யவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("beetroot", "crop", "Beetroot", "பீட்ரூட்",
     ["beetroot", "beet", "பீட்ரூட்"],
     ["Sow directly in loose, well-drained soil and thin plants for good root development.", "Water evenly; drought followed by heavy watering can cause cracking. Monitor leaf spots.", "Harvest roots at the desired size before they become woody.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["இலகுவான வடிகால் மண்ணில் நேரடியாக விதைத்து, வேர் வளர்ச்சிக்காக செடிகளை இடைவெளிப்படுத்தவும்.", "சீராக நீர் பாய்ச்சுங்கள்; வறட்சிக்குப் பின் அதிக நீர் கொடுத்தால் வேர் பிளக்கலாம். இலைப்புள்ளிகளைக் கண்காணிக்கவும்.", "மரத்தன்மை ஏற்படுவதற்கு முன் தேவையான அளவில் அறுவடை செய்யவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("amaranth", "crop", "Amaranth / Leafy Greens", "அரைக்கீரை / கீரைகள்",
     ["amaranth", "spinach", "leafy greens", "keerai", "கீரை", "அரைக்கீரை", "பசலைக்கீரை", "முளைக்கீரை"],
     ["Sow in fertile soil with good drainage; keep moisture steady for tender leaves.", "Use clean irrigation water and harvest hygienically; monitor leaf-eating caterpillars and leaf spots.", "Harvest outer leaves or cut at the appropriate young stage; avoid repeated harvesting from unhealthy plants.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["வளமான வடிகால் மண்ணில் விதைத்து, மென்மையான இலைகளுக்குச் சீரான ஈரம் பராமரிக்கவும்.", "சுத்தமான பாசன நீரைப் பயன்படுத்தி சுகாதாரமாக அறுவடை செய்யுங்கள்; இலை உண்ணும் புழுக்கள் மற்றும் இலைப்புள்ளிகளைக் கண்காணிக்கவும்.", "வெளிப்புற இலைகளைப் பறிக்கவும் அல்லது இளம் நிலையில் அறுவடை செய்யவும்; நோயுற்ற செடிகளில் மீண்டும் மீண்டும் அறுவடை செய்யாதீர்கள்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("beans", "crop", "Beans", "பீன்ஸ்",
     ["beans", "green bean", "french bean", "பீன்ஸ்"],
     ["Provide a suitable trellis for climbing varieties and well-drained soil.", "Avoid waterlogging; monitor aphids, pod borers and fungal leaf diseases.", "Pick pods regularly while tender and rotate with non-legume crops.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["ஏறும் ரகங்களுக்கு பந்தல் அமைத்து வடிகால் மண் வழங்கவும்.", "நீர் தேங்குவதைத் தவிர்த்து, அசுவினி, காய்த்துளைப்பான், இலைப் பூஞ்சை நோய்களைக் கண்காணிக்கவும்.", "இளமையான காய்களைத் தொடர்ந்து பறித்து, பயறு அல்லாத பயிர்களுடன் சுழற்சி செய்யுங்கள்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("peas", "crop", "Peas", "பட்டாணி",
     ["pea", "peas", "பட்டாணி"],
     ["Peas prefer cool weather and well-drained soil; use healthy seed and support tall varieties.", "Avoid waterlogging and excessive nitrogen; legumes can fix nitrogen when properly nodulated.", "Harvest pods at the tender stage and monitor powdery mildew and pod borers.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["பட்டாணிக்கு குளிர்ச்சியான காலமும் வடிகால் மண்ணும் ஏற்றவை; ஆரோக்கிய விதை பயன்படுத்தி உயரமான ரகங்களுக்கு ஆதரவு கொடுக்கவும்.", "நீர் தேங்குதல், அதிக தழைச்சத்து ஆகியவற்றைத் தவிர்க்கவும்; வேர் முடிச்சுகள் நன்றாக இருந்தால் பயறு வகைகள் தழைச்சத்தை நிலைநிறுத்தும்.", "இளமையான நிலையில் காய்களை அறுவடை செய்து மாவுப்பூஞ்சை, காய்த்துளைப்பானைக் கண்காணிக்கவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("watermelon", "crop", "Watermelon", "தர்பூசணி",
     ["watermelon", "தர்பூசணி"],
     ["Needs warm weather, sunlight and well-drained soil; avoid overwatering as fruits mature.", "Monitor fruit fly, aphids and wilt; remove damaged fruits and rotate crops.", "Use maturity indicators such as a dried tendril near the fruit and a yellow ground spot; confirm by variety and local practice.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["வெப்பமான காலம், சூரிய ஒளி, வடிகால் மண் தேவை; காய்கள் முதிரும்போது அதிக பாசனத்தைத் தவிர்க்கவும்.", "காய்ப்பழ ஈ, அசுவினி, வாடல் நோயைக் கண்காணித்து பாதித்த காய்களை அகற்றி பயிர் சுழற்சி செய்யுங்கள்.", "காய்க்கருகிலுள்ள கொடி நுனி உலர்தல், தரையில் படும் பகுதி மஞ்சளாதல் போன்ற முதிர்ச்சி அறிகுறிகளை ரகம் மற்றும் உள்ளூர் முறையுடன் ஒப்பிட்டு அறுவடை செய்யுங்கள்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("papaya", "crop", "Papaya", "பப்பாளி",
     ["papaya", "பப்பாளி"],
     ["Plant healthy seedlings in warm, frost-free, well-drained soil; papaya is very sensitive to waterlogging.", "Watch for papaya ringspot virus, mites and mealybugs. Remove severely virus-affected plants and control weeds/alternate hosts as locally advised.", "Avoid damaging roots and support plants in windy locations.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["வெப்பமான, பனியில்லாத, வடிகால் மண்ணில் ஆரோக்கிய நாற்றுகளை நடவும்; பப்பாளிக்கு நீர் தேங்குவது மிகவும் தீங்கு.", "பப்பாளி வளையப்புள்ளி வைரஸ், சிலந்தி, மாவுப்பூச்சிகளைக் கவனிக்கவும். கடுமையாக வைரஸ் பாதித்த செடிகளை அகற்றி, உள்ளூர் ஆலோசனைப்படி களைகள்/மாற்று தாவரங்களை கட்டுப்படுத்தவும்.", "வேர்களைச் சேதப்படுத்தாதீர்கள்; காற்று அதிகமுள்ள இடங்களில் செடிகளுக்கு ஆதரவு கொடுக்கவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("mango", "crop", "Mango", "மாம்பழம் / மாமரம்",
     ["mango", "mangoes", "மாம்பழம்", "மாமரம்"],
     ["Choose a locally suitable variety and well-drained site; young trees need establishment watering, while mature trees need careful moisture management.", "Monitor hopper, fruit fly, powdery mildew and anthracnose, especially around flowering and fruiting.", "Prune only as appropriate for the tree and season; collect fallen infested fruits and seek local advice before spraying.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["உள்ளூருக்கு ஏற்ற ரகத்தையும் வடிகால் நிலத்தையும் தேர்ந்தெடுக்கவும்; இளம் மரங்களுக்கு நிலைபெறும் வரை நீர் தேவை, முதிர்ந்த மரங்களில் ஈரத்தைச் சரியாக நிர்வகிக்கவும்.", "பூக்கும்/காய்க்கும் காலங்களில் மாம்பூச்சி, காய்ப்பழ ஈ, மாவுப்பூஞ்சை, ஆந்த்ராக்னோஸ் நோய்களைக் கண்காணிக்கவும்.", "மரம் மற்றும் பருவத்திற்கேற்ற முறையில் மட்டுமே கவாத்து செய்யவும்; பாதித்த விழுந்த காய்களை அகற்றி தெளிப்பதற்கு முன் உள்ளூர் ஆலோசனை பெறவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("turmeric", "crop", "Turmeric", "மஞ்சள்",
     ["turmeric", "மஞ்சள்"],
     ["Use healthy rhizomes and loose, well-drained soil rich in organic matter; mulch after planting.", "Maintain moisture without waterlogging; watch for rhizome rot and leaf spot.", "Harvest when leaves yellow and dry; cure and dry rhizomes using locally recommended methods.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["ஆரோக்கியமான விதைக்கிழங்குகளை இயற்கைச் சத்து நிறைந்த இலகு வடிகால் மண்ணில் நடவு செய்து மூடாக்கு இடவும்.", "நீர் தேங்காமல் ஈரம் பராமரிக்கவும்; கிழங்கு அழுகல், இலைப்புள்ளி நோய்களைக் கண்காணிக்கவும்.", "இலைகள் மஞ்சளாகி உலரும்போது அறுவடை செய்து, உள்ளூர் பரிந்துரைப்படி வேகவைத்து/உலர்த்தவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("ginger", "crop", "Ginger", "இஞ்சி",
     ["ginger", "இஞ்சி"],
     ["Plant healthy seed rhizomes in loose, fertile, well-drained soil and mulch well.", "Rhizome rot is serious in waterlogged soil; ensure drainage and avoid moving contaminated soil.", "Harvest according to the intended use and maturity; dry/store only healthy rhizomes.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["ஆரோக்கிய விதைக்கிழங்குகளை வளமான இலகு வடிகால் மண்ணில் நடவு செய்து நன்றாக மூடாக்கு இடவும்.", "நீர் தேங்கும் மண்ணில் கிழங்கு அழுகல் கடுமையாகும்; வடிகால் ஏற்படுத்தி பாதித்த மண்ணை எடுத்துச் செல்லாதீர்கள்.", "பயன்பாடு மற்றும் முதிர்ச்சிக்கேற்ப அறுவடை செய்து ஆரோக்கியமான கிழங்குகளை மட்டுமே உலர்த்தி சேமிக்கவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("soybean", "crop", "Soybean", "சோயாபீன்",
     ["soybean", "soya bean", "சோயாபீன்"],
     ["Sow at the locally recommended monsoon window in well-drained soil; use certified seed and suitable rhizobium inoculant if advised.", "Avoid waterlogging; monitor girdle beetle, stem fly, defoliators and yellow mosaic/other local diseases.", "Harvest when most pods mature and dry; prevent grain moisture and damage during storage.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["உள்ளூர் பரிந்துரைக்கப்பட்ட மழைக்காலத்தில் வடிகால் மண்ணில் சான்று பெற்ற விதையை விதைக்கவும்; பரிந்துரைத்தால் ரைசோபியம் உயிருரம் பயன்படுத்தவும்.", "நீர் தேங்குவதைத் தவிர்த்து, தண்டு வெட்டுவண்டு, தண்டு ஈ, இலை உண்ணிகள், மஞ்சள் தேமல் போன்ற நோய்களைக் கண்காணிக்கவும்.", "பெரும்பாலான காய்கள் முதிர்ந்து உலரும்போது அறுவடை செய்து, சேமிப்பில் ஈரப்பதம் மற்றும் தானிய சேதத்தைத் தவிர்க்கவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("blackgram", "crop", "Black Gram", "உளுந்து",
     ["black gram", "blackgram", "urad", "உளுந்து"],
     ["Use clean seed and locally recommended varieties; ensure drainage and sow in the correct season.", "Monitor yellow mosaic virus, whitefly, pod borer and powdery mildew; remove virus-affected plants early where practical.", "Avoid excessive nitrogen; harvest when pods mature and dry.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["சுத்தமான விதை, உள்ளூர் பரிந்துரைக்கப்பட்ட ரகங்களைப் பயன்படுத்தி உரிய பருவத்தில் வடிகால் நிலத்தில் விதைக்கவும்.", "மஞ்சள் தேமல் வைரஸ், வெள்ளை ஈ, காய்த்துளைப்பான், மாவுப்பூஞ்சை நோய்களைக் கண்காணித்து வைரஸ் பாதித்த செடிகளை இயன்றால் ஆரம்பத்திலேயே அகற்றவும்.", "அதிக தழைச்சத்தைத் தவிர்த்து, காய்கள் முதிர்ந்து உலரும்போது அறுவடை செய்யவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("greengram", "crop", "Green Gram", "பாசிப்பயறு",
     ["green gram", "greengram", "mung bean", "moong", "பாசிப்பயறு", "பாசி பயறு"],
     ["Use locally recommended seed and sow at the right season in well-drained soil.", "Monitor whitefly, yellow mosaic virus, thrips and pod borers; use integrated pest management.", "Avoid waterlogging and excessive nitrogen; harvest pods as they mature to reduce shattering.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["உள்ளூர் பரிந்துரைக்கப்பட்ட விதையை உரிய பருவத்தில் வடிகால் மண்ணில் விதைக்கவும்.", "வெள்ளை ஈ, மஞ்சள் தேமல் வைரஸ், இலைப்பேன், காய்த்துளைப்பானைக் கண்காணித்து ஒருங்கிணைந்த பூச்சி மேலாண்மை செய்யவும்.", "நீர் தேங்குதல், அதிக தழைச்சத்தைத் தவிர்த்து, காய்கள் முதிரும்போது உதிர்வைக் குறைக்க அறுவடை செய்யவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("bengalgram", "crop", "Bengal Gram / Chickpea", "கொண்டைக்கடலை",
     ["bengal gram", "bengalgram", "chickpea", "chana", "கொண்டைக்கடலை"],
     ["Grow in cool, relatively dry conditions with well-drained soil and healthy seed.", "Avoid excess irrigation; monitor wilt, pod borer and Ascochyta/leaf blight symptoms.", "Protect flowering and pod formation from moisture stress; dry grain well before storage.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["குளிர்ச்சியான, ஒப்பீட்டளவில் வறண்ட சூழலில் வடிகால் மண்ணில் ஆரோக்கிய விதையுடன் வளர்க்கவும்.", "அதிக பாசனத்தைத் தவிர்த்து, வாடல், காய்த்துளைப்பான், இலைக் கருகல் அறிகுறிகளைக் கண்காணிக்கவும்.", "பூக்கும் மற்றும் காய் உருவாகும் காலத்தில் ஈரப்பத அழுத்தம் வராமல் பார்த்து, சேமிப்புக்கு முன் தானியத்தை நன்கு உலர்த்தவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("sesame", "crop", "Sesame", "எள்",
     ["sesame", "gingelly", "til", "எள்"],
     ["Sesame needs warm weather and well-drained soil; avoid waterlogging and overcrowding.", "Monitor phyllody, leaf webber/capsule borer and wilt; use healthy seed and remove severely diseased plants.", "Harvest when lower capsules begin to mature, following local practice to reduce seed shattering.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["எள்ளுக்கு வெப்பமான காலமும் வடிகால் மண்ணும் தேவை; நீர் தேங்குதல், நெருக்கமான நடவைத் தவிர்க்கவும்.", "பைலோடி, இலை வலைப்புழு/காய்ப்புழு, வாடல் நோயைக் கண்காணித்து ஆரோக்கிய விதை பயன்படுத்தி கடுமையாகப் பாதித்த செடிகளை அகற்றவும்.", "விதைகள் உதிர்வதைத் தவிர்க்க கீழ் காய்கள் முதிரத் தொடங்கும்போது உள்ளூர் முறையின்படி அறுவடை செய்யவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("sunflower", "crop", "Sunflower", "சூரியகாந்தி",
     ["sunflower", "சூரியகாந்தி"],
     ["Choose a locally suitable hybrid and sow in well-drained soil; avoid water stress at flowering and seed filling.", "Monitor head rot, downy mildew, sucking pests and bird damage; ensure good drainage.", "Harvest when the back of the head turns yellow-brown and seeds mature; dry heads thoroughly.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["உள்ளூருக்கு ஏற்ற கலப்பினத்தைத் தேர்ந்தெடுத்து வடிகால் மண்ணில் விதைக்கவும்; பூக்கும் மற்றும் விதை நிரம்பும் காலத்தில் நீர் பற்றாக்குறை வரக்கூடாது.", "தலை அழுகல், டவுனி மில்டியூ, சாறு உறிஞ்சும் பூச்சிகள், பறவை சேதத்தைக் கண்காணித்து வடிகால் உறுதி செய்யவும்.", "பூத்தலையின் பின்புறம் மஞ்சள்-பழுப்பாகி விதைகள் முதிரும்போது அறுவடை செய்து நன்கு உலர்த்தவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("wheat", "crop", "Wheat", "கோதுமை",
     ["wheat", "கோதுமை"],
     ["Wheat is generally a cool-season crop; use locally recommended varieties and sowing dates.", "Critical irrigation stages often include crown-root initiation and flowering/grain filling; avoid waterlogging.", "Monitor rusts, aphids and weeds; harvest when plants and grains are mature and dry grain safely for storage.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["கோதுமை பொதுவாக குளிர்காலப் பயிர்; உள்ளூர் பரிந்துரைக்கப்பட்ட ரகம் மற்றும் விதைப்புக் காலத்தைப் பின்பற்றவும்.", "வேர் உருவாகும் ஆரம்ப நிலை மற்றும் பூக்கும்/மணி நிரம்பும் நிலைகளில் பாசனம் முக்கியம்; நீர் தேங்கக்கூடாது.", "துரு நோய்கள், அசுவினி, களைகளைக் கண்காணித்து தாவரமும் தானியமும் முதிர்ந்ததும் அறுவடை செய்து பாதுகாப்பாக உலர்த்தவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])
_add("fodder", "crop", "Fodder Crops", "தீவனப் பயிர்கள்",
     ["fodder", "forage", "கால்நடை தீவனம்", "தீவனப் பயிர்"],
     ["Choose fodder sorghum, maize, cowpea or other crops suited to local season and livestock needs.", "Use clean irrigation water and recommended seed; avoid grazing or feeding plants suspected of pesticide contamination.", "Harvest at the recommended growth stage for the crop; some sorghums under stress can contain toxic prussic acid, so seek local advice.",
      'Inspect plants at least weekly, especially new leaves, buds, and the underside of leaves, so problems are noticed early.',
      'Keep the field clean and well drained, remove badly diseased plant debris safely, and avoid moving contaminated soil or tools between plots.',
      'Record sowing/transplanting date, irrigation, fertilizer, pest symptoms, and harvest. Use local agriculture-department recommendations for exact spacing, dose, and timing.'],
     ["உள்ளூர் பருவம் மற்றும் கால்நடைத் தேவைக்கு ஏற்ற தீவனச் சோளம், மக்காச்சோளம், தட்டைப்பயறு போன்றவற்றைத் தேர்ந்தெடுக்கவும்.", "சுத்தமான பாசன நீரும் பரிந்துரைக்கப்பட்ட விதையும் பயன்படுத்தவும்; பூச்சிமருந்து மாசு இருக்கலாம் என சந்தேகிக்கும் செடிகளை மேய்ச்சலுக்கு/தீவனமாகக் கொடுக்காதீர்கள்.", "பயிருக்கு ஏற்ற வளர்ச்சி நிலையில் அறுவடை செய்யவும்; வறட்சியால் பாதித்த சில சோள வகைகளில் நச்சுத்தன்மை உருவாகலாம், எனவே உள்ளூர் ஆலோசனை பெறவும்.",
      'புதிய இலைகள், மொட்டுகள் மற்றும் இலை அடிப்பகுதியை வாரத்திற்கு ஒருமுறையாவது பாருங்கள்; பிரச்சனைகளை ஆரம்பத்திலேயே கண்டறியலாம்.',
      'வயலைச் சுத்தமாகவும் வடிகால் வசதியுடனும் வைத்துக் கொள்ளுங்கள். கடுமையாக நோயுற்ற தாவரக் கழிவுகளைப் பாதுகாப்பாக அகற்றி, பாதிக்கப்பட்ட மண்ணை அல்லது கருவிகளைப் பிற வயல்களுக்கு எடுத்துச் செல்ல வேண்டாம்.',
      'விதைத்த/நட்ட தேதி, பாசனம், உரம், பூச்சி அறிகுறிகள், அறுவடை ஆகியவற்றைப் பதிவு செய்யுங்கள். சரியான இடைவெளி, அளவு, நேரத்திற்கு உள்ளூர் வேளாண் பரிந்துரைகளைப் பின்பற்றுங்கள்.'])

# ---- topics ----
_add("pest", "topic", "Pest management", "பூச்சி மேலாண்மை",
     ["pest", "insect", "bug", "worm", "caterpillar", "aphid", "whitefly", "thrips", "borer",
      "பூச்சி", "புழு", "அசுவினி", "வெள்ளை ஈ"],
     ["Identify the pest before spraying and scout fields weekly.",
      "Yellow sticky traps and pheromone traps help; neem seed kernel extract (5%) is a common early-stage option.",
      "Protect beneficial insects. Use only approved products, exactly as per label, with protective clothing.",
      "If you cannot identify the pest, take a sample or clear photo to your nearest agriculture office or KVK.",
      'Scout the field regularly and identify the pest before choosing a control; beneficial insects may help keep pests in check.',
      'Use integrated pest management: sanitation, crop rotation, traps or physical barriers where suitable, and a locally approved pesticide only when necessary.',
      'Follow the product label for crop, dose, protective equipment, re-entry interval, and pre-harvest interval; never mix products casually.'],
     ["தெளிப்பதற்கு முன் பூச்சியை அடையாளம் காணுங்கள்; வாரந்தோறும் வயலைக் கண்காணியுங்கள்.",
      "மஞ்சள் ஒட்டும் பொறி, இனக்கவர்ச்சிப் பொறி உதவும்; ஆரம்ப நிலையில் வேப்பங்கொட்டைச் சாறு (5%) பொதுவான தீர்வு.",
      "நன்மை செய்யும் பூச்சிகளைப் பாதுகாக்கவும்; அனுமதிக்கப்பட்ட மருந்துகளை மட்டும், லேபிள் அளவுப்படி, பாதுகாப்பு உடையுடன் பயன்படுத்தவும்.",
      "பூச்சி தெரியவில்லை எனில் மாதிரி/தெளிவான புகைப்படத்துடன் அருகிலுள்ள வேளாண் அலுவலகம் அல்லது KVK-வை அணுகவும்.",
      'பூச்சியை கட்டுப்படுத்தும் முறையைத் தேர்வுசெய்வதற்கு முன் வயலைத் தொடர்ந்து கண்காணித்து பூச்சியை அடையாளம் காணுங்கள்; நன்மை தரும் பூச்சிகளும் உதவலாம்.',
      'ஒருங்கிணைந்த பூச்சி மேலாண்மையைப் பயன்படுத்துங்கள்: வயல் சுத்தம், பயிர் சுழற்சி, பொருத்தமான பொறிகள்/தடைகள், அவசியமானால் உள்ளூரில் அனுமதிக்கப்பட்ட மருந்து.',
      'மருந்தின் லேபிளில் உள்ள பயிர், அளவு, பாதுகாப்பு உபகரணம், மீண்டும் வயலுக்குள் செல்லும் நேரம், அறுவடைக்கு முன் காத்திருக்கும் காலம் ஆகியவற்றைப் பின்பற்றுங்கள்; மருந்துகளைத் தன்னிச்சையாகக் கலக்க வேண்டாம்.'])

_add("disease", "topic", "Disease management", "நோய் மேலாண்மை",
     ["disease", "fungus", "fungal", "blight", "rot", "rotting", "infection", "infected", "bacterial", "virus",
      "நோய்", "பூஞ்சை", "அழுகல்", "வைரஸ்"],
     ["Remove and destroy badly infected plants; avoid overhead irrigation and improve spacing for airflow.",
      "Disease-free seed, seed treatment and crop rotation are the strongest prevention. Bio-agents such as Trichoderma and Pseudomonas help as preventives.",
      "Use a fungicide only after the disease is confirmed, following the label and local recommendation.",
      'Compare affected and healthy plants and note whether symptoms spread in patches or follow irrigation lines; this helps narrow down causes.',
      'Use healthy seed/seedlings, clean tools, suitable spacing, and good drainage to reduce many disease risks.',
      'Avoid treating every symptom as a fungal disease; confirm the likely cause with a local agriculture officer or KVK when uncertain.'],
     ["கடுமையாகப் பாதித்த செடிகளை அகற்றி அழிக்கவும்; மேல்நீர்ப் பாசனத்தைத் தவிர்த்து, இடைவெளி கொடுத்து காற்றோட்டம் அதிகரிக்கவும்.",
      "நோயற்ற விதை, விதை நேர்த்தி, பயிர் சுழற்சி சிறந்த தடுப்பு முறைகள்; டிரைக்கோடெர்மா, சூடோமோனாஸ் போன்ற உயிரியல் காரணிகள் தடுப்பாக உதவும்.",
      "நோயை உறுதிப்படுத்திய பின்பே, லேபிள் மற்றும் உள்ளூர் பரிந்துரைப்படி பூஞ்சைக்கொல்லி பயன்படுத்தவும்.",
      'பாதிக்கப்பட்ட செடிகளையும் ஆரோக்கியமான செடிகளையும் ஒப்பிட்டு, அறிகுறிகள் திட்டுகளாகப் பரவுகிறதா அல்லது பாசன வரிசையிலா எனக் கவனியுங்கள்.',
      'ஆரோக்கியமான விதை/நாற்று, சுத்தமான கருவிகள், பொருத்தமான இடைவெளி, நல்ல வடிகால் ஆகியவை பல நோய் அபாயங்களைக் குறைக்கும்.',
      'எல்லா அறிகுறிகளையும் பூஞ்சை நோயாகக் கருத வேண்டாம்; உறுதி இல்லாவிட்டால் உள்ளூர் வேளாண் அலுவலர் அல்லது KVK-யிடம் ஆலோசனை பெறுங்கள்.'])

_add("fertilizer", "topic", "Fertilizer", "உரம்",
     ["fertilizer", "fertiliser", "manure", "urea", "dap", "npk", "compost", "nutrient", "உரம்", "யூரியா", "உரங்கள்"],
     ["Do a soil test first and follow your Soil Health Card recommendation.",
      "Apply nitrogen, phosphorus and potash in balance, and split nitrogen into more than one dose.",
      "Avoid excess urea. Farmyard manure or vermicompost improves soil health.",
      "Zinc deficiency is common in rice soils; correct it only as locally advised.",
      'Base fertilizer decisions on crop stage and soil-test results where possible; split applications when the crop recommendation calls for it.',
      'Keep fertilizer away from direct contact with seeds, stems, and roots unless the product directions specifically allow it.',
      'Store fertilizers dry and labelled, away from children, animals, food, and drinking water.'],
     ["முதலில் மண் பரிசோதனை செய்யுங்கள்; மண் வள அட்டை பரிந்துரையைப் பின்பற்றுங்கள்.",
      "தழை, மணி, சாம்பல் சத்துகளை சமச்சீராக இடவும்; தழைச்சத்தைப் பிரித்து இடவும்.",
      "யூரியாவை அதிகமாக இடுவதைத் தவிர்க்கவும்; தொழுவுரம்/மண்புழு உரம் மண் வளத்தை மேம்படுத்தும்.",
      "நெல் மண்ணில் துத்தநாகப் பற்றாக்குறை பொதுவானது; உள்ளூர் ஆலோசனைப்படி மட்டும் சரிசெய்யவும்.",
      'முடிந்தால் மண் பரிசோதனை மற்றும் பயிரின் வளர்ச்சி நிலையை அடிப்படையாகக் கொண்டு உரமிடுங்கள்; பரிந்துரைக்கப்பட்டால் அளவைப் பிரித்து இடுங்கள்.',
      'தயாரிப்பு வழிமுறை அனுமதிக்காவிட்டால் உரத்தை விதை, தண்டு, வேர் ஆகியவற்றுடன் நேரடியாகத் தொடும் வகையில் இட வேண்டாம்.',
      'உரங்களை உலர்ந்த, லேபிள் உள்ள இடத்தில் குழந்தைகள், விலங்குகள், உணவு மற்றும் குடிநீரிலிருந்து விலக்கி வையுங்கள்.'])

_add("irrigation", "topic", "Irrigation", "பாசனம்",
     ["irrigation", "irrigate", "water", "watering", "drip", "sprinkler", "drought",
      "பாசனம்", "நீர்", "தண்ணீர்", "சொட்டு"],
     ["Irrigate by soil moisture and crop stage, not by the calendar. Check moisture by hand at 5-10 cm depth.",
      "Drip and sprinkler save water. Irrigate early morning or evening, and mulch to reduce evaporation.",
      "Waterlogging is as harmful as drought - make sure fields can drain. Flowering and grain filling are the most sensitive stages.",
      "Micro-irrigation subsidy may be available under schemes like PMKSY; ask your agriculture office.",
      'Check moisture in the root zone before irrigating and adjust after rain; a fixed daily schedule may waste water or waterlog roots.',
      'Repair leaks and keep channels or drip emitters clear so water reaches the intended plants evenly.',
      'During sensitive stages such as establishment, flowering, or fruit filling, avoid sudden severe water stress.'],
     ["நாள்காட்டியை விட மண் ஈரம் மற்றும் பயிர் நிலையை வைத்து நீர் பாய்ச்சுங்கள்; 5-10 செ.மீ ஆழத்தில் மண் ஈரத்தைக் கையால் சோதிக்கலாம்.",
      "சொட்டுநீர்/தெளிப்புநீர் நீரைச் சேமிக்கும்; காலை அல்லது மாலையில் பாசனம் செய்யவும்; மூடாக்கு ஆவியாதலைக் குறைக்கும்.",
      "நீர் தேங்குவதும் வறட்சியைப் போலவே தீங்கு; வடிகால் வசதியை உறுதி செய்யவும். பூக்கும் மற்றும் மணி பிடிக்கும் நிலைகள் மிக முக்கியம்.",
      "நுண்ணீர்ப் பாசனத்துக்கு PMKSY போன்ற திட்டங்களில் மானியம் கிடைக்கலாம்; வேளாண் அலுவலகத்தில் விசாரிக்கவும்.",
      'பாசனத்திற்கு முன் வேர் பகுதியில் ஈரத்தைச் சரிபார்த்து மழைக்குப் பிறகு அளவை மாற்றுங்கள்; தினசரி ஒரே அட்டவணை நீரை வீணாக்கலாம் அல்லது வேர் பகுதியில் நீர் தேக்கலாம்.',
      'கசிவுகளைச் சரிசெய்து, கால்வாய் அல்லது சொட்டுநீர் வெளியீடுகள் அடைப்பு இல்லாமல் இருப்பதை உறுதி செய்யுங்கள்.',
      'நாற்று நிலைபெறுதல், பூத்தல், காய் நிரம்புதல் போன்ற முக்கிய நிலைகளில் திடீர் கடுமையான நீர் அழுத்தத்தைத் தவிர்க்குங்கள்.'])

_add("soil", "topic", "Soil health", "மண் வளம்",
     ["soil", "ph", "salinity", "acidic", "alkaline", "soil test", "மண்", "மண் பரிசோதனை", "களர்", "உவர்"],
     ["Test soil every 2-3 years at your nearest agriculture department or KVK lab.",
      "Add organic matter and green manure (sunnhemp, daincha) and rotate with legumes.",
      "Use lime for acidic soils and gypsum for sodic soils - only according to test results.",
      'Avoid working soil when it is excessively wet, because this can compact the soil and damage its structure.',
      'Add organic matter gradually and keep the soil covered where practical to reduce erosion and moisture loss.',
      'Test soil pH and salinity if plants repeatedly perform poorly despite reasonable watering and fertilization.'],
     ["2-3 ஆண்டுகளுக்கு ஒருமுறை அருகிலுள்ள வேளாண் துறை/KVK ஆய்வகத்தில் மண் பரிசோதனை செய்யுங்கள்.",
      "தொழுவுரம், பசுந்தாள் உரம் (சணப்பை, தக்கைப்பூண்டு) சேர்த்து, பயறு வகைகளுடன் பயிர் சுழற்சி செய்யுங்கள்.",
      "அமில மண்ணுக்கு சுண்ணாம்பு, களர் மண்ணுக்கு ஜிப்சம் - பரிசோதனை முடிவின்படி மட்டும் இடவும்.",
      'மண் மிகவும் ஈரமாக இருக்கும்போது உழுவதைத் தவிர்க்குங்கள்; அது மண்ணை இறுக்கமாக்கி அமைப்பைச் சேதப்படுத்தலாம்.',
      'கரிமப் பொருளை படிப்படியாகச் சேர்த்து, சாத்தியமான இடங்களில் மண்ணை மூடி வைத்து அரிப்பையும் ஈர இழப்பையும் குறையுங்கள்.',
      'சரியான பாசனம் மற்றும் உரமிடுதலுக்குப் பிறகும் பயிர் தொடர்ந்து மோசமாக இருந்தால் மண் pH மற்றும் உப்புத்தன்மையைப் பரிசோதியுங்கள்.'])

_add("organic", "topic", "Organic farming", "இயற்கை விவசாயம்",
     ["organic", "natural farming", "jeevamrut", "jeevamrutham", "panchagavya", "vermicompost",
      "இயற்கை", "பஞ்சகவ்யா", "ஜீவாமிர்தம்", "மண்புழு"],
     ["Farmyard manure, vermicompost and green manure build soil health.",
      "Neem-based products and bio-pesticides are common pest options.",
      "Panchagavya and jeevamrutham are traditional inputs; evidence on yield effect is mixed, so use them alongside soil testing.",
      "Selling as 'organic' needs certification (NPOP for export, PGS-India for domestic markets).",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["தொழுவுரம், மண்புழு உரம், பசுந்தாள் உரம் மண் வளத்தை உயர்த்தும்.",
      "வேம்பு சார்ந்த இடுபொருட்கள், உயிரியல் பூச்சிக்கொல்லிகள் பொதுவான தீர்வுகள்.",
      "பஞ்சகவ்யா, ஜீவாமிர்தம் பாரம்பரிய இடுபொருட்கள்; மகசூல் மீதான தாக்கம் குறித்த ஆதாரங்கள் கலவையானவை, எனவே மண் பரிசோதனையுடன் சேர்த்துப் பயன்படுத்துங்கள்.",
      "'இயற்கை' என விற்க சான்றிதழ் தேவை (ஏற்றுமதிக்கு NPOP, உள்நாட்டுக்கு PGS-India).",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("season", "topic", "Seasons & sowing time", "பருவம் & விதைப்பு",
     ["season", "sowing", "sow", "when to plant", "planting time", "kharif", "rabi", "zaid",
      "பருவம்", "விதைப்பு", "நடவு", "விதைக்க"],
     ["India's main seasons: Kharif (sown with monsoon, ~Jun-Jul), Rabi (sown ~Oct-Dec) and the summer season.",
      "In Tamil Nadu, the southwest monsoon (Jun-Sep) and especially the northeast monsoon (Oct-Dec) drive sowing decisions.",
      "Confirm variety and sowing date for your district with TNAU or your agriculture office.",
      'Choose sowing dates using local rainfall patterns, irrigation availability, crop duration, and the variety recommended for your area.',
      'Check the seed label for the variety, lot number, germination percentage, and expiry or validity details.',
      'Keep a backup plan for delayed rains or unexpected heat, such as adjusting sowing timing in consultation with local advisers.'],
     ["இந்தியாவின் முக்கியப் பருவங்கள்: காரிஃப் (பருவமழையுடன், சுமார் ஜூன்-ஜூலை), ரபி (சுமார் அக்.-டிச.) மற்றும் கோடைப் பருவம்.",
      "தமிழகத்தில் தென்மேற்குப் பருவமழை (ஜூன்-செப்.), குறிப்பாக வடகிழக்குப் பருவமழை (அக்.-டிச.) விதைப்பைத் தீர்மானிக்கும்.",
      "உங்கள் மாவட்டத்துக்கான ரகம், விதைப்பு தேதியை TNAU / வேளாண் அலுவலகத்தில் உறுதிசெய்யுங்கள்.",
      'உள்ளூர் மழை முறை, பாசன வசதி, பயிர் கால அளவு, உங்கள் பகுதிக்கு பரிந்துரைக்கப்பட்ட ரகம் ஆகியவற்றைப் பார்த்து விதைப்பு தேதியைத் தேர்ந்தெடுங்கள்.',
      'விதை உறையில் ரகம், தொகுதி எண், முளைப்பு சதவீதம், காலாவதி/செல்லுபடித் தகவலைச் சரிபாருங்கள்.',
      'மழை தாமதம் அல்லது எதிர்பாராத வெப்பத்திற்கான மாற்றுத் திட்டத்தை உள்ளூர் ஆலோசனையுடன் வைத்திருங்கள்.'])

_add("weather", "topic", "Weather & climate", "வானிலை",
     ["weather", "rain", "rainfall", "monsoon", "flood", "heat", "storm", "cyclone", "மழை", "வெயில்", "புயல்", "வெள்ளம்", "வானிலை"],
     ["Check IMD agromet advisories. Postpone spraying and fertilizer before heavy rain.",
      "In rain or flood, drain the field and support the plants.",
      "In extreme heat, mulch and irrigate in the morning or evening.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["IMD வேளாண் வானிலை ஆலோசனைகளைப் பாருங்கள்; கனமழைக்கு முன் தெளிப்பு, உரமிடுதலை ஒத்திவையுங்கள்.",
      "மழை/வெள்ளத்தின் போது வயலில் நீரை வடியச் செய்து, செடிகளுக்கு முட்டுக் கொடுக்கவும்.",
      "கடும் வெப்பத்தில் மூடாக்கு இட்டு, காலை/மாலையில் பாசனம் செய்யவும்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("scheme", "topic", "Government schemes", "அரசுத் திட்டங்கள்",
     ["scheme", "schemes", "subsidy", "loan", "insurance", "pm-kisan", "pm kisan", "pmkisan", "pmfby", "kisan credit", "kcc",
      "திட்டம்", "திட்டங்கள்", "மானியம்", "கடன்", "காப்பீடு"],
     ["PM-KISAN: income support of Rs 6,000 per year in three instalments for eligible farmer families.",
      "PMFBY crop insurance: enrol before the cut-off date; farmer premium is low (2% Kharif, 1.5% Rabi, up to 5% commercial/horticulture crops).",
      "Kisan Credit Card (KCC) for short-term credit, Soil Health Card, and PMKSY for micro-irrigation.",
      "Check current rules and amounts on pmkisan.gov.in, pmfby.gov.in, the Tamil Nadu Agriculture Department and the Uzhavan app - they can change.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["PM-KISAN: தகுதியுள்ள விவசாயக் குடும்பங்களுக்கு ஆண்டுக்கு ₹6,000, மூன்று தவணைகளில்.",
      "PMFBY பயிர்க் காப்பீடு: கடைசி தேதிக்குள் பதிவு செய்யவும்; விவசாயி பிரீமியம் குறைவு (காரிஃப் 2%, ரபி 1.5%, வணிக/தோட்டக்கலைப் பயிர்கள் 5% வரை).",
      "குறுகியகாலக் கடனுக்கு கிசான் கிரெடிட் கார்டு (KCC), மண் வள அட்டை, நுண்ணீர்ப் பாசனத்துக்கு PMKSY.",
      "தற்போதைய விதிகள், தொகையை pmkisan.gov.in, pmfby.gov.in, தமிழ்நாடு வேளாண்மைத் துறை, உழவன் செயலி ஆகியவற்றில் சரிபாருங்கள் - அவை மாறக்கூடும்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("harvest", "topic", "Harvest & storage", "அறுவடை & சேமிப்பு",
     ["harvest", "harvesting", "storage", "store", "drying", "post harvest", "அறுவடை", "சேமிப்பு"],
     ["Harvest at physiological maturity.",
      "Dry grain to safe moisture (about 12-14%); dry groundnut pods thoroughly before storing.",
      "Store in clean, dry places or hermetic bags and never mix damp produce with dry.",
      "Consider selling through e-NAM and regulated markets.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["உடலியல் முதிர்ச்சியில் அறுவடை செய்யுங்கள்.",
      "தானியங்களை பாதுகாப்பான ஈரப்பதத்துக்கு (சுமார் 12-14%) உலர்த்தவும்; நிலக்கடலை காய்களை சேமிக்கும் முன் நன்கு உலர்த்தவும்.",
      "சுத்தமான, உலர்ந்த இடத்தில் அல்லது காற்றுப் புகாத பைகளில் சேமிக்கவும்; ஈரமான விளைபொருளைக் கலக்காதீர்கள்.",
      "e-NAM மற்றும் ஒழுங்குமுறை சந்தைகள் வழியாக விற்பனை செய்யலாம்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

# ---- additional practical farming topics ----
_add("seed", "topic", "Seed selection and treatment", "விதைத் தேர்வு மற்றும் நேர்த்தி",
     ["seed", "seeds", "seedling", "germination", "seed treatment", "seed quality", "விதை", "விதைகள்", "முளைப்பு", "நாற்று"],
     ["Buy certified, crop-appropriate seed from a trusted source and check the label, variety, lot and expiry details.",
      "Before sowing, test a small sample for germination using a clean, moist cloth or tray; poor germination means you may need fresh seed.",
      "Use only crop-specific seed treatment recommended by the agriculture department or label. Never mix chemicals casually, and label treated seed clearly.",
      "Keep seed dry, cool and pest-free. Do not use grain treated for sowing as food or animal feed.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["நம்பகமான இடத்தில் சான்றளிக்கப்பட்ட, பயிருக்கு ஏற்ற விதையை வாங்கி ரகம், தொகுதி, காலாவதி விவரங்களைப் பார்க்கவும்.",
      "விதைப்பதற்கு முன் சிறிய மாதிரியை ஈரமான சுத்தமான துணி/தட்டில் வைத்து முளைப்புத் திறனைச் சோதிக்கவும்.",
      "வேளாண் துறை அல்லது லேபிள் பரிந்துரைக்கும் பயிர்-சார்ந்த விதை நேர்த்தியை மட்டும் செய்யவும்; ரசாயனங்களை ஊகத்தில் கலக்காதீர்கள்.",
      "விதைகளை உலர்ந்த, குளிர்ந்த, பூச்சி இல்லாத இடத்தில் வைக்கவும். நேர்த்தி செய்த விதையை உணவாகவோ கால்நடைத் தீவனமாகவோ பயன்படுத்தாதீர்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("weed", "topic", "Weed management", "களை மேலாண்மை",
     ["weed", "weeds", "weeding", "herbicide", "களை", "களைகள்", "களைக்கொல்லி"],
     ["Control weeds early, especially during the crop's critical competition period; the timing differs by crop.",
      "Combine timely hand/mechanical weeding, mulching, crop rotation, clean seed and suitable spacing as practical.",
      "If a herbicide is considered, verify that it is registered for the exact crop and target weed, then follow the product label and local advice. Prevent spray drift to neighbouring crops and water.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["பயிரின் ஆரம்ப முக்கியப் போட்டிக் காலத்தில் களைகளைக் கட்டுப்படுத்தவும்; சரியான காலம் பயிரைப் பொறுத்து மாறும்.",
      "கை/இயந்திரக் களை எடுப்பு, மூடாக்கு, பயிர் சுழற்சி, சுத்தமான விதை, சரியான இடைவெளி ஆகியவற்றைச் சேர்த்துப் பயன்படுத்தவும்.",
      "களைக்கொல்லி பயன்படுத்தினால் அந்தப் பயிருக்கும் களைக்கும் பதிவு செய்யப்பட்டதா உறுதிசெய்து, லேபிள் மற்றும் உள்ளூர் ஆலோசனையைப் பின்பற்றவும். அருகிலுள்ள பயிர்/நீர்நிலைகளுக்கு தெளிப்பு செல்லாமல் தடுக்கவும்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("spray_safety", "topic", "Pesticide safety", "பூச்சிக்கொல்லி பாதுகாப்பு",
     ["pesticide", "spray", "spraying", "chemical", "poison", "protective equipment", "பூச்சிக்கொல்லி", "தெளிப்பு", "மருந்து", "நச்சு"],
     ["Identify the pest or disease first; spraying without a diagnosis can waste money and harm beneficial insects.",
      "Use only a product registered for the crop and problem. Follow the label exactly for dose, protective equipment, re-entry interval and pre-harvest interval; this assistant does not provide chemical doses.",
      "Do not spray in strong wind, near people, livestock or water, or when rain is expected. Never reuse pesticide containers; dispose of them as instructed on the label.",
      "Keep products locked away from children and food. If poisoning is suspected, seek emergency medical help and take the product label/container if safe.",
      'Scout the field regularly and identify the pest before choosing a control; beneficial insects may help keep pests in check.',
      'Use integrated pest management: sanitation, crop rotation, traps or physical barriers where suitable, and a locally approved pesticide only when necessary.',
      'Follow the product label for crop, dose, protective equipment, re-entry interval, and pre-harvest interval; never mix products casually.'],
     ["பூச்சி/நோயை முதலில் அடையாளம் காணுங்கள்; காரணமின்றி தெளிப்பது செலவையும் நன்மை செய்யும் பூச்சிகளுக்கான பாதிப்பையும் அதிகரிக்கும்.",
      "பயிருக்கும் பிரச்சனைக்கும் பதிவு செய்யப்பட்ட மருந்தை மட்டும் பயன்படுத்தவும். அளவு, பாதுகாப்பு உபகரணம், மீண்டும் வயலுக்குள் செல்லும் நேரம், அறுவடைக்கு முன் காத்திருப்பு ஆகியவற்றை லேபிள்படி பின்பற்றவும்; இங்கு ரசாயன அளவு வழங்கப்படாது.",
      "பலத்த காற்றில், மக்கள்/கால்நடை/நீர்நிலைகள் அருகில் அல்லது மழை எதிர்பார்க்கும்போது தெளிக்காதீர்கள். காலி மருந்துக் கொள்கலன்களை மீண்டும் பயன்படுத்தாதீர்கள்.",
      "குழந்தைகள் மற்றும் உணவுப் பொருட்களிலிருந்து பூட்டிவைக்கவும். நச்சுத்தன்மை சந்தேகித்தால் உடனடி மருத்துவ உதவி பெறவும்.",
      'பூச்சியை கட்டுப்படுத்தும் முறையைத் தேர்வுசெய்வதற்கு முன் வயலைத் தொடர்ந்து கண்காணித்து பூச்சியை அடையாளம் காணுங்கள்; நன்மை தரும் பூச்சிகளும் உதவலாம்.',
      'ஒருங்கிணைந்த பூச்சி மேலாண்மையைப் பயன்படுத்துங்கள்: வயல் சுத்தம், பயிர் சுழற்சி, பொருத்தமான பொறிகள்/தடைகள், அவசியமானால் உள்ளூரில் அனுமதிக்கப்பட்ட மருந்து.',
      'மருந்தின் லேபிளில் உள்ள பயிர், அளவு, பாதுகாப்பு உபகரணம், மீண்டும் வயலுக்குள் செல்லும் நேரம், அறுவடைக்கு முன் காத்திருக்கும் காலம் ஆகியவற்றைப் பின்பற்றுங்கள்; மருந்துகளைத் தன்னிச்சையாகக் கலக்க வேண்டாம்.'])

_add("climate_smart", "topic", "Climate-smart farming", "காலநிலை மாற்றத்திற்கேற்ற விவசாயம்",
     ["climate smart", "climate change", "heat stress", "drought resistant", "water conservation", "காலநிலை மாற்றம்", "வறட்சி", "நீர் சேமிப்பு"],
     ["Choose locally recommended, stress-tolerant varieties and stagger sowing only when advised for your district.",
      "Conserve soil moisture with crop residue or suitable mulch, maintain field drainage and repair irrigation leaks.",
      "Diversify crops where feasible, include legumes in rotations, and keep a simple record of rainfall, sowing dates and yields.",
      "Use current IMD and district agriculture advisories for severe weather; this offline app does not provide live forecasts.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["உங்கள் மாவட்டத்திற்குப் பரிந்துரைக்கப்படும் வெப்பம்/வறட்சியைத் தாங்கும் ரகங்களைத் தேர்ந்தெடுக்கவும்.",
      "பயிர் கழிவு அல்லது ஏற்ற மூடாக்கால் மண் ஈரத்தைப் பாதுகாத்து, வடிகாலைச் சரிசெய்து, பாசனக் கசிவுகளைத் தடுக்கவும்.",
      "சாத்தியமான இடங்களில் பல்வகைப் பயிர் மற்றும் பயறு வகைப் பயிர் சுழற்சி செய்யவும்; மழை, விதைப்பு தேதி, மகசூலைப் பதிவு செய்யவும்.",
      "கடுமையான வானிலைக்கு தற்போதைய IMD மற்றும் மாவட்ட வேளாண் அறிவுரைகளைப் பார்க்கவும்; இந்த ஆஃப்லைன் செயலி நேரடி முன்னறிவிப்பை வழங்காது.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("marketing", "topic", "Farm records and marketing", "பண்ணைப் பதிவுகள் மற்றும் சந்தைப்படுத்தல்",
     ["market", "selling", "price", "profit", "income", "cost", "expense", "mandi", "enam", "சந்தை", "விலை", "லாபம்", "வருமானம்", "செலவு"],
     ["Record seed, fertilizer, labour, irrigation, transport and other costs separately for each crop and season.",
      "Compare the expected selling price with local market information, transport costs, quality requirements and likely wastage before choosing where to sell.",
      "Keep receipts and weighment records. Compare offers from more than one buyer when practical and use regulated market/e-NAM information where available.",
      "The built-in calculator estimates revenue and profit from the figures you enter; it is not a guaranteed price forecast.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["ஒவ்வொரு பயிர்/பருவத்திற்கும் விதை, உரம், கூலி, பாசனம், போக்குவரத்து உள்ளிட்ட செலவுகளைத் தனித்தனியாகப் பதிவு செய்யவும்.",
      "விற்பனை இடத்தைத் தேர்வதற்கு முன் உள்ளூர் விலை, போக்குவரத்துச் செலவு, தரத் தேவை, வீணாகும் அளவு ஆகியவற்றை ஒப்பிடவும்.",
      "ரசீதுகள் மற்றும் எடைப் பதிவுகளை வைத்திருங்கள்; இயன்றால் பல வாங்குபவர்களின் விலையை ஒப்பிட்டு, ஒழுங்குமுறை சந்தை/e-NAM தகவல்களைப் பயன்படுத்தவும்.",
      "உள்ளிட்ட எண்களின் அடிப்படையில் கணிப்பான் வருவாய்/லாபத்தை கணக்கிடும்; இது உறுதியான விலை முன்னறிவிப்பு அல்ல.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

# ---- broader everyday agriculture questions ----
_add("farm_basics", "topic", "Getting started with farming", "விவசாயம் தொடங்குதல்",
     ["farming", "agriculture", "start farming", "beginner farmer", "farm basics", "cultivation", "விவசாயம்", "உழவு", "சாகுபடி"],
     ["Start by checking your land size, soil-test results, reliable water source, local climate, labour availability and nearby buyers.",
      "Choose a crop that suits the season, soil, water and local demand—not only the highest advertised price.",
      "Make a simple budget for seed, land preparation, labour, nutrients, irrigation, pest management, transport and a contingency reserve.",
      "Ask your local agriculture office or KVK for district-specific varieties, sowing dates and current recommendations.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["நில அளவு, மண் பரிசோதனை, நீர் வசதி, உள்ளூர் காலநிலை, தொழிலாளர் வசதி, அருகிலுள்ள சந்தை ஆகியவற்றை முதலில் மதிப்பிடுங்கள்.",
      "அதிக விலை என்ற காரணத்திற்காக மட்டும் பயிரைத் தேர்ந்தெடுக்காமல், பருவம், மண், நீர், உள்ளூர் தேவைக்கு ஏற்ற பயிரைத் தேர்ந்தெடுக்கவும்.",
      "விதை, நிலத் தயாரிப்பு, கூலி, உரம், பாசனம், பூச்சி மேலாண்மை, போக்குவரத்து மற்றும் அவசரச் செலவுகளுக்குப் பட்ஜெட் அமைக்கவும்.",
      "மாவட்டத்திற்கேற்ற ரகம், விதைப்பு தேதி, தற்போதைய பரிந்துரைகளுக்கு வேளாண் அலுவலகம் அல்லது KVK-வை அணுகுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("crop_rotation", "topic", "Crop rotation and intercropping", "பயிர் சுழற்சி மற்றும் ஊடுபயிர்",
     ["crop rotation", "rotate crops", "intercrop", "intercropping", "mixed cropping", "companion planting", "பயிர் சுழற்சி", "ஊடுபயிர்", "கலப்புப் பயிர்"],
     ["Rotate crops from different plant families to reduce the build-up of crop-specific pests and soil-borne diseases.",
      "Including legumes such as pulses can contribute nitrogen to the system, but nutrient needs still depend on the crop and soil test.",
      "Intercropping can spread risk and use light, water and space efficiently; select compatible crops and locally recommended row ratios.",
      "Avoid repeating the same crop family season after season, especially where wilt, nematodes or other soil-borne problems occur.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["வேறுபட்ட தாவரக் குடும்பங்களைச் சேர்ந்த பயிர்களை மாற்றி மாற்றி பயிரிடுவது குறிப்பிட்ட பூச்சி மற்றும் மண் வழி நோய்கள் பெருகுவதைத் தடுக்க உதவும்.",
      "பயறு வகைகளைச் சேர்ப்பது மண்ணில் நைட்ரஜன் கிடைப்புக்கு உதவும்; இருப்பினும் உரத் தேவை பயிர் மற்றும் மண் பரிசோதனையைப் பொறுத்தது.",
      "ஊடுபயிர் அபாயத்தைப் பகிர்ந்து ஒளி, நீர், இடத்தைச் சிறப்பாகப் பயன்படுத்த உதவும்; பொருந்தும் பயிர்களையும் உள்ளூர் பரிந்துரைக்கப்பட்ட வரிசை விகிதத்தையும் தேர்ந்தெடுக்கவும்.",
      "வாடல், நூற்புழு அல்லது மண் வழி பிரச்சனைகள் உள்ள இடங்களில் ஒரே குடும்பப் பயிரை தொடர்ந்து பயிரிடாதீர்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("compost", "topic", "Compost and farmyard manure", "கம்போஸ்ட் மற்றும் தொழுவுரம்",
     ["compost", "composting", "farmyard manure", "cow dung", "manure preparation", "organic matter", "கம்போஸ்ட்", "தொழுவுரம்", "மாட்டுச்சாணம்", "மட்குரம்"],
     ["Mix plant residues with suitable animal manure and keep the pile moist but not waterlogged; turn it periodically to provide oxygen.",
      "Finished compost is generally dark, crumbly and earthy-smelling, with no obvious fresh waste. Immature compost can harm seedlings.",
      "Keep plastics, batteries, treated wood, chemical containers and contaminated waste out of compost.",
      "Compost improves soil structure and organic matter, but nutrient content varies; do not assume it replaces all crop fertilizer needs.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["தாவரக் கழிவுகளை ஏற்ற கால்நடை எருவுடன் கலந்து, ஈரமாக வைத்திருக்கவும்; நீர் தேங்க விடாமல் அவ்வப்போது கிளறி காற்றோட்டம் அளிக்கவும்.",
      "முதிர்ந்த கம்போஸ்ட் பொதுவாக கருமையாகவும் உதிரியாகவும் மண் மணத்துடனும் இருக்கும்; முழுமையாக மட்காத உரம் நாற்றுகளுக்கு தீங்கு செய்யலாம்.",
      "பிளாஸ்டிக், பேட்டரி, ரசாயனக் கொள்கலன் அல்லது மாசடைந்த கழிவுகளை கம்போஸ்டில் சேர்க்காதீர்கள்.",
      "கம்போஸ்ட் மண் அமைப்பு மற்றும் கரிமப் பொருளை மேம்படுத்தும்; சத்தளவு மாறுபடும் என்பதால் எல்லா உரத் தேவையையும் இது பூர்த்தி செய்யும் என நினைக்காதீர்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("plant_nutrition", "topic", "Plant nutrients and deficiency", "தாவரச் சத்துகள் மற்றும் குறைபாடு",
     ["nutrient deficiency", "nitrogen deficiency", "phosphorus deficiency", "potassium deficiency", "micronutrient", "nutrients", "plant nutrition", "சத்துக் குறைபாடு", "தழைச்சத்து", "மணிச்சத்து", "சாம்பல் சத்து"],
     ["Nitrogen shortage often causes older leaves to become uniformly pale; phosphorus shortage can slow growth; potassium shortage may cause leaf-edge scorching. These signs are not definitive.",
      "Iron or zinc deficiency may cause yellowing between the veins, often on young leaves, depending on the crop and soil.",
      "Waterlogging, root damage, salinity, disease and pests can mimic nutrient deficiency.",
      "Use a soil test and crop-specific local recommendation before applying fertilizer; avoid guessing a dose from leaf colour alone.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["தழைச்சத்துக் குறைபாட்டில் பழைய இலைகள் சீராக வெளிரலாம்; மணிச்சத்துக் குறைபாடு வளர்ச்சியைக் குறைக்கலாம்; சாம்பல் சத்துக் குறைபாட்டில் இலை ஓரங்கள் கருகலாம். இவை உறுதியான அறிகுறிகள் அல்ல.",
      "பயிர் மற்றும் மண்ணைப் பொறுத்து இரும்பு/துத்தநாகக் குறைபாட்டில், குறிப்பாக இளம் இலைகளில், நரம்புகளுக்கிடையே மஞ்சளாதல் தோன்றலாம்.",
      "நீர் தேக்கம், வேர் சேதம், உவர்ப்பு, நோய், பூச்சிகளும் சத்துக் குறைபாடு போலத் தோன்றலாம்.",
      "இலை நிறத்தை மட்டும் வைத்து உர அளவை ஊகிக்காமல், மண் பரிசோதனை மற்றும் பயிர் சார்ந்த உள்ளூர் பரிந்துரையைப் பின்பற்றுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("nursery", "topic", "Nursery and transplanting", "நாற்றங்கால் மற்றும் நடவு",
     ["nursery", "seed tray", "transplant", "transplanting", "seedling care", "hardening seedlings", "நாற்றங்கால்", "நாற்று நடவு", "நாற்று பராமரிப்பு"],
     ["Use clean trays or a well-prepared nursery bed and a clean, well-drained growing medium.",
      "Avoid overcrowding and overwatering; provide enough light and monitor seedlings for damping-off and insects.",
      "Harden seedlings gradually before transplanting by adjusting watering and exposure to outdoor conditions without allowing severe wilting.",
      "Transplant during cooler hours where practical, water after planting, and follow crop-specific age and spacing recommendations.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["சுத்தமான தட்டுகள் அல்லது நன்கு தயாரிக்கப்பட்ட, நீர் வடிகால் உள்ள நாற்றங்காலைப் பயன்படுத்தவும்.",
      "நெருக்கமாக விதைப்பதையும் அதிக நீரையும் தவிர்த்து, போதிய ஒளி அளித்து நாற்றழுகல் மற்றும் பூச்சிகளை கண்காணிக்கவும்.",
      "நடவுக்கு முன் நீர்ப்பாசனம் மற்றும் வெளிப்புற சூழலுக்கு நாற்றுகளை படிப்படியாக பழக்கப்படுத்தவும்; கடுமையாக வாட விடாதீர்கள்.",
      "சாத்தியமானால் குளிர்ச்சியான நேரத்தில் நடவு செய்து உடனே நீர் பாய்ச்சவும்; பயிருக்கேற்ற நாற்று வயது மற்றும் இடைவெளியைப் பின்பற்றவும்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("pollination", "topic", "Flowering and pollination", "பூத்தல் மற்றும் மகரந்தச் சேர்க்கை",
     ["flowering", "flowers falling", "flower drop", "pollination", "fruit set", "poor fruit set", "blossom drop", "பூ உதிர்வு", "மகரந்தச் சேர்க்கை", "காய் பிடிப்பு"],
     ["Flower drop or poor fruit set can be caused by heat, cold, irregular watering, excess nitrogen, poor pollination or pests; the cause varies by crop.",
      "Keep soil moisture reasonably even during flowering and avoid excess fertilizer, especially nitrogen, unless recommended by a soil test.",
      "Protect bees and other pollinators: avoid unnecessary spraying during flowering and never spray directly on active pollinators.",
      "Tell the assistant the crop, location/season and whether flowers drop before opening or after opening to narrow down causes.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["பூ உதிர்வு அல்லது காய் பிடிக்காமை வெப்பம், குளிர், ஒழுங்கற்ற பாசனம், அதிக தழைச்சத்து, மகரந்தச் சேர்க்கை குறைவு அல்லது பூச்சிகளால் ஏற்படலாம்; காரணம் பயிரைப் பொறுத்து மாறும்.",
      "பூக்கும் காலத்தில் மண் ஈரத்தைச் சீராக வைத்துக் கொள்ளவும்; மண் பரிசோதனை பரிந்துரையின்றி அதிக உரம், குறிப்பாக தழைச்சத்து, இடாதீர்கள்.",
      "தேனீ மற்றும் மகரந்தச் சேர்க்கை செய்யும் உயிரினங்களைப் பாதுகாக்கவும்; பூக்கும் போது தேவையற்ற தெளிப்பைத் தவிர்த்து, அவற்றின் மீது நேரடியாகத் தெளிக்காதீர்கள்.",
      "காரணத்தைச் சுருக்க பயிர், இடம்/பருவம், பூ திறப்பதற்கு முன்பா பின்பா உதிர்கிறது என்பதைக் கூறுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("greenhouse", "topic", "Greenhouse and protected cultivation", "பசுமைக் குடில் சாகுபடி",
     ["greenhouse", "polyhouse", "shade net", "protected cultivation", "net house", "பசுமைக் குடில்", "நிழல்வலை", "குடில் சாகுபடி"],
     ["Protected cultivation can help manage rain, wind, temperature and some pests, but it requires investment and active ventilation and humidity management.",
      "Choose the structure and crop according to local climate, water quality, market demand and available technical support.",
      "Monitor temperature, humidity, irrigation and disease daily; high humidity and poor airflow can encourage fungal disease.",
      "Before investing, compare construction, maintenance, replacement, energy, labour and marketing costs and verify any current subsidy with the agriculture department.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["பசுமைக் குடில் மழை, காற்று, வெப்பநிலை மற்றும் சில பூச்சிகளை கட்டுப்படுத்த உதவும்; ஆனால் முதலீடு, காற்றோட்டம், ஈரப்பத மேலாண்மை தேவை.",
      "உள்ளூர் காலநிலை, நீர்தரம், சந்தைத் தேவை, தொழில்நுட்ப உதவி ஆகியவற்றைப் பொறுத்து அமைப்பையும் பயிரையும் தேர்ந்தெடுக்கவும்.",
      "வெப்பநிலை, ஈரப்பதம், பாசனம், நோய்களை தினமும் கண்காணிக்கவும்; அதிக ஈரப்பதமும் குறைந்த காற்றோட்டமும் பூஞ்சை நோயை அதிகரிக்கும்.",
      "முதலீட்டுக்கு முன் கட்டுமானம், பராமரிப்பு, மாற்றுச் செலவு, மின்சாரம், கூலி, சந்தைப்படுத்தலை ஒப்பிட்டு, மானியத்தை வேளாண் துறையில் உறுதிசெய்யவும்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("hydroponics", "topic", "Hydroponics and soilless growing", "மண்ணில்லா சாகுபடி",
     ["hydroponics", "soilless", "nutrient solution", "vertical farming", "ஹைட்ரோபோனிக்ஸ்", "மண்ணில்லா சாகுபடி"],
     ["Hydroponics grows plants using water with carefully balanced nutrients and an appropriate support medium; it is not simply growing plants in plain water.",
      "Monitor water pH, electrical conductivity, temperature, cleanliness and oxygenation with suitable instruments.",
      "Start with a small trial and easy leafy crops before investing in pumps, reservoirs and climate control.",
      "Use clean water and crop-specific nutrient guidance. A power, pump or water-quality failure can damage plants quickly.",
      'Avoid working soil when it is excessively wet, because this can compact the soil and damage its structure.',
      'Add organic matter gradually and keep the soil covered where practical to reduce erosion and moisture loss.',
      'Test soil pH and salinity if plants repeatedly perform poorly despite reasonable watering and fertilization.'],
     ["ஹைட்ரோபோனிக்ஸ் முறையில் சரியான சத்துக் கலந்த நீரும் பொருத்தமான தாங்கு ஊடகமும் பயன்படுத்தப்படும்; சாதாரண நீரில் மட்டும் வளர்ப்பது அல்ல.",
      "நீரின் pH, மின்கடத்துத்திறன், வெப்பநிலை, சுத்தம், ஆக்சிஜன் ஆகியவற்றை பொருத்தமான கருவிகளால் கண்காணிக்கவும்.",
      "பம்ப், தொட்டி, காலநிலை கட்டுப்பாட்டில் முதலீடு செய்வதற்கு முன் சிறிய அளவில் கீரை போன்ற எளிய பயிர்களுடன் முயற்சி செய்யவும்.",
      "சுத்தமான நீர் மற்றும் பயிருக்கு ஏற்ற சத்துப் பரிந்துரையைப் பயன்படுத்தவும்; மின்சாரம், பம்ப் அல்லது நீர்தரக் கோளாறு விரைவில் பயிரை பாதிக்கலாம்.",
      'மண் மிகவும் ஈரமாக இருக்கும்போது உழுவதைத் தவிர்க்குங்கள்; அது மண்ணை இறுக்கமாக்கி அமைப்பைச் சேதப்படுத்தலாம்.',
      'கரிமப் பொருளை படிப்படியாகச் சேர்த்து, சாத்தியமான இடங்களில் மண்ணை மூடி வைத்து அரிப்பையும் ஈர இழப்பையும் குறையுங்கள்.',
      'சரியான பாசனம் மற்றும் உரமிடுதலுக்குப் பிறகும் பயிர் தொடர்ந்து மோசமாக இருந்தால் மண் pH மற்றும் உப்புத்தன்மையைப் பரிசோதியுங்கள்.'])

_add("livestock", "topic", "Livestock and farm integration", "கால்நடை மற்றும் ஒருங்கிணைந்த பண்ணை",
     ["livestock", "cattle", "cow", "goat", "sheep", "poultry", "chicken", "dairy", "animal feed", "கால்நடை", "மாடு", "ஆடு", "கோழி", "பால் பண்ணை"],
     ["Provide clean drinking water, balanced species-appropriate feed, shade, ventilation and clean housing.",
      "Follow a veterinarian's vaccination, deworming and disease-control schedule; isolate sick animals and seek veterinary help promptly.",
      "Store feed away from moisture, mould, pesticides and chemicals. Never feed animals plants or crop residues suspected of contamination.",
      "Keep basic records of feed, medicines, breeding, milk/egg output, mortality and sales to understand costs and performance.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["சுத்தமான குடிநீர், இனத்திற்கேற்ற சமச்சீர் தீவனம், நிழல், காற்றோட்டம், சுத்தமான கொட்டகை வழங்கவும்.",
      "கால்நடை மருத்துவர் பரிந்துரைக்கும் தடுப்பூசி, குடற்புழு நீக்கம், நோய் தடுப்பு அட்டவணையைப் பின்பற்றவும்; நோயுற்றவற்றைத் தனிமைப்படுத்தி உடனே உதவி பெறவும்.",
      "தீவனத்தை ஈரம், பூஞ்சை, பூச்சிக்கொல்லி மற்றும் ரசாயனங்களிலிருந்து விலக்கி வைக்கவும்; மாசடைந்திருக்கலாம் என சந்தேகிக்கும் பயிர்க் கழிவுகளைத் தீவனமாகக் கொடுக்காதீர்கள்.",
      "தீவனம், மருந்து, இனப்பெருக்கம், பால்/முட்டை உற்பத்தி, இறப்பு, விற்பனை ஆகியவற்றைப் பதிவு செய்து செலவு மற்றும் செயல்திறனைப் புரிந்துகொள்ளுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("mushroom", "topic", "Mushroom cultivation", "காளான் வளர்ப்பு",
     ["mushroom", "mushroom farming", "oyster mushroom", "காளான்", "காளான் வளர்ப்பு"],
     ["Choose a mushroom species suited to your climate, available substrate and local market; oyster mushrooms are often used for beginner trials.",
      "Use clean substrate, reliable spawn from a trusted supplier and hygienic handling. Contamination can spread quickly.",
      "Maintain the species-specific temperature, humidity, fresh-air exchange and light requirements; these differ among mushroom types.",
      "Start with a small batch and confirm buyers, packaging and cold-chain needs before scaling up.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["உங்கள் காலநிலை, கிடைக்கும் வளர்ப்பு மூலப்பொருள், உள்ளூர் சந்தைக்கு ஏற்ற காளான் வகையைத் தேர்ந்தெடுக்கவும்; தொடக்க முயற்சிக்கு சிப்பிக் காளான் பயன்படுத்தப்படலாம்.",
      "சுத்தமான மூலப்பொருள், நம்பகமான விற்பனையாளரின் தரமான விதைக் காளான், சுகாதாரமான கையாளுதலைப் பயன்படுத்தவும்; மாசுபாடு விரைவில் பரவும்.",
      "காளான் வகைக்கேற்ற வெப்பநிலை, ஈரப்பதம், காற்றோட்டம், ஒளியைப் பராமரிக்கவும்; தேவைகள் வகைபடி மாறும்.",
      "பெரிய அளவில் தொடங்குவதற்கு முன் சிறிய தொகுதியில் முயன்று, வாங்குபவர், பொதி, குளிர்சங்கிலி தேவைகளை உறுதிசெய்யவும்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("beekeeping", "topic", "Beekeeping and pollinators", "தேனீ வளர்ப்பு மற்றும் மகரந்தச் சேர்க்கை",
     ["beekeeping", "bee keeping", "honey bee", "honey production", "தேனீ வளர்ப்பு", "தேனீ", "தேன் உற்பத்தி"],
     ["Learn local seasonal forage, colony management and safe hive handling from a trained beekeeper or agriculture extension officer.",
      "Place hives where water and forage are available and where people and livestock can pass safely.",
      "Avoid pesticide exposure: coordinate any necessary spraying with nearby beekeepers and follow label precautions, especially during bloom.",
      "Use suitable protective equipment and get training before opening or moving colonies; people with serious sting allergies need particular caution.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["உள்ளூர் பருவ மலர்வளம், தேனீக் கூட்ட மேலாண்மை, பாதுகாப்பான பெட்டி கையாளுதல் ஆகியவற்றை பயிற்சி பெற்ற தேனீ வளர்ப்பாளர் அல்லது வேளாண் அலுவலரிடம் கற்றுக்கொள்ளுங்கள்.",
      "நீர் மற்றும் மலர்வளம் கிடைக்கும், மக்கள்/கால்நடைகள் பாதுகாப்பாகச் செல்லக்கூடிய இடத்தில் பெட்டிகளை வைக்கவும்.",
      "பூச்சிக்கொல்லி பாதிப்பைத் தவிர்க்கவும்; அவசியமான தெளிப்பை அருகிலுள்ள தேனீ வளர்ப்பாளர்களுடன் ஒருங்கிணைத்து, குறிப்பாக பூக்கும் போது லேபிள் பாதுகாப்பைப் பின்பற்றவும்.",
      "கூட்டுகளைத் திறக்க அல்லது நகர்த்த முன் பயிற்சியும் பாதுகாப்பு உபகரணமும் பெறவும்; கடுமையான தேனீக் கொட்டல் ஒவ்வாமை உள்ளவர்கள் கூடுதல் கவனம் தேவை.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("water_quality", "topic", "Irrigation water quality", "பாசன நீர்தரம்",
     ["water quality", "salty water", "salinity water", "hard water", "irrigation water", "நீர்தரம்", "உவர் நீர்", "பாசன நீர்"],
     ["Poor-quality or saline water can reduce germination and yield and may build salts in soil, especially where drainage is poor.",
      "Test irrigation water for salinity and other locally relevant parameters through an agriculture or water-testing laboratory.",
      "Use efficient irrigation and maintain drainage; do not attempt to correct saline soil without test-based local advice.",
      "Crop tolerance differs, so select crops and irrigation practices based on measured water quality and local recommendations.",
      'Check moisture in the root zone before irrigating and adjust after rain; a fixed daily schedule may waste water or waterlog roots.',
      'Repair leaks and keep channels or drip emitters clear so water reaches the intended plants evenly.',
      'During sensitive stages such as establishment, flowering, or fruit filling, avoid sudden severe water stress.'],
     ["தரமற்ற அல்லது உவர் நீர் முளைப்பு, மகசூலைக் குறைத்து, குறிப்பாக வடிகால் குறைவான இடங்களில் மண்ணில் உப்பைச் சேர்க்கலாம்.",
      "வேளாண் அல்லது நீர் பரிசோதனை ஆய்வகத்தில் பாசன நீரின் உவர்ப்பு மற்றும் தேவையான பிற அளவுகளைச் சோதிக்கவும்.",
      "திறமையான பாசனம் மற்றும் நல்ல வடிகாலைப் பராமரிக்கவும்; பரிசோதனை மற்றும் உள்ளூர் ஆலோசனையின்றி உவர் மண்ணைச் சரிசெய்ய முயலாதீர்கள்.",
      "பயிர்களின் உவர் சகிப்புத்தன்மை மாறுபடும்; அளவிடப்பட்ட நீர்தரம் மற்றும் உள்ளூர் பரிந்துரைப்படி பயிரையும் பாசன முறையையும் தேர்ந்தெடுக்கவும்.",
      'பாசனத்திற்கு முன் வேர் பகுதியில் ஈரத்தைச் சரிபார்த்து மழைக்குப் பிறகு அளவை மாற்றுங்கள்; தினசரி ஒரே அட்டவணை நீரை வீணாக்கலாம் அல்லது வேர் பகுதியில் நீர் தேக்கலாம்.',
      'கசிவுகளைச் சரிசெய்து, கால்வாய் அல்லது சொட்டுநீர் வெளியீடுகள் அடைப்பு இல்லாமல் இருப்பதை உறுதி செய்யுங்கள்.',
      'நாற்று நிலைபெறுதல், பூத்தல், காய் நிரம்புதல் போன்ற முக்கிய நிலைகளில் திடீர் கடுமையான நீர் அழுத்தத்தைத் தவிர்க்குங்கள்.'])

_add("pruning", "topic", "Pruning and plant training", "கவாத்து மற்றும் செடி பயிற்சி",
     ["pruning", "prune", "training plants", "staking", "trellis", "கிளை வெட்டுதல்", "கவாத்து", "பந்தல்", "முட்டுக்கொடுத்தல்"],
     ["Pruning methods differ greatly by crop and growth stage; first confirm whether the crop needs pruning or only removal of damaged branches.",
      "Use clean, sharp tools and disinfect them between plants when disease spread is possible.",
      "Avoid removing too much healthy foliage at once, as it can reduce photosynthesis and expose fruit or stems to sun damage.",
      "Support climbing or heavy-fruiting plants with suitable stakes or trellises and secure stems without constricting them.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["கவாத்து முறை பயிர் மற்றும் வளர்ச்சி நிலையைப் பொறுத்து மாறும்; கவாத்து தேவையா அல்லது சேதமடைந்த கிளைகளை மட்டும் அகற்ற வேண்டுமா என்பதை முதலில் உறுதிசெய்யவும்.",
      "சுத்தமான கூர்மையான கருவிகளைப் பயன்படுத்தி, நோய் பரவும் வாய்ப்புள்ளபோது செடிகளுக்கிடையே கிருமிநீக்கம் செய்யவும்.",
      "ஒரே நேரத்தில் அதிக ஆரோக்கியமான இலைகளை அகற்றாதீர்கள்; ஒளிச்சேர்க்கை குறைந்து காய்/தண்டு வெயிலால் பாதிக்கப்படலாம்.",
      "படரும் அல்லது அதிக காய்கள் தரும் செடிகளுக்கு பொருத்தமான குச்சி/பந்தல் அமைத்து, தண்டை நெருக்காமல் கட்டவும்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("farm_safety", "topic", "Farm and equipment safety", "பண்ணை மற்றும் கருவி பாதுகாப்பு",
     ["farm safety", "tractor safety", "equipment safety", "machinery", "farm machine", "விவசாய கருவி", "டிராக்டர்", "பண்ணை பாதுகாப்பு"],
     ["Read equipment instructions and use guards, suitable footwear and other protective equipment.",
      "Switch off and isolate machinery before clearing blockages, cleaning or servicing moving parts.",
      "Keep children and bystanders away from operating machinery; never carry extra riders unless the equipment is designed for it.",
      "Store fuel, pesticides and fertilizers separately from food, drinking water and living areas.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["கருவி வழிமுறைகளைப் படித்து, பாதுகாப்புக் கவசம், பொருத்தமான காலணி மற்றும் தேவையான பாதுகாப்பு உபகரணங்களைப் பயன்படுத்தவும்.",
      "அடைப்பை நீக்க, சுத்தம் செய்ய அல்லது பழுது பார்க்கும் முன் இயந்திரத்தை நிறுத்தி மின்சாரம்/இயக்கத்தைத் துண்டிக்கவும்.",
      "இயங்கும் இயந்திரங்களிலிருந்து குழந்தைகள் மற்றும் பார்வையாளர்களை விலக்கி வைக்கவும்; கருவி வடிவமைக்கப்படாவிட்டால் கூடுதல் நபர்களை ஏற்றாதீர்கள்.",
      "எரிபொருள், பூச்சிக்கொல்லி, உரங்களை உணவு, குடிநீர், குடியிருப்பு பகுதிகளிலிருந்து தனியாகச் சேமிக்கவும்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

# ---- symptoms ----
_add("yellow", "symptom", "Yellowing leaves", "இலை மஞ்சளாதல்",
     ["yellow", "yellowing", "yellowish", "chlorosis", "மஞ்சள்", "மஞ்சளாக"],
     ["Possible causes: nitrogen deficiency (older leaves, uniform), iron/zinc deficiency (young leaves, between veins), waterlogging, root rot or wilt, virus (mosaic pattern) or sap-sucking pests.",
      "Check: old or young leaves? whole plant or patches? roots and soil moisture?",
      "Do not add fertilizer blindly - confirm with a soil or leaf test.",
      'Note when the problem began, which plant parts are affected first, and whether symptoms are spreading; this information helps diagnosis.',
      'Check both sides of leaves, stems, roots, and nearby plants, and compare with a healthy plant of the same crop.',
      'Avoid applying pesticide or fertilizer based on a symptom alone; several different causes can look similar.'],
     ["காரணங்கள்: தழைச்சத்துக் குறைபாடு (பழைய இலைகள் சீராக மஞ்சளாதல்), இரும்பு/துத்தநாகக் குறைபாடு (இளம் இலைகள், நரம்புகளுக்கிடையே), நீர் தேக்கம், வேர் அழுகல்/வாடல், வைரஸ் (மொசைக் வடிவம்), சாறு உறிஞ்சும் பூச்சிகள்.",
      "பழைய இலைகளா இளம் இலைகளா, முழுச் செடியா திட்டுத் திட்டாகவா, வேர் மற்றும் மண் ஈரம் எப்படி என்று பாருங்கள்.",
      "காரணம் தெரியாமல் உரம் இடாதீர்கள்; மண்/இலை பரிசோதனை செய்யுங்கள்.",
      'பிரச்சனை எப்போது தொடங்கியது, எந்தப் பகுதி முதலில் பாதிக்கப்பட்டது, அறிகுறி பரவுகிறதா என்பதைக் குறித்துக் கொள்ளுங்கள்; இது நோயறிதலுக்கு உதவும்.',
      'இலைகளின் இருபுறம், தண்டு, வேர், அருகிலுள்ள செடிகளைப் பார்த்து அதே பயிரின் ஆரோக்கியமான செடியுடன் ஒப்பிடுங்கள்.',
      'அறிகுறியை மட்டும் வைத்து பூச்சிக்கொல்லி அல்லது உரம் பயன்படுத்த வேண்டாம்; பல காரணங்கள் ஒரே மாதிரியாகத் தோன்றலாம்.'])

_add("spots", "symptom", "Leaf spots", "இலைப் புள்ளிகள்",
     ["spot", "spots", "lesion", "blotch", "patches", "brown spot", "black spot", "புள்ளி", "புள்ளிகள்", "கறை"],
     ["Ring-like spots can indicate early blight; water-soaked, angular spots can indicate a bacterial disease.",
      "Remove infected leaves and water at the base so leaves stay dry.",
      "Photograph clearly and show it to an agriculture officer - do not spray by guesswork.",
      'Note when the problem began, which plant parts are affected first, and whether symptoms are spreading; this information helps diagnosis.',
      'Check both sides of leaves, stems, roots, and nearby plants, and compare with a healthy plant of the same crop.',
      'Avoid applying pesticide or fertilizer based on a symptom alone; several different causes can look similar.'],
     ["வளையம் போன்ற புள்ளிகள் ஏர்லி ப்ளைட்டைக் குறிக்கலாம்; நீர் ஊறிய, கோணல் புள்ளிகள் பாக்டீரியா நோயைக் குறிக்கலாம்.",
      "பாதித்த இலைகளை அகற்றி, இலைகளை நனைக்காமல் நீர் பாய்ச்சவும்.",
      "தெளிவான புகைப்படம் எடுத்து வேளாண் அலுவலரிடம் காட்டுங்கள்; ஊகத்தில் மருந்து தெளிக்காதீர்கள்.",
      'பிரச்சனை எப்போது தொடங்கியது, எந்தப் பகுதி முதலில் பாதிக்கப்பட்டது, அறிகுறி பரவுகிறதா என்பதைக் குறித்துக் கொள்ளுங்கள்; இது நோயறிதலுக்கு உதவும்.',
      'இலைகளின் இருபுறம், தண்டு, வேர், அருகிலுள்ள செடிகளைப் பார்த்து அதே பயிரின் ஆரோக்கியமான செடியுடன் ஒப்பிடுங்கள்.',
      'அறிகுறியை மட்டும் வைத்து பூச்சிக்கொல்லி அல்லது உரம் பயன்படுத்த வேண்டாம்; பல காரணங்கள் ஒரே மாதிரியாகத் தோன்றலாம்.'])

_add("wilt", "symptom", "Wilting plants", "செடி வாடுதல்",
     ["wilt", "wilting", "wilted", "drooping", "dry up", "drying up", "வாடல்", "வாடுது", "வாடி", "காய்ந்து"],
     ["Wilting in moist soil points to root rot or wilt disease (Fusarium/bacterial).",
      "Cut the stem: brown internal tissue or ooze suggests wilt - remove the plant and improve drainage.",
      "If soil is dry, irrigate. Midday wilting that recovers by evening is heat stress.",
      'Note when the problem began, which plant parts are affected first, and whether symptoms are spreading; this information helps diagnosis.',
      'Check both sides of leaves, stems, roots, and nearby plants, and compare with a healthy plant of the same crop.',
      'Avoid applying pesticide or fertilizer based on a symptom alone; several different causes can look similar.'],
     ["மண் ஈரமாக இருந்தும் செடி வாடினால் வேர் அழுகல் அல்லது வாடல் நோய் (ஃபியூசேரியம்/பாக்டீரியா) இருக்கலாம்.",
      "தண்டை வெட்டிப் பாருங்கள்; உள்ளே பழுப்பு நிறம் அல்லது கசிவு இருந்தால் வாடல் நோய் சாத்தியம் - அந்தச் செடியை அகற்றி வடிகாலை மேம்படுத்துங்கள்.",
      "மண் உலர்ந்திருந்தால் நீர் பாய்ச்சவும்; மதிய வெப்பத்தில் வாடி மாலையில் மீண்டால் அது வெப்ப அழுத்தம்.",
      'பிரச்சனை எப்போது தொடங்கியது, எந்தப் பகுதி முதலில் பாதிக்கப்பட்டது, அறிகுறி பரவுகிறதா என்பதைக் குறித்துக் கொள்ளுங்கள்; இது நோயறிதலுக்கு உதவும்.',
      'இலைகளின் இருபுறம், தண்டு, வேர், அருகிலுள்ள செடிகளைப் பார்த்து அதே பயிரின் ஆரோக்கியமான செடியுடன் ஒப்பிடுங்கள்.',
      'அறிகுறியை மட்டும் வைத்து பூச்சிக்கொல்லி அல்லது உரம் பயன்படுத்த வேண்டாம்; பல காரணங்கள் ஒரே மாதிரியாகத் தோன்றலாம்.'])

_add("powdery", "symptom", "White powder on leaves", "இலையில் வெள்ளைத் தூள்",
     ["powdery", "white powder", "white patch", "white patches", "mildew", "downy", "வெள்ளைத் தூள்", "சாம்பல் நோய்", "பொடி"],
     ["This is often powdery mildew, common when days are dry and nights humid.",
      "Improve airflow and remove affected leaves.",
      "If needed, use a sulphur-based or other approved fungicide as per label and local recommendation.",
      'Note when the problem began, which plant parts are affected first, and whether symptoms are spreading; this information helps diagnosis.',
      'Check both sides of leaves, stems, roots, and nearby plants, and compare with a healthy plant of the same crop.',
      'Avoid applying pesticide or fertilizer based on a symptom alone; several different causes can look similar.'],
     ["இது பெரும்பாலும் சாம்பல் நோய் (powdery mildew); வறண்ட பகலும் ஈரமான இரவும் இருக்கும் போது பரவும்.",
      "காற்றோட்டத்தை அதிகரித்து, பாதித்த இலைகளை அகற்றவும்.",
      "தேவைப்பட்டால் உள்ளூர் பரிந்துரை, லேபிள்படி கந்தகம் சார்ந்த அல்லது அனுமதிக்கப்பட்ட பூஞ்சைக்கொல்லியைப் பயன்படுத்தவும்.",
      'பிரச்சனை எப்போது தொடங்கியது, எந்தப் பகுதி முதலில் பாதிக்கப்பட்டது, அறிகுறி பரவுகிறதா என்பதைக் குறித்துக் கொள்ளுங்கள்; இது நோயறிதலுக்கு உதவும்.',
      'இலைகளின் இருபுறம், தண்டு, வேர், அருகிலுள்ள செடிகளைப் பார்த்து அதே பயிரின் ஆரோக்கியமான செடியுடன் ஒப்பிடுங்கள்.',
      'அறிகுறியை மட்டும் வைத்து பூச்சிக்கொல்லி அல்லது உரம் பயன்படுத்த வேண்டாம்; பல காரணங்கள் ஒரே மாதிரியாகத் தோன்றலாம்.'])

_add("curl", "symptom", "Leaf curl / twisting", "இலை சுருட்டை",
     ["curl", "curling", "curled", "twisted", "crinkled", "சுருள்", "சுருட்டை", "சுருண்டு", "முறுக்கு"],
     ["Leaf curl is often a virus spread by whitefly or thrips, or caused by mites. Viruses have no cure.",
      "Remove infected plants early; use yellow sticky traps and resistant varieties.",
      "Herbicide drift (e.g. 2,4-D) can also twist leaves.",
      'Note when the problem began, which plant parts are affected first, and whether symptoms are spreading; this information helps diagnosis.',
      'Check both sides of leaves, stems, roots, and nearby plants, and compare with a healthy plant of the same crop.',
      'Avoid applying pesticide or fertilizer based on a symptom alone; several different causes can look similar.'],
     ["இலை சுருட்டை பெரும்பாலும் வெள்ளை ஈ/இலைப்பேன் மூலம் பரவும் வைரஸ் அல்லது சிலந்திப் பேனால் ஏற்படும்; வைரஸுக்கு மருந்து இல்லை.",
      "பாதித்த செடிகளை ஆரம்பத்திலேயே அகற்றவும்; மஞ்சள் ஒட்டும் பொறி, எதிர்ப்பு ரகங்களைப் பயன்படுத்தவும்.",
      "களைக்கொல்லி (2,4-D) காற்றில் படிந்தாலும் இலைகள் முறுக்கிக் கொள்ளலாம்.",
      'பிரச்சனை எப்போது தொடங்கியது, எந்தப் பகுதி முதலில் பாதிக்கப்பட்டது, அறிகுறி பரவுகிறதா என்பதைக் குறித்துக் கொள்ளுங்கள்; இது நோயறிதலுக்கு உதவும்.',
      'இலைகளின் இருபுறம், தண்டு, வேர், அருகிலுள்ள செடிகளைப் பார்த்து அதே பயிரின் ஆரோக்கியமான செடியுடன் ஒப்பிடுங்கள்.',
      'அறிகுறியை மட்டும் வைத்து பூச்சிக்கொல்லி அல்லது உரம் பயன்படுத்த வேண்டாம்; பல காரணங்கள் ஒரே மாதிரியாகத் தோன்றலாம்.'])

_add("holes", "symptom", "Holes / chewed leaves", "இலையில் துளைகள்",
     ["hole", "holes", "chewed", "eaten", "bitten", "frass", "துளை", "துளைகள்", "அரித்த", "கடித்த"],
     ["Holes or chewed edges point to chewing insects such as caterpillars or beetles.",
      "Look under leaves and at night; hand-pick, and use pheromone or light traps.",
      "Neem or Bt-based products can help early on; if you suspect fall armyworm in maize, contact an agriculture officer quickly.",
      'Note when the problem began, which plant parts are affected first, and whether symptoms are spreading; this information helps diagnosis.',
      'Check both sides of leaves, stems, roots, and nearby plants, and compare with a healthy plant of the same crop.',
      'Avoid applying pesticide or fertilizer based on a symptom alone; several different causes can look similar.'],
     ["இலையில் துளைகள் அல்லது கடிபட்ட விளிம்புகள் கம்பளிப்புழு/வண்டு போன்ற கடிக்கும் பூச்சிகளைக் குறிக்கும்.",
      "இலையின் அடிப்பகுதியிலும் இரவிலும் தேடுங்கள்; கையால் பொறுக்கி அழிக்கவும்; இனக்கவர்ச்சி/விளக்குப் பொறி பயன்படுத்தவும்.",
      "ஆரம்ப நிலையில் வேம்பு அல்லது Bt போன்ற உயிரியல் முறைகள் உதவும்; மக்காச்சோளத்தில் படைப்புழு சந்தேகமெனில் உடனே வேளாண் அலுவலரை அணுகவும்.",
      'பிரச்சனை எப்போது தொடங்கியது, எந்தப் பகுதி முதலில் பாதிக்கப்பட்டது, அறிகுறி பரவுகிறதா என்பதைக் குறித்துக் கொள்ளுங்கள்; இது நோயறிதலுக்கு உதவும்.',
      'இலைகளின் இருபுறம், தண்டு, வேர், அருகிலுள்ள செடிகளைப் பார்த்து அதே பயிரின் ஆரோக்கியமான செடியுடன் ஒப்பிடுங்கள்.',
      'அறிகுறியை மட்டும் வைத்து பூச்சிக்கொல்லி அல்லது உரம் பயன்படுத்த வேண்டாம்; பல காரணங்கள் ஒரே மாதிரியாகத் தோன்றலாம்.'])




# ---- cross-crop questions and common growing problems ----
# These entries apply across crops; use the crop-specific entries above as
# additional context when a question names a particular crop.
_add("flower_drop_general", "topic", "Flower drop across crops", "பல்வேறு பயிர்களில் பூ உதிர்வு",
     ["flowers falling", "flowers dropping", "flower drop", "blossom drop",
      "flowers fall off", "flowers falling off", "flowers dry and fall",
      "blossoms falling", "plant flowers falling", "no fruit after flowering",
      "flowers but no fruit", "பூக்கள் உதிர்வு", "பூக்கள் உதிர்கின்றன", "பூ உதிர்வு"],
     ["Flowers can drop because of heat or cold stress, irregular watering, waterlogged roots, poor pollination, excess nitrogen, or pests. The most likely cause depends on the crop and its growth stage.",
      "Keep soil moisture steady without waterlogging, use mulch where suitable, avoid excessive nitrogen, and protect pollinators. In hot weather, reduce plant stress and follow crop-specific local guidance.",
      "Inspect buds and flowers for insect damage before using any pesticide. Do not spray during pollinator activity, and do not use a pesticide unless the pest and locally approved product are identified.",
      "To narrow it down, share the crop, location, plant age, recent weather, watering routine, and fertilizer used.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["வெப்பம் அல்லது குளிர் அழுத்தம், ஒழுங்கற்ற பாசனம், வேர் பகுதியில் நீர் தேங்குதல், மகரந்தச் சேர்க்கை குறைவு, அதிக தழைச்சத்து அல்லது பூச்சிகளால் பூக்கள் உதிரலாம். சரியான காரணம் பயிர் மற்றும் வளர்ச்சி நிலையைப் பொறுத்தது.",
      "மண்ணின் ஈரத்தைச் சீராக வைத்துக் கொள்ளுங்கள்; நீர் தேங்க விடாதீர்கள். பொருத்தமான இடங்களில் மூடாக்கு பயன்படுத்தி, அதிக தழைச்சத்து உரத்தைத் தவிர்த்து, மகரந்தச் சேர்க்கை உயிரினங்களைப் பாதுகாக்கவும். வெப்பத்தில் செடிகளின் அழுத்தத்தைக் குறைத்து உள்ளூர் பயிர் வழிகாட்டுதலைப் பின்பற்றுங்கள்.",
      "பூச்சிக்கொல்லி பயன்படுத்துவதற்கு முன் பூக்கள் மற்றும் மொட்டுகளில் சேதம் உள்ளதா பாருங்கள். தேனீக்கள் செயல்படும் நேரத்தில் தெளிக்க வேண்டாம்; பூச்சியை உறுதி செய்து உள்ளூரில் அனுமதிக்கப்பட்ட மருந்தை மட்டுமே பயன்படுத்துங்கள்.",
      "காரணத்தைத் துல்லியமாகக் கண்டறிய பயிர், இடம், செடியின் வயது, சமீபத்திய வானிலை, பாசன முறை, பயன்படுத்திய உரம் ஆகியவற்றைச் சொல்லுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("fruit_drop_general", "topic", "Young fruit drop", "இளம் காய்கள் உதிர்வு",
     ["fruit falling", "fruits falling", "fruit drop", "young fruits falling",
      "small fruits falling", "baby fruits falling", "fruitlets dropping",
      "unripe fruit falling", "காய் உதிர்வு", "இளம் காய்கள் உதிர்கின்றன"],
     ["Young fruits may drop after poor pollination, heat or drought stress, irregular watering, waterlogging, nutrient imbalance, heavy fruit load, or pest/disease damage. Some crops naturally shed a portion of young fruits.",
      "Maintain even soil moisture, ensure good drainage, avoid sudden heavy fertilizer applications, and inspect dropped fruit and stems for signs of pests or disease. Nutrient needs vary by crop, so avoid applying a nutrient without a clear reason or soil-test guidance.",
      "Tell me the crop, approximate fruit size, plant age, weather, watering schedule, and whether the fallen fruits show spots, holes, or rotting.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["மகரந்தச் சேர்க்கை குறைவு, வெப்பம் அல்லது வறட்சி அழுத்தம், ஒழுங்கற்ற பாசனம், நீர் தேக்கம், சத்துச் சமநிலையின்மை, அதிக காய்ப்பாரம் அல்லது பூச்சி/நோய் காரணமாக இளம் காய்கள் உதிரலாம். சில பயிர்களில் ஒரு பகுதி இளம் காய்கள் இயல்பாக உதிரும்.",
      "மண்ணின் ஈரத்தைச் சீராக வைத்துக் கொள்ளுங்கள்; நல்ல வடிகால் உறுதி செய்யுங்கள்; ஒரே நேரத்தில் அதிக உரம் இடுவதைத் தவிர்த்து, உதிர்ந்த காய்கள் மற்றும் காம்புகளில் பூச்சி/நோய் அறிகுறிகளைப் பாருங்கள். பயிருக்கு ஏற்ப சத்துத் தேவை மாறுவதால் காரணமின்றி உரமிட வேண்டாம்.",
      "பயிர், காயின் அளவு, செடியின் வயது, வானிலை, பாசன அட்டவணை, உதிர்ந்த காய்களில் புள்ளி/துளை/அழுகல் உள்ளதா என்பதைக் கூறுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("not_flowering_general", "topic", "Plants not flowering", "செடிகளில் பூ வராமை",
     ["not flowering", "no flowers", "plant not flowering", "plants not blooming",
      "no bloom", "not producing flowers", "flowers not coming",
      "செடியில் பூ வரவில்லை", "பூ பூக்கவில்லை"],
     ["Plants may fail to flower because they are too young, receive unsuitable day length or temperature, get too much nitrogen, lack enough light, are pruned at the wrong time, or are under water or root stress. The cause is crop-specific.",
      "Check whether the crop has reached its normal flowering age, whether it gets the light it needs, and whether fertilizer is too nitrogen-heavy. Keep watering consistent and avoid drastic pruning or fertilizer changes.",
      "Share the crop/variety, age after sowing or planting, location, sunlight hours, and fertilizer schedule for more targeted advice.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["செடி இன்னும் இளமையாக இருப்பது, பொருத்தமற்ற பகல் நேரம்/வெப்பநிலை, அதிக தழைச்சத்து, போதிய வெளிச்சமின்மை, தவறான நேரத்தில் கவாத்து அல்லது வேர்/நீர் அழுத்தம் காரணமாக பூ வராமல் இருக்கலாம். காரணம் பயிரைப் பொறுத்தது.",
      "பயிர் பூக்கும் வழக்கமான வயதை அடைந்துள்ளதா, தேவையான வெளிச்சம் கிடைக்கிறதா, உரத்தில் தழைச்சத்து மிகுதியா எனப் பாருங்கள். பாசனத்தைச் சீராக வைத்துக் கொண்டு திடீர் கவாத்து அல்லது உர மாற்றங்களைத் தவிர்க்கவும்.",
      "பயிர்/ரகம், விதைத்த அல்லது நட்ட பின் வயது, இடம், தினசரி சூரிய ஒளி நேரம், உர அட்டவணை ஆகியவற்றைச் சொல்லுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("yellow_leaves_general", "topic", "Yellow leaves across crops", "இலை மஞ்சளாதல்",
     ["yellow leaves", "leaves turning yellow", "yellowing leaves", "leaves are yellow",
      "yellow leaf", "yellow plant", "இலை மஞ்சளாகிறது", "இலைகள் மஞ்சள்"],
     ["Yellow leaves can be caused by overwatering or drought, poor drainage, nitrogen or other nutrient deficiency, root damage, pests, or disease. Older leaves yellowing first can mean something different from new leaves yellowing first.",
      "Check soil moisture and drainage first. Look at whether the yellowing starts on old or new leaves and whether it is uniform or patchy. Inspect the underside of leaves and stems for pests. Avoid adding fertilizer until the likely cause is clearer.",
      "Tell me the crop, whether old or new leaves turn yellow first, the pattern (whole leaf or between veins), and your watering/fertilizer routine.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["அதிக பாசனம் அல்லது வறட்சி, வடிகால் குறைவு, தழைச்சத்து அல்லது பிற சத்துக் குறைபாடு, வேர் சேதம், பூச்சி அல்லது நோயால் இலைகள் மஞ்சளாகலாம். முதிர்ந்த இலைகள் முதலில் மஞ்சளாவது மற்றும் புதிய இலைகள் முதலில் மஞ்சளாவது வெவ்வேறு காரணங்களைக் குறிக்கலாம்.",
      "முதலில் மண்ணின் ஈரத்தையும் வடிகாலையும் பாருங்கள். பழைய இலைகளா புதிய இலைகளா முதலில் மஞ்சளாகின்றன, முழு இலையா நரம்புகளுக்கு இடையிலா என கவனியுங்கள். இலை அடிப்பகுதி மற்றும் தண்டில் பூச்சிகளைப் பாருங்கள். காரணம் தெளிவாகும்வரை உரம் சேர்க்க வேண்டாம்.",
      "பயிர், பழைய/புதிய இலைகளில் எது முதலில் மஞ்சளாகிறது, மஞ்சளின் வடிவம், பாசனம்/உர முறை ஆகியவற்றைச் சொல்லுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("wilting_general", "topic", "Wilting plants", "செடி வாடுதல்",
     ["plant wilting", "plants wilting", "wilting plant", "leaves drooping",
      "plant is drooping", "suddenly wilted", "செடி வாடுகிறது", "இலைகள் தொங்குகின்றன"],
     ["Wilting may result from dry soil, waterlogged roots, root injury, vascular disease, or severe heat. Adding more water is not always the answer: check the soil before watering.",
      "If soil is dry, water the root zone thoroughly. If it is wet, stop extra watering and improve drainage. Check whether one plant or many plants are affected and whether stems show darkening or cutting reveals brown vascular tissue. Remove severely diseased plants carefully and seek local diagnosis if wilting spreads.",
      "Tell me the crop, whether soil is dry or wet, whether wilting happens at midday or all day, and whether one plant or a patch is affected.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["மண் காய்ந்திருத்தல், வேர் பகுதியில் நீர் தேங்குதல், வேர் காயம், தண்டு வழி நோய் அல்லது கடும் வெப்பத்தால் செடி வாடலாம். வாடுகிறது என்பதற்காக எப்போதும் கூடுதல் நீர் ஊற்ற வேண்டாம்; முதலில் மண்ணைப் பாருங்கள்.",
      "மண் காய்ந்திருந்தால் வேர் பகுதியில் நன்றாக நீர் பாய்ச்சுங்கள். மண் ஈரமாக இருந்தால் கூடுதல் பாசனத்தை நிறுத்தி வடிகாலை மேம்படுத்துங்கள். ஒரு செடியா பல செடிகளா பாதிக்கப்பட்டுள்ளன, தண்டில் கருமை உள்ளதா எனப் பாருங்கள். வாடுதல் பரவினால் உள்ளூர் நிபுணரிடம் நோயறிதல் பெறுங்கள்.",
      "பயிர், மண் உலர்ந்துள்ளதா ஈரமாக உள்ளதா, மதியத்தில் மட்டும் வாடுகிறதா நாள் முழுவதுமா, ஒரு செடியா பல செடிகளா என்பதைக் கூறுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("leaf_curl_general", "topic", "Leaf curl and distortion", "இலை சுருட்டல்",
     ["leaf curl", "leaves curling", "curled leaves", "leaf twisting",
      "leaves twisted", "leaves distorted", "இலை சுருட்டல்", "இலை சுருண்டுள்ளது"],
     ["Leaf curling can be caused by sap-sucking insects, viral disease, heat or water stress, herbicide drift, or nutrient imbalance. The pattern and presence of insects help distinguish causes.",
      "Inspect the underside of leaves for whiteflies, aphids, and mites. Check whether new growth is distorted and whether nearby plants show similar symptoms. Remove badly affected plants only when a serious viral disease is suspected and local guidance supports it; control the identified cause rather than spraying blindly.",
      "Share the crop, photos if available, whether insects are visible, and whether the newest leaves or older leaves curl.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["சாறு உறிஞ்சும் பூச்சிகள், வைரஸ் நோய், வெப்பம்/நீர் அழுத்தம், களைக்கொல்லி காற்றில் படுதல் அல்லது சத்துச் சமநிலையின்மையால் இலை சுருளலாம். இலை சுருளும் விதமும் பூச்சிகள் உள்ளனவா என்பதும் காரணத்தை வேறுபடுத்த உதவும்.",
      "இலை அடிப்பகுதியில் வெள்ளை ஈ, அசுவினி, சிலந்திப்பேன் போன்றவை உள்ளனவா பாருங்கள். புதிய வளர்ச்சி சிதைந்துள்ளதா, அருகிலுள்ள செடிகளும் பாதிக்கப்பட்டுள்ளனவா கவனியுங்கள். காரணமின்றி மருந்து தெளிக்காமல் உறுதி செய்யப்பட்ட காரணத்தைக் கையாளுங்கள்.",
      "பயிர், சாத்தியமெனில் படம், பூச்சிகள் உள்ளனவா, புதிய இலைகளா பழைய இலைகளா சுருளுகின்றன என்பதைக் கூறுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("leaf_spots_general", "topic", "Leaf spots and browning", "இலைப் புள்ளிகள் மற்றும் கருகல்",
     ["leaf spots", "spots on leaves", "brown spots", "black spots on leaves",
      "leaves turning brown", "leaf blight", "leaf lesions", "இலையில் புள்ளிகள்", "இலை கருகல்"],
     ["Spots and browning may be caused by fungal or bacterial disease, nutrient problems, sun scorch, or chemical injury. Wet foliage and poor airflow can worsen some diseases.",
      "Avoid overhead watering where practical, improve airflow, remove badly affected fallen leaves, and clean tools between plants. Do not use a fungicide or antibiotic-like product without identifying the likely disease and checking local approved guidance.",
      "Tell me the crop, whether spots are circular or angular, their color, whether they spread after rain, and whether the underside of leaves has growth or rings.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["பூஞ்சை/பாக்டீரியா நோய், சத்துப் பிரச்சனை, வெயில் கருகல் அல்லது ரசாயனப் பாதிப்பால் இலைப் புள்ளிகள் மற்றும் கருகல் ஏற்படலாம். ஈரமான இலைகளும் காற்றோட்டக் குறைவும் சில நோய்களை அதிகரிக்கலாம்.",
      "சாத்தியமான இடங்களில் மேலிருந்து இலைகளை நனைக்காமல் பாசனம் செய்யுங்கள்; காற்றோட்டத்தை மேம்படுத்துங்கள்; கடுமையாகப் பாதித்த உதிர்ந்த இலைகளை அகற்றி, செடிகளுக்கிடையில் கருவிகளைச் சுத்தம் செய்யுங்கள். நோயை அடையாளம் காணாமல் பூஞ்சைக்கொல்லி அல்லது பிற மருந்துகளைப் பயன்படுத்த வேண்டாம்.",
      "பயிர், புள்ளிகள் வட்டமா கோணமாகவா, நிறம், மழைக்குப் பிறகு பரவுகிறதா, இலை அடியில் படலம்/வளையம் உள்ளதா என்பதைக் கூறுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("poor_growth_general", "topic", "Slow or stunted growth", "வளர்ச்சி குறைவு",
     ["plant not growing", "slow growth", "stunted growth", "stunted plants",
      "crop growth poor", "poor plant growth", "seedlings not growing",
      "செடி வளரவில்லை", "வளர்ச்சி குறைவு"],
     ["Slow growth can result from poor seed quality, unsuitable temperature, compacted or poorly drained soil, wrong pH, nutrient deficiency, root damage, weeds, or pests.",
      "Check drainage, root-zone moisture, sunlight, plant spacing, and weeds. Compare symptoms across the field and consider a soil test before applying fertilizer. Avoid increasing fertilizer blindly, as excess salts can damage roots.",
      "Tell me the crop, age, soil type, spacing, recent weather, and fertilizer history.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["மோசமான விதைத் தரம், பொருத்தமற்ற வெப்பநிலை, இறுக்கமான/வடிகால் குறைந்த மண், தவறான pH, சத்துக் குறைபாடு, வேர் சேதம், களை அல்லது பூச்சியால் வளர்ச்சி குறையலாம்.",
      "வடிகால், வேர் பகுதி ஈரம், சூரிய ஒளி, இடைவெளி, களை ஆகியவற்றைப் பாருங்கள். உரமிடுவதற்கு முன் மண் பரிசோதனையைப் பரிசீலியுங்கள். கண்மூடித்தனமாக அதிக உரம் இட வேண்டாம்; அதிக உப்புச் சத்து வேரைச் சேதப்படுத்தலாம்.",
      "பயிர், வயது, மண் வகை, நடவு இடைவெளி, சமீபத்திய வானிலை, உர விவரங்களைச் சொல்லுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("fruit_cracking_general", "topic", "Fruit cracking and splitting", "காய்கள் வெடித்தல்",
     ["fruit cracking", "fruits cracking", "fruit splitting", "tomato cracking",
      "cracked fruits", "fruit split open", "காய் வெடிப்பு", "காய்கள் பிளக்கின்றன"],
     ["Fruit cracking often follows a sudden change in water availability, especially after dry soil is followed by heavy rain or irrigation. Variety, maturity, temperature, and nutrient balance can also affect cracking.",
      "Keep watering as even as practical, use mulch where appropriate, harvest at the recommended maturity, and avoid letting plants become very dry before heavy watering. Recommendations differ by crop and variety.",
      "Tell me which crop, whether cracking occurs near the stem or elsewhere, and whether it follows rain or irrigation.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["மண் காய்ந்த பின் திடீரென அதிக மழை அல்லது பாசனம் கிடைப்பதால் காய்கள் வெடிக்கலாம். ரகம், முதிர்ச்சி, வெப்பநிலை மற்றும் சத்துச் சமநிலையும் தாக்கம் ஏற்படுத்தும்.",
      "சாத்தியமானவரை பாசனத்தைச் சீராக வைத்துக் கொள்ளுங்கள்; பொருத்தமான இடங்களில் மூடாக்கு இடுங்கள்; பரிந்துரைக்கப்பட்ட முதிர்ச்சி நிலையில் அறுவடை செய்யுங்கள். நீண்ட நேரம் மண் காயவிட்டு பின்னர் அதிக நீர் கொடுப்பதைத் தவிர்க்கவும்.",
      "எந்தப் பயிர், காம்பு அருகிலா வேறு இடத்திலா வெடிக்கிறது, மழை/பாசனத்துக்குப் பிறகா என்பதைக் கூறுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("germination_general", "topic", "Poor seed germination", "விதை முளைப்பு குறைவு",
     ["seeds not germinating", "poor germination", "seed not sprouting",
      "seeds not sprouting", "low germination", "விதை முளைக்கவில்லை", "முளைப்பு குறைவு"],
     ["Poor germination may be due to old or damaged seed, sowing too deep, unsuitable soil temperature, dry soil, waterlogging, seed-borne disease, or poor seed-to-soil contact.",
      "Use good-quality seed from a reliable source, sow at the crop-recommended depth, keep the seed zone moist but not waterlogged, and avoid sowing into unsuitable conditions. Check the seed packet and local crop recommendations.",
      "Tell me the crop, seed age/source, days since sowing, sowing depth, and whether the soil is dry or wet.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["பழைய/சேதமடைந்த விதை, மிக ஆழமாக விதைத்தல், பொருத்தமற்ற மண் வெப்பநிலை, மண் காய்தல், நீர் தேக்கம், விதை வழி நோய் அல்லது விதை-மண் தொடர்பு குறைவு காரணமாக முளைப்பு குறையலாம்.",
      "நம்பகமான மூலத்திலிருந்து நல்ல விதை வாங்கி, பயிருக்கு பரிந்துரைக்கப்பட்ட ஆழத்தில் விதையுங்கள். விதை இருக்கும் மண் ஈரமாக இருக்கட்டும்; நீர் தேங்க விடாதீர்கள். விதை உறை மற்றும் உள்ளூர் பரிந்துரைகளைப் பின்பற்றுங்கள்.",
      "பயிர், விதையின் வயது/மூலம், விதைத்துப் பின் நாட்கள், விதைத்த ஆழம், மண் உலர்ந்ததா ஈரமா என்பதைக் கூறுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("root_rot_general", "topic", "Root rot and waterlogged soil", "வேர் அழுகல் மற்றும் நீர் தேக்கம்",
     ["root rot", "rotting roots", "roots are rotten", "waterlogged soil",
      "soil waterlogging", "bad smell from roots", "வேர் அழுகல்", "மண்ணில் நீர் தேங்குகிறது"],
     ["Root rot is commonly associated with prolonged waterlogging and soil-borne pathogens, although the exact cause varies. Roots may turn brown or black and become soft.",
      "Improve drainage, avoid repeated overwatering, and use clean planting material. Do not reuse badly affected soil or planting containers without proper cleaning. Crop-specific disease management may be needed after diagnosis.",
      "Tell me the crop, soil drainage, watering frequency, and whether roots are brown/soft or simply dry.",
      'Avoid working soil when it is excessively wet, because this can compact the soil and damage its structure.',
      'Add organic matter gradually and keep the soil covered where practical to reduce erosion and moisture loss.',
      'Test soil pH and salinity if plants repeatedly perform poorly despite reasonable watering and fertilization.'],
     ["நீண்ட நேரம் நீர் தேங்குதல் மற்றும் மண்ணிலுள்ள நோய்க்கிருமிகள் வேர் அழுகலுடன் தொடர்புடையவை. வேர்கள் பழுப்பு/கருப்பாகி மென்மையாகலாம்.",
      "வடிகாலை மேம்படுத்தி, மீண்டும் மீண்டும் அதிக நீர் ஊற்றுவதைத் தவிர்த்து, ஆரோக்கியமான நடவுப் பொருளைப் பயன்படுத்துங்கள். பாதிக்கப்பட்ட மண்/கொள்கலன்களைச் சுத்தம் செய்யாமல் மீண்டும் பயன்படுத்த வேண்டாம். நோயறிதலுக்குப் பிறகு பயிருக்கேற்ற மேலாண்மை தேவைப்படலாம்.",
      "பயிர், மண் வடிகால், பாசன அடிக்கடி, வேர்கள் பழுப்பு/மென்மையா அல்லது உலர்ந்துள்ளனவா என்பதைக் கூறுங்கள்.",
      'மண் மிகவும் ஈரமாக இருக்கும்போது உழுவதைத் தவிர்க்குங்கள்; அது மண்ணை இறுக்கமாக்கி அமைப்பைச் சேதப்படுத்தலாம்.',
      'கரிமப் பொருளை படிப்படியாகச் சேர்த்து, சாத்தியமான இடங்களில் மண்ணை மூடி வைத்து அரிப்பையும் ஈர இழப்பையும் குறையுங்கள்.',
      'சரியான பாசனம் மற்றும் உரமிடுதலுக்குப் பிறகும் பயிர் தொடர்ந்து மோசமாக இருந்தால் மண் pH மற்றும் உப்புத்தன்மையைப் பரிசோதியுங்கள்.'])

_add("pest_identification_general", "topic", "Identifying crop pests", "பயிர் பூச்சிகளை அடையாளம் காணுதல்",
     ["what insect is this", "identify pest", "which pest", "insect on plant",
      "bugs on leaves", "pest on crop", "crop pest identification",
      "பயிரில் பூச்சி", "எந்த பூச்சி"],
     ["Different pests need different management, so identify the insect and the damage before choosing a control. Check the underside of leaves, tender shoots, flowers, and fruits; note whether leaves have holes, silvering, sticky honeydew, webbing, or curled growth.",
      "Start with field monitoring, removing a small number of visible pests by hand where safe, conserving beneficial insects, and using traps or barriers appropriate to the pest. Use only locally registered pesticides according to the label when needed.",
      "Describe the crop, insect size/color, where it is found, and the damage. A clear close-up photo can help, but an in-person local diagnosis may still be needed.",
      'Scout the field regularly and identify the pest before choosing a control; beneficial insects may help keep pests in check.',
      'Use integrated pest management: sanitation, crop rotation, traps or physical barriers where suitable, and a locally approved pesticide only when necessary.',
      'Follow the product label for crop, dose, protective equipment, re-entry interval, and pre-harvest interval; never mix products casually.'],
     ["ஒவ்வொரு பூச்சிக்கும் வேறு மேலாண்மை தேவை; எனவே கட்டுப்பாட்டு முறையைத் தேர்வு செய்வதற்கு முன் பூச்சி மற்றும் சேதத்தை அடையாளம் காணுங்கள். இலை அடிப்பகுதி, இளம் தண்டு, பூ, காய்களைப் பாருங்கள்; துளை, வெள்ளி நிறக் கீறல், ஒட்டும் சாறு, வலை அல்லது சுருண்ட வளர்ச்சி உள்ளதா கவனியுங்கள்.",
      "வயலில் தொடர்ந்து கண்காணிக்கவும்; பாதுகாப்பாக முடிந்தால் காணப்படும் சில பூச்சிகளை கையால் அகற்றவும்; நன்மை தரும் பூச்சிகளைப் பாதுகாத்து, பொருத்தமான பொறி/தடைகளைப் பயன்படுத்துங்கள். தேவையானபோது உள்ளூரில் பதிவு செய்யப்பட்ட மருந்தை லேபிளின்படி மட்டுமே பயன்படுத்துங்கள்.",
      "பயிர், பூச்சியின் அளவு/நிறம், அது இருக்கும் இடம், சேதத்தின் விவரத்தைச் சொல்லுங்கள். தெளிவான அருகுப் படம் உதவலாம்; இருப்பினும் உள்ளூர் நேரடி ஆய்வு தேவைப்படலாம்.",
      'பூச்சியை கட்டுப்படுத்தும் முறையைத் தேர்வுசெய்வதற்கு முன் வயலைத் தொடர்ந்து கண்காணித்து பூச்சியை அடையாளம் காணுங்கள்; நன்மை தரும் பூச்சிகளும் உதவலாம்.',
      'ஒருங்கிணைந்த பூச்சி மேலாண்மையைப் பயன்படுத்துங்கள்: வயல் சுத்தம், பயிர் சுழற்சி, பொருத்தமான பொறிகள்/தடைகள், அவசியமானால் உள்ளூரில் அனுமதிக்கப்பட்ட மருந்து.',
      'மருந்தின் லேபிளில் உள்ள பயிர், அளவு, பாதுகாப்பு உபகரணம், மீண்டும் வயலுக்குள் செல்லும் நேரம், அறுவடைக்கு முன் காத்திருக்கும் காலம் ஆகியவற்றைப் பின்பற்றுங்கள்; மருந்துகளைத் தன்னிச்சையாகக் கலக்க வேண்டாம்.'])

_add("watering_schedule_general", "topic", "How often to water crops", "எவ்வளவு அடிக்கடி பாசனம் செய்ய வேண்டும்",
     ["how often water", "how much water", "watering schedule", "when to irrigate",
      "how often should i water", "how much should i water",
      "எவ்வளவு தண்ணீர்", "எப்போது பாசனம்"],
     ["Water needs depend on crop, growth stage, soil texture, weather, and irrigation method, so one schedule does not fit every farm. Sandy soil usually dries faster than clay soil; seedlings and flowering/fruiting stages can be sensitive to water stress.",
      "Check moisture in the root zone rather than watering only by the calendar. Aim for even moisture and good drainage; reduce irrigation after rain and avoid prolonged waterlogging. Drip irrigation can improve water efficiency where suitable.",
      "Tell me the crop, growth stage, soil type, local weather, and irrigation method for a more useful schedule.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["பயிர், வளர்ச்சி நிலை, மண் அமைப்பு, வானிலை, பாசன முறை ஆகியவற்றைப் பொறுத்து நீர் தேவை மாறும்; எல்லா பண்ணைக்கும் ஒரே அட்டவணை பொருந்தாது. மணற்பாங்கான மண் களிமண்ணைவிட விரைவாகக் காயலாம்; நாற்று மற்றும் பூ/காய்ப்பருவங்களில் நீர் அழுத்தம் பாதிக்கலாம்.",
      "நாள்காட்டியை மட்டும் நம்பாமல் வேர் பகுதியில் ஈரத்தைச் சரிபாருங்கள். ஈரத்தைச் சீராகவும் வடிகாலை நன்றாகவும் வைத்துக் கொள்ளுங்கள்; மழைக்குப் பிறகு பாசனத்தைக் குறைத்து, நீண்ட நேர நீர் தேக்கத்தைத் தவிர்க்கவும். பொருத்தமான இடங்களில் சொட்டுநீர் நீரைச் சேமிக்க உதவும்.",
      "பயிர், வளர்ச்சி நிலை, மண் வகை, உள்ளூர் வானிலை, பாசன முறை ஆகியவற்றைச் சொல்லுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

_add("fertilizer_amount_general", "topic", "Choosing fertilizer and amount", "உரம் மற்றும் அளவு தேர்வு",
     ["which fertilizer", "what fertilizer", "fertilizer dose", "how much fertilizer",
      "fertilizer for plants", "best fertilizer", "which manure",
      "எந்த உரம்", "உர அளவு"],
     ["The right fertilizer and amount depend on the crop, soil test, growth stage, expected yield, and local recommendations. Too much fertilizer can burn roots, increase salt stress, pollute water, and cause excess leafy growth.",
      "If possible, use a soil test and follow recommendations from your local agriculture department/KVK. Apply nutrients at the right stage and split doses when recommended. Do not mix products unless the label or a qualified adviser confirms compatibility.",
      "Tell me the crop, area, age/stage, soil-test result if available, and what fertilizer has already been applied.",
      'Base fertilizer decisions on crop stage and soil-test results where possible; split applications when the crop recommendation calls for it.',
      'Keep fertilizer away from direct contact with seeds, stems, and roots unless the product directions specifically allow it.',
      'Store fertilizers dry and labelled, away from children, animals, food, and drinking water.'],
     ["சரியான உரமும் அளவும் பயிர், மண் பரிசோதனை, வளர்ச்சி நிலை, எதிர்பார்க்கும் மகசூல், உள்ளூர் பரிந்துரைகளைப் பொறுத்தது. அதிக உரம் வேரை எரிக்கலாம், உப்புச் சுமையை அதிகரிக்கலாம், நீரை மாசுபடுத்தலாம், இலை வளர்ச்சியை மட்டும் அதிகரிக்கலாம்.",
      "முடிந்தால் மண் பரிசோதனை செய்து உள்ளூர் வேளாண் துறை/KVK பரிந்துரையைப் பின்பற்றுங்கள். சரியான வளர்ச்சி நிலையில் உரமிடுங்கள்; பரிந்துரைக்கப்பட்டால் அளவைப் பிரித்து இடுங்கள். லேபிள் அல்லது தகுதியான ஆலோசகர் உறுதி செய்யாமல் உரங்களை கலக்க வேண்டாம்.",
      "பயிர், நிலப்பரப்பு, வயது/நிலை, மண் பரிசோதனை முடிவு இருந்தால் அது, ஏற்கனவே பயன்படுத்திய உரம் ஆகியவற்றைச் சொல்லுங்கள்.",
      'முடிந்தால் மண் பரிசோதனை மற்றும் பயிரின் வளர்ச்சி நிலையை அடிப்படையாகக் கொண்டு உரமிடுங்கள்; பரிந்துரைக்கப்பட்டால் அளவைப் பிரித்து இடுங்கள்.',
      'தயாரிப்பு வழிமுறை அனுமதிக்காவிட்டால் உரத்தை விதை, தண்டு, வேர் ஆகியவற்றுடன் நேரடியாகத் தொடும் வகையில் இட வேண்டாம்.',
      'உரங்களை உலர்ந்த, லேபிள் உள்ள இடத்தில் குழந்தைகள், விலங்குகள், உணவு மற்றும் குடிநீரிலிருந்து விலக்கி வையுங்கள்.'])

_add("market_price_general", "topic", "Crop market prices", "பயிர் சந்தை விலை",
     ["today price", "market price today", "crop price today", "mandi price",
      "current price", "today market rate", "இன்றைய விலை", "சந்தை விலை"],
     ["Crop prices change by date, market, grade, quality, and arrival volume. This offline app does not have live market-price access, so it should not guess today's price.",
      "Check the official Agmarknet portal or your regulated market/marketing committee for the latest arrivals and prices. Compare the same crop, grade, and unit, and include transport and commission costs when estimating your net return.",
      'Start with a small, practical change and observe the result before changing several practices at once.',
      'Keep simple records of dates, inputs, weather, symptoms, and results so you can compare what works on your farm.',
      'Exact recommendations depend on crop variety, location, soil, and season; confirm local rates and regulations with the agriculture department or KVK.'],
     ["பயிர் விலை தேதி, சந்தை, தரம், தரநிலை, வரத்து அளவு ஆகியவற்றைப் பொறுத்து மாறும். இந்த ஆஃப்லைன் செயலியில் நேரடி விலைத் தகவல் இல்லை; எனவே இன்றைய விலையை ஊகித்துச் சொல்லாது.",
      "சமீபத்திய வரத்து மற்றும் விலைக்கு அதிகாரப்பூர்வ Agmarknet தளம் அல்லது ஒழுங்குமுறை சந்தையைப் பாருங்கள். ஒரே பயிர், தரம், அலகு ஆகியவற்றை ஒப்பிட்டு, போக்குவரத்து மற்றும் கமிஷன் செலவுகளையும் கணக்கில் கொள்ளுங்கள்.",
      'ஒரே நேரத்தில் பல முறைகளை மாற்றாமல், நடைமுறைக்கு ஏற்ற ஒரு சிறிய மாற்றத்துடன் தொடங்கி அதன் விளைவைக் கவனியுங்கள்.',
      'தேதி, பயன்படுத்திய பொருட்கள், வானிலை, அறிகுறிகள், முடிவுகள் ஆகியவற்றைப் பதிவு செய்து உங்கள் பண்ணையில் எது சிறப்பாகச் செயல்படுகிறது என ஒப்பிடுங்கள்.',
      'சரியான பரிந்துரைகள் பயிர் ரகம், இடம், மண், பருவம் ஆகியவற்றைப் பொறுத்தவை; அளவு மற்றும் விதிமுறைகளுக்கு உள்ளூர் வேளாண் துறை அல்லது KVK-யிடம் உறுதி செய்யுங்கள்.'])

# =====================================================================
#  UI TEXT
# =====================================================================
TEXT = {
    "understood": {"en": "Understood: ", "ta": "புரிந்து கொண்டது: "},
    "no_match": {
        "en": "I could not find a reliable match in the offline farming knowledge base.\n\n"
              "I can help with crop growing, sowing seasons, soil, fertilizer, irrigation, pests, diseases, weeds, seedling care, organic methods, harvest and storage, farm costs, livestock, mushrooms, protected cultivation and more.\n\n"
              "Try asking with the crop/topic and details, e.g. \"How do I grow chilli?\", \"Why are my rice leaves yellow?\", or \"How can I improve soil fertility?\". For crop problems, include your district, crop age, symptoms and recent watering/fertilizer use. This offline version cannot reliably answer every possible question; live weather and current prices also require current sources.",
        "ta": "ஆஃப்லைன் விவசாய அறிவுத்தளத்தில் உங்கள் கேள்விக்கான நம்பகமான பொருத்தம் கிடைக்கவில்லை.\n\n"
              "பயிர் வளர்ப்பு, விதைப்பு பருவம், மண், உரம், பாசனம், பூச்சி, நோய், களை, நாற்று பராமரிப்பு, இயற்கை முறைகள், அறுவடை/சேமிப்பு, பண்ணைச் செலவு, கால்நடை, காளான், பசுமைக் குடில் போன்றவற்றில் உதவ முடியும்.\n\n"
              "பயிர்/தலைப்புடன் விவரமாகக் கேளுங்கள்; உதா: \"மிளகாய் எப்படி வளர்ப்பது?\", \"நெல் இலை ஏன் மஞ்சளாகிறது?\", \"மண் வளத்தை எப்படி உயர்த்துவது?\". பயிர் பிரச்சனைக்கு மாவட்டம், பயிரின் வயது, அறிகுறிகள், சமீபத்திய பாசனம்/உர விவரங்களைச் சொல்லுங்கள். ஆஃப்லைன் பதிப்பு எல்லா கேள்விகளுக்கும் உறுதியான பதில் தர முடியாது; நேரடி வானிலை மற்றும் தற்போதைய சந்தை விலைகளுக்கு புதுப்பிக்கப்பட்ட ஆதாரங்கள் தேவை."},
    "disclaimer": {
        "en": "General guidance only. For a confirmed diagnosis or chemical advice, "
              "consult your local agriculture officer or KVK.",
        "ta": "இது பொது வழிகாட்டுதல் மட்டுமே. உறுதியான நோய் கண்டறிதல் அல்லது மருந்து ஆலோசனைக்கு "
              "உள்ளூர் வேளாண் அலுவலர் அல்லது KVK-வை அணுகுங்கள்."},
    "thinking": {"en": "Preparing your answer...", "ta": "பதில் தயாராகிறது..."},
    "src_kb": {"en": "Source: built-in knowledge base", "ta": "ஆதாரம்: உள்ளமைந்த அறிவுத்தளம்"},
    "src_ai": {"en": "Source: Claude AI + knowledge base", "ta": "ஆதாரம்: Claude AI + அறிவுத்தளம்"},
    }


def tr(key, lang):
    return TEXT[key][lang]


# =====================================================================
#  ANSWER ENGINE
# =====================================================================
_SINGLE_EN_KW = sorted({
    k for e in KB for k in e["kw"]
    if re.fullmatch(r"[a-z]{5,}", k)
})


def _kw_hit(keyword, text):
    """True if keyword appears in text (English: word-prefix, Tamil: substring)."""
    if re.search(r"[\u0B80-\u0BFF]", keyword):
        return keyword in text
    if len(keyword) <= 3:
        return re.search(r"\b" + re.escape(keyword) + r"\b", text) is not None
    return re.search(r"\b" + re.escape(keyword), text) is not None


def find_matches(question, max_other=2):
    """Return (best_crop_entry_or_None, [other_entries]) ranked by relevance."""
    q = question.lower()
    tokens = [t for t in re.findall(r"[a-z]+", q) if len(t) >= 5]
    scores = {}

    for entry in KB:
        score = 0.0
        matched_phrases = 0
        for kw in entry["kw"]:
            if _kw_hit(kw, q):
                # Full question phrases are stronger signals than single crop names.
                score += 3.0 if " " in kw else (1.5 if len(kw) > 6 else 1.0)
                matched_phrases += 1

        if score == 0:  # fuzzy rescue for spelling / speech errors
            entry_words = {w for kw in entry["kw"] for w in re.findall(r"[a-z]+", kw)}
            for tok in tokens:
                close = difflib.get_close_matches(tok, _SINGLE_EN_KW, n=1, cutoff=0.78)
                if close and close[0] in entry_words:
                    score += 0.8
                    break

        if score > 0:
            # Crop names provide context, but should not dominate a problem/topic match.
            if entry["kind"] == "crop":
                score *= 0.85
            elif entry["kind"] in ("topic", "symptom"):
                score += 0.15 * matched_phrases
            scores[entry["id"]] = score

    by_id = {e["id"]: e for e in KB}
    ranked = sorted(scores, key=lambda i: -scores[i])
    crop = next((by_id[i] for i in ranked if by_id[i]["kind"] == "crop"), None)
    others = [by_id[i] for i in ranked if by_id[i]["kind"] != "crop"][:max_other]
    return crop, others


def kb_answer(question, lang):
    """Build a structured answer from the knowledge base."""
    crop, others = find_matches(question)
    entries = ([crop] if crop else []) + others
    if not entries:
        return [(tr("no_match", lang) + "\n", "")]

    parts = [(tr("understood", lang) + " • ".join(e["name"][lang] for e in entries) + "\n", "src")]
    for entry in entries:
        parts.append((f"\n{entry['name'][lang]}\n", "h"))
        for bullet in entry[lang]:
            parts.append((f"• {bullet}\n", ""))
    parts.append(("\n" + tr("disclaimer", lang) + "\n", "note"))
    return parts


def kb_notes_for_ai(question):
    """English reference notes passed to the AI to ground its answer."""
    crop, others = find_matches(question, max_other=3)
    entries = ([crop] if crop else []) + others
    return "\n".join(f"[{e['name']['en']}] " + " ".join(e["en"]) for e in entries)


# =====================================================================
#  OFFLINE ANSWER MODE
# =====================================================================
def ai_available():
    """This edition intentionally works without API keys or cloud AI."""
    return False


# =====================================================================
#  SPEECH RECOGNITION
# =====================================================================
def mic_status():
    """(ok, description) - checks sounddevice + at least one input device."""
    if sd is None:
        return False, "sounddevice/PortAudio missing (pip install sounddevice)"
    try:
        device = sd.query_devices(kind="input")   # default input device
        return True, device["name"]
    except Exception:
        return False, "No microphone detected"


_SOUND_FIXES = {  # common mis-hearings of farming words
    r"\bparty\b": "paddy",
    r"\bsugar can\b": "sugarcane",
    r"\bground nut\b": "groundnut",
    r"\btomatoe\b": "tomato",
    r"\bfertlizer\b": "fertilizer",
    r"\bpestiside\b": "pesticide",
    r"\birrigat\b": "irrigation",
}


def clean_transcript(text, lang):
    """Light cleanup + fix common farming-word mis-hearings (English only)."""
    text = " ".join(text.split())
    if lang == "en":
        low = text.lower()
        for pattern, fix in _SOUND_FIXES.items():
            low = re.sub(pattern, fix, low)
        # snap near-miss words to known farming vocabulary
        words = []
        for w in low.split():
            bare = re.sub(r"[^a-z]", "", w)
            if len(bare) >= 5:
                close = difflib.get_close_matches(bare, _SINGLE_EN_KW, n=1, cutoff=0.86)
                if close and close[0] != bare:
                    w = w.replace(bare, close[0])
            words.append(w)
        text = " ".join(words)
        text = text[:1].upper() + text[1:]
    return text


class SpeechEngine:
    """Microphone capture (sounddevice) + Google recognition with alternatives and retry."""

    def __init__(self):
        self.recognizer = sr.Recognizer()   # still used for recognize_google
        self.recognizer.operation_timeout = 15
        self.pause_threshold = 1.0          # seconds of silence that end a phrase
        self.pre_roll_blocks = 6            # keep ~0.3 s before speech starts

    @staticmethod
    def _rms(block):
        return float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))

    def _record(self, on_status):
        """Calibrate, wait for speech, record until silence. Returns sr.AudioData."""
        if sd is None:
            raise OSError("sounddevice is not installed")

        blocksize = int(SAMPLE_RATE * BLOCK_SECONDS)
        q = queue.Queue()

        def callback(indata, frames, time_info, status):
            q.put(indata[:, 0].copy())

        try:
            stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                                    blocksize=blocksize, callback=callback)
            stream.start()
        except sd.PortAudioError as error:
            raise OSError(str(error))

        try:
            # 1) calibrate for background noise (~1 s)
            on_status("🔧 Calibrating for background noise...")
            levels = [self._rms(q.get(timeout=3)) for _ in range(int(1.0 / BLOCK_SECONDS))]
            threshold = max(float(np.mean(levels)) * 1.5, MIN_ENERGY)

            # 2) wait for speech to start
            on_status("🎙 Listening... please speak clearly")
            pre_roll = deque(maxlen=self.pre_roll_blocks)
            frames = []
            waited = 0.0
            while True:
                block = q.get(timeout=3)
                if self._rms(block) > threshold:
                    frames.extend(pre_roll)
                    frames.append(block)
                    break
                pre_roll.append(block)
                waited += BLOCK_SECONDS
                if waited >= LISTEN_TIMEOUT:
                    raise sr.WaitTimeoutError("listening timed out while waiting for phrase to start")

            # 3) record until a long-enough pause (or the phrase limit)
            silence = 0.0
            spoken = 0.0
            while spoken < PHRASE_LIMIT and silence < self.pause_threshold:
                block = q.get(timeout=3)
                frames.append(block)
                spoken += BLOCK_SECONDS
                silence = silence + BLOCK_SECONDS if self._rms(block) <= threshold else 0.0
        except queue.Empty:
            raise OSError("no audio received from the microphone")
        finally:
            stream.stop()
            stream.close()

        return sr.AudioData(np.concatenate(frames).tobytes(), SAMPLE_RATE, 2)

    def listen(self, language_code, on_status):
        """Return list of candidate transcripts, best first."""
        last_error = None
        for attempt in range(1, LISTEN_ATTEMPTS + 1):
            try:
                audio = self._record(on_status)

                on_status("⏳ Converting speech to text...")
                raw = self.recognizer.recognize_google(
                    audio, language=language_code, show_all=True
                )
                candidates = [
                    a["transcript"].strip()
                    for a in (raw.get("alternative", []) if isinstance(raw, dict) else [])
                    if a.get("transcript", "").strip()
                ]
                if not candidates:
                    raise sr.UnknownValueError()
                return candidates

            except (sr.WaitTimeoutError, sr.UnknownValueError) as error:
                last_error = error
                if attempt < LISTEN_ATTEMPTS:
                    on_status("🔁 Didn't catch that - listening again...")
        raise last_error


# =====================================================================
#  UI HELPERS
# =====================================================================
def make_output(parent, height=10):
    frame = tk.Frame(parent, bg=WHITE)
    box = tk.Text(
        frame, height=height, wrap="word", font=("Segoe UI", 11),
        bg="#edf7f0", fg=DARK, relief="flat", padx=12, pady=10, state="disabled"
    )
    scrollbar = ttk.Scrollbar(frame, command=box.yview)
    box.configure(yscrollcommand=scrollbar.set)
    box.tag_configure("h", font=("Segoe UI", 12, "bold"), foreground=GREEN_DARK, spacing1=4)
    box.tag_configure("note", font=("Segoe UI", 9, "italic"), foreground=MUTED)
    box.tag_configure("src", font=("Segoe UI", 10, "bold"), foreground=PURPLE)
    scrollbar.pack(side="right", fill="y")
    box.pack(side="left", fill="both", expand=True)
    return frame, box


def write_output(box, parts):
    box.config(state="normal")
    box.delete("1.0", "end")
    for text, tag in parts:
        box.insert("end", text, (tag,) if tag else ())
    box.config(state="disabled")


# =====================================================================
#  MAIN APPLICATION
# =====================================================================
class AgroSmartAI:

    def __init__(self, root):
        self.root = root
        self.root.title("AgroSmart AI - Smart Farming Assistant")
        self.root.geometry("1150x750")
        self.root.minsize(950, 640)
        self.root.configure(bg=BG)

        self.language = tk.StringVar(value="English")
        self.speech = SpeechEngine()
        self.listening = False
        self.current_page = "Crop Disease"

        self.build_header()
        self.build_sidebar()
        self.build_main_area()
        self.show_page(self.current_page)

    # ---------- helpers ----------
    def lang_key(self):
        return "ta" if self.language.get() == "தமிழ்" else "en"

    def ui(self, fn, *args, **kwargs):
        """Run a UI update safely on the main thread."""
        def run():
            try:
                fn(*args, **kwargs)
            except tk.TclError:
                pass  # widget was destroyed (page changed)
        self.root.after(0, run)

    def make_card(self):
        card = tk.Frame(self.content, bg=WHITE,
                        highlightbackground="#cfe4d9", highlightthickness=1)
        card.pack(fill="both", expand=True)
        return card

    # ---------- HEADER ----------
    def build_header(self):
        header = tk.Frame(self.root, bg=DARK, height=75)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="🌱 AgroSmart AI", font=("Segoe UI", 19, "bold"),
                 bg=DARK, fg="#4ade80").pack(side="left", padx=20)
        tk.Label(header, text="Smart Agriculture Companion", font=("Segoe UI", 10),
                 bg=DARK, fg="white").pack(side="left", padx=10)

        combo = ttk.Combobox(header, textvariable=self.language,
                             values=["English", "தமிழ்"], state="readonly", width=12)
        combo.pack(side="right", padx=20)
        combo.bind("<<ComboboxSelected>>", lambda e: self.show_page(self.current_page))
        tk.Label(header, text="🌐 Language / மொழி", bg=DARK, fg="#cbd5e1",
                 font=("Segoe UI", 9)).pack(side="right")

    # ---------- SIDEBAR ----------
    def build_sidebar(self):
        sidebar = tk.Frame(self.root, bg=DARK, width=210)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="MAIN MENU", bg=DARK, fg="#94a3b8",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=20)

        pages = [("Dashboard", "🏠"), ("Crop Disease", "🌿"), ("Crop Analysis", "📊"),
                 ("Farming Advisor", "🌾"), ("Farm Tools", "🧮"), ("Schemes", "📋")]
        for page, icon in pages:
            tk.Button(
                sidebar, text=f"  {icon}  {page}", font=("Segoe UI", 11), anchor="w",
                bg=DARK, fg="white", activebackground=GREEN_DARK, activeforeground="white",
                relief="flat", padx=12, pady=13, cursor="hand2",
                command=lambda p=page: self.show_page(p)
            ).pack(fill="x", padx=8, pady=3)

        tk.Label(sidebar, text="🌱 Grow smarter\nwith AgroSmart AI", bg="#123b32",
                 fg="#bbf7d0", font=("Segoe UI", 11, "bold"), pady=20
                 ).pack(side="bottom", fill="x", padx=10, pady=15)

    # ---------- MAIN AREA ----------
    def build_main_area(self):
        self.main = tk.Frame(self.root, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)

        self.page_title = tk.Label(self.main, text="", font=("Segoe UI", 23, "bold"),
                                   bg=BG, fg=GREEN_DARK)
        self.page_title.pack(anchor="w", padx=25, pady=(20, 5))

        self.subtitle = tk.Label(self.main, text="", font=("Segoe UI", 10), bg=BG, fg=MUTED)
        self.subtitle.pack(anchor="w", padx=27, pady=(0, 10))

        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=22, pady=(0, 10))

        tk.Label(self.root, text="AgroSmart AI | Smart Farming Assistant",
                 bg="#dcece3", fg=MUTED, pady=5).pack(side="bottom", fill="x")

    # ---------- PAGE NAVIGATION ----------
    def show_page(self, page):
        self.current_page = page
        for widget in self.content.winfo_children():
            widget.destroy()

        if page == "Crop Disease":
            self.page_title.config(text="🌿 Crop Disease Help")
            self.subtitle.config(text="Describe crop symptoms by voice or text.")
            self.crop_disease_page()
        elif page in ("Crop Analysis", "Farming Advisor"):
            self.page_title.config(
                text="📊 Crop Analysis" if page == "Crop Analysis" else "🌾 Smart Farming Advisor")
            self.subtitle.config(text="Ask farming questions using text or voice.")
            self.advisor_page()
        elif page == "Farm Tools":
            self.page_title.config(text="🧮 Farm Tools & Profit Calculator")
            self.subtitle.config(text="Estimate farm revenue and costs; explore practical offline guides.")
            self.farm_tools_page()
        elif page == "Dashboard":
            self.page_title.config(text="🌱 AgroSmart AI Dashboard")
            self.subtitle.config(text="Your smart farming workspace.")
            self.dashboard_page()
        else:
            self.page_title.config(text="📋 Farming Schemes")
            self.subtitle.config(text="Government agriculture schemes")
            self.schemes_page()

    # ---------- DASHBOARD ----------
    def dashboard_page(self):
        card = self.make_card()
        tk.Label(card, text="Welcome, Farmer!", bg=WHITE, fg=GREEN_DARK,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=25, pady=(25, 8))
        tk.Label(card,
                 text="Ask farming questions by voice (English or Tamil), "
                      "and get guidance on 10 major crops, pests, diseases, fertilizer, "
                      "irrigation, seasons and schemes.",
                 bg=WHITE, fg=DARK, font=("Segoe UI", 12), wraplength=720,
                 justify="left").pack(anchor="w", padx=25, pady=5)

        mic_ok, mic_name = mic_status()
        rows = [
            ("🎙 Voice input", f"Ready - {mic_name}" if mic_ok else f"Not ready - {mic_name}",
             GREEN_DARK if mic_ok else RED),
            ("📚 Answers", "Offline built-in farming knowledge base (no API key required)", GREEN_DARK),
            ("🌐 Internet", "Typing and farm calculator work offline; voice recognition may need internet", MUTED),
        ]
        for title, value, color in rows:
            row = tk.Frame(card, bg="#edf7f0")
            row.pack(fill="x", padx=25, pady=5)
            tk.Label(row, text=title, bg="#edf7f0", fg=DARK, width=30, anchor="w",
                     font=("Segoe UI", 11, "bold")).pack(side="left", padx=12, pady=10)
            tk.Label(row, text=value, bg="#edf7f0", fg=color, anchor="w",
                     font=("Segoe UI", 10), wraplength=480, justify="left").pack(side="left")

    # ---------- FARM TOOLS ----------
    def farm_tools_page(self):
        card = self.make_card()
        tk.Label(card, text="Farm Revenue & Profit Calculator", bg=WHITE, fg=GREEN_DARK,
                 font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=22, pady=(18, 6))
        tk.Label(card, text="Enter your own estimates. Results are calculations, not guaranteed market returns.",
                 bg=WHITE, fg=MUTED, font=("Segoe UI", 10), wraplength=760,
                 justify="left").pack(anchor="w", padx=22, pady=(0, 12))

        form = tk.Frame(card, bg=WHITE)
        form.pack(fill="x", padx=22)
        fields = [
            ("Cultivated area (acres)", "1"),
            ("Expected yield per acre (kg)", "1000"),
            ("Expected selling price per kg (₹)", "25"),
            ("Total estimated costs (₹)", "10000"),
        ]
        self.calc_inputs = []
        for i, (label, default) in enumerate(fields):
            tk.Label(form, text=label, bg=WHITE, fg=DARK, font=("Segoe UI", 10, "bold")).grid(
                row=i, column=0, sticky="w", padx=(0, 12), pady=5)
            entry = ttk.Entry(form, width=24)
            entry.insert(0, default)
            entry.grid(row=i, column=1, sticky="w", pady=5)
            self.calc_inputs.append(entry)

        result = tk.Frame(card, bg="#edf7f0", highlightbackground="#cfe4d9", highlightthickness=1)
        result.pack(fill="x", padx=22, pady=12)
        self.calc_result = tk.Label(result, text="Click Calculate to estimate your results.",
                                    bg="#edf7f0", fg=DARK, font=("Segoe UI", 11),
                                    justify="left", anchor="w", wraplength=740)
        self.calc_result.pack(fill="x", padx=14, pady=12)
        tk.Button(form, text="Calculate", command=self.calculate_profit, bg=GREEN,
                  fg=WHITE, font=("Segoe UI", 10, "bold"), relief="flat",
                  padx=16, pady=8, cursor="hand2").grid(row=4, column=0, sticky="w", pady=10)
        tk.Button(form, text="Reset", command=self.reset_calculator, bg=MUTED,
                  fg=WHITE, font=("Segoe UI", 10, "bold"), relief="flat",
                  padx=16, pady=8, cursor="hand2").grid(row=4, column=1, sticky="w", pady=10)

        tk.Label(card, text="Quick guides (ask the Farming Advisor for more detail)", bg=WHITE,
                 fg=GREEN_DARK, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=22, pady=(4, 4))
        guide_text = (
            "• Soil: test before choosing fertilizer; avoid applying lime/gypsum without test results.\n"
            "• Water: use soil moisture and crop stage; avoid both drought stress and waterlogging.\n"
            "• Pest control: identify the pest first, conserve beneficial insects and follow product labels.\n"
            "• Records: note dates, input quantities, labour, yield, sale price and transport costs.\n"
            "• Live weather, current market prices and scheme eligibility are not fetched by this offline app."
        )
        tk.Label(card, text=guide_text, bg=WHITE, fg=DARK, font=("Segoe UI", 10),
                 justify="left", anchor="w", wraplength=760).pack(fill="x", padx=22, pady=(0, 16))

    def calculate_profit(self):
        try:
            area, yield_per_acre, price_per_kg, costs = [float(x.get().strip()) for x in self.calc_inputs]
            if area <= 0 or yield_per_acre < 0 or price_per_kg < 0 or costs < 0:
                raise ValueError
            production = area * yield_per_acre
            revenue = production * price_per_kg
            profit = revenue - costs
            margin = (profit / revenue * 100) if revenue else 0.0
            label = "Estimated loss" if profit < 0 else "Estimated profit"
            self.calc_result.config(text=(
                f"Total expected production: {production:,.2f} kg\n"
                f"Gross revenue: ₹{revenue:,.2f}\n"
                f"Total costs: ₹{costs:,.2f}\n"
                f"{label}: ₹{abs(profit):,.2f}\n"
                f"Profit margin: {margin:.1f}% of revenue\n"
                f"Break-even selling price: ₹{(costs / production):,.2f}/kg" if production > 0 else
                f"Total expected production: 0 kg\nGross revenue: ₹0.00\nTotal costs: ₹{costs:,.2f}\nEstimated loss: ₹{costs:,.2f}\nEnter a positive yield to calculate break-even price."
            ))
        except ValueError:
            messagebox.showerror("Check your inputs", "Enter valid numbers. Area must be above zero; other values cannot be negative.")

    def reset_calculator(self):
        for entry, value in zip(self.calc_inputs, ("1", "1000", "25", "10000")):
            entry.delete(0, "end")
            entry.insert(0, value)
        self.calc_result.config(text="Click Calculate to estimate your results.")

    # ---------- SCHEMES ----------
    def schemes_page(self):
        lang = self.lang_key()
        entry = next(e for e in KB if e["id"] == "scheme")
        card = self.make_card()
        tk.Label(card, text=entry["name"][lang], bg=WHITE, fg=GREEN_DARK,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=25, pady=(25, 10))
        for bullet in entry[lang]:
            tk.Label(card, text=f"• {bullet}", bg=WHITE, fg=DARK, font=("Segoe UI", 12),
                     wraplength=760, justify="left").pack(anchor="w", padx=25, pady=4)

    # ---------- CROP DISEASE PAGE ----------
    def crop_disease_page(self):
        card = self.make_card()

        tk.Label(card, text="Describe crop symptoms (type or speak)", bg=WHITE, fg=DARK,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=20, pady=(20, 8))

        self.symptom_box = tk.Text(card, height=5, wrap="word", font=("Segoe UI", 11),
                                   relief="solid", bd=1)
        self.symptom_box.pack(fill="x", padx=20)

        self.symptom_status = tk.Label(card, text="Click the microphone and speak.",
                                       bg=WHITE, fg=MUTED, font=("Segoe UI", 10), anchor="w")
        self.symptom_status.pack(fill="x", padx=20, pady=4)

        row = tk.Frame(card, bg=WHITE)
        row.pack(anchor="w", padx=20, pady=6)
        self.symptom_mic = tk.Button(
            row, text="🎙 Speak", bg=GREEN, fg=WHITE, font=("Segoe UI", 10, "bold"),
            relief="flat", padx=14, pady=8, cursor="hand2",
            command=lambda: self.start_listening(
                self.symptom_box, self.symptom_status, self.symptom_mic))
        self.symptom_mic.pack(side="left", padx=(0, 8))
        tk.Button(row, text="🗑 Clear", bg=MUTED, fg=WHITE, font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=14, pady=8, cursor="hand2",
                  command=lambda: self.symptom_box.delete("1.0", "end")).pack(side="left", padx=(0, 8))
        self.analyze_btn = tk.Button(
            row, text="⚡ Analyze", command=self.analyze_image, bg=PURPLE, fg=WHITE,
            font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=8, cursor="hand2")
        self.analyze_btn.pack(side="left")

        frame, self.disease_box = make_output(card, height=10)
        frame.pack(fill="both", expand=True, padx=20, pady=(8, 20))
        write_output(self.disease_box, [("Describe the crop and its symptoms to begin.", "note")])

    def analyze_image(self):
        symptoms = self.symptom_box.get("1.0", "end").strip()
        lang = self.lang_key()

        if not symptoms:
            messagebox.showwarning("No symptoms entered",
                                   "Please describe the crop and its symptoms.")
            return

        self.run_answer(symptoms, self.disease_box, self.analyze_btn)

    # ---------- ADVISOR PAGE ----------
    def advisor_page(self):
        card = self.make_card()

        tk.Label(card, text="🎙 Ask your farming question", bg=WHITE, fg=DARK,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=20, pady=(15, 8))

        self.question_box = tk.Text(card, height=4, wrap="word", font=("Segoe UI", 11),
                                    relief="solid", bd=1)
        self.question_box.pack(fill="x", padx=20, pady=4)
        self.question_box.bind("<Control-Return>", lambda e: (self.get_advice(), "break")[1])

        self.voice_status = tk.Label(card, text="Click the microphone and speak. "
                                     "You can edit the text before asking.",
                                     bg=WHITE, fg=MUTED, font=("Segoe UI", 10), anchor="w")
        self.voice_status.pack(fill="x", padx=20, pady=2)

        alt_row = tk.Frame(card, bg=WHITE)
        alt_row.pack(fill="x", padx=20, pady=2)
        tk.Label(alt_row, text="Did you mean:", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 10)).pack(side="left")
        self.alt_combo = ttk.Combobox(alt_row, state="disabled", width=70)
        self.alt_combo.pack(side="left", padx=8)
        self.alt_combo.bind("<<ComboboxSelected>>", self.pick_alternative)

        buttons = tk.Frame(card, bg=WHITE)
        buttons.pack(anchor="w", padx=20, pady=8)

        self.mic_btn = tk.Button(
            buttons, text="🎙 Speak to Text", bg=GREEN, fg=WHITE, font=("Segoe UI", 10, "bold"),
            relief="flat", padx=14, pady=9, cursor="hand2",
            command=lambda: self.start_listening(
                self.question_box, self.voice_status, self.mic_btn,
                alt_combo=self.alt_combo, auto_answer=self.auto_var.get()))
        self.mic_btn.pack(side="left", padx=(0, 8))

        tk.Button(buttons, text="🗑 Clear", command=self.clear_question, bg=MUTED, fg=WHITE,
                  font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=9,
                  cursor="hand2").pack(side="left", padx=(0, 8))

        self.advice_btn = tk.Button(
            buttons, text="Get Farming Guidance", command=self.get_advice, bg=PURPLE, fg=WHITE,
            font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=9, cursor="hand2")
        self.advice_btn.pack(side="left", padx=(0, 12))

        self.auto_var = tk.BooleanVar(value=True)
        tk.Checkbutton(buttons, text="Answer automatically after speaking", variable=self.auto_var,
                       bg=WHITE, activebackground=WHITE, fg=DARK,
                       font=("Segoe UI", 10)).pack(side="left")

        tk.Label(card, text="Farming Guidance", bg=WHITE, fg=GREEN_DARK,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=20, pady=(6, 4))
        frame, self.advice_box = make_output(card, height=10)
        frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        write_output(self.advice_box, [("Your advice will appear here.", "note")])

    def clear_question(self):
        self.question_box.delete("1.0", "end")
        self.voice_status.config(text="Click the microphone and speak. You can edit the text before asking.")
        self.alt_combo.config(values=[], state="disabled")
        self.alt_combo.set("")
        write_output(self.advice_box, [("Your advice will appear here.", "note")])

    def pick_alternative(self, _event=None):
        chosen = self.alt_combo.get()
        if chosen:
            self.question_box.delete("1.0", "end")
            self.question_box.insert("end", chosen)

    def get_advice(self):
        question = self.question_box.get("1.0", "end").strip()
        if not question:
            messagebox.showwarning("Empty question", "Please type or speak your farming question.")
            return
        self.run_answer(question, self.advice_box, self.advice_btn)

    # ---------- ANSWER PIPELINE ----------
    def run_answer(self, question, box, button):
        lang = self.lang_key()
        write_output(box, [(tr("thinking", lang), "note")])
        button.config(state="disabled")

        def work():
            try:
                parts = [(tr("src_kb", lang) + "\n", "src")] + kb_answer(question, lang)
                self.ui(write_output, box, parts)
            finally:
                self.ui(button.config, state="normal")

        threading.Thread(target=work, daemon=True).start()

    # ---------- SPEECH TO TEXT ----------
    def start_listening(self, text_box, status_label, button, alt_combo=None, auto_answer=False):
        if self.listening:
            return
        self.listening = True
        button.config(state="disabled", text="🎙 Listening...")
        threading.Thread(
            target=self.listen_worker,
            args=(text_box, status_label, button, alt_combo, auto_answer),
            daemon=True).start()

    def listen_worker(self, text_box, status_label, button, alt_combo, auto_answer):
        lang = self.lang_key()
        code = "ta-IN" if lang == "ta" else "en-IN"
        say = lambda msg: self.ui(status_label.config, text=msg)
        success = False

        try:
            candidates = self.speech.listen(code, say)
            cleaned = []
            for c in candidates:
                c = clean_transcript(c, lang)
                if c not in cleaned:
                    cleaned.append(c)
            best = cleaned[0]

            def show():
                text_box.delete("1.0", "end")
                text_box.insert("end", best)
                if alt_combo is not None:
                    if len(cleaned) > 1:
                        alt_combo.config(values=cleaned, state="readonly")
                        alt_combo.set(best)
                    else:
                        alt_combo.config(values=[], state="disabled")
                        alt_combo.set("")
                status_label.config(
                    text="✅ Done. Check the text (edit if needed)"
                         + (" - answering..." if auto_answer else "."))
            self.ui(show)
            success = True

        except sr.WaitTimeoutError:
            say("⚠ No speech detected. Move closer to the mic and try again.")
        except sr.UnknownValueError:
            say("⚠ Speech unclear. Speak slowly and clearly, or type your question.")
        except sr.RequestError:
            say("⚠ Recognition service unreachable. Check your internet connection.")
        except (AttributeError, OSError):
            say("⚠ Microphone not available. Install sounddevice and check your mic settings.")
        except Exception as error:
            say(f"⚠ Microphone error: {str(error)[:100]}")
        finally:
            self.listening = False
            self.ui(button.config, state="normal",
                    text="🎙 Speak" if button is getattr(self, "symptom_mic", None)
                    else "🎙 Speak to Text")

        if success and auto_answer:
            self.ui(self.get_advice)


# ---------- RUN PROGRAM ----------
if __name__ == "__main__":
    root = tk.Tk()
    app = AgroSmartAI(root)
    root.mainloop()
