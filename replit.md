# Telegram Bot — «Пиши или умри»

A Python Telegram writing tracker bot («Write or Die») built with `python-telegram-bot`.

## Overview

This bot helps writers track their daily writing progress. User data is stored in `writers.json`.

## Commands

- `/start` — greet the user and show available commands (also sends `welcome.png` if present)
- `/goal <number>` — set a daily word count goal (default: 500)
- `/report <number>` — log words written today; updates streak and totals
- `/stats` — show today's count, total words, and current day streak

## Project Structure

- `bot.py` — main bot file with all handlers
- `writers.json` — persistent user data (auto-created on first run)
- `welcome.png` — optional welcome image sent on `/start`

## Setup

1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram and get the token
2. Set `TELEGRAM_BOT_TOKEN` as a secret in the environment
3. Run via the "Start application" workflow

## Dependencies

- `python-telegram-bot` — Telegram Bot API wrapper
