# Shelter Finder — Design Document

**Date :** 2026-04-13
**Statut :** Approuvé
**Repo :** SecurityFamily
**Type :** Custom component Home Assistant (HACS)
**Cible :** Communauté HA francophone

---

## 1. Vue d'ensemble

Système de mise à l'abri automatisé pour Home Assistant. Deux modes :

- **Mode veille** : dashboard permanent montrant les abris autour de chaque membre du foyer
- **Mode alerte** : déclenchement actif qui guide chaque personne vers l'abri le plus adapté à la menace en cours

Distribution via HACS. Doit tourner sur Raspberry Pi 4 (2GB RAM).

---

## 2. Architecture des composants

```
custom_components/shelter_finder/
├── __init__.py              # Setup, enregistrement webhook, services, auto-enregistrement ressource Lovelace
├── manifest.json            # Métadonnées HA (dependencies, iot_class: cloud_polling)
├── const.py                 # Constantes, threat types, tags OSM par défaut, scores
├── config_flow.py           # 2 étapes install + Options reconfigurables
├── coordinator.py           # ShelterUpdateCoordinator (cycle lent Overpass, 24h)
├── alert_coordinator.py     # AlertCoordinator (état d'alerte, logique temps réel)
├── sensor.py                # nearest, distance, eta, alert_type
├── binary_sensor.py         # alert active/inactive
├── button.py                # Boutons trigger_alert / cancel_alert
├── services.yaml            # trigger_alert, cancel_alert, refresh_shelters, add_custom_poi, confirm_safe
├── strings.json             # Traductions en
├── translations/
│   ├── en.json
│   └── fr.json
├── overpass.py              # Client Overpass avec retry + rate limiting
├── shelter_logic.py         # Scoring, classification menace → abri, rayon adaptatif
├── routing.py               # Haversine + OSRM optionnel
├── webhook.py               # Réception webhook externe (futur FR-Alert)
└── cache.py                 # Cache .storage/ JSON avec TTL configurable

www/
└── shelter-map-card.js      # Carte Lovelace custom (Leaflet + Lit Element)

tests/
├── conftest.py
├── test_overpass.py
├── test_shelter_logic.py
├── test_routing.py
├── test_cache.py
├── test_config_flow.py
├── test_coordinator.py
├── test_alert_coordinator.py
├── test_sensor.py
├── test_binary_sensor.py
└── test_button.py

.github/workflows/
├── tests.yml                # pytest Python 3.12/3.13
├── hacs.yml                 # Validation HACS
└── release.yml              # GitHub Release sur tag
```

### Décisions architecturales

- **Pas de `notify.py`** : en HA moderne, on appelle `hass.services.async_call("notify", ...)` directement depuis l'AlertCoordinator
- **Deux coordinators séparés** : `coordinator.py` (cycle lent Overpass 24h) et `alert_coordinator.py` (état d'alerte temps réel). Responsabilités distinctes, pas de mélange de rythmes.
- **`button.py` ajouté** : entités bouton pour trigger/cancel alert depuis l'UI Lovelace native sans custom card
- **`webhook.py` dédié** : endpoint pour déclencheurs externes, prépare l'intégration FR-Alert

---

## 3. Modèle de données

### Entités par personne

| Entité | Type | État | Attributs |
|---|---|---|---|
| `sensor.shelter_finder_{person}_nearest` | sensor | Nom de l'abri | `latitude`, `longitude`, `address`, `shelter_type`, `source` (osm/manual), `threat_suitability` |
| `sensor.shelter_finder_{person}_distance` | sensor | Distance en mètres | `unit_of_measurement: m`, `travel_mode`, `route_polyline` (si OSRM) |
| `sensor.shelter_finder_{person}_eta` | sensor | Minutes estimées | `unit_of_measurement: min`, `travel_mode` |

### Entités globales

| Entité | Type | État | Attributs |
|---|---|---|---|
| `binary_sensor.shelter_finder_alert` | binary_sensor | on/off | `threat_type`, `triggered_at`, `triggered_by` (manual/webhook/automation), `persons_safe` (liste) |
| `sensor.shelter_finder_alert_type` | sensor | Type de menace ou `none` | `priority_shelters` (liste des types d'abri prioritaires) |
| `button.shelter_finder_trigger_alert` | button | — | — |
| `button.shelter_finder_cancel_alert` | button | — | — |

### Scoring menace → abri

```python
THREAT_SHELTER_SCORES = {
    "storm": {"subway": 10, "bunker": 9, "civic": 8, "school": 7, "worship": 6, "shelter": 5, "sports": 4, "open_space": 1},
    "earthquake": {"open_space": 10, "sports": 7, "shelter": 5, "school": 4, "subway": 2, "bunker": 2},
    "attack": {"bunker": 10, "subway": 9, "civic": 7, "worship": 6, "school": 5},
    "armed_conflict": {"bunker": 10, "subway": 10, "civic": 6, "school": 5},
    "flood": {"civic": 8, "school": 7, "worship": 6, "sports": 5, "subway": 1, "bunker": 1},
    "nuclear_chemical": {"bunker": 10, "subway": 8, "civic": 4},
}
```

Surchargeable via `shelter_finder_scores.yaml` dans le dossier config HA.

### Tags OSM par défaut

```python
DEFAULT_OSM_TAGS = [
    "amenity=shelter",
    "building=bunker",
    "amenity=place_of_worship",
    "railway=station",
    "station=subway",
    "building=civic",
    "building=government",
    "building=school",
    "amenity=school",
    "building=hospital",
    "leisure=sports_centre",
    "shelter_type=*",
]
```

Configurable dans les Options (ajout/retrait de tags).

### Rayon adaptatif

1. Chercher dans le rayon configuré (défaut 2000m)
2. Si < 3 résultats → élargir à rayon × 2.5 (5000m)
3. Si toujours < 3 → élargir à rayon × 5 (10000m)
4. Cap maximum : 15000m

Activable/désactivable dans les Options.

### Structure POI manuel

```python
{
    "id": "uuid4",
    "name": "Cave maison",
    "latitude": 48.8566,
    "longitude": 2.3522,
    "shelter_type": "bunker",
    "capacity": 6,             # optionnel
    "notes": "Code digicode: 4521B",
    "threat_suitability": ["storm", "attack", "armed_conflict"],  # optionnel, sinon tous
}
```

Stockage dans `.storage/shelter_finder_pois.json`.

---

## 4. Flux de données

### Mode veille

- `ShelterUpdateCoordinator` appelle Overpass toutes les 24h (TTL configurable)
- Résultats cachés dans `.storage/shelter_finder_cache.json`
- Cache fusionné avec les POI manuels (dédoublication : si un POI manuel est à < 50m d'un résultat OSM, le POI manuel prévaut car ses métadonnées sont plus fiables)
- Les positions des personnes sont écoutées via `state_changed` events (pas de polling)
- À chaque changement de position → recalcul du nearest shelter depuis le cache
- Distance Haversine uniquement (pas d'OSRM en veille)

### Mode alerte

1. Déclencheur reçu (button / service call / webhook)
2. `binary_sensor` → ON, `sensor.alert_type` → threat_type
3. Force GPS refresh : `notify.mobile_app_xxx` avec `{"message": "request_location"}`
4. Attente positions (timeout 30s, utilise dernière position connue si timeout)
5. Pour chaque personne : scoring des abris du cache selon le type de menace + calcul distance/ETA
6. Update sensors avec résultats scorés
7. Notification push par personne : type de menace, nom/adresse abri, distance/ETA, deep link navigation, action "Je suis à l'abri"
8. Boucle active tant que alerte ON : recalcul si position change, re-notification à 5min/15min/30min (3 max)

### Webhook

```
POST /api/webhook/{webhook_id}
Content-Type: application/json

{
    "threat_type": "storm",        # requis
    "message": "Alerte tempête",   # optionnel
    "source": "fr-alert"           # optionnel
}
```

Validation stricte : `threat_type` inconnu → rejet 400.

### Confirmation

- Action "Je suis à l'abri" → `shelter_finder.confirm_safe(person)`
- `persons_safe` mis à jour dans les attributs du binary_sensor
- Stop re-notifications pour cette personne
- L'alerte ne s'annule PAS automatiquement quand tous confirmés — reste active, seul `cancel_alert` la désactive

---

## 5. Config flow et Options

### Installation (2 étapes)

**Étape 1 :**
- `persons` : multi-select des entités `person` (défaut : toutes)
- `search_radius` : rayon en mètres (défaut : 2000)
- `language` : fr/en (défaut : fr)

**Étape 2 :**
- `enabled_threats` : multi-select des types de menaces (défaut : toutes)
- `default_travel_mode` : walking/driving (défaut : walking)

### Options reconfigurables

| Champ | Catégorie | Défaut |
|---|---|---|
| `persons` | Général | config initiale |
| `search_radius` | Général | 2000 |
| `enabled_threats` | Général | toutes |
| `default_travel_mode` | Général | walking |
| `overpass_url` | Avancé | `https://overpass-api.de/api/interpreter` |
| `cache_ttl` | Avancé | 24 (heures) |
| `osrm_enabled` | Avancé | false |
| `osrm_url` | Avancé | `""` |
| `custom_osm_tags` | Avancé | `""` (comma-separated) |
| `webhook_id` | Avancé | auto-généré (readonly) |
| `re_notification_interval` | Alerte | 5 (minutes) |
| `max_re_notifications` | Alerte | 3 |
| `adaptive_radius` | Avancé | true |
| `adaptive_radius_max` | Avancé | 15000 (mètres) |

Les scores menace/abri sont surchargeables via `shelter_finder_scores.yaml` (pas dans le config flow).

---

## 6. Carte Lovelace

### Technique

- Lit Element + Leaflet.js (import dynamique)
- Fichier unique : `www/shelter-map-card.js` (< 50KB hors Leaflet)
- Auto-découverte via `window.customCards` : visible dans "Ajouter une carte" sans YAML

```javascript
window.customCards = window.customCards || [];
window.customCards.push({
    type: "shelter-map-card",
    name: "Shelter Finder Map",
    description: "Carte des abris et membres du foyer",
    preview: true,
});
```

### Auto-enregistrement ressource

Dans `__init__.py`, la ressource Lovelace est enregistrée automatiquement à l'installation. L'utilisateur n'a aucun fichier à configurer manuellement.

### Configuration carte

```yaml
type: custom:shelter-map-card
entities:
  - person.mathieu
  - person.partner
show_radius: true
default_zoom: 13
alert_zoom: 15
height: 400px
```

### Mode veille

- Carte centrée pour englober toutes les personnes
- Marqueurs personne : icône avec initiale, couleur distincte
- Marqueurs abri : icône par type
- Clic abri → popup (nom, type, distance)
- Clic personne → popup (abri le plus proche, distance)
- Rayon de recherche en cercle semi-transparent (toggle)

### Mode alerte

- Fond assombri, bandeau rouge avec type de menace
- Abris non pertinents grisés/masqués
- Abris recommandés en pulsation CSS
- Itinéraire en pointillés personne → abri
- Personnes confirmées → marqueur vert checkmark
- Personnes non confirmées → marqueur rouge clignotant

### Progression

| Version | Carte |
|---|---|
| v0.2 | Affichage statique : personnes + abris + popups |
| v0.3 | Itinéraire tracé, mode alerte visuel |
| v0.4 | Clic droit → ajouter POI, édition en place |
| v1.0 | Animations fluides, responsive tablette, dark mode |

---

## 7. Expérience utilisateur

### Installation

1. HACS → Intégrations → "Shelter Finder" → Installer (copie automatique Python + JS)
2. Redémarrer HA
3. Paramètres → Appareils & Services → Ajouter → "Shelter Finder" → config flow 2 étapes
4. Dashboard → Modifier → "+" → "Shelter Finder Map" (auto-découverte)

Aucune manipulation de fichier. Pas de Code Server nécessaire.

### Onboarding post-installation

Notification persistante HA :

```
Shelter Finder installé !

- X personnes suivies
- Y abris trouvés dans un rayon de Zm
- Webhook configuré : /api/webhook/sf_xxxx

→ Ajoutez la carte : Modifier le dashboard → + → Shelter Finder Map
→ Testez : Services → shelter_finder.trigger_alert
```

Au premier lancement :
- Cache Overpass rempli immédiatement
- Sensors créés avec valeurs initiales (pas de `unavailable`)
- Event `shelter_finder_ready` émis

### Empreinte ressources

| Ressource | Estimation | Impact |
|---|---|---|
| RAM | ~15-25 MB | < 3% sur HA typique |
| Stockage | ~2-5 MB | Négligeable |
| CPU | Négligeable en veille | Pic de quelques secondes en alerte |
| Réseau | ~1 requête/24h | 50-200 KB par requête Overpass |
| Batterie mobile | Aucun impact en veille | Force-refresh GPS ponctuel en alerte |

### Compatibilité

- Home Assistant 2024.1+
- Python 3.12+
- HACS v2.0+
- App companion iOS 2024.1+ / Android 2024.1+

---

## 8. Tests et CI/CD

### Stratégie

| Cible | Méthode |
|---|---|
| Logique métier (scoring, Haversine, rayon adaptatif) | Tests unitaires purs, pas de mock HA |
| Coordinators, config flow, sensors | `pytest-homeassistant-custom-component` avec `hass` mocké |
| Client Overpass | `aioclient_mock` |
| Webhook | Validation payload, rejet 400 |
| Cache | Écriture, lecture, TTL, corruption |
| Flux alerte complet | trigger → GPS → scoring → notification → confirm |

**Non testé :** rendu Leaflet (pas de DOM), notifications push réelles (on vérifie les appels service), API Overpass réelle.

### Couverture

| Version | Cible |
|---|---|
| v0.1 | > 70% |
| v1.0 | > 80% |

### GitHub Actions

- **tests.yml** : pytest Python 3.12/3.13, coverage Codecov
- **hacs.yml** : validation structure via `hacs/action@main`
- **release.yml** : GitHub Release sur tag vX.Y.Z avec zip

---

## 9. Roadmap révisée

### v0.1 — MVP

- Structure projet + manifest + hacs.json
- Client Overpass avec cache et retry
- Rayon adaptatif
- Sensors nearest/distance par personne (Haversine)
- Binary sensor alerte
- Boutons trigger/cancel alert
- Service trigger_alert + cancel_alert + refresh_shelters
- Webhook entrant
- AlertCoordinator : flux complet trigger → GPS → scoring → notification → confirm
- Notification persistante onboarding
- Tests > 70%
- CI GitHub Actions (tests + HACS)
- README

### v0.2 — Carte

- Custom card Leaflet + Lit Element
- Auto-découverte dans "Ajouter une carte"
- Auto-enregistrement ressource JS
- Affichage personnes + abris + popups
- Mode veille statique

### v0.3 — Classification et routing

- Scoring complet par type de menace
- OSRM optionnel
- Itinéraire sur la carte
- Mode alerte visuel (bandeau, pulsation, grisage)

### v0.4 — POI et enrichissement

- Service add_custom_poi
- Ajout POI depuis la carte (clic)
- Import/export JSON
- Confirmation visuelle sur la carte

### v1.0 — Release publique

- Tests > 80%
- Traductions fr/en complètes
- Validation HACS officielle
- Dark mode carte
- Responsive tablette
- Documentation complète
- Release workflow
