# Digital Humanities Studio

A lightweight Streamlit studio for an academic presentation: artwork
classification, heritage-inspired image generation, and manuscript
transcription/export. AI inference runs through hosted APIs; no local GPU or
model downloads are used. The sample painting and manuscript scan are drawn
locally at runtime, so the demo works without downloading image assets.

## Requirements

- Python 3.10 or newer
- Internet access for hosted inference and (optionally) Google Fonts
- A Hugging Face access token for image classification and image generation
- A Google Gemini API key for manuscript transcription

## Windows setup (PowerShell)

Run these commands from the project directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and replace the example values:

```dotenv
HF_TOKEN=your_huggingface_read_token
GEMINI_API_KEY=your_google_gemini_api_key
```

Generate the keys:

1. **Hugging Face:** create an account at [huggingface.co](https://huggingface.co/),
   then create a **Read** access token in Settings → Access Tokens. It is used
   for the image-classification and hosted image-generation inference APIs.
2. **Gemini:** create an API key in [Google AI Studio](https://aistudio.google.com/apikey).
   It is used only when you choose **Extract Text with AI**.

Then launch:

```powershell
streamlit run app.py
```

If PowerShell prevents environment activation, run the venv executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Presentation walkthrough

- **Art Authentication:** choose **Load Sample Artwork**, then **Analyze artwork**.
- **Artistic Style Generator:** choose **Use sample prompt** and optionally
  **Show local demo**. To generate through Hugging Face, choose **Generate with
  Hugging Face**; generation requires a valid `HF_TOKEN` and an available model.
- **AI Wikisource Studio:** choose **Load Sample Scan** to explore the
  zoomable/pannable viewer and edit the sample transcription. **Extract Text
  with AI** requires `GEMINI_API_KEY`. Export the current text as TXT,
  Markdown, or TEI-XML.

The local demo preview is explicitly labeled and is not presented as an
AI-generated result. Cloud inference buttons report provider/network errors
instead of substituting fabricated results.

## Configuration and privacy

Keys are read from `.env`, which is ignored by Git. Never commit that file.
Optional model overrides are documented in `.env.example`. The app does not
persist uploaded images or send them anywhere until the corresponding cloud
action is selected. Once selected, images and prompts are sent to Hugging Face
or Google Gemini for inference.
