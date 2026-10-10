# Suivi des anomalies - Samba Sarr (Jarvis)

Branche : fiabilite-coeur
Derniere mise a jour : 2026-10-10

Important : la liste originale des 42 anomalies de l'audit n'a pas ete
retrouvee. Ce tableau ne contient que les anomalies traitees et verifiees
depuis la reprise. Il faudra y ajouter les autres au fur et a mesure.

## Anomalies traitees

| # | Anomalie | Fichier | Cause | Correction | Test | Commit | Statut |
|---|----------|---------|-------|------------|------|--------|--------|
| 1 | Contraintes de schema JSON non appliquees | core/ai_engine.py (_valider_arguments_outil) | Seuls les champs et les types etaient controles | Ajout de enum, minLength, maxLength, minimum, maximum | tests/test_validation_contraintes.py (7 tests) | 37df75c | Corrige et teste |
| 2 | Rejeu apres echec : diagnostics perdus, succes non verifie | core/ai_engine.py (rejouer_outil_echoue) | Succes retourne sans verification | Verification du succes avant de retourner True, diagnostics conserves | test_rejouer_outil_echoue.py (2 tests) | 37df75c, 38ad699 | Corrige et teste |
| 3 | Mission declaree terminee sans action reelle (mission af67579a) | core/validation_manager.py, core/jarvis.py | valider() ne controlait rien quand la liste de resultats d'outils etait vide | Parametre outils_attendus : une mission qui attend des outils sans resultat est rejetee | tests/test_outils_attendus.py (5 tests) | d020638 | Corrige et teste |
| 4 | Chemin complet du tool calling non teste | core/ai_engine.py | Tests uniquement par morceaux | Test avec faux fournisseur : succes prouve, fausse reussite, outil non autorise, outil qui ment | tests/test_bout_en_bout_outils.py (4 tests) | a2f2030 | Teste |
| 5 | Double execution possible lors d'un fallback | core/ai_router.py | Risque identifie, protection deja presente mais sans test | Aucune modification du code | tests/test_routeur_double_execution.py (4 tests) | a3879d6 | Protection confirmee par test |
| 6 | Politique de correction automatique non testee | core/validation_manager.py (autoriser_correction), core/coordination_manager.py | Regles correctes mais non verifiees par des tests | Aucune modification du code : seul ecrire_fichier est rejouable, une fois par demande, apres un echec de verification ; compteur remis a zero au debut de traiter_commande() | tests/test_politique_correction.py (7 tests) | 6644459 | Politique confirmee par test |
| 7 | Recursion infinie sur texte vide | core/voice_manager.py (_normaliser_transcription) | La fonction s'appelait elle-meme quand le texte etait vide | Retourne le texte tel quel | tests/test_normalisation_stt.py (4 tests) | d3bad40 | Corrige et teste (non verifie a la voix) |

## Points connus, non traites

- Arguments JSON invalides envoyes par le modele : le message d'erreur est
  renvoye au modele mais rien n'est ajoute a derniers_resultats_outils.
  Une mission est alors bloquee (sur), une conversation passe.
- Un schema dont "type" est une liste (ex. ["string", "null"]) peut
  provoquer une TypeError dans _valider_arguments_outil.
- Erreur 402 d'OpenRouter avec max_tokens=16384 : probleme de credits ou de
  facturation a examiner cote fournisseur, pas forcement un bug Python.
- signaux_echec_complet de validation_manager.py non relus : on ne sait pas si
  valider() rejette seul un message "Erreur IA apres execution".

- Normalisation vocale : "Sambassar" (en un seul mot) et "quel air" ne sont pas geres.
- Le dossier tests/ n'a pas de __init__.py : unittest discover echoue ;
  lancer les tests par nom de module.

## Non confirme

- Fonctionnement complet de tous les outils avec les vrais fournisseurs.
- Resolution de l'ensemble des problemes de l'audit precedent.
- Absence de secrets dans tout l'historique Git (seuls les fichiers
  actuellement suivis ont ete controles, aucun secret trouve).

## Reste a faire

1. Boucle de correction automatique, sans contourner les protections.
2. Problemes vocaux encore ouverts (transcription, capture audio, journaux).
3. Retrouver ou reconstituer la liste des 42 anomalies.
4. Tests du chemin complet avec de vrais fournisseurs, a faire avec precaution.
