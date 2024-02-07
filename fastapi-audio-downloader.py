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
from pytube import YouTube


app = FastAPI()

SERVICE_ACCOUNT_FILE = 'triple-water-379900-cd410b5aff31.json'
SCOPES = ['https://www.googleapis.com/auth/drive']

def build_drive_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=credentials)

def download_audio_with_pytube(video_url: str) -> BytesIO:
    try:
        yt = YouTube(video_url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        
        if audio_stream:
            buffer = BytesIO()
            audio_stream.stream_to_buffer(buffer=buffer)
            buffer.seek(0)  # Rewind the buffer to the beginning
            return buffer
        else:
            print(f"No audio stream found for {video_url}")
            return None
    except pytube.exceptions.RegexMatchError:
        print(f"Invalid YouTube URL: {video_url}")
        return None
    except Exception as e:
        print(f"Error downloading audio from {video_url}: {e}")
        return None

@app.post("/download-audios/")
async def download_audios(query: str = Query(..., description="The search query for downloading audios")):
    service = build_drive_service()
    video_url = query  # Assuming the query is the YouTube video URL for simplicity

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_filename = os.path.join(temp_dir, "audios.zip")
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            file_content = download_audio_with_pytube(video_url)
            if file_content:
                audio_name = "audio.mp3"  # Simplified to a single file for this example
                audio_path = os.path.join(temp_dir, audio_name)
                with open(audio_path, 'wb') as audio_file:
                    audio_file.write(file_content.read())
                
                zipf.write(audio_path, arcname=audio_name)
            else:
                return {"message": "Failed to download any audio."}

        # Upload the zip file to Google Drive
        file_metadata = {'name': 'audios.zip'}
        media = MediaFileUpload(zip_filename, mimetype='application/zip')
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        permission = {'type': 'anyone', 'role': 'reader'}
        service.permissions().create(fileId=file.get('id'), body=permission).execute()
        drive_url = f"https://drive.google.com/uc?id={file.get('id')}"
        
        return {"message": "Zip file with audios uploaded successfully.", "url": drive_url}
