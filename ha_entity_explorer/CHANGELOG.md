# Changelog
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
