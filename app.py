import io
import time
import zipfile
from datetime import datetime

import pandas as pd
import streamlit as st
from google import genai
from google.genai import types

from drive_utils import get_drive_service, get_or_create_folder, upload_image_to_drive

st.set_page_config(page_title="Bulk Prompt → Image Generator", page_icon="🎨", layout="wide")

st.title("🎨 Bulk Prompt → Image Generator")
st.caption("Upload an Excel file of prompts → generate images via Google Gemini → save to Google Drive")

# ---------------------------------------------------------------------------
# Sidebar: settings & status
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Settings")

    aspect_ratio = st.selectbox(
        "Aspect ratio", ["1:1", "16:9", "9:16", "4:3", "3:2", "4:5", "21:9"], index=0,
        help="9:16 is the vertical format used by YouTube Shorts.",
    )

    st.divider()
    drive_folder_name = st.text_input("Google Drive folder name", value="Generated Images")
    project_id = st.text_input(
        "Batch/project ID",
        value=datetime.now().strftime("batch_%Y%m%d_%H%M%S"),
        help="Prefixes every image ID in this run. Change it to group images by project "
             "(e.g. 'shorts_ep1'). Step 2 of your pipeline will reference these IDs.",
    )

    st.divider()
    st.markdown(
        "**Required secrets** (set in `.streamlit/secrets.toml` locally, "
        "or in Streamlit Cloud → App settings → Secrets):\n"
        "- `GEMINI_API_KEY`\n"
        "- `[gcp_service_account]` block (Drive service account JSON)\n"
    )

# ---------------------------------------------------------------------------
# Validate secrets up front
# ---------------------------------------------------------------------------
missing = []
if "GEMINI_API_KEY" not in st.secrets:
    missing.append("GEMINI_API_KEY")
if "gcp_service_account" not in st.secrets:
    missing.append("gcp_service_account")

if missing:
    st.error(
        f"Missing required secret(s): {', '.join(missing)}. "
        "See the README for how to set these up."
    )
    st.stop()

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

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


def generate_image_bytes(prompt: str) -> bytes:
    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        ),
    )

    candidates = getattr(response, "candidates", None)
    if not candidates:
        raise RuntimeError("Gemini returned no candidates (prompt may have been blocked).")

    for part in candidates[0].content.parts:
        inline_data = getattr(part, "inline_data", None)
        if inline_data is not None and inline_data.data:
            return inline_data.data

    raise RuntimeError("Gemini response had no image data — prompt may need rewording.")


if st.button("🚀 Generate all images", type="primary"):
    drive_service = get_drive_service(st.secrets["gcp_service_account"])
    folder_id = get_or_create_folder(drive_service, drive_folder_name)

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
            drive_link, drive_file_id = upload_image_to_drive(drive_service, folder_id, fname, img_bytes)
            results.append({
                "id": img_id, "prompt": prompt, "filename": fname,
                "status": "✅ Success", "drive_link": drive_link, "drive_file_id": drive_file_id,
            })
        except Exception as e:
            results.append({
                "id": img_id, "prompt": prompt, "filename": fname,
                "status": f"❌ {e}", "drive_link": "", "drive_file_id": "",
            })

        progress.progress((i + 1) / total)
        time.sleep(0.2)  # gentle pacing to avoid rate limit bursts

    zf.close()
    status.write("Done.")

    results_df = pd.DataFrame(results)
    st.subheader("Results")
    st.dataframe(results_df, use_container_width=True)

    n_ok = (results_df["status"] == "✅ Success").sum()
    st.success(f"{n_ok}/{total} images generated and uploaded to Drive folder '{drive_folder_name}'.")

    st.download_button(
        "⬇️ Download all as ZIP (local backup)",
        data=zip_buffer.getvalue(),
        file_name=f"{project_id}_images.zip",
        mime="application/zip",
    )

    log_buf = io.BytesIO()
    results_df.to_excel(log_buf, index=False)
    log_bytes = log_buf.getvalue()

    st.download_button(
        "⬇️ Download results log (.xlsx)",
        data=log_bytes,
        file_name=f"{project_id}_log.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # Save the log to Drive too — this is the handoff file the next pipeline
    # stage (image -> video) will read to map each id to its image.
    try:
        log_link, _ = upload_image_to_drive(
            drive_service, folder_id, f"{project_id}_log.xlsx", log_bytes,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.info(f"Handoff log also saved to Drive: {log_link}")
    except Exception as e:
        st.warning(f"Could not save log to Drive (you still have the download button above): {e}")
