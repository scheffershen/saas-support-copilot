# Prompter cette construction — comment ces 19 épisodes ont vraiment été écrits

**À l'écran :** pas du code — le `git log --oneline` de ce dépôt lui-même (75 commits
réels) et l'instruction de deux mots qui en a produit la plupart :
`Continue to Episode N.`

## Pourquoi ce document existe

Chaque leçon de ce cours enseigne l'architecture, la sécurité et la discipline de
vérification à travers du vrai code fonctionnel. Aucune d'elles ne dit qui a tapé ce
code. Celle-ci, si : chaque ligne de `src/saas_copilot/`, chaque test, chacun des 18
autres documents de leçon, a été produite par une seule personne dirigeant un agent de
codage IA (Claude Code) en langage naturel — jamais en tapant une implémentation à la
main. Ce n'est pas une mise en garde à mentionner une fois puis à oublier. Cela mérite
sa propre leçon, parce que *comment* diriger un agent à travers une construction
réelle, multi-sessions, est une compétence distincte et apprenable, et la construction
de ce dépôt en est un témoignage honnête et complet — pas une hypothèse.

## L'affirmation qu'il faut préciser

« Plus personne n'écrit de code à la main » exagère - beaucoup le font encore, et le
feront toujours là où cela compte le plus. Mais la tendance est réelle, et il vaut la
peine de se demander ce qu'elle change concrètement ici. Reprenez n'importe quelle
leçon de ce cours — `resolve_within_root()` de l'Épisode 5, `eligible_indices()` de
l'Épisode 10, l'enveloppe uniforme `DATA_HEADER` de l'Épisode 13. Aucun de leurs points
à aborder n'explique *comment taper une fonction Python*. Chacun explique *pourquoi* :
pourquoi une restriction de l'ensemble de candidats l'emporte sur un filtre a
posteriori, pourquoi supprimer un texte suspect corrompt un contenu légitime qui en
parle, pourquoi un verrou de preuve doit rejeter un appel d'outil qui a *échoué* comme
preuve, pas seulement exiger *un* appel d'outil quelconque. C'est la partie qui ne
s'évapore pas quand un agent IA écrit l'implémentation — c'est la partie qu'il faut
comprendre assez bien pour *savoir la demander correctement*, et la partie qu'il faut
savoir reconnaître quand la sortie de l'agent se trompe discrètement. La culture
architecturale et le fait de bien prompter ne sont pas des compétences concurrentes.
La première est ce qui rend la seconde possible.

## Points à aborder

1. **Des règles permanentes, posées une fois, valables pour toute la construction —
   c'est ce qui fait fonctionner un prompt de deux mots.** « Continue to Episode N » a
   été, presque mot pour mot, l'instruction entière pour la plupart de ce cours. Cela
   ne fonctionne que parce qu'une poignée de règles ont été établies une fois, tôt, et
   n'ont jamais eu besoin d'être répétées : chaque épisode livre du code *et* des
   tests *et* un document de leçon ; chaque affirmation d'un document de leçon est
   vérifiée contre une vraie sortie avant d'être écrite, jamais inventée ; rien ne
   passe à l'épisode N+1 sans cette instruction explicite. Un prompt court appuyé sur
   un contrat explicite et durable produit un résultat discipliné. Un prompt court
   sans contrat derrière produit ce que l'agent devine que vous vouliez dire.
2. **Un prompt, un changement ciblé et testé — pas « construire tout le système ».**
   Personne n'a jamais demandé « l'agent ». Le nombre de tests a grandi une étape
   vérifiable à la fois : 3 → 9 → 18 → 31 → 38 → 80 → 94 → 117 → 158 → 174 → 191 → 207
   → 241 → 267 → 280 → 297 → 305, à travers exactement autant de vrais commits que de
   capacités. Un prompt délimité à une seule capacité révisable produit un diff qu'on
   peut réellement lire de bout en bout avant de lui faire confiance. « Construire un
   pipeline RAG avec contrôle d'accès et une boucle d'agent » ne le permet pas.
3. **Exiger la vérification, à chaque fois — « faites-moi confiance » n'est pas une
   réponse acceptable de la part d'un agent, pas plus que de la part d'une personne.**
   Chaque section « Démo en direct » et « Cas d'échec » de chaque leçon est une vraie
   sortie capturée, pas une prose décrivant ce qui se passerait probablement. Le
   graphe d'appels de l'Épisode 9 a été vérifié interactivement contre le vrai code
   source de Loopline *avant* qu'un seul test soit écrit. La découverte `localhost`
   contre `127.0.0.1` de l'Épisode 16 — un vrai délai de connexion de 5 secondes — a
   été mesurée, pas supposée. Si l'affirmation d'un agent sur sa propre sortie ne peut
   pas être ré-exécutée et re-vérifiée, traitez-la comme non vérifiée, parce qu'elle
   l'est.
4. **Détecter l'excès de confiance en vérifiant la trace, pas seulement la
   narration.** Cela s'applique de façon récursive, et l'Épisode 18 en a capturé un
   vrai exemple : le texte de réponse du vrai modèle en direct affirmait *« une
   vérification query_graph... montre »* — et `tools_called` pour cette requête
   valait en réalité `["search_code"]`. La trace est ce qui est vérifiable ; la prose
   est une affirmation. La même discipline s'applique un niveau plus haut, à un agent
   de codage IA qui raconte ce qu'il a fait — lire le diff, exécuter les tests, ne pas
   prendre le résumé pour la vérification.
5. **Corriger les dérives par écrit, ne pas réécrire silencieusement l'histoire.**
   Quand l'Épisode 8 a changé le comportement de `Document.citation`, la leçon de
   l'Épisode 1 a reçu un addendum daté, pas une modification silencieuse. Quand
   l'Épisode 17 a fermé une lacune que l'Épisode 10 avait explicitement différée, la
   leçon de l'Épisode 10 a reçu le même traitement. Un agent capable de réécrire
   silencieusement ses propres affirmations antérieures pour coller à la nouvelle
   réalité est un agent dont on ne peut plus faire confiance à l'historique — la
   solution est une correction visible, à chaque fois, pas une réécriture plus
   présentable.
6. **Enquêter sur un état inconnu avant d'y toucher — un agent devrait par défaut
   faire preuve de la même prudence qu'un ingénieur consciencieux.** Une entrée
   `.gitmodules` et un répertoire `video-production` sont apparus en plein cours, sans
   rapport avec ce travail. La bonne réponse a été de vérifier de quoi il s'agissait
   (l'outillage séparé propre à l'utilisateur) avant de faire quoi que ce soit, puis
   d'utiliser des commits limités par pathspec pour le reste du cours afin que rien de
   tout cela ne puisse être balayé par accident dans un commit sans rapport.
7. **Le prompt n'est pas la frontière de sécurité — pour un agent de codage non
   plus.** Ce cours consacre les Épisodes 3, 12 et 13 à prouver qu'un LLM suivra une
   mauvaise instruction aussi volontiers qu'une bonne, et que la vraie sécurité vient
   de la validation, des contrats en lecture seule et des tests, pas du fait de
   demander gentiment. La même propriété tient un niveau plus haut : un agent dirigé
   pour « juste faire que ça marche » fera exactement cela, y compris en coupant des
   coins qu'un prompt soigné aurait exclus d'avance. Le vrai filet de sécurité de
   cette construction a été la règle permanente (point 1), l'humain relisant chaque
   diff avant qu'il soit poussé, et une vraie suite de tests qui devait rester verte.
8. **Rien de tout cela ne remplace les points 1 à 7 des 18 autres leçons — cela en
   dépend.** Vous ne pouvez pas demander à un agent de fermer une lacune que vous ne
   savez pas décrire. Vous ne pouvez pas reconnaître une mauvaise réponse dont vous
   ignorez qu'elle est mauvaise. « Ajouter un contrôle d'accès basé sur les rôles » et
   « restreindre l'ensemble de candidats avant le classement, pas après, pour qu'une
   paraphrase ne puisse pas récupérer un document restreint » demandent à un agent des
   choses très différentes, et une seule des deux est l'Épisode 10. La connaissance
   architecturale n'est pas la partie que ce cours enseigne *autour* du prompting —
   c'est la partie qui rend le prompting possible.

## Exercice

Choisissez trois épisodes quelconques de ce cours et, sans regarder comment ils ont
réellement été construits, écrivez ce que vous pensez que l'instruction réelle a dû
préciser pour produire ce diff exact, ce nombre exact de tests, et ce document de
leçon exact — pas « ajouter le RBAC » mais la propriété réellement appliquée et
comment vous sauriez qu'elle a été correctement implémentée. Comparez ensuite avec ce
qu'un prompt nu « ajouter un contrôle d'accès » aurait plausiblement produit à la
place. L'écart entre ces deux résultats est la vraie compétence dont parle ce
document.

## Suite

Il n'y a pas d'épisode suivant — ce document se place aux côtés des 19 épisodes, pas à
l'intérieur de leur séquence. Lisez-le d'abord si vous commencez par
[l'Épisode 0](00-setup.md), ou en dernier si vous venez de terminer
[le capstone](18-capstone-demonstration.md) ; il parle de la construction entière, pas
d'une seule étape.
