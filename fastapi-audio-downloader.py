from fastapi import FastAPI, Query, __version__
from fastapi.responses import HTMLResponse
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

SERVICE_ACCOUNT_FILE = 'YOUR_JSON_FILE'
SCOPES = ['https://www.googleapis.com/auth/drive']

html = f"""
<!DOCTYPE html>
<html>
    <head>
        <title>FastAPI on Vercel</title>
        <link rel="icon" href="/static/favicon.ico" type="image/x-icon" />
    </head>
    <body>
        <div class="bg-gray-200 p-4 rounded-lg shadow-lg">
            <h1>Hello from FastAPI@{__version__}</h1>
            <ul>
                <li><a href="/docs">/docs</a></li>
                <li><a href="/redoc">/redoc</a></li>
            </ul>
            <p>Powered by <a href="https://vercel.com" target="_blank">Vercel</a></p>
        </div>
    </body>
</html>
"""

@app.get("/")
async def root():
    return HTMLResponse(html)


def build_drive_service():
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=credentials)


executor = ThreadPoolExecutor(max_workers=5)


async def get_audio_urls_for_query(query: str, limit: int = 5):
    def _sync_search():
        videos_search = VideosSearch(query, limit=limit)
        videos_search.next()
        return [result['link'] for result in videos_search.result()['result']]

    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(None, _sync_search)
    return results


def download_audio_in_memory(audio_url: str):
    try:
        yt = YouTube(audio_url)
        # Filter the audio streams, preferably by the audio format (e.g., mp4) and select the highest quality
        audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').first()
        if audio_stream:
            # Download the audio stream in memory
            buffer = BytesIO()
            audio_stream.stream_to_buffer(buffer)
            buffer.seek(0)  # Move to the start of the buffer

            # Simple file size check - ensure the file is larger than a minimal size (e.g., 1KB)
            if buffer.getbuffer().nbytes > 1024:
                return buffer
            else:
                print("Downloaded content is too small to be a valid audio file.")
                return None
        else:
            print("No audio stream found for this video.")
            return None
    except Exception as e:
        print(f"Error downloading audio content: {e}")
        return None
        
        download_audio_in_memory.max_duration = 300


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
