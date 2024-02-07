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
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=credentials)

def download_audio_from_youtube(url, save_path):
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

async def upload_to_drive(service, file_path):
    file_metadata = {'name': os.path.basename(file_path)}
    media = MediaFileUpload(file_path, mimetype='audio/mp3')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    permission = {'type': 'anyone', 'role': 'reader'}
    service.permissions().create(fileId=file.get('id'), body=permission).execute()
    return f"https://drive.google.com/uc?id={file.get('id')}"

@app.post("/download-and-upload-audio/")
async def download_and_upload_audio(youtube_url: str = Query(..., description="The YouTube URL to download audio from")):
    service = build_drive_service()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        audio_file_path = download_audio_from_youtube(youtube_url, temp_dir)
        
        if not audio_file_path:
            return {"message": "Failed to download audio."}

        drive_url = await upload_to_drive(service, audio_file_path)
        
        return {"message": "Audio uploaded successfully.", "url": drive_url}
