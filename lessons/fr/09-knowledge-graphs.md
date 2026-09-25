# Épisode 9 — Graphes de connaissances pour les relations de code

**À l'écran :** la question « pourrait-on laisser n'importe qui s'auto-assigner un
ticket ? » - et la fonction `services.assign_ticket` dont elle dépend, sans aucun
indice visible sur qui d'autre l'appelle.

## Objectif d'apprentissage

La recherche textuelle répond à « où ce mot apparaît-il ». Elle ne peut pas répondre à
« qu'est-ce que modifier cette fonction casserait » - c'est une question sur la
*structure*, pas sur le *contenu*. Construire le second paradigme de récupération
dont ce cours a besoin : des entités et les relations entre elles, pas des documents
et des chunks.

## Points à aborder

1. **Entités et relations vs. documents et chunks.** Le `DocumentIndex` de l'épisode
   8 traite tout comme du texte à classer. `CallGraph` traite les fonctions de
   Loopline comme des *nœuds* et les « appels » comme des *arêtes* - une forme de
   question fondamentalement différente : non pas « qu'est-ce qui est pertinent pour
   cette requête » mais « qu'est-ce qui est connecté à cette chose ».
2. **Analyse statique avec `ast`.** Pas de regex, pas de recherche de chaînes sur
   les lignes d'import - `CallGraph` analyse de véritables arbres syntaxiques Python
   et résout les appels comme Python lui-même le ferait : repli sur le même module,
   et les véritables champs `level`/`module` d'`ast.ImportFrom` pour les imports
   relatifs (`from .models import X` contre `from ..services import Y` se résolvent
   différemment, correctement, parce que les fichiers `routers/` de Loopline se
   trouvent un niveau de package plus profond que ses modules de premier niveau).
3. **Graphes d'appels.** Deux passes, pas une seule : collecter d'abord tous les
   nœuds, puis n'enregistrer une arête que lorsque l'appelé se résout vers un nœud
   *déjà connu*. C'est ce qui exclut correctement `session.add(...)`,
   `session.commit()`, et les appels de décorateur `@router.post(...)` du graphe,
   sans traiter SQLAlchemy ou FastAPI comme des cas particuliers par leur nom - ils
   ne correspondent tout simplement jamais à une fonction définie par Loopline.
4. **Quand la structure l'emporte sur la recherche textuelle.**
   `search_code("assign_ticket")` trouve chaque *mention* du texte
   « assign_ticket » - y compris la chaîne dans une docstring ou un commentaire.
   `query_graph("services.assign_ticket", "callers")` trouve chaque endroit qui
   l'*appelle* réellement. Pour « qu'est-ce que ce changement affecterait », cette
   distinction est toute la réponse.
5. **Une vraie limite, assumée.** Pas de répartition dynamique, pas d'appels via une
   variable contenant une référence de fonction, pas de résolution de
   `self.method()`. Le code de Loopline lui-même n'utilise rien de tout ça, donc le
   graphe construit à partir de lui est complètement exact pour cette base de code -
   une base plus grande ou plus dynamique nécessiterait un outil plus lourd. Dit
   clairement, pas édulcoré.
6. **Le spécialiste `feature` devient plus affûté.** `query_graph` rejoint
   `read_source`/`search_code`/`list_files` comme preuve qu'il peut rassembler, et
   son prompt indique désormais de vérifier les appelants avant de qualifier un
   changement d'« isolé ». Prouvé via la véritable boucle d'agent, pas seulement
   déclaré : `test_feature_specialist_can_satisfy_evidence_via_query_graph` route
   une question de faisabilité, appelle réellement `query_graph`, et répond.

## Implémentation

- [`src/saas_copilot/graph/call_graph.py`](../../src/saas_copilot/graph/call_graph.py) — `CallGraph`, `FunctionNode`.
- [`src/saas_copilot/tools/graph.py`](../../src/saas_copilot/tools/graph.py) — l'outil `query_graph`.
- [`src/saas_copilot/tools/__init__.py`](../../src/saas_copilot/tools/__init__.py) — le graphe construit une seule fois au démarrage du registre, comme l'index de documents de l'épisode 8.
- [`src/saas_copilot/specialists/`](../../src/saas_copilot/specialists/) — l'ensemble de preuves et le prompt de `feature` mis à jour.

## Exécution

```bash
pytest tests/unit/test_graph_call_graph.py tests/unit/test_tools_graph.py \
       tests/unit/test_specialists.py tests/unit/test_agent.py -v
```

Chaque arête attendue dans `test_graph_call_graph.py` a été trouvée en exécutant
réellement le constructeur de graphe sur le vrai code source de Loopline et en
imprimant d'abord son résultat - y compris deux arêtes d'injection de dépendances
(`routers.tickets._session` / `routers.users._session` → `database.get_session`)
qu'un traçage manuel du code source n'avait même pas anticipées.

## Cas d'échec (à montrer en direct)

```pycon
>>> query_graph("assign_ticket", graph=graph)   # missing the "services." qualifier
ToolError: unknown symbol: 'assign_ticket'. Known symbols: database.get_session,
main._ensure_schema, main.health, notifications._settings_by_user,
notifications.notify_assignee_on_comment, routers.tickets._session,
routers.tickets.add_comment, routers.tickets.assign, routers.tickets.create_ticket,
routers.tickets.get_ticket, routers.tickets.list_tickets, routers.users._session,
routers.users.list_users, seed.seed, services.assign_ticket
```

Un nom deviné, non qualifié, échoue bruyamment avec la véritable liste, au lieu de
renvoyer silencieusement un résultat vide (et trompeusement « aucun appelant »).

## Exercice

`CallGraph` ne suit que les appels de fonctions au niveau module - il n'a aucune idée
que `sample_app/loopline/docs/assigning-tickets.md` *parle* de
`services.assign_ticket`, alors même qu'un humain lisant les deux les relierait
instantanément. Ajoutez une méthode `doc_references()` qui effectue un simple
appariement de mots-clés (le texte normalisé d'un document contient-il le nom nu
d'une fonction ?) entre les chunks de `DocumentIndex` et les nœuds de `CallGraph`, et
un test prouvant que `assigning-tickets.md` se lie à `services.assign_ticket`. C'est
exactement la « référence croisée doc↔code » que le plan du cours esquisse -
délibérément laissée pour que vous la construisiez une fois que les deux moitiés
(l'index de l'épisode 8, le graphe de cet épisode) existent déjà.

## Suite

L'épisode 10 rend la récupération *consciente des permissions* : une partie de ce que
`search_docs`, `search_code`, et `query_graph` peuvent voir ne devrait pas être
visible pour tous les rôles.
