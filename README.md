# Zayavki Olesya Bot — Бот №1 (Анкета ассистента)

## Что сделано
- Telegram-бот на **python3 + aiogram v3**.
- Вопросы и варианты ответов хранятся в **SQLite** и редактируются через простую **админ‑панель**.
- Поддержка фиксированных вариантов, множественного выбора, свободного текста и загрузки файлов.
- Файлы скачиваются на сервер и отдаются по ссылке `/files/{id}`.
- Опциональная отправка данных в Google Sheets (с фоллбеком в JSONL-лог).

## Запуск
1. Установите зависимости:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Создайте `.env`:
   ```env
   BOT_TOKEN=your_telegram_bot_token
   FILES_BASE_URL=https://your-domain.com
   ADMIN_TOKEN=supersecret
   GOOGLE_SHEET_ID=your_sheet_id
   GOOGLE_SHEET_TAB=Sheet1
   # Один из вариантов:
   GOOGLE_SHEETS_CREDENTIALS_PATH=/absolute/path/to/service_account.json
   # или
   GOOGLE_SHEETS_CREDENTIALS_JSON={"type":"service_account",...}
   ```
3. Запустите приложение:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

## Админ‑панель
- Список вопросов: `http://your-domain.com/admin/questions?token=ADMIN_TOKEN`
- Редактирование вопроса: клик по вопросу в списке
- Список пользователей: `http://your-domain.com/admin/users?token=ADMIN_TOKEN`

## Хранение данных
- База данных: `data/app.db`
- Файлы пользователей: `data/files/`
- Лог заглушки Google Sheets: `data/google_sheets_stub.jsonl`

## Google Sheets
1. Создайте таблицу и нужный лист (таб) в Google Sheets.
2. В Google Cloud создайте Service Account и скачайте JSON‑ключ.
3. Поделитесь таблицей с email сервисного аккаунта.
4. Заполните переменные окружения `GOOGLE_SHEET_ID`, `GOOGLE_SHEET_TAB` и путь/JSON ключа.

## Важно
- После изменения вопросов/вариантов через админку бот использует новые данные сразу.
- Для продакшна убедитесь, что домен доступен извне и корректно настроен `WEBHOOK_URL`.
