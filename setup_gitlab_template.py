#!/usr/bin/env python3
"""
Initialise le template complet (labels + milestone Backlog + board) sur
GitLab via l'API :
  - Les labels [D]/[P]/[T]/[W] et le milestone "Backlog" sont créés au
    niveau du GROUPE -> hérités automatiquement par tous les projets de
    ce groupe, donc créés une seule fois par groupe (le script vérifie
    ce qui existe déjà et ne recrée rien en double).
    Sans --group-id (projet hors groupe), ils sont créés au niveau du PROJET.
  - Le board (listes + limites WIP) est propre à chaque PROJET -> recréé
    à chaque nouveau projet. Les limites WIP demandent l'offre Premium :
    sans elle, le script avertit et crée le board sans limites.
  - Le projet reçoit aussi ses protections : branches main/staging/develop
    (push interdit), tags v* (Maintainers) et réglages de merge.

Usage :
    export GITLAB_URL="https://gitlab.com"        # ou l'URL de ton instance
    export GITLAB_TOKEN="glpat-xxxxxxxxxxxx"       # token personnel, scope "api"
    python3 setup_gitlab_template.py --project-id 42 --group-id 51

    # projet sans groupe : labels et milestone créés au niveau du projet
    python3 setup_gitlab_template.py --project-id 42

Prérequis :
    pip install -r requirements.txt
"""

import argparse
import os
import sys
from urllib.parse import quote

import requests

# --- Labels [D] / [P] / [T] (domaine / priorité / type) ---
LABELS_DPT = [
    ("[D] 🎭 Animation", "#6699cc", "Animations front si traité comme domaine à part"),
    ("[D] 🏗️ INFRA", "#cd5b45", "Serveurs, Docker, hébergement, réseau"),
    ("[D] 📡 Observabilité", "#009966", "Logs, monitoring, alertes, métriques"),
    ("[D] 🔁 CI/CD", "#ed9121", "Pipelines GitLab, déploiement automatisé, scripts"),
    ("[D] 🖥️ Back", "#dc143c", "Laravel, API, base de données, logique métier"),
    ("[D] 🖼️ Front", "#ed9121", "Vue.js, Livewire, HTML/CSS, JS"),
    ("[P] 🔴 P1 · Critical", "#dc143c", "Bloquant, à traiter dans les heures qui suivent"),
    ("[P] 🟠 P2 · High", "#ed9121", "Important, à traiter avant les P3 et P4"),
    ("[P] 🟡 P3 · Medium", "#eee600", "Normal, à prendre dans l'ordre du backlog"),
    ("[P] 🟢 P4 · Low", "#009966", "Mineur, à faire si le temps le permet"),
    ("[T] ♻️ Refactor", "#ed9121", "Réécriture de code sans changement de comportement visible"),
    ("[T] ⚡ Fix Urgent", "#c21e56", "Correction urgente hors bug (config, data, env…)"),
    ("[T] ⚡ Performance", "#009966", "Optimisation requêtes SQL, cache, mémoire, temps de réponse"),
    ("[T] ✨ Feature", "#cc338b", "Nouvelle fonctionnalité à développer"),
    ("[T] ❓ Question", "#ed9121", "Discussion, clarification, décision à prendre avant de coder"),
    ("[T] 🎨 Design", "#8fbc8f", "Intégration HTML/CSS, composants UI, responsive"),
    ("[T] 🎬 Animation", "#9400d3", "Animations CSS/JS, transitions, effets visuels"),
    ("[T] 🏚️ Dette technique", "#6699cc", "Problème connu, à corriger sur le long terme"),
    ("[T] 🐛 Bug", "#dc143c", "Comportement incorrect ou inattendu, reproductible"),
    ("[T] 📈 Improvement", "#009966", "Amélioration d'une fonctionnalité existante"),
    ("[T] 🔧 Chore", "#607d8b", "Tâche de maintenance technique : dépendances, configuration, scripts, CI (sans changement de comportement ni bug)"),
]

# --- Labels [W] (colonnes du board), dans l'ordre du workflow ---
LABELS_W = [
    ("[W] 📋 Backlog", "#6699cc", "Issue identifiée mais non planifiée", 0),
    ("[W] 📌 To Do", "#cc338b", "Prête à être prise, à piocher en haut de la colonne", 0),
    ("[W] ⚙️ En cours", "#dc143c", "Activement en développement", 3),
    ("[W] 🚫 Bloqué", "#808080", "En attente d'une dépendance externe (accès, retour, décision) avant de reprendre", 0),
    ("[W] 👀 En review", "#cd5b45", "MR ouverte, en attente de code review", 2),
    ("[W] 🧪 En test", "#ed9121", "En cours de test QA / recette interne", 2),
    ("[W] 🚀 À déployer en Pré-production", "#eee600", "Validé en interne, prêt à pousser en staging", 0),
    ("[W] 🟡 En Pré-production", "#eee600", "Déployé en staging, en attente de validation", 0),
    ("[W] 🚢 À déployer en Production", "#009966", "Validé en staging, prêt pour la prod", 0),
    ("[W] ✅ Done", "#009966", "Déployé en production, issue clôturée", 0),
]


PROTECTED_BRANCHES = ("main", "staging", "develop")
PROTECTED_TAG = "v*"
NO_ONE = 0
MAINTAINER = 40


def _access_levels(entry, key):
    return {level["access_level"] for level in entry[key]}


def check_response(resp, method, path):
    if not resp.ok:
        raise requests.HTTPError(f"Erreur {resp.status_code} sur {method} {path} : {resp.text}", response=resp)


def api(session, base_url, method, path, **kwargs):
    resp = session.request(method, f"{base_url}/api/v4{path}", **kwargs)
    check_response(resp, method, path)
    return resp.json() if resp.text else None


def api_all(session, base_url, path, params=None):
    """GET paginé : suit l'en-tête X-Next-Page pour lire toutes les pages, pas seulement les 100 premiers éléments."""
    params = {**(params or {}), "per_page": 100, "page": 1}
    items = []
    while params["page"]:
        resp = session.get(f"{base_url}/api/v4{path}", params=params)
        check_response(resp, "GET", path)
        items.extend(resp.json())
        params["page"] = resp.headers.get("X-Next-Page")
    return items


def ensure_labels(session, base_url, scope):
    """Crée les labels manquants sur le scope (groupe ou projet) et réaligne la description de ceux qui existent."""
    existing = {label["name"]: label for label in api_all(session, base_url, f"{scope}/labels")}
    wanted = LABELS_DPT + [(title, color, description) for title, color, description, _wip in LABELS_W]

    for title, color, description in wanted:
        label = existing.get(title)
        if not label:
            api(session, base_url, "POST", f"{scope}/labels",
                json={"name": title, "color": color, "description": description})
            print(f"Label créé ({scope}) : {title}")
        # Sur un projet, la liste inclut les labels hérités du groupe : seul le groupe peut les modifier.
        elif label.get("description") != description and label.get("is_project_label", True):
            api(session, base_url, "PUT", f"{scope}/labels/{label['id']}", json={"description": description})
            print(f"Description mise à jour ({scope}) : {title}")


def ensure_backlog_milestone(session, base_url, scope):
    """Crée le milestone 'Backlog' sur le scope (groupe ou projet) s'il n'existe pas déjà, hérité compris."""
    # include_ancestors vaut pour un groupe, include_parent_milestones pour un projet : GitLab ignore l'autre.
    existing = api_all(session, base_url, f"{scope}/milestones",
                       params={"include_ancestors": True, "include_parent_milestones": True})
    if any(m["title"] == "Backlog" for m in existing):
        return
    try:
        api(session, base_url, "POST", f"{scope}/milestones", json={"title": "Backlog"})
    except requests.HTTPError as err:
        # GitLab refuse un titre déjà pris par un milestone d'un projet du groupe, invisible depuis l'API groupe.
        if err.response.status_code == 400 and "already being used" in err.response.text:
            print("Milestone 'Backlog' déjà utilisé par un projet du groupe : création ignorée.", file=sys.stderr)
            return
        raise
    print(f"Milestone créé ({scope}) : Backlog")


def get_or_create_board(session, base_url, project_id):
    boards = api(session, base_url, "GET", f"/projects/{project_id}/boards")
    if boards:
        return boards[0]["id"]
    board = api(session, base_url, "POST", f"/projects/{project_id}/boards", json={"name": "Issue Board"})
    return board["id"]


def clear_existing_label_lists(session, base_url, project_id, board_id):
    # L'API ne renvoie que les listes de labels (jamais les listes Open/Closed) : tout est à supprimer.
    lists = api_all(session, base_url, f"/projects/{project_id}/boards/{board_id}/lists")
    for lst in lists:
        api(session, base_url, "DELETE", f"/projects/{project_id}/boards/{board_id}/lists/{lst['id']}")


def set_wip_limit(session, base_url, list_id, wip_limit):
    """Pose une limite WIP via GraphQL (l'API REST ne le permet pas). Renvoie la liste des erreurs, vide si OK."""
    query = """
    mutation($listId: ListID!, $max: Int) {
      boardListUpdateLimitMetrics(input: {listId: $listId, limitMetric: issue_count, maxIssueCount: $max}) {
        errors
      }
    }
    """
    resp = session.post(f"{base_url}/api/graphql", json={
        "query": query,
        "variables": {"listId": f"gid://gitlab/List/{list_id}", "max": wip_limit},
    })
    check_response(resp, "POST", "/api/graphql")
    body = resp.json()
    errors = [e["message"] for e in body.get("errors") or []]
    result = (body.get("data") or {}).get("boardListUpdateLimitMetrics") or {}
    return errors + (result.get("errors") or [])


def apply_board_template(session, base_url, project_id, scope):
    labels = api_all(session, base_url, f"{scope}/labels")
    label_ids = {label["name"]: label["id"] for label in labels}

    board_id = get_or_create_board(session, base_url, project_id)
    clear_existing_label_lists(session, base_url, project_id, board_id)

    for title, _color, _description, wip_limit in LABELS_W:
        lst = api(session, base_url, "POST", f"/projects/{project_id}/boards/{board_id}/lists",
                  json={"label_id": label_ids[title]})
        wip_errors = set_wip_limit(session, base_url, lst["id"], wip_limit) if wip_limit else []
        if wip_errors:
            print(f"Limite WIP {wip_limit} non appliquée sur {title} : les limites WIP demandent l'offre GitLab Premium "
                  f"(réponse GitLab : {'; '.join(wip_errors)})", file=sys.stderr)
        print(f"Liste créée : {title}" + (f" (WIP {wip_limit})" if wip_limit and not wip_errors else ""))

    print(f"Board {board_id} configuré sur le projet {project_id}.")


def ensure_protected_branches(session, base_url, project_id):
    """Protège main, staging et develop : push interdit, merge réservé aux Maintainers."""
    path = f"/projects/{project_id}/protected_branches"
    existing = {entry["name"]: entry for entry in api_all(session, base_url, path)}

    for name in PROTECTED_BRANCHES:
        entry = existing.get(name)
        if entry and _access_levels(entry, "push_access_levels") == {NO_ONE} \
                and _access_levels(entry, "merge_access_levels") == {MAINTAINER} \
                and not entry["allow_force_push"]:
            continue
        # GitLab protège main par défaut avec push Maintainers : l'API ne permet de resserrer qu'en recréant.
        if entry:
            api(session, base_url, "DELETE", f"{path}/{quote(name, safe='')}")
        api(session, base_url, "POST", path, json={
            "name": name,
            "push_access_level": NO_ONE,
            "merge_access_level": MAINTAINER,
            "allow_force_push": False,
        })
        print(f"Branche protégée : {name}")


def ensure_protected_tags(session, base_url, project_id):
    """Réserve la création des tags v* aux Maintainers : un tag déclenche la mise en production."""
    path = f"/projects/{project_id}/protected_tags"
    existing = {entry["name"]: entry for entry in api_all(session, base_url, path)}

    entry = existing.get(PROTECTED_TAG)
    if entry and _access_levels(entry, "create_access_levels") == {MAINTAINER}:
        return
    if entry:
        api(session, base_url, "DELETE", f"{path}/{quote(PROTECTED_TAG, safe='')}")
    api(session, base_url, "POST", path, json={"name": PROTECTED_TAG, "create_access_level": MAINTAINER})
    print(f"Tag protégé : {PROTECTED_TAG}")


def apply_merge_settings(session, base_url, project_id):
    """Impose pipeline vert et discussions résolues avant merge, et supprime la branche source ensuite."""
    api(session, base_url, "PUT", f"/projects/{project_id}", json={
        "only_allow_merge_if_pipeline_succeeds": True,
        "only_allow_merge_if_all_discussions_are_resolved": True,
        "remove_source_branch_after_merge": True,
    })
    print("Réglages de merge appliqués : pipeline vert, discussions résolues, suppression de la branche source.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", default=None, help="ID du projet GitLab cible (demandé si absent)")
    parser.add_argument("--group-id", default=None,
                        help="ID du groupe qui porte les labels/milestones (si absent, créés au niveau du projet)")
    args = parser.parse_args()

    # La console Windows utilise cp1252 par défaut, incapable d'afficher les emojis des labels.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    project_id = args.project_id or input("ID du projet : ").strip()
    scope = f"/groups/{args.group_id}" if args.group_id else f"/projects/{project_id}"

    base_url = os.environ.get("GITLAB_URL", "https://gitlab.com").rstrip("/")
    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        sys.exit("Variable d'environnement GITLAB_TOKEN manquante.")

    session = requests.Session()
    session.headers.update({"PRIVATE-TOKEN": token})

    ensure_labels(session, base_url, scope)
    ensure_backlog_milestone(session, base_url, scope)
    apply_board_template(session, base_url, project_id, scope)
    ensure_protected_branches(session, base_url, project_id)
    ensure_protected_tags(session, base_url, project_id)
    apply_merge_settings(session, base_url, project_id)


if __name__ == "__main__":
    main()
