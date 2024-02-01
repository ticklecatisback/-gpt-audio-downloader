from fastapi import FastAPI, HTTPException, Query, __version__
from fastapi.responses import HTMLResponse
from bing_image_downloader import downloader
from typing import Optional

app = FastAPI()

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
</ht>ml
"""

@app.get("/")
async def root():
    return HTMLResponse(html)

@app.post("/download-images/")
async def download_images(query: str = Query(..., description="The search query for downloading images"),
                          limit: Optional[int] = Query(10, description="The number of images to download")):
    """
    Downloads images based on the search query and limit provided by the user.

    - **query**: The search term to use for downloading images.
    - **limit**: The maximum number of images to download. Default is 10.
    """
    try:
        # Specify the output directory where images will be saved
        output_dir = 'downloaded_images'
        # Download images using the bing-image-downloader
        downloader.download(query, limit=limit, output_dir=output_dir, adult_filter_off=True, force_replace=False, timeout=60)
        return {"message": f"Successfully downloaded {limit} images for query '{query}' in the '{output_dir}/{query}' directory."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))