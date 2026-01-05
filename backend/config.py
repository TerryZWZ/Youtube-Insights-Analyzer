import os
from dotenv import load_dotenv

"""
Create a .env file to store these values
"""
load_dotenv()

# Llama server configuration
LLAMA_SERVER_URL = os.getenv("LLAMA_SERVER_URL")
LLAMA_SERVER_MODEL = os.getenv("LLAMA_SERVER_MODEL")
LLAMA_API_KEY = os.getenv("LLAMA_API_KEY")

# Groq configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL")
