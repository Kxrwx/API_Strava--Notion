

# 🏃‍♀️ Strava-Notion Sync API

## 🌟 1. Description du Projet

Cette application est une API légère construite avec **Python Flask** qui permet la **synchronisation automatique et instantanée** de vos activités sportives enregistrées sur **Strava** vers une base de données **Notion** pour un suivi d'entraînement centralisé.

Elle intègre une **interface graphique Tkinter** pour simplifier la configuration initiale des clés API et de l'authentification Strava.

## ✨ 2. Fonctionnalités

  * **Synchronisation en Temps Réel :** Utilise les *webhooks* Strava pour détecter et traiter instantanément les nouvelles activités dès leur création.
  * **Interface Graphique (GUI) :** Configuration facile de tous les secrets d'API (Strava & Notion) via une fenêtre Tkinter.
  * **Authentification Simplifiée :** Lancement de l'autorisation OAuth 2.0 Strava directement depuis le GUI.
  * **Mappage de Données Complètes :** Prise en charge de toutes les activités et transfert des métriques clés de Strava vers Notion.

## 🛠️ 3. Prérequis

  * **Python 3.13+**
  * Un compte **Strava Developer** (pour obtenir un Client ID/Secret)
  * Un compte **Notion** avec une intégration créée
  * **Un outil de tunneling** comme `ngrok` ou un serveur public (obligatoire pour recevoir les *webhooks* de Strava en production ou en développement local).

## 📦 4. Installation et Démarrage

### 4.1. Cloner le Dépôt

```bash
git clone [URL_DE_VOTRE_DEPOT]
cd strava-notion-sync-api
```

### 4.2. Environnement Virtuel et Dépendances

Créez et activez un environnement virtuel, puis installez les dépendances nécessaires :

```bash
python3.13 -m venv venv
source venv/bin/activate  # Pour Windows : venv\Scripts\activate
pip install flask requests python-dotenv tk
```

### 4.3. Lancement de l'Interface Graphique

L'application est lancée par le script principal du GUI :

```bash
python gui.py  # (Assurez-vous que votre point d'entrée s'appelle bien gui.py)
```

## 📐 5. Structure de la Base de Données Notion

Votre base de données cible dans Notion **doit impérativement** avoir les propriétés suivantes. Veuillez respecter le nommage et le type pour garantir la synchronisation :

| Propriété Notion | Type | Correspondance Strava |
| :--- | :--- | :--- |
| **Activity Name** (ou **Nom**) | Titre | `name` |
| **Date** | Date | `start_date_local` |
| **Activity ID** | Nombre | `id` (Identifiant unique) |
| **Type** | Sélection | `type` (Run, Ride, etc.) |
| **Distance** | Nombre | `distance` (en mètres) |
| **Durée** | Nombre | `moving_time` (en secondes) |
| **D+** | Nombre | `total_elevation_gain` (en mètres) |
| **Calorie** | Nombre | `calories` |

## 🚀 6. Utilisation de l'Interface Graphique (GUI)

Le GUI vous guidera à travers les étapes de configuration.

### Étape 1 : Configuration des Secrets

1.  Ouvrez l'onglet **Configuration** dans l'application Tkinter.
2.  Entrez vos clés obtenues auprès de Strava et Notion (Client ID, Client Secret, Notion Token, Database ID).
3.  Cliquez sur **"Sauvegarder la Configuration"**. Ces informations sont enregistrées dans un fichier `.env`.

### Étape 2 : Autorisation Strava

1.  Rendez-vous dans l'onglet **Connexion Strava**.
2.  Cliquez sur le bouton **"Autoriser Strava"**. Votre navigateur s'ouvrira, vous demandant l'autorisation sur Strava.
3.  Après avoir accordé l'accès, l'API Flask récupérera le **`REFRESH_TOKEN`** nécessaire et le stockera automatiquement.

### Étape 3 : Démarrage du Service API

1.  Ouvrez l'onglet **Service API**.
2.  Cliquez sur le bouton **"Démarrer le Service API"**.
3.  Le serveur Flask démarre et se met en attente de *webhooks* sur l'URL publique configurée.

> **❗ Configuration du Webhook Strava :** Après le démarrage de l'API, vous devez enregistrer l'URL publique de votre service auprès de Strava Developer pour que la synchronisation automatique fonctionne. L'URL à fournir est généralement : `https://VOTRE_URL_PUBLIQUE/webhook`.

## 7\. Points de Terminaison de l'API (Flask)

Ces routes sont gérées en arrière-plan par l'application Flask, mais sont essentielles à son fonctionnement :

| Endpoint | Méthode | Rôle |
| :--- | :--- | :--- |
| `/auth/strava` | `GET` | Gère le processus initial d'échange de code contre un `REFRESH_TOKEN`. |
| `/webhook` | `GET` | **Vérification** de l'abonnement par Strava (étape de configuration). |
| `/webhook` | `POST` | **Réception** du *payload* d'une nouvelle activité Strava pour le traitement et l'insertion dans Notion. |

-----
