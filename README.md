# LLM-Bahnhof 🚂

[ENG] **LLM-Bahnhof** is a lightweight, robust, OpenAI-compatible model router and fallback proxy designed for local and hybrid LLM infrastructures. It acts as a central switching station (*Bahnhof*) for your AI requests, intelligently routing prompts and falling back to alternative endpoints if primary models fail.

[DEU] **LLM-Bahnhof** ist ein schlanker, robuster, OpenAI-kompatibler Modell-Router und Fallback-Proxy für lokale und hybride KI-Infrastrukturen. Er fungiert als zentrale Weiche (*Bahnhof*) für deine LLM-Anfragen, leitet intelligent um und springt automatisch auf alternative Gleise (Modelle/Provider), wenn ein Endpunkt ausfällt.

---

## Features

- **OpenAI-Compatible API:** Drop-in replacement for any OpenAI client (`openai` SDK, `aider`, `Continue`, etc.).
- **Smart Routing & Fallback:** Route requests based on model preferences with automated fallback mechanisms.
- **Local & Hybrid:** Perfect for combining local Ollama nodes with external API providers.
- **Lightweight & Fast:** Built in pure Python with zero heavy bloat, runs smoothly even on low-resource servers or VMs (e.g., 2GB RAM).
- **Clean Architecture:** Modular design without brittle browser-scraping hacks.

---

## Installation

~~~bash
git clone https://github.com/o-valo/llm-bahnhof.git
cd llm-bahnhof
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
~~~

---

## Quickstart

1. Configure your endpoints and fallback rules in the configuration file or via environment variables.
2. Start the proxy server:

~~~bash
./venv/bin/python llm_bahnhof.py --host 127.0.0.1 --port 8788
~~~

3. Connect any OpenAI-compatible tool:

~~~python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8788/v1",
    api_key="not-needed"  # Local proxy
)

response = client.chat.completions.create(
    model="default-route",
    messages=[{"role": "user", "content": "Hallo vom Gleis 1!"}]
)

print(response.choices[0].message.content)
~~~

---

## License

MIT License — see [LICENSE](LICENSE) for details.

#EOF

Powerd by AI :-) 
