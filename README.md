# Bulk Prompt → Image Generator

Upload an Excel file full of image-generation prompts → each row gets turned into an
image via the OpenAI Images API → images are saved to a Google Drive folder (plus
a ZIP/log download in the browser). Built for Streamlit Community Cloud.

## How it works

- `app.py` — the Streamlit UI: upload, preview, generate, show results
- `drive_utils.py` — Google Drive upload via a **service account** (no browser login needed,
  which matters because Streamlit Cloud can't pop up a Google OAuth consent screen)
- Secrets (OpenAI key + Drive credentials) are read from `st.secrets`, never hardcoded

## Excel format

| prompt | filename (optional) |
|---|---|
| A watercolor fox in an autumn forest | fox_watercolor |
| A futuristic city skyline at sunset | city_sunset |

Only `prompt` is required. If `filename` is blank, one is auto-generated.
Run the app once and click "Generate sample template" if you want a starter file.

## 1. Get an OpenAI API key

1. Go to https://platform.openai.com/api-keys → create a new key.
2. Make sure the account has billing enabled (image generation isn't on the free tier).

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
- `OPENAI_API_KEY` — your key from step 1
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
4. Deploy. The public URL is shareable; only people with the OpenAI/Drive keys can
   ever see those keys — they're never exposed to end users of the app.

## Notes & gotchas

- **Cost**: every row in your Excel = one paid OpenAI image call. Check pricing at
  https://openai.com/api/pricing before running a 500-row sheet.
- **Rate limits**: the app pauses briefly between calls; if you hit rate limits on a
  large batch, lower batch size or add a longer delay in `app.py`.
- **Model choice**: `gpt-image-1` is OpenAI's newest image model; `dall-e-3` and
  `dall-e-2` remain available. Pick from the sidebar.
- **Public Drive links**: by default, uploaded files are set to "anyone with the
  link can view" so you can share them. Remove that block in `drive_utils.py` if you
  want files to stay private to the service account + people you manually share with.
