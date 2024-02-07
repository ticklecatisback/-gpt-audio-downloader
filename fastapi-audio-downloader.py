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

def download_audio_with_pytube(url, save_path):
    try:
        yt = YouTube(url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        if audio_stream:
            audio_stream.download(output_path=save_path)
            return True
        else:
            print("No audio stream found")
            return False
    except Exception as e:
        print(f"Error downloading audio: {e}")
        return False


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

@app.post("/download-audios/")
async def download_audios(query: str = Query(..., description="The search query for downloading audios"), 
                          limit: int = Query(1, description="The number of audios to download")):
    audio_urls = await get_audio_urls_for_query(query, limit=limit)
    service = build_drive_service()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_filename = os.path.join(temp_dir, "audios.zip")
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for i, audio_url in enumerate(audio_urls):  # Ensure audio_url is defined here
                file_content = download_audio_in_memory(audio_url)  # audio_url should be defined
                if not file_content:
                    continue
                
                audio_name = f"audio_{i}.mp3"
                audio_path = os.path.join(temp_dir, audio_name)
                with open(audio_path, 'wb') as audio_file:
                    audio_file.write(file_content.getbuffer())
                
                zipf.write(audio_path, arcname=audio_name)

        # Upload the zip file to Google Drive
        file_metadata = {'name': 'audios.zip'}
        media = MediaFileUpload(zip_filename, mimetype='application/zip')
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        permission = {'type': 'anyone', 'role': 'reader'}
        service.permissions().create(fileId=file.get('id'), body=permission).execute()
        drive_url = f"https://drive.google.com/uc?id={file.get('id')}"
        
        return {"message": "Zip file with audios uploaded successfully.", "url": drive_url}
