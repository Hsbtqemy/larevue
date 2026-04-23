# Outil de gestion éditoriale

Webapp Django de suivi de production pour revues scientifiques associatives.
Permet à des équipes éditoriales de piloter numéros thématiques et articles,
du projet de numéro jusqu'à la publication.

## Stack technique

- **Backend** : Python 3.13, Django 6.0, PostgreSQL
- **Frontend** : HTMX, Alpine.js, Tailwind CSS (CDN pour l'instant — TODO: migrer vers django-tailwind)
- **Workflow** : django-fsm-2
- **Auth** : django-allauth (email comme identifiant)

## Prérequis

- Python 3.12+
- PostgreSQL 14+
- `make`

## Installation

```bash
# 1. Cloner et entrer dans le dossier
git clone https://github.com/Hsbtqemy/larevue.git editorial-tool
cd editorial-tool

# 2. Créer l'environnement et installer les dépendances
make install

# 3. Configurer les variables d'environnement
cp .env.example .env
# Éditer .env : SECRET_KEY, DB_NAME, DB_USER, DB_PASSWORD...

# 4. Créer la base de données PostgreSQL
createdb editorial_tool

# 5. Appliquer les migrations
make migrate

# 6. Créer un superutilisateur
make superuser

# 7. Lancer le serveur
make run
```

## Commandes utiles

| Commande            | Description                             |
|---------------------|-----------------------------------------|
| `make install`      | Crée le venv et installe les dépendances |
| `make run`          | Lance le serveur de développement       |
| `make migrate`      | Applique les migrations                 |
| `make makemigrations` | Génère les migrations                 |
| `make test`         | Lance la suite de tests                 |
| `make lint`         | Vérifie le code avec ruff               |
| `make format`       | Formate le code avec ruff               |
| `make shell`        | Lance le shell Django enrichi           |
| `make superuser`    | Crée un superutilisateur                |

## TODO

- [ ] Migrer Tailwind CSS du CDN vers `django-tailwind` (nécessite Node.js)
- [ ] Coder les vues utilisateur et templates
- [ ] Configurer Sentry en production (`requirements/production.txt`)
