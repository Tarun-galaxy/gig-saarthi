# Gig Saarthi — Dev Server Run Doc

## Reproduce artifacts
1. Copy `.env` from the main checkout if missing.
2. No `npm install` needed — this is a Django project.
3. Apply migrations: `python manage.py migrate`
4. Seed data: `python manage.py seed_data`

## Run the server
```
python manage.py runserver 8000
```

Default port: **8000**

## Detach (Windows)
Use PowerShell to start `python.exe` in background:
```powershell
Start-Process -FilePath 'python.exe' -ArgumentList 'manage.py','runserver','8000' -RedirectStandardOutput '<log>' -RedirectStandardError '<log>.err' -WindowStyle Hidden -PassThru
```
