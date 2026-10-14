# Backstage — event accreditation platform

A Django app for running the people side of an event, in the spirit of tools like In2event:
**accreditation**, **partner portals**, **artist advancing** and **crew planning**, with QR
check-in at the gate.

## Modules

**Accreditation**
- *Zones* (Backstage, Stage, VIP…), *credentials* (Artist, Crew, Press…) that combine zones and
  default *items* (wristbands, drink tokens, parking tickets).
- *People*: one accreditation per person with credential, company, valid days, extra zones,
  items and status (draft → pending → approved / rejected / cancelled). Filter, search, bulk
  approve/reject/e-mail, CSV export.
- *Approvals* queue grouped by company, showing contingent usage.
- *Personal e-ticket* (`/t/<code>/`) with a QR code, zones, days and items to pick up. It is
  e-mailed on approval.
- *Check-in*: scan with a phone camera or a USB barcode scanner, or search by name. It checks
  status, valid day and zone access, flags double check-ins, tracks who is on site, and shows
  which items to hand out.

**Partner portals** – every company gets a private link (`/p/<token>/`) and a contingent per
credential. Partners add their people as drafts and submit them for approval; the quota is
enforced. Credentials can be set to auto-approve.

**Artists** – bookings with performances on stages (visual timetable, overlap check),
advancing sheet (arrival, technical/hospitality rider, rider file, dressing room),
transport and hotel requests the organiser confirms. The artist's tour manager uses the same
portal link to fill in advancing, request transport/hotel and register the party.

**Crew** – teams and shifts with capacity, a printable roster per day, and a public volunteer
sign-up form (`/v/<token>/`). Approved volunteers get their credential and claim open shifts
from their e-ticket page (capacity, overlap and max-shift rules enforced).

## Getting started

```bash
cd website
python3 -m pip install -r requirements.txt
python3 manage.py migrate
python3 manage.py createsuperuser
python3 manage.py seed_demo        # optional: a fully filled demo event
python3 manage.py runserver
```

Open http://127.0.0.1:8000, sign in, and pick the event. Portal, ticket and volunteer links work
without logging in; everything else requires an organiser account.

E-mails (tickets, rejections, portal invites) are printed to the console until you configure SMTP.

```bash
python3 manage.py test tests
```

## Configuration

| Variable | Default | |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | dev key | **Set in production.** |
| `DJANGO_DEBUG` | `1` | `0` in production. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma separated. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | – | e.g. `https://accr.example.nl` |
| `DJANGO_SITE_URL` | `http://127.0.0.1:8000` | Used for links in e-mails. |
| `DJANGO_DB_PATH` | `website/db.sqlite3` | |
| `DJANGO_MEDIA_ROOT` | `website/media` | Uploaded rider files. |
| `DJANGO_EMAIL_BACKEND`, `DJANGO_EMAIL_HOST`, `…_PORT`, `…_HOST_USER`, `…_HOST_PASSWORD`, `…_USE_TLS`, `DJANGO_DEFAULT_FROM_EMAIL` | console | SMTP settings. |

The camera scanner and QR codes load two small libraries from jsDelivr (`jsqr`,
`qrcode-generator`). USB scanners and name search work fully offline.

## Layout

```
website/
  config/         settings & URLs
  core/           events, days, activity log, dashboard, UI (templates, CSS, JS)
  accreditation/  zones, credentials, items, companies, contingents, people, scanning
  artists/        stages, artists, performances, transport, hotel rooms
  crew/           teams, shifts, assignments, volunteer settings & profiles
  portal/         public pages: partner/artist portal, e-ticket, volunteer sign-up
  tests/
```
