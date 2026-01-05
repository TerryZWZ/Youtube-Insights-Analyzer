from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl
from transcript_extractor import get_transcript
from inference import call_groq_inference, call_llama_server_inference
import tiktoken
import uvicorn
import logging
import os

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Enable CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all domains; change to specific domains if needed
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (including OPTIONS)
    allow_headers=["*"],  # Allows all headers
)


# Preparing request parameters
class SummarizationRequest(BaseModel):
    video_url: HttpUrl
    use_local: bool


# POST request to create summary
@app.post("/summarize")
async def summarize_video(request: SummarizationRequest):

    # Logging request
    logger.info(f"Received summarization request: {request}")
    logger.info(f"Received video URL: {request.video_url}")
    logger.info(f"Received provider: {request.use_local}")

    # Retrieve transcript
    try:
        transcript = get_transcript(request.video_url)
        logger.info(f"Transcript obtained successfully: {transcript[:50]}...")
    except Exception as e:
        logger.error(f"Transcript error: {e}")
        raise HTTPException(status_code=400, detail=f"Transcript error: {str(e)}")

    # Set up prompt
    try:
        current_directory = os.path.dirname(os.path.abspath(__file__))
        prompt_file_path = os.path.join(current_directory, "prompt.txt")

        with open(prompt_file_path, "r", encoding="utf-8") as file:
            prompt_template = file.read()

        content = prompt_template.format(transcript=transcript)
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(content)
        logger.info(f"Approximate token count: {int(len(tokens) * 1.15)}.")

        prompt = [{"role": "user", "content": content}]
    except Exception as e:
        logger.error(f"Prompt setup error: {e}")
        raise HTTPException(status_code=500, detail=f"Prompt setup error: {str(e)}")

    # Define a generator to stream for llama-server or whole for Groq
    def generate():
        if request.use_local:
            logger.info("llama-server called.")
            for chunk in call_llama_server_inference(prompt):
                yield chunk
        else:
            logger.info(f"Groq called.")
            summary = call_groq_inference(prompt)
            logger.info(f"Groq summary generated.")
            yield summary

    # Return a streaming response
    return StreamingResponse(generate(), media_type="text/plain")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
