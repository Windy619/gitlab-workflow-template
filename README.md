# GitLab Workflow Template

Base GitLab standardisée à appliquer sur n'importe quel nouveau projet : labels, board Kanban, milestones et templates d'issue et de merge request cohérents entre eux.

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
- Des sprints datés, créés à la demande avec `--new-sprint`, au même niveau.

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
| `--new-sprint` | Titre d'un milestone de sprint à créer (optionnel) |
| `--sprint-start` | Date de début du sprint au format `YYYY-MM-DD`, obligatoire avec `--new-sprint` |
| `--sprint-weeks` | Durée du sprint en semaines (défaut : 2) |

Exemple avec un nouveau sprint :

```bash
python setup_gitlab_template.py --project-id 42 --group-id 51 --new-sprint "Sprint 2" --sprint-start 2026-10-07
```

### Relancer le script

Le script peut être relancé sans risque :

- les labels et le milestone `Backlog` déjà présents sont conservés, jamais recréés ;
- les colonnes du board sont supprimées puis recréées dans l'ordre du workflow ;
- une protection de branche ou de tag déjà conforme est conservée, une protection plus souple est recréée au niveau attendu.

## Contribuer

La stratégie de branches, le versionnement et le format des commits sont décrits dans [CONTRIBUTING.md](CONTRIBUTING.md).
