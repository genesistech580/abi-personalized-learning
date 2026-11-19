# AI-Powered Personalized Learning System

This Django 5.2 starter includes username-based sign-in, a role-specific dashboard, and user management in Django administration. The `courses`, `assessments`, and `recommendations` apps are registered scaffolds for future work. This version uses SQLite for local development.

## Set up in VS Code on Windows 11

1. Install Python 3.11 and the Microsoft Python extension for VS Code.
2. Open this project folder in VS Code and open a PowerShell terminal from **Terminal → New Terminal**.
3. Run these commands from the folder containing `manage.py`.

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe manage.py migrate
   .\.venv\Scripts\python.exe manage.py createsuperuser
   .\.venv\Scripts\python.exe manage.py runserver
   ```

   The commands use the virtual environment directly, so PowerShell activation is optional. In VS Code, run **Python: Select Interpreter** from the Command Palette and select `.venv\Scripts\python.exe`.

4. Open [the dashboard](http://127.0.0.1:8000/) and sign in with your superuser credentials. Open [Django administration](http://127.0.0.1:8000/admin/) to manage users.

## Try the three roles

- **Student** is the default role for a new user.
- **Lecturer** can be selected when creating or editing a user in Django administration.
- **Administrator** is assigned automatically by `createsuperuser`. Django independently controls access to its administration site through staff status and permissions.

In Django administration, choose **Users → Add user** to create Student and Lecturer accounts with passwords. Leave staff and superuser permissions disabled for these accounts. Sign out of the dashboard and sign in as each user to see its role-specific view.

The initial migration creates `accounts.User`. Run `manage.py makemigrations` after future model changes, then run `manage.py migrate` to apply them. [Django 5.2 custom user documentation](https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#substituting-a-custom-user-model)
