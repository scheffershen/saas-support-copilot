# Épisode 12 — Approbation humaine et refus

**À l'écran :** « Deactivate bob@loopline.example's account » - refusé, zéro appel LLM
effectué. « How do I deactivate a compromised account? » - traité normalement, en
citant le manuel d'administration.

## Objectif d'apprentissage

Chaque spécialiste, jusqu'ici, a répondu à des questions. Aucun n'a jamais été
sollicité pour *exécuter* quoi que ce soit - parce que rien de ce que cet agent peut
appeler n'écrit quoi que ce soit ; tous les outils sont en lecture seule depuis
l'Épisode 5. Mais une question peut malgré tout être *formulée* comme une commande, et
la faire transiter par le pipeline habituel serait malhonnête quant à ce qui s'est
réellement passé : rien ne serait réellement désactivé, mais une réponse fluide du LLM
pourrait facilement donner l'impression que si. Donnez à l'agent un moyen de
reconnaître cette forme de requête et de dire, en toutes lettres : « je ne peux pas
faire cela, voici qui le peut, et voici ce que je *peux* vous dire » - avant même que
la question n'atteigne un spécialiste.

## Points à aborder

1. **Une porte déterministe, pas un jugement du LLM.** `detect_destructive_intent()`,
   dans `security/intent.py`, n'est qu'une simple regex appliquée au texte brut de la
   question - aucun appel au modèle. L'Épisode 3 a déjà établi qu'un system prompt est
   une requête, pas une garantie ; une porte jugée par un modèle serait tout aussi
   contournable-par-la-parole que la chose qu'elle est censée protéger. Ceci
   s'exécute dans du code que le modèle ne touche jamais, avant même que le modèle ne
   soit invoqué pour ce tour.
2. **« You » contre « we » : le véritable signal.** Un impératif (« Deactivate... »,
   « Delete... ») ou une tournure de commande adressée à « you » débouchant
   directement sur un verbe destructeur (« can you delete... », « please disable... »)
   est une commande. « could we » / « can we » est l'idiome de question de
   fonctionnalité déjà établi par ce cours depuis l'Épisode 4 (« could we add dark
   mode? ») et n'est jamais confondu avec une commande -
   `test_a_feasibility_question_using_we_is_not_a_command` le prouve directement. La
   tournure de commande doit aussi être *directement rattachée* au verbe, pas
   simplement présente quelque part plus tôt dans la phrase - « can you check if we
   should delete stale tickets » n'est pas une commande de supprimer quoi que ce soit.
3. **La correspondance exacte du verbe règle le passé sans effort.** « deactivate »
   n'est pas « deactivated » - un rapport de bug à propos de quelque chose qui s'est
   déjà produit (`"the account got deactivated, why?"`) continue de router
   normalement vers le spécialiste `bug`, sans aucune logique de détection du temps
   grammatical. Il suffit de ne pas raciniser (stem) la liste de verbes.
4. **Deux couches indépendantes, pas une seule.** Cette porte attrape les commandes en
   langage naturel, dans du code que le modèle n'exécute jamais. Elle n'attrape *pas*
   une formulation à forme SQL déguisée en requête anodine
   (`"run this: DROP TABLE tickets"`) - prouvé directement, pas seulement affirmé
   (`test_sql_shaped_input_is_not_this_layers_job`). C'est le travail propre de
   `query_database` (point 7) - une seconde couche, indépendante, parce qu'une couche
   unique censée tout attraper finit toujours par laisser passer quelque chose.
5. **Le refus *est* le chemin d'escalade.** `build_refusal_answer()` ne se contente
   pas de dire non - il indique qui peut réellement faire cela (un humain, avec le bon
   rôle, en suivant le propre processus de Loopline) et comment obtenir une
   explication plutôt qu'un refus. Un simple « non » serait honnête mais inutile.
6. **La confirmation réutilise la mémoire plutôt que d'inventer un nouvel état.** Un
   simple « yes » après un refus ne signifie rien en soi.
   `agent.py::_confirmed_original_question()` reconnaît cette forme - une réponse
   affirmative immédiatement après un refus *émis par cette porte elle-même*, détectée
   via une chaîne marqueur fixe dans le tour précédent de l'assistant - et repose la
   question *originale*, reformulée comme une demande d'explication, en utilisant le
   `history` déjà existant de l'Épisode 7, sans nouveau champ d'état de session.
7. **De nouveaux outils, avec la même discipline que chaque outil depuis
   l'Épisode 5.** `query_database` : le caractère lecture seule est imposé deux fois -
   une vérification de préfixe n'autorisant que SELECT, pour une erreur rapide et
   claire, et la connexion SQLite elle-même ouverte en mode URI lecture seule, de
   sorte qu'une instruction ayant d'une manière ou d'une autre échappé à la regex ne
   puisse toujours pas écrire. Prouvé directement contre le vrai driver
   (`test_the_database_file_is_opened_read_only_not_just_regex_checked`), pas
   seulement supposé. `read_logs` : aucun argument de chemin - il lit toujours
   l'unique fichier de log auquel sa racine est liée au moment de la construction du
   registre, le même schéma `functools.partial` que chaque racine en liste blanche
   depuis l'Épisode 5.
8. **Le spécialiste `bug` obtient deux nouveaux moyens de rassembler des preuves.**
   `required_evidence_tools` s'enrichit de `read_logs` et `query_database` -
   vérifier des données réelles ou l'état des logs compte comme preuve, au même titre
   que lire le code source. `query_database` peut en particulier confirmer
   directement la cause profonde du bug de notification injecté :
   `notification_settings` a bien zéro ligne pour l'utilisateur 5.

## Implémentation

- [`src/saas_copilot/security/intent.py`](../../src/saas_copilot/security/intent.py) — `detect_destructive_intent`, `build_refusal_answer`, `CONFIRMATION_MARKER`.
- [`src/saas_copilot/agent.py`](../../src/saas_copilot/agent.py) — la porte et `_confirmed_original_question()`, vérifiées avant `classify()`.
- [`src/saas_copilot/tools/database.py`](../../src/saas_copilot/tools/database.py) — `query_database`, `resolve_sqlite_path`.
- [`src/saas_copilot/tools/logs.py`](../../src/saas_copilot/tools/logs.py) — `read_logs`.
- [`src/saas_copilot/tools/__init__.py`](../../src/saas_copilot/tools/__init__.py) — les deux outils enregistrés ; `loopline.db` injecté de façon idempotente au moment de la construction.
- [`src/saas_copilot/specialists/specialist.py`](../../src/saas_copilot/specialists/specialist.py) / [`prompts.py`](../../src/saas_copilot/specialists/prompts.py) — l'ensemble de preuves du spécialiste `bug` s'agrandit.

## Exécution

```bash
pytest tests/unit/test_security_intent.py tests/unit/test_tools_database.py \
       tests/unit/test_tools_logs.py tests/unit/test_agent.py \
       tests/unit/test_specialists.py tests/unit/test_tools_default_registry.py -v
```

## Démo en direct (sortie vérifiée)

```pycon
>>> detect_destructive_intent("Deactivate the account for bob@loopline.example")
DestructiveIntentMatch(verb='deactivate', question='Deactivate the account for bob@loopline.example')
>>> detect_destructive_intent("how do I deactivate a compromised account?")
None

>>> client = FakeLLMClient(responses=["SHOULD NEVER BE READ"])
>>> result = run_agent(client, registry, "Deactivate the account for bob@loopline.example")
>>> result.answer.refused, client.call_count
(True, 0)
>>> result.answer.answer
"I can't perform this action myself - every tool I can call is read-only, so there is
no way for me to actually deactivate anything. If this needs to happen right now, it
needs a human with the right role, following Loopline's own process (see the admin
runbook for account actions). If you want an explanation of the process instead - what
it involves, who can do it - just ask, for example \"how do I deactivate an
account?\", or reply \"yes\" and I'll explain this one."

>>> # user replies "yes please" - history carries the refusal from above
>>> result2 = run_agent(client2, registry, "yes please", history=history)
>>> result2.answer.refused
False
>>> [m.content for m in client2.received_messages[0] if m.role == "user"][-1]
'Explain how to do this, without performing it: Deactivate the account for bob@loopline.example'
```

```pycon
>>> registry.call("query_database", {"sql": "SELECT * FROM notification_settings WHERE user_id = 5"})
[]   # confirmed: user 5 really has no row - the seeded bug's exact root cause
>>> registry.call("read_logs", {"tail": 2, "grep": "notifications"})
['2026-09-23 09:12:30 INFO  loopline.notifications: notified user_id=2 re ticket_id=2',
 '2026-09-23 15:47:02 ERROR loopline.notifications: failed to notify assignee for ticket_id=4']
```

## Cas d'échec (à montrer en direct)

```pycon
>>> registry.call("query_database", {"sql": "DELETE FROM users"})
ToolError: query_database only allows SELECT statements
```

C'est l'erreur rapide et claire issue de la vérification de préfixe. La garantie plus
profonde est prouvée séparément, directement contre le driver, en contournant
entièrement la regex de ce code : la même URI en lecture seule à laquelle
`query_database` se connecte lève une
`sqlite3.OperationalError: attempt to write a readonly database` dès qu'on tente
d'écrire à travers elle - quel qu'ait été le texte SQL.

## Exercice

Actuellement, un refus suivi de n'importe quoi d'autre qu'une phrase appartenant à un
ensemble fixe de formulations « yes » (`_AFFIRMATIVE_RESPONSES`) retombe simplement
dans le routage ordinaire - y compris un « no » explicite. Ajoutez une gestion du
refus : reconnaissez un petit ensemble de réponses à forme « no » (`"no"`,
`"never mind"`, `"cancel"`) survenant immédiatement après le refus émis par cette
porte, et renvoyez un court accusé de clôture propre plutôt que de laisser un « no »
non routable atteindre le routeur. Écrivez un test prouvant qu'un « no » *isolé*, sans
refus préalable, reste une simple question ordinaire (non routable) - la même
propriété que
`test_a_bare_affirmative_with_no_preceding_refusal_is_not_treated_as_a_confirmation`
démontre déjà pour « yes ».

## Suite

L'Épisode 13 se défend contre une version plus difficile du même problème : la porte
de cet épisode fait confiance au fait qu'une commande tapée par l'utilisateur, dans le
tour de conversation lui-même, est bien ce qu'elle semble être. Elle ne dit rien d'une
commande cachée *à l'intérieur* d'un document, d'une ligne de log, ou d'un résultat
d'outil que l'agent lit en cours de route - un texte que l'agent n'était censé traiter
comme des instructions en aucun cas. L'injection de prompt directe et indirecte, la
séparation instructions/données, et la rédaction (redaction) des secrets sont les
sujets suivants.
