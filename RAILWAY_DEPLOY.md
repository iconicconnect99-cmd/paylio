# Deploy Paylio on Railway with Supabase

## Connect the project

1. Create a Railway project and deploy the Paylio GitHub repository.
2. In the Railway service variables, set the environment variables listed below.
3. Generate a Railway public domain for the service. Railway provides
   `RAILWAY_PUBLIC_DOMAIN`, which Django uses for allowed hosts and CSRF checks.
4. Deploy. Railway builds the `Dockerfile`, which collects static files and
   applies Django migrations before starting Gunicorn.

## Required variables

- `SECRET_KEY`: a unique, randomly generated Django secret.
- `DEBUG`: `False`.
- `DATABASE_URL`: the PostgreSQL connection URI for the existing Supabase
  database, including `sslmode=require`. Use the connection details in the
  Supabase dashboard; the Supabase project API URL and publishable key are not
  database credentials.
- `SUPABASE_URL`: `https://wybkkjmtmdyjipmdufdj.supabase.co`.
- `SUPABASE_ANON_KEY`: the Supabase publishable key used by this app's auth
  integration.

Set secrets in Railway's variable manager, not in source control. Do not add a
Railway PostgreSQL database if Supabase is to remain the database.

## Existing Supabase data

The deployment runs `manage.py migrate --noinput`. Django applies migrations
that are not recorded in `django_migrations`; it does not drop or recreate
existing tables. Before the first production deploy, confirm the Supabase
database URI targets the intended project and take a database backup. If
Supabase contains tables created outside Django's migration history, inspect
the migration state and schema compatibility before deployment.

## After deployment

Open the generated Railway domain and verify the homepage, sign-in, static
files, and admin portal. Set `ALLOWED_HOSTS` only if additional hostnames are
needed. Set `CSRF_TRUSTED_ORIGINS` to a comma-separated list of full origins
for any additional HTTPS domains.
