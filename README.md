
# Visualiseur d'Historique Smart-PI

Ce script standalone permet de visualiser les exports JSON d'historique de Home Assistant pour le Thermostat Versatile.

## Utilisation avec pipx (Recommandé)

Cette méthode ne nécessite aucune installation manuelle de dépendances.

1. Placer vos fichiers d'export JSON dans le dossier `data/`.
   
2. Lancer le serveur (depuis la racine du projet) :
   ```bash
   pipx run dev_tests/smartpi_history_graph/server.py
   ```

3. Ouvrir le navigateur :
   - Local : [http://127.0.0.1:5000](http://127.0.0.1:5000)
   - Réseau : `http://<IP_DE_VOTRE_MACHINE>:5000` (Le serveur écoute maintenant sur toutes les interfaces)

## Installation Manuelle (Alternative)

1. Installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
2. Lancer :
   ```bash
   python3 server.py
   ```

## Fonctionnalités
- **Graphique interactif** : Zoom, Pan, Reset.
- **Données** : Température intérieure, Consigne, Température extérieure, Zones de chauffe.
- **Détails** : Cliquez sur le graphique pour voir les états détaillés de Smart-PI à l'instant T dans le panneaulatéral.
- **Sélecteur de fichier** : Basculez facilement entre plusieurs fichiers JSON présents dans le dossier `data/`.
