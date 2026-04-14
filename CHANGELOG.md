# Changelog

All notable changes to Shelter Finder are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.6.0] — 2026-04-14

Major feature release: real routing, drill mode, voice announcements, and French government alert integration.

### Added
- **OSRM real walking routing** with automatic haversine fallback on error. In-memory LRU+TTL cache (500 entries, 5 min) and top-N batch prefilter keep per-poll HTTP calls bounded. Configurable via Options → Routage (public server or self-hosted URL, walking/driving). (#9)
- **Drill mode** — `shelter_finder.trigger_alert` accepts a `drill: true` parameter for practice alerts. Yellow "EXERCICE" banner in the Lovelace card, `[EXERCICE]` prefix on push notifications, normal priority, and "Ceci est un exercice." voice prefix. New `button.shelter_drill` entity. (#10)
- **TTS voice announcements** on media players when an alert fires. Auto-detects available TTS service (`google_translate_say` / `cloud_say` / `speak`), saves and restores speaker volume, and speaks the closest shelter in French with distance + ETA. Configurable via Options → Notifications. (#11, #12)
- **FR-Alert providers** — polling integration with two French government alert sources:
  - Georisques (floods, earthquakes, industrial/ICPE risks)
  - Meteo France vigilance (storms, floods)
  Each alert auto-triggers `shelter_finder.trigger_alert` when the threat zone is within the configured radius. Deduplication by `alert_id`, severity gating, and optional auto-cancel on expiry. Configurable via Options → Sources. (#13)
- **Multi-step OptionsFlow** — the options page is now a 4-step wizard (Sources & Rayon, Routage, Notifications, Avancé) to accommodate the new v0.6 config surface. (#8)

### Changed
- `AlertCoordinator.get_best_shelter()` is now async — integrators calling it directly must `await` it. (#9)
- Push notifications and TTS announcements in drill mode use distinct styling so they can't be mistaken for a real alert. (#10)

### Fixed
- Consolidated duplicate `THREAT_LABELS_FR` / `THREAT_TYPE_LABELS_FR` constants, corrected `CONF_TTS_VOLUME` voluptuous validator (float 0.0–1.0), and made `build_shelters_by_person` properly async. (#12)
- `AlertCoordinator.get_best_shelter()` no longer mutates the shared shelter dicts cached in `ShelterUpdateCoordinator.data`; enrichment (`eta_minutes`, `route_source`, `distance_m`) is written to a shallow copy so state from one alert (e.g. a drill) can't leak into the next.
- Georisques FR severity labels (`faible` / `moyen` / `fort` / `tres_fort`, plus numeric `1`–`4`) are now translated to the English keys that `SEVERITY_RANK` / `meets_min_severity` understand. Without this, every Georisques alert was silently filtered out at the default `min_severity="severe"`.
- `CONF_OSRM_MODE` (the `public` vs `self_hosted` selector in Options → Routage) is now read at setup and compared against the configured URL; a `_LOGGER.warning` is emitted when the mode and URL disagree. Does not block startup.

## [0.5.0] — 2026-04-13

See git history.

## [0.4.1] — 2026-04-13

Force HACS cache refresh with corrected entity IDs.

## [0.4.0] — 2026-04-13

Initial HACS-ready release.
