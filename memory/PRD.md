# Sri Vengamamba PG (S.V PG Hostel — Gents) | PRD

## Current Status (Jan 2026)

### Implemented
- Single-property PG booking (Sri Vengamamba PG, Gents)
- 6 floors, 34 rooms, 80 beds — pricing ₹11k/₹9k + ₹20k advance (matches GitHub repo)
- Bed-grid selection UI (green / terracotta-selected / gray-locked)
- Email/password JWT auth · mandatory PG rules acceptance gate
- **Mandatory booking form**: name (≥2 chars), phone (≥10), alt-phone (≥10), email, Aadhaar (exactly 12 digits), join date, photo upload, Aadhaar upload — server-side validated
- Photo + Aadhaar uploads (5MB cap, jpg/png/webp/pdf)
- Razorpay LIVE TEST mode + HMAC webhook
- **Auto-generated PDF receipts** on payment success
- **Auto-generated monthly rent schedule** (12 months) on booking paid

### NEW Admin Features
- **Stylish sidebar admin layout** at `/admin.html` with 6 sections
- **Overview**: KPI cards — total/booked/available beds, occupancy %, current-month rent collected/pending/paid-count/pending-count, lifetime rent + advance
- **Residents**: Card-style list with photo thumbnail, contact details, beds chips, Aadhaar view button, **Check-out** button
- **Monthly Rent Matrix**: residents × months grid · click pending cell to mark paid · click bell icon to send reminder
- **Mark Paid modal**: choose method (cash/UPI/bank/cheque) + reference
- **Reminders log**: every reminder stored with sent/logged status
- **All Bookings**: full table with photo/Aadhaar thumbnails
- **Webhooks**: Razorpay webhook event audit log
- **Document viewer modal** (click any thumbnail anywhere)

### Email Reminders
- Endpoint: `POST /api/admin/rent/{id}/send_reminder`
- Logs every reminder to DB
- **If `SENDGRID_API_KEY` env var is set**, sends via SendGrid API; otherwise just logs
- Setup: add `SENDGRID_API_KEY` + `SENDGRID_FROM_EMAIL` to `/app/backend/.env`

### Checkout
- `POST /api/admin/bookings/group/{gid}/checkout`
- Frees beds (status → checked_out) + cancels future pending rent payments
- Verified: bed disappears from `/api/pg/availability` immediately

## Design System (boutique)
- Cream #F9F6F0 + Deep Forest Green #1A3B2B + Terracotta #C85A32
- Outfit (headings) + Manrope (body)
- Pill-shaped buttons, 20px rounded cards, soft shadows
- Sidebar (forest green) for admin · cream main canvas

## Future / Backlog
- P1: Configure SendGrid API key to enable real email delivery
- P2: SMS reminders via Twilio
- P2: Bulk send reminders ("send to all overdue this month")
- P2: Auto-cron daily reminder job (currently admin-triggered)
- P2: Resident self-pay monthly rent flow

Last updated: 2026-01
