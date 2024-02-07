from fastapi import FastAPI, Query
import requests
from io import BytesIO
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import tempfile
import zipfile
import os
from youtubesearchpython import VideosSearch
import asyncio
from concurrent.futures import ThreadPoolExecutor
import pytube

app = FastAPI()

SERVICE_ACCOUNT_FILE = 'triple-water-379900-cd410b5aff31.json'
SCOPES = ['https://www.googleapis.com/auth/drive']

def build_drive_service():
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=credentials)

executor = ThreadPoolExecutor(max_workers=5)

def get_audio_urls_for_query(url, save_path):
    try:
        yt = YouTube(url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        if audio_stream:
            audio_file_path = audio_stream.download(output_path=save_path)
            return audio_file_path  # Return the path of the downloaded file
        else:
            print("No audio stream found")
            return None
    except Exception as e:
        print(f"Error downloading audio: {e}")
        return None

def download_audio_in_memory(audio_url: str):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(audio_url, headers=headers)
        response.raise_for_status()
        content = BytesIO(response.content)
        
        # Simple file size check - ensure the file is larger than a minimal size (e.g., 1KB)
        if content.getbuffer().nbytes > 1024:
            return content
        else:
            print("Downloaded content is too small to be a valid audio file.")
            return None
    except requests.RequestException as e:
        print(f"Error downloading audio content: {e}")
        return None

async def upload_to_drive(service, file_path):
    file_metadata = {'name': os.path.basename(file_path)}
    media = MediaFileUpload(file_path, mimetype='application/zip')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return f"https://drive.google.com/uc?id={file.get('id')}"

@app.post("/download-audio/")
async def download_audio(youtube_url: str = Query(..., description="The YouTube URL to download audio from")):
    service = build_drive_service()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        audio_file_path = download_audio_from_youtube(youtube_url, temp_dir)
        
        if not audio_file_path:
            return {"message": "Failed to download audio."}

        # Upload the audio file to Google Drive
        drive_url = await upload_to_drive(service, audio_file_path)
        
        return {"message": "Audio uploaded successfully.", "url": drive_url}
