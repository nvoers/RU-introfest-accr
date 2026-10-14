# IN.T.R.O. — accreditation & check-in

*Inschrijving, Toegang & Registratie Organisatie.* A small Django app for running
accreditation at an event: who's on the list, what they may access, what they
get handed at the desk, and who has arrived.

## Features

- **Events** with a live arrivals overview (tickets arrived vs. expected, per access level and type).
- **Accreditations** per event: name, organisation, type (Artist / Crew / Guest / Press / Supplier),
  number of tickets, access level, entrance, contact details and notes. Search and filter the list,
  check people in straight from the table.
- **Check-in desk**: a fast, phone-friendly screen. Type a name, press Enter when one match is
  left, and it's checked in. Shows access level, tickets and what to hand out. Undo is one tap.
- **Setup** per event: access levels (with colour), entrances and spaces (dressing rooms etc.).
- **Hospitality**: coins, consumption cards and vouchers. Allocate per person on an accreditation;
  totals scale with the number of tickets and can be marked as issued. The event overview shows
  how much of each item to prepare.
- **Riders** per accreditation.
- **CSV import/export** (Excel-friendly) and a **printable guest list** as a paper fallback.
- Light and dark mode, no external CDNs or Node build: it keeps working on flaky venue wifi.

## Running locally

```bash
cd website
python3 -m pip install -r requirements.txt
python3 manage.py migrate
python3 manage.py createsuperuser
python3 manage.py runserver
```

Then open http://127.0.0.1:8000 and sign in. Every page requires a login; staff users also see a
link to the Django admin.

```bash
python3 manage.py test
```

## Configuration

Settings are read from environment variables so the same code runs in production:

| Variable | Default | |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | insecure dev key | **Set this in production.** |
| `DJANGO_DEBUG` | `1` | Set to `0` in production. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma separated. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | *(empty)* | e.g. `https://accr.example.nl` |
| `DJANGO_DB_PATH` | `website/db.sqlite3` | SQLite database file. |

For production, run `python3 manage.py collectstatic` and serve `website/staticfiles/`.

## CSV import format

Header row required; comma, semicolon and tab separated files all work. Only `name` is required:

```
name,organisation,type,tickets,access_level,entrance,email,phone,notes
Eva Vrijdag,Band X,Artist,3,Goud,Backstage,,,
```

`access_level` and `entrance` must match names set up for the event (case-insensitive).
An exported CSV can be imported again, e.g. into next year's event.
