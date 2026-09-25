# Épisode 16 — Déploiement local et reproductibilité

**À l'écran :** `POST /ask` - « peux-tu confirmer à partir des données réelles si
l'assigné a une ligne notification_settings ? » - répondu correctement, en citant
`query_database`, la cause racine établie contre de **vraies données MySQL**,
atteintes via un **vrai processus de serveur MCP séparé**, construit de toutes
pièces dans cet épisode.

## Objectif d'apprentissage

Jusqu'ici, chaque épisode a exécuté `query_database` contre SQLite - un bouche-trou,
toujours nommé comme tel. Cet épisode lui donne un vrai chemin vers la base de données
cible réelle de Loopline (MySQL), accessible de deux façons - directement, et via un
serveur MCP autonome - plus l'échafaudage de déploiement qu'une vraie dépendance à une
base de données exige réellement : Docker Compose, des secrets qui ne touchent jamais
le contrôle de version, une migration honnêtement délimitée, et une sonde de santé qui
vérifie que la base de données est vraiment là, pas seulement que le processus tourne.

## Points à aborder

1. **Docker Compose pour l'infrastructure, pas pour toute l'application.**
   `docker-compose.yml` ne fait tourner que MySQL. Le copilote continue de tourner
   nativement (`uvicorn ...`, inchangé depuis l'Épisode 14) - ce projet dépend d'une
   base de données, il n'est pas façonné par elle.
2. **Des migrations, honnêtement délimitées.** `schema.sql` et `seed_data.sql`
   s'exécutent une seule fois, via le mécanisme `docker-entrypoint-initdb.d` propre à
   MySQL, contre un volume de données neuf - toute l'« histoire de migration » de ce
   cours, nommée exactement comme telle : une version de schéma, appliquée une fois,
   pas un framework. Un second *changement* de schéma plus tard nécessiterait un vrai
   outil (Alembic, Flyway) ; une seule version ne mérite pas encore ce poids.
3. **La frontière lecture-seule, version MySQL cette fois.** La connexion `?mode=ro`
   de SQLite n'a pas d'équivalent MySQL - donc `mysql-readonly-user.sh` provisionne un
   utilisateur dédié `loopline_reader` avec seulement `GRANT SELECT`, rien d'autre.
   Prouvé en direct, pas supposé : connecté en tant que cet utilisateur, un vrai
   `DELETE` a été exécuté -
   `ERROR 1142 (42000): DELETE command denied to user 'loopline_reader'@'localhost'
   for table 'users'` - le système de privilèges propre à MySQL le refusant, la même
   propriété impossible à contourner que l'Épisode 12 obtenait d'un simple flag de
   connexion.
4. **Trois backends, un seul point de dispatch.** `tools/__init__.py`, via
   `_query_database_handler()`, choisit SQLite (`tools/database.py`, inchangé), MySQL
   en processus (`tools/database_mysql.py`), ou MySQL via MCP (`tools/database_mcp.py`)
   - décidé une fois, à partir de `Settings`, jamais quelque chose qu'un argument
   d'outil pourrait choisir. `sql_safety.py::validate_select_only()` est partagé par
   les trois (et par la fonction outil du serveur MCP lui-même) - une seule
   vérification, pas trois copies qui pourraient dériver en silence.
5. **Une vraie intégration MCP, pas une simple mention de nom.** `mcp_server/server.py`
   est un vrai serveur MCP autonome (`mcp.server.fastmcp.FastMCP`), lancé comme son
   propre processus OS et contacté via stdio - le même transport qu'utilisent Claude
   Desktop et d'autres vrais clients MCP. Le client de `tools/database_mcp.py`
   effectue réellement la poignée de main (`ClientSession.initialize()`), appelle
   l'outil, et relit `result.structuredContent["result"]` - vérifié contre le
   comportement réel du SDK avant d'être écrit dans le code de ce cours, pas supposé à
   partir de la documentation.
6. **Recréé à neuf à chaque appel - une limite assumée, pas cachée.** Pas de pooling
   de connexions, pas de client persistant. Simple et correct pour un cours ; un vrai
   système garderait une session active entre les appels. Nommé explicitement dans la
   docstring de `database_mcp.py`, et dans l'exercice de cet épisode.
7. **Un import circulaire, intercepté avant livraison.** `mcp_server/server.py` a
   besoin de `tools.mysql_query`, ce qui signifie qu'importer ce module initialise
   tout le package `tools` - qui a besoin de `database_mcp.py` pour enregistrer le
   handler MCP. Si `database_mcp.py` avait importé quoi que ce soit en retour depuis
   `mcp_server`, cet import aurait atterri en plein milieu de l'initialisation et
   aurait échoué. Corrigé de la même façon que l'Épisode 11 avait corrigé son propre
   import circulaire : la constante partagée (`DATABASE_URL_ENV_VAR`) vit désormais du
   côté qui ne crée pas le cycle, et l'autre côté l'importe depuis là.
8. **`env=` remplace, il ne fusionne pas - vérifié, pas supposé.** Passer une variable
   d'environnement personnalisée au serveur MCP lancé nécessite de partir de
   `get_default_environment()` du SDK lui-même (PATH et une poignée d'autres) et d'y
   ajouter - un `env={"MY_VAR": ...}` explicite à lui seul remplace tout
   l'environnement de l'enfant, et un `python` sans `PATH` pourrait même ne pas
   démarrer. Prouvé dans les deux sens avec un serveur-sonde jetable avant d'écrire le
   vrai client.

## Implémentation

- [`docker-compose.yml`](../../docker-compose.yml) — MySQL uniquement.
- [`sample_app/loopline/mysql-readonly-user.sh`](../../sample_app/loopline/mysql-readonly-user.sh) — provisionne `loopline_reader`.
- [`src/saas_copilot/tools/sql_safety.py`](../../src/saas_copilot/tools/sql_safety.py) — vérification SELECT-only extraite et partagée.
- [`src/saas_copilot/tools/mysql_query.py`](../../src/saas_copilot/tools/mysql_query.py) — connexion+requête MySQL partagée, utilisée par les deux backends MySQL.
- [`src/saas_copilot/tools/database_mysql.py`](../../src/saas_copilot/tools/database_mysql.py) — le repli MySQL en processus.
- [`src/saas_copilot/mcp_server/server.py`](../../src/saas_copilot/mcp_server/server.py) — le serveur MCP autonome.
- [`src/saas_copilot/tools/database_mcp.py`](../../src/saas_copilot/tools/database_mcp.py) — le client MCP.
- [`src/saas_copilot/tools/__init__.py`](../../src/saas_copilot/tools/__init__.py) — le dispatch à trois voies.
- [`src/saas_copilot/api/routes.py`](../../src/saas_copilot/api/routes.py) — `/health` sonde désormais réellement la base de données.

## Exécution

```bash
# SQLite (default, no Docker):
pytest tests/unit/test_tools_sql_safety.py -v

# MySQL + MCP (needs `docker compose up -d` and LOOPLINE_READONLY_DATABASE_URL set):
pytest tests/unit/test_tools_database_mysql.py tests/unit/test_tools_database_mcp.py \
       tests/unit/test_tools_default_registry.py -v
```

## Démo en direct (sortie vérifiée)

```bash
docker compose exec mysql mysql -uloopline_reader -p"$MYSQL_READER_PASSWORD" \
  -e "USE loopline; DELETE FROM users WHERE id=1;"
# ERROR 1142 (42000): DELETE command denied to user 'loopline_reader'@'localhost'
# for table 'users'
```

```bash
curl http://localhost:8000/health   # USE_DATABASE_MCP=true, real MySQL configured
# {"status":"ok","docs_indexed":13,"database":"ok"}

curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d \
  '{"session_id": "demo16", "question": "a user reported that commenting on ticket 4
    crashes the server - can you confirm from the actual data whether the assignee
    has a notification_settings row?"}'
# {"domain":"bug","answer":"The assignee for ticket 4 does not have a corresponding
#  row in the notification_settings table, which may indicate that they are not set
#  up to receive notifications.","citations":["query_database"],"confidence":0.9,
#  "tools_called":["query_database"],"latency_ms":9657.0,"tokens_used":2820}
```

Le spécialiste bug a fait appel à `query_database` de sa propre initiative, et la
requête est passée par un vrai processus de serveur MCP séparé contre de vraies
données MySQL - ni SQLite, ni un mock.

## Cas d'échec (réel, trouvé en direct pendant la construction)

La même connexion exacte, un seul mot différent dans l'URL :

```pycon
>>> query_database_mysql("SELECT id FROM users LIMIT 1",
...     database_url="mysql+pymysql://loopline_reader:...@localhost:3306/loopline")
# took 5.094 s -> [{'id': 1}]

>>> query_database_mysql("SELECT id FROM users LIMIT 1",
...     database_url="mysql+pymysql://loopline_reader:...@127.0.0.1:3306/loopline")
# took 0.062 s -> [{'id': 1}]
```

`localhost` se résolvait d'abord vers une adresse IPv6 sur laquelle rien n'écoutait,
sur cette configuration Windows + Docker Desktop - pymysql attendait l'échec de cette
tentative avant de retomber sur IPv4. `127.0.0.1` évite entièrement la question de
résolution. Les deux connexions atteignent le même conteneur MySQL ; seule l'une des
deux gaspille cinq secondes réelles à le trouver. Corrigé en documentant `127.0.0.1`
comme hôte recommandé dans `.env.example`, pas en faisant réécrire silencieusement par
le code ce que l'appelant fournit - une réécriture surprenante et non demandée est son
propre genre de bug.

Une seconde découverte, distincte, qui mérite d'être nommée précisément tant elle
aurait été facile à dissimuler : ajouter `LOOPLINE_READONLY_DATABASE_URL` au `.env`
local de cette machine pour les tests a cassé deux tests *déjà livrés* de l'Épisode 12
- `Settings()` lit `.env` globalement, et ces tests avaient toujours implicitement
supposé SQLite sans le dire. Corrigé en rendant l'hypothèse explicite
(`Settings(loopline_readonly_database_url="")`) plutôt qu'en se souvenant de garder
l'environnement propre - la même propriété « ne pas dépendre d'un état ambiant que
l'on ne contrôle pas » dont les propres tests MySQL de cet épisode ont aussi besoin
(ignorés, pas échoués, quand cette variable est absente).

## Exercice

`database_mcp.py` relance un processus serveur neuf et effectue une poignée de main
MCP complète à *chaque* appel - nommé explicitement comme le choix
simple-mais-pas-optimal de cet épisode. Ajoutez une variante persistante : une petite
classe qui ouvre `stdio_client`/`ClientSession` une seule fois (par exemple comme
gestionnaire de contexte conservé pour la durée de vie d'un `ToolRegistry`) et le
réutilise à travers les appels. Écrivez un test prouvant que le second appel via une
session persistante est nettement plus rapide que deux appels via
`query_database_via_mcp` tel qu'il existe aujourd'hui - et réfléchissez à ce qui se
passe si le processus serveur meurt entre deux appels, ce dont la version actuelle
par appel n'a jamais à se soucier.

## Suite

L'Épisode 17 couvre l'écart entre ce prototype et un système de production : SSO,
RBAC/ABAC, isolation des tenants, frontières réseau, rétention d'audit, files d'attente,
limites de débit, sauvegardes, réponse aux incidents, coût, et modélisation des
menaces - y compris la frontière du « pointer ceci vers le code d'une vraie
entreprise », nommée dès le tout premier commit de ce cours. Produit une checklist de
préparation à la production.
