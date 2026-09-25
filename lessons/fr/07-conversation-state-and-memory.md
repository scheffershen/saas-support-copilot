# Épisode 7 — État de conversation et mémoire

**À l'écran :** deux questions tapées l'une après l'autre — « quels statuts un ticket
peut-il avoir ? » puis « qui peut les changer ? » — la seconde n'ayant aucun sens sans
la première.

## Objectif d'apprentissage

`run_agent()` de l'épisode 6 repart de zéro à chaque appel. Lui donner un endroit où
se souvenir d'une conversation, sans prétendre que « se souvenir de cette discussion »
et « se souvenir de cet utilisateur » sont le même problème.

## Points à aborder

1. **Contexte vs. état de session vs. mémoire long terme — trois choses
   différentes.** Le *contexte* est ce qui est réellement envoyé au LLM lors d'un
   appel (`Session.as_context()` — une tranche bornée). L'*état de session* est
   l'intégralité de la conversation en cours pour une discussion (`Session.turns` —
   qui peut être plus long que ce qui tient dans le contexte ; rien ici ne raccourcit
   en cours de session pour l'instant, c'est un exercice légitime). La *mémoire long
   terme* regroupe des faits qui survivent à la conversation elle-même (`UserMemory`
   — indexée par `user_id`, pas par `session_id`). Confondre tout cela en un seul
   blob « mémoire » est la meilleure façon de se retrouver incapable de répondre à
   « supprimer ma discussion oublie-t-il aussi ma préférence de rôle ? ».
2. **Rétention.** `Session.add_turn()` réduit à la limite des `max_turns` derniers
   échanges à chaque ajout, pas via une tâche de nettoyage séparée qu'on risque
   d'oublier de planifier. Un historique illimité est à la fois un coût qui croît
   indéfiniment et une part croissante de la conversation d'une personne conservée
   en mémoire sans raison active.
3. **Suppression.** `SessionStore.delete()` et `UserMemoryStore.forget_all()` sont
   deux contrôles utilisateur différents avec deux significations différentes,
   prouvées indépendantes par un test, pas seulement affirmées dans une docstring :
   supprimer une conversation ne doit pas pouvoir effacer qui est l'utilisateur, et
   oublier des faits à long terme ne doit pas supprimer son historique de
   discussion.
4. **En mémoire pour l'instant, une interface pour plus tard.** `SessionStore` est
   une ABC ; `InMemorySessionStore` est la seule implémentation que ce cours livre,
   et elle est perdue au redémarrage - c'est ce que signifie « prototype local »
   ici. Un déploiement réel y substitue un stockage adossé à SQL ou Redis derrière
   exactement la même interface ; `ask()`, `run_agent()`, et tout ce qui se trouve
   au-dessus n'auraient pas à changer.
5. **Le routeur a besoin de l'historique aussi.** « qui peut les changer ? » n'est
   pas routable isolément. `classify()` (épisode 4) prend désormais `history=`, tout
   comme l'étape spécialiste - les deux moitiés de la boucle voient la même
   conversation, pas seulement la moitié qui répond.
6. **Un enrobage léger, pas un nouveau chemin.** `ask()` ne réimplémente ni
   n'assouplit rien de ce que `run_agent()` impose déjà -
   `test_ask_does_not_bypass_the_agent_loops_evidence_rule` prouve qu'un spécialiste
   `bug` ne peut toujours pas contourner la règle de preuve simplement parce que
   `ask()`, et non `run_agent()` directement, est le point d'entrée.

## Implémentation

- [`src/saas_copilot/memory/session.py`](../../src/saas_copilot/memory/session.py) — `Turn`, `Session`.
- [`src/saas_copilot/memory/store.py`](../../src/saas_copilot/memory/store.py) — `SessionStore`, `InMemorySessionStore`.
- [`src/saas_copilot/memory/user_memory.py`](../../src/saas_copilot/memory/user_memory.py) — `UserMemory`, `UserMemoryStore`, `InMemoryUserMemoryStore`.
- [`src/saas_copilot/memory/orchestration.py`](../../src/saas_copilot/memory/orchestration.py) — `ask()`.
- [`src/saas_copilot/router/classify.py`](../../src/saas_copilot/router/classify.py) / [`src/saas_copilot/agent.py`](../../src/saas_copilot/agent.py) — les deux prennent `history=` désormais.

## Exécution

```bash
pytest tests/unit/test_memory_session.py tests/unit/test_memory_user_memory.py \
       tests/unit/test_memory_orchestration.py -v
```

## Démo en direct (sortie vérifiée, pas illustrative)

```pycon
>>> ask(client, registry, store, "demo-session", "what statuses can a ticket have?").answer.answer
'Statuses are open, in_progress, resolved, closed.'
>>> ask(client, registry, store, "demo-session", "who can change them?").answer.answer
'A support_agent or support_lead can change them.'
>>> len(store.get("demo-session").turns)
2
>>> store.delete("demo-session")
>>> store.get("demo-session")
None
```

La seconde réponse n'a de sens que parce que le routeur et le spécialiste ont tous
deux vu la première question et sa réponse comme historique - poser la même question
de relance à une session neuve, et elle n'a rien contre quoi résoudre « les ».

## Exercice

`Session.turns` n'a aucune limite sur sa *taille* totale - seules les évaluations de
l'épisode 15 remarqueront si une poignée d'échanges très longs dépasse ce qui tient
dans le contexte, même avec `max_turns`. Ajoutez une limite
`Session.as_context(max_turns=..., max_chars=...)` qui élimine d'abord les échanges
les plus anciens jusqu'à ce que le contexte rendu tienne, et un test avec quelques
faux échanges délibérément longs prouvant qu'elle raccourcit effectivement.

## Suite

L'épisode 8 rend `search_docs` et `read_source` réellement performants en recherche —
découpage, embeddings, reranking — au lieu de la simple recherche par comptage de
termes de l'épisode 5.
