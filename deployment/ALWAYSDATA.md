# Alwaysdata testing deployment

Use a Python 3.11 WSGI site. Replace ACCOUNT with your Alwaysdata account name.

Upload the project to /home/ACCOUNT/abi-learning. Exclude .venv, __pycache__, .env, and the nested duplicate project directory. Keep the existing local database and photos on your computer. Start the hosted evaluation with a new database unless existing records have been explicitly chosen for transfer.

In Alwaysdata Web > Sites, use:

- Application path /home/ACCOUNT/abi-learning/deployment/wsgi.py
- Working directory /home/ACCOUNT/abi-learning
- Virtual environment /home/ACCOUNT/abi-learning/.venv
- Address ACCOUNT.alwaysdata.net
- Python 3.11
- Force HTTPS

Configure DJANGO_SECRET_KEY with a fresh random secret of at least 50 characters, and DJANGO_ALLOWED_HOSTS with the hostname. Set the same values in the SSH session before running management commands. Never commit secrets.

Run using Alwaysdata SSH:

    cd ~/abi-learning
    python -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python manage.py migrate --settings=config.hosting
    .venv/bin/python manage.py collectstatic --noinput --settings=config.hosting
    .venv/bin/python manage.py createsuperuser --settings=config.hosting
    .venv/bin/python manage.py check --deploy --settings=config.hosting

Add an Alwaysdata Static files site for ACCOUNT.alwaysdata.net/static/ with root /home/ACCOUNT/abi-learning/staticfiles. Profile photos are delivered through Django authentication and do not need a public media mapping.

SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD and SMTP_FROM_EMAIL enable reset email delivery. OPENAI_API_KEY enables chat and requires available API quota. Keep them in the site's environment settings.

Verify sign-in, CSS and watermark, enrollment, quiz submission, profile photos, password reset, role access and sign-out over HTTPS before inviting evaluators. Back up the hosted database and media before updates. Do not overwrite the hosted database on later uploads.
