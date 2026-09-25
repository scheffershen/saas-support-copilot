# Épisode 14 — La frontière applicative FastAPI

**À l'écran :** `curl -X POST /ask` envoyé à un serveur réel, en cours d'exécution -
une réponse réelle et citée revient, avec un identifiant de requête à la fois dans
l'en-tête et dans le corps. Puis exactement la même requête envoyée à un client non
configuré, non scripté - un `502 malformed_output` propre, et non une traceback
Python.

## Objectif d'apprentissage

Tout ce qui a été construit jusqu'ici a été appelé en-process, directement, par les
tests et par les composants entre eux. Cet épisode lui donne une frontière HTTP - le
même pipeline `ask()`/`run_agent()` que les tests de chaque épisode précédent
exercent déjà, désormais accessible via le réseau. Cette frontière apporte ses propres
préoccupations : un corps de requête venant d'un inconnu a besoin d'une forme
validée, les ressources partagées coûteuses (l'index de documents, le graphe
d'appels) doivent survivre à travers de nombreuses requêtes sans être reconstruites à
chaque fois, le travail synchrone ne peut pas bloquer la boucle d'événements que
partagent les autres requêtes, et chacun des types d'exception propres à ce cours doit
devenir une réponse qu'un client peut réellement parser - pas une traceback.

## Points à aborder

1. **Des modèles de requête/réponse, pour la même raison que `Answer` (Épisode 3).**
   `AskRequest`/`AskResponse`, dans `api/schemas.py`, sont des modèles Pydantic - un
   corps de requête HTTP est une entrée non fiable, au même titre que la sortie d'un
   LLM, et FastAPI la valide avant qu'un gestionnaire de route ne la voie.
2. **L'injection de dépendances rembourse une vieille dette.**
   `tools/__init__.py::build_default_registry` porte un commentaire depuis
   l'Épisode 10 : reconstruire l'index de documents et le graphe d'appels à *chaque*
   appel convient pour un test qui construit un seul registre puis s'arrête, mais
   c'est faux pour un serveur qui traite de nombreuses requêtes avec des rôles
   différents. Scindé en `build_shared_resources()` (coûteux, construit une seule
   fois) et `build_registry_for_role()` (peu coûteux, ne relie que le rôle) - le
   `lifespan` de `api/main.py` construit la partie partagée une seule fois au
   démarrage et la range dans `app.state` ; les fournisseurs `Depends()` de
   `api/dependencies.py` la relisent à chaque requête. `build_default_registry()` est
   désormais un mince wrapper au-dessus des deux, conservé pour que les tests de
   chaque épisode précédent continuent de l'appeler exactement comme avant - prouvé
   directement (`test_build_default_registry_matches_the_split_two_step_build`).
3. **Des endpoints asynchrones, en toute honnêteté.** `run_agent()`/`ask()` sont
   synchrones, volontairement, depuis la propre note de correction de l'Épisode 5 (un
   timeout de pool de threads, pas un vrai asynchrone). Les gestionnaires de route
   sont malgré tout des `async def`, et font explicitement basculer le travail réel de
   l'agent vers un thread de travail avec `asyncio.to_thread()` - de sorte qu'une
   exécution d'agent lente ne bloque pas la boucle d'événements que partagent toutes
   les autres requêtes concurrentes. FastAPI exécuterait aussi automatiquement un
   gestionnaire `def` classique dans un pool de threads (le propre `routers/tickets.py`
   de Loopline s'appuie exactement là-dessus, inchangé depuis l'Épisode 0) - la
   version explicite ici énonce le même mécanisme au lieu de le laisser implicite.
4. **Des identifiants de requête, sous forme de middleware.** `add_request_id`
   enveloppe chaque requête - le propre `X-Request-ID` de l'appelant s'il en a envoyé
   un, sinon un nouveau - défini sur `request.state` avant l'exécution de la route et
   répercuté comme en-tête de réponse en cas de succès *et* en cas de réponse
   d'erreur, puisque le middleware enveloppe l'appel tout entier, y compris la
   gestion des exceptions.
5. **Un contrôle de santé qui est à la fois peu coûteux *et* réel.** `/health` rapporte
   un nombre réel (`docs_indexed`, lu depuis `app.state`) sans rien reconstruire - la
   preuve que la dépendance réelle du service (l'index de documents) est vivante, et
   pas seulement que le processus tourne, et assez rapide pour être interrogé en
   continu.
6. **Réponses d'erreur : un gestionnaire par type d'exception que ce cours définit
   déjà, jamais un `except Exception` nu.** `UnknownRoleError` -> 400 (l'erreur du
   client) ; `AgentError` et chacune de ses sous-classes -> 422 (une requête bien
   formée que les propres contraintes de sécurité de l'agent ont empêché de recevoir
   une réponse) ; `LLMTimeoutError` -> 504, enregistré avant le plus général
   `LLMError` -> 502 (Starlette résout les gestionnaires en parcourant le MRO de
   l'exception, donc l'enregistrement le plus spécifique l'emporte) ;
   `MalformedOutputError` -> 502 (le fournisseur a répondu, mais n'a jamais produit de
   sortie valide même après les réessais de `complete_structured()`). Tout ce qui
   n'est *pas* nommé ici ressort encore comme le 500 ordinaire de FastAPI - avaler des
   exceptions inconnues cacherait de vrais bugs, cela ne les traiterait pas.
7. **Le rôle voyage comme un en-tête, jamais comme un champ du corps de requête.**
   `AskRequest` n'a aucun champ `role` - `X-User-Role` est une dépendance
   (`get_role`), hors bande par rapport à la question, la même discipline que pour
   chaque racine en liste blanche et chaque rôle lié depuis les Épisodes 5/10. Prouvé
   de bout en bout à travers la chaîne d'injection de dépendances, pas seulement
   affirmé : `test_get_registry_binds_the_role_all_the_way_to_the_tools_own_filtering`
   appelle `get_registry()` directement (une dépendance FastAPI n'est qu'une simple
   fonction) et confirme que le `search_docs` du registre résultant ne peut toujours
   pas faire apparaître le manuel d'administration restreint pour `support_agent`.
8. **`/ingest` et `/evaluations`, honnêtes sur ce qu'ils font réellement
   aujourd'hui.** `/ingest` est réel, pas une coquille vide : il relit depuis le
   disque les docs/le code source de Loopline et reconstruit les ressources partagées
   sans redémarrer le processus, en ne les basculant sur `app.state` qu'une fois la
   reconstruction terminée, pour qu'une requête en cours ne soit pas perturbée.
   `/evaluations` renvoie `{"suites": []}` - véritablement vide, parce qu'aucune suite
   d'évaluation n'est encore enregistrée ; c'est le travail de l'Épisode 15, et ceci
   est la forme qu'il viendra remplir, pas un espace réservé prétendant exécuter
   quelque chose qui n'existe pas.

## Implémentation

- [`src/saas_copilot/tools/__init__.py`](../../src/saas_copilot/tools/__init__.py) — `SharedResources`, `build_shared_resources`, `build_registry_for_role`.
- [`src/saas_copilot/api/schemas.py`](../../src/saas_copilot/api/schemas.py) — les modèles de requête/réponse.
- [`src/saas_copilot/api/dependencies.py`](../../src/saas_copilot/api/dependencies.py) — les fournisseurs `Depends()`.
- [`src/saas_copilot/api/routes.py`](../../src/saas_copilot/api/routes.py) — `/health`, `/ask`, `/ingest`, `/evaluations`.
- [`src/saas_copilot/api/main.py`](../../src/saas_copilot/api/main.py) — `lifespan`, le middleware d'identifiant de requête, les gestionnaires d'exception.

## Exécution

```bash
pytest tests/unit/test_api.py tests/unit/test_tools_default_registry.py -v
```

## Démo en direct (sortie vérifiée)

```bash
curl http://localhost:8000/health
# {"status":"ok","docs_indexed":13}

curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"session_id": "demo", "question": "how do I create a ticket?"}'
# {"request_id":"b65f7813-...","domain":"usage",
#  "answer":"To create a ticket in Loopline, follow these steps:\n\n1. Click New
#  ticket.\n2. Enter a title and description.\n3. Submit the ticket. The ticket will
#  start in the open status with no assignee.",
#  "citations":["docs/creating-a-ticket.md#chunk-0"],"confidence":1.0,
#  "refused":false,"refusal_reason":null,"steps_taken":2,"tools_called":["search_docs"]}
# (captured with a real OpenAI-compatible provider configured; the committed default,
# LLM_PROVIDER=fake, is covered in the failure case below instead - it was never
# meant to produce a coherent answer unscripted, only this course's tests script it)

curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" \
  -H "X-User-Role: superadmin" -d '{"session_id": "demo", "question": "hi"}'
# 400 {"error":"unknown_role",
#      "detail":"unknown role: 'superadmin'. Known roles: billing_admin,
#      support_agent, support_lead","request_id":"c7eb6274-..."}

curl -D - -o /dev/null http://localhost:8000/health -H "X-Request-ID: my-own-trace-id"
# x-request-id: my-own-trace-id   <- echoed back exactly, not replaced
```

## Cas d'échec (à montrer en direct — le véritable défaut committé, sans aucune configuration)

`LLM_PROVIDER=fake` (le propre défaut du `.env.example` du dépôt) vous donne un
`FakeLLMClient` *non scripté* - sa seule réponse fixe, `"This is a fake response."`,
n'a jamais été censée constituer un JSON valide à elle seule ; chaque démo réelle de
ce cours le scripte au préalable. Appeler `/ask` sans rien configurer au-delà du
quickstart du README :

```pycon
>>> response = client.post("/ask", json={"session_id": "demo", "question": "how do I create a ticket?"})
>>> response.status_code
502
>>> response.json()
{'error': 'malformed_output',
 'detail': "no valid RouteDecision after 3 attempts: not valid JSON: Expecting value: line 1 column 1 (char 0)",
 'request_id': '859ae080-...'}
```

Exactement le comportement propre de `complete_structured()`, réessayer-puis-lever,
issu de l'Épisode 4, désormais visible sous la forme d'un 502 propre et structuré au
lieu d'une exception non gérée - la frontière a fait son travail, même dans le seul
cas où rien derrière elle ne fonctionne encore.

## Exercice

`AgentCancelledError` dispose d'une correspondance exception-vers-statut complète
(422) depuis cet épisode, mais rien dans l'API ne le déclenche jamais réellement -
`memory/orchestration.py::ask()` n'accepte pas du tout de `cancel_token` pour
l'instant. Faites-en passer un de bout en bout : ajoutez `cancel_token` à la
signature de `ask()` (en le transmettant directement à `run_agent()`, qui en accepte
déjà un), créez un nouveau `threading.Event` par requête dans le gestionnaire
`/ask`, et positionnez-le si le client se déconnecte avant que l'exécution de l'agent
ne se termine (`Request.is_disconnected()` de FastAPI, vérifié depuis une petite
tâche d'arrière-plan en course avec l'appel `asyncio.to_thread()`). Écrivez un test
prouvant qu'une exécution qui réussirait autrement est coupée en plein milieu de la
boucle lorsque le jeton se déclenche.

## Suite

L'Épisode 15 couvre l'évaluation et l'observabilité : jeux de données de référence
(golden datasets), tests de réponse/citation/refus/contrôle d'accès, une vérification
« preuve requise avant de répondre » spécifiquement pour les questions
`bug`/`feature`, des traces, la latence, l'utilisation de tokens, des diagnostics de
recherche, et des logs respectueux de la vie privée. `/evaluations` obtient enfin
quelque chose de réel à rapporter.
