# کوین‌پالس — CoinPulse

سبد ارز دیجیتال با قیمت ۵۰ ارز برتر، نمودار تاریخی، هشدار قیمتی و اطلاع‌رسانی تلگرام.

پشته: FastAPI · Vue 3 · PostgreSQL 16 · Redis 7 · ARQ · aiogram

- طراحی تاییدشده: [`docs/design/architecture.html`](docs/design/architecture.html)
- حالت زنده پروژه (اول این را بخوانید): [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)
- قوانین مخزن برای هوش مصنوعی: [`CLAUDE.md`](CLAUDE.md)

## راه‌اندازی

```bash
cp .env.example .env          # کلیدها را داخل همین فایل بگذارید
bash scripts/install_hooks.sh # هوک به‌روزرسانی PROJECT_STATE
make up                       # postgres · redis · api · worker · bot · web · mailhog
make migrate                  # ساخت جدول‌ها (alembic)
make seed                     # گرفتن فهرست ۵۰ ارز برتر
```

| سرویس | آدرس |
|---|---|
| وب‌اپ | http://localhost:5173 |
| مستندات API | http://localhost:8000/docs |
| سلامت سیستم | http://localhost:8000/api/v1/health |
| ایمیل محیط توسعه (MailHog) | http://localhost:8025 |

## کلیدهای لازم در `.env`

| متغیر | از کجا |
|---|---|
| `COINGECKO_DEMO_KEY` | داشبورد CoinGecko، سهم Demo |
| `TELEGRAM_BOT_TOKEN` | ربات `@BotFather` |
| `SMTP_*` | هر ارائه‌دهنده SMTP؛ در محیط توسعه MailHog بدون کلید کار می‌کند |
| `SECRET_KEY` | یک رشته تصادفی ۳۲ بایتی |

بدون این کلیدها هم پروژه بالا می‌آید: ایمیل‌ها در MailHog می‌نشینند و ربات تلگرام
غیرفعال می‌ماند، ولی فهرست بازار با سهم عمومی CoinGecko کار می‌کند.

## نکته مهم درباره قیمت‌ها

قیمت هر ۵ دقیقه با **یک** فراخوان از CoinGecko گرفته می‌شود (سقف رایگان ~۱۰٬۰۰۰
درخواست در ماه). یعنی:

- تاخیر هشدار تا ۵ دقیقه است.
- نوسانی که بین دو نمونه‌گیری رخ بدهد و برگردد، هشدار نمی‌سازد.
- `POLL_INTERVAL_SECONDS` را کمتر از ۳۰۰ نگذارید مگر با سهم پولی.

جزئیات و مسیر ارتقا: [`docs/adr/0001-price-source.md`](docs/adr/0001-price-source.md)

## دستورهای روزمره

```bash
make test    # تست‌های بک‌اند (هسته هشدار)
make lint    # ruff + mypy
make logs    # لاگ api و worker
make state   # به‌روزرسانی دستی docs/PROJECT_STATE.md
```

## ساختار

```
backend/app/
  core/      config · security · errors · deps
  domain/    enum های دامنه، بدون هیچ فریم‌ورکی
  db/        مدل‌های SQLAlchemy و session
  schemas/   ورودی و خروجی Pydantic
  api/v1/    روترها — فقط اعتبارسنجی و صدا زدن سرویس
  services/  منطق دامنه (alert_engine هسته تست‌شده است)
  workers/   کارگرهای ARQ
  bot/       هندلرهای aiogram
frontend/src/
  api/ stores/ components/ views/ styles/
```
