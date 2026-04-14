# Changelog

All notable changes to Shelter Finder are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.6.3] — 2026-04-14

Safety-critical scoring fix exposed by the v0.6.2 per-person refresh.

### Fixed
- **Safety-critical:** the recommended best shelter for a given person could be
  20+ km away even when much closer alternatives existed. After v0.6.2, shelters
  fetched around other configured persons enter the global shelter pool, and a
  high type-score shelter far from person D (e.g. a metro station 22 km away in
  a neighbor's zone, score 90) could outrank a closer, lower-type shelter near
  person D (e.g. a mairie 500 m away, score ~80) because `rank_shelters` weights
  shelter type 10x over distance. Per-person best-shelter selection now applies
  a strict haversine distance cutoff *before* ranking: shelters beyond
  `search_radius × 1.5` are excluded outright. If fewer than 3 candidates remain
  the cutoff is widened once to `search_radius × 3`; only when zero shelters
  remain at 3x does the sensor report no shelter (person genuinely isolated).
  This guarantees that a close-by shelter is always preferred over a distant
  one with a slightly better type-score.

## [0.6.2] — 2026-04-14

Safety fix for households with multiple tracked persons.

### Fixed
- Shelter refresh now queries Overpass around **each configured person's
  current location** instead of only around `zone.home`. Previously, with
  two or more persons configured in different parts of town (e.g. one at
  home, one at work), only the `zone.home` area was covered — the other
  person(s) had no nearby shelters discovered at all, which defeats the
  point of per-person nearest-shelter routing during an alert. Each
  person now gets their own Overpass query with the same adaptive-radius
  widening; results are merged and deduplicated by OSM id (or rounded
  coordinates when the id is missing). `zone.home` is still used as a
  last-resort fallback when no tracked person has a known location.

## [0.6.1] — 2026-04-14

Post-release polish sweep closing the v0.6 code-review findings. No user-facing
config changes; existing installs upgrade in place.

### Changed
- TTS voice announcements now pick the closest person (minimum `distance_m`)
  instead of relying on arbitrary dict-iteration order, matching the spec.
  (#17)
- `_send_alert_notifications` schedules the TTS flow via
  `hass.async_create_task`, so push notifications are no longer serialized
  behind TTS playback + volume restore (which can take 10+ seconds on slow
  speakers). (#17)
- Meteo France provider now maps `neige-verglas` (snow/ice) and `canicule`
  (heatwave) vigilance bulletins to the `storm` threat type, so those
  advisories actually trigger alerts. (#18)
- Options flow now validates `provider_alert_radius_km` as a float
  (`vol.Coerce(float)`), accepting fractional radii instead of int-only. (#19)

### Fixed
- `AlertProviderManager.async_stop` no longer silently swallows
  non-`CancelledError` exceptions during shutdown — they are logged at
  debug level with `exc_info` so real shutdown failures are surfaced. (#20)

### Internal
- `const.py` consolidated: merged the legacy OSRM block with the v0.6 block,
  dropped plan-aligned aliases (`CONF_POLLING_INTERVAL`, `CONF_ALERT_RADIUS`,
  `CONF_AUTO_CANCEL`, `CONF_MIN_SEVERITY` and their `DEFAULT_*`/`MIN_*`/`MAX_*`
  siblings), dropped the `THREAT_TYPE_LABELS_FR` alias, and documented that
  `attack` / `armed_conflict` are deliberately not mapped by any FR-Alert
  provider. Call sites in `__init__.py` and tests use the canonical
  `CONF_PROVIDER_*` / `PROVIDER_POLL_INTERVAL_*` names. (#15)
- Dropped the `hass.data[DOMAIN]["alert_coordinator"]` and
  `["tts_service"]` globals — they would have collided with a second
  config entry. Per-entry storage under `hass.data[DOMAIN][entry.entry_id]`
  is the only location; service handlers and the webhook iterate entries.
  `_send_alert_notifications` takes an explicit `tts_service` kwarg from
  its caller. Single-entry behavior is unchanged. (#16)
- DRY helpers: extracted `haversine_km` to a shared `_geo` module (replaces
  duplicated implementations in `alert_provider_manager` and
  `alert_providers/meteo_france`); moved `parse_iso8601` to
  `alert_providers/base`. Cleaned up duplicate `OrderedDict` / `asyncio`
  / `TRAVEL_SPEEDS` imports inside `routing.py`. Added a TODO on
  `ShelterDrillButton` documenting the `"storm"` hardcode. Test coverage
  expanded: regression test now calls `get_best_shelter` twice to guard
  against repeat-enrichment leaks, and the `_FakeCoordinator.trigger` in
  `test_alert_provider_manager` mirrors the real signature's `drill=False`
  kwarg. (#21)

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
