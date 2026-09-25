# Épisode 4 — Décisions, routage et workflows

**À l'écran :** quatre questions d'exemple sur un tableau blanc/une slide — une de
type usage, une de type bug, une de type feature, une ambiguë — avant tout code.

## Objectif d'apprentissage

Décider *de quel genre de question il s'agit* avant de décider *comment y répondre*.
Cette séparation est ce qui rend le reste du cours praticable : le spécialiste des
bugs (Épisode 6) n'a jamais à se demander « attends, est-ce que c'est en fait une
demande de fonctionnalité ? ».

## Points à aborder

1. **Classifier, router, exécuter, synthétiser.** La forme en quatre étapes que suit
   tout ce projet capstone : classifier la question (cet épisode), router vers le bon
   spécialiste et les bons outils (les outils de l'Épisode 5, la boucle de
   l'Épisode 6), exécuter ces outils, synthétiser les preuves en un `Answer`
   (Épisode 3, réutilisé). Aujourd'hui, c'est l'étape un, isolée.
2. **Workflows déterministes vs agents en forme libre.** `classify()` ne laisse pas
   le modèle décider de ce qui se passe après sa réponse — c'est le *code* qui
   examine `decision.domain` et choisit un chemin. C'est cela, un workflow : une
   forme fixe que le LLM remplit, pas un agent décidant librement de sa prochaine
   étape. Nous restons sur ce terrain jusqu'à l'Épisode 10 ; l'Épisode 11 est le
   premier endroit où le modèle obtient une réelle latitude, et même alors, elle
   reste bornée.
3. **Un second schéma, pas un plus gros.** `RouteDecision` (`domain`, `rationale`)
   aurait pu se résumer à « utiliser simplement `Answer` avec des citations vides ».
   Rejeté délibérément — cela aurait fait mentir `citations` et `confidence` sur ce
   que le routage a réellement produit. Un schéma plus étroit et honnête vaut mieux
   qu'un schéma partagé rembourré de champs hors de propos.
4. **Généraliser sur le second cas d'usage.** `parse_answer()`/`complete_structured()`
   de l'Épisode 3 étaient codées en dur pour `Answer`. Le routeur avait besoin de la
   logique identique de parse-validation-nouvelle-tentative pour `RouteDecision`,
   donc cet épisode commence par un refactor : `parse_structured(raw, schema)` /
   `complete_structured(client, messages, schema)`. Observez le diff — ce sont les
   mêmes lignes, simplement paramétrées, et la suite de tests complète (les 31 tests
   préexistants) passe toujours sans modification, prouvant que le refactor
   préservait le comportement.

## Implémentation

- [`src/saas_copilot/structured.py`](../../src/saas_copilot/structured.py) —
  refactor : les fonctions spécifiques à `Answer` deviennent génériques par rapport
  au schéma. **Commitez ceci séparément** de la nouvelle fonctionnalité ci-dessous,
  pour que « refactor » et « feature » restent faciles à relire et à annuler
  indépendamment.
- [`src/saas_copilot/prompts.py`](../../src/saas_copilot/prompts.py) — `ROUTER_SYSTEM_PROMPT`.
- [`src/saas_copilot/router/`](../../src/saas_copilot/router/) — `RouteDecision` (schema.py), `classify()` (classify.py).

## Exécution

```bash
pytest tests/unit/test_structured.py tests/unit/test_router.py -v
```

## Cas d'échec (à montrer en direct)

```pycon
>>> from saas_copilot.llm.fake import FakeLLMClient
>>> from saas_copilot.router import classify
>>> client = FakeLLMClient(response='{"domain": "urgent", "rationale": "sounds important"}')
>>> classify(client, "the export button is broken")
Traceback (most recent call last):
    ...
saas_copilot.structured.MalformedOutputError: no valid RouteDecision after 3 attempts:
JSON did not match the RouteDecision schema: 1 validation error for RouteDecision
domain
  Input should be 'usage', 'bug', 'feature' or 'general' [type=literal_error, input_value='urgent', input_type=str]
    For further information visit https://errors.pydantic.dev/2.13/v/literal_error
```

`"urgent"` a l'air d'un domaine plausible — ce n'est simplement pas l'un des quatre
que le reste du système sait gérer. Le rejeter ici, bruyamment, vaut mieux que de
router silencieusement vers `general` et de répondre discrètement moins bien.

## Exercice

`classify()` dépense toujours un appel LLM complet, même pour les quatre noms de
domaine qu'elle renvoie systématiquement. Ajoutez un chemin rapide : un
`KEYWORD_HINTS: dict[str, Domain]` regroupant quelques mots déclencheurs évidents
(par ex. `"crash"`, `"error"`, `"traceback"` → `bug`) qui, en cas de correspondance
exacte de sous-chaîne, renvoie un `RouteDecision` avec `rationale="keyword match"`
*sans* appeler le LLM du tout. Écrivez un test prouvant que le chemin rapide
n'incrémente pas `client.call_count`. (C'est une véritable optimisation de
coût/latence, pas seulement un exercice — l'Épisode 15 mesurera à quelle fréquence
elle se déclenche réellement.)

## Suite

L'Épisode 5 donne au copilote quelque chose vers quoi router : des outils en lecture
seule sur les docs, le code source, l'historique git, la base de données, et les logs
de Loopline.
