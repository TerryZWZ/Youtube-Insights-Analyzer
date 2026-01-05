# Frontend Setup

- React framework
- manifest.json         Extension ID Card
- package.json          NPM Package List
- webpack.config.js     Bundler
- .babelrc              Compability Compiler

# Frontend Content

- index.html → index.jsx → App.jsx

- 4 useEffect()
    - loading
    - summary
    - error
    - useLocalInference

- 2 useEffect()
    - Load browser storage data
    - Save browser storage data

- handleSummarize() async
    - Clear summary/error and starts loading
    - Get URL with getCurrentTabUrl()
    - API call to backend for summary by sending URL and useLocalInference
    - Decode response into UTF-8 format since response is a chunked HTTP object

- handleRest()
    - Resets summary
    - Stops loading

- getCurrentTabUrl() async
    - Sets promise to identify active tabs and picks current tab

- renderBoldText()
    - Helper function to bold text surrounded by **

- renderSummary()
    - Removes <think><think/> for reasoning models
    - Summary is mapped, each index is identified by splitting \n
    - Each line is evaluated to be formatted if there are headings with #, ##, ###, •/-
    - Each line passes through renderBoldText() to detect if there's text to be bolded

- Display Breakdown
    - Title
    - Toggle Switch
    - Button
    - Summary

# Backend Setup

- FastAPI framework
- uvicorn                   Web Server
- pydantic                  Data Validation
- python-dotenv             Environmental Variables
- tiktoken                  Tokenization
- requests                  API requests
- youtube-transcript-api    API for YouTube transcripts
- groq                      API for Groq
- llama-server              API for llama-server

# Backend Content

- main.py → transcript_extrator.py + inference.py

- CORS middleware to allow usage in all domains

- /summarize POST request
    - main.py
    - Gets URl from client and verify URL
    - Retrieve transcript with get_transcript()
    - Initialize prompt from prompt.txt
    - Calculate token count
    - generate() for summary inference
    - Return StreamingResponse(generate(), media_type="text/plain") chunked object to frontend

- extract_video_id()
    - transcript_extrator.py
    - Extract video ID from full URL

- get_transcript()
    - Extracts video ID with extract_video_id()
    - Attempt to retrieve existing transcript
    - Otherwise attempt to use generated transcript
    - Joins the transcript into one string

- call_llama_server_inference()
    - Uses llama-server API key
    - API call with parameters: message, model
    - Allow text streaming
    - Receive response JSON
    - Return response message content

- call_groq_inference()
    - Uses Groq API key
    - API call with parameters: message, model, max_completion_tokens
    - Receive response JSON
    - Return response message content
