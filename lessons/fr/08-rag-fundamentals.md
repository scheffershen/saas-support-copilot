# Épisode 8 — Fondamentaux du RAG

**À l'écran :** le `search_docs` de l'épisode 5 notant une requête par simple
comptage de termes, juste à côté de cette même requête sur le point de passer par
BM25 + embeddings à la place.

## Objectif d'apprentissage

La génération augmentée par récupération (RAG) tient en quatre étapes réelles, pas un
simple import de bibliothèque : découper le texte en morceaux assez petits pour être
utiles, transformer chaque morceau en quelque chose de comparable à une requête,
classer selon cette comparaison, et combiner plusieurs méthodes de classement quand
elles sont en désaccord. Construire ces quatre étapes à partir de rien, une fois pour
toutes, pour que le « RAG » cesse d'être une boîte noire.

## Points à aborder

1. **Ingestion et normalisation.** `normalize_text()` corrige les fins de ligne et
   supprime les marqueurs de titre Markdown - une question de mise en forme, pas de
   contenu - avant que quoi que ce soit d'autre ne touche au texte. Un détail
   minime, mais c'est le premier endroit où une mauvaise entrée se transforme
   silencieusement en une mauvaise recherche.
2. **Découpage.** Des chunks de taille fixe avec chevauchement (`chunk_text()`).
   Trop grands, et une vraie réponse se dilue dans du texte environnant hors sujet ;
   trop petits, et elle perd son contexte ; le chevauchement évite qu'une phrase à
   cheval sur une frontière de chunk ne soit coupée en deux. `getting-started.md`,
   le plus long document Loopline, se divise véritablement en 2 chunks à la taille
   de 300 caractères retenue pour ce cours - ce n'est pas un exemple artificiel.
3. **Recherche BM25 en texte intégral.** `BM25Index` est un véritable BM25 Okapi
   construit à partir de rien, pas un appel de bibliothèque : la saturation de la
   fréquence de terme (la 10e occurrence d'un terme compte bien moins que sa 1re) et
   la normalisation par longueur (un document long n'est pas plus pertinent
   simplement parce qu'il contient plus de mots) - les deux choses que le scoring
   par simple comptage de termes de l'épisode 5 faisait mal.
4. **Embeddings.** `EmbeddingClient` reprend le schéma `LLMClient` de l'épisode 2,
   appliqué à un nouveau problème - dépendre de « quelque chose qui vectorise du
   texte », jamais d'un fournisseur. `HashingEmbeddingClient` est la valeur par
   défaut du cours : déterministe, hors ligne, la même philosophie que
   `FakeLLMClient`. Il obtient la *mécanique* de la recherche vectorielle correcte
   mais n'a aucune véritable compréhension sémantique - un vrai manque, documenté,
   pas caché.
5. **Reranking / recherche hybride.** Les scores BM25 et les similarités cosinus
   vivent sur des échelles incomparables, donc `reciprocal_rank_fusion()` combine
   des *rangs*, pas des scores bruts - la même technique qu'utilise la recherche
   hybride d'Elasticsearch.
6. **Citations.** `Document.citation` signifie désormais quelque chose :
   `docs/getting-started.md#chunk-0` et `#chunk-1` sont deux morceaux véritablement
   différents et récupérables du même fichier.

## Deux vrais bugs, trouvés en construisant ceci

Même discipline qu'à l'épisode 5 : aucun des deux n'a été planté, tous deux ont
surgi en exécutant les tests.

**Un faux positif dû à un mot vide.** Tester « aucune correspondance » avec la
requête `"xyzzy-not-a-real-term"` a produit une correspondance - et pas une de faible
confiance. Ses « not » et « a » sont entrés en collision de hachage avec des mots
courants dispersés dans tous les documents, lui donnant une similarité sémantique
*plus élevée* avec un article sans rapport qu'une requête authentique n'en obtenait
face au bon document. Corrigé avec une courte liste de mots vides dans le tokeniseur
de `HashingEmbeddingClient`.

**Le bug plus profond que le filtrage des mots vides n'a pas corrigé.** Même avec du
vrai charabia (`"zzqvxlpfmnbwortkugh"`, ne partageant aucun vocabulaire avec quoi que
ce soit), `search_hybrid` continuait de renvoyer des résultats. `_semantic_ranking`
n'avait aucun plancher de pertinence - il classait *tous* les chunks par similarité
cosinus, y compris les chunks se trouvant à exactement `0.0`. La « recherche »
sémantique ne pouvait jamais que réordonner l'ensemble du corpus, jamais vraiment ne
rien trouver. Corrigé avec un plancher `min_similarity`
(`DEFAULT_MIN_SIMILARITY = 0.05`) appliqué avant le classement, pas après.

## Implémentation

- [`src/saas_copilot/retrieval/normalize.py`](../../src/saas_copilot/retrieval/normalize.py) — `normalize_text`.
- [`src/saas_copilot/retrieval/chunking.py`](../../src/saas_copilot/retrieval/chunking.py) — `chunk_text`.
- [`src/saas_copilot/retrieval/bm25.py`](../../src/saas_copilot/retrieval/bm25.py) — `BM25Index`.
- [`src/saas_copilot/retrieval/embeddings.py`](../../src/saas_copilot/retrieval/embeddings.py) — `EmbeddingClient`, `cosine_similarity`.
- [`src/saas_copilot/retrieval/hashing_embeddings.py`](../../src/saas_copilot/retrieval/hashing_embeddings.py) — `HashingEmbeddingClient`.
- [`src/saas_copilot/retrieval/rrf.py`](../../src/saas_copilot/retrieval/rrf.py) — `reciprocal_rank_fusion`.
- [`src/saas_copilot/retrieval/index.py`](../../src/saas_copilot/retrieval/index.py) — `DocumentIndex`.
- [`src/saas_copilot/tools/docs.py`](../../src/saas_copilot/tools/docs.py) / [`tools/__init__.py`](../../src/saas_copilot/tools/__init__.py) — `search_docs` rebranché sur l'index.
- [`src/saas_copilot/models.py`](../../src/saas_copilot/models.py) — `Document.citation` inclut désormais toujours le suffixe de chunk (voir la note de l'épisode 1).

## Exécution

```bash
pytest tests/unit/test_retrieval_normalize.py tests/unit/test_retrieval_chunking.py \
       tests/unit/test_retrieval_bm25.py tests/unit/test_retrieval_embeddings.py \
       tests/unit/test_retrieval_rrf.py tests/unit/test_retrieval_index.py \
       tests/unit/test_tools_docs.py -v
```

## Cas d'échec (réel, tiré du développement de cet épisode)

```pycon
>>> len(index)   # 5 docs, 7 chunks - getting-started.md and roles-and-permissions.md each split in two
7
>>> index.search_semantic("zzqvxlpfmnbwortkugh", min_similarity=-1.0)   # the old, floor-less behavior
[<all 7 chunks, "ranked" at exactly 0.0 similarity>]
>>> index.search_semantic("zzqvxlpfmnbwortkugh")   # today's default floor
[]
```

Un « classement » sans plancher n'est pas une recherche. C'est juste une opinion
d'ordonnancement sur des éléments qui n'ont jamais été des candidats pour commencer.

## Exercice

`DEFAULT_MIN_SIMILARITY = 0.05` a été choisi en observant les chiffres de ce corpus
précis, pas dérivé de quelque chose de principié - exactement le genre de nombre
magique qu'un vrai système calibre sur des données plutôt qu'à l'œil. Construisez un
minuscule jeu d'évaluation « est-ce que ça correspond » (5 à 10 paires
requête/document-attendu couvrant les docs de Loopline) et balayez quelques valeurs
de seuil face à ce jeu, en choisissant celle qui sépare le mieux les vraies
correspondances du bruit. (Aperçu complet de l'épisode 15 - c'est cette même idée à
la plus petite échelle possible.)

## Suite

L'épisode 9 ajoute un second paradigme de récupération à côté de celui-ci : un
graphe d'appels léger sur le code source de Loopline lui-même, pour les questions que
la recherche textuelle ne sait pas bien traiter (« qu'est-ce que modifier cette
fonction casserait ? »).
