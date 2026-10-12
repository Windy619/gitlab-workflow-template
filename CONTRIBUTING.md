# Workflow Git - stratégie de branches

```
<type>/<iid>-<slug> ──► develop ──► staging ──► main ──► tag v* ──► production
                                                      ▲
hotfix/<iid>-<slug> ──────────────────────────────────┘
```

## Branches

| Branche                | Rôle                                                       | Push direct |
|------------------------|------------------------------------------------------------|-------------|
| `main`                 | Production stable, chaque release porte un tag `v*`        | ❌ Jamais    |
| `staging`              | Pré-production, validation avant mise en production       | ❌ Jamais    |
| `develop`              | Intégration, base de toutes les branches de travail        | ❌ Jamais    |
| `<type>/<iid>-<slug>`  | Une branche par issue, créée depuis `develop`              | ✅           |
| `hotfix/<iid>-<slug>`  | Correctif urgent, créé depuis `main`                       | ✅           |

`<iid>` est le numéro de l'issue et `<slug>` son titre en minuscules sans accents, séparé par des tirets. Types : `feat`, `fix`, `hotfix`, `improv`, `refactor`, `chore`, `test`, `docs`.

Toute modification passe par une **Merge Request** : aucun commit direct sur `develop`, `staging` ou `main`.

## Nouvelle branche de travail

```bash
git checkout develop
git pull
git checkout -b feat/42-ajouter-la-connexion-sso

# ... travail + commits ...

git push -u origin feat/42-ajouter-la-connexion-sso
```

→ Ouvrir une Merge Request draft `feat/42-ajouter-la-connexion-sso → develop` (template `Default`, `Relates to #42`).
→ Merger dans `develop` après review, puis supprimer la branche.

## Mise en production

1. MR de batch `develop → staging` - titre : `chore: merge develop into staging - YYYY-MM-DD`
2. Validation sur l'environnement de staging.
3. MR de batch `staging → main` - titre : `chore: merge staging into main - YYYY-MM-DD`
4. Tag SemVer sur `main` après le merge :

   ```bash
   git checkout main
   git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

5. Le tag `v*` déclenche le déploiement en production.
6. Fermer manuellement les issues concernées (les MR utilisent `Relates to #XX`, jamais `Closes #XX`).

## Hotfix

```bash
git checkout main
git pull
git checkout -b hotfix/42-corriger-le-calcul-de-la-tva

# ... correctif ...

git push -u origin hotfix/42-corriger-le-calcul-de-la-tva
```

→ MR `hotfix/42-corriger-le-calcul-de-la-tva → main`, puis tag PATCH (`vX.Y.Z+1`).
→ Reporter le correctif dans `develop` (MR `main → develop`) pour ne pas le perdre au batch suivant.

## Versionnement SemVer

| Changement      | Incrément | Exemple           |
|-----------------|-----------|-------------------|
| `fix`           | PATCH     | `v1.0.0 → v1.0.1` |
| `feat`          | MINOR     | `v1.0.1 → v1.1.0` |
| `improvement`   | MINOR     | `v1.1.0 → v1.2.0` |
| breaking change | MAJOR     | `v1.2.0 → v2.0.0` |

Un batch qui ne contient que `refactor`, `perf`, `test`, `docs` ou `chore` donne un PATCH s'il change le livrable, aucun tag sinon.

Le tag se pose uniquement sur `main`, jamais sur une branche de travail.

## Commits

Format : `<emoji> <type>(<scope>): <description en anglais>`

Un emoji fixe par type :

| Type          | Emoji |
|---------------|-------|
| `feat`        | ✨    |
| `fix`         | 🐛    |
| `improvement` | 📈    |
| `refactor`    | ♻️    |
| `perf`        | ⚡    |
| `test`        | ✅    |
| `docs`        | 📝    |
| `chore`       | 🔧    |

Exemple : `✨ feat(auth): add microsoft azure single sign-on`
