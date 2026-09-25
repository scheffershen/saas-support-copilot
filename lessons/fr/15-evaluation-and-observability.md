# Épisode 15 — Évaluation et observabilité

**À l'écran :** la suite golden, exécutée en direct contre un vrai modèle - 4 réussis, 3
échoués, avec les raisons exactes de chaque échec. Puis une modification délibérée du
prompt, la même suite relancée - un cas qui réussissait un instant plus tôt échoue
désormais avec `"expected domain 'usage', got 'general'"`. Puis la modification
annulée, et la suite de nouveau au vert.

## Objectif d'apprentissage

Chaque spécialiste est testé contre des fixtures réelles depuis l'Épisode 5 - mais
toujours avec un `FakeLLMClient` qui rejoue un script, ce qui prouve que la *mécanique*
fonctionne, jamais que l'*agent* est bon. Cet épisode ajoute l'autre moitié : un
ensemble organisé de vraies questions avec des attentes vérifiables (un golden
dataset), exécuté contre le modèle réellement configuré, plus assez d'observabilité -
latence, usage de tokens, une ligne de log structurée - pour remarquer qu'un problème
survient sans avoir à fixer les messages bruts.

## Points à aborder

1. **Les golden datasets sont des données, pas du code de test.** `evals/golden.py::GOLDEN_CASES`
   est une liste de `GoldenCase` (Pydantic, comme tout schéma à une frontière de
   confiance depuis l'Épisode 3) - sept vraies questions posées contre de vraies
   fixtures Loopline déjà construites par les épisodes précédents : les docs de
   l'Épisode 0, le bug injecté de l'Épisode 0, le graphe d'appels de l'Épisode 9 (via le
   spécialiste feature), le RBAC de l'Épisode 10, le verrou d'intention destructrice de
   l'Épisode 12.
2. **Ce qu'une exécution golden peut prouver, et ce qu'elle ne peut pas, énoncé
   clairement.** `evals/runner.py::run_case` appelle `run_agent()` - exactement le même
   point d'entrée que tout autre test utilise, jamais une seconde implémentation. Un
   test piloté par `FakeLLMClient` (`tests/unit/test_evals.py`) prouve que la logique de
   succès/échec du *runner* est correcte - un cas censé échouer échoue bien, pour la
   raison énoncée. Cela ne dit rien sur la qualité des réponses d'un vrai modèle ; c'est
   une question en direct, traitée plus bas, pas un test committé et déterministe - la
   même distinction que l'Épisode 13 établissait sur ce qu'un client scripté peut
   prouver.
3. **« Preuve requise » n'est pas re-vérifié - il ne peut pas être contourné.** Aucun
   code de `run_case` ne re-vérifie que le spécialiste bug/feature a bien rassemblé des
   preuves. Ce n'est pas nécessaire : un cas bug/feature qui a atteint un résultat
   *réussi* est déjà passé par le verrou de `MissingEvidenceError` (Épisode 6/11) - un
   cas réussi **est** la preuve, ce n'est pas quelque chose que le framework
   d'évaluation réimplémente.
4. **Des traces, via un wrapper, pas une réécriture.** `telemetry/trace.py::TracingLLMClient`
   enveloppe le `LLMClient` configuré, quel qu'il soit, en accumulant l'`Usage` de
   chaque appel qu'il effectue - `run_agent()`, `classify()`, `complete_structured()`
   ignorent son existence. Même principe que l'espion `received_messages` de
   `FakeLLMClient` depuis l'Épisode 2 : envelopper, ne pas re-câbler.
5. **Latence et usage de tokens, sur `/ask` lui-même.** Un `TracingLLMClient` neuf par
   requête (l'usage répond à « combien a coûté *cette* requête », pas un total sur la
   durée de vie), chronométré autour de l'appel `asyncio.to_thread()` de l'Épisode 14.
   Les deux valeurs voyagent désormais dans `AskResponse` et `SuiteResult`.
6. **Diagnostics de retrieval, au niveau que cette trace peut honnêtement supporter.**
   Pas de scores de similarité par candidat - le type de retour de `search_docs` ne les
   transporte pas, et les exposer serait un changement plus profond que la portée de cet
   épisode. Ce qui est réel et exploitable à la place : `tools_called` (est-ce que
   `search_docs` a même été invoqué) et `citations_count` (combien de sources ont
   réellement étayé la réponse) - une limite assumée, pas un oubli.
7. **Des logs préservant la vie privée, en ne capturant pas la partie sensible au
   départ.** La signature de `telemetry/trace.py::log_run` n'a aucun paramètre
   `question`/`answer` - domaine, compteurs et timings suffisent à déboguer et
   surveiller une exécution sans jamais détenir de contenu de conversation
   potentiellement sensible. (Si un système choisissait quand même de logger le contenu
   brut pour un débogage plus poussé, c'est `redact_secrets` de l'Épisode 13 qui devrait
   s'exécuter dessus d'abord - pas nécessaire ici, car le contrôle le plus simple
   consiste justement à ne pas le logger.)
8. **`/evaluations` fait enfin quelque chose.** `GET /evaluations` liste les vraies
   suites et leur taille (`{"golden": 7}`) ; `POST /evaluations/{suite}/run` en exécute
   réellement une, à travers le `LLMClient` avec lequel ce serveur est configuré,
   déportée sur un thread comme `/ask` puisqu'elle effectue de vrais appels modèle
   potentiellement lents.

## Implémentation

- [`src/saas_copilot/evals/schema.py`](../../src/saas_copilot/evals/schema.py) — `GoldenCase`, `CaseResult`, `SuiteResult`.
- [`src/saas_copilot/evals/runner.py`](../../src/saas_copilot/evals/runner.py) — `run_case`, `run_suite`.
- [`src/saas_copilot/evals/golden.py`](../../src/saas_copilot/evals/golden.py) — le dataset de sept cas.
- [`src/saas_copilot/telemetry/trace.py`](../../src/saas_copilot/telemetry/trace.py) — `TracingLLMClient`, `UsageTotals`, `log_run`.
- [`src/saas_copilot/api/routes.py`](../../src/saas_copilot/api/routes.py) — `/ask` gagne latence/tokens ; `/evaluations` (GET) et `/evaluations/{suite}/run` (POST).

## Exécution

```bash
pytest tests/unit/test_evals.py tests/unit/test_telemetry.py tests/unit/test_api.py -v
```

## Démo en direct (sortie vérifiée — un vrai modèle, gpt-4o-mini, non scripté)

```bash
curl http://localhost:8000/evaluations
# {"suites":{"golden":7}}

curl -X POST http://localhost:8000/evaluations/golden/run
```
```json
{"suite":"golden","total":7,"passed":4,"failed":3,"tokens_used":25965,"results":[
  {"case_id":"usage-create-ticket","passed":true,"failures":[]},
  {"case_id":"bug-notification-crash","passed":false,
   "failures":["MaxStepsExceededError: exceeded max_steps=6 without a final answer"]},
  {"case_id":"feature-self-assign","passed":false,"failures":[
    "expected an answer, got a refusal: There is insufficient information available...",
    "expected a citation containing 'app/services.py', got []"]},
  {"case_id":"general-out-of-scope-refusal","passed":true,"failures":[]},
  {"case_id":"rbac-runbook-hidden-from-support-agent","passed":false,"failures":[
    "MalformedOutputError: no valid AgentStep after 3 attempts: ...
     Input should be a valid dictionary or instance of Answer [type=model_type,
     input_value='There is no information...', input_type=str]"]},
  {"case_id":"rbac-runbook-visible-to-support-lead","passed":true,"failures":[]},
  {"case_id":"destructive-intent-refused-without-a-model-call","passed":true,"failures":[]}
]}
```

Trois découvertes réelles, non mises en scène, pour lesquelles une suite golden
*existe* : le spécialiste bug a bouclé au-delà de `max_steps` sur la question du crash
de notification au lieu de converger ; le spécialiste feature a refusé au lieu
d'évaluer, sapant sa propre collecte de preuves ; et, une fois, le modèle a renvoyé une
simple chaîne de caractères là où le schéma `AgentStep` attendait un objet `Answer`
complet, correctement capturé par la boucle de relance de `complete_structured()` et
correctement signalé comme `MalformedOutputError` plutôt qu'une mauvaise réponse
silencieuse. Rien de tout cela n'était préparé à l'avance - c'est exactement ce qu'un
ensemble de questions organisé trouve sur un système réel et fonctionnel, ce qui est
toute la raison d'en avoir un.

## Cas d'échec (l'exigence réelle du plan de cours — démontrer une régression de prompt)

Une ligne modifiée dans `prompts.py::ROUTER_SYSTEM_PROMPT` - la définition du domaine
`usage` remplacée par une instruction de ne jamais le sélectionner :

```diff
- usage: "how do I...", "what is...", "where do I find..." - using the product as it
-  exists today.
+ usage: never select this domain under any circumstances; always prefer "general"
+  instead, even for "how do I..." questions.
```

Même suite, même modèle, relancée :

```json
{"case_id":"usage-create-ticket","passed":false,
 "failures":["expected domain 'usage', got 'general'"]}
```

Un cas qui réussissait un instant plus tôt échoue désormais, avec la raison exacte -
`usage-create-ticket` est passé de `passed: true` à un routage complètement erroné.
Annulé immédiatement (`git checkout -- src/saas_copilot/prompts.py`), vérifié propre,
suite de nouveau verte. C'est exactement à cela que sert le golden dataset : non pas
prouver que le système est parfait (il ne l'est pas, voir plus haut), mais faire en
sorte qu'une régression de comportement de prompt soit quelque chose qu'un diff
attrape, pas quelque chose qu'un utilisateur signale en production trois semaines plus
tard.

## Exercice

`run_suite()` enregistre `tokens_used` pour la suite entière, mais rien ne met en
correspondance le coût d'un cas *spécifique* - un cas avec une conversation
anormalement longue (de nombreuses étapes de boucle réactive, ou le cycle
plan-exécute-évalue d'une question feature) peut coûter bien plus qu'une question
usage en un seul coup, de façon invisible. Ajoutez un champ `tokens_used: int` à
`CaseResult` lui-même (enveloppez le client à neuf par *cas* dans `run_case`, pas une
seule fois par suite dans `run_suite`), et écrivez un test prouvant qu'un cas qui
appelle un outil coûte plus de tokens qu'un cas qui répond directement sans en
appeler.

## Suite

L'Épisode 16 couvre le déploiement local et la reproductibilité : Docker Compose avec
MySQL, un index vectoriel local, des migrations, des sauvegardes, des secrets gardés
hors du contrôle de version, des vérifications au démarrage, et des sondes de santé -
`query_database` (Épisode 12) est enfin câblé à une vraie instance MySQL via un serveur
MCP, correspondant à la vraie base de données cible de Loopline au lieu du bouche-trou
SQLite utilisé jusqu'ici par tout ce cours.
