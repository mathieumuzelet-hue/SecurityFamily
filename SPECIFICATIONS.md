# Shelter Finder — Cahier des charges

## 1. Vue d'ensemble

**Nom du projet :** Shelter Finder
**Type :** Intégration custom Home Assistant (custom_component)
**Distribution :** GitHub + HACS
**Licence :** MIT

**Objectif :** Fournir un système de mise à l'abri automatisé qui, en cas d'événement grave (tempête, séisme, attentat, conflit armé…), identifie et guide chaque membre du foyer vers le lieu sécurisé le plus adapté et le plus proche de sa position en temps réel.

---

## 2. Fonctionnalités

### 2.1 Géolocalisation des personnes

- Exploitation des `device_tracker` et `person` existants dans Home Assistant.
- Support de l'app companion HA (iOS / Android) pour la position GPS en temps réel.
- Support optionnel de trackers tiers (GPSLogger, OwnTracks, etc.).
- Rafraîchissement de position forcé lors du déclenchement d'une alerte.

### 2.2 Recherche d'abris

- Interrogation de l'API Overpass (OpenStreetMap) pour trouver les points d'abri dans un rayon configurable autour de chaque personne.
- Tags OSM ciblés :
  - `amenity=shelter`
  - `building=bunker`
  - `amenity=place_of_worship` (bâtiments en dur)
  - `railway=station` / `station=subway` (souterrains)
  - `amenity=public_building`
  - `shelter_type=*`
  - `building=civic`, `building=government`
  - Tags custom configurables par l'utilisateur
- Cache local des résultats Overpass pour fonctionner en mode dégradé (perte réseau).
- Possibilité d'ajouter des POI manuels (abri personnel, cave, voisin de confiance…) via la configuration.

### 2.3 Classification par type de menace

Chaque type de menace privilégie des abris différents :

| Menace | Abris prioritaires |
|---|---|
| Tempête / ouragan | Sous-sols, abris en dur, bâtiments publics |
| Séisme | Espaces ouverts, zones de rassemblement |
| Attentat / fusillade | Bâtiments verrouillables, sous-sols, bunkers |
| Conflit armé | Bunkers, stations de métro, caves |
| Inondation | Points en hauteur, étages supérieurs |
| Nucléaire / chimique | Bunkers, sous-sols hermétiques |

L'utilisateur peut personnaliser les priorités par type de menace dans la configuration.

### 2.4 Calcul d'itinéraire

- Calcul de distance à vol d'oiseau (Haversine) pour le tri initial.
- Intégration optionnelle avec un service de routing (OSRM auto-hébergé ou API) pour le temps de trajet réel (à pied, en voiture).
- Prise en compte du mode de déplacement par personne (configurable).

### 2.5 Carte interactive

- Carte Lovelace custom card basée sur Leaflet + tuiles OpenStreetMap.
- Affichage en temps réel :
  - Position de chaque membre du foyer (icône distincte par personne).
  - Abris à proximité (icônes par type).
  - Itinéraire recommandé (tracé sur la carte).
  - Rayon de recherche.
- Mode normal : vue d'ensemble du foyer.
- Mode alerte : vue centrée sur la personne la plus exposée, abris mis en surbrillance.

### 2.6 Système d'alerte

- Déclenchement par :
  - Bouton manuel (service HA ou bouton Lovelace).
  - Automation HA (webhook, capteur météo, détection de séisme…).
  - Intégration future possible avec FR-Alert / SAIP (API publique si disponible).
- Actions à l'alerte :
  - Forcer la mise à jour GPS de tous les device_trackers.
  - Calculer l'abri optimal pour chaque personne.
  - Envoyer une notification push (via HA companion) avec :
    - Type de menace.
    - Nom et adresse de l'abri recommandé.
    - Distance et temps estimé.
    - Lien deep-link vers la navigation (Google Maps / Waze / OsmAnd).
  - Mettre à jour la carte Lovelace en mode alerte.
- Notification de confirmation demandée à chaque membre ("Je suis à l'abri").

### 2.7 POI manuels et enrichissement

- Interface de configuration pour ajouter des abris personnalisés :
  - Coordonnées GPS (ou adresse géocodée).
  - Type d'abri.
  - Capacité (optionnel).
  - Notes (code d'accès, horaires, contact…).
- Import/export des POI en JSON/YAML.
- Fusion automatique POI manuels + résultats Overpass avec dédoublication.

---

## 3. Architecture technique

### 3.1 Structure du projet

```
shelter-finder/
├── custom_components/
│   └── shelter_finder/
│       ├── __init__.py              # Setup de l'intégration
│       ├── manifest.json            # Métadonnées HA
│       ├── const.py                 # Constantes
│       ├── config_flow.py           # Configuration UI (flux de config)
│       ├── coordinator.py           # DataUpdateCoordinator
│       ├── sensor.py                # Entités sensor (abri le plus proche, etc.)
│       ├── binary_sensor.py         # État d'alerte actif/inactif
│       ├── notify.py                # Service de notification d'alerte
│       ├── services.yaml            # Définition des services
│       ├── strings.json             # Traductions (en)
│       ├── translations/
│       │   ├── en.json
│       │   └── fr.json
│       ├── overpass.py              # Client API Overpass
│       ├── shelter_logic.py         # Tri, scoring, classification des abris
│       ├── routing.py               # Calcul d'itinéraire (Haversine + OSRM optionnel)
│       └── cache.py                 # Cache local des données d'abri
├── www/
│   └── shelter-map-card.js          # Carte Lovelace custom (Leaflet)
├── tests/
│   ├── test_overpass.py
│   ├── test_shelter_logic.py
│   ├── test_routing.py
│   └── conftest.py
├── hacs.json                        # Métadonnées HACS
├── SPECIFICATIONS.md                # Ce document
├── README.md                        # Documentation utilisateur
├── LICENSE
└── .github/
    └── workflows/
        ├── tests.yml                # CI : tests unitaires
        └── hacs.yml                 # CI : validation HACS
```

### 3.2 Stack technique

| Composant | Technologie |
|---|---|
| Intégration HA | Python 3.12+, API Home Assistant |
| Données cartographiques | API Overpass (OpenStreetMap) |
| Carte interactive | Leaflet.js, tuiles OSM |
| Carte Lovelace | Custom card en Lit Element |
| Routing (optionnel) | OSRM ou calcul Haversine |
| Cache | Fichier JSON local (`.storage/`) |
| Tests | pytest, pytest-homeassistant-custom-component |
| CI/CD | GitHub Actions |

### 3.3 Entités créées

| Entité | Type | Description |
|---|---|---|
| `sensor.shelter_finder_{person}_nearest` | sensor | Abri le plus proche pour une personne |
| `sensor.shelter_finder_{person}_distance` | sensor | Distance vers l'abri recommandé (m) |
| `sensor.shelter_finder_{person}_eta` | sensor | Temps estimé d'arrivée |
| `binary_sensor.shelter_finder_alert` | binary_sensor | Alerte active oui/non |
| `sensor.shelter_finder_alert_type` | sensor | Type de menace en cours |

### 3.4 Services exposés

| Service | Description |
|---|---|
| `shelter_finder.trigger_alert` | Déclencher une alerte (paramètre : type de menace) |
| `shelter_finder.cancel_alert` | Annuler l'alerte en cours |
| `shelter_finder.refresh_shelters` | Forcer le rafraîchissement du cache Overpass |
| `shelter_finder.add_custom_poi` | Ajouter un POI manuel |
| `shelter_finder.confirm_safe` | Confirmer la mise à l'abri d'une personne |

---

## 4. Configuration utilisateur

### 4.1 Config flow (UI)

- Étape 1 : Sélection des entités `person` à suivre.
- Étape 2 : Rayon de recherche par défaut (en mètres, défaut : 2000).
- Étape 3 : Types de menaces activés.
- Étape 4 : Options avancées :
  - URL Overpass custom (pour instance auto-hébergée).
  - Activation du routing OSRM.
  - Intervalle de rafraîchissement du cache (défaut : 24h).
  - Mode de déplacement par défaut (à pied / voiture).

### 4.2 Options reconfigurables

Toutes les options ci-dessus sont modifiables après installation via le panneau d'options de l'intégration.

---

## 5. Contraintes et limites connues

- **Couverture OSM inégale :** Les tags d'abris sont peu renseignés dans certaines zones. Le système de POI manuels compense ce manque.
- **Latence Overpass :** L'API publique Overpass peut être lente sous charge. Le cache local et la possibilité de pointer vers une instance privée atténuent ce risque.
- **Réseau en situation de crise :** Le cache local est essentiel. En mode dégradé, le système utilise les dernières données connues.
- **Accessibilité réelle des abris :** Le système ne peut pas garantir qu'un abri est ouvert ou accessible. Le champ "notes" des POI manuels permet de documenter les conditions d'accès.
- **Précision GPS :** En intérieur, la position GPS peut être imprécise. Le système utilise la dernière position connue.
- **Aucun conseil médical ou réglementaire :** Le système est un outil d'aide à la décision, pas une autorité de sécurité civile.

---

## 6. Roadmap

### v0.1 — MVP

- [x] Structure du projet + manifest
- [ ] Client Overpass avec cache
- [ ] Sensor "abri le plus proche" par personne (distance Haversine)
- [ ] Service `trigger_alert` + notifications push basiques
- [ ] Documentation README

### v0.2 — Carte

- [ ] Lovelace custom card Leaflet
- [ ] Affichage personnes + abris
- [ ] Mode alerte visuel

### v0.3 — Classification et routing

- [ ] Scoring des abris par type de menace
- [ ] Intégration OSRM optionnelle
- [ ] Itinéraire affiché sur la carte

### v0.4 — POI et enrichissement

- [ ] Ajout de POI manuels via config flow
- [ ] Import/export JSON
- [ ] Confirmation de mise à l'abri

### v1.0 — Release publique

- [ ] Tests complets (couverture > 80%)
- [ ] Traductions fr/en
- [ ] Validation HACS
- [ ] Documentation complète
- [ ] CI GitHub Actions

### Futures évolutions possibles

- Intégration FR-Alert / SAIP.
- Widget carte pour tablette murale (Fully Kiosk Browser).
- Mode multi-foyers (partage d'abris entre voisins).
- Analyse IA du contexte (LLM pour évaluer la menace et recommander des actions).
- Support Wear OS / Apple Watch pour notifications critiques.
