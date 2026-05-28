# Moon666 — Anti-Fraud 2.0 + Admin Power Tools + Premium Features
**Date:** 2026-05-28  
**Status:** Approved  
**Scope:** Phase 2 (Anti-Fraud 2.0) + Phase 3 (Admin Power Tools) + Phase 5 partial (Referral Cards, Achievements)

---

## 1. Overview

Eight tasks across three phases that harden fraud protection, give the admin full operational control, and add viral/engagement mechanics for users.

---

## 2. Database Changes

### 2.1 Modified tables

**`users`** — add one column:
```sql
is_banned BOOLEAN NOT NULL DEFAULT FALSE
```

### 2.2 New tables

**`campaigns`**
```
id            SERIAL PRIMARY KEY
name          VARCHAR(128) NOT NULL
bonus_multiplier NUMERIC(5,2) NOT NULL DEFAULT 1.00
applies_to    ENUM('join','reaction','all') NOT NULL DEFAULT 'join'
starts_at     TIMESTAMPTZ NOT NULL
ends_at       TIMESTAMPTZ NOT NULL
created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
```

**`user_achievements`**
```
id              SERIAL PRIMARY KEY
user_id         BIGINT NOT NULL REFERENCES users(id)
achievement_type ENUM('first_referral','referrals_10','referrals_25','referrals_100') NOT NULL
achieved_at     TIMESTAMPTZ NOT NULL DEFAULT now()
UNIQUE (user_id, achievement_type)
```

### 2.3 Alembic migration
Single migration file: `alembic/versions/002_antifrud_features.py`

---

## 3. Config Changes (`shared/config.py`)

```python
min_referred_user_id: Optional[int] = None   # None = disabled; set e.g. 7_000_000_000 to block very new TG accounts
auto_approve_below: Decimal = Decimal("0.00") # 0.00 = disabled
suspicious_hourly_threshold: int = 8          # referrals from one referrer within 1 hour
```

---

## 4. Feature Designs

### 4.1 Anti-Fraud — Account Age Check (2.1)

**Context:** Telegram Bot API does not expose account creation date. User IDs are sequential — lower ID = older account. Approximate mapping: IDs > 7 000 000 000 were created in 2024+.

**Implementation:**
- In `bot/handlers/start.py` → `_record_referral()`: before creating the `Referral` row, if `settings.min_referred_user_id is not None` and `user.id > settings.min_referred_user_id` → return without creating referral.
- Configurable via `MIN_REFERRED_USER_ID` env var. Default: disabled.

**Limitation:** This is a heuristic, not a precise date check. Document in README.

---

### 4.2 Anti-Fraud — User Ban System (2.2)

**Bot side:**
- `DbSessionMiddleware` extended: after loading session, check `user.is_banned`. If True → send "🚫 You've been restricted from using this bot." and return without calling handler.
- Referrals from/to banned users are skipped in `_record_referral()`.

**Admin panel side:**
- `POST /users/{user_id}/ban` — toggles `is_banned`.
- `POST /users/{user_id}/unban` — same toggle.
- Ban button visible on Users list and User Detail page.

---

### 4.3 Anti-Fraud — Suspicious Activity Alert (2.3)

**Flow:**
1. After `Referral` row committed in `_record_referral()`, count referrals created by same `referrer_id` in the past 1 hour.
2. If count >= `settings.suspicious_hourly_threshold` AND count == threshold (fire once, not on every subsequent referral):
   → `bot.send_message(settings.admin_tg_id, alert_text, reply_markup=InlineKeyboardMarkup)`
   → Buttons: `[🚫 Ban user | ✅ Ignore]`
3. Callback data: `ban_user:{user_id}` / `ignore_alert:{user_id}`
4. New handler file `bot/handlers/admin_callbacks.py` processes these callbacks.

---

### 4.4 Admin — User Detail Page (3.1)

**Route:** `GET /users/{user_id}`

**Template sections:**
- **Header:** avatar placeholder, @username, full_name, joined_at, is_banned badge.
- **Stats row:** balance, total referrals, total earned, total withdrawn.
- **Referrals table:** referred user, date, join/reaction/retention bonus status.
- **Transactions table:** date, type, amount, related user.
- **Withdrawals table:** date, amount, wallet, status.
- **Action buttons:** Ban/Unban toggle, Adjust Balance (modal form `POST /users/{id}/adjust`), Send Message (form `POST /users/{id}/message`).

**Send Message** calls `bot.send_message(user_id, text)` via `web/notifications.py`.

**Adjust Balance** — adds or subtracts amount from `user.balance_usdt`, inserts a `Transaction` row with type `manual_adjustment` (new enum value).

---

### 4.5 Admin — Campaign Manager (3.2)

**Routes:**
- `GET /campaigns` — list all campaigns.
- `GET /campaigns/new` — creation form.
- `POST /campaigns` — create campaign.
- `GET /campaigns/{id}/edit` — edit form.
- `POST /campaigns/{id}` — update.
- `POST /campaigns/{id}/delete` — delete.

**Bot integration in `referral.py`:**
```python
async def _get_active_campaign(session, bonus_type) -> Optional[Campaign]:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Campaign).where(
            Campaign.starts_at <= now,
            Campaign.ends_at >= now,
            or_(Campaign.applies_to == bonus_type, Campaign.applies_to == 'all')
        ).limit(1)
    )
    return result.scalar_one_or_none()
```
- `award_join_bonus()` and `award_reaction_bonus()` call `_get_active_campaign()` and multiply amount.

**Campaign announcement:**
- When a campaign is created via admin panel → `POST /campaigns` also sends announcement to all users via broadcast (see 4.6 — or just admin channel post).

---

### 4.6 Admin — CSV Export (3.3)

**Routes (return `StreamingResponse` with `text/csv` content type):**
- `GET /users/export.csv`
- `GET /withdrawals/export.csv`
- `GET /transactions/export.csv` (optional, add later if needed)

Fields:
- Users: id, username, full_name, balance_usdt, referrals_count, joined_at, channel_joined_at, is_banned
- Withdrawals: id, user_id, username, amount_usdt, wallet_address, status, created_at, processed_at

---

### 4.7 Admin — Auto-Approval (3.4)

**Location:** `bot/handlers/withdrawal.py` — after withdrawal row is inserted:
```python
if settings.auto_approve_below > 0 and w.amount_usdt <= settings.auto_approve_below:
    w.status = WithdrawalStatus.approved
    w.processed_at = datetime.now(timezone.utc)
    user.balance_usdt -= w.amount_usdt
    await session.commit()
    await bot.send_message(user.id, "✅ Your withdrawal was auto-approved...")
    return  # skip pending flow
```

---

### 4.8 Admin — Mobile Responsive (3.5)

**Changes in `web/templates/base.html`:**
- Add hamburger button `☰` visible only on mobile.
- Add CSS `@media (max-width: 768px)` block:
  - Sidebar hidden by default, slides in via `.open` class.
  - Main content takes full width.
  - Tables scroll horizontally.
  - Cards stack vertically.
- ~30 lines of vanilla JS for sidebar toggle.

---

### 4.9 Referral Card Generator (5.1)

**Command:** `/card` in bot.

**Library:** `Pillow` (add to `requirements.txt`).

**Design:**
- 800×420px, dark background `#0b0c10`.
- Crescent moon graphic (reuse bot avatar or simplified vector drawn with Pillow).
- Text: `@username`, `X referrals`, `$Y.YY earned`, Moon666 branding.
- Gold `#f0b90b` accent color.
- Output: PNG bytes → `bot.send_photo(user_id, BufferedInputFile(img_bytes, "card.png"))`.

**File:** `bot/services/card_generator.py` — single function `generate_card(username, ref_count, earned) -> bytes`.

---

### 4.10 Achievement System (5.2)

**Milestones:**
| Enum value | Trigger | Message |
|---|---|---|
| `first_referral` | 1st referral join bonus | 🌱 First Referral! |
| `referrals_10` | 10th | 🔥 10 Referrals! |
| `referrals_25` | 25th | ⚡ 25 Referrals! |
| `referrals_100` | 100th | 💎 100 Referrals! |

**File:** `bot/services/achievements.py`
```python
async def check_and_award(session, referrer_id, bot) -> None:
    count = # total join bonuses paid for referrer
    for threshold, ach_type, msg in MILESTONES:
        if count >= threshold:
            exists = # check UserAchievement for this user+type
            if not exists:
                session.add(UserAchievement(...))
                await session.commit()
                await bot.send_message(referrer_id, msg)
```
Called from `award_join_bonus()` after commit.

**Bot display:** Cabinet handler — new section "🏆 Achievements" in the `/myref` or main menu showing earned badges.

---

## 5. New Files Summary

| File | Purpose |
|---|---|
| `bot/handlers/admin_callbacks.py` | Ban/Ignore inline keyboard callbacks |
| `bot/services/card_generator.py` | Pillow referral card |
| `bot/services/achievements.py` | Achievement check + award |
| `web/routes/campaigns.py` | Campaign CRUD routes |
| `web/templates/user_detail.html` | User detail page |
| `web/templates/campaigns.html` | Campaigns list |
| `web/templates/campaign_form.html` | Create/edit campaign |
| `alembic/versions/002_antifrud_features.py` | DB migration |

## 6. Modified Files Summary

| File | Change |
|---|---|
| `shared/models.py` | `User.is_banned`, `Campaign`, `UserAchievement`, `TransactionType.manual_adjustment` |
| `shared/config.py` | 3 new settings |
| `bot/handlers/start.py` | user_id threshold check in `_record_referral` |
| `bot/middlewares/db.py` | Ban check before handler dispatch |
| `bot/services/referral.py` | Campaign multiplier, suspicious alert, call achievements |
| `bot/handlers/cabinet.py` | `/card` command, achievements section |
| `bot/main.py` | Register `admin_callbacks` router |
| `web/routes/users.py` | Detail page, ban/unban endpoints, CSV export |
| `web/routes/withdrawals.py` | Auto-approval logic |
| `web/main.py` | Register `campaigns_router` |
| `web/templates/base.html` | Mobile CSS + JS, Campaigns sidebar link |
| `web/templates/users.html` | Ban button, clickable rows |

---

## 7. Implementation Order

| Task | Files | Estimated effort |
|---|---|---|
| T1: DB migration | `models.py`, `002_migration.py` | Small |
| T2: Anti-fraud (ban middleware, user_id check, suspicious alert) | `middlewares/db.py`, `start.py`, `referral.py`, `admin_callbacks.py` | Medium |
| T3: Ban UI + User Detail page | `users.py`, `user_detail.html`, `users.html` | Medium |
| T4: Campaign Manager | `campaigns.py`, `referral.py`, templates | Large |
| T5: CSV Export | `users.py`, `withdrawals.py` | Small |
| T6: Auto-approval + Mobile admin | `withdrawals.py`, `base.html` | Small |
| T7: Referral Card | `card_generator.py`, `cabinet.py` | Medium |
| T8: Achievement System | `achievements.py`, `referral.py`, `cabinet.py`, `models.py` | Medium |
