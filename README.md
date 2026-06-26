# Bulk Prompt → Image Generator

Upload an Excel file full of image-generation prompts → each row gets turned into an
image via a free Hugging Face model → download everything as a ZIP, plus a results
log. Built for Streamlit Community Cloud.

## How it works

- `app.py` — the whole app: upload, preview, generate, download
- Calls Hugging Face's free Inference API using `black-forest-labs/FLUX.1-schnell`
  (Apache 2.0 licensed — safe for commercial use, e.g. monetized YouTube content)
- Your Hugging Face token is read from `st.secrets`, never hardcoded

No Google Drive integration — Drive uploads via a service account turned out to be
unreliable on personal (non-Workspace) Google accounts, hitting an intermittent
"Service Accounts do not have storage quota" error that has no consistent fix for
that account type. Downloading a ZIP + log and dragging them into Drive yourself
(if you want them there) is simpler and 100% reliable.

## Excel format

| id (optional) | prompt | filename (optional) |
|---|---|---|
| fox_01 | A watercolor fox in an autumn forest | fox_watercolor |
| city_02 | A futuristic city skyline at sunset | city_sunset |

Only `prompt` is required. If `id`/`filename` are blank, they're auto-generated.
Click "Generate sample template" in the app for a ready-made starter file.

## 1. Get a free Hugging Face token

1. Go to https://huggingface.co/join → create a free account (no card needed)
2. Go to https://huggingface.co/settings/tokens → **Create new token**
3. Name it anything, "Read" access is enough (or "Fine-grained" with
   "Make calls to Inference Providers" checked)
4. Copy the token — starts with `hf_...`

## 2. Configure secrets

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in:
```toml
HF_TOKEN = "hf_your_real_token"
```

**Locally:** this file lives at `.streamlit/secrets.toml` and is already in
`.gitignore`, so it won't be pushed to GitHub.

**On Streamlit Community Cloud:** App → Settings (⚙️) → Secrets → paste the same
content there.

## 3. Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 4. Deploy to Streamlit Community Cloud

1. Push this folder to a GitHub repo (`secrets.toml` will NOT be included — that's
   intentional; only the `.example` template is).
2. Go to https://share.streamlit.io → New app → pick your repo/branch → main file
   `app.py`.
3. App Settings → Secrets → paste your `HF_TOKEN` line.
4. Deploy.

## Notes & gotchas

- **Free tier size**: Hugging Face gives every account a small monthly credit
  (enough for testing and light batches — dozens to ~100 images). Once it runs
  out, usage becomes pay-as-you-go at the underlying provider's rate (typically
  a fraction of a cent per image) — no extra step needed, it just starts billing
  your HF account.
- **Cold starts**: the first call to a model that hasn't been used in a while can
  take 20–60 seconds. The app retries automatically with a short delay.
- **Image size**: pick the "Shorts / vertical 9:16" preset in the sidebar for
  YouTube Shorts; other presets are available too.
- **Output**: after a run, download the ZIP (all images) and the `.xlsx` log
  (one row per image — id, prompt, filename, status). Keep both together; stage 2
  (image → video) will read the log to know which prompt produced which image.
