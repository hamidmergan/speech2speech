# speech2speech

A conversation between two people in two languages on one device. One side speaks
into the microphone, a speech to text model writes it down, the chat model
translates it, and the other side reads the translation and can have it read
aloud. Both sides have a name and a language. Conversations are stored, single
sentences can be corrected afterwards.

## Shape

- Two containers: a FastAPI backend with SQLite and a Next.js frontend.
- No Postgres, no Redis, no background queue. Every call answers straight away.
- One OpenAI compatible endpoint per capability: chat, speech to text, speech output.
- Access optionally behind one password from the environment, otherwise open on your own network.

## Decisions

- Storage is SQLite through `sqlite3` from the standard library. Two tables,
  `sessions` and `turns`, in one file under `DATA_DIR`.
- Conversations belong to the installation, not to a user. There are no accounts.
  `ACCESS_PASSWORD` guards the whole API with a signed cookie.
- Translation goes through the chat model. There is no separate translation API.
- Speech output is optional. Without `TTS_MODEL` the page shows no read aloud button.
- Recordings are sent as short windows while somebody speaks, so the transcript
  grows live. A recording over `MAX_AUDIO_BYTES` is refused with a clear message,
  never cut. A conversation over `SESSION_CHAR_LIMIT` ends and stays readable,
  nothing is dropped.
- The browser only grants microphone access on https or on localhost.

## Checklist

- [x] 0 Scaffold: repo, LICENSE, PLAN, README skeleton, backend and frontend shells,
      `docker-compose.yml` with two services, `.env.example`.
- [x] 1 Backend: SQLite repository, service, routes, translation, transcription and
      speech output through `providers.py`, access through `ACCESS_PASSWORD`.
- [x] 2 Backend tests against a fake model server: sessions, correcting sentences,
      limits, password protection.
- [x] 3 Frontend: the conversation page, recording, two sides, history, read aloud.
- [x] 4 `docker compose up`, a conversation held in the browser against real models.
- [ ] 5 README and CHANGELOG.
- [ ] 6 English sweep, final commit.

## Open

- The glossary of the source tool is not carried in 0.1.0. A conversation is
  spoken language, and a per conversation term list wants a place in the UI that
  does not crowd the two cards. If it comes back it comes back as a CSV file per
  conversation.
- Only the pair German and English is offered. Both the language codes and the
  texts inside the two cards are a fixed pair, so a third language is more than
  one more entry in a list.
- A recording past MAX_AUDIO_BYTES is now refused in the browser as well, not only
  by the server. The server answers 413 straight away, but the page's own proxy
  carries the whole upload before that answer reaches the browser, and a 33 MB
  upload therefore sat there as if the page had frozen. The recording never leaves
  the device now, the card says the recording grew too long, and nothing is cut.
- The shell's stylesheet came with the classes of features that are not here. A
  test guards that no class is defined without a user, so those blocks were taken
  out one by one: the citation chips, the source rows, the mind map palette, the
  panel handles, the heatmap, the schedule dot, the streaming cursor and the
  waiting animation. 34 classes in all.
- The frontend shell carries the design tokens and the small components. The login
  flow of the shell is not carried, so `src/lib/api.ts` lost the redirect to a login
  page and its test covers the access password instead. `src/lib/browserStore.ts`
  keeps only the preferences key, the workspace and per person keys went with the
  features that used them.
- The translation prompt is carried unchanged from the source tool, including its
  formal register. It was written for written material, and a spoken conversation
  comes back a little more formal than it went in.
- The batch path of the translation client is not carried. One spoken sentence at
  a time never batches. With it went the numbered list prompt, the parser for that
  list, the per item fallback and the two constants that sized a chunk.
- There are no accounts, so a conversation belongs to the installation. The test
  that proved one person could not see another person's conversation went with the
  owner column it checked.
- The target language reaches the model as a name, "German" or "English", not as
  the code the page sends. The source handed the code straight to the prompt
  because the same interface also served a translation API that wanted codes.
