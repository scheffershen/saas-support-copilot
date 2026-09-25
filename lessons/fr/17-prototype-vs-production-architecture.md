# Épisode 17 — Architecture prototype versus production

**À l'écran :** exactement le même appel — un appelant anonyme, sans en-tête
`X-User-Role`, demandant de rechercher « désactiver de force un compte compromis » —
exécuté deux fois : une fois contre le code de départ de cet épisode, une fois après
son correctif d'une seule ligne. `docs/admin-runbook.md` figure dans les résultats la
première fois. Il a disparu la seconde.

## Objectif d'apprentissage

Chaque épisode jusqu'ici a ajouté une capacité. Celui-ci trace la limite autour de
toutes : qu'est-ce que ce prototype possède réellement, de quoi un vrai déploiement en
production a-t-il encore besoin, et — le seul endroit où ces deux questions se
rejoignent assez concrètement pour être corrigé aujourd'hui — où le code de ce cours
s'est-il tranquillement reposé sur une lacune qu'il avait déjà nommée à voix haute ?
Fermer celle-là pour de bon, puis consigner le reste avec assez de précision pour
agir, pas simplement l'esquisser.

## Points à aborder

1. **Une lacune que deux épisodes précédents avaient déjà nommée et délibérément
   différée.** La branche `role=None` de `security/classification.py::is_visible_to`
   renvoyait `True` sans condition depuis l'Épisode 10 - « aucune identité connue »
   était traité comme *plus* digne de confiance que n'importe quel rôle réel, pas
   moins. La propre docstring de l'Épisode 10 qualifiait cela de « commodité de
   prototype... pas un défaut sûr pour la production ». `api/dependencies.py::get_role`
   de l'Épisode 14 reprenait la même remarque : « inverser ce défaut est explicitement
   le travail de l'Épisode 17 ». Une lacune documentée reste une vraie lacune jusqu'à
   ce que l'épisode qui a promis de la fermer le fasse réellement.
2. **Le correctif est plus étroit que « appelant inconnu ne voit rien ».**
   `RESTRICTED_DOCS` est une liste d'exclusion - la plupart des docs n'y ont aucune
   entrée et sont visibles par tout le monde. L'inversion correcte n'est pas « pas
   d'identité, pas d'accès » (cela casserait toute réponse du domaine usage, puisqu'aucun
   client de ce cours n'envoie jamais `X-User-Role` sauf s'il teste spécifiquement une
   restriction de rôle) - c'est « l'absence d'identité n'est jamais traitée comme
   implicitement autorisée pour un contenu qui nomme des rôles autorisés spécifiques »,
   exactement ce que tout autre rôle non autorisé reçoit déjà. `is_visible_to` vérifie
   désormais `path not in RESTRICTED_DOCS` en premier, le même court-circuit que
   `roles_allowed()` utilisait déjà, avant même de comparer `role`.
3. **Ce que ce correctif ne ferme *pas*.** `get_role()` fait toujours confiance à
   n'importe quel `X-User-Role` envoyé par l'appelant - validé pour être un nom de rôle
   réel (`validate_role`), jamais pour appartenir réellement à celui qui l'a envoyé. Le
   RBAC (restreindre ce qu'un rôle peut voir) et l'authentification (confirmer qu'un
   appelant est vraiment ce rôle) sont des préoccupations différentes ; cet épisode a
   fermé la première lacune dans la première préoccupation, pas la seconde. La
   checklist ci-dessous les garde volontairement comme deux points séparés, non
   cochés.
4. **La checklist de préparation à la production.**
   `docs/production-readiness-checklist.md` - identité/accès, isolation des tenants,
   frontières réseau, rétention d'audit, limites de débit et coût, files d'attente,
   sauvegardes, réponse aux incidents, modélisation des menaces, ownership. Chaque
   ligne nomme le fichier ou le comportement réel dont il s'agit, jamais un conseil
   générique - la même discipline que ce cours a appliquée aux points à aborder de
   chaque leçon, tournée cette fois vers le système entier plutôt que la capacité d'un
   seul épisode.
5. **L'isolation des tenants est la plus grande lacune unique de la liste.** Rien dans
   ce code n'a jamais eu de notion de « tenant » - un seul schéma MySQL, aucun
   `tenant_id` nulle part, `query_database` un outil SELECT généraliste construit dans
   les Épisodes 12 et 16 qui serait exactement la mauvaise forme pour lui faire
   confiance avec un filtre de tenant fourni par l'appelant. Aucun épisode avant
   celui-ci n'a eu besoin de le nommer, car Loopline lui-même n'a jamais modélisé
   qu'une seule organisation.
6. **La frontière de la propriété intellectuelle et de l'autorisation, dans son
   intégralité.** Référencée depuis le tout premier commit de ce dépôt et la note
   d'origine de conception de `youtube_course_plan.md`, elle reçoit ici son traitement
   complet : avant de pointer ce pattern vers le code, la base de données ou les logs
   d'un vrai employeur, obtenir une autorisation écrite explicite sur exactement ce que
   l'agent peut lire et où sa sortie peut aller - traitée comme un identifiant, pas
   comme une commodité - et ne jamais laisser de vrai code, de vraies données ou de
   vrais noms de produits propriétaires atteindre un dépôt public ou un contenu de
   leçon public. Ce dépôt tient cette ligne depuis le premier commit.
7. **Le capstone ne ferme pas cette liste - il la montre.** L'Épisode 18 démontre le
   prototype terminé de bout en bout et présente cette checklist à ses côtés,
   honnêtement étiquetée comme ce qui manque encore. C'est la même règle « énoncer
   clairement les limites de production » du tout premier point à aborder de
   l'Épisode 0, appliquée cette fois au système entier en sortie plutôt qu'à une seule
   fonctionnalité en entrée.

## Implémentation

- [`src/saas_copilot/security/classification.py`](../../src/saas_copilot/security/classification.py) — l'inversion deny-by-default de `is_visible_to`.
- [`src/saas_copilot/api/dependencies.py`](../../src/saas_copilot/api/dependencies.py) — la docstring de `get_role`, corrigée maintenant que l'inversion est réelle.
- [`docs/production-readiness-checklist.md`](../../docs/production-readiness-checklist.md) — le second livrable de cet épisode.
- [`tests/unit/test_security_classification.py`](../../tests/unit/test_security_classification.py), [`tests/unit/test_tools_docs.py`](../../tests/unit/test_tools_docs.py), [`tests/unit/test_api.py`](../../tests/unit/test_api.py) — un test inversé et un nouveau, prouvant la propriété à la couche de classification, à la couche outil, et dans la vraie chaîne de dépendances FastAPI.

## Exécution

```bash
pytest tests/unit/test_security_classification.py tests/unit/test_tools_docs.py tests/unit/test_api.py -v
```

## Cas d'échec (réel, le point de départ de cet épisode)

Contre le code exactement tel que l'Épisode 16 l'a laissé - `get_role(x_user_role=None)`,
la vraie fonction que FastAPI appelle pour une requête sans aucun en-tête
`X-User-Role`, injectée directement dans `get_registry()`, la vraie chaîne de
dépendances, aucun mock :

```pycon
>>> role = get_role(x_user_role=None)
>>> role
None
>>> registry = build_registry_for_role(resources, role=role)
>>> {d.path for d in registry.call("search_docs", {"query": "force-deactivate a compromised account"})}
{'docs/admin-runbook.md', 'docs/assigning-tickets.md', 'docs/creating-a-ticket.md',
 'docs/getting-started.md', 'docs/integration-notes.md', 'docs/notifications.md',
 'docs/roles-and-permissions.md'}
```

Un appelant authentifié en tant que personne a récupéré le seul document de tout ce
corpus qui est restreint à `support_lead`.

## Démo en direct (sortie vérifiée)

Le même appel identique, après le changement unique de cet épisode dans
`is_visible_to` :

```pycon
>>> role = get_role(x_user_role=None)
>>> role
None
>>> registry = build_registry_for_role(resources, role=role)
>>> {d.path for d in registry.call("search_docs", {"query": "force-deactivate a compromised account"})}
{'docs/assigning-tickets.md', 'docs/creating-a-ticket.md', 'docs/getting-started.md',
 'docs/integration-notes.md', 'docs/notifications.md', 'docs/roles-and-permissions.md'}
```

`docs/admin-runbook.md` — disparu. Tout le reste — identique, six sur six. Le correctif
a retiré exactement le seul document qu'il devait retirer, et rien d'autre : un
appelant anonyme peut toujours retrouver tous les documents ordinaires, comme avant.

## Exercice

Choisissez un point ouvert dans `production-readiness-checklist.md` et fermez-en la
plus petite tranche réelle possible. La limitation de débit est la plus autonome :
ajoutez un token bucket basique par appelant devant `POST /ask` (indexé sur
`X-User-Role`, ou l'IP de connexion en son absence - la vraie identité reste le travail
de l'authentification, pas celui-ci), renvoyant `429` dès qu'un appelant le dépasse
dans une fenêtre donnée. Écrivez un test prouvant que la Nième requête dans une boucle
serrée est bloquée et que la (N-1)ième ne l'est pas - puis mettez à jour la case de
limitation de débit de la checklist pour refléter exactement ce que vous avez construit
et ce qui manque encore (un token bucket mono-processus ne survivra pas à plusieurs
instances de serveur ; nommez-le honnêtement plutôt que de prétendre silencieusement en
avoir fait plus).

## Suite

L'Épisode 18 est le capstone : ingestion, questions-réponses sensibles aux
permissions, un diagnostic de bug avec preuves citées, un triage de faisabilité de
fonctionnalité utilisant le graphe d'appels, des citations, un refus, des traces
d'outils, des résultats d'évaluation, un déploiement local, et la checklist de cet
épisode - montrés ensemble, de bout en bout. Il met les apprenants au défi d'ajouter un
nouveau module Loopline avec sa propre documentation, ses propres restrictions de
rôle, et dix tests bien à eux.
