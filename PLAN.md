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
- [x] 5 README and CHANGELOG.
- [x] 6 English sweep, final commit.
- [x] 7 Review round: the findings of the review worked through, each with a test
      that fails without the change.

## The English sweep

Everything in the repo is English: identifiers, comments, logs, test names and
test data. Three places stay German on purpose, because German users read them:
the `"de"` entries of `backend/src/i18n.py`, the German half of
`frontend/src/app/[locale]/_cardTexts.ts`, and the German fallback sentences in
`frontend/src/lib/api.ts`. Two more are German on purpose because they are the
input of a translation test: the German sentences in `test_interpreter_route.py`
and `test_speak.py`, and the two words in `_limits.test.ts` whose length is
asserted.

The sweep was done file by file, never by a search and replace over the tree.
Every rename in `tts_number_words.py` was checked against the source by diffing
every string literal and every number in the file: only the one log message
changed. The same check on `globals.css` showed all 203 colour values and numbers
unchanged. No string that is matched against input or shown to a person was
touched.

## Deliberate deviations from the source

- The translation prompt is rewritten. The source prompt was written for written
  lecture material: it asked for a formal register, which turned every casual
  spoken sentence into a stiff one, and it carried a rule about a
  `__GLOSSARY_<number>__` token that cannot appear here, because the glossary is
  not carried. It also still described the content as academic and university
  material. The new prompt names a spoken conversation, asks the model to keep
  the register of the speaker and has no glossary rule.
- Timestamps are stored as UTC with an offset. The source stored a naive
  timestamp in a Postgres `TIMESTAMP` column. The browser reads an offsetless
  date-time as its own local time, and the container has no time zone of its
  own, so a conversation finished ten minutes ago appeared hours in the past.
- The upsert of a sentence is scoped to its conversation. The source scoped
  everything by `owner_id`, which is gone with the accounts, so without this
  every conversation on the installation would share one id space.
- `TTS_VOICE` has no default. The source read the voice from a settings table
  with a provider that knew its own voices. Here a guessed name means a read
  aloud button that answers 502 on every press.
- The ceiling of a single sentence is 4000 characters on every route. The source
  allowed 2000 for a translation and 4000 for a stored turn, so a long spoken
  sentence could be stored and then never translated.
- The access cookie carries `secure` wherever the browser used https. The source
  sat behind a reverse proxy that set the flag.

## Known properties

Faithful to the source and kept on purpose, so a later reader does not take them
for an oversight.

- Only the sentence currently on a card can be corrected. The server takes a
  correction of any sentence, but once the other side speaks, your sentence
  moves into the history list, which has no edit field. The README says so now.
- `synchronous = NORMAL` in WAL mode survives a crash of the process but does
  not flush on every commit, so a power cut can cost the newest transactions.
  The comment in `database.py` says this rather than promising durability.
- Writers serialize. SQLite takes one writer at a time, which is the right shape
  for two people on one device, and readers never wait.
- The sentence end search in the speech splitter takes the first punctuation
  kind it finds, not the position nearest the middle.
- The eviction query sorts by `updated_at DESC, id DESC`. The extra tiebreaker
  is harmless and makes the order stable when two conversations share a stamp.
- A part of a long text goes to the speech endpoint trimmed, so the one space at
  a sentence end is not inside any request. The parts are joined as audio, where
  that space has no sound.

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
- The batch path of the translation client is not carried. One spoken sentence at
  a time never batches. With it went the numbered list prompt, the parser for that
  list, the per item fallback and the two constants that sized a chunk.
- There are no accounts, so a conversation belongs to the installation. The test
  that proved one person could not see another person's conversation went with the
  owner column it checked.
- The target language reaches the model as a name, "German" or "English", not as
  the code the page sends. The source handed the code straight to the prompt
  because the same interface also served a translation API that wanted codes.
