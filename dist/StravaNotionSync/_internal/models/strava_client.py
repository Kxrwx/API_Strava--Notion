# models/strava_client.py
import requests
from .config_manager import ConfigManager
import time 

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_URL = "https://www.strava.com/api/v3"
# La variable STRAVA_PUSH_API_URL n'est pas utilisée en mode Polling
# STRAVA_PUSH_API_URL = "https://api.strava.com/api/v3/push_subscriptions" 

class StravaClient:
    """Client pour interagir avec l'API Strava."""

    def __init__(self, config: ConfigManager):
        self.config = config
        self.client_id = config.get("STRAVA_CLIENT_ID")
        self.client_secret = config.get("STRAVA_CLIENT_SECRET")
        self.refresh_token = config.get("STRAVA_REFRESH_TOKEN")
        self.access_token = self.config.get("STRAVA_ACCESS_TOKEN")

    def _get_headers(self):
        """Retourne les headers d'autorisation."""
        if not self.access_token:
            # Tente de rafraîchir si le token est manquant
            self.refresh_access_token() 
            
        if not self.access_token:
            # Si le rafraîchissement échoue, on lève une erreur
            raise Exception("Access Token Strava manquant. Veuillez vous authentifier (onglet 4).")
            
        return {'Authorization': f'Bearer {self.access_token}'}

    def get_auth_url(self, callback_url):
        """Génère l'URL pour l'autorisation OAuth de Strava."""
        # Correction mineure de la redirection: L'URL doit être exacte
        formatted_callback = callback_url 
        return (f"{STRAVA_AUTH_URL}?client_id={self.client_id}&response_type=code"
                f"&redirect_uri={formatted_callback}&scope=activity:read_all")

    def exchange_code_for_token(self, code):
        """Échange le code d'autorisation contre un token initial."""
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'grant_type': 'authorization_code'
        }
        response = requests.post(STRAVA_TOKEN_URL, data=payload)
        response.raise_for_status()
        data = response.json()
        
        new_refresh_token = data.get('refresh_token')
        self.config.set('STRAVA_REFRESH_TOKEN', new_refresh_token)
        self.refresh_token = new_refresh_token
        
        new_access_token = data.get('access_token')
        self.config.set('STRAVA_ACCESS_TOKEN', new_access_token)
        self.access_token = new_access_token
        
        self.config.save_configuration({'STRAVA_REFRESH_TOKEN': new_refresh_token, 
                                        'STRAVA_ACCESS_TOKEN': new_access_token})
        
        return new_refresh_token

    def refresh_access_token(self):
        """Rafraîchit le token d'accès en utilisant le refresh token."""
        if not self.refresh_token:
            print("AVERTISSEMENT: Refresh Token Strava manquant. Impossible de rafraîchir l'Access Token.")
            return None 

        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }
        
        try:
            response = requests.post(STRAVA_TOKEN_URL, data=payload)
            response.raise_for_status()
            data = response.json()
            
            self.access_token = data.get('access_token')
            if 'refresh_token' in data: 
                # Strava peut renvoyer un nouveau refresh token, on l'enregistre
                self.config.set('STRAVA_REFRESH_TOKEN', data.get('refresh_token'))
                self.refresh_token = data.get('refresh_token') 
            
            self.config.set('STRAVA_ACCESS_TOKEN', self.access_token) 
            
            # Sauvegarder immédiatement les nouveaux tokens
            self.config.save_configuration({'STRAVA_ACCESS_TOKEN': self.access_token,
                                            'STRAVA_REFRESH_TOKEN': self.refresh_token})
            print("INFO: Access Token Strava rafraîchi et sauvegardé avec succès.")
            return self.access_token
            
        except requests.exceptions.HTTPError as e:
             print(f"ERREUR lors du rafraîchissement du token Strava (HTTP {e.response.status_code}).")
             print(f"Réponse: {e.response.text}")
             raise Exception(f"Échec de l'Access Token Strava: {e}")
        except Exception as e:
             print(f"ERREUR inattendue lors du rafraîchissement du token Strava: {e}")
             raise

    def get_activity_details(self, activity_id):
        """Récupère les détails d'une activité spécifique."""
        headers = self._get_headers()
        url = f"{STRAVA_API_URL}/activities/{activity_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    # ----------------------------------------------------------------------
    # CORRECTION: Nouvelle méthode pour le Polling (récupère plus d'une activité)
    # ----------------------------------------------------------------------
    def get_latest_activities(self, per_page=10):
        """
        Récupère les N dernières activités de l'athlète (par défaut les 10 dernières).
        Utilisé pour le Polling périodique et la 'Sync. Rapide'.
        """
        headers = self._get_headers()
        # Requête pour 1 page, N éléments, trié par défaut par date décroissante
        url = f"{STRAVA_API_URL}/athlete/activities?per_page={per_page}&page=1" 
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Retourne la liste des activités (ou une liste vide)
        return response.json()


    # ----------------------------------------------------------------------
    # NOUVELLE MÉTHODE: Pour la Synchronisation Historique (rattrapage)
    # ----------------------------------------------------------------------
    def get_all_activities(self):
        """
        Récupère l'historique COMPLET des activités de l'athlète, en gérant la pagination.
        Utilisé pour la 'Sync. Historique'.
        """
        headers = self._get_headers()
        all_activities = []
        page = 1
        per_page = 200 # Maximum autorisé par Strava
        
        print("INFO: Démarrage de la récupération de l'historique Strava (Pagination activée)...")
        
        while True:
            url = f"{STRAVA_API_URL}/athlete/activities?per_page={per_page}&page={page}"
            
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                activities_page = response.json()

                if not activities_page:
                    print(f"INFO: Page {page} vide. Fin de l'historique.")
                    break # Arrêter si la page est vide (fin de l'historique)

                all_activities.extend(activities_page)
                print(f"INFO: Récupéré {len(activities_page)} activités de la page {page}. Total actuel: {len(all_activities)}")
                
                # Si le nombre d'activités retournées est inférieur à per_page, c'est la dernière page
                if len(activities_page) < per_page:
                    break
                
                page += 1
                # Ajout d'un petit délai pour respecter les limites de débit de l'API Strava (Rate Limiting)
                time.sleep(0.5) 

            except requests.exceptions.HTTPError as e:
                print(f"ERREUR HTTP lors de la pagination Strava à la page {page}: {e}")
                print(f"Réponse: {e.response.text}")
                break
            except Exception as e:
                print(f"ERREUR inattendue lors de la récupération historique: {e}")
                break

        print(f"SUCCÈS: Historique Strava complet récupéré. Total: {len(all_activities)} activités.")
        return all_activities


    # Les méthodes Webhook sont neutralisées en mode Polling.
    def subscribe_webhook(self, callback_url, verify_token):
        print("NOTE: La méthode Webhook n'est pas utilisée en mode Polling.")
        pass
        
    def unsubscribe_webhook(self):
        print("NOTE: La méthode Webhook n'est pas utilisée en mode Polling.")
        pass