# Zayavki Olesya Bot — Бот №1 (Анкета ассистента)

## Что сделано
- Telegram-бот на **python3 + aiogram v3**.
- Вопросы и варианты ответов хранятся в **SQLite** и редактируются через простую **админ‑панель**.
- Поддержка фиксированных вариантов, множественного выбора, свободного текста и загрузки файлов.
- Файлы скачиваются на сервер и отдаются по ссылке `/files/{id}`.
- Опциональная отправка данных в Google Sheets (с фоллбеком в JSONL-лог).
- Поддержка второго бота (тест ассистента) с выдачей результата и PDF.

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
   ASSISTANT_TEST_BOT_TOKEN=your_second_bot_token
   FILES_BASE_URL=https://your-domain.com
   ADMIN_TOKEN=supersecret
   GOOGLE_SHEET_ID=your_sheet_id
   GOOGLE_SHEET_TAB=Sheet1
   # Один из вариантов:
   GOOGLE_SHEETS_CREDENTIALS_PATH=/absolute/path/to/service_account.json
   # или
   GOOGLE_SHEETS_CREDENTIALS_JSON={"type":"service_account",...}
   # Файлы результатов теста (4 pdf)
   ASSISTANT_TEST_PDF_DIR=/absolute/path/to/assistant_test_pdfs
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
- PDF для теста ассистента: `data/assistant_test_pdfs/`

## Google Sheets
1. Создайте таблицу и нужный лист (таб) в Google Sheets.
2. В Google Cloud создайте Service Account и скачайте JSON‑ключ.
3. Поделитесь таблицей с email сервисного аккаунта.
4. Заполните переменные окружения `GOOGLE_SHEET_ID`, `GOOGLE_SHEET_TAB` и путь/JSON ключа.

## Тест ассистента (второй бот)
1. Создайте второго бота в Telegram и укажите `ASSISTANT_TEST_BOT_TOKEN`.
2. Положите 4 файла в папку `ASSISTANT_TEST_PDF_DIR`:
   - `office_assistant.pdf`
   - `personal_assistant.pdf`
   - `business_assistant.pdf`
   - `multi_assistant.pdf`
3. В админ‑панели перейдите в раздел «Анкеты» и проверьте вопросы теста.

## Важно
- После изменения вопросов/вариантов через админку бот использует новые данные сразу.
- Для продакшна убедитесь, что домен доступен извне и корректно настроен `WEBHOOK_URL`.
