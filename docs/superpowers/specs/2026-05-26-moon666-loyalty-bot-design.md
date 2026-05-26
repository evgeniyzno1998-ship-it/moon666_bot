# Moon666 Loyalty Bot — Design Spec

**Date:** 2026-05-26  
**Project:** Новый standalone Telegram-бот для канала Moon666  
**Channel:** t.me/Moon666 (11 подписчиков на старте), трафик из X (@moonstone0609)

---

## 1. Цель

Реферальная программа лояльности для Telegram-канала Moon666. Подписчики приглашают друзей по личной ссылке и зарабатывают USDT. Владелец видит полную аналитику и управляет выплатами.

---

## 2. Архитектура

Два отдельных сервиса, общая PostgreSQL, деплой через docker-compose.

```
Подписчики (Telegram) ──→ Сервис 1: aiogram 3 (бот)
Владелец (браузер)    ──→ Сервис 2: FastAPI (веб-панель)
                               ↓            ↓
                          PostgreSQL (общая БД)
```

**Стек:**
- Bot: Python 3.12, aiogram 3, asyncpg, SQLAlchemy async
- Web: FastAPI, Jinja2, SQLAlchemy async, тёмная тема
- DB: PostgreSQL 16
- Deploy: docker-compose (3 контейнера: bot, web, postgres)

---

## 3. Бонусная система

За каждого приведённого реферала начисляется до трёх разовых бонусов:

| Событие | Сумма | Условие начисления |
|---|---|---|
| Реферал подписался на канал | +0.20 USDT | Один раз при верификации подписки |
| Реферал поставил реакцию на пост | +0.01 USDT | Один раз за всё время жизни |
| Реферал остался в канале 30 дней | +0.05 USDT | Один раз, проверка через 30 дней после вступления |

**Максимум с одного реферала:** 0.26 USDT  
**Вывод:** от 10 USDT, ручное подтверждение владельцем

---

## 4. Модель данных

### `users`
| Поле | Тип | Описание |
|---|---|---|
| id | BIGINT PK | Telegram user_id |
| username | VARCHAR | @username |
| full_name | VARCHAR | Имя |
| referred_by | BIGINT FK | user_id реферера |
| balance_usdt | NUMERIC(10,2) | Текущий баланс |
| joined_at | TIMESTAMP | Дата регистрации в боте |
| channel_joined_at | TIMESTAMP | Дата подтверждённой подписки |

### `referrals`
| Поле | Тип | Описание |
|---|---|---|
| id | SERIAL PK | |
| referrer_id | BIGINT FK | Кто привёл |
| referred_id | BIGINT FK | Кого привёл |
| join_bonus_paid | BOOLEAN | Выплачен ли бонус за вступление |
| reaction_bonus_paid | BOOLEAN | Выплачен ли бонус за реакцию |
| retention_bonus_paid | BOOLEAN | Выплачен ли бонус 30 дней |
| created_at | TIMESTAMP | |

### `transactions`
| Поле | Тип | Описание |
|---|---|---|
| id | SERIAL PK | |
| user_id | BIGINT FK | Получатель |
| amount_usdt | NUMERIC(10,2) | Сумма |
| type | ENUM | `referral_join`, `referral_reaction`, `referral_retention` |
| related_user_id | BIGINT | Реферал за которого начислено |
| created_at | TIMESTAMP | |

### `withdrawals`
| Поле | Тип | Описание |
|---|---|---|
| id | SERIAL PK | |
| user_id | BIGINT FK | |
| amount_usdt | NUMERIC(10,2) | |
| wallet_address | VARCHAR | Адрес кошелька пользователя |
| status | ENUM | `pending`, `approved`, `rejected` |
| created_at | TIMESTAMP | |
| processed_at | TIMESTAMP | Когда владелец обработал |

### `channel_reactions`
| Поле | Тип | Описание |
|---|---|---|
| id | SERIAL PK | |
| user_id | BIGINT FK | Пользователь который среагировал |
| post_id | BIGINT | ID поста в канале |
| reacted_at | TIMESTAMP | |

Уникальный индекс на `(user_id)` — нам достаточно знать факт первой реакции для начисления бонуса рефереру. Повторные реакции игнорируются.

---

## 5. Бот — сценарии

### Старт
1. Пользователь кликает `t.me/Moon666Bot?start=REF123`
2. Бот фиксирует реферера из deep link
3. Проверяет подписку на канал Moon666
4. Если не подписан → кнопка «Подписаться» + «Проверить»
5. После подтверждения → приветствие + личный кабинет + реферер получает +0.20 USDT и уведомление

### Главное меню (inline кнопки)
- 💰 Мой баланс → карточка Premium Dark с прогресс-баром к выводу
- 👥 Мои рефералы → список приведённых с суммой заработка
- 🔗 Моя ссылка → реф. ссылка + текст для шаринга
- 📤 Вывод → форма ввода кошелька (если баланс ≥ 10 USDT)
- 🏆 Топ рефералов → топ-10 по количеству рефералов

### Личный кабинет (стиль Premium Dark)
```
🌙 Moon666 · @username

┌─────────────────────────┐
│  3.40 USDT              │
│  ████░░░░░░ 34%         │
│  До вывода: 6.60 USDT   │
└─────────────────────────┘

👥 17 рефералов · 💰 заработано 4.42 USDT

🔗 t.me/Moon666Bot?start=REF123
```

### Уведомления
- Новый реферал зарегистрировался → уведомление рефереру
- Начислен бонус (реакция / 30 дней) → уведомление рефереру
- Заявка на вывод одобрена / отклонена → уведомление пользователю

### Отслеживание реакций
Бот подключается к каналу как участник через `channel_post_reaction` хэндлер aiogram. При первой реакции реферала проверяет `channel_reactions` — если записи нет, начисляет +0.01 USDT рефереру.

### Проверка удержания 30 дней
Фоновая задача (asyncio scheduler, раз в час): проверяет пользователей у которых `channel_joined_at` было 30 дней назад и `retention_bonus_paid = False`. Проверяет через Telegram API что пользователь ещё в канале. Начисляет бонус рефереру.

---

## 6. Веб-панель администратора

**Аутентификация:** простой логин/пароль в `.env`, JWT-сессия.

### Страницы

**Dashboard (главная)**
- KPI: подписчиков всего, начислено USDT, выплачено USDT, заявок в очереди
- Граф роста подписчиков (по неделям)
- Последние 5 заявок на вывод
- Фильтр периода: Today / 7d / 30d / 90d / Custom (date picker)

**Аналитика**
- Retention воронка: день 1 / 7 / 30 / 60
- Расход по типам бонусов (referral join / reaction / retention) — bar chart
- Стоимость одного привлечённого подписчика
- Топ-10 рефереров
- Все метрики пересчитываются под выбранный период

**Выводы**
- Таблица заявок: username, кошелёк, сумма, дата, статус
- Кнопки: ✅ Выплатить / ❌ Отклонить
- При нажатии «Выплатить» → статус `approved`, уведомление пользователю в боте
- История всех выплат с фильтром по статусу и периоду

**Пользователи**
- Список всех: username, баланс, кол-во рефералов, дата вступления, статус (в канале / вышел)
- Поиск по username

**Настройки**
- Суммы бонусов (реферал, реакция, retention) — редактируемые
- Минимальная сумма вывода
- Текст приветственного сообщения бота

---

## 7. Структура проекта

```
moon666_bot/
├── bot/
│   ├── main.py              # aiogram app entry
│   ├── handlers/
│   │   ├── start.py         # /start, deep link
│   │   ├── cabinet.py       # кабинет, баланс, ссылка
│   │   ├── withdrawal.py    # запрос на вывод
│   │   └── reactions.py     # channel_post_reaction
│   ├── services/
│   │   ├── referral.py      # логика начислений
│   │   └── scheduler.py     # retention checker
│   └── keyboards.py
├── web/
│   ├── main.py              # FastAPI app entry
│   ├── routes/
│   │   ├── dashboard.py
│   │   ├── analytics.py
│   │   ├── withdrawals.py
│   │   ├── users.py
│   │   └── settings.py
│   └── templates/           # Jinja2, тёмная тема
├── shared/
│   ├── models.py            # SQLAlchemy models
│   ├── database.py          # async engine
│   └── config.py            # настройки из .env
├── docker-compose.yml
├── .env.example
└── alembic/                 # миграции БД
```

---

## 8. Деплой

```yaml
# docker-compose.yml (схема)
services:
  postgres:
    image: postgres:16
  bot:
    build: ./bot
    depends_on: [postgres]
  web:
    build: ./web
    depends_on: [postgres]
    ports: ["8000:8000"]
```

Деплой на VPS: `git pull && docker-compose up -d --build`

---

## 9. Что за рамками v1

- Автоматические крипто-выплаты (v2)
- Мультиканальность (v2)
- Задания (подписаться на X, репост) (v2)
- Мобильное приложение (не нужно, Telegram и так мобильный)
