# Recette de mise en service

Protocole à dérouler **sur le site**, matériel branché, avant de laisser
l'observatoire tourner sans surveillance. Chaque case cochée est une preuve,
pas une impression.

Durée indicative : 1 h 30, dont 30 min de mouvements réels.

---

## 0. Préparation

- [ ] Toit **débrayé ou sur cales** pour les premiers essais moteur, puis
      remis en prise pour les mesures de trajet.
- [ ] Arrêt d'urgence physique accessible (coupure de l'alimentation moteur).
- [ ] NINA fermé, Arduino IDE fermé.
- [ ] Sauvegarde de `%ProgramData%\ObservatoryServer\config\settings.json`.
- [ ] Noter la date, l'opérateur, la version (`/api/health` → `version`).

---

## A. Installation

- [ ] Lancer `ObservatoryServer-Setup-3.0.0.exe`, accepter l'UAC.
- [ ] Cocher démarrage automatique et règle de pare-feu.
- [ ] **Attendu** : icône verte près de l'horloge ; `Program Files\ObservatoryServer`
      existe ; `%ProgramData%\ObservatoryServer` contient `config`, `logs`, `state`.
- [ ] Vérifier le raccourci du dossier Démarrage.
- [ ] `netsh advfirewall firewall show rule name="ObservatoryServer (Alpaca)"`
      → règle active, profils Domaine et Privé.

---

## B. Démarrage en simulation

À ce stade, `simulation` doit être **vrai** : aucun mouvement réel.

- [ ] `http://localhost:11111/ui/` s'ouvre, badge « simulation ».
- [ ] Ouvrir/Arrêter/Fermer répondent, l'état change et la position progresse.
- [ ] Sur un `OPEN` puis `CLOSE` immédiat : refus 1035 « mouvement opposé ».
- [ ] Arrêter, puis Fermer : accepté.
- [ ] Les journaux se remplissent (bouton **Journaux**), dates au format
      `jj-mm-aaaa hh:mm:ss`.

---

## C. Alpaca et NINA

- [ ] `http://localhost:11111/management/v1/configureddevices` liste
      **Toit roulant** et **Sécurité météo**.
- [ ] Dans NINA, connecter les deux devices via Alpaca (`127.0.0.1:11111`).
- [ ] Laisser tourner 5 minutes.
- [ ] **Attendu** : aucun 404 dans `server.log`, NINA affiche Closed au repos.
- [ ] `CanFindHome` et `CanSlave` faux, `CanPark` vrai.
- [ ] Depuis NINA : Open shutter → état Opening → Open ; Close shutter →
      Closing → Closed.

---

## D. Toit réel

- [ ] Décocher `simulation`, régler `serial_port` (COM4), Enregistrer,
      **Redémarrer**.
- [ ] **Attendu** : `/api/health` → `link.connected = true`, description
      `COM4@115200` ; état cohérent avec la position physique.
- [ ] Mesurer le trajet d'ouverture au chronomètre, noter : ______ s.
- [ ] Mesurer le trajet de fermeture, noter : ______ s.
- [ ] Reporter la valeur la plus longue dans `full_travel_time`, arrondie
      au-dessus.
- [ ] Vérifier `max_travel_time` ≥ trajet + 3 s, et égal à
      `ROOF_MAX_TRAVEL_MS` du firmware (50 s par défaut).
- [ ] En cours d'ouverture : `Arrêter` → arrêt immédiat, état STOPPED figé.
- [ ] Après l'arrêt, `Ouvrir` ou `Fermer` fonctionne.
- [ ] Actionner chaque fin de course à la main : l'état bascule, sans
      clignotement (anti-rebond).

---

## E. Interlock monture

- [ ] Lancer EQMOD, connecter la monture, la parquer.
- [ ] Dans l'interface : monture « parquée », commandes acceptées.
- [ ] **Déparquer** la monture.
- [ ] Tenter `Ouvrir` puis `Fermer`.
- [ ] **Attendu** : refus `MOUNT_NOT_PARKED`, alarme affichée, **aucun
      mouvement**.
- [ ] Arrêter EQMOD (monture injoignable), tenter une commande.
- [ ] **Attendu** : refus `MOUNT_UNKNOWN`, aucun mouvement.
- [ ] Reconnecter et parquer : les commandes repassent.

---

## F. Sécurité météo et agent de sauvegarde

- [ ] Vérifier le verdict dans la carte **Sécurité météo** (SAFE/UNSAFE) et
      l'âge de la mesure (0 min après démarrage).
- [ ] `safety_agent_enabled` coché, `auto_park_mount` selon l'exploitation
      (coché pour un site non surveillé).

**Test de fermeture automatique** (à faire toit ouvert, temps sec) :

- [ ] Ouvrir le toit, attendre l'état `OPENED`.
- [ ] Dans la carte **Sécurité météo**, cliquer **UNSAFE** (verdict forcé
      10 min).
- [ ] **Attendu** : bandeau « Météo forcée », carte rouge, et l'agent ferme
      le toit dans les 15 s (journal `Agent de sauvegarde : closed`).
- [ ] Cliquer **Réel** pour revenir au verdict mesuré.
- [ ] Vérifier qu'Alpaca suit : `/api/v1/safetymonitor/0/issafe` passe à
      `false` pendant le forçage, puis revient à `true`.

**Test de refus avec monture en séquence** (toit ouvert) :

- [ ] Forcer **UNSAFE**, puis déparquer la monture avant que l'agent n'agisse.
- [ ] **Attendu** : l'agent ne peut pas fermer, alarme
      `ROOF_UNSAFE_NOT_PARKED`, toit **immobile**. C'est le comportement voulu
      avec `close_anyway = false`.
- [ ] Revenir à **Réel**, parquer la monture.

**Test de non-décision sans données** :

- [ ] Arrêter l'application, supprimer `state\roof_state.json` n'est pas
      nécessaire : au redémarrage, avant la première mesure, l'état
      météo est inconnu.
- [ ] **Attendu** : aucune fermeture intempestive avant la première mesure.

**Test de panne du fournisseur** (optionnel, si coupure réseau possible) :

- [ ] Couper l'accès Internet, attendre le cycle de mise à jour.
- [ ] **Attendu** : le verdict reste celui de la dernière mesure, puis passe
      UNSAFE (`DONNEES PERIMEES`) au-delà de `weather_max_age_minutes`.

---

## G. Atelier Arduino

- [ ] Carte : Nano (ou ancien bootloader / Uno selon le matériel), port COM4.
- [ ] **Compiler** → succès, 4 484 octets de flash annoncés.
- [ ] **Téléverser** → succès, « Controleur repond : … » à la fin.
- [ ] Pendant le téléversement : le toit ne bouge pas, la liaison revient
      seule, aucune alarme persistante.
- [ ] Modifier un réglage Arduino (par exemple `roof_pwm_min`), compiler :
      la taille change, la compilation réussit.
- [ ] Rétablir la valeur.
- [ ] Tenter un téléversement **toit en mouvement** : refus explicite.

---

## H. Robustesse

- [ ] Bouton **Redémarrer** de l'interface : serveur de retour en moins de
      15 s, état conservé, liaison rétablie.
- [ ] Débrancher puis rebrancher l'USB de l'Arduino : la liaison se rétablit
      seule (sans redémarrer l'application).
- [ ] Fermer l'application (icône → Quitter) : le serveur s'arrête, le port
      11111 est libéré.
- [ ] Relancer : une seule icône, pas de doublon.
- [ ] Vérifier `server.log`, `tray.log`, `roof.log`, `meteo_log.txt` : dates
      complètes, pas de lignes tronquées.

---

## I. Nuit de validation

- [ ] Laisser tourner une nuit complète, sans intervention.
- [ ] Le lendemain :
  - [ ] aucune alarme non expliquée ;
  - [ ] trajets conformes aux mesures (pas de dérive) ;
  - [ ] journaux cohérents, moins de 48 h conservées ;
  - [ ] l'application a survécu à la mise en veille / reprise si le PC en fait.

---

## Fiche de recette

| | |
|---|---|
| Date | |
| Opérateur | |
| Version | |
| Trajet ouverture | ______ s |
| Trajet fermeture | ______ s |
| `full_travel_time` retenu | ______ s |
| `max_travel_time` / firmware | ______ s |
| Anomalies rencontrées | |
| Recette validée | ☐ oui ☐ non |

**Critère de réussite** : toutes les cases A à H cochées, aucun mouvement
inattendu, aucune alarme inexpliquée après la nuit de validation.
