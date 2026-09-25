# Épisode 6 — La boucle d'agent

**À l'écran :** un schéma de boucle sur tableau blanc — question → routage → (appel
d'outil ⟲) → réponse — dessiné avant tout code, puis construit.

## Objectif d'apprentissage

Tout ce qui s'est passé depuis l'épisode 3 n'était qu'un seul appel LLM à la fois. Cet
épisode est celui où ces appels se connectent en une boucle que le modèle pilote
réellement : `router.classify()` choisit un domaine, `specialists.get_specialist()`
indique quelles preuves ce domaine exige, et le modèle choisit, une étape à la fois,
s'il doit appeler un outil ou répondre.

## Points à aborder

1. **Observer → décider → agir → observer.** À chaque itération : le modèle
   *décide* (`AgentStep`), la boucle *agit* (`registry.call()`) s'il a choisi un
   outil, et le résultat devient l'*observation* suivante (`Message(role="user",
   content="Tool result: ...")`) que le modèle *observe* au tour suivant.
   `run_agent()` est une simple boucle `for` sur ce cycle - pas de framework, parce
   qu'il n'y a rien ici qu'une boucle `for` n'exprime pas déjà clairement.
2. **Transitions d'état.** Deux états seulement : `call_tool` et `final_answer`. Le
   `model_validator` d'`AgentStep` rend une combinaison invalide (par exemple
   `action="call_tool"` sans `tool_call`) irreprésentable, la même discipline que la
   règle refusé/citations d'`Answer` à l'épisode 3.
3. **Nombre maximal d'étapes.** `for step_number in range(1, max_steps + 1)` - pas
   `while True`. Une boucle qui pourrait théoriquement tourner indéfiniment a besoin
   d'une raison qui l'*autorise* à continuer, pas d'une raison qui finit par
   l'arrêter.
4. **Garde-fous contre les appels répétés.** `seen_calls` suit des paires
   (outil, arguments-json-triés). Le même appel exact deux fois signifie que le
   modèle ne progresse pas malgré la nouvelle information - `RepeatedToolCallError`
   le signale au lieu de brûler cinq étapes identiques supplémentaires.
5. **Erreurs d'outil.** Une `ToolError` venant de `registry.call()` ne fait pas
   planter la boucle - elle devient `"Tool error: ..."` comme observation suivante,
   et le modèle a l'occasion d'essayer autre chose.
   `test_loop_continues_after_a_tool_error_instead_of_crashing` prouve qu'elle
   atteint une véritable réponse malgré une première tentative échouée.
6. **La règle de preuve a des dents.** Les spécialistes `bug`/`feature`
   (`required_evidence_tools` de l'épisode 5) ne peuvent pas faire `final_answer`
   sans un appel **réussi** à l'un de leurs outils requis - et un appel *échoué* ne
   compte pas (`test_a_failed_tool_call_does_not_count_as_evidence`). « J'ai essayé
   de vérifier et ça a échoué » n'est pas non plus une preuve.
7. **Annulation.** `cancel_token: threading.Event` est vérifié avant l'appel au
   routeur et avant chaque étape - une exécution déjà annulée ne fait aucun travail,
   pas « un appel gaspillé avant de s'en apercevoir ». L'épisode 14 y branchera la
   véritable déconnexion d'une requête.
8. **Une troisième utilisation de `complete_structured()`.** `Answer` (ép. 3),
   `RouteDecision` (ép. 4), maintenant `AgentStep`. Trois sites d'appel réels pour la
   même mécanique généralisée de parsing-validation-retry, zéro logique de retry
   dupliquée.
9. **Le prompt est généré, pas écrit à la main.** `_initial_messages()` construit le
   menu d'outils à partir de `registry.specs()` - ajoutez un septième outil plus
   tard, et le prompt du modèle le connaît déjà ; il n'y a pas de second endroit où
   se souvenir de le mettre à jour.

## Implémentation

- [`src/saas_copilot/agent.py`](../../src/saas_copilot/agent.py) — `AgentStep`, `ToolCall`, les quatre sous-classes d'`AgentError`, `run_agent()`, `AgentRunResult`.

## Exécution

```bash
pytest tests/unit/test_agent.py -v
```

Chaque test fait tourner le *véritable* registre d'outils sur le *véritable*
`sample_app/loopline/` de ce dépôt (`build_default_registry`) - seules les réponses
du LLM sont scriptées. Quand le scénario « bug » réussit, `search_code` a réellement
tourné sur `notifications.py`.

## Cas d'échec (à montrer en direct)

```pycon
>>> # bug specialist tries to answer immediately, no tool call first
>>> run_agent(client, registry, "why does commenting on ticket 4 crash?")
MissingEvidenceError: bug specialist tried to answer without calling one of ['git_log', 'git_show', 'read_source', 'search_code'] first
```

Le texte de réponse du modèle (« probablement un plantage dû à un contrôle de nullité
manquant ») sonne même plausible. C'est exactement pour cette raison que ça ne peut
pas rester une simple suggestion - une supposition sûre d'elle-même et un fait cité se
lisent de façon identique en prose.

## Exercice

Rien n'empêche actuellement le `answer.domain` d'un `final_answer` de contredire le
spécialiste qui l'a produit - un spécialiste `bug` pourrait renvoyer
`answer.domain="feature"` sans que `run_agent()` ne le remarque. Ajoutez une
vérification dans la branche `final_answer` qui lève une nouvelle sous-classe
d'`AgentError` (`DomainMismatchError`) quand ils diffèrent, ainsi qu'un test prouvant
qu'un domaine incohérent est rejeté.

## Suite

L'épisode 7 ajoute la mémoire : pour l'instant, chaque appel à `run_agent()` repart de
zéro.
