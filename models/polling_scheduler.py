# models/polling_scheduler.py
import time
import threading
import traceback
from datetime import datetime
import queue 

# Importations
from models.config_manager import ConfigManager
from models.strava_client import StravaClient
from models.notion_client import NotionClient 

class PollingScheduler:
    
    def __init__(self, config_manager: ConfigManager, interval_minutes=15, log_queue: queue.Queue = None):
        self.config_manager = config_manager
        self.interval = interval_minutes * 60  # intervalle en secondes
        self._stop_event = threading.Event()
        self.thread = None
        self.is_running = False
        self.last_check_time = None
        self.log_queue = log_queue 
        
        # Initialisation des clients
        self.strava_client = StravaClient(config_manager)
        self.notion_client = None 
        
    def _log(self, message):
        """Méthode helper pour envoyer un log à la console et au dashboard."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        if self.log_queue:
            self.log_queue.put(log_entry)

    def _create_notion_client(self):
        """
        Crée et retourne une nouvelle instance de NotionClient 
        en utilisant la configuration actuelle.
        """
        self._log("INFO: Création/Rafraîchissement du NotionClient avec la configuration actuelle.")
        try:
            self.config_manager.load_configuration() 
            # Si l'ID de la DB est mal formaté, le NotionClient lèvera une exception ici
            self.notion_client = NotionClient(self.config_manager)
            return self.notion_client
        except Exception as e:
            self._log(f"ERREUR: Échec de la création du NotionClient. Cause possible: ID DB Notion invalide ou Token invalide. Détails: {e}")
            raise 

    def _run(self):
        """Méthode de la boucle de Polling exécutée dans un thread séparé."""
        while not self._stop_event.is_set():
            try:
                self._log("--- Démarrage du cycle de polling ---")

                # 1. Rafraîchir les tokens Strava
                self.strava_client.refresh_access_token()
                
                # 2. S'assurer que le client Notion est prêt
                if not self.notion_client:
                    self._create_notion_client()
                    
                # 3. Synchroniser les activités
                self._sync_latest_activities()
                
                self.last_check_time = time.time()
                self._log("--- Cycle de polling terminé avec succès ---")

            except Exception as e:
                self._log(f"ERREUR CRITIQUE lors du cycle de polling : {e}")
                traceback.print_exc() 

            self._stop_event.wait(self.interval)

    def _sync_activities_list(self, activities_list: list, sync_type: str):
        """Logique interne pour synchroniser une liste d'activités données."""
        synced_count = 0
        total_count = len(activities_list)
        
        if not activities_list:
            self._log(f"INFO: Aucune activité à vérifier ({sync_type}).")
            return
            
        self._log(f"INFO: {total_count} activités trouvées ({sync_type}). Vérification de la synchronisation...")

        for i, activity in enumerate(activities_list):
            if total_count > 10 and i % 50 == 0 and i > 0:
                 self._log(f"INFO: Progression {sync_type}: {i}/{total_count} activités vérifiées.")

            try:
                if not self.notion_client.is_activity_synced(activity['id']):
                    self.notion_client.sync_activity(activity)
                    synced_count += 1
            except Exception as sync_e:
                self._log(f"ERREUR lors de la synchronisation de l'activité {activity.get('id')}: {sync_e}")
        
        self._log(f"SUCCÈS: {synced_count} activités ont été ajoutées à Notion ({sync_type}).")


    def _sync_latest_activities(self):
        """[Polling périodique] Récupère UNIQUEMENT les dernières activités Strava."""
        try:
            latest_activities = self.strava_client.get_latest_activities(per_page=10)
            self._sync_activities_list(latest_activities, "Polling Périodique")
        except Exception as e:
            self._log(f"ERREUR de synchronisation (Strava ou Notion) : {e}")
            raise
    
    # -----------------------------------------------------
    # MÉTHODES DE SYNCHRONISATION MANUELLE
    # -----------------------------------------------------
    
    def sync_all_activities(self):
        """[Sync. Manuelle/Initiale] Déclenche une synchronisation complète."""
        def historical_sync_task():
            self._log("--- Démarrage de la SYNCHRONISATION HISTORIQUE ---")
            
            try:
                self.strava_client.refresh_access_token()
                all_activities = self.strava_client.get_all_activities() 
                
                if not isinstance(all_activities, list):
                     self._log("ERREUR: get_all_activities n'a pas retourné une liste. Annulation.")
                     return
                
                self._sync_activities_list(all_activities, "Synchronisation Historique")
                
                self.last_check_time = time.time()
                self._log("--- Synchronisation HISTORIQUE terminée. ---")

            except Exception as e:
                self._log(f"ERREUR lors de la synchronisation HISTORIQUE : {e}")
                traceback.print_exc()
                
        sync_thread = threading.Thread(target=historical_sync_task)
        sync_thread.daemon = True
        sync_thread.start()


    def sync_now(self):
        """[Sync. Manuelle/Rapide] Déclenche immédiatement une vérification rapide."""
        def immediate_sync_task():
            self._log("--- Démarrage de la synchronisation rapide ---")
            try:
                self.strava_client.refresh_access_token()
                self._sync_latest_activities()
                self.last_check_time = time.time()
                self._log("--- Synchronisation rapide terminée avec succès ---")
            except Exception as e:
                self._log(f"ERREUR lors de la synchronisation rapide : {e}")
                traceback.print_exc()

        sync_thread = threading.Thread(target=immediate_sync_task)
        sync_thread.daemon = True
        sync_thread.start()


    def start(self):
        """Démarre le thread de polling."""
        if not self.is_running:
            self._stop_event.clear()
            self.thread = threading.Thread(target=self._run)
            self.thread.daemon = True
            self.thread.start()
            self.is_running = True
            self.last_check_time = time.time() 

    def stop(self):
        """Arrête le thread de polling."""
        if self.is_running:
            self._log("INFO: Signal d'arrêt envoyé au thread de polling.")
            self._stop_event.set()
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)
            self.is_running = False
            self._log("INFO: Service de polling arrêté.")