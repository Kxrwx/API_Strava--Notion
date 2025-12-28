# models/notion_client.py
import requests
import re
from models.config_manager import ConfigManager

class NotionClient:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.token = self.config_manager.get("NOTION_TOKEN")
        
        # L'extraction doit garantir un format UUID 8-4-4-4-12 valide
        db_url_or_id = self.config_manager.get("NOTION_DATABASE_URL")
        self.database_id = self._extract_database_id(db_url_or_id)
        
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        # Vérification critique après l'extraction
        if not self._is_valid_uuid(self.database_id):
            raise ValueError(
                f"L'ID de base de données Notion extrait ('{self.database_id}') n'est pas un UUID valide (format attendu: 8-4-4-4-12). "
                "Veuillez vérifier NOTION_DATABASE_URL dans le .env."
            )


    def _is_valid_uuid(self, uuid_string):
        """Vérifie si la chaîne est un UUID formaté correctement (8-4-4-4-12)."""
        # Motif Regex pour l'UUID standard de 36 caractères (incluant les 4 tirets)
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
        return bool(uuid_pattern.match(uuid_string))


    def _extract_database_id(self, url_or_id: str) -> str:
        """
        Extrait l'ID de la DB (32 caractères) et le formate en UUID standard 
        (8-4-4-4-12) si nécessaire.
        """
        # 1. Tente de trouver les 32 caractères hexadécimaux
        # Cela capture l'ID brut, qu'il soit dans une URL ou un ID mal formaté.
        match = re.search(r'([a-f0-9]{32})', url_or_id, re.IGNORECASE)
        
        raw_id = ""
        if match:
            raw_id = match.group(1).lower()
        else:
            # Si aucune correspondance n'est trouvée, on nettoie l'entrée.
            raw_id = url_or_id.replace('-', '').strip().lower()

        # Si l'ID brut a la bonne longueur, on le reformate
        if len(raw_id) == 32:
            # Formatage en UUID standard (8-4-4-4-12)
            parts = [
                raw_id[0:8],
                raw_id[8:12],
                raw_id[12:16],
                raw_id[16:20],
                raw_id[20:32]
            ]
            return "-".join(parts)
        
        # Si on n'a pas pu obtenir 32 caractères, on retourne l'entrée originale
        return url_or_id # Cette valeur sera testée par _is_valid_uuid dans __init__ et devrait échouer


    def _get_mapping(self):
        """Récupère tous les mappings MAP_* depuis le ConfigManager."""
        return {
            key: self.config_manager.get(key)
            for key in self.config_manager._config 
            if key.startswith('MAP_')
        }

    def is_activity_synced(self, strava_id: int) -> bool:
        """Vérifie si une activité existe déjà dans la base de données Notion."""
        
        mapping = self._get_mapping()
        strava_id_column = mapping.get('MAP_STRAVA_ID')
        
        if not strava_id_column:
            print("ERREUR NOTION: MAP_STRAVA_ID non défini. Impossible de vérifier la présence. Risque de doublons.")
            return False 

        filter_data = {
            "filter": {
                "property": strava_id_column,
                "number": {
                    "equals": strava_id
                }
            }
        }
        
        response = requests.post(
            f"https://api.notion.com/v1/databases/{self.database_id}/query",
            headers=self.headers,
            json=filter_data
        )

        if response.status_code == 200:
            results = response.json().get('results', [])
            return len(results) > 0
        else:
            # L'erreur 404 (object_not_found) est critique : DB introuvable ou permissions.
            if response.status_code == 404:
                 # Le Poller loguera cette exception de manière plus visible
                 raise Exception(
                     f"Erreur 404 (Base de données non trouvée/partagée). ID utilisé: {self.database_id}. "
                     "Veuillez CONFIRMER:\n1. Le partage de la DB avec l'intégration Notion.\n2. Le champ NOTION_DATABASE_URL est correct."
                 )
            
            print(f"Erreur API Notion (is_synced) : {response.status_code} - {response.text}")
            return False 

    def _create_notion_properties(self, activity):
        """Construit le dictionnaire de propriétés Notion à partir d'une activité Strava."""
        
        mapping = self._get_mapping()

        # Conversion et calculs de base
        distance_km = activity.get('distance', 0) / 1000.0
        duration_min = activity.get('moving_time', 0) / 60.0
        
        properties = {
            # Titre
            mapping['MAP_TITLE']: {
                "title": [{"text": {"content": activity.get('name', 'Activité sans nom')}}]
            },
            # ID Strava (Unique)
            mapping['MAP_STRAVA_ID']: {
                "number": activity['id']
            },
            # Date
            mapping['MAP_DATE']: {
                "date": {"start": activity['start_date_local'].split('T')[0]} 
            },
            # Distance
            mapping['MAP_DISTANCE']: {
                "number": round(distance_km, 2)
            },
            # Durée
            mapping['MAP_DURATION']: {
                "number": round(duration_min, 2)
            },
            # Type de Sport
            mapping['MAP_TYPE']: {
                "select": {"name": activity.get('type', 'Inconnu')}
            },
            # Gain d'Altitude
            mapping['MAP_ELEVATION']: {
                "number": activity.get('total_elevation_gain')
            },

            # NOUVELLES PROPRIÉTÉS AJOUTÉES :
            
            # Calories (si disponible)
            mapping.get('MAP_CALORIES', 'Calories'): {
                "number": activity.get('calories')
            },
            
            # Fréquence Cardiaque Moyenne (si disponible)
            mapping.get('MAP_HEART_RATE', 'FC Moy'): {
                "number": activity.get('average_heartrate')
            },
            
            # Effort Perçu (Rate of Perceived Exertion)
            mapping.get('MAP_PERCEIVED_EXERTION', 'RPE'): {
                "number": activity.get('perceived_exertion') 
            },
            
            # Notes/Description
            mapping.get('MAP_DESCRIPTION', 'Notes'): {
                "rich_text": [{"text": {"content": activity.get('description', '')}}]
            },
            
        }
        
        # Nettoyage : Exclure les propriétés de type 'number' dont la valeur est None
        final_properties = {}
        for prop_name, prop_data in properties.items():
            if not prop_name or prop_name.strip() == "":
                continue 

            if 'number' in prop_data:
                # Si la valeur est None, on exclut la propriété du JSON
                if prop_data['number'] is not None:
                     final_properties[prop_name] = prop_data
            else:
                # Inclure les autres types (Title, Text, Date, Select) même s'ils sont vides
                final_properties[prop_name] = prop_data

        return final_properties

    def sync_activity(self, activity: dict):
        """Ajoute une activité à la base de données Notion."""
        
        properties = self._create_notion_properties(activity)
        
        if not properties:
            raise ValueError("Propriétés Notion non générées. Vérifiez le mapping ou si Strava a fourni des données.")

        data = {
            "parent": {"database_id": self.database_id},
            "properties": properties
        }
        
        response = requests.post(
            "https://api.notion.com/v1/pages",
            headers=self.headers,
            json=data
        )

        if response.status_code != 200:
            # Soulever une exception détaillée pour que le Poller puisse la loguer
            raise Exception(f"Échec de l'ajout à Notion (Code {response.status_code}). Réponse API: {response.text}")
        
        return response.json()