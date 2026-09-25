# Épisode 11 — Planification et travail multi-étapes : la faisabilité des fonctionnalités

**À l'écran :** la question « could we let anyone self-assign a ticket? » - et, comme
annoncé par l'Épisode 4, le moment de ce cours où le modèle est enfin amené à décider
de quelque chose qui va au-delà du simple choix du prochain outil à appeler.

## Objectif d'apprentissage

La boucle réactive de l'Épisode 6 décide une étape à la fois, en réagissant à ce
qu'elle vient d'observer. C'est la bonne approche pour un rapport de bug. C'est la
mauvaise approche pour « évaluer si c'est faisable » - cette question bénéficie d'une
réflexion en amont : quelles preuves permettraient de trancher, dans quel ordre, avant
même de dépenser le moindre appel d'outil. Donnez au spécialiste `feature` un workflow
qui planifie d'abord.

## Points à aborder

1. **Les plans comme données structurées.** `FeaturePlan` (`planning/plan.py`) est un
   modèle Pydantic, pas une chaîne que le modèle rédige librement - une liste de
   `PlanStep`, chacun avec un `tool`, des `arguments`, un `depends_on` et un
   `rationale`. Même discipline que pour `Answer` et `AgentStep` : valider la forme
   avant de lui faire confiance.
2. **Actions atomiques, ordonnancement par dépendances.** Chaque `PlanStep` correspond
   à un seul appel d'outil. Le `model_validator` d'un plan rejette une référence
   `depends_on` orpheline, un `step_id` en double, ou un cycle (y compris une simple
   boucle sur soi-même) - en exécutant réellement `topological_order()` (l'algorithme
   de Kahn) et en laissant une vraie `ValueError` se propager jusque dans la boucle de
   réessai que fournit déjà `complete_structured()`. Un *plan* mal formé est corrigé de
   la même façon qu'une *Answer* mal formée.
3. **Workflow séquentiel.** Une fois validé, le plan s'exécute dans l'ordre des
   dépendances - démontré, pas supposé :
   `test_plan_executes_in_dependency_order_not_json_order` place délibérément l'étape
   dépendante en premier dans le JSON scripté, et vérifie `tools_called` (l'ordre
   d'exécution réel) plutôt que de faire confiance à l'ordre du JSON lui-même.
4. **Un compromis assumé, pas dissimulé.** Rien ici ne permet aux `arguments` d'une
   étape ultérieure de référencer le *résultat* d'une étape précédente - le plan
   entier est rédigé en amont, avant qu'aucune preuve ne revienne. `depends_on`
   contrôle l'*ordre*, pas le *flux de données*. C'est une vraie marge de manœuvre
   perdue par rapport à la boucle réactive de l'Épisode 6, capable d'adapter chaque
   étape à ce qu'elle vient d'observer. L'exercice de cet épisode consiste à combler
   cet écart.
5. **Workflow évaluateur-optimiseur.** Un second jugement, indépendant
   (`FeasibilityEvaluation`), vérifie le brouillon d'`Answer` par rapport à une grille
   de critères - présence de citations, une affirmation « isolée » étayée par une
   véritable vérification `query_graph` des appelants, pas de surconfiance - et peut le
   renvoyer pour exactement une révision.
6. **Une révision qui est recontrôlée, pas simplement acceptée sur parole.** La
   première version de cette boucle pouvait réviser une fois et livrer le résultat
   *sans jamais le réévaluer* - ce qui annule tout l'intérêt d'avoir un évaluateur.
   Corrigé en écrivant les tests : chaque révision est recontrôlée avant d'être
   livrée ; si le budget s'épuise sur une réponse toujours rejetée, elle est livrée
   quand même (elle a déjà franchi la porte des preuves et constitue une `Answer`
   valide) - un effort borné, pas une garantie d'approbation.
7. **La même porte des preuves, appliquée à un plan plutôt qu'à une boucle.** Le
   `required_evidence_tools` du spécialiste `feature` (Épisode 6/9) est inchangé - ce
   qui change, c'est *comment* il est vérifié : contre les appels d'outils réussis du
   plan, et non contre ceux d'une boucle pas à pas.

## Implémentation

- [`src/saas_copilot/agent_types.py`](../../src/saas_copilot/agent_types.py) — `AgentRunResult` et ses erreurs, extraits pour que `agent.py` et `planning/` n'aient pas à s'importer mutuellement.
- [`src/saas_copilot/tools/formatting.py`](../../src/saas_copilot/tools/formatting.py) — `format_tool_result`, partagé de la même façon.
- [`src/saas_copilot/tools/registry.py`](../../src/saas_copilot/tools/registry.py) — `ToolRegistry.describe()`.
- [`src/saas_copilot/planning/plan.py`](../../src/saas_copilot/planning/plan.py) — `PlanStep`, `FeaturePlan`, `topological_order`.
- [`src/saas_copilot/planning/schema.py`](../../src/saas_copilot/planning/schema.py) — `FeasibilityEvaluation`.
- [`src/saas_copilot/planning/feasibility.py`](../../src/saas_copilot/planning/feasibility.py) — `assess_feasibility`.
- [`src/saas_copilot/agent.py`](../../src/saas_copilot/agent.py) — `run_agent` aiguille "feature" vers ce chemin plutôt que d'exécuter la boucle réactive.

## Exécution

```bash
pytest tests/unit/test_planning_plan.py tests/unit/test_planning_feasibility.py \
       tests/unit/test_agent.py -v
```

## Démo en direct (sortie vérifiée)

```pycon
>>> # plan JSON lists "callers" (depends on "find") BEFORE "find" itself
>>> result = assess_feasibility(client, registry, "could we let anyone self-assign a ticket?", specialist=feature)
>>> result.tools_called
('search_code', 'query_graph')   # "find" ran first, despite JSON order - topological_order() resorted it
>>> result.answer.answer
'Only support_lead can currently assign tickets to others; letting anyone self-assign would touch assign_ticket and its one caller.'
```

## Cas d'échec (à montrer en direct)

```pycon
>>> assess_feasibility(client, registry, "could we add dark mode?", specialist=feature)
# plan only calls search_docs - not in feature's required_evidence_tools
MissingEvidenceError: feature specialist's plan didn't include a successful call to one of ['list_files', 'query_graph', 'read_source', 'search_code']
```

Planifier à l'avance n'assouplit pas la règle des preuves - cela déplace simplement
*quand* elle est vérifiée, de « après chaque étape » à « après l'exécution du plan
entier ».

## Exercice

Comblez l'écart mentionné au point 4 : permettez aux `arguments` d'un `PlanStep` de
référencer le résultat d'une étape précédente via un espace réservé (par exemple
`"{{find.first_match_path}}"`), résolu juste avant l'exécution de cette étape, une fois
que ses dépendances ont déjà été exécutées. Écrivez un test avec un plan où les
arguments de l'étape B ne peuvent littéralement pas être connus avant que le résultat
réel de l'étape A ne revienne - prouvant que la résolution a lieu au moment de
l'exécution, pas au moment de la génération du plan.

## Suite

L'Épisode 12 dote les questions à forme d'écriture (« how do I deactivate this
account ») d'une véritable porte d'approbation - expliquer une action et être digne de
confiance pour l'exécuter sont deux choses différentes.
