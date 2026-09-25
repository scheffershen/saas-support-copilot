# Épisode 10 — Recherche consciente des permissions

**À l'écran :** la même question - « comment forcer la désactivation d'un compte
compromis ? » - posée deux fois, une fois en tant que `support_lead`, une fois en tant
que `support_agent`.

## Objectif d'apprentissage

Un système de recherche capable de tout trouver est un système capable de tout
divulguer. Faites du rôle une entrée de première classe pour la recherche, appliquée au
niveau de la couche qui décide de ce qui est même *candidat*, et non une simple
suggestion que l'on demande au LLM de respecter.

## Points à aborder

1. **Classification des documents.** `RESTRICTED_DOCS`, dans `security/classification.py`,
   fait correspondre un chemin aux rôles autorisés à le voir - `docs/admin-runbook.md`
   (injecté dans cet épisode : forcer la désactivation d'un compte compromis) est
   réservé à `support_lead`, ce qui correspond à ce que `docs/roles-and-permissions.md`
   indique déjà : ce rôle est le seul habilité à le faire (désactiver des
   utilisateurs).
2. **Rôles.** `ROLES`, dans `security/roles.py`, n'est pas un ensemble d'exemples
   inventé - ce sont exactement les trois rôles propres à Loopline, tirés directement
   de `seed.py` et de `roles-and-permissions.md`.
3. **Autorisation au moment de la recherche, comme frontière stricte.**
   `DocumentIndex.eligible_indices()` calcule le sous-ensemble d'index de chunks
   autorisés *avant* que le moindre classement n'ait lieu ; `eligible` restreint
   ensuite `BM25Index.search()` et le classement sémantique à ces seuls index. Un
   chunk non éligible n'est jamais noté - pas noté-puis-caché, jamais candidat.
4. **Pourquoi « jamais candidat » compte : la résistance à la paraphrase.** Un filtre
   a posteriori (tout classer, puis écarter les résultats non autorisés) n'est sûr que
   dans la mesure où personne n'oublie d'appeler l'étape de filtrage.
   `test_restricted_doc_stays_invisible_to_a_paraphrased_query_too` pose une question
   sur la même procédure restreinte avec des mots complètement différents, ne
   partageant presque aucun vocabulaire avec le document source - elle reste
   introuvable, car exclure le chunk de `eligible` fait que *la question de savoir à
   quel point il correspond* ne se pose même jamais.
5. **Le rôle est lié, jamais transmis.** Même discipline que pour chaque racine en
   liste blanche depuis l'Épisode 5 : `role` est une liaison `functools.partial` dans
   `build_default_registry()`, jamais un champ de `SearchDocsArgs`. Si c'était un
   argument fournissable par le LLM, le modèle pourrait tout simplement prétendre
   chercher en tant que `support_lead` - tout l'intérêt du RBAC est que l'identité
   provient de l'appelant, et non de ce que prétend la requête de l'appelant
   lui-même.
6. **Une lacune de prototype assumée, pas dissimulée.** `is_visible_to(path, role=None)`
   a par défaut un comportement visible-par-tous - pratique tant qu'il n'y a pas
   encore de couche d'authentification, et explicitement documenté comme le mauvais
   choix par défaut pour la production, qui doit refuser les identités inconnues, pas
   les autoriser. L'Épisode 17 revient là-dessus.

   **Mise à jour (Épisode 17) :** refermé - `role=None` désigne désormais l'appelant
   le moins privilégié, et non le plus privilégié. Voir
   [`lessons/17-prototype-vs-production-architecture.md`](17-prototype-vs-production-architecture.md)
   pour l'avant/après en direct. Ce qui est décrit ci-dessus était exact jusqu'à
   l'Épisode 16 ; laissé tel quel plutôt que discrètement modifié, comme pour la note
   de citation de l'Épisode 1.

## Implémentation

- [`src/saas_copilot/security/roles.py`](../../src/saas_copilot/security/roles.py) — `ROLES`, `validate_role`.
- [`src/saas_copilot/security/classification.py`](../../src/saas_copilot/security/classification.py) — `RESTRICTED_DOCS`, `is_visible_to`.
- [`sample_app/loopline/docs/admin-runbook.md`](../../sample_app/loopline/docs/admin-runbook.md) — le document restreint injecté pour cet épisode.
- [`src/saas_copilot/retrieval/bm25.py`](../../src/saas_copilot/retrieval/bm25.py) / [`retrieval/index.py`](../../src/saas_copilot/retrieval/index.py) — `eligible` propagé à travers la recherche.
- [`src/saas_copilot/tools/docs.py`](../../src/saas_copilot/tools/docs.py) / [`tools/__init__.py`](../../src/saas_copilot/tools/__init__.py) — `search_docs`/`build_default_registry` acquièrent `role`.

## Exécution

```bash
pytest tests/unit/test_security_roles.py tests/unit/test_security_classification.py \
       tests/unit/test_retrieval_bm25.py tests/unit/test_retrieval_index.py \
       tests/unit/test_tools_docs.py tests/unit/test_tools_default_registry.py -v
```

## Démo en direct (sortie vérifiée)

```pycon
>>> registry = build_default_registry(settings, repo_root=repo_root, role="support_lead")
>>> {d.path for d in registry.call("search_docs", {"query": "force-deactivate a compromised account"})}
{'docs/admin-runbook.md', 'docs/roles-and-permissions.md', 'docs/notifications.md', ...}

>>> registry = build_default_registry(settings, repo_root=repo_root, role="support_agent")
>>> {d.path for d in registry.call("search_docs", {"query": "force-deactivate a compromised account"})}
{'docs/roles-and-permissions.md', 'docs/notifications.md', ...}   # admin-runbook.md: gone
```

(`admin-runbook.md` apparaît en réalité trois fois dans la liste brute de résultats
`support_lead`, avant déduplication - il a été découpé en trois chunks, le découpage de
l'Épisode 8 à l'œuvre sur un document juste assez long pour franchir deux fois la
limite des 300 caractères.)

## Cas d'échec (celui qui a compté pendant la construction)

Mon premier test pour le cas du rôle non autorisé affirmait que la requête ne
trouverait *rien*. Elle a trouvé cinq autres documents. `roles-and-permissions.md`
contient légitimement la phrase « Deactivate users » dans son propre tableau de
permissions, et correspond correctement pour tous les rôles - il n'est pas restreint,
il *parle* simplement d'une action restreinte. La véritable propriété n'est pas « une
recherche non autorisée renvoie un résultat vide » ; elle est plus étroite et plus
précise : « le document restreint, spécifiquement, n'apparaît jamais ». Affirmer la
version plus forte, et erronée, aurait fait échouer le test pour une raison n'ayant
rien à voir avec la propriété de sécurité qu'il était censé démontrer.

## Exercice

`eligible_indices()` prend un prédicat, donc il généralise déjà au-delà d'une simple
vérification « quels rôles ». Ajoutez une seconde dimension de classification,
indépendante - restreignez un document par *sensibilité du contenu* (par exemple,
« financier ») en plus du rôle - et prouvez qu'une requête a besoin à la fois d'un rôle
autorisé ET d'un niveau de sensibilité autorisé pour le faire apparaître
(`predicate = lambda doc: is_visible_to(doc.path, role) and is_sensitivity_allowed(doc.path, clearance)`).
C'est la forme dont les systèmes multi-tenants ont besoin pour « rôle ET tenant », pas
seulement « rôle ».

## Suite

L'Épisode 11 donne au spécialiste `feature` une véritable structure de planification :
un workflow borné, en plusieurs étapes, plutôt que « appeler quelques outils, puis
répondre ».
