#!/usr/bin/env python3
"""
Initialise le template complet (labels + milestone Backlog + board) sur
GitLab via l'API :
  - Les labels [D]/[P]/[T]/[W] et le milestone "Backlog" sont créés au
    niveau du GROUPE -> hérités automatiquement par tous les projets de
    ce groupe, donc créés une seule fois par groupe (le script vérifie
    ce qui existe déjà et ne recrée rien en double).
  - Le board (listes + limites WIP) est propre à chaque PROJET -> recréé
    à chaque nouveau projet.

Usage :
    export GITLAB_URL="https://gitlab.com"        # ou l'URL de ton instance
    export GITLAB_TOKEN="glpat-xxxxxxxxxxxx"       # token personnel, scope "api"
    python3 setup_gitlab_template.py --project-id 42 --group-id 51

    # ou sans arguments : le script les demande de manière interactive
    python3 setup_gitlab_template.py

    # pour créer un nouveau sprint daté au niveau du groupe (optionnel) :
    python3 setup_gitlab_template.py --new-sprint "Sprint 2" --sprint-start 2026-10-07

Prérequis :
    pip install -r requirements.txt
"""

import argparse
import datetime
import os
import sys

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
    ("[P] 🟠 P2 · High", "#ed9121", "Important, à traiter dans le sprint en cours"),
    ("[P] 🟡 P3 · Medium", "#eee600", "Normal, planifiable au prochain sprint"),
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
    ("[W] 📌 To Do", "#cc338b", "Planifiée pour le sprint/itération en cours", 0),
    ("[W] ⚙️ En cours", "#dc143c", "Activement en développement", 3),
    ("[W] 🚫 Bloqué", "#808080", "En attente d'une dépendance externe (accès, retour, décision) avant de reprendre", 0),
    ("[W] 👀 En review", "#cd5b45", "MR ouverte, en attente de code review", 2),
    ("[W] 🧪 En test", "#ed9121", "En cours de test QA / recette interne", 2),
    ("[W] 🚀 À déployer en Pré-production", "#eee600", "Validé en interne, prêt à pousser en staging", 0),
    ("[W] 🟡 En Pré-production", "#eee600", "Déployé en staging, en attente de validation", 0),
    ("[W] 🚢 À déployer en Production", "#009966", "Validé en staging, prêt pour la prod", 0),
    ("[W] ✅ Done", "#009966", "Déployé en production, issue clôturée", 0),
]


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


def ensure_group_labels(session, base_url, group_id):
    """Crée les labels manquants au niveau du groupe. Ne touche pas à ceux qui existent déjà."""
    existing = api_all(session, base_url, f"/groups/{group_id}/labels")
    existing_names = {label["name"] for label in existing}

    for title, color, description in LABELS_DPT:
        if title in existing_names:
            continue
        api(session, base_url, "POST", f"/groups/{group_id}/labels",
            json={"name": title, "color": color, "description": description})
        print(f"Label groupe créé : {title}")

    for title, color, description, _wip in LABELS_W:
        if title in existing_names:
            continue
        api(session, base_url, "POST", f"/groups/{group_id}/labels",
            json={"name": title, "color": color, "description": description})
        print(f"Label groupe créé : {title}")


def ensure_backlog_milestone(session, base_url, group_id):
    """Crée le milestone 'Backlog' au niveau du groupe s'il n'existe pas déjà."""
    existing = api_all(session, base_url, f"/groups/{group_id}/milestones", params={"include_ancestors": True})
    if any(m["title"] == "Backlog" for m in existing):
        return
    try:
        api(session, base_url, "POST", f"/groups/{group_id}/milestones", json={"title": "Backlog"})
    except requests.HTTPError as err:
        # GitLab refuse un titre déjà pris par un milestone d'un projet du groupe, invisible depuis l'API groupe.
        if err.response.status_code == 400 and "already being used" in err.response.text:
            print("Milestone 'Backlog' déjà utilisé par un projet du groupe : création ignorée.", file=sys.stderr)
            return
        raise
    print("Milestone groupe créé : Backlog")


def create_sprint_milestone(session, base_url, group_id, title, start_date, weeks=2):
    """Crée un nouveau milestone de sprint daté au niveau du groupe."""
    start = datetime.date.fromisoformat(start_date)
    due = start + datetime.timedelta(weeks=weeks)
    api(session, base_url, "POST", f"/groups/{group_id}/milestones", json={
        "title": title,
        "description": f"Itération de {weeks} semaines - exemple à dupliquer/renommer pour chaque nouveau sprint",
        "start_date": start.isoformat(),
        "due_date": due.isoformat(),
    })
    print(f"Milestone groupe créé : {title} ({start.isoformat()} → {due.isoformat()})")


def get_or_create_board(session, base_url, project_id):
    boards = api(session, base_url, "GET", f"/projects/{project_id}/boards")
    if boards:
        return boards[0]["id"]
    board = api(session, base_url, "POST", f"/projects/{project_id}/boards", json={"name": "Issue Board"})
    return board["id"]


def clear_existing_label_lists(session, base_url, project_id, board_id):
    lists = api(session, base_url, "GET", f"/projects/{project_id}/boards/{board_id}/lists")
    for lst in lists:
        if lst["list_type"] == "label":
            api(session, base_url, "DELETE", f"/projects/{project_id}/boards/{board_id}/lists/{lst['id']}")


def apply_board_template(session, base_url, project_id, group_id):
    labels = api_all(session, base_url, f"/groups/{group_id}/labels")
    label_ids = {label["name"]: label["id"] for label in labels}

    board_id = get_or_create_board(session, base_url, project_id)
    clear_existing_label_lists(session, base_url, project_id, board_id)

    for title, _color, _description, wip_limit in LABELS_W:
        lst = api(session, base_url, "POST", f"/projects/{project_id}/boards/{board_id}/lists",
                  json={"label_id": label_ids[title]})
        if wip_limit:
            api(session, base_url, "PUT", f"/projects/{project_id}/boards/{board_id}/lists/{lst['id']}",
                json={"max_issue_count": wip_limit, "limit_metric": "issue_count"})
        print(f"Liste créée : {title}" + (f" (WIP {wip_limit})" if wip_limit else ""))

    print(f"Board {board_id} configuré sur le projet {project_id}.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", default=None, help="ID du projet GitLab cible (demandé si absent)")
    parser.add_argument("--group-id", default=None, help="ID du groupe qui porte les labels/milestones (demandé si absent)")
    parser.add_argument("--new-sprint", default=None, help="Titre d'un nouveau milestone de sprint à créer (optionnel)")
    parser.add_argument("--sprint-start", default=None, help="Date de début du sprint (YYYY-MM-DD), requis avec --new-sprint")
    parser.add_argument("--sprint-weeks", type=int, default=2, help="Durée du sprint en semaines (défaut : 2)")
    args = parser.parse_args()

    # La console Windows utilise cp1252 par défaut, incapable d'afficher les emojis des labels.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    project_id = args.project_id or input("ID du projet : ").strip()
    group_id = args.group_id or input("ID du groupe (labels/milestones) : ").strip()

    base_url = os.environ.get("GITLAB_URL", "https://gitlab.com").rstrip("/")
    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        sys.exit("Variable d'environnement GITLAB_TOKEN manquante.")

    session = requests.Session()
    session.headers.update({"PRIVATE-TOKEN": token})

    ensure_group_labels(session, base_url, group_id)
    ensure_backlog_milestone(session, base_url, group_id)
    apply_board_template(session, base_url, project_id, group_id)

    if args.new_sprint:
        if not args.sprint_start:
            sys.exit("--sprint-start est requis avec --new-sprint")
        create_sprint_milestone(session, base_url, group_id, args.new_sprint, args.sprint_start, args.sprint_weeks)


if __name__ == "__main__":
    main()
