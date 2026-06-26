"""
Google Drive helpers using a service-account.
No browser OAuth flow needed — works headlessly on Streamlit Cloud.
"""
import io

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service(service_account_info):
    """service_account_info: dict-like (e.g. st.secrets['gcp_service_account'])"""
    creds = service_account.Credentials.from_service_account_info(
        dict(service_account_info), scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def get_or_create_folder(service, folder_name: str, parent_id: str | None = None) -> str:
    query = (
        f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' "
        "and trashed = false"
    )
    if parent_id:
        query += f" and '{parent_id}' in parents"

    resp = service.files().list(q=query, fields="files(id, name)").execute()
    files = resp.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def upload_image_to_drive(
    service, folder_id: str, filename: str, file_bytes: bytes, mimetype: str = "image/png"
) -> tuple[str, str]:
    """Uploads a file to Drive. Returns (webViewLink, file_id) — file_id is what
    a later pipeline stage (image -> video) can use to fetch this exact file."""
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mimetype, resumable=False)
    metadata = {"name": filename, "parents": [folder_id]}
    file = service.files().create(
        body=metadata, media_body=media, fields="id, webViewLink"
    ).execute()

    # Make the file viewable via link (optional — comment out to keep private)
    service.permissions().create(
        fileId=file["id"], body={"role": "reader", "type": "anyone"}
    ).execute()

    return file.get("webViewLink", ""), file.get("id", "")
