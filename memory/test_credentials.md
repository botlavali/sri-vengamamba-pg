# SV PG for Gents — Test Credentials

## Admin
- Email: `admin@svpg.com`
- Password: `Admin@123`
- Role: `admin`
- Dashboard: `/admin.html`

## Demo bookings (already seeded, will show as RED on bed grid)
- Floor 1 Room 101 Bed 1 — Ramesh (2-share, ₹11,000)
- Floor 1 Room 103 Bed 2 — Suresh (3-share, ₹9,000)
- Floor 2 Room 204 Bed 1 — Vijay (3-share, ₹9,000)
- Floor 3 Room 302 Bed 1 — Kumar (2-share, ₹11,000)
- Floor 6 Room 601 Bed 1 — Anil (2-share, ₹11,000)

## To test booking flow (create a guest)
1. Go to `/register.html` → create account
2. Accept rules at `/rules.html`
3. At `/rooms.html` → click any green bed → fill modal → pay (Razorpay TEST mode)
4. Use Razorpay test card `4111 1111 1111 1111` · CVV `123` · any future expiry · OTP `1234`

## Razorpay
- Mode: TEST (live keys configured)
- Key ID: `rzp_test_T10i4ZBVthrTAW`
- Webhook URL: `<BASE_URL>/api/payments/webhook`
- Webhook Secret (already in .env): `F4GJiyV9QOcpX6AojurYDtJVJTbmy5W_0hEGQO32vq4`
