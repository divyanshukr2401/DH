from __future__ import annotations

import base64
import html
import io
import os
import re
import textwrap
import xml.sax.saxutils
from typing import Any

import httpx
import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

st.set_page_config(
    page_title="Digital Humanities Studio",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

HF_ROUTER = "https://router.huggingface.co/hf-inference/models"
HF_CLASSIFIER_MODEL = os.getenv(
    "HF_CLASSIFIER_MODEL", "Ateeqq/ai-vs-human-image-detector"
)
HF_IMAGE_MODEL = os.getenv("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
PAGE_BREAK = "[[PAGE BREAK]]"

STYLE_TEMPLATES = {
    "Madhubani Folk Art (Mithila)": (
        "Madhubani folk art from Mithila, intricate hand-drawn double outlines, "
        "dense decorative patterns, flat natural-pigment colors, fish and lotus "
        "motifs, finely patterned borders, handmade paper texture"
    ),
    "Mughal Miniature Painting": (
        "Mughal miniature painting, finely detailed courtly composition, precise "
        "delicate brushwork, jewel-toned pigments, floral borders, gold leaf accents, "
        "burnished handmade paper"
    ),
    "Raja Ravi Varma Realism": (
        "19th-century Indian academic realism in the spirit of Raja Ravi Varma, "
        "luminous oil-painting technique, graceful composition, rich textiles, "
        "naturalistic light and expressive figures"
    ),
    "Vincent van Gogh Post-Impressionism": (
        "Post-Impressionist oil painting inspired by Vincent van Gogh, energetic "
        "directional impasto brushstrokes, vivid complementary colors, expressive "
        "swirling sky, tactile canvas"
    ),
    "Japanese Ukiyo-e Woodblock": (
        "Japanese ukiyo-e woodblock print, bold elegant contour lines, flat areas "
        "of color, asymmetrical composition, subtle washi paper grain, stylized "
        "clouds and waves"
    ),
}

OCR_SYSTEM_PROMPT = """You are a careful historical-document transcription assistant.
Transcribe only words that are visible in the supplied page image. Preserve the
original spelling, punctuation, paragraph structure, and meaningful line breaks.
Join words split at line endings when the hyphen is only typographic; retain
genuine hyphens. Do not modernize, translate, summarize, or silently repair text.
Never guess missing or illegible words: mark uncertain spans as [illegible] and
partial words as [unclear: visible letters]. Return only the transcription."""

def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def make_sample_artwork() -> bytes:
    image = Image.new("RGB", (1100, 760), "#e8d7b3")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1100, 760), fill="#e8d7b3")
    draw.rectangle((0, 0, 1100, 390), fill="#d7a278")
    draw.ellipse((775, 86, 940, 251), fill="#f3d37d")
    draw.polygon(
        [(0, 390), (190, 310), (365, 390), (570, 287), (795, 394), (970, 305),
         (1100, 370), (1100, 760), (0, 760)],
        fill="#72836b",
    )
    draw.rectangle((0, 486, 1100, 760), fill="#547d83")
    for y in range(510, 750, 35):
        draw.arc((80, y, 1010, y + 34), 190, 350, fill="#c6c092", width=3)
    # A small temple silhouette anchors the sample as a cultural heritage scene.
    draw.rectangle((423, 331, 677, 498), fill="#a4513b")
    draw.polygon([(400, 334), (550, 227), (700, 334)], fill="#7e3e32")
    draw.rectangle((516, 399, 584, 498), fill="#593b35")
    draw.rectangle((448, 356, 486, 399), fill="#e0b56d")
    draw.rectangle((615, 356, 652, 399), fill="#e0b56d")
    draw.line((550, 226, 550, 178), fill="#714434", width=8)
    draw.ellipse((532, 164, 568, 194), fill="#bd7745")
    for x in range(38, 1070, 48):
        draw.ellipse((x, 24, x + 7, 31), fill="#825941")
        draw.ellipse((x + 15, 715, x + 22, 722), fill="#825941")
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def make_sample_scan() -> bytes:
    width, height = 1000, 1360
    image = Image.new("RGB", (width, height), "#e5d6b8")
    draw = ImageDraw.Draw(image)
    draw.rectangle((68, 64, width - 68, height - 64), fill="#f4ead2")
    draw.rectangle((86, 82, width - 86, height - 82), outline="#9b7955", width=2)
    title_font = _font(32)
    body_font = _font(23)
    draw.text((width // 2, 135), "A RECORD OF THE EASTERN SHRINE",
              fill="#49382a", font=title_font, anchor="mm")
    draw.text((width // 2, 190), "Copied in the year of the river's rising",
              fill="#6c5740", font=_font(19), anchor="mm")
    draw.line((185, 225, width - 185, 225), fill="#9b7955", width=2)
    scan_lines = [
        "At the first light of day the river lay",
        "quiet beneath the old stone steps. The",
        "keepers opened the eastern gate, and",
        "the pilgrims entered in small companies.",
        "",
        "The inscription above the doorway records",
        "the names of those who restored the shrine",
        "after the great flood. Some letters are",
        "worn away; the remaining lines are copied",
        "here as they appear upon the stone.",
        "",
        "On the seventh day, offerings of flowers",
        "and rice were placed beside the water.",
        "The village elders spoke the names of",
        "their ancestors before the evening bell.",
    ]
    y = 282
    for index, line in enumerate(scan_lines):
        if line:
            x = 170 if index % 7 in (2, 3) else 150
            draw.text((x, y), line, fill="#4a3a2d", font=body_font)
        y += 52
    draw.text((width // 2, height - 152), "—  1  —", fill="#6c5740",
              font=_font(20), anchor="mm")
    # Faint edge marks evoke an archival scan without obscuring the text.
    draw.line((111, 240, 114, height - 260), fill="#d4c3a3", width=3)
    draw.line((width - 112, 260, width - 116, height - 230),
              fill="#d4c3a3", width=2)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _image_details(data: bytes) -> tuple[str, str]:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("This image is larger than 15 MB. Please choose a smaller file.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            image_format = (image.format or "").upper()
            if image_format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Please upload a JPG, PNG, or WebP image.")
            mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[
                image_format
            ]
            return image_format, mime
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("The uploaded file could not be read as an image.") from exc


def _api_key(name: str, label: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{label} is not set. Add it to the project's .env file and restart the app."
        )
    return value


def _hf_request(model: str, token: str, data: bytes, content_type: str) -> requests.Response:
    return requests.post(
        f"{HF_ROUTER}/{model}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
        },
        data=data,
        timeout=120,
    )


def _response_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text[:500]
    if isinstance(payload, dict):
        detail = payload.get("error") or payload.get("message") or str(payload)
    else:
        detail = str(payload)
    return f"Cloud service returned HTTP {response.status_code}: {detail}"


def classify_artwork(image_bytes: bytes, mime: str) -> dict[str, float]:
    token = _api_key("HF_TOKEN", "HF_TOKEN")
    response = _hf_request(HF_CLASSIFIER_MODEL, token, image_bytes, mime)
    if not response.ok:
        raise RuntimeError(_response_error(response))
    payload: Any = response.json()
    if isinstance(payload, dict):
        payload = payload.get("labels", payload.get("outputs", payload))
    if isinstance(payload, list) and payload and isinstance(payload[0], list):
        payload = payload[0]
    if not isinstance(payload, list):
        raise RuntimeError("The classifier returned an unexpected response format.")

    scores = {"human": 0.0, "ai": 0.0}
    for item in payload:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).lower()
        try:
            score = float(item.get("score", 0))
        except (TypeError, ValueError):
            continue
        if any(word in label for word in ("human", "real", "authentic", "natural")):
            scores["human"] += score
        elif any(word in label for word in ("artificial", "generated", "synthetic", "fake", "ai")):
            scores["ai"] += score
    total = scores["human"] + scores["ai"]
    if total <= 0:
        labels = ", ".join(
            str(item.get("label", "unknown"))
            for item in payload
            if isinstance(item, dict)
        )
        raise RuntimeError(
            "The classifier's labels could not be mapped to human/AI categories"
            + (f" ({labels})." if labels else ".")
        )
    return {key: value / total for key, value in scores.items()}


def generate_artwork(prompt: str) -> bytes:
    token = _api_key("HF_TOKEN", "HF_TOKEN")
    try:
        from huggingface_hub import InferenceClient
        from huggingface_hub.errors import HfHubHTTPError
    except ImportError as exc:
        raise RuntimeError(
            "The Hugging Face client is missing. Run `python -m pip install -r requirements.txt`."
        ) from exc
    try:
        image = InferenceClient(provider="auto", api_key=token).text_to_image(
            prompt,
            model=HF_IMAGE_MODEL,
        )
    except HfHubHTTPError as exc:
        raise RuntimeError(f"Hugging Face image generation failed: {exc}") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Hugging Face image generation request failed: {exc}") from exc
    try:
        out = io.BytesIO()
        image.convert("RGB").save(out, format="PNG")
        return out.getvalue()
    except (OSError, Image.DecompressionBombError, AttributeError) as exc:
        raise RuntimeError(
            "The image service returned data that could not be read as an image."
        ) from exc


def transcribe_scan(image_bytes: bytes, mime: str) -> str:
    api_key = _api_key("GEMINI_API_KEY", "GEMINI_API_KEY")
    try:
        from google import genai
        from google.genai import errors
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "The Gemini SDK is missing. Run `python -m pip install -r requirements.txt`."
        ) from exc
    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime),
                "Transcribe this scanned page according to the transcription rules.",
            ],
            config=types.GenerateContentConfig(system_instruction=OCR_SYSTEM_PROMPT),
        )
    except (errors.APIError, httpx.HTTPError, TimeoutError) as exc:
        raise RuntimeError(f"Gemini request failed: {exc}") from exc
    transcription = response.text
    if not transcription or not transcription.strip():
        raise RuntimeError("Gemini returned an empty transcription.")
    return transcription.strip()


def _pan_zoom_viewer(image_bytes: bytes, alt: str) -> None:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    source = f"data:image/png;base64,{encoded}"
    safe_alt = html.escape(alt, quote=True)
    markup = f"""<!doctype html>
<html><head><style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #f3f5ef; font: 13px sans-serif; color: #151711; }}
.tools {{ min-height: 42px; display:flex; align-items:center; flex-wrap:wrap; gap:8px; padding:4px 8px; }}
button {{ border:1px solid #d5dccf; background:#ffffff; color:#151711; padding:5px 10px; border-radius:7px; cursor:pointer; transition:background-color 140ms cubic-bezier(.23,1,.32,1), border-color 140ms cubic-bezier(.23,1,.32,1), transform 140ms cubic-bezier(.23,1,.32,1); }}
.stage {{ height:calc(100vh - 60px); max-height:540px; min-height:320px; overflow:hidden; position:relative; cursor:grab; touch-action:none;
          background-color:#f3f5ef; background-image:radial-gradient(#dfe5d8 0.7px, transparent 0.7px);
          background-size:12px 12px; }}
.stage.dragging {{ cursor:grabbing; }}
img {{ position:absolute; top:50%; left:50%; max-width:none; width:auto; height:auto;
       max-height:none; transform-origin:center; user-select:none; -webkit-user-drag:none; }}
@media (hover: hover) and (pointer: fine) {{
  button:hover {{ background:#f2f9e3; border-color:#a6dd31; }}
}}
button:active {{ transform:scale(.97); }}
button:focus-visible {{ outline:2px solid #151711; outline-offset:2px; }}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ transition-duration:.01ms !important; }}
}}
@media (max-width: 640px) {{
  .tools {{ padding:6px; gap:6px; }}
  .tools span {{ flex:1 1 100%; }}
  .stage {{ height:calc(100vh - 82px); max-height:500px; min-height:300px; }}
}}
</style></head>
<body>
<div class="tools"><button id="minus">−</button><button id="plus">+</button>
<button id="reset">Reset</button><span>Scroll to zoom · drag to pan</span></div>
<div class="stage" id="stage"><img id="scan" alt="{safe_alt}" src="{source}"></div>
<script>
const stage=document.getElementById('stage'), img=document.getElementById('scan');
let scale=0.46, x=0, y=0, drag=null;
function render() {{ img.style.transform=`translate(calc(-50% + ${{x}}px),calc(-50% + ${{y}}px)) scale(${{scale}})`; }}
function fit() {{
  if (!img.naturalWidth || !img.naturalHeight) return;
  scale=Math.max(0.2,Math.min(0.46,(stage.clientWidth-24)/img.naturalWidth,(stage.clientHeight-24)/img.naturalHeight));
  x=0; y=0; render();
}}
img.onload=fit;
window.addEventListener('resize',fit);
function zoom(factor) {{ scale=Math.min(3,Math.max(0.25,scale*factor)); render(); }}
document.getElementById('plus').onclick=()=>zoom(1.2);
document.getElementById('minus').onclick=()=>zoom(1/1.2);
document.getElementById('reset').onclick=()=>{{scale=0.46;x=0;y=0;render();}};
stage.addEventListener('wheel',e=>{{e.preventDefault();zoom(e.deltaY<0?1.12:1/1.12);}},{{passive:false}});
stage.addEventListener('pointerdown',e=>{{drag=[e.clientX-x,e.clientY-y];stage.setPointerCapture(e.pointerId);stage.classList.add('dragging');}});
stage.addEventListener('pointermove',e=>{{if(drag){{x=e.clientX-drag[0];y=e.clientY-drag[1];render();}}}});
stage.addEventListener('pointerup',()=>{{drag=null;stage.classList.remove('dragging');}});
stage.addEventListener('pointercancel',()=>{{drag=null;stage.classList.remove('dragging');}});
fit();
</script></body></html>"""
    st.iframe(markup, height=600, alt="Interactive scanned-page viewer")


def _to_tei(text: str, status: str) -> str:
    pieces = re.split(r"(?im)^\s*" + re.escape(PAGE_BREAK) + r"\s*$", text)
    body: list[str] = []
    for page_number, piece in enumerate(pieces, start=1):
        if page_number > 1:
            body.append(f'<pb n="{page_number}"/>')
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", piece) if part.strip()]
        for paragraph in paragraphs:
            safe_text = xml.sax.saxutils.escape(paragraph)
            safe_text = safe_text.replace("\n", "<lb/>")
            body.append(f"<p>{safe_text}</p>")
    safe_status = xml.sax.saxutils.escape(status)
    return textwrap.dedent(
        f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <TEI xmlns="http://www.tei-c.org/ns/1.0">
          <teiHeader>
            <fileDesc>
              <titleStmt><title>Transcribed manuscript page</title></titleStmt>
              <publicationStmt><p>Created with Digital Humanities Studio</p></publicationStmt>
              <sourceDesc><p>Source: scanned page supplied by the user or sample asset.</p></sourceDesc>
            </fileDesc>
            <revisionDesc><change>Proofread status: {safe_status}</change></revisionDesc>
          </teiHeader>
          <text><body>{''.join(body)}</body></text>
        </TEI>
        """
    )


def _set_sample(which: str) -> None:
    if which == "art":
        st.session_state["art_image_bytes"] = make_sample_artwork()
        st.session_state["art_image_name"] = "sample-heritage-painting.png"
        st.session_state["art_upload_version"] += 1
        st.session_state["art_result"] = None
        st.session_state["art_error"] = ""
    elif which == "scan":
        st.session_state["scan_image_bytes"] = make_sample_scan()
        st.session_state["scan_image_name"] = "sample-manuscript-page.png"
        st.session_state["scan_upload_version"] += 1
        st.session_state["ocr_error"] = ""


def _set_sample_prompt() -> None:
    st.session_state["subject_prompt"] = (
        "An ancient Indian temple complex at sunrise beside a quiet river"
    )


def _format_editor(action: str) -> None:
    value = st.session_state.get("transcription_text", "")
    if action == "heading":
        lines = value.splitlines()
        for index, line in enumerate(lines):
            if line.strip():
                lines[index] = "# " + line.lstrip("# ").strip()
                break
        else:
            lines = ["# Heading"]
        st.session_state["transcription_text"] = "\n".join(lines)
    elif action == "bold" and value.strip():
        st.session_state["transcription_text"] = f"**{value.strip()}**"
    elif action == "italic" and value.strip():
        st.session_state["transcription_text"] = f"*{value.strip()}*"
    elif action == "page_break":
        st.session_state["transcription_text"] = value.rstrip() + f"\n\n{PAGE_BREAK}\n\n"


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
    :root {
      --ink:#151711; --muted:#62695d; --paper:#f5f7f2; --line:#dfe4da;
      --lime:#b8f23f; --lime-hover:#a9e638; --lime-soft:#f2f9e3;
      --card:#ffffff; --ease-out:cubic-bezier(.23,1,.32,1);
    }
    .stApp {
      background:var(--paper);
      color:var(--ink);
      font-family:'DM Sans',system-ui,sans-serif;
    }
    [data-testid="stHeader"] { background:rgba(245,247,242,.94); }
    .block-container { max-width:1280px; padding:2rem 2.25rem 3rem; }
    h1,h2,h3 { font-family:'DM Sans',system-ui,sans-serif !important; color:var(--ink); }
    h1 { font-size:clamp(2.3rem, 4.5vw, 3.35rem) !important; font-weight:700 !important; letter-spacing:-.055em; line-height:1.04 !important; }
    h2 { letter-spacing:-.035em; }
    h3 { font-size:1.35rem !important; font-weight:650 !important; letter-spacing:-.025em; }
    p, label, .stMarkdown { color:var(--ink); }
    .eyebrow { color:#536b2d; text-transform:uppercase; letter-spacing:.17em; font-size:.7rem; font-weight:700; }
    .lede { color:var(--muted); font-size:1rem; max-width:850px; line-height:1.7; }
    .syllabus {
      padding:14px 18px; border:1px solid var(--line); border-left:3px solid var(--lime);
      background:var(--card); border-radius:0 10px 10px 0;
      color:var(--ink); line-height:1.55;
    }
    .panel { padding:18px 20px; border:1px solid var(--line); background:var(--card); border-radius:12px; }
    [data-testid="stVerticalBlockBorderWrapper"] {
      border-color:var(--line) !important; border-radius:14px !important;
      background:var(--card); box-shadow:0 8px 26px rgba(21,23,17,.045);
      transition:border-color 160ms var(--ease-out), box-shadow 160ms var(--ease-out);
    }
    @media (hover:hover) and (pointer:fine) {
      [data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color:#c4cfb9 !important; box-shadow:0 10px 28px rgba(21,23,17,.07);
      }
    }
    .stButton > button, .stDownloadButton > button {
      border-radius:9px; border:1px solid #cbd3c5; min-height:2.75rem;
      background:var(--card); color:var(--ink); font-weight:600;
      transition:transform 140ms var(--ease-out), box-shadow 140ms var(--ease-out), background-color 140ms var(--ease-out), border-color 140ms var(--ease-out);
    }
    @media (hover:hover) and (pointer:fine) {
      .stButton > button:hover:not(:disabled), .stDownloadButton > button:hover:not(:disabled) {
        transform:translateY(-1px); border-color:#9eb17e; box-shadow:0 5px 14px rgba(21,23,17,.09);
      }
    }
    .stButton > button:active:not(:disabled), .stDownloadButton > button:active:not(:disabled) {
      transform:scale(.97);
    }
    .stButton > button:focus-visible, .stDownloadButton > button:focus-visible,
    [data-baseweb="tab"]:focus-visible, [data-testid="stFileUploader"] button:focus-visible {
      outline:2px solid var(--ink) !important; outline-offset:3px;
    }
    .stButton > button[kind="primary"] {
      background:var(--lime); border-color:var(--lime); color:var(--ink); font-weight:700;
    }
    .stButton > button[kind="primary"]:hover:not(:disabled) {
      background:var(--lime-hover); border-color:var(--lime-hover);
    }
    .stButton > button[kind="primary"]:disabled {
      background:#e8ece3; border-color:#e8ece3; color:#7a8174;
    }
    [data-testid="stFileUploader"] { border-radius:10px; }
    [data-testid="stFileUploader"] section {
      border-color:#cbd3c5; border-radius:10px; background:#fbfcf9;
    }
    @media (hover:hover) and (pointer:fine) {
      [data-testid="stFileUploader"] section:hover { border-color:#a8c777; }
    }
    [data-testid="stMetric"] { background:var(--card); padding:14px; border:1px solid var(--line); border-radius:9px; }
    .stTabs [data-baseweb="tab-list"] {
      display:flex; gap:7px; border-bottom:1px solid var(--line); overflow-x:auto;
      scrollbar-width:thin; scrollbar-color:#cbd3c5 transparent;
    }
    .stTabs [data-baseweb="tab"] {
      flex:0 0 auto; white-space:nowrap; background:transparent; padding:12px 15px;
      border-radius:8px 8px 0 0; transition:background-color 140ms var(--ease-out), color 140ms var(--ease-out);
    }
    @media (hover:hover) and (pointer:fine) {
      .stTabs [data-baseweb="tab"]:hover { background:#eef2e8; }
    }
    .stTabs [aria-selected="true"] {
      color:var(--ink); border-bottom-color:var(--lime) !important; background:var(--lime-soft);
    }
    div[role="progressbar"] > div { background:#e8ede2 !important; }
    div[role="progressbar"] > div > div { background:var(--lime) !important; }
    [data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input {
      border-radius:9px; border-color:#cbd3c5; background:var(--card); color:var(--ink);
    }
    [data-testid="stTextArea"] textarea:focus, [data-testid="stTextInput"] input:focus {
      border-color:#8ba94c; box-shadow:0 0 0 1px #8ba94c;
    }
    .small-note { font-size:.86rem; color:var(--muted); line-height:1.6; }
    .st-key-art-layout, .st-key-style-layout, .st-key-wikisource-layout { margin-top:.4rem; }
    .st-key-art-layout [data-testid="stHorizontalBlock"],
    .st-key-style-layout [data-testid="stHorizontalBlock"],
    .st-key-wikisource-layout [data-testid="stHorizontalBlock"] { gap:1.1rem; }
    .st-key-format-toolbar [data-testid="stHorizontalBlock"] { gap:.45rem; }
    .st-key-art-layout [data-testid="stColumn"],
    .st-key-style-layout [data-testid="stColumn"],
    .st-key-wikisource-layout [data-testid="stColumn"] { min-width:0; }
    @media (max-width: 820px) {
      .block-container { padding:1.6rem 1.35rem 2.5rem; }
      .st-key-art-layout [data-testid="stHorizontalBlock"],
      .st-key-style-layout [data-testid="stHorizontalBlock"],
      .st-key-wikisource-layout [data-testid="stHorizontalBlock"] {
        flex-direction:column !important; flex-wrap:nowrap !important; align-items:stretch !important;
      }
      .st-key-art-layout [data-testid="stColumn"],
      .st-key-style-layout [data-testid="stColumn"],
      .st-key-wikisource-layout [data-testid="stColumn"] {
        width:100% !important; min-width:0 !important; flex:1 1 100% !important;
      }
    }
    @media (max-width: 560px) {
      .block-container { padding:1.2rem .9rem 2rem; }
      h1 { font-size:2.2rem !important; }
      .lede { font-size:.96rem; }
      .syllabus { padding:12px 14px; font-size:.92rem; }
      .stTabs [data-baseweb="tab"] { padding:10px 12px; font-size:.88rem; }
      [data-testid="stTextArea"] textarea { height: min(54vh, 380px) !important; }
      .stDownloadButton > button { white-space:normal; line-height:1.25; }
      .st-key-format-toolbar [data-testid="stHorizontalBlock"] {
        flex-direction:row !important; flex-wrap:wrap !important; align-items:stretch !important;
      }
      .st-key-format-toolbar [data-testid="stColumn"] {
        width:calc(50% - .25rem) !important; min-width:0 !important;
        flex:1 1 calc(50% - .25rem) !important;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration:.01ms !important; animation-iteration-count:1 !important;
        scroll-behavior:auto !important; transition-duration:.01ms !important;
      }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

for key, default in {
    "art_image_bytes": None,
    "art_image_name": "",
    "art_upload_version": 0,
    "art_result": None,
    "art_error": "",
    "style_result": None,
    "style_prompt_used": "",
    "style_is_demo": False,
    "style_error": "",
    "scan_image_bytes": None,
    "scan_image_name": "",
    "scan_upload_version": 0,
    "transcription_text": "",
    "ocr_error": "",
    "proofread_status": "Not Proofread",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.markdown('<div class="eyebrow">Culture · Archives · Computation</div>', unsafe_allow_html=True)
st.title("Digital Humanities Studio")
st.markdown(
    '<div class="lede">A small laboratory for exploring how machine learning meets art history, '
    'heritage, and the work of making texts readable.</div>',
    unsafe_allow_html=True,
)
st.write("")

art_tab, style_tab, text_tab = st.tabs(
    ["01 · Art Authentication", "02 · Artistic Style Generator", "03 · AI Wikisource Studio"]
)

with art_tab:
    st.markdown(
        '<div class="syllabus"><b>Culture &amp; AI · Unit 2</b> &nbsp;—&nbsp; Authenticity &amp; Museum Verification</div>',
        unsafe_allow_html=True,
    )
    st.write("")
    with st.container(key="art-layout"):
        left, right = st.columns([0.95, 1.05], gap="large", border=True)
    with left:
        st.subheader("Examine an artwork")
        uploaded_art = st.file_uploader(
            "Drop an image here or browse",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"art_upload_{st.session_state['art_upload_version']}",
            help="JPG, PNG, or WebP · up to 15 MB",
        )
        if uploaded_art is not None:
            candidate = uploaded_art.getvalue()
            if candidate != st.session_state["art_image_bytes"]:
                try:
                    _image_details(candidate)
                    st.session_state["art_image_bytes"] = candidate
                    st.session_state["art_image_name"] = uploaded_art.name
                    st.session_state["art_result"] = None
                    st.session_state["art_error"] = ""
                except ValueError as exc:
                    st.error(str(exc))
        sample_col, analyze_col = st.columns(2)
        with sample_col:
            st.button("Load Sample Artwork", on_click=_set_sample, args=("art",), width="stretch")
        with analyze_col:
            analyze = st.button(
                "Analyze artwork",
                type="primary",
                width="stretch",
                disabled=not bool(st.session_state["art_image_bytes"]),
            )
        art_bytes = st.session_state["art_image_bytes"]
        if art_bytes:
            st.image(art_bytes, caption=st.session_state["art_image_name"], width="stretch")
        else:
            st.info("Load the sample painting or upload an image to begin.")
        if analyze and art_bytes:
            try:
                _, art_mime = _image_details(art_bytes)
                with st.spinner("Asking the image classifier…"):
                    st.session_state["art_result"] = classify_artwork(art_bytes, art_mime)
                st.session_state["art_error"] = ""
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                st.session_state["art_error"] = str(exc)
                st.session_state["art_result"] = None
    with right:
        st.subheader("Classifier reading")
        st.markdown(
            '<div class="panel"><b>What this estimate can tell us</b><br>'
            '<span class="small-note">A classifier compares patterns in the image with its training data. '
            'It cannot establish provenance, authorship, or authenticity on its own.</span></div>',
            unsafe_allow_html=True,
        )
        if st.session_state["art_error"]:
            st.error(st.session_state["art_error"])
        result = st.session_state["art_result"]
        if result:
            human, ai = result["human"], result["ai"]
            verdict = "Likely human-created" if human >= ai else "Likely AI-generated"
            st.markdown(f"### Verdict · {verdict}")
            st.progress(human, text=f"Human-created · {human:.1%}")
            st.progress(ai, text=f"AI-generated · {ai:.1%}")
            st.caption(
                "Visual cues may include texture regularity, repeated patterns, edge detail, "
                "and other learned image statistics. Treat these scores as an educational "
                "signal—not a forensic conclusion."
            )
        else:
            st.markdown("#### Confidence breakdown")
            st.progress(0.0, text="Human-created · waiting for analysis")
            st.progress(0.0, text="AI-generated · waiting for analysis")
            st.caption("Results use the Hugging Face image-classification inference API.")

with style_tab:
    st.markdown(
        '<div class="syllabus"><b>Culture &amp; AI · Unit 2</b> &nbsp;—&nbsp; Emerging Technologies &amp; Visual Culture</div>',
        unsafe_allow_html=True,
    )
    st.write("")
    with st.container(key="style-layout"):
        style_left, style_right = st.columns([0.92, 1.08], gap="large", border=True)
    with style_left:
        st.subheader("Compose a visual prompt")
        style_name = st.selectbox("Art tradition / visual language", list(STYLE_TEMPLATES))
        st.text_area(
            "Describe the subject",
            key="subject_prompt",
            height=110,
            placeholder="For example: an ancient Indian temple complex at sunrise beside a river",
        )
        prompt_col, demo_col = st.columns(2)
        with prompt_col:
            st.button("Use sample prompt", on_click=_set_sample_prompt, width="stretch")
        with demo_col:
            show_demo = st.button("Show local demo", width="stretch")
        full_prompt = (
            f"Create an original image depicting: {st.session_state.get('subject_prompt', '').strip()}. "
            f"Visual direction: {STYLE_TEMPLATES[style_name]}. "
            "Respect cultural context; avoid text, logos, and signatures."
        )
        with st.expander("Engineered prompt", expanded=False):
            st.code(full_prompt, language="text")
        generate = st.button(
            "Generate with Hugging Face",
            type="primary",
            width="stretch",
            disabled=not bool(st.session_state.get("subject_prompt", "").strip()),
        )
        if show_demo:
            st.session_state["style_result"] = make_sample_artwork()
            st.session_state["style_prompt_used"] = full_prompt
            st.session_state["style_is_demo"] = True
            st.session_state["style_error"] = ""
        if generate:
            try:
                with st.spinner("Generating image with a hosted inference model…"):
                    st.session_state["style_result"] = generate_artwork(full_prompt)
                st.session_state["style_prompt_used"] = full_prompt
                st.session_state["style_is_demo"] = False
                st.session_state["style_error"] = ""
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                st.session_state["style_error"] = str(exc)
                st.session_state["style_result"] = None
    with style_right:
        st.subheader("Studio canvas")
        if st.session_state["style_error"]:
            st.error(st.session_state["style_error"])
        generated = st.session_state["style_result"]
        if generated:
            if st.session_state["style_is_demo"]:
                st.info("Local demo preview — this sample is not AI-generated.")
            st.image(generated, width="stretch")
            st.download_button(
                "Download Image",
                data=generated,
                file_name="digital-humanities-artwork.png",
                mime="image/png",
                width="stretch",
            )
            with st.expander("Prompt used"):
                st.write(st.session_state["style_prompt_used"])
        else:
            st.markdown(
                '<div class="panel">Choose a style and describe a subject, then generate an image. '
                'Use the local demo preview to explore the canvas without an API key.</div>',
                unsafe_allow_html=True,
            )

with text_tab:
    st.markdown(
        '<div class="syllabus"><b>Creating &amp; Editing Machine-Readable Text · Unit 1, Lab 4</b>'
        ' &nbsp;·&nbsp; <b>Digitisation of Manuscripts · Unit 5</b></div>',
        unsafe_allow_html=True,
    )
    st.write("")
    with st.container(key="wikisource-layout"):
        scan_col, editor_col = st.columns([1, 1.05], gap="large", border=True)
    with scan_col:
        st.subheader("Scanned page")
        uploaded_scan = st.file_uploader(
            "Upload a book page, document, or manuscript",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"scan_upload_{st.session_state['scan_upload_version']}",
            help="JPG, PNG, or WebP · up to 15 MB",
        )
        if uploaded_scan is not None:
            candidate = uploaded_scan.getvalue()
            if candidate != st.session_state["scan_image_bytes"]:
                try:
                    _image_details(candidate)
                    st.session_state["scan_image_bytes"] = candidate
                    st.session_state["scan_image_name"] = uploaded_scan.name
                except ValueError as exc:
                    st.error(str(exc))
        st.button("Load Sample Scan", on_click=_set_sample, args=("scan",))
        scan_bytes = st.session_state["scan_image_bytes"]
        if scan_bytes:
            _pan_zoom_viewer(scan_bytes, st.session_state["scan_image_name"])
        else:
            st.info("Load the sample scan or upload a page. Drag to pan and scroll to zoom.")
    with editor_col:
        st.subheader("Transcription workspace")
        with st.container(key="format-toolbar"):
            toolbar = st.columns(4)
            toolbar[0].button("Heading", on_click=_format_editor, args=("heading",), width="stretch")
            toolbar[1].button("Bold", on_click=_format_editor, args=("bold",), width="stretch")
            toolbar[2].button("Italic", on_click=_format_editor, args=("italic",), width="stretch")
            toolbar[3].button("Page break", on_click=_format_editor, args=("page_break",), width="stretch")
        st.caption("Formatting actions apply to the current text; edit the Markdown-like markers directly.")
        st.selectbox(
            "Proofread status",
            ["Not Proofread", "Proofread", "Validated"],
            key="proofread_status",
        )
        extract = st.button(
            "Extract Text with AI",
            type="primary",
            width="stretch",
            disabled=not bool(scan_bytes),
        )
        if extract and scan_bytes:
            try:
                _, scan_mime = _image_details(scan_bytes)
                with st.spinner("Gemini is reading the page…"):
                    st.session_state["transcription_text"] = transcribe_scan(scan_bytes, scan_mime)
                st.session_state["ocr_error"] = ""
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                st.session_state["ocr_error"] = str(exc)
        st.text_area(
            "Editable transcription",
            key="transcription_text",
            height=390,
            placeholder="Extract text with AI or begin transcribing here…",
            label_visibility="collapsed",
        )
        if st.session_state["ocr_error"]:
            st.error(st.session_state["ocr_error"])
        text_value = st.session_state.get("transcription_text", "")
        if text_value.strip():
            md_text = text_value
            tei_text = _to_tei(text_value, st.session_state["proofread_status"])
            download_cols = st.columns(3)
            download_cols[0].download_button(
                "Plain Text (.txt)",
                data=text_value,
                file_name="transcription.txt",
                mime="text/plain",
                width="stretch",
            )
            download_cols[1].download_button(
                "Markdown (.md)",
                data=md_text,
                file_name="transcription.md",
                mime="text/markdown",
                width="stretch",
            )
            download_cols[2].download_button(
                "TEI-XML (.xml)",
                data=tei_text,
                file_name="transcription.xml",
                mime="application/xml",
                width="stretch",
            )

st.divider()
st.caption(
    "Cloud processing is opt-in per action. Uploaded images and API credentials are not saved by this app."
)
