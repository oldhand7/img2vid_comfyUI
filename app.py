from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
import io
import uvicorn
from PIL import Image
import json
from urllib import request, parse
import os
import asyncio
import time
from starlette.background import BackgroundTasks
import uuid
import datetime
from fastapi.staticfiles import StaticFiles

app = FastAPI()
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/files", StaticFiles(directory='/home/administrator/ComfyUI/output/'), name="files")

class GifRequest(BaseModel):
  
  selfie_base64: str


def decode_base64_to_image(base64_str: str) -> Image.Image:
    """ Decode a base64 string to PIL Image. """
    image_data = base64.b64decode(base64_str)
    return Image.open(io.BytesIO(image_data))


def queue_prompt(prompt):
    p = {"prompt": prompt}
    data = json.dumps(p).encode('utf-8')
    req =  request.Request("http://127.0.0.1:7860/prompt", data=data)
    print("req --------> ", req)
    result = request.urlopen(req)

    
    
async def check_done(request_id, timeout=360):
    result_path = os.path.join("/home/administrator/ComfyUI/output", f"{request_id}_00001.gif")
    start_time = time.time()
    while True:
        # Check for file existence with efficient os.path.exists
        if await asyncio.to_thread(os.path.exists, result_path):
            return True

        # # Check if timeout has been reached
        # if time.time() - start_time > timeout:
        #     return False

        # Non-blocking delay to avoid busy waiting
        await asyncio.sleep(0.1)
    
    
async def process_image(selfie_img_path, request_id):
    f = open("workflow_api.json") 
    workflow = json.load(f)
    print(selfie_img_path, request_id)
    # change input image path
    workflow["116"]["inputs"]["image"] = selfie_img_path
    # chaneg save path
    workflow["106"]["inputs"]["filename_prefix"] = request_id
    
    queue_prompt(workflow)
    
    file_exists = await check_done(request_id)
    
    if not file_exists:
        # File not found within timeout, raise an HTTPException
        raise HTTPException(status_code=408, detail="Request timed out. File not found.")
    print("file exist")
    return os.path.join("/home/administrator/ComfyUI/output", f"{request_id}_00001.gif")
        
        
def remove_file(result_gif_path: str) -> None:
    os.remove(result_gif_path)
    
    
@app.post("/generate_gif")
async def generate_gif(gif_request: GifRequest, background_tasks: BackgroundTasks):
  # try:
  # Decode the selfie image
  selfie_img = decode_base64_to_image(gif_request.selfie_base64)

  current_time = datetime.datetime.now()
  date_string = current_time.strftime("%Y-%m-%d")
  filename = date_string + str(uuid.uuid4())

#   selfie_img = selfie_img.convert("RGB")
  selfie_img_path = f"/home/administrator/comfyui_api/tmp/{filename}.png"
  selfie_img.save(selfie_img_path)

  # Process the image and generate GIF
  result_gif_path = await process_image(selfie_img_path, filename)
  print("result -> ", result_gif_path)
#   background_tasks.add_task(remove_file, result_gif_path)
  background_tasks.add_task(remove_file, selfie_img_path)
  
  return "http://69.197.164.130:8000/files/" + filename + "_00001.gif"

  # except Exception as e:
  #   return {"error": str(e)}


if __name__ == "__main__":
  uvicorn.run("app:app", host="0.0.0.0", port=8000)