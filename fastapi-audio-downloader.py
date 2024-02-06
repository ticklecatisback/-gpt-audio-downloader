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

def test_download_audio_directly(file_id: str):
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '')
        print(f"Content-Type: {content_type}, Content-Length: {len(response.content)}")
        
        if 'audio' not in content_type:
            print("Downloaded content is not an audio file.")
            return None
        
        return BytesIO(response.content)
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
            for i, audio_url in enumerate(audio_urls):
                file_content = test_download_audio_directly(audio_url)  # Ensure this matches your function name
                if file_content and file_content.getbuffer().nbytes > 0:
                    audio_name = f"audio_{i}.mp3"
                    audio_path = os.path.join(temp_dir, audio_name)
                    # Save the downloaded audio content to a file
                    with open(audio_path, 'wb') as audio_file:
                        audio_file.write(file_content.getbuffer())
                    
                    # Optionally, process the audio file here using PyDub or another library
                    
                    # Add the audio file to the ZIP archive
                    zipf.write(audio_path, arcname=audio_name)
                else:
                    print(f"Skipping URL {audio_url}, no content downloaded or the content is not an audio file.")
        
        # After all audio files are added to the ZIP, proceed to upload it to Google Drive
        if os.path.getsize(zip_filename) > 0:
            drive_url = await upload_to_drive(service, zip_filename)
            return {"message": "Zip file with audios uploaded successfully.", "url": drive_url}
        else:
            print("Zip file is empty. No audio files were added.")
            return {"message": "No audios were downloaded. Zip file is empty."}
