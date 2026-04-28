# GPT for Telegram Tasks

Telegram-бот принимает фото, PDF или DOCX с заданием, извлекает текст, отправляет его в OpenAI и возвращает ответ пользователю.

## Pipeline

```text
Telegram -> file -> download -> limits -> parse/OCR -> extracted text -> GPT -> answer
```

## Возможности

- Фото: локальный OCR через Tesseract, затем OpenAI vision fallback.
- PDF: сначала текстовый слой через `pypdf`, затем OCR страниц в пределах лимита.
- DOCX: чтение абзацев через `python-docx`.
- Защита бюджета:
  - лимит размера файла;
  - лимит страниц PDF;
  - дневной лимит запросов на пользователя;
  - минимальная пауза между запросами пользователя.

## Локальный запуск

1. Создайте виртуальное окружение и установите зависимости:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Создайте `.env` по примеру:

```bash
copy .env.example .env
```

3. Заполните переменные:

```text
TELEGRAM_BOT_TOKEN=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
```

4. Запустите бота:

```bash
python -m src.bot
```

## Переменные окружения

| Variable | Default in `.env.example` | Description |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | required | Токен бота из BotFather |
| `TELEGRAM_PROXY_URL` | empty | Опциональный HTTP/SOCKS proxy для доступа к Telegram API |
| `OPENAI_API_KEY` | required | API key OpenAI |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Модель OpenAI для OCR fallback и ответов |
| `MAX_FILE_MB` | `15` | Максимальный размер файла |
| `MAX_PDF_PAGES` | `10` | Максимум страниц PDF |
| `USER_DAILY_LIMIT` | `20` | Запросов в день на пользователя |
| `USER_MIN_SECONDS_BETWEEN_REQUESTS` | `10` | Пауза между запросами |

## Render deploy

Репозиторий содержит `render.yaml`.

Render service:

- Type: `worker`
- Build command: `pip install -r requirements.txt`
- Start command: `python -m src.bot`

В Render Dashboard добавьте секреты:

- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`

`OPENAI_MODEL=gpt-4.1-mini` уже прописан в `render.yaml`, но его можно поменять через env.

## Ошибка подключения к Telegram API

Если локально видите ошибку вроде `Cannot connect to host api.telegram.org:443`, значит процесс не может достучаться до Telegram API. Проверьте:

- работает ли интернет/VPN;
- открывается ли `https://api.telegram.org` из этой же сети;
- не блокирует ли соединение firewall/antivirus;
- нужен ли proxy.

Для локального proxy добавьте в `.env`:

```text
TELEGRAM_PROXY_URL=http://127.0.0.1:7890
```

или SOCKS:

```text
TELEGRAM_PROXY_URL=socks5://127.0.0.1:1080
```

## OCR system packages

Для локального OCR нужны системные зависимости:

- `tesseract-ocr`
- `poppler-utils`

На Windows дополнительно может понадобиться добавить пути к Tesseract и Poppler в `PATH`.

Если на Render системные OCR-пакеты недоступны или не настроены, бот всё равно может извлекать текст из изображений через OpenAI vision fallback. Для PDF без текстового слоя желательно подключить Poppler/Tesseract или отправлять более простые PDF/фото.

## Ограничения v1

- `.doc` не поддерживается. Отправляйте `.docx` или PDF.
- Rate limit хранится в памяти процесса. После перезапуска Render Worker счетчики сбрасываются.
