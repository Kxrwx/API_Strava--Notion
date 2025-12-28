# ATTENTION CE N'EST PAS UNE API OFFICIEL
# 🚀 Strava-Notion Sync App

**Synchronisez automatiquement et instantanément vos activités Strava vers une base de données Notion.**

## 🌟 1. À quoi sert l'application ?

Cette application permet d'intégrer vos données sportives de Strava dans votre environnement de productivité Notion, offrant un **suivi d'entraînement centralisé et automatique**. Fini la saisie manuelle : toute nouvelle activité Strava est détectée et ajoutée à votre base de données Notion en temps réel si l'application tourne. Il y a un mode rattrapage qui permet de recup tout vos activitées passées.

## 📥 2. Téléchargement et Démarrage Rapide (Pour les Utilisateurs)

Pour utiliser l'application sans installer Python :

1. **Téléchargez** le fichier d'installation (`.exe` ou `setup.exe`) depuis la page des publications (Releases) :
**[CLIQUEZ ICI pour télécharger la dernière version]([https://www.google.com/search?q=https://github.com/Kxrwx/API_Strava--Notion/releases/latest](https://github.com/Kxrwx/API_Strava--Notion/releases/tag/v1.2.0))**
2. **Lancez l'installeur** et suivez les instructions.
3. Une fois installé, lancez l'application **"StravaNotionSync"**.

---

## ⚙️ 3. Guide d'Utilisation et Mode d'Emploi

L'application utilise une interface graphique (GUI) pour guider la configuration en trois étapes.

### Prérequis Indispensables

Pour que la synchronisation fonctionne, vous devez obtenir trois clés auprès des services externes :

1. **Strava Client ID / Client Secret** : Obtenus sur votre [compte Strava Developer](https://developers.strava.com/).
2. **Notion Integration Token** : Créé dans [Mes Intégrations Notion](https://www.notion.so/my-integrations).
3. **Notion Database ID** : L'identifiant de la page de votre base de données cible (voir Section 3.4).

### 3.1. Étape 1 : Configuration des Clés API (Onglet **Configuration**)

1. Ouvrez l'onglet **Configuration** dans l'application.
2. Entrez vos clés **Client ID**, **Client Secret** (Strava) et le **Notion Token**.
3. Entrez l'identifiant de votre **Database ID Notion** (voir 3.4).
4. Cliquez sur **"Sauvegarder la Configuration"**. Ces clés sont stockées localement dans un fichier `.env`.

### 3.2. Étape 2 : Autorisation Strava (Onglet **Connexion Strava**)

1. Cliquez sur le bouton **"Autoriser Strava"**.
2. Votre navigateur s'ouvrira, vous demandant d'accorder l'accès à l'application sur Strava.
3. **Accordez l'accès.** L'application récupérera et stockera automatiquement le **`REFRESH_TOKEN`** nécessaire pour maintenir la connexion Strava active.

### 3.3. Étape 3 : Démarrage du Service API (Onglet **Service API**)

1. Cliquez sur le bouton **"Démarrer le Service API"**.
2. Le serveur Flask démarre en arrière-plan.

### 3.4. 📐 Structure de la Base de Données Notion

Pour que la synchronisation fonctionne, votre base de données cible dans Notion **doit impérativement** avoir les propriétés suivantes. Veuillez respecter le nommage et le type exacts :

| Propriété Notion | Type | Correspondance Strava |
| --- | --- | --- |
| **Activity Name** (ou **Nom**) | Titre | Nom de l'activité |
| **Date** | Date | Date de début de l'activité |
| **Activity ID** | Nombre | Identifiant unique de Strava |
| **Type** | Sélection | Type d'activité (Course, Vélo, etc.) |
| **Distance** | Nombre | Distance parcourue (en mètres) |
| **Durée** | Nombre | Temps de mouvement (en secondes) |
| **D+** | Nombre | Gain d'élévation (en mètres) |
| **Calorie** | Nombre | Calories dépensées |


| Endpoint | Méthode | Rôle |
| --- | --- | --- |
| `/auth/strava` | `GET` | Gère le processus initial d'échange de code contre un `REFRESH_TOKEN`. |
| `/webhook` | `GET` | **Vérification** de l'abonnement par Strava (étape de configuration). |
| `/webhook` | `POST` | **Réception** du *payload* d'une nouvelle activité Strava pour le traitement et l'insertion dans Notion. |
