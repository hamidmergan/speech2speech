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
