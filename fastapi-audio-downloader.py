from fastapi import FastAPI, Query
import requests
from io import BytesIO
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from pydub import AudioSegment
import requests
import tempfile
import zipfile
import os
from youtubesearchpython import VideosSearch
import asyncio
from concurrent.futures import ThreadPoolExecutor
import subprocess

app = FastAPI()

SERVICE_ACCOUNT_FILE = 'triple-water-379900-cd410b5aff31.json'
SCOPES = ['https://www.googleapis.com/auth/drive']

def build_drive_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=credentials)

async def get_audio_urls_for_query(query: str, limit: int = 5):
    def _sync_search():
        videos_search = VideosSearch(query, limit=limit)
        videos_search.next()
        return [result['link'] for result in videos_search.result()['result']]

    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(None, _sync_search)
    return results

def download_file_from_google_drive(file_id):
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = requests.get(url)
    if response.status_code == 200:
        # Process the file, e.g., save it locally
        with open("downloaded_file.mp3", "wb") as file:
            file.write(response.content)
        print("File downloaded successfully.")
    else:
        print("Failed to download file.")

file_id = "1Yd1glel8P7gRbPOoEzCy5ZZ6bJtNtmrF"  # Use your actual file ID
download_file_from_google_drive(file_id)

# Test a known good audio URL
audio_url = "https://drive.google.com/uc?export=download&id=1Yd1glel8P7gRbPOoEzCy5ZZ6bJtNtmrF"
audio_content = test_download_audio_directly(audio_url)
if audio_content:
    # Write to the /tmp directory which is writable in AWS Lambda
    temp_audio_path = "/tmp/test_audio.mp3"
    with open(temp_audio_path, "wb") as f:
        f.write(audio_content.getbuffer())
    print(f"Audio file saved as {temp_audio_path}. Try to play it with a media player.")


async def upload_to_drive(service, file_path):
    file_metadata = {'name': os.path.basename(file_path)}
    media = MediaFileUpload(file_path, mimetype='application/zip')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return f"https://drive.google.com/uc?id={file.get('id')}"

@app.get("/download-audio/")
async def download_audio(file_id: str):
    destination_path = "/tmp/downloaded_audio.mp3"  # Ensure this path is writable in your environment
    success = download_file_from_google_drive(file_id, destination_path)
    if success:
        return {"message": "File downloaded successfully.", "path": destination_path}
    else:
        raise HTTPException(status_code=404, detail="Failed to download file.")
