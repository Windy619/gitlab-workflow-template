# Workflow Git - stratégie de branches

```
feature/* ──► develop ──► staging ──► main ──► tag v* ──► production
                                        ▲
hotfix/*  ──────────────────────────────┘
```

## Branches

| Branche      | Rôle                                                   | Push direct |
|--------------|--------------------------------------------------------|-------------|
| `main`       | Production stable, chaque release porte un tag `v*`    | ❌ Jamais    |
| `staging`    | Pré-production, validation avant mise en production   | ❌ Jamais    |
| `develop`    | Intégration, base de toutes les features               | ❌ Jamais    |
| `feature/nom` | Une branche par fonctionnalité, créée depuis `develop` | ✅           |
| `hotfix/nom` | Correctif urgent, créé depuis `main`                   | ✅           |

Toute modification passe par une **Merge Request** : aucun commit direct sur `develop`, `staging` ou `main`.

## Nouvelle feature

```bash
git checkout develop
git pull
git checkout -b feature/ma-feature

# ... travail + commits ...

git push -u origin feature/ma-feature
```

→ Ouvrir une Merge Request `feature/ma-feature → develop` (template `Default`).
→ Merger dans `develop` après review, puis supprimer la branche feature.

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
git checkout -b hotfix/mon-correctif

# ... correctif ...

git push -u origin hotfix/mon-correctif
```

→ MR `hotfix/mon-correctif → main`, puis tag PATCH (`vX.Y.Z+1`).
→ Reporter le correctif dans `staging` et `develop` (MR `main → develop`) pour ne pas le perdre à la release suivante.

## Versionnement SemVer

| Changement      | Incrément | Exemple           |
|-----------------|-----------|-------------------|
| `fix`           | PATCH     | `v1.0.0 → v1.0.1` |
| `feat`          | MINOR     | `v1.0.1 → v1.1.0` |
| breaking change | MAJOR     | `v1.1.0 → v2.0.0` |

Le tag se pose uniquement sur `main`, jamais sur une branche feature.

## Commits

Format : `<emoji> <type>(<scope>): <description en anglais>`

Un emoji fixe par type :

| Type       | Emoji |
|------------|-------|
| `feat`     | ✨    |
| `fix`      | 🐛    |
| `docs`     | 📝    |
| `perf`     | ⚡    |
| `chore`    | 🔧    |

Exemple : `✨ feat(auth): add microsoft azure single sign-on`
