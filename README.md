# Bulk Prompt → Image Generator

Upload an Excel file full of image-generation prompts → each row gets turned into an
image via Google's Gemini image model (free, up to 500 images/day) → images are saved
to a Google Drive folder (plus a ZIP/log download in the browser). Built for Streamlit
Community Cloud.

## How it works

- `app.py` — the Streamlit UI: upload, preview, generate, show results
- `drive_utils.py` — Google Drive upload via a **service account** (no browser login needed,
  which matters because Streamlit Cloud can't pop up a Google OAuth consent screen)
- Secrets (Gemini key + Drive credentials) are read from `st.secrets`, never hardcoded

## Excel format

| prompt | filename (optional) |
|---|---|
| A watercolor fox in an autumn forest | fox_watercolor |
| A futuristic city skyline at sunset | city_sunset |

Only `prompt` is required. If `filename` is blank, one is auto-generated.
Run the app once and click "Generate sample template" if you want a starter file.

## 1. Get a Gemini API key (free)

1. Go to https://aistudio.google.com/apikey
2. Sign in with the same Google account as your Cloud project.
3. Click **Create API key** → choose your existing project (e.g. the one you used for
   the Drive service account) → copy the key (starts with `AIza...`).
4. No credit card needed. The free tier covers up to 500 image generations/day.

## 2. Set up Google Drive access (service account)

Streamlit Cloud apps run headlessly — there's no browser for you to click "Allow" in a
Google sign-in popup. The fix is a **service account**: a robot Google identity that
your app authenticates as directly, using a key file instead of a login.

1. Go to https://console.cloud.google.com/ → create a project (or pick an existing one).
2. Enable the **Google Drive API**: APIs & Services → Library → search "Google Drive API" → Enable.
3. Create a service account: APIs & Services → Credentials → Create Credentials →
   Service account. Give it any name (e.g. `image-uploader`).
4. Open the new service account → Keys tab → Add Key → Create new key → JSON.
   This downloads a `.json` file — **keep it private, never commit it to GitHub.**
5. **Important:** the service account has its own Drive, separate from yours. Either:
   - Open the JSON file, copy the `client_email` value, and **share a Drive folder
     with that email address** (so uploads land somewhere you can see them), or
   - Don't pre-share anything — the app will create its own folder under the
     service account's Drive, and you can find it via the `webViewLink` printed in
     the results table after generation.
   The first option (share a folder with the service account email) is recommended
   so the images show up in your normal Drive.

## 3. Configure secrets

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in:
- `GEMINI_API_KEY` — your key from step 1
- `[gcp_service_account]` — open the downloaded JSON file and copy each field into
  the matching key under that section (this is the exact format Streamlit expects)

**Locally:** this file lives at `.streamlit/secrets.toml` and is already in `.gitignore`,
so it won't be pushed to GitHub.

**On Streamlit Community Cloud:** secrets aren't read from any file in your repo.
Instead: your app → Settings (⚙️) → Secrets → paste the same TOML content there.

## 4. Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 5. Deploy to Streamlit Community Cloud

1. Push this folder to a GitHub repo (secrets.toml will NOT be included — that's intentional).
2. Go to https://share.streamlit.io → New app → pick your repo/branch → main file `app.py`.
3. Before or after first deploy, go to App Settings → Secrets and paste your TOML
   (same content as your local `secrets.toml`).
4. Deploy. The public URL is shareable; only people with the Gemini/Drive keys can
   ever see those keys — they're never exposed to end users of the app.

## Notes & gotchas

- **Free tier limit**: Gemini's free tier allows up to 500 image generations per day
  and roughly 10 requests/minute. A row-by-row batch over ~10 prompts may need brief
  pauses — the app already adds a small delay between calls.
- **Aspect ratio**: pick `9:16` in the sidebar for vertical formats like YouTube Shorts;
  `1:1`, `16:9`, and others are also available.
- **Model**: uses `gemini-2.5-flash-image` (the current non-preview Gemini image model).
- **Public Drive links**: by default, uploaded files are set to "anyone with the
  link can view" so you can share them. Remove that block in `drive_utils.py` if you
  want files to stay private to the service account + people you manually share with.
