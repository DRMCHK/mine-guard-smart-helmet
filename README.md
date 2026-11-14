# MineGuard Smart Helmet — simulation Wokwi (ESP32-S3, MicroPython)
https://wokwi.com/projects/480627419507670017

Prototype de casque de sécurité pour mineur, simulé dans Wokwi. Le casque surveille en continu le gaz, la température, les chocs et les chutes, l'obstacle devant le porteur, le port du casque et un bouton SOS. Il signale le danger par une LED et un buzzer, et envoie des messages texte que la surface pourrait recevoir.

> Ce projet est une **simulation**. Les seuils sont des valeurs d'exemple, pas des normes minières. La liaison radio vers la surface (LoRa) n'est pas simulée : le terminal série de Wokwi en tient lieu.

---

## 1. Fichiers du projet

| Fichier | Rôle |
|---|---|
| `main.py` | Programme MicroPython exécuté par l'ESP32-S3 |
| `diagram.json` | Schéma du circuit : pièces et câblage |
| `README.md` | Ce document |

---

## 2. Ce que fait le casque

Le programme évalue en permanence toutes les causes de danger, puis en déduit un **niveau** :

| Niveau | LED | Buzzer | Causes possibles |
|---|---|---|---|
| **OK** | Verte fixe | Silencieux | Aucune cause active |
| **WARN** (avertissement) | Rouge, clignote lentement (1 Hz) | Bip court (80 ms) chaque seconde | Gaz élevé, température élevée, choc, casque non porté, obstacle proche |
| **ALARM** (alarme) | Rouge, clignote vite | Bips rapides | Gaz dangereux, température dangereuse, chute, SOS actif |

Une cause d'alarme l'emporte toujours sur une cause d'avertissement.

### Les neuf causes surveillées

| Code | Signification | Niveau | Condition |
|---|---|---|---|
| `GAS_W` | Gaz élevé | WARN | Tension du capteur ≥ air propre + 0,30 V |
| `GAS_A` | Gaz dangereux | ALARM | Tension du capteur ≥ air propre + 0,70 V |
| `TEMP_W` | Température élevée | WARN | ≥ 35 °C |
| `TEMP_A` | Température dangereuse | ALARM | ≥ 45 °C |
| `FALL` | Chute | ALARM (10 s) | Chute libre puis choc, voir §6.3 |
| `IMPACT` | Choc | WARN (5 s) | Accélération > 2,5 g |
| `SOS` | Appel de détresse | ALARM | Bouton SOS basculé sur « actif » |
| `NOHELM` | Casque non porté | WARN | Interrupteur « casque porté » ouvert |
| `OBST` | Obstacle proche | WARN | Distance mesurée < 30 cm |

---

## 3. Composants simulés

| Fonction | Pièce Wokwi | Rôle |
|---|---|---|
| Cerveau | ESP32-S3-DevKitC-1 (MicroPython) | Lit les capteurs, décide, commande les sorties |
| Chute et choc | MPU6050 (I2C) | Accéléromètre 3 axes |
| Gaz | Capteur MQ-2 | Sortie analogique proportionnelle au gaz |
| Température | DHT22 | Température ambiante |
| Obstacle | HC-SR04 | Distance par ultrasons |
| Appel de détresse | Bouton poussoir | SOS |
| Casque porté | Interrupteur à glissière | Fermé = porté |
| Alerte sonore | Buzzer | Bips |
| Alerte visuelle | LED rouge et LED verte, 2 résistances 220 Ω | État du casque |

**Choix par rapport au projet d'origine :** le LM35 prévu au départ n'était pas disponible dans les listes de pièces Wokwi consultées, il est remplacé par un DHT22.

---

## 4. Câblage

Tous les noms de broches ont été vérifiés contre les définitions officielles de Wokwi. Les broches GPIO de l'ESP32-S3 s'appellent simplement `1`, `2`, `4`… dans Wokwi.

| Composant | Broche du composant | Broche ESP32-S3 |
|---|---|---|
| MPU6050 | VCC / GND | 3V3 / GND |
| | SDA | GPIO8 |
| | SCL | GPIO9 |
| MQ-2 | VCC / GND | 3V3 / GND |
| | AOUT | GPIO1 |
| DHT22 | VCC / GND | 3V3 / GND |
| | SDA (données) | GPIO2 |
| HC-SR04 | VCC / GND | 5V / GND |
| | TRIG | GPIO17 |
| | ECHO | GPIO18 |
| Bouton SOS | une borne / l'autre | GPIO5 / GND |
| Interrupteur casque | borne commune (2) / borne (1) | GPIO6 / GND |
| Buzzer | pin 2 (+) / pin 1 (−) | GPIO15 / GND |
| LED rouge | résistance 220 Ω puis anode / cathode | GPIO16 / GND |
| LED verte | résistance 220 Ω puis anode / cathode | GPIO21 / GND |

**Pourquoi pas GPIO19 et GPIO20 ?** Sur l'ESP32-S3, ces deux broches servent à l'USB. Les utiliser comme sorties couperait la programmation par USB sur un vrai montage.

**Pourquoi les entrées SOS et casque sont tirées vers GND ?** Elles utilisent la résistance de rappel interne (`Pin.PULL_UP`) : le niveau au repos est 1, et un appui ou une fermeture le fait passer à 0. Aucune résistance externe n'est nécessaire.

---

## 5. Mise en route dans Wokwi

1. Crée un projet depuis le **modèle MicroPython pour ESP32-S3** (https://wokwi.com/projects/new/micropython-esp32-s3). Les onglets doivent s'appeler `main.py` et `diagram.json`. Un projet Arduino (onglet `sketch.ino`) ne convient pas : le type est fixé à la création.
2. Colle le contenu de `diagram.json` et de `main.py` dans les onglets du même nom.
3. Dans `diagram.json`, la carte `esp` doit avoir un attribut `env` qui choisit le firmware MicroPython :
   ```json
   "attrs": { "env": "micropython-20260406-v1.28.0", "flashSize": "8" }
   ```
   Cette valeur est celle du modèle au moment de la rédaction. Si ton modèle en propose une autre, **garde celle du modèle**. Sans cet attribut, ou avec une version inconnue, le programme ne démarre pas et Wokwi n'affiche aucune erreur.
4. Lance la simulation. Le terminal série doit afficher `MPU6050: OK`, `HC-SR04: OK`, puis `CAL;...` environ 2 s plus tard, et ensuite une trame `MG;...` par seconde.

---

## 6. Fonctionnement du code

### 6.1 Boucle principale non bloquante

Le programme n'utilise jamais de longue pause. À chaque tour (toutes les 5 ms), il lit l'horloge `ticks_ms()` et ne fait une tâche que si son intervalle est écoulé :

| Tâche | Intervalle | Pourquoi |
|---|---|---|
| Bouton SOS | à chaque tour (5 ms) | Réactivité de l'appui |
| MPU6050 | 20 ms (50 Hz) | Une chute libre dure quelques dixièmes de seconde, il faut échantillonner vite |
| Gaz | 200 ms (5 Hz) | Le gaz évolue lentement |
| DHT22 | 2000 ms | Limite du capteur : pas plus d'une lecture toutes les 2 s |
| HC-SR04 | 250 ms (4 Hz) | Évite que les mesures se chevauchent |
| Télémétrie `MG` | 1000 ms | Un message par seconde |

La comparaison utilise `ticks_diff(now, t_dernier)` plutôt qu'une soustraction directe, car le compteur de MicroPython finit par revenir à zéro. Le même principe s'applique aux durées de maintien des alarmes.

### 6.2 Calibration du gaz au démarrage

Je ne connais pas la courbe exacte du capteur simulé. Des seuils absolus seraient donc devinés. Le programme mesure plutôt l'air propre :

1. Il lit le capteur 20 fois en 2 s (la LED rouge et la verte restent allumées pendant ce temps).
2. Il en fait la moyenne : c'est la tension de référence `base`.
3. Il fixe les seuils à partir de cette référence :
   - avertissement = `base` + 0,30 V
   - alarme = `base` + 0,70 V
   - l'alarme est plafonnée à 3,2 V (la limite de lecture est 3,3 V) et l'avertissement reste au moins 0,1 V en dessous.

Exemple chiffré : si `base` = 1,65 V, l'avertissement se déclenche à 1,95 V et l'alarme à 2,35 V.

Conséquence importante : **le capteur doit être réglé sur une valeur d'air propre avant de lancer la simulation**. Si tu pars d'une concentration déjà élevée, elle devient la référence et les seuils sont trop hauts.

La lecture de tension se fait avec `read_u16()` (0 à 65535), donc : tension = valeur / 65535 × 3,3 V.

### 6.3 Détection de chute avec le MPU6050

**Le module de l'accélération.** Le capteur donne trois valeurs (ax, ay, az). On calcule le module :

```
g = racine(ax² + ay² + az²) / 2048
```

Au repos, seule la pesanteur agit : le module vaut environ 1 g, quelle que soit l'orientation du casque. En chute libre, il tombe près de 0. Lors du choc à l'arrivée, il monte fortement.

**Pourquoi 2048 ?** Le MPU6050 est réglé sur la plage ±16 g (écriture de `0x18` dans le registre `0x1C`). Sur cette plage, 1 g correspond à 2048 unités. Avec la plage par défaut (±2 g, 16384 unités par g), le capteur plafonne vers 2 g et le seuil de choc de 2,5 g ne pourrait jamais être atteint.

**La logique :**

1. Si `g` < 0,4 : on note l'instant (chute libre).
2. Si `g` > 2,5 : on note l'instant du choc (`IMPACT`, avertissement pendant 5 s).
3. Si ce choc arrive moins de 3 s après une chute libre : c'est une **chute** (`FALL`, alarme pendant 10 s).

Un choc seul (casque cogné contre une paroi) ne donne donc qu'un avertissement, alors qu'une chute libre suivie d'un choc déclenche l'alarme.

**Fenêtre de 3 s :** sur un vrai casque, le choc suit la chute libre en environ une seconde. La fenêtre est élargie à 3 s pour permettre la démonstration à la main avec les curseurs de Wokwi.

**À vérifier au premier lancement :** dans la trame `MG`, `g=` doit afficher environ 1,00 au repos. Si tu vois environ 0,12 (soit 1/8), le simulateur ignore la configuration de plage : remplace `ACCEL_LSB_PER_G = 2048` par `16384`.

### 6.4 Distance par ultrasons (HC-SR04)

Le programme envoie une impulsion de 10 µs sur TRIG, puis mesure la durée de l'écho avec `time_pulse_us`. Le son parcourt 0,0343 cm par µs et fait l'aller-retour, donc :

```
distance (cm) = durée / 2 × 0,0343 ≈ durée / 58
```

La mesure s'abandonne après 30 ms, ce qui correspond à une portée d'environ 5 m. Si l'écho n'arrive pas, la distance vaut `None` (affichée `NA`).

### 6.5 Bouton SOS

Le bouton fonctionne en **bascule** : un appui active le SOS, un second appui l'annule. Le programme détecte le front descendant (le passage de 1 à 0) et ignore tout nouveau front pendant 250 ms pour éviter les rebonds mécaniques.

### 6.6 Évaluation et sorties

À chaque tour, le programme construit un nombre entier où chaque cause active allume un bit (`GAS_W`, `GAS_A`, …). Cette représentation évite de manipuler des listes de texte dans la boucle rapide. Le niveau se déduit ainsi : alarme si un bit d'alarme est allumé, sinon avertissement si un bit quelconque est allumé, sinon OK.

Les clignotements se calculent à partir de l'horloge, sans pause :

- **ALARM** : `(now // 150) % 2 == 0` donne une alternance toutes les 150 ms.
- **WARN** : LED rouge sur `(now // 500) % 2`, buzzer sur `now % 1000 < 80`.

### 6.7 Mesure de température

Le DHT22 est lu toutes les 2 s. Si une lecture échoue (`OSError`), le programme garde la dernière valeur. Au démarrage, la température est supposée à 25 °C en attendant la première mesure.

---

## 7. Messages envoyés au terminal

Trois types de lignes, séparés par des points-virgules.

**`CAL` : calibration, une seule fois au démarrage**
```
CAL;base=1.65V;warn=1.95V;alarm=2.35V
```

**`EVT` : événement, à chaque changement de cause**
```
EVT;t=42;lvl=ALARM;why=GAS_A+SOS
```

**`MG` : télémétrie, une fois par seconde**
```
MG;t=43;lvl=ALARM;gas=2.41V;temp=24.0C;g=1.00;dist=120;worn=1;sos=1;why=GAS_A+SOS
```

(Les valeurs ci-dessus illustrent le format, elles ne sont pas des mesures réelles.)

| Champ | Signification |
|---|---|
| `t` | Secondes depuis le démarrage |
| `lvl` | Niveau : OK, WARN ou ALARM |
| `gas` | Tension du capteur de gaz, en volts |
| `temp` | Température, en °C |
| `g` | Module de l'accélération, en g (`NA` si le MPU6050 est absent) |
| `dist` | Distance en cm (`NA` si aucune mesure) |
| `worn` | 1 = casque porté, 0 = non porté |
| `sos` | 1 = SOS actif |
| `why` | Causes actives séparées par `+`, ou `-` si aucune |

Ce format simple est pensé pour être envoyé tel quel par une liaison radio vers un poste en surface.

---

## 8. Seuils réglables

Tous les paramètres sont regroupés en haut de `main.py`.

| Paramètre | Valeur | Rôle |
|---|---|---|
| `GAS_WARN_DELTA` | 0,30 V | Écart au-dessus de l'air propre pour l'avertissement |
| `GAS_ALARM_DELTA` | 0,70 V | Écart au-dessus de l'air propre pour l'alarme |
| `TEMP_WARN_C` / `TEMP_ALARM_C` | 35 / 45 °C | Seuils de température |
| `FREEFALL_G` | 0,4 g | En dessous : chute libre |
| `IMPACT_G` | 2,5 g | Au-dessus : choc |
| `FALL_WINDOW_MS` | 3000 ms | Délai maximal entre chute libre et choc |
| `FALL_HOLD_MS` | 10 000 ms | Durée de l'alarme de chute |
| `IMPACT_HOLD_MS` | 5000 ms | Durée de l'avertissement de choc |
| `OBSTACLE_CM` | 30 cm | Distance d'avertissement |
| `ACCEL_LSB_PER_G` | 2048 | Conversion unités vers g (plage ±16 g) |

---

## 9. Scénarios de test

| Pour tester | Action dans Wokwi | Résultat attendu |
|---|---|---|
| Démarrage normal | Lancer la simulation | LED verte, puis `lvl=OK` |
| Gaz | Augmenter la concentration (ppm) du MQ-2 | WARN puis ALARM selon l'écart |
| Température | Régler la température du DHT22 au-delà de 35 puis 45 °C | WARN puis ALARM (rafraîchi toutes les 2 s) |
| SOS | Cliquer sur le bouton | ALARM avec `SOS`; un second clic l'annule |
| Casque non porté | Basculer l'interrupteur | WARN avec `NOHELM` |
| Obstacle | Régler la distance du HC-SR04 sous 30 cm | WARN avec `OBST` |
| Choc | Cliquer sur le MPU6050 et monter un axe d'accélération au-dessus de 2,5 g | WARN avec `IMPACT` pendant 5 s |
| Chute | Mettre les trois axes à 0 (chute libre), puis moins de 3 s plus tard monter un axe à une forte valeur | ALARM avec `FALL` pendant 10 s |

---

## 10. Limites de la simulation

- **Pas de liaison radio.** Le LoRa n'est pas simulé. Le terminal série joue le rôle de la passerelle en surface.
- **Pas de géolocalisation.** Le GPS ne fonctionne pas sous terre. Localiser un mineur en galerie demanderait une autre approche (par exemple des balises à portée radio).
- **Seuils indicatifs.** Les valeurs de gaz et de température ne reposent sur aucune norme minière. Un MQ-2 est aussi un capteur large et peu sélectif : pour une application réelle, on choisirait des capteurs spécifiques (par exemple un MQ-4 pour le méthane, un MQ-7 pour le CO) avec un étalonnage.
- **Chute simulée à la main.** La fenêtre de 3 s est une concession à la démonstration manuelle.
- **Le capteur de température diffère du plan initial.** Le DHT22 remplace le LM35 uniquement parce que ce dernier n'est pas disponible dans Wokwi.

---

## 11. Passage à un vrai montage

Points à traiter si le prototype est construit physiquement :

| Sujet | Ce qu'il faut savoir |
|---|---|
| MPU6050 | Utiliser un module (GY-521). Même adresse I2C 0x68, mêmes registres |
| MQ-2 | Le module sort jusqu'à 5 V sur AOUT alors que l'ESP32-S3 lit au maximum 3,3 V. Il faut un pont diviseur, par exemple 10 kΩ en série avec 20 kΩ vers GND : 5 V × 20 / (10 + 20) = 3,33 V. Le MQ-2 demande aussi un préchauffage |
| HC-SR04 | La broche ECHO sort en 5 V : même pont diviseur avant l'entrée de l'ESP32 |
| Buzzer | Passer par un transistor (par exemple 2N2222 avec 1 kΩ sur la base) si le buzzer consomme plus de 20 mA |
| LED | Avec 220 Ω sous 3,3 V, le courant est d'environ (3,3 − 2) / 220 ≈ 6 mA : suffisant pour allumer une LED |
| Radio | Ajouter un module LoRa ou équivalent et envoyer les trames `MG` et `EVT` |
| Alimentation | Batterie 18650 avec chargeur (TP4056) et régulation adaptée |
| Température | Un DHT22 ou un LM35 conviennent, le code gère le DHT22 |

---

## 12. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| La simulation compile (ou démarre) puis rien ne se passe, aucune erreur | L'attribut `env` du firmware MicroPython manque ou n'est pas reconnu dans `diagram.json` | Reprendre la valeur `env` du modèle Wokwi (voir §5) |
| Erreurs sur `sketch.ino` et des lignes commençant par `#` | Le projet a été créé en Arduino : les commentaires Python sont lus comme du C++ | Créer un nouveau projet depuis le modèle MicroPython |
| `MPU6050: ABSENT` | Le bus I2C ne répond pas à l'adresse 0x68 | Vérifier SDA sur GPIO8, SCL sur GPIO9 et l'alimentation 3V3 |
| `HC-SR04: DESACTIVE` | `time_pulse_us` n'est pas disponible dans le firmware | Le reste fonctionne ; la distance restera `NA` |
| `NOHELM` dès le démarrage | L'interrupteur est dans la position « non porté » | Le basculer |
| `g=` affiche environ 0,12 au repos | Le simulateur ignore la plage ±16 g | Mettre `ACCEL_LSB_PER_G = 16384` |
| Les alertes gaz ne se déclenchent jamais | La concentration de départ était déjà élevée et sert de référence | Relancer avec une valeur d'air propre |

---

## 13. Idées d'évolution

- Envoyer les trames par une vraie liaison radio vers un poste de surveillance.
- Étendre le casque en un réseau de capteurs avec une analyse de risque (idée MineGuard AI).
- Ajouter la détection d'une immobilité prolongée après une chute.
