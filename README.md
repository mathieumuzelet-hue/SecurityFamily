<p align="center">
  <img src="docs/assets/logo.png" alt="Shelter Finder" width="340"/>
</p>

<p align="center">
  <a href="https://github.com/mathieumuzelet-hue/SecurityFamily/actions/workflows/tests.yml"><img src="https://github.com/mathieumuzelet-hue/SecurityFamily/actions/workflows/tests.yml/badge.svg" alt="Tests"/></a>
  <a href="https://github.com/mathieumuzelet-hue/SecurityFamily/actions/workflows/hacs.yml"><img src="https://github.com/mathieumuzelet-hue/SecurityFamily/actions/workflows/hacs.yml/badge.svg" alt="HACS"/></a>
  <a href="https://github.com/mathieumuzelet-hue/SecurityFamily/releases"><img src="https://img.shields.io/github/v/release/mathieumuzelet-hue/SecurityFamily" alt="Release"/></a>
</p>

---

## Français

**Shelter Finder** est une intégration Home Assistant qui localise les abris proches de chaque membre du foyer et les guide vers le plus sûr en cas d'urgence (tempête, séisme, attaque, inondation, risque nucléaire/chimique, conflit armé).

L'intégration combine la cartographie ouverte (OpenStreetMap via Overpass), un routage piéton réel (OSRM) et les flux d'alerte du gouvernement français (Georisques + Vigilance Meteo France) pour fournir, pour chaque personne, un capteur « meilleur abri » à jour en temps réel, avec distance et temps de marche.

Elle peut être déclenchée manuellement, via webhook externe, ou automatiquement par les providers FR-Alert.

## English

**Shelter Finder** is a Home Assistant custom integration that locates nearby shelters for every household member and guides them to the safest one during emergencies (storm, earthquake, attack, flood, nuclear/chemical, armed conflict).

It combines open mapping (OpenStreetMap via Overpass), real pedestrian routing (OSRM), and French government alert feeds (Georisques + Meteo France Vigilance) to provide a per-person "best shelter" sensor kept live with distance and walking time.

Alerts can be fired manually, via an external webhook, or automatically by the FR-Alert providers.

---

## Version highlights

### [v0.6.4](https://github.com/mathieumuzelet-hue/SecurityFamily/releases/tag/v0.6.4) — 2026-04-14

- **Nouveau type d'abri : `police`** (OSM `amenity=police`). Scoring élevé en **attaque (9/10)** — personnel armé, bâtiment solide, communications. Score modéré en conflit armé (6/10, cible potentielle). Standard ailleurs.
- _New `police` shelter type, high attack priority._

### [v0.6.3](https://github.com/mathieumuzelet-hue/SecurityFamily/releases/tag/v0.6.3) — 2026-04-14

- **Fix safety-critical : cut-off distance par personne avant ranking.** Un métro à 22 km ne pouvait plus battre une mairie à 500 m sous prétexte d'un meilleur type. Filtre strict à `search_radius × 1.5`, élargi à `× 3` si < 3 candidats.
- _Safety-critical scoring fix: strict per-person distance cutoff prevents recommending distant shelters when closer alternatives exist._

### [v0.6.2](https://github.com/mathieumuzelet-hue/SecurityFamily/releases/tag/v0.6.2) — 2026-04-14

- **Refresh par personne** — les abris sont désormais recherchés autour de la position actuelle de **chaque** personne, pas uniquement autour de `zone.home`. Avec 2 personnes éloignées, 2 zones sont couvertes. Fallback à `zone.home` si aucune personne n'a de position.
- _Per-person shelter search — each person's live location is queried independently with adaptive radius, results merged + deduplicated._

### [v0.6.1](https://github.com/mathieumuzelet-hue/SecurityFamily/releases/tag/v0.6.1) — 2026-04-14

- Polish post-v0.6 : annonce TTS non-bloquante, sélection de la personne la plus proche pour l'annonce vocale, mapping neige/canicule Meteo France, DRY interne (helpers partagés), support multi-entry propre.

### [v0.6.0](https://github.com/mathieumuzelet-hue/SecurityFamily/releases/tag/v0.6.0) — 2026-04-14

- **Routage OSRM réel** avec fallback haversine automatique, cache LRU 5 min et pré-filtre top-N (#9)
- **Mode exercice** — service `shelter_finder.trigger_alert` accepte `drill: true`, bannière jaune "EXERCICE", préfixe `[EXERCICE]` sur les push, préfixe vocal "Ceci est un exercice." (#10)
- **Annonces vocales TTS** — lecture automatique en français sur les media_player (auto-détection du service TTS, sauvegarde/restauration du volume) (#11)
- **Providers FR-Alert** — polling automatique de Georisques (inondations, séismes, risques industriels) et Meteo France Vigilance (tempêtes, inondations). Déclenche un alert Shelter Finder si la zone de menace recoupe le rayon configuré (#13)
- **OptionsFlow 4 étapes** — Sources · Routage · Notifications · Avancé (#8)

### [v0.5.0](https://github.com/mathieumuzelet-hue/SecurityFamily/releases/tag/v0.5.0) et antérieurs

MVP : détection d'abris via Overpass, scoring par menace, notifications push avec lien navigation, rayon adaptatif, webhook, POI personnalisés, carte Lovelace Leaflet.

→ **Le [CHANGELOG complet](CHANGELOG.md) détaille chaque version.**

---

## Installation

### HACS (recommandé)

1. HACS → **Intégrations** → **+** → rechercher "Shelter Finder"
2. Installer, redémarrer Home Assistant
3. **Paramètres → Appareils & services → Ajouter une intégration → "Shelter Finder"**

### Manuelle

```bash
# Copier le dossier dans votre HA
cp -r custom_components/shelter_finder/ /config/custom_components/
```

Redémarrer HA, puis ajouter l'intégration via Paramètres.

---

## Configuration

### Install initial (2 étapes)

1. **Personnes & Rayon** — sélectionner les entités `person.*` à suivre, fixer le rayon de recherche (m)
2. **Menaces** — cocher les types de menaces à activer, choisir le mode de transport par défaut

### Options (reconfigurable, 4 pages — v0.6)

| Page | Contenu |
|---|---|
| **Sources & Rayon** | Rayon adaptatif, URL Overpass, TTL cache, **providers Georisques / Meteo France**, intervalle de polling (30–300s), sévérité minimum, auto-annulation |
| **Routage** | Activer OSRM, serveur public / self-hosted, mode piéton / voiture |
| **Notifications** | Intervalle de re-notification, **annonces vocales TTS**, service TTS, media_player cibles, volume |
| **Avancé** | Tags OSM custom, URL Overpass override |

---

## Comment identifier les capteurs utiles

Après installation, Shelter Finder crée automatiquement plusieurs entités. Voici comment les repérer dans Home Assistant.

### Dans **Paramètres → Appareils & services → Shelter Finder**

L'intégration regroupe toutes ses entités. Ouvre la carte de l'intégration pour voir la liste complète.

### Entités principales

| Entité | Description | Exemple d'usage |
|---|---|---|
| `sensor.{person}_shelter_nearest` | Nom du meilleur abri pour cette personne | Afficher dans un card Markdown |
| `sensor.{person}_shelter_distance` | Distance (m) vers l'abri recommandé | Automation : "si distance > 5000m, notifier" |
| `sensor.{person}_shelter_eta` | Temps de trajet estimé (min) | Affichage sur dashboard |
| `binary_sensor.alert` | `on` si une alerte est active | Trigger pour automations d'urgence |
| `sensor.alert_type` | Type de menace courante (storm, flood...) | Adapter les notifications au type |
| `button.trigger_alert` | Déclencher une alerte (tempête par défaut) | Bouton dashboard |
| `button.cancel_alert` | Annuler l'alerte active | Bouton dashboard |
| `button.drill` | Déclencher un **exercice** (v0.6) | Test mensuel, pas de panique |

### Attributs utiles

Le sensor `sensor.{person}_shelter_nearest` expose en attributs :
- `latitude`, `longitude` — coordonnées de l'abri (pour lien navigation)
- `shelter_type` — `subway`, `bunker`, `civic`, `school`...
- `distance_m` — distance réelle (OSRM si activé, sinon haversine)
- `eta_minutes` — temps de marche estimé
- `route_source` — `"osrm"` ou `"haversine"` (v0.6)

Le `binary_sensor.alert` expose :
- `threat_type` — type de menace
- `triggered_at` — timestamp de déclenchement
- `triggered_by` — `"manual"`, `"webhook"`, `"georisques"`, `"meteo_france"` (v0.6)
- `drill` — `true` si mode exercice (v0.6)
- `persons_safe` — liste des personnes ayant confirmé être en sécurité

### Truc rapide pour tout lister

Dans **Outils de développement → États** : filtre par `shelter_finder` ou par nom de personne pour voir tous les capteurs disponibles en un coup d'œil.

---

## Carte Lovelace

```yaml
type: custom:shelter-map-card
title: Shelter Finder
entities:
  - person.alice
  - person.bob
default_zoom: 13
height: 400px
show_radius: true
```

Affiche : marqueurs personnes (cercles colorés), marqueurs abris (icônes par type), **abri recommandé** avec étoile et halo pulsant, lignes de route pointillées, popups cliquables, **bannière d'alerte rouge** (ou jaune "EXERCICE" en mode drill v0.6).

La ressource JS est enregistrée automatiquement — pas de YAML à éditer.

---

## Services

| Service | Description |
|---|---|
| `shelter_finder.trigger_alert` | Déclencher une alerte (param `threat_type`, optionnel `drill: true`, `message`) |
| `shelter_finder.cancel_alert` | Annuler l'alerte active |
| `shelter_finder.refresh_shelters` | Forcer un refresh du cache des abris |
| `shelter_finder.add_custom_poi` | Ajouter un abri personnalisé (cave, voisin...) |
| `shelter_finder.confirm_safe` | Confirmer qu'une personne est en sécurité |

---

## Webhook externe

```bash
curl -X POST https://ton-ha/api/webhook/sf_xxxx \
  -H "Content-Type: application/json" \
  -d '{"threat_type": "storm", "source": "fr-alert"}'
```

L'ID webhook s'affiche dans les Options de l'intégration.

---

## Types de menaces et scoring

Le choix du meilleur abri combine **type de menace × type d'abri × distance**. La matrice ci-dessous donne le score de base (0 = inutile/dangereux, 10 = idéal). Le score final ajoute un bonus de proximité.

| Type abri | 🌪️ Tempête | 🌍 Séisme | 🎯 Attaque | ⚔️ Conflit armé | 🌊 Inondation | ☢️ Nucléaire/Chimique |
|---|---|---|---|---|---|---|
| **subway** (métro) | **10** | 2 | 9 | **10** | 1 | 8 |
| **bunker** | 9 | 2 | **10** | **10** | 1 | **10** |
| **civic** (mairie) | 8 | 3 | 7 | 6 | **8** | 4 |
| **school** (école) | 7 | 4 | 5 | 5 | 7 | 3 |
| **worship** (lieu de culte) | 6 | 3 | 6 | 4 | 6 | 2 |
| **shelter** (abri générique OSM) | 5 | 5 | 3 | 3 | 4 | 1 |
| **sports** (gymnase) | 4 | 7 | 2 | 2 | 5 | 1 |
| **hospital** | 3 | 4 | 4 | 4 | 7 | 3 |
| **government** (bât. officiel) | 3 | 3 | 6 | 5 | 7 | 4 |
| **police** (commissariat) _v0.6.4_ | 5 | 3 | **9** | 6 | 5 | 3 |
| **open_space** (terrain ouvert) | 1 | **10** | 1 | 1 | 3 | 0 |

**Logique** : tempête → souterrains/enfermés · séisme → **inversé** (fuir les structures, préférer l'ouvert) · attaque/conflit → bunker/métro/police · inondation → bâtiments en hauteur · NRBC → étanchéité (bunker).

**Formule finale (v0.6.3+)** :
```
1. Filtrer par personne : shelters à ≤ search_radius × 1.5 (élargi à × 3 si < 3 candidats)
2. score = table[menace][type] × 10 + max(0, 10 × (1 - distance_m / 15000))
3. Le plus haut score gagne
```

**Surcharger** : créer `shelter_finder_scores.yaml` dans `/config` avec ta propre matrice.

---

## Modèles d'automatisation

### 1. Déclencher un exercice mensuel automatiquement (v0.6)

```yaml
automation:
  - alias: "Exercice Shelter Finder — 1er du mois à 11h"
    trigger:
      - platform: time
        at: "11:00:00"
    condition:
      - condition: template
        value_template: "{{ now().day == 1 }}"
    action:
      - service: shelter_finder.trigger_alert
        data:
          threat_type: storm
          drill: true
          message: "Exercice mensuel — pas de panique"
```

### 2. Recevoir une notification avec lien navigation en cas d'alerte

```yaml
automation:
  - alias: "Notification abri sur alerte"
    trigger:
      - platform: state
        entity_id: binary_sensor.alert
        to: "on"
    action:
      - service: notify.mobile_app_pixel_mathieu
        data:
          title: >
            {% if state_attr('binary_sensor.alert', 'drill') %}[EXERCICE] {% endif %}
            ALERTE {{ states('sensor.alert_type') | upper }}
          message: >
            Abri : {{ states('sensor.mathieu_shelter_nearest') }}
            ({{ states('sensor.mathieu_shelter_distance') }}m,
            ~{{ states('sensor.mathieu_shelter_eta') }} min)
          data:
            url: >-
              https://www.google.com/maps/dir/?api=1&destination={{
              state_attr('sensor.mathieu_shelter_nearest', 'latitude') }},{{
              state_attr('sensor.mathieu_shelter_nearest', 'longitude') }}&travelmode=walking
            priority: high
```

### 3. Alerter si un proche est trop loin de tout abri

```yaml
automation:
  - alias: "Alerte eloignement abri"
    trigger:
      - platform: numeric_state
        entity_id: sensor.mathieu_shelter_distance
        above: 5000
        for: "00:10:00"
    action:
      - service: notify.mobile_app_pixel_mathieu
        data:
          title: "Shelter Finder"
          message: >
            Tu es a {{ states('sensor.mathieu_shelter_distance') }}m du premier abri.
```

### 4. Auto-annuler quand tout le monde est en sécurité

```yaml
automation:
  - alias: "Auto-cancel alerte quand tout le monde en securite"
    trigger:
      - platform: state
        entity_id: binary_sensor.alert
        attribute: persons_safe
    condition:
      - condition: template
        value_template: >
          {{ state_attr('binary_sensor.alert', 'persons_safe') | length ==
             state_attr('binary_sensor.alert', 'persons_total') | length }}
    action:
      - service: shelter_finder.cancel_alert
```

### 5. Forcer un refresh quotidien des abris (v0.6.2+ : par personne)

```yaml
automation:
  - alias: "Refresh abris quotidien"
    trigger:
      - platform: time
        at: "03:30:00"
    action:
      - service: shelter_finder.refresh_shelters
```

### 6. Dashboard conditionnel

```yaml
type: conditional
conditions:
  - entity: binary_sensor.alert
    state: "on"
card:
  type: markdown
  content: >
    ## {% if state_attr('binary_sensor.alert', 'drill') %}[EXERCICE] {% endif %}ALERTE
    {{ states('sensor.alert_type') | upper }}

    | Personne | Abri | Distance | ETA |
    |---|---|---|---|
    | Mathieu | {{ states('sensor.mathieu_shelter_nearest') }} | {{ states('sensor.mathieu_shelter_distance') }}m | {{ states('sensor.mathieu_shelter_eta') }} min |
    | Delphine | {{ states('sensor.delphine_shelter_nearest') }} | {{ states('sensor.delphine_shelter_distance') }}m | {{ states('sensor.delphine_shelter_eta') }} min |
```

### 7. Intégration webhook FR-Alert (système externe)

```bash
# Depuis n'importe quel outil (curl, Node-RED, n8n...)
curl -X POST https://ton-ha/api/webhook/sf_xxxx \
  -H "Content-Type: application/json" \
  -d '{"threat_type": "attack", "source": "fr-alert"}'
```

### 8. Annonce TTS personnalisée sur enceinte (v0.6)

Par défaut, Shelter Finder annonce automatiquement l'alerte sur les media_player configurés (Options → Notifications). Pour une annonce additionnelle :

```yaml
automation:
  - alias: "Annonce custom sur Echo salon"
    trigger:
      - platform: state
        entity_id: binary_sensor.alert
        to: "on"
    action:
      - service: tts.google_translate_say
        data:
          entity_id: media_player.echo_salon
          message: >
            Attention, une alerte {{ states('sensor.alert_type') }} est active.
            Rejoins {{ states('sensor.mathieu_shelter_nearest') }} au plus vite.
```

---

## Contribuer

Issues et PRs bienvenus — voir les [issues ouvertes](https://github.com/mathieumuzelet-hue/SecurityFamily/issues).

Pour le dev local : `pip install -r requirements_test.txt && pytest` (nécessite `homeassistant` + deps).

## Licence

MIT
