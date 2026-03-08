# Changelog
## 1.1.4
- fix wrong color in climate graph legend
- fix export only data from selected timeframe

## 1.1.3
- remove  "minimal_response" and "significant_changes_only" from API call. 

## 1.1.2
- fix: force browser cache invalidation on update
- fix attribute-only state changes not shown in history ( fix [#2](https://github.com/KipK/ha_entity_explorer/issues/2) )
- Fixes [#2](https://github.com/KipK/ha_entity_explorer/issues/2) - all recorded state changes (including attribute-only) are
now displayed with their correct timestamps in charts and detail views.
- fix string attribute list not filtereing selected timeframe.
improve UI responsiveness and fix sidebar attribute overflow
- Fix sidebar attribute table overflow: table-layout fixed, ellipsis on
  keys, word-wrap on values, title tooltips for full text on hover
- Add resizable sidebar with drag handle (mouse + touch), width saved
  in localStorage
- Add collapsible sidebar toggle button, state persisted in localStorage
- Add focus mode (fullscreen chart) hiding navbar and sidebar
- Move entity badge outside navbar collapse so it's always visible on
  mobile, with adaptive max-width per breakpoint
- Add quick export button next to Refresh, visible when entity selected
- Make date range display clickable to open date picker directly
- Update grid to 3-column layout (1fr 4px sidebar) across all breakpoints

##  1.0.10
- fix display with HA Ingress
- fix non scrollable page on mobile

## 1.0.9
- Fix attributes not visibible on Mobile. Added responsive layout

## 1.0.8
- Add ZIP file support for import and export
  Export data as ZIP by default (smaller file size)
  Import from ZIP files containing a single JSON file
- fix: Reset attribute display when loading new entity
- fix: fix Refresh button only refreshed from server cache
- fix: indent correctly exported json file

## 1.0.7
- Fix attributes graph not displayed with imported data with Ingress

## 1.0.6
- Fix attributes graph not displayed with imported data

## 1.0.5
- Implement server-side memory cleanup for imported sessions
- Add `DELETE /api/import/<import_id>` endpoint to remove imported data from server RAM
- Trigger cleanup request when user closes the entity view
- Use `pagehide` event with `keepalive: true` to ensure memory is freed on page unload/refresh

## 1.0.4
- Add JSON import functionality ( fixed on HA Addon )
    - Can import entity export, or attribute export.
    - Enable visualization of offline/imported data

## 1.0.1
- Added dockerhub prebuilt images
- Implement PBKDF2 password hashing for user credentials.
- Disable Flask debug mode in production environment.
- Enforce secret key presence; fail to start if missing in production.
- Add HTTP security headers (CSP, X-Frame-Options, X-Content-Type-Options).
- Fix potential DOM-based XSS in attribute view.

## 1.0.0
- Initial release as Home Assistant Add-on
- Dynamic entity history visualization
- Attribute exploration and history charting
- Data export to JSON
- IP banning for security
- Whitelist/blacklist entity filtering
- Integration with Home Assistant Ingress
