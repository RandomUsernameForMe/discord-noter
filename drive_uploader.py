from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def upload_file(local_path: str, drive_folder_id: str, service_account_json: str) -> str:
    """Upload a file to Google Drive, return shareable URL."""

    creds = service_account.Credentials.from_service_account_file(
        service_account_json, scopes=SCOPES
    )
    service = build("drive", "v3", credentials=creds)

    file_name = Path(local_path).name
    metadata = {"name": file_name, "parents": [drive_folder_id]}
    media = MediaFileUpload(local_path, mimetype="text/markdown")

    uploaded = service.files().create(body=metadata, media_body=media, fields="id").execute()
    file_id = uploaded["id"]

    # Make it readable by anyone with the link
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return f"https://drive.google.com/file/d/{file_id}/view"
