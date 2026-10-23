# speech2speech

A conversation between two people in two languages, on one device. One side
speaks into the microphone, the other side reads the translation and can have it
read aloud. Both sides have a name and a language, and either side can also type.
Every conversation is kept, so you can read one again or carry it on.

speech2speech is a small web app in two containers: a FastAPI backend that keeps
the conversations in a SQLite file, and a Next.js page. There is no queue, no
Postgres and no cache.

It currently speaks:

- German and English, one on each side

## Prerequisites

- Docker, or Python 3.11 and Node 20 to run the two parts by hand
- A server with an OpenAI-compatible API and these models:
  - a **chat model**, required. It does the translating.
  - a **speech to text model** (Whisper style), required for talking. Without it
    the page still translates what you type and says that the microphone has no model.
  - a **text to speech model**, optional. Without it the page shows no read aloud button.
- An API key is optional. Many self-hosted servers do not need one.
- A browser only grants microphone access on **https or on localhost**. On a plain
  http address from another machine the Speak button cannot open the microphone,
  so put the page behind https or open it on the machine it runs on.

If you run your own models, the audio and the text of a conversation stay on your
own network. Nothing leaves your machine or data center.

## Installation

```bash
git clone https://github.com/hamidmergan/speech2speech.git
cd speech2speech
cp .env.example .env
```

Edit `.env` and name your models, then start both containers:

```bash
docker compose up -d
```

Open http://localhost:3100.

To run the two parts without Docker:

```bash
# backend
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
DATA_DIR=./data LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=your-model \
  STT_MODEL=your-speech-to-text-model \
  .venv/bin/python -m uvicorn src.app:app --port 8100

# frontend, in a second terminal
cd frontend
npm install
npm run dev
```

## Usage

Each person has a card of their own, written in their own language. Press Speak
and talk. The transcript grows while you speak, and the translation on the other
card follows along. Press Done, or the other side presses Speak and takes over.

Typing works too: write into your card and press Enter.

A sentence that came out wrong can be corrected in the field afterwards. The
translation is made again, and the conversation marks the sentence as corrected.

The three buttons at the top:

- **Transcript** shows the whole conversation in both languages and downloads it as a text file.
- **Past conversations** lists what was said before. Open one to read it again or carry it on.
- **New conversation** starts a fresh one. The old one is kept.

Behind the gear sit the models this installation has, a switch for the read aloud
button, and the way to sign out when a password is set.

### Protecting the page

Without `ACCESS_PASSWORD` the API is open to anyone who reaches the port. That is
fine on a network only you can reach. Set a password before you publish the page:

```
ACCESS_PASSWORD=a password you choose
SESSION_SECRET=a long random string
```

Everybody then enters the same password once. The cookie is signed, nothing is
stored, and changing the password or the secret signs everybody out.

## Settings

Everything is read from the environment, so `.env` is the one place. Base URL and
API key fall back to the `LLM_*` values, the model never does.

| Variable | Purpose | Default |
| --- | --- | --- |
| `LLM_BASE_URL` | chat endpoint, with or without `/v1` | none, required |
| `LLM_MODEL` | chat model, it translates | none, required |
| `LLM_API_KEY` | key for the chat endpoint (then `OPENAI_API_KEY`) | optional |
| `STT_MODEL` | speech to text model | none, microphone off without it |
| `STT_BASE_URL` / `STT_API_KEY` | its own endpoint | falls back to `LLM_*` |
| `TTS_MODEL` | text to speech model | none, read aloud off without it |
| `TTS_VOICE` | voice the endpoint knows | `alloy` |
| `TTS_BASE_URL` / `TTS_API_KEY` | its own endpoint | falls back to `LLM_*` |
| `ACCESS_PASSWORD` | one password for the whole page | none, page is open |
| `SESSION_SECRET` | signs the access cookie | derived from the password |
| `DATA_DIR` | folder of the SQLite file | `/data` in Docker |
| `MAX_SESSIONS` | conversations kept at once | 100 |
| `SESSION_CHAR_LIMIT` | characters one conversation may collect | 20000 |
| `MAX_AUDIO_BYTES` | largest recording one request may carry | 31457280 (30 MB) |
| `TTS_MAX_CHARS_PER_REQUEST` | characters per request to the speech model | 400 |
| `FRONTEND_PORT` / `BACKEND_PORT` | published ports | 3100 / 8100 |
| `CORS_ORIGINS` | browser origins the API accepts | `http://localhost:3100` |

If a limit is reached, it is said out loud. A recording over `MAX_AUDIO_BYTES` is
refused with a message naming what happened, and the page stops the recording
instead of sending half of it. A conversation that reaches `SESSION_CHAR_LIMIT`
ends and stays readable, and the sentence that did not fit is simply not taken.
Nothing is silently truncated and nothing is silently dropped.

## Limitations

Quality depends on the chosen models. A small chat model translates spoken
language more stiffly than it sounds, and a speech model mishears names and
places. Check important results, and correct a sentence in the field when it came
out wrong.

Only German and English are offered. Both sides of the page are written in their
own language, so a third language is more than one more entry in a list.

A conversation belongs to the installation, not to a person. Everybody who can
open the page sees every conversation.

The page keeps the newest `MAX_SESSIONS` conversations. When a new one starts, the
one untouched longest is deleted with its sentences.

## Running Tests

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
```

The tests run against a local fake server and need no real model.

```bash
cd frontend
npm install
npm test
npm run lint
npx tsc --noEmit
npm run build
```

## License

MIT
