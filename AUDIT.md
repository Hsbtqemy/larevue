# Audit de code et de sécurité — général

Date : 2026-04-27
Tests : 604 verts.
Sessions A et B de correctifs déjà appliquées.

---

## Résumé exécutif

Le projet est **sain**. Aucune faille critique n'a été trouvée. La sécurité
côté HTTP (CSRF, ownership cross-revue, uploads, session) est solide. Les
patterns introduits lors des sessions A et B sont correctement appliqués.

Les points qui restent sont de trois ordres :

1. **Performance admin** : plusieurs `ModelAdmin` génèrent des N+1 silencieux
   faute de `list_select_related`. Mineur sur petits volumes, visible en
   production dès que les tables grossissent.

2. **Un bug de rendu potentiel** dans le filtre templatetag `to_json` :
   `mark_safe(json.dumps(...))` injecte des guillemets droits dans un attribut
   HTML entre guillemets, ce qui peut casser l'évaluation Alpine des `inlineEdit`
   avec des options sélect. À vérifier visuellement en priorité.

3. **Administration incomplète** : `JournalDocument` absent de l'admin,
   `InternalNoteAdmin` aveugle aux notes attachées à un numéro (vs un article).

---

## Axe 1 — Code

### 1.1 `to_json` filtre — guillemets non échappés en attribut HTML

**Localisation** : `apps/core/templatetags/edito.py:148`

```python
def to_json(value):
    return mark_safe(json.dumps(value))
```

**Problème** : `json.dumps` produit des guillemets droits (`"`) autour des
chaînes. Ce résultat est inséré dans l'attribut `x-data` entre guillemets
doubles :

```html
<span x-data="inlineEdit('...', '...', 'select', {{ options|to_json }})">
```

Le HTML parsé par le navigateur voit `"` à l'intérieur d'un attribut
délimité par `"` — il coupe l'attribut au premier guillemet interne. Alpine.js
reçoit donc un `x-data` tronqué. Le `inlineEdit` avec `type="select"` et des
options non vides est vraisemblablement rendu inactif ou bugué.

**Fix** : HTML-échapper la sortie JSON pour que `"` devienne `&quot;`
(décodé proprement par le navigateur avant évaluation Alpine).

```python
from django.utils.html import escape, mark_safe
return mark_safe(escape(json.dumps(value, ensure_ascii=False)))
```

**Effort** : 15 min. **À vérifier manuellement** en ouvrant un champ
`article_type` en édition inline.

---

### 1.2 N+1 dans `Issue.progress`

**Localisation** : `apps/issues/models.py:139-145`

```python
@property
def progress(self) -> int:
    total = self.articles.count()        # requête 1
    validated = self.articles.filter(state="validated").count()  # requête 2
    return int((validated / total) * 100)
```

**Usage** : uniquement dans `IssueAdmin.get_progress()` (ligne 35) via
`list_display`. Pour N numéros en admin → 2N requêtes supplémentaires.

**Note** : le dashboard (`journals/views.py:98-110`) calcule correctement
le même résultat via `.annotate(validated_count=..., article_count=...)` —
la propriété n'est pas utilisée là.

**Fix** : ajouter `list_select_related` et une annotation dans `IssueAdmin`,
ou remplacer `get_progress` par une requête annotée dans `get_queryset`.

**Effort** : 30 min.

---

### 1.3 N+1 dans les admin — `list_display` avec FK sans `list_select_related`

Aucun `ModelAdmin` ne définit `list_select_related`. Plusieurs ont des FK
dans `list_display` qui déclenchent une requête par ligne.

| Admin | FK dans list_display | Requêtes par ligne |
|---|---|---|
| `IssueAdmin` | `journal` | 1 |
| `ArticleAdmin` | `issue` | 1 |
| `IssueDocumentAdmin` | `issue`, `uploaded_by` | 2 |
| `ReviewRequestAdmin` | `article` | 1 (+ `article.issue` si affiché) |
| `InternalNoteAdmin` | `article`, `author` | 2 |

**Fix** : ajouter `list_select_related = True` (ou une liste précise) à
chaque `ModelAdmin` concerné.

**Effort** : 15 min total.

---

### 1.4 `InternalNoteAdmin` aveugle aux notes de numéro

**Localisation** : `apps/articles/admin.py:52-57`

```python
class InternalNoteAdmin(admin.ModelAdmin):
    list_display = ("article", "author", "is_automatic", "created_at")
    list_filter = ("is_automatic", "article__issue__journal")
    search_fields = ("article__title", "content")
    autocomplete_fields = ["article"]
```

`InternalNote` a deux FK exclusifs : `article` (nullable) et `issue`
(nullable). Les notes créées via `IssueTransitionView` et
`IssueDocumentCreateView` ont `article=NULL` — elles apparaissent dans
l'admin avec `article = None`, sont invisibles au `list_filter` par
journal et ne sont pas trouvées par `search_fields`.

**Fix** :
- Séparer en deux `InlineAdmin` (un dans `ArticleAdmin`, un dans
  `IssueAdmin`) plutôt qu'un `ModelAdmin` standalone, ou
- Ajouter `issue` dans `list_display`, `autocomplete_fields`, et gérer
  les deux `list_filter` / `search_fields` en parallèle.

**Effort** : 30 min.

---

### 1.5 `_confirm_delete.html` — `delete_url` sans `|escapejs`

**Localisation** : `templates/partials/_confirm_delete.html:2-4`

```html
<div x-data="confirmDelete('{{ delete_url }}', '{{ require_typing|escapejs }}')">
<div x-data="confirmDelete('{{ delete_url }}')">
```

`delete_url` vient d'un `{% url ... %}` et ne contient en pratique que
`[a-z0-9/_-]`. Mais l'absence de `|escapejs` est incohérente avec
`_image_upload.html` (qui utilise `|escapejs` sur `current_url`), et avec
tous les autres `x-data` du projet.

Si un slug venait à contenir un apostrophe ou une quote (par exemple via
un import ou une manipulation directe en DB), la chaîne JS serait cassée.

**Fix** : `{{ delete_url|escapejs }}` aux deux endroits.

**Effort** : 5 min.

---

### 1.6 Architecture modale — décision en attente (audit précédent, item C)

`_confirm_delete.html` et `_transition_confirm_modal.html` dupliquent la
structure `x-teleport / modal-backdrop / modal` du partial générique
`_modal.html`. Le générique utilise `{% block %}` (héritage), incompatible
avec `{% include %}`.

**Décision en attente** : slot-based (passer le body comme variable),
composant Alpine partagé, ou duplication assumée avec commentaire.

**Effort** : 2h+ (architecture à trancher avant de coder).

---

### 1.7 `RunPython.noop` sur deux migrations de données

| Migration | Reverse |
|---|---|
| `issues/0005_issue_backfill_archive_dates.py:24` | `noop` |
| `reviews/0004_reviewrequest_migrate_expected_to_sent.py:15` | `noop` |

En cas de rollback, la migration est silencieusement ignorée et les données
restent dans l'état post-migration. Non bloquant (les deux migrations
concernent des backfills one-shot), mais à documenter.

**Fix** : remplacer `noop` par une fonction de rollback explicite, ou
ajouter un commentaire `# not reversible — one-shot backfill`.

**Effort** : 10 min.

---

### 1.8 `Article.state`, `Issue.state`, `ReviewRequest.state` — pas de `db_index`

Ces champs `CharField` sont utilisés dans des filtres fréquents
(`filter(state__in=...)`, `filter(state="validated")`). Django n'indexe
pas automatiquement les `CharField` non-FK.

Sur les volumes actuels (quelques centaines de lignes), cela n'a pas
d'impact. À anticiper si le volume augmente.

**Fix** : ajouter `db_index=True` ou un index dans `Meta.indexes`.

**Effort** : 15 min + migration.

---

## Axe 2 — Administration

### 2.1 `JournalDocument` absent de l'admin

**Localisation** : `apps/journals/admin.py`

`JournalDocument` (modèle complet avec Meta, `__str__`, stockage UUID)
n'est pas enregistré dans l'admin. Les documents d'une revue ne peuvent
être gérés qu'via l'interface applicative.

**Fix** :

```python
@admin.register(JournalDocument)
class JournalDocumentAdmin(admin.ModelAdmin):
    list_display = ("name", "journal", "uploaded_by", "uploaded_at")
    list_filter = ("journal",)
    search_fields = ("name", "journal__name")
    readonly_fields = ("uploaded_at", "uploaded_by")
    list_select_related = ("journal", "uploaded_by")
```

**Effort** : 10 min.

---

## Axe 3 — Sécurité

### 3.1 Synthèse des points sécurité — tous couverts

| Vérification | Statut |
|---|---|
| Authentification sur toutes les vues | ✓ |
| Isolation cross-revue (ownership) | ✓ |
| CSRF sur tous les POST | ✓ |
| Upload : taille limitée, UUID, download protégé | ✓ |
| Cookies sécurisés en production (HTTPS, HSTS, preload) | ✓ |
| `X_FRAME_OPTIONS = "DENY"` | ✓ |
| `SECURE_CONTENT_TYPE_NOSNIFF = True` | ✓ |
| Inscription publique désactivée (`NoSignupAccountAdapter`) | ✓ |
| Rate limiting login (`allauth` défaut : 10/min/IP) | ✓ par défaut |
| `SECRET_KEY` et credentials via `decouple` | ✓ |
| `.gitignore` protège `.env` et media | ✓ |
| Soft delete ne laisse pas fuir d'objets dans les FK inverses | ✓ vérifié |
| `mark_safe` / `to_json` en contexte `<script>` | ✓ (uniquement attributs Alpine) |

---

### 3.2 `NoSignupAccountAdapter.get_client_ip()` — `PermissionDenied` sans nginx

**Localisation** : `apps/accounts/adapters.py:13-23`

```python
def get_client_ip(self, request):
    ip = request.META.get("HTTP_X_REAL_IP")
    if not ip:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = forwarded.split(",")[0].strip()
    if not ip:
        ip = request.META.get("REMOTE_ADDR", "")
    if not ip:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Unable to determine client IP address")
    return ip
```

Allauth appelle `get_client_ip` pour le rate limiting à chaque tentative
de login. Si le serveur est accédé directement (sans nginx, ex. debug
via `runserver` ou exposé directement), `REMOTE_ADDR` est vide sur certaines
configurations, ce qui lève `PermissionDenied` à chaque login — la page
de connexion devient inaccessible.

**Contexte** : production avec nginx → `HTTP_X_REAL_IP` est toujours
présent. Développement → utilise `ACCOUNT_EMAIL_VERIFICATION = "none"` et
`runserver` (REMOTE_ADDR non vide). Risque réel uniquement en cas de
déploiement mal configuré.

**Fix** : remplacer le `raise PermissionDenied` par `return ""` (retourner
une chaîne vide est acceptable pour allauth si le rate limiting per-IP ne
peut pas s'appliquer).

**Effort** : 5 min.

---

### 3.3 `CSRF_TRUSTED_ORIGINS` par défaut vide

**Localisation** : `config/settings/production.py:8`

```python
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", cast=Csv(), default="")
```

Si `CSRF_TRUSTED_ORIGINS` n'est pas défini dans `.env` production, les
requêtes HTMX via `https://` échoueront avec 403 CSRF (Django 4+ vérifie
l'origin pour les connexions HTTPS). À documenter dans le guide de déploiement.

**Effort** : 0 min (configuration, pas de code).

---

## Axe 4 — Dépendances

### 4.1 État des dépendances

| Package | Version | Remarque |
|---|---|---|
| Django | 6.0.4 | Récent ✓ |
| django-allauth | 65.16.1 | Récent ✓ |
| django-fsm-2 | 4.2.4 | Récent ✓ |
| psycopg | 3.3.3 (binary) | Récent ✓ |
| Pillow | 12.2.0 | Récent ✓ |
| weasyprint | 68.1 | Récent ✓ |
| gunicorn | 25.3.0 | Récent ✓ |
| whitenoise | 6.12.0 | Récent ✓ |

Aucun package en fin de vie ou avec advisory connu. Recommandé : passer
`pip-audit` en CI.

---

## Synthèse priorisée

### Critique
_Aucun._

---

### Important

| # | Item | Effort |
|---|---|---|
| **1.1** | `to_json` casse les `inlineEdit` sélect — vérifier visuellement, puis fixer `mark_safe(escape(json.dumps(...)))` | 15 min |
| **1.2** | `Issue.progress` N+1 en admin — annoter dans `IssueAdmin.get_queryset()` | 30 min |
| **1.3** | `list_select_related` manquant sur 5 `ModelAdmin` | 15 min |
| **2.1** | `JournalDocument` absent de l'admin | 10 min |
| **1.4** | `InternalNoteAdmin` aveugle aux notes de numéro | 30 min |

---

### Mineur

| # | Item | Effort |
|---|---|---|
| **1.5** | `delete_url` sans `\|escapejs` dans `_confirm_delete.html` | 5 min |
| **3.2** | `get_client_ip()` lève `PermissionDenied` si pas de nginx | 5 min |
| **1.7** | Documenter les `RunPython.noop` comme "non reversible" | 10 min |
| **1.8** | `db_index` sur les champs `state` | 15 min + migration |
| **3.3** | Documenter `CSRF_TRUSTED_ORIGINS` dans le guide de déploiement | — |

---

### Décision architecturale en attente

| # | Item | Effort |
|---|---|---|
| **1.6** | Architecture modale : slot-based vs duplication assumée | 2h+ |
