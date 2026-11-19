# GitLab Workflow Template

Base GitLab standardisée à appliquer sur n'importe quel nouveau projet : labels, board Kanban, milestones, templates d'issue et de merge request, et templates CI communs, cohérents entre eux.

Le script [`setup_gitlab_template.py`](setup_gitlab_template.py) déploie la configuration via l'API GitLab, sans passer par l'import/export de projet.

## Contenu

### Labels

Une taxonomie en quatre axes, créée au niveau du **groupe** et donc héritée par tous ses projets. Sans `--group-id`, elle est créée au niveau du **projet**.

| Axe | Préfixe | Exemples |
|---|---|---|
| Domaine | `[D]` | `[D] 🖥️ Back`, `[D] 🖼️ Front`, `[D] 🏗️ INFRA`, `[D] 🔁 CI/CD` |
| Priorité | `[P]` | `[P] 🔴 P1 · Critical` à `[P] 🟢 P4 · Low` |
| Type | `[T]` | `[T] ✨ Feature`, `[T] 🐛 Bug`, `[T] ♻️ Refactor`, `[T] 🔧 Chore` |
| Workflow | `[W]` | `[W] 📋 Backlog` à `[W] ✅ Done` (colonnes du board) |

### Board Kanban

Créé sur chaque **projet**, avec une colonne par label `[W]`, dans l'ordre du workflow :

| Colonne | Limite WIP |
|---|---|
| 📋 Backlog | |
| 📌 To Do | |
| ⚙️ En cours | 3 |
| 🚫 Bloqué | |
| 👀 En review | 2 |
| 🧪 En test | 2 |
| 🚀 À déployer en Pré-production | |
| 🟡 En Pré-production | |
| 🚢 À déployer en Production | |
| ✅ Done | |

> [!NOTE]
> Les limites WIP demandent l'offre **GitLab Premium**. Sur l'offre Free, le script affiche un avertissement et crée le board sans limites.

### Milestones

- `Backlog`, créé au niveau du groupe (ou du projet sans `--group-id`).
- Une version (`v1.2.0`) par batch livré, créée à la main sur le **projet** : une version a un rythme propre à chaque projet, contrairement au `Backlog`.

Le flux est continu (Kanban, limites WIP) : il n'y a pas de sprint. Une issue sans version cible reste dans `Backlog`.

### Protections du projet

Appliquées sur chaque **projet** :

| Élément | Réglage |
|---|---|
| Branches `main`, `staging`, `develop` | Push interdit, merge réservé aux Maintainers, force push interdit |
| Tags `v*` | Création réservée aux Maintainers (un tag déclenche la mise en production) |
| Merge | Pipeline vert et discussions résolues exigés, branche source supprimée après merge |

> [!NOTE]
> Le script ne change pas la branche par défaut. Les approbations de MR et les CODEOWNERS demandent l'offre Premium et ne sont pas configurés.

### Templates d'issue et de merge request

- [`issue_templates/Default.md`](issue_templates/Default.md)
- [`merge_request_templates/Default.md`](merge_request_templates/Default.md)

Le script ne les déploie pas. Copiez-les dans le projet cible, dans `.gitlab/issue_templates/` et `.gitlab/merge_request_templates/`, pour que GitLab les propose.

Ce dépôt applique lui-même ses templates : `.gitlab/` en contient une copie versionnée. Les fichiers de `issue_templates/` et `merge_request_templates/` restent la source, et toute modification s'y fait en même temps que dans `.gitlab/`.

### Templates CI

Des morceaux de pipeline communs, dans [`ci/`](ci/), que chaque projet inclut au lieu de recopier ses jobs. Le dépôt est public : l'inclusion fonctionne depuis gitlab.com comme depuis une autre instance, ce que les composants CI/CD (limités à leur instance) ne permettent pas.

| Template | Jobs | Inputs |
|---|---|---|
| [`base.yml`](ci/base.yml) | aucun : étapes `build` `test` `deploy` `rollback`, déclencheurs, annulation des pipelines dépassés | |
| [`php-quality.yml`](ci/php-quality.yml) | `test_pint`, `test_phpstan` (si `phpstan.neon` existe), `test_composer_audit` | `php_version` |
| [`php-test.yml`](ci/php-test.yml) | `test_phpunit`, renommable | `job`, `runner`, `testsuite`, `image`, `php_version`, `php_extensions`, `apt_packages`, `services` |
| [`node-build.yml`](ci/node-build.yml) | `build_assets` | `node_version`, `build_script`, `artifact_path` |
| [`node-quality.yml`](ci/node-quality.yml) | `test_lint`, `test_typecheck` (si `tsconfig.json` existe) | `node_version`, `lint_script`, `typecheck_script` |
| [`python-quality.yml`](ci/python-quality.yml) | `test_ruff`, `test_mypy`, `test_pytest`, avec uv | `python_version`, `uv_version`, `working_dir` |

Chaque input a une valeur par défaut, décrite dans l'en-tête `spec` du template.

**Déclencheurs** (`base.yml`) : une branche de travail passe par le pipeline de sa MR, `develop`, `staging` et `main` ont toujours leur pipeline de branche, même quand une MR de batch part d'elles, et un tag `vX.Y.Z` lance le sien. Une branche poussée sans MR n'a pas de pipeline : la MR draft s'ouvre au démarrage du ticket.

**Démarrer un projet** : copier le starter de sa stack en `.gitlab-ci.yml`, puis ajouter les jobs propres au projet (déploiement, tests spécifiques) sous les `include`.

| Stack | Starter |
|---|---|
| Laravel | [`ci/starters/laravel.yml`](ci/starters/laravel.yml) |
| Node.js | [`ci/starters/node.yml`](ci/starters/node.yml) |
| Python | [`ci/starters/python.yml`](ci/starters/python.yml) |

**Adapter un job** : redéclarer le job dans le `.gitlab-ci.yml` du projet. GitLab fusionne les deux définitions, comme le fait le starter Laravel pour les variables de la base de test. Pour une seconde suite de tests, inclure `php-test.yml` une seconde fois avec un autre `job`.

**Monter de version** : l'URL d'inclusion est épinglée sur un tag (`-/raw/v1.2.0/ci/...`), jamais sur une branche, pour qu'une modification ici ne change pas un pipeline sans que le projet l'ait décidé. Changer le tag dans les URL du projet suffit. Un changement cassant pour les projets (input renommé ou retiré, job renommé) est une version majeure.

Les jobs de déploiement appartiennent encore à chaque projet et doivent poser `interruptible: false` : `base.yml` rend tous les jobs interruptibles par défaut.

## Prérequis

- Python 3.7 ou plus récent
- Un token d'accès personnel GitLab avec le scope `api`
- Les droits de gestion des labels et milestones sur le groupe (ou sur le projet sans `--group-id`), et du board, des branches protégées et des réglages sur le projet (rôle Maintainer)

```bash
pip install -r requirements.txt
```

## Utilisation

### Variables d'environnement

| Variable | Obligatoire | Défaut | Rôle |
|---|---|---|---|
| `GITLAB_TOKEN` | Oui | | Token d'accès personnel, scope `api` |
| `GITLAB_URL` | Non | `https://gitlab.com` | URL de l'instance GitLab |

Bash :

```bash
export GITLAB_TOKEN="glpat-xxxxxxxxxxxx"
export GITLAB_URL="https://gitlab.com"
```

PowerShell :

```powershell
$env:GITLAB_TOKEN = "glpat-xxxxxxxxxxxx"
$env:GITLAB_URL = "https://gitlab.com"
```

### Lancement

```bash
python setup_gitlab_template.py --project-id 42 --group-id 51
```

Sans `--project-id`, le script demande l'identifiant du projet de manière interactive.

Pour un projet hors groupe (namespace personnel), omettez `--group-id` : labels et milestone sont alors créés sur le projet.

```bash
python setup_gitlab_template.py --project-id 42
```

### Options

| Option | Description |
|---|---|
| `--project-id` | ID du projet qui reçoit le board |
| `--group-id` | ID du groupe qui porte les labels et milestones (optionnel : sans lui, ils sont créés sur le projet) |

### Relancer le script

Le script peut être relancé sans risque :

- les labels et le milestone `Backlog` déjà présents sont conservés, jamais recréés ; seule la description d'un label existant est réalignée sur celle du script ;
- les colonnes du board sont supprimées puis recréées dans l'ordre du workflow ;
- une protection de branche ou de tag déjà conforme est conservée, une protection plus souple est recréée au niveau attendu.

## Contribuer

La stratégie de branches, le versionnement et le format des commits sont décrits dans [CONTRIBUTING.md](CONTRIBUTING.md).

La CI GitLab vérifie le script à chaque push (syntaxe, analyse statique, tests sous Python 3.7 et 3.12) et les templates CI (inputs déclarés et utilisés, nommage des jobs, schéma GitLab, starters épinglés sur une même version). Pour lancer les tests en local :

```bash
python -m unittest discover -s tests -v
```
