import json
import os
import requests
import config
from groq import Groq


def call_llama_server_inference(prompt: list) -> str:
    """
    Call the local inference service (llama-server) to get a summary.
    """
    llama_url = os.environ.get("LLAMA_SERVER_URL", config.LLAMA_SERVER_URL)
    llama_model = os.environ.get("LLAMA_SERVER_MODEL", config.LLAMA_SERVER_MODEL)
    llama_api_key = os.environ.get("LLAMA_API_KEY", config.LLAMA_API_KEY)

    try:
        if not llama_url:
            raise ValueError("LLAMA_SERVER_URL is not configured.")
        
        if not llama_model:
            raise ValueError("LLAMA_SERVER_MODEL is not configured.")

        endpoint = f"{llama_url.rstrip('/')}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        
        if llama_api_key:
            headers["Authorization"] = f"Bearer {llama_api_key}"

        payload = {"model": llama_model, "messages": prompt, "stream": True}

        with requests.post(
            endpoint, headers=headers, json=payload, stream=True, timeout=60
        ) as response:
            response.raise_for_status()

            if not response.encoding or response.encoding.lower() == "iso-8859-1":
                response.encoding = "utf-8"
                
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data:"):
                    line = line[len("data:") :].strip()
                if line == "[DONE]":
                    break

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                choice = data.get("choices", [{}])[0]
                delta = choice.get("delta") or choice.get("message") or {}
                content = delta.get("content")
                
                if content:
                    yield content
    except requests.RequestException as e:
        raise Exception(f"Llama server request failed: {e}")
    except Exception as e:
        raise Exception(f"Llama server inference failed: {e}")


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
