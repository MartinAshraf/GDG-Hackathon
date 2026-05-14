import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def ask(prompt, system_prompt=None, json_mode=False):
    """
    Single function all agents use to call Groq.
    Drop-in replacement for all Gemini calls.
    """
    messages = [
        {"role": "system", "content": system_prompt or "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]

    kwargs = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.2,
    }

    # JSON mode — guarantees clean JSON output
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content.strip()
