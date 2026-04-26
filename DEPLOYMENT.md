# Déploiement Edito — VPS Ubuntu 24.04

## Prérequis serveur

- Ubuntu 24.04 LTS
- Python 3.13+
- PostgreSQL 16+
- nginx
- certbot (Let's Encrypt)
- Dépendances système WeasyPrint : `libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b fonts-liberation`

```bash
sudo apt update && sudo apt install -y python3.13 python3.13-venv python3-pip \
    postgresql postgresql-contrib nginx certbot python3-certbot-nginx \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b fonts-liberation
```

## Variables d'environnement

Copier `.env.example` vers `/etc/edito/edito.env` (ou `/home/edito/.env`) et compléter :

```bash
SECRET_KEY=<générer avec : python -c "import secrets; print(secrets.token_urlsafe(50))">
DEBUG=False
ALLOWED_HOSTS=votre-domaine.fr,www.votre-domaine.fr
DJANGO_SETTINGS_MODULE=config.settings.production

DB_NAME=edito
DB_USER=edito
DB_PASSWORD=<mot de passe fort>
DB_HOST=localhost
DB_PORT=5432

STATIC_ROOT=/var/www/edito/staticfiles
MEDIA_ROOT=/var/www/edito/media
LOG_FILE=/var/log/edito/edito.log

# Email SMTP
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=contact@votre-domaine.fr
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@votre-domaine.fr
```

## Setup initial

```bash
# 1. Utilisateur système dédié
sudo useradd -m -s /bin/bash edito

# 2. Base de données
sudo -u postgres psql -c "CREATE USER edito WITH PASSWORD 'xxx';"
sudo -u postgres psql -c "CREATE DATABASE edito OWNER edito;"

# 3. Dossiers
sudo mkdir -p /var/www/edito/{staticfiles,media} /var/log/edito
sudo chown -R edito:edito /var/www/edito /var/log/edito

# 4. Clone et virtualenv
sudo -u edito git clone <repo> /home/edito/edito
cd /home/edito/edito
sudo -u edito python3.13 -m venv .venv
sudo -u edito .venv/bin/pip install -r requirements/production.txt

# 5. Fichier .env
sudo -u edito cp .env.example /home/edito/edito/.env
# Éditer .env avec les valeurs réelles

# 6. Migrations et collectstatic
sudo -u edito .venv/bin/python manage.py migrate
sudo -u edito .venv/bin/python manage.py collectstatic --noinput
sudo -u edito .venv/bin/python manage.py createsuperuser

# 7. Vérification
sudo -u edito DJANGO_SETTINGS_MODULE=config.settings.production \
    .venv/bin/python manage.py check --deploy
```

## Configuration gunicorn (systemd)

`/etc/systemd/system/edito.service` :

```ini
[Unit]
Description=Edito gunicorn daemon
After=network.target

[Service]
User=edito
Group=edito
WorkingDirectory=/home/edito/edito
EnvironmentFile=/home/edito/edito/.env
ExecStart=/home/edito/edito/.venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/run/edito.sock \
    --access-logfile /var/log/edito/access.log \
    --error-logfile /var/log/edito/gunicorn.log \
    config.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now edito
```

## Configuration nginx

`/etc/nginx/sites-available/edito` :

```nginx
server {
    listen 80;
    server_name votre-domaine.fr www.votre-domaine.fr;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name votre-domaine.fr www.votre-domaine.fr;

    ssl_certificate     /etc/letsencrypt/live/votre-domaine.fr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/votre-domaine.fr/privkey.pem;

    client_max_body_size 20M;

    location /static/ {
        alias /var/www/edito/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /var/www/edito/media/;
    }

    location / {
        proxy_pass http://unix:/run/edito.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/edito /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## HTTPS — certbot

```bash
sudo certbot --nginx -d votre-domaine.fr -d www.votre-domaine.fr
```

Le renouvellement automatique est configuré par certbot via un timer systemd.

## Procédure de mise à jour

```bash
cd /home/edito/edito
sudo -u edito git pull
sudo -u edito .venv/bin/pip install -r requirements/production.txt
sudo -u edito .venv/bin/python manage.py migrate
sudo -u edito .venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart edito
```

## Sauvegarde

> TODO (session ultérieure) — stratégie Backblaze B2 via script cron côté serveur.

Points à couvrir :
- Dump PostgreSQL quotidien (`pg_dump`) chiffré et envoyé vers B2
- Sauvegarde du dossier `MEDIA_ROOT`
- Rétention et rotation des sauvegardes

## TODO — Assets frontend

> À traiter dans une session dédiée avant la mise en production.

Les deux bibliothèques JS/CSS sont actuellement chargées depuis des CDN :

- **Alpine.js** — `https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js`
  → À vendoriser : télécharger `alpine.min.js` dans `static/js/` et utiliser `{% static %}`.

- **Tailwind CSS** — `https://cdn.tailwindcss.com` (play CDN, compile en navigateur)
  → Non adapté à la production. Nécessite un pipeline de build :
  1. Installer Node.js + npm sur le poste de développement
  2. `npm install tailwindcss @tailwindcss/cli`
  3. Configurer `tailwind.config.js` (content paths vers les templates)
  4. Générer `static/css/tailwind.css` à chaque déploiement
  5. Référencer avec `{% static 'css/tailwind.css' %}`

En attendant, le CDN play Tailwind fonctionne mais impose une dépendance réseau
et une latence de compilation au premier rendu.
