import io
import time
import zipfile
from datetime import datetime

import pandas as pd
import streamlit as st
from huggingface_hub import InferenceClient

# Pinned explicitly — Apache 2.0 licensed (commercial use OK, important since this
# feeds monetized YouTube content), strong prompt adherence. FLUX.1-schnell (the
# previous choice here) is speed-optimized and trades prompt accuracy for speed —
# swap this string if you want to try yet another free HF model later.
HF_IMAGE_MODEL = "Qwen/Qwen-Image"

st.set_page_config(page_title="Bulk Prompt → Image Generator", page_icon="🎨", layout="wide")

st.title("🎨 Bulk Prompt → Image Generator")
st.caption("Upload an Excel file of prompts → generate images via Hugging Face → download as ZIP")

# ---------------------------------------------------------------------------
# Sidebar: settings & status
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Settings")

    size_presets = {
        "Square (1024x1024)": (1024, 1024),
        "Shorts / vertical 9:16 (768x1344)": (768, 1344),
        "Widescreen 16:9 (1344x768)": (1344, 768),
        "Portrait 4:5 (896x1120)": (896, 1120),
    }
    size_label = st.selectbox("Image size", list(size_presets.keys()), index=1)
    img_width, img_height = size_presets[size_label]

    st.divider()
    project_id = st.text_input(
        "Batch/project ID",
        value=datetime.now().strftime("batch_%Y%m%d_%H%M%S"),
        help="Prefixes every image ID in this run. Change it to group images by project "
             "(e.g. 'shorts_ep1'). Step 2 of your pipeline will reference these IDs.",
    )

    st.divider()
    st.markdown(
        "**Required secret** (set in `.streamlit/secrets.toml` locally, "
        "or in Streamlit Cloud → App settings → Secrets):\n"
        "- `HF_TOKEN`\n"
    )

# ---------------------------------------------------------------------------
# Validate secrets up front
# ---------------------------------------------------------------------------
if "HF_TOKEN" not in st.secrets:
    st.error(
        "Missing required secret: HF_TOKEN. See the README for how to set this up."
    )
    st.stop()

client = InferenceClient(api_key=st.secrets["HF_TOKEN"])

# ---------------------------------------------------------------------------
# Upload Excel
# ---------------------------------------------------------------------------
uploaded_file = st.file_uploader("Upload Excel file with prompts", type=["xlsx", "xls"])

st.caption(
    "Expected columns: **prompt** (required), **id** (optional — unique ID for this image; "
    "auto-generated if blank), **filename** (optional — defaults to the id)."
)

if uploaded_file is None:
    st.info("Upload a file to get started. Need a template? Use the button below.")
    if st.button("Generate sample template"):
        sample = pd.DataFrame({
            "id": ["fox_01", "city_02"],
            "prompt": [
                "A watercolor painting of a fox in an autumn forest",
                "A futuristic city skyline at sunset, digital art",
            ],
            "filename": ["fox_watercolor", "city_sunset"],
        })
        buf = io.BytesIO()
        sample.to_excel(buf, index=False)
        st.download_button(
            "Download template.xlsx",
            data=buf.getvalue(),
            file_name="prompt_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    st.stop()

try:
    df = pd.read_excel(uploaded_file)
except Exception as e:
    st.error(f"Could not read the Excel file: {e}")
    st.stop()

df.columns = [str(c).strip().lower() for c in df.columns]

if "prompt" not in df.columns:
    st.error("Your file must have a column named 'prompt'.")
    st.stop()

df = df[df["prompt"].notna() & (df["prompt"].astype(str).str.strip() != "")].reset_index(drop=True)

if "filename" not in df.columns:
    df["filename"] = ""
if "id" not in df.columns:
    df["id"] = ""

def make_id(raw_id: str, idx: int) -> str:
    raw_id = str(raw_id).strip()
    if raw_id and raw_id.lower() != "nan":
        keep = "-_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        cleaned = "".join(c for c in raw_id if c in keep)
        if cleaned:
            return cleaned
    return f"{project_id}_{idx+1:04d}"

df["id"] = [make_id(v, i) for i, v in enumerate(df["id"])]

# guarantee uniqueness even if the sheet had duplicate/blank ids
seen = {}
for i, _id in enumerate(df["id"]):
    if _id in seen:
        seen[_id] += 1
        df.loc[i, "id"] = f"{_id}_{seen[_id]}"
    else:
        seen[_id] = 0

st.success(f"Loaded {len(df)} prompt(s).")
st.dataframe(df[["id", "prompt", "filename"]], use_container_width=True)

# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------
def safe_filename(name: str, fallback_id: str) -> str:
    name = str(name).strip()
    if not name or name.lower() == "nan":
        name = fallback_id
    keep = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    cleaned = "".join(c for c in name if c in keep).strip().replace(" ", "_")
    return cleaned or fallback_id


def generate_image_bytes(prompt: str, max_retries: int = 2) -> bytes:
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            image = client.text_to_image(
                prompt,
                model=HF_IMAGE_MODEL,
                width=img_width,
                height=img_height,
            )
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(15)  # model may be cold-starting on HF's free tier
    raise last_error


if st.button("🚀 Generate all images", type="primary"):
    progress = st.progress(0.0)
    status = st.empty()
    results = []
    zip_buffer = io.BytesIO()
    zf = zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED)

    total = len(df)
    for i, row in df.iterrows():
        img_id = row["id"]
        prompt = str(row["prompt"]).strip()
        fname = safe_filename(row.get("filename", ""), img_id) + ".png"
        status.write(f"Generating {i+1}/{total}: `{img_id}` → `{fname}`")

        try:
            img_bytes = generate_image_bytes(prompt)
            zf.writestr(fname, img_bytes)
            results.append({
                "id": img_id, "prompt": prompt, "filename": fname, "status": "✅ Success",
            })
        except Exception as e:
            results.append({
                "id": img_id, "prompt": prompt, "filename": fname,
                "status": f"❌ [{HF_IMAGE_MODEL}] {e}",
            })

        progress.progress((i + 1) / total)
        time.sleep(0.2)  # gentle pacing to avoid rate limit bursts

    zf.close()
    status.write("Done.")

    results_df = pd.DataFrame(results)
    st.subheader("Results")
    st.dataframe(results_df, use_container_width=True)

    n_ok = (results_df["status"] == "✅ Success").sum()
    st.success(f"{n_ok}/{total} images generated.")

    st.download_button(
        "⬇️ Download all images as ZIP",
        data=zip_buffer.getvalue(),
        file_name=f"{project_id}_images.zip",
        mime="application/zip",
    )

    log_buf = io.BytesIO()
    results_df.to_excel(log_buf, index=False)
    log_bytes = log_buf.getvalue()

    st.download_button(
        "⬇️ Download results log (.xlsx) — this is the handoff file for stage 2",
        data=log_bytes,
        file_name=f"{project_id}_log.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.caption(
        "Tip: keep both the ZIP and this log file together somewhere safe (e.g. drag "
        "them into a Google Drive folder yourself, or a local project folder) — "
        "stage 2 (image → video) will read the log to match each image to its prompt."
    )
