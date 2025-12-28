# models/config_manager.py
import os
from dotenv import load_dotenv, set_key
import re 

class ConfigManager:
    """
    Gère la configuration et les secrets de l'application
    à partir du fichier .env.
    """

    def __init__(self):
        load_dotenv()
        
        # Initialisation du cache de configuration avec les valeurs par défaut
        self._config = {
            "STRAVA_CLIENT_ID": os.getenv("STRAVA_CLIENT_ID"),
            "STRAVA_CLIENT_SECRET": os.getenv("STRAVA_CLIENT_SECRET"),
            "STRAVA_REFRESH_TOKEN": os.getenv("STRAVA_REFRESH_TOKEN"),
            "STRAVA_ACCESS_TOKEN": os.getenv("STRAVA_ACCESS_TOKEN"),
            "NOTION_TOKEN": os.getenv("NOTION_TOKEN"),
            "NOTION_DATABASE_URL": os.getenv("NOTION_DATABASE_URL"),
            "FLASK_PORT": os.getenv("FLASK_PORT") or "5000",
            
            # --- CLÉS DE MAPPING AVEC VALEURS PAR DÉFAUT ---
            "MAP_TITLE": os.getenv("MAP_TITLE") or "Nom",
            "MAP_STRAVA_ID": os.getenv("MAP_STRAVA_ID") or "ID Strava",
            "MAP_DATE": os.getenv("MAP_DATE") or "Date",
            "MAP_DISTANCE": os.getenv("MAP_DISTANCE") or "Distance (km)",
            "MAP_DURATION": os.getenv("MAP_DURATION") or "Durée (min)",
            "MAP_TYPE": os.getenv("MAP_TYPE") or "Sport",
            "MAP_ELEVATION" : os.getenv("MAP_ELEVATION") or "D+",
            "MAP_CALORIES" : os.getenv("MAP_CALORIES") or "Calories",
            "MAP_HEART_RATE" : os.getenv("MAP_HEART_RATE") or "FC Moy",
            "MAP_PERCEIVED_EXERTION" : os.getenv("MAP_PERCEIVED_EXERTION") or "EP",
            "MAP_DESCRIPTION" : os.getenv("MAP_DESCRIPTION") or "Notes",
        }

    def _extract_notion_id(self, url_or_id: str) -> str:
        """Extrait l'ID propre (32 caractères) de la base de données Notion."""
        
        if "notion.so" in url_or_id:
            match = re.search(r'([a-f0-9]{32})', url_or_id)
            if match:
                return match.group(1)
            
            last_part = url_or_id.split('/')[-1]
            if last_part:
                cleaned_id = last_part.split('?')[0].replace('-', '')
                if len(cleaned_id) == 32:
                    return cleaned_id

        cleaned_id = url_or_id.replace('-', '')
        if len(cleaned_id) == 32:
             return cleaned_id
             
        return url_or_id


    def get(self, key: str):
        """Récupère une valeur de configuration. Applique l'extraction pour l'URL de la DB."""
        value = self._config.get(key)
        
        if key == "NOTION_DATABASE_URL" and value:
            return self._extract_notion_id(value)
            
        return value

    def set(self, key: str, value: str):
        """Met à jour une valeur dans le cache de configuration et l'enregistre dans .env."""
        self._config[key] = str(value)
        self._save_to_env(key, str(value))

    def _save_to_env(self, key: str, value: str):
        """Fonction utilitaire pour écrire une seule paire clé/valeur dans .env."""
        try:
            set_key(dotenv_path='.env', key_to_set=key, value_to_set=value)
        except Exception as e:
            print(f"Erreur lors de l'écriture dans .env pour la clé {key}: {e}")

    def load_configuration(self):
        """Recharge la configuration depuis le fichier .env."""
        load_dotenv()
        
        # Clés de base
        self._config["STRAVA_CLIENT_ID"] = os.getenv("STRAVA_CLIENT_ID")
        self._config["STRAVA_CLIENT_SECRET"] = os.getenv("STRAVA_CLIENT_SECRET")
        self._config["STRAVA_REFRESH_TOKEN"] = os.getenv("STRAVA_REFRESH_TOKEN")
        self._config["STRAVA_ACCESS_TOKEN"] = os.getenv("STRAVA_ACCESS_TOKEN")
        self._config["NOTION_TOKEN"] = os.getenv("NOTION_TOKEN")
        self._config["NOTION_DATABASE_URL"] = os.getenv("NOTION_DATABASE_URL")
        self._config["FLASK_PORT"] = os.getenv("FLASK_PORT") or "5000"
        
        # Clés de mapping
        self._config["MAP_TITLE"] = os.getenv("MAP_TITLE") or "Nom"
        self._config["MAP_STRAVA_ID"] = os.getenv("MAP_STRAVA_ID") or "ID Strava"
        self._config["MAP_DATE"] = os.getenv("MAP_DATE") or "Date"
        self._config["MAP_DISTANCE"] = os.getenv("MAP_DISTANCE") or "Distance (km)"
        self._config["MAP_DURATION"] = os.getenv("MAP_DURATION") or "Durée (min)"
        self._config["MAP_TYPE"] = os.getenv("MAP_TYPE") or "Sport"
        self._config["MAP_ELEVATION"] = os.getenv("MAP_ELEVATION") or "D+"
        self._config["MAP_CALORIES"] = os.getenv("MAP_CALORIES") or "Calories"
        self._config["MAP_HEART_RATE"] = os.getenv("MAP_HEART_RATE") or "FC Moy"
        self._config["MAP_PERCEIVED_EXERTION"] = os.getenv("MAP_PERCEIVED_EXERTION") or "EP"
        self._config["MAP_DESCRIPTION"] = os.getenv("MAP_DESCRIPTION") or "Notes"


    def save_configuration(self, updates: dict):
        """Sauvegarde plusieurs clés à la fois dans le fichier .env."""
        for key, value in updates.items():
            self._config[key] = str(value)
            self._save_to_env(key, str(value))