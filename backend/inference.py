import os
import requests
import config
from ollama import Client
from groq import Groq


def call_ollama_inference(prompt: list) -> str:
    """
    Call the local inference service (Ollama) to get a summary.
    """
    ollama_url = os.environ.get("OLLAMA_URL", config.OLLAMA_URL)

    try:
        client = Client(host=ollama_url)
        response = client.chat(model=config.OLLAMA_MODEL, messages=prompt, stream=True)

        for chunk in response:
            yield chunk["message"]["content"]
    except requests.RequestException as e:
        raise Exception(f"Ollama request failed: {e}")
    except Exception as e:
        raise Exception(f"Ollama inference failed: {e}")


def call_groq_inference(prompt: list) -> str:
    """
    Call the third-party inference service (Groq) to get a summary.
    """
    groq_api_key = os.environ.get("GROQ_API_KEY", config.GROQ_API_KEY)
    client = Groq(api_key=groq_api_key)

    try:
        response = client.chat.completions.create(
            messages=prompt, model=config.GROQ_MODEL, max_completion_tokens=8192
        )

        summary = response.choices[0].message.content

        if not summary:
            raise ValueError("No summary returned from Groq.")
        return summary
    except Exception as e:
        raise Exception(f"Groq inference failed: {e}")
