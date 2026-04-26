# Déploiement Edito — VPS Ubuntu 24.04

Déployé sur VPS Infomaniak (Ubuntu 24.04 LTS, 2 vCPU, 4 Go RAM).
Chemins effectifs : `/home/edito/edito/`, venv dans `venv/` (pas `.venv`).

## Prérequis serveur

- Ubuntu 24.04 LTS
- Python 3.12+ (3.12.3 fourni par Ubuntu 24.04)
- Node.js 20 LTS+ (via NodeSource — apt fournit une version trop ancienne)
- PostgreSQL 16+
- nginx
- certbot (Let's Encrypt) — pour HTTPS, après l'ajout d'un domaine
- Dépendances système WeasyPrint : `libpango-1.0-0 libpangoft2-1.0-0`

```bash
sudo apt update && sudo apt upgrade -y

# Stack de base
sudo apt install -y python3-pip python3-venv python3-dev build-essential \
    libpq-dev git postgresql postgresql-contrib nginx \
    libpango-1.0-0 libpangoft2-1.0-0 fail2ban unattended-upgrades

# Node.js 20 LTS via NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

## Firewall

UFW + firewall réseau Infomaniak (deux couches indépendantes) :

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

**Important** : ouvrir aussi les ports 22 et 80 (puis 443) dans le firewall
réseau Infomaniak (Manager → VPS → Régler le Firewall). UFW seul ne suffit pas.

## Utilisateur dédié

```bash
sudo adduser --disabled-password --gecos "" edito
sudo usermod -aG www-data edito

# Donner accès à nginx au répertoire home (traverse le socket)
sudo chmod o+x /home/edito
```

## Base de données

```bash
# Générer un mot de passe fort
openssl rand -base64 32

# Créer la base et l'utilisateur (commandes séparées pour éviter le bug \c)
sudo -u postgres psql -c "CREATE DATABASE edito_prod;"
sudo -u postgres psql -c "CREATE USER edito_user WITH PASSWORD 'MOT_DE_PASSE';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE edito_prod TO edito_user;"
sudo -u postgres psql -c "ALTER DATABASE edito_prod OWNER TO edito_user;"
sudo -u postgres psql -d edito_prod -c "GRANT ALL ON SCHEMA public TO edito_user;"
```

> Note : ne pas utiliser `\c edito_prod` dans psql interactif — utiliser
> `psql -d edito_prod -c "..."` directement depuis le shell.

## Variables d'environnement

Créer `/home/edito/edito/.env` :

```bash
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=<python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=False
ALLOWED_HOSTS=83.228.221.204,localhost,127.0.0.1
HTTPS_ENABLED=False   # passer à True après certbot

DB_NAME=edito_prod
DB_USER=edito_user
DB_PASSWORD=<mot de passe généré>
DB_HOST=localhost
DB_PORT=5432

STATIC_ROOT=/home/edito/edito/staticfiles
MEDIA_ROOT=/home/edito/edito/media
LOG_FILE=/var/log/edito/edito.log

CSRF_TRUSTED_ORIGINS=http://83.228.221.204   # ajouter https://domaine.fr après certbot

# Email SMTP (configurer pour reset de mot de passe, etc.)
# EMAIL_HOST=smtp.example.com
# EMAIL_PORT=587
# EMAIL_HOST_USER=contact@domaine.fr
# EMAIL_HOST_PASSWORD=
# EMAIL_USE_TLS=True
# DEFAULT_FROM_EMAIL=noreply@domaine.fr
```

**Important** : `DJANGO_SETTINGS_MODULE` dans `.env` n'est pas lu par
`manage.py` (qui utilise `os.environ.setdefault`). Pour les commandes
manuelles, toujours exporter explicitement :

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
```

## Setup initial

```bash
# Se connecter en tant qu'edito
sudo su - edito

# Cloner le repo
git clone https://github.com/Hsbtqemy/larevue.git edito
cd edito

# Virtualenv et dépendances
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements/production.txt

# Créer les dossiers
mkdir -p staticfiles media

# Créer le .env (voir section Variables d'environnement)
nano .env

# Exporter le settings module pour les commandes manage.py
export DJANGO_SETTINGS_MODULE=config.settings.production

# Build Tailwind et collectstatic
npm install
npm run build:css
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser

exit  # retour à ubuntu
```

## Logs

```bash
sudo mkdir -p /var/log/edito
sudo chown edito:www-data /var/log/edito
```

## Configuration gunicorn (systemd)

`/etc/systemd/system/edito.service` :

```ini
[Unit]
Description=Gunicorn daemon for Edito
After=network.target

[Service]
User=edito
Group=www-data
WorkingDirectory=/home/edito/edito
EnvironmentFile=/home/edito/edito/.env
Environment=DJANGO_SETTINGS_MODULE=config.settings.production
ExecStart=/home/edito/edito/venv/bin/gunicorn \
          --workers 3 \
          --forwarded-allow-ips="*" \
          --bind unix:/home/edito/edito/edito.sock \
          --access-logfile /var/log/edito/access.log \
          --error-logfile /var/log/edito/error.log \
          config.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now edito
sudo systemctl status edito
```

## Configuration nginx

`/etc/nginx/sites-available/edito` :

```nginx
server {
    listen 80;
    server_name 83.228.221.204;

    client_max_body_size 25M;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        alias /home/edito/edito/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /home/edito/edito/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/edito/edito/edito.sock;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/edito /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

## HTTPS — certbot (après ajout du domaine)

1. Pointer le domaine sur `83.228.221.204` (DNS)
2. Mettre à jour `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` dans `.env`
3. Passer `HTTPS_ENABLED=True` dans `.env`
4. Lancer certbot :

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d domaine.fr -d www.domaine.fr
sudo systemctl restart edito
```

Le renouvellement automatique est configuré par certbot via un timer systemd.

## Commandes Django utiles (depuis ubuntu)

```bash
# Alias pratique à ajouter dans ~/.bashrc
alias edito-manage='sudo -u edito bash -c "cd /home/edito/edito && source venv/bin/activate && DJANGO_SETTINGS_MODULE=config.settings.production python manage.py"'

# Exemples
edito-manage migrate
edito-manage createsuperuser
edito-manage shell
```

## Procédure de mise à jour

```bash
sudo -u edito git -C /home/edito/edito pull
sudo -u edito bash -c "cd /home/edito/edito && source venv/bin/activate && pip install -r requirements/production.txt"
sudo -u edito bash -c "cd /home/edito/edito && npm install && npm run build:css"
sudo -u edito bash -c "cd /home/edito/edito && source venv/bin/activate && DJANGO_SETTINGS_MODULE=config.settings.production python manage.py migrate"
sudo -u edito bash -c "cd /home/edito/edito && source venv/bin/activate && DJANGO_SETTINGS_MODULE=config.settings.production python manage.py collectstatic --noinput"
sudo systemctl restart edito
```

## Logs utiles

```bash
sudo tail -f /var/log/edito/edito.log      # logs Django
sudo tail -f /var/log/edito/error.log      # logs gunicorn
sudo tail -f /var/log/edito/access.log     # accès HTTP
sudo tail -f /var/log/nginx/error.log      # erreurs nginx
sudo journalctl -u edito -f                # journal systemd
```

## Sauvegarde

> TODO (session ultérieure) — stratégie Backblaze B2 via script cron côté serveur.

Points à couvrir :
- Dump PostgreSQL quotidien (`pg_dump`) chiffré et envoyé vers B2
- Sauvegarde du dossier `MEDIA_ROOT`
- Rétention et rotation des sauvegardes
