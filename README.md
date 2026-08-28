# Gig Saarthi 🤝

**Cooperative Gig Services Platform for Household & Community Services**

> Ministry of Cooperation — NCCT | Problem Statement ID: 26089

## Overview

Gig Saarthi is a cooperative-model gig platform connecting workers and customers for household and community services. Workers organize through cooperatives, ensuring fair wages, insurance, and dignity.

### Key Features

- **Geo-Matching Engine** — Haversine-based nearby worker finder with distance + rating ranking
- **AI Demand Forecasting** — Moving average + seasonal patterns predict service demand
- **Cooperative Model** — Federation hierarchy (Village → District → State)
- **Razorpay Payments** — Secure checkout with UPI/Card support (test mode)
- **OTP Authentication** — Phone-based registration with OTP verification
- **Multi-step Onboarding** — 5-step worker profile with document upload
- **Multilingual** — English + Hindi + Bengali with language switcher
- **Mobile-First** — Responsive design works as a web app on Android Chrome
- **Real-time Updates** — Live booking status polling and notifications

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5.x + Django REST Framework |
| Frontend | Django Templates + Tailwind CSS + HTMX + Alpine.js |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Payments | Razorpay (test mode) |
| Maps | Leaflet.js + OpenStreetMap |
| Charts | Chart.js |
| Async | Celery + Redis (optional) |
| Auth | Django Auth + SimpleJWT |

## Quick Start

### 1. Clone & Setup

```bash
cd "Gig Saarthi"
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt  # or install manually
```

### 2. Initialize Database

```bash
python manage.py migrate
python manage.py seed_data
```

### 3. Create Superuser (for Admin)

```bash
python manage.py createsuperuser
```

### 4. Run Development Server

```bash
python manage.py runserver
```

Visit: http://localhost:8000

## Demo Credentials

| Role | Username | Password | Access |
|------|----------|----------|--------|
| Platform Admin | `admin` | `admin123` | Admin dashboard, worker verification |
| Worker | `worker_001` | `worker123` | Worker dashboard, job management |
| Customer | `customer_001` | `customer123` | Booking, payment, ratings |

## Project Structure

```
gigsaarthi/
├── accounts/          # Custom User model, OTP auth, registration
├── bookings/          # Booking lifecycle, matching engine, signals
├── cooperative_admin/ # Admin dashboard, demand forecasting
├── core/              # Shared utilities, OTP service, matching, validation
├── customers/         # Customer profiles, onboarding
├── notifications/     # In-app notifications
├── payments/          # Razorpay integration, invoices, payouts
├── ratings/           # Reviews, rating breakdown, flagging
├── workers/           # Worker profiles, skills, certifications
├── templates/         # All HTML templates (Tailwind CSS)
├── locale/            # Hindi translations (i18n)
├── static/            # Static files
├── media/             # User uploads
└── gigsaarthi/        # Django project settings
```

## Architecture

### Booking Lifecycle

```
Customer creates booking
        ↓
Matching engine finds nearby workers (Haversine)
        ↓
Best worker assigned (status: matched)
        ↓
Worker accepts/rejects
        ↓ (accept)
Worker starts job (in_progress)
        ↓
Worker marks complete (completed)
        ↓
Invoice auto-generated
        ↓
Customer pays via Razorpay
        ↓
Worker payout record created
        ↓
Customer rates worker
```

### Matching Algorithm

1. Filter workers by required skill
2. Filter: available + verified + no active bookings
3. Calculate Haversine distance from booking location
4. Rank by: 60% distance + 40% rating (normal) / 80% distance + 20% rating (emergency)
5. Return top 5 candidates, auto-assign best

### Demand Forecasting

- Weighted moving average of last 4 weeks
- Seasonal multipliers (Diwali peak, monsoon plumbing, etc.)
- Day-of-week weights (weekend peak)
- Service-specific patterns (cleaning spikes before festivals)
- Shortage detection when demand > 1.5× available workers

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register/` | Register with OTP |
| POST | `/api/auth/register/verify/` | Verify OTP & create account |
| POST | `/api/auth/login/` | Login (password) |
| POST | `/api/auth/otp/request/` | Request OTP |
| POST | `/api/auth/otp/verify/` | Verify OTP (login) |
| GET | `/api/auth/me/` | Current user profile |

### Workers
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/workers/` | List workers (filterable) |
| GET | `/api/workers/<id>/` | Worker detail |
| GET/PATCH | `/api/workers/me/` | My worker profile |

### Bookings
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/bookings/` | List bookings |
| POST | `/api/bookings/create/` | Create booking |
| GET | `/api/bookings/<id>/` | Booking detail |
| GET | `/api/bookings/categories/` | Service categories |

### Payments
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/payments/invoices/` | List invoices |
| POST | `/api/payments/webhook/` | Razorpay webhook |

## Environment Variables

Create a `.env` file:

```env
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (SQLite default)
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3

# Razorpay (Test Mode)
RAZORPAY_KEY_ID=rzp_test_xxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxx

# Celery (optional)
CELERY_BROKER_URL=redis://localhost:6379/0
```

## Production Deployment

### Railway / Render

1. Push to GitHub
2. Connect repo to Railway/Render
3. Set environment variables
4. Deploy with:
   ```
   pip install -r requirements.txt
   python manage.py collectstatic --noinput
   python manage.py migrate
   python manage.py seed_data
   ```

### Security Checklist

- [x] CSRF protection on all forms
- [x] File upload validation (type/size limits)
- [x] Rate limiting on login endpoints
- [x] Environment variables for secrets
- [x] OTP hashed storage (not raw)
- [x] Razorpay signature verification
- [x] Webhook signature validation
- [ ] `DEBUG=False` for production
- [ ] `ALLOWED_HOSTS` configured
- [ ] HTTPS enforced

## Screenshots

### Landing Page
Mobile-first responsive design with cooperative branding.

### Booking Flow
Customer selects service → picks location on map → submits → system matches worker.

### Admin Dashboard
Real-time stats, booking monitor, demand forecast charts, worker verification queue.

## License

Built for NCCT Hackathon — Gig Saarthi Team

---

**Generated with Codebuff 🤖**
