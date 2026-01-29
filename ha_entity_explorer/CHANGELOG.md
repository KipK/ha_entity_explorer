# Changelog

## 1.0.3
- Add JSON import functionality ( fixed on HA Addon )
    - Can import entity export, or attribute export.
    - Enable visualization of offline/imported data

## 1.0.2
- Add JSON import functionality
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
