# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-23

### Added

- A conversation between two people in two languages on one device. Each side has
  a card in its own language, with a name, a microphone and a field to type in.
- Speech to text through an OpenAI compatible endpoint. The recording is sent in
  short windows, so the transcript grows while somebody is still speaking.
- Translation through the chat model, live while a sentence grows and once more as
  a whole when a side hands the floor over.
- Speech output, optional. A button next to every translation reads it aloud.
- A conversation is kept in SQLite and can be read again or carried on. Single
  sentences can be corrected afterwards, and a corrected sentence is marked.
- The transcript of a conversation, shown in both languages and downloadable as text.
- One password for the whole page through `ACCESS_PASSWORD`, with a signed cookie.
  Without it the page is open on your own network.
- Two containers and a `docker-compose.yml`, so `docker compose up` works.
- Settable ceilings: conversations kept, characters per conversation, bytes per
  recording and characters per request to the speech model. Each of them says so
  when it is reached rather than cutting anything away.
- German and English interface, and the two cards are always written in their own
  language rather than in the language of the interface.

### Fixed

- An error between a write and its commit left the cached connection in an open
  transaction, which held the write lock of the whole database file until that
  thread wrote again, and committed the orphaned statement on the back of an
  unrelated request. The connection is rolled back now, and one that cannot be
  rolled back is thrown away.
- Every value the API takes from outside has a ceiling. `at` was an unbounded
  integer, and one request past the eight byte range answered 500 and left the
  database locked. Ten further fields had no ceiling either.
- A turn id from another conversation overwrote that conversation's sentence and
  was handed back as this one. The write is scoped to its conversation and a
  foreign id answers 409.
- The translation on the receiving card is announced by a screen reader. It sat
  in a read only textarea, whose value is a property and never content, so a
  live region had nothing to announce.
- `TTS_VOICE` no longer defaults to a voice name most self hosted servers refuse.
  Without it speech output counts as not configured and the page shows no button.
- Timestamps carry a UTC offset, so the browser no longer reads them as its own
  local time.
- A missing `.env` no longer stops `docker compose`, the backend names the
  missing variable instead.
