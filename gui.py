# gui.py
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import webbrowser
import os
import sys
import time 
from datetime import datetime
import queue 

# --- Importations des modules locaux ---
try:
    from models.config_manager import ConfigManager
    from models.strava_client import StravaClient
    from models.polling_scheduler import PollingScheduler 
    # Importation de la fonction corrigée pour le démarrage du serveur Flask
    from app import run_flask_server 
except ImportError as e:
    messagebox.showerror("Erreur d'Importation", 
                          f"Erreur de dépendance: {e}. Vérifiez les modules (config_manager, strava_client, polling_scheduler et la présence de run_flask_server dans app.py).")
    sys.exit(1)


class StravaNotionGUI(tk.Tk):
    """Interface graphique pour configurer, autoriser et lancer la synchronisation Strava-Notion."""
    
    def __init__(self):
        super().__init__()
        self.title("Strava-Notion Sync Configuration (Mode Polling)")
        self.geometry("800x850") 
        
        self.config_manager = ConfigManager()
        self.flask_port = self.config_manager.get("FLASK_PORT") or "5000"
        
        self.strava_client = StravaClient(self.config_manager) 
        
        self.log_queue = queue.Queue() 
        self.total_synced_count = tk.IntVar(value=0) 
        self.last_sync_success = tk.StringVar(value="Non vérifié")
        
        self.flask_server_thread = None # Thread pour le serveur Flask
        
        # NOUVEAU: Variable pour le minuteur de Polling
        self.time_until_next_check = tk.StringVar(value="--:--") 

        try:
              # Polling Scheduler utilise maintenant un log_queue
              self.polling_scheduler = PollingScheduler(self.config_manager, interval_minutes=15, log_queue=self.log_queue) 
        except Exception as e:
              messagebox.showwarning("Avertissement Initialisation", 
                                     f"Échec de l'initialisation du Polling Scheduler. Cause : {e}. "
                                     "Vous ne pourrez pas démarrer le service avant d'avoir corrigé la config.")
              self.polling_scheduler = None 

        self.service_running = False
        
        self._create_widgets()
        self._load_config_to_gui() 
        self.protocol("WM_DELETE_WINDOW", self._on_closing) 
        self.after(100, self._process_log_queue) 
        
        # CHANGEMENT: Mise à jour du tableau de bord toutes les secondes (pour le minuteur)
        self.after(1000, self._update_dashboard_metrics) 

    # ----------------------------------------------------------------------
    # MÉTHODES POUR FLASK EN THREAD
    # ----------------------------------------------------------------------

    def _start_flask_server(self):
        """Démarre le serveur Flask dans un thread séparé pour l'OAuth."""
        try:
            # Vérification de l'existence et de l'état du thread pour éviter les doubles démarrages
            if self.flask_server_thread and self.flask_server_thread.is_alive():
                self.log_queue.put("--- Serveur Flask : Déjà actif. ---")
                return

            self.log_queue.put(f"--- Serveur Flask : Démarrage en arrière-plan sur le port {self.flask_port}... ---")
            
            # Le thread est lancé en utilisant la fonction importée run_flask_server 
            self.flask_server_thread = threading.Thread(
                target=run_flask_server, 
                args=(self.config_manager, self.strava_client), 
                daemon=True # Tue le thread lorsque le programme principal se ferme
            )
            self.flask_server_thread.start()
            # Donner un court instant au serveur pour s'initialiser
            time.sleep(1) 
            
        except Exception as e:
            self.log_queue.put(f"--- ERREUR CRITIQUE: Échec du démarrage du serveur Flask: {e} ---")
            # Lever l'exception pour que _launch_strava_auth puisse la rattraper avant d'ouvrir le navigateur
            raise 

    # ----------------------------------------------------------------------
    # MÉTHODES D'ACTION
    # ----------------------------------------------------------------------
    
    def _validate_sync_prerequisites(self):
        """Vérifie les prérequis avant de lancer une synchronisation."""
        if not self.polling_scheduler:
              messagebox.showwarning("Initialisation Manquante", "Le Polling Scheduler n'a pas pu être initialisé. Vérifiez les dépendances ou relancez l'application.")
              return False

        if not self.config_manager.get("STRAVA_REFRESH_TOKEN"):
              messagebox.showwarning("Autorisation Manquante", "Veuillez d'abord autoriser Strava (Onglet 4) et obtenir un Refresh Token.")
              return False
        if not (self.config_manager.get("NOTION_TOKEN") and self.config_manager.get("NOTION_DATABASE_URL")):
            messagebox.showwarning("Configuration Manquante", "Veuillez vérifier le Token Notion et l'URL de la Base de Données (Onglet 1).")
            return False
        return True
        
    def _manual_sync_all(self):
        """Déclenche une synchronisation HISTORIQUE complète."""
        if not self._validate_sync_prerequisites():
            return
            
        try:
            # S'assurer que les dernières infos sont utilisées
            self._save_config() 
            self.polling_scheduler._create_notion_client()
            self.polling_scheduler.sync_all_activities()
            messagebox.showinfo("Synchronisation Historique", 
                                 "Synchronisation Historique déclenchée. "
                                 "Consultez l'onglet 'Tableau de Bord & Logs'.")
            
        except Exception as e:
            messagebox.showerror("Erreur Critique", f"Échec de la synchronisation historique. Cause: {e}")

    def _manual_sync_now(self):
        """Déclenche une synchronisation RAPIDE (dernière activité)."""
        if not self._validate_sync_prerequisites():
            return

        try:
            # S'assurer que les dernières infos sont utilisées
            self._save_config() 
            self.polling_scheduler._create_notion_client()
            self.polling_scheduler.sync_now()
            messagebox.showinfo("Synchronisation Rapide", "Synchronisation rapide déclenchée ! Consultez l'onglet 'Tableau de Bord & Logs'.")
            
        except Exception as e:
            messagebox.showerror("Erreur de Sync.", f"Échec de la synchronisation rapide. Cause: {e}")


    def _toggle_polling_service(self):
        """Démarre/Arrête le planificateur de Polling."""
        
        if not self._validate_sync_prerequisites():
              return

        if self.service_running:
            # Arrêter le service
            self.polling_scheduler.stop()
            self.service_running = False
            self.service_status.set("Service: Arrêté")
            self.toggle_button.config(text="▶️ Démarrer le Polling (Vérif. toutes les 15 min)", state=tk.NORMAL)
            self.last_check_status.set("Dernière vérification: Arrêté")
            self.polling_status_db.set("Inactif")
            # NOUVEAU: Réinitialisation du minuteur
            self.time_until_next_check.set("--:--")
            self.log_queue.put(f"--- {datetime.now().strftime('%H:%M:%S')} --- Service de Polling arrêté.")

        else:
            # Démarrer le service
            try:
                # S'assurer que les dernières infos sont utilisées
                self._save_config() 
                self.polling_scheduler._create_notion_client()
                
                self.polling_scheduler.start()
                self.service_running = True
                self.service_status.set("✅ Service ACTIF (Vérification en cours...)")
                self.toggle_button.config(text="◼️ Arrêter le Service", state=tk.NORMAL)
                self.polling_status_db.set("ACTIF")
                self._update_dashboard_metrics() 
                self.log_queue.put(f"--- {datetime.now().strftime('%H:%M:%S')} --- Service de Polling DÉMARRÉ.")
                messagebox.showinfo("Démarrage Réussi", 
                                     "Le Polling est actif et vérifiera Strava toutes les 15 minutes."
                                     "\nConsultez l'onglet 'Tableau de Bord & Logs' pour le suivi.")
            except Exception as e:
                self.service_status.set("❌ Échec de l'Activation")
                self.log_queue.put(f"--- {datetime.now().strftime('%H:%M:%S')} --- ERREUR CRITIQUE: Échec du démarrage. Cause: {e}")
                messagebox.showerror("Erreur Critique", f"Échec du démarrage du Polling. Cause : {e}")
                
    # ----------------------------------------------------------------------
    # Méthode _launch_strava_auth
    # ----------------------------------------------------------------------

    def _launch_strava_auth(self):
        """
        Démarre le processus d'autorisation Strava : 
        1. Sauvegarde la config.
        2. Valide les ID et Port.
        3. Démarre Flask en thread.
        4. Ouvre l'URL d'autorisation.
        """
        
        # 1. Sauvegarde et mise à jour des configurations en mémoire
        try:
              self._save_config() # Sauvegarde et recharge la configuration dans self.config_manager
        except Exception as e:
             messagebox.showwarning("Avertissement", f"Impossible de sauvegarder la configuration actuelle, vérifiez les droits du fichier .env. Erreur: {e}")
             pass 

        client_id_str = self.config_manager.get("STRAVA_CLIENT_ID")
        flask_port = self.config_manager.get("FLASK_PORT")
        
        # 2. Validation Critique des configurations
        
        if not client_id_str or not client_id_str.strip():
            messagebox.showwarning("Configuration Manquante", 
                                 "Le champ 'ID Client Strava' est vide. Veuillez le remplir (Onglet 1) et sauvegarder.")
            return

        if not flask_port or not flask_port.strip():
              messagebox.showwarning("Configuration Manquante", 
                                     "Le champ 'Port Flask' est vide. Veuillez le remplir (Onglet 1) et sauvegarder.")
              return
              
        # L'ID Strava doit être un nombre entier
        if not client_id_str.strip().isdigit():
              messagebox.showerror("Erreur de Format", 
                                     "L'ID Client Strava doit être un nombre entier valide. "
                                     "Veuillez corriger la valeur dans l'Onglet 1.")
              return
              
        # Le port doit être un nombre entier
        if not flask_port.strip().isdigit():
              messagebox.showerror("Erreur de Format", 
                                     "Le Port Flask doit être un nombre entier valide. "
                                     "Veuillez corriger la valeur dans l'Onglet 1.")
              return


        try:
            # 3. Démarrage du serveur Flask en arrière-plan
            self._start_flask_server()
            
            # 4. Lancement de la requête d'autorisation
            # L'URI DOIT correspondre à la route dans app.py (/auth/callback)
            redirect_uri = f"http://localhost:{flask_port.strip()}/auth/callback" 
            auth_url = self.strava_client.get_auth_url(redirect_uri)
            
            self._open_url(auth_url)
            
            messagebox.showinfo("Autorisation Strava", 
                                 "Une fenêtre de navigateur s'est ouverte pour l'autorisation Strava."
                                 "\n\nAprès acceptation, cliquez sur le bouton 'Vérifier le Statut' ci-dessous."
                                 )
            
        except Exception as e:
            # Cette exception attrape les erreurs dans _start_flask_server OU get_auth_url (ex: ID/Secret invalide)
            messagebox.showerror("Erreur Critique d'Autorisation", 
                                 f"Échec du processus. Assurez-vous que votre Client ID et votre Client Secret sont corrects (Onglet 1) et que le port n'est pas déjà utilisé. Cause: {e}")

    # ----------------------------------------------------------------------
    # FIN DES MÉTHODES D'ACTION
    # ----------------------------------------------------------------------

    def _open_url(self, url):
        """Ouvre l'URL spécifiée dans le navigateur par défaut."""
        webbrowser.open_new_tab(url)

    def _create_widgets(self):
        """Crée tous les éléments de l'interface utilisateur (Notebook, onglets, champs)."""
        
        notebook = ttk.Notebook(self)
        notebook.pack(pady=10, padx=10, expand=True, fill="both")

        # --- Onglet 1: Configuration des Secrets --- 
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="1. Configuration des Secrets")
        
        main_config_frame = ttk.Frame(config_frame)
        main_config_frame.pack(pady=10, padx=10, expand=True, fill="both")
        
        self._create_help_panel_general(main_config_frame).pack(fill='x', pady=5) 
        
        input_frame = ttk.LabelFrame(main_config_frame, text="Clés API et Base de Données")
        input_frame.pack(fill='x', pady=10)
        
        self.config_inputs = self._create_config_fields(input_frame)
        
        # --- Onglet 2: Mapping des Colonnes Notion ---
        mapping_frame = ttk.Frame(notebook)
        notebook.add(mapping_frame, text="2. Mapping des Colonnes Notion")
        
        map_info_frame = ttk.Frame(mapping_frame)
        map_info_frame.pack(pady=10, padx=10, fill='x')
        ttk.Label(map_info_frame, text="Entrez les NOMS EXACTS des colonnes de votre base de données Notion.", font=("Arial", 10, "bold")).pack(pady=(0, 10))
        ttk.Label(map_info_frame, text="⚠️ Respectez la CASSE, les ACCENTS et le TYPE (Ex : 'Distance (km)' doit être Numéro).", foreground='red').pack()

        map_input_frame = ttk.LabelFrame(mapping_frame, text="Mapping Strava vers Notion")
        map_input_frame.pack(fill='x', padx=10, pady=10)
        
        self.map_inputs = self._create_mapping_fields(map_input_frame)

        # --- Onglet 3: Service Polling ---
        service_frame = ttk.Frame(notebook)
        notebook.add(service_frame, text="3. Démarrage du Service Polling")

        # Statut du service
        self.service_status = tk.StringVar(value="Service: Arrêté")
        ttk.Label(service_frame, textvariable=self.service_status, font=("Arial", 12, "bold")).pack(pady=20)
        
        # Bouton Démarrer/Arrêter
        self.toggle_button = ttk.Button(service_frame, text="▶️ Démarrer le Polling (Vérif. toutes les 15 min)", command=self._toggle_polling_service)
        self.toggle_button.pack(pady=10)
        
        # SÉPARATION et BOUTONS DE SYNCHRONISATION MANUELLE
        ttk.Separator(service_frame, orient='horizontal').pack(fill='x', padx=20, pady=10)

        # Bouton Sync. Rapide (dernière activité, pour test)
        ttk.Label(service_frame, text="Synchronisations Manuelles :", font=("Arial", 10, "bold")).pack()
        ttk.Button(service_frame, text="⚡ Sync. RAPIDE (Dernière activité)", command=self._manual_sync_now).pack(pady=5)
        
        # Bouton Sync. Historique (toutes les activités)
        ttk.Button(service_frame, text="🔁 Sync. HISTORIQUE (Rattrapage complet)", command=self._manual_sync_all).pack(pady=5)
        
        ttk.Separator(service_frame, orient='horizontal').pack(fill='x', padx=20, pady=10)

        # Logique de la dernière vérification (sera mis à jour par _update_dashboard_metrics)
        self.last_check_status = tk.StringVar(value="Dernière vérification: Jamais")
        ttk.Label(service_frame, textvariable=self.last_check_status).pack(pady=10)
        
        ttk.Separator(service_frame, orient='horizontal').pack(fill='x', padx=20, pady=10)
        
        ttk.Label(service_frame, text="* Le service ne fonctionne que lorsque cette fenêtre est ouverte. Le Polling utilise les ressources de votre machine.", 
                                     font=("Arial", 9, "italic")).pack()
        
        # --- Onglet 4: Connexion Strava (OAuth & Tokens) --- 
        auth_frame = ttk.Frame(notebook)
        notebook.add(auth_frame, text="4. Autorisation Strava (OAuth & Tokens)")
        
        self._create_help_panel_auth(auth_frame).pack(fill='x', pady=5) # Texte d'aide simplifié
        
        # Bouton mis à jour pour refléter l'étape 1 simplifiée
        self.auth_button = ttk.Button(auth_frame, text="🚀 Étape 1 : Lancer la Demande d'Autorisation Strava", command=self._launch_strava_auth)
        self.auth_button.pack(pady=20)
        
        ttk.Separator(auth_frame, orient='horizontal').pack(fill='x', padx=20, pady=10)
        
        token_display_frame = ttk.LabelFrame(auth_frame, text="Statut et Tokens Actuels")
        token_display_frame.pack(fill='x', padx=20, pady=10)

        self.token_status = tk.StringVar(value="Statut: En cours de vérification...")
        ttk.Label(token_display_frame, textvariable=self.token_status, font=("Arial", 12, "bold")).pack(pady=(5, 10))

        self.refresh_token_var = tk.StringVar(value="Non disponible (Autoriser d'abord)")
        ttk.Label(token_display_frame, text="Refresh Token :").pack(anchor='w', padx=5)
        ttk.Entry(token_display_frame, textvariable=self.refresh_token_var, width=80, state='readonly').pack(fill='x', padx=5, pady=2)

        self.access_token_var = tk.StringVar(value="Non disponible")
        ttk.Label(token_display_frame, text="Access Token (Temporaire) :").pack(anchor='w', padx=5)
        ttk.Entry(token_display_frame, textvariable=self.access_token_var, width=80, state='readonly').pack(fill='x', padx=5, pady=2)

        ttk.Button(auth_frame, text="🔄 Vérifier le Statut et Mettre à jour les Tokens", command=self._load_config_to_gui).pack(pady=10)
        
        # --- Nouvel Onglet : Dashboard ---
        dashboard_frame = ttk.Frame(notebook)
        notebook.add(dashboard_frame, text="5. Tableau de Bord & Logs")
        self._create_dashboard_frame(dashboard_frame)
        
        # Bouton de Sauvegarde Unique
        save_button = ttk.Button(self, text="💾 Sauvegarder TOUTES les Configurations", command=self._save_config)
        save_button.pack(pady=10)
        
        # Supprime l'appel après la création des widgets pour le laisser dans __init__ et ainsi le démarrer tout de suite
        # self._update_dashboard_metrics() 
        
    def _create_help_panel_general(self, master_frame):
        """Crée le panneau d'aide général (Onglet 1)."""
        help_frame = ttk.LabelFrame(master_frame, text="💡 Guide d'Aide Rapide & Instructions", padding=10)
        tk.Label(help_frame, text="1. Strava : Créez une application pour obtenir l'ID et le Secret.", justify=tk.LEFT, font=("Arial", 9, "bold")).pack(anchor='w')
        ttk.Button(help_frame, text="Accéder à Strava Developer 🔗", command=lambda: self._open_url("https://www.strava.com/settings/api")).pack(anchor='w', pady=(5, 5))
        tk.Label(help_frame, text="2. Notion : Créez une intégration, une Base de Données, et **PARTAGEZ** cette DB avec l'intégration.", justify=tk.LEFT, font=("Arial", 9, "bold")).pack(anchor='w')
        ttk.Button(help_frame, text="Accéder à Mes Intégrations Notion 🔗", command=lambda: self._open_url("https://www.notion.so/my-integrations")).pack(anchor='w', pady=(5, 10))
        tk.Label(help_frame, text=f"⚠️ Collez l'URL complète de votre Base de Données dans le champ ci-dessous. Le programme extrait l'ID tout seul.", fg='red', font=("Arial", 9, "bold")).pack(anchor='w', padx=15, pady=(5, 10))
        tk.Label(help_frame, text=f"Le port local utilisé pour l'OAuth Strava est : {self.flask_port}", font=("Arial", 8, "italic")).pack(anchor='w')
        return help_frame

    def _create_help_panel_auth(self, master_frame):
        """Crée le panneau d'aide pour l'autorisation Strava (Onglet 4)."""
        auth_help_frame = ttk.LabelFrame(master_frame, text="🔑 Processus d'Autorisation Strava (Automatisé)", padding=10)
        ttk.Label(auth_help_frame, text="Le processus d'authentification se fait en deux étapes :", font=("Arial", 10, "bold")).pack(anchor='w', pady=(0, 5))
        
        # Étape 1 simplifiée (lancement automatique du serveur)
        tk.Label(auth_help_frame, text="Étape 1 : Lancement de la Demande", justify=tk.LEFT).pack(anchor='w')
        tk.Label(auth_help_frame, text="   → Le micro-serveur Flask démarre automatiquement. Cliquez sur le bouton ci-dessous : votre navigateur s'ouvre sur la page d'autorisation Strava.", fg='blue').pack(anchor='w', padx=10)
        
        ttk.Separator(auth_help_frame, orient='horizontal').pack(fill='x', padx=5, pady=5)
        
        # Étape 2 simplifiée
        tk.Label(auth_help_frame, text="Étape 2 : Réception des Tokens", justify=tk.LEFT).pack(anchor='w')
        tk.Label(auth_help_frame, text="   → Après acceptation dans le navigateur, le serveur récupère le code.", justify=tk.LEFT).pack(anchor='w', padx=10)
        tk.Label(auth_help_frame, text="   → Le serveur échange ce code contre un Refresh Token, et le sauvegarde dans votre fichier .env.", justify=tk.LEFT).pack(anchor='w', padx=10)
        tk.Label(auth_help_frame, text="Vérifiez ensuite le 'Statut et Tokens Actuels' ci-dessous.", font=("Arial", 9, "bold")).pack(anchor='w', pady=(5, 0))
        return auth_help_frame


    def _create_config_fields(self, master_frame):
        """Crée les champs de saisie pour les configurations de base (Clés API)."""
        fields = {}
        config_labels = {
            "STRAVA_CLIENT_ID": "ID Client Strava :",
            "STRAVA_CLIENT_SECRET": "Secret Client Strava :",
            "NOTION_TOKEN": "Token d'Intégration Notion :",
            "NOTION_DATABASE_URL": "URL ou ID de la Base de Données Notion :",
            "FLASK_PORT": "Port Flask (pour OAuth) :",
        }

        row_num = 0
        for key, label_text in config_labels.items():
            label = ttk.Label(master_frame, text=label_text)
            label.grid(row=row_num, column=0, padx=5, pady=5, sticky='w')
            
            var = tk.StringVar()
            entry = ttk.Entry(master_frame, textvariable=var, width=50)
            entry.grid(row=row_num, column=1, padx=5, pady=5, sticky='ew')
            fields[key] = var
            row_num += 1
            
        master_frame.grid_columnconfigure(1, weight=1)
        return fields
        
    def _create_mapping_fields(self, master_frame):
        """Crée les champs de saisie pour le mapping Notion avec toutes les colonnes."""
        fields = {}
        mapping_fields = {
            "MAP_TITLE": ("Nom de l'Activité (Type Titre) :", "Nom"),
            "MAP_STRAVA_ID": ("ID Strava (Type Numéro) :", "ID Strava"),
            "MAP_DATE": ("Date de l'Activité (Type Date) :", "Date"),
            "MAP_DISTANCE": ("Distance (Type Numéro) :", "Distance (km)"),
            "MAP_DURATION": ("Durée (Type Numéro) :", "Durée (min)"),
            "MAP_TYPE": ("Type/Sport (Type Sélection) :", "Sport"),
            "MAP_ELEVATION": ("Gain d'Altitude (Type Numéro) :", "D+ (m)"), 
            "MAP_CALORIES": ("Calories (Type Numéro) :", "Calories"),
            "MAP_HEART_RATE": ("Fréq. Cardiaque Moy. (Type Numéro) :", "FC Moy"),
            "MAP_PERCEIVED_EXERTION": ("Effort Perçu (Type Numéro ou Sélection) :", "RPE"),
            "MAP_DESCRIPTION": ("Notes/Description (Type Texte) :", "Notes"),
        }

        row_num = 0
        for key, (label_text, default_value) in mapping_fields.items():
            ttk.Label(master_frame, text=label_text).grid(row=row_num, column=0, padx=5, pady=5, sticky='w')
            
            var = tk.StringVar(value=default_value)
            entry = ttk.Entry(master_frame, textvariable=var, width=50)
            entry.grid(row=row_num, column=1, padx=5, pady=5, sticky='ew')
            fields[key] = var
            row_num += 1
            
        master_frame.grid_columnconfigure(1, weight=1)
        return fields
        
    # MÉTHODE MODIFIÉE: Ajout de l'affichage du minuteur dans le Dashboard
    def _create_dashboard_frame(self, master_frame):
        """Crée l'interface du Tableau de Bord."""
        metrics_frame = ttk.LabelFrame(master_frame, text="📈 Métriques de Santé du Système", padding=10)
        metrics_frame.pack(fill='x', padx=10, pady=10)
        metrics_frame.columnconfigure(0, weight=1)
        metrics_frame.columnconfigure(1, weight=1)
        
        ttk.Label(metrics_frame, text="État du Polling :", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky='w', pady=5)
        self.polling_status_db = tk.StringVar(value="Inactif")
        ttk.Label(metrics_frame, textvariable=self.polling_status_db, font=("Arial", 10, "bold"), foreground='gray').grid(row=0, column=1, sticky='w', pady=5)
        
        ttk.Label(metrics_frame, text="Dernière Vérification Strava :", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky='w', pady=5)
        self.last_check_status_db = tk.StringVar(value="Jamais")
        ttk.Label(metrics_frame, textvariable=self.last_check_status_db, foreground='blue').grid(row=1, column=1, sticky='w', pady=5)
        
        # NOUVEAU: AFFICHAGE DU MINUTEUR
        ttk.Label(metrics_frame, text="⏳ Prochain Check dans :", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky='w', pady=5)
        ttk.Label(metrics_frame, textvariable=self.time_until_next_check, font=("Arial", 14, "bold"), foreground='darkred').grid(row=2, column=1, sticky='w', pady=5)
        
        ttk.Label(metrics_frame, text="Dernière Opération de Sync. :", font=("Arial", 10, "bold")).grid(row=3, column=0, sticky='w', pady=5)
        self.last_sync_success_db = tk.StringVar(value="N/A")
        ttk.Label(metrics_frame, textvariable=self.last_sync_success_db, foreground='orange').grid(row=3, column=1, sticky='w', pady=5)
        
        ttk.Label(metrics_frame, text="Total Activités Synchronisées :", font=("Arial", 10, "bold")).grid(row=4, column=0, sticky='w', pady=5)
        self.total_synced_count_db = tk.StringVar(value="0")
        ttk.Label(metrics_frame, textvariable=self.total_synced_count_db, font=("Arial", 12, "bold"), foreground='green').grid(row=4, column=1, sticky='w', pady=5)
        
        ttk.Separator(metrics_frame, orient='horizontal').grid(row=5, columnspan=2, sticky="ew", pady=10)
        
        # Mise à jour des coordonnées pour laisser de la place au minuteur
        ttk.Label(metrics_frame, text="Heure Prévue du Prochain Check :", font=("Arial", 10, "bold")).grid(row=6, column=0, sticky='w', pady=5)
        self.next_check_time = tk.StringVar(value="Inconnu")
        ttk.Label(metrics_frame, textvariable=self.next_check_time, foreground='darkred').grid(row=6, column=1, sticky='w', pady=5)
        
        logs_frame = ttk.LabelFrame(master_frame, text="📄 Console des Logs (Mises à jour en temps réel)", padding=10)
        logs_frame.pack(fill='both', expand=True, padx=10, pady=10)
        self.log_text_area = scrolledtext.ScrolledText(logs_frame, wrap=tk.WORD, height=20, state='disabled')
        self.log_text_area.pack(fill='both', expand=True)


    def _load_config_to_gui(self):
        """Charge la configuration et le mapping du fichier .env dans l'interface."""
        # Utilise la configuration en mémoire (mise à jour par _save_config)
        
        config_keys = ["STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "NOTION_TOKEN", "NOTION_DATABASE_URL", "FLASK_PORT"]
        for key in config_keys:
              if key in self.config_inputs:
                self.config_inputs[key].set(self.config_manager._config.get(key) or "") 
        map_keys = ["MAP_TITLE", "MAP_STRAVA_ID", "MAP_DATE", "MAP_DISTANCE", "MAP_DURATION", "MAP_TYPE", "MAP_ELEVATION", 
                    "MAP_CALORIES", "MAP_HEART_RATE", "MAP_PERCEIVED_EXERTION", "MAP_DESCRIPTION"]
        if hasattr(self, 'map_inputs'):
            for key in map_keys:
                current_value = self.config_manager._config.get(key)
                if current_value is not None:
                      self.map_inputs[key].set(current_value)
                
        refresh_token = self.config_manager.get("STRAVA_REFRESH_TOKEN")
        access_token = self.config_manager.get("STRAVA_ACCESS_TOKEN")
        self.refresh_token_var.set(refresh_token or "Non disponible")
        self.access_token_var.set(access_token or "Non disponible")
        if refresh_token:
            self.token_status.set("Statut: ✅ Token de Rafraîchissement trouvé. Vous pouvez démarrer le Polling (Onglet 3).")
        else:
            self.token_status.set("Statut: ⚠️ Token manquant. Autorisation requise (Voir les étapes ci-dessus).")

    def _save_config(self):
        """Sauvegarde les valeurs de TOUS les champs (config et mapping) dans le fichier .env."""
        config_to_save = {}
        config_to_save.update({k: v.get() for k, v in self.config_inputs.items()})
        if hasattr(self, 'map_inputs'):
              config_to_save.update({k: v.get() for k, v in self.map_inputs.items()})
              
        try:
            # Mettre à jour la configuration en mémoire avant de recharger le GUI
            self.config_manager._config.update(config_to_save)
            
            self.config_manager.save_configuration(config_to_save) 
            
            self._load_config_to_gui() 
        except Exception as e:
            raise Exception(f"Impossible d'écrire dans le fichier .env : {e}")
            
    def _process_log_queue(self):
        """Traite les logs en attente et les affiche dans la zone de texte."""
        while not self.log_queue.empty():
            try:
                log_entry = self.log_queue.get_nowait()
                self.log_text_area.config(state='normal')
                self.log_text_area.insert(tk.END, log_entry + '\n')
                self.log_text_area.config(state='disabled')
                self.log_text_area.see(tk.END)
                if "SUCCÈS:" in log_entry:
                    self.last_sync_success.set("✅ " + log_entry)
                    if "activités ont été ajoutées à Notion" in log_entry:
                        try:
                            count_str = log_entry.split('SUCCÈS: ')[1].split(' activités')[0]
                            count = int(count_str.split(' ')[0]) 
                            self.total_synced_count.set(self.total_synced_count.get() + count)
                        except:
                            pass
                elif "ERREUR" in log_entry:
                    self.last_sync_success.set("❌ " + log_entry)
            except queue.Empty:
                break
            except Exception as e:
                print(f"Erreur lors du traitement du log: {e}") 
                break
        self.after(100, self._process_log_queue)

    # MÉTHODE MODIFIÉE: Intégration du calcul et de l'affichage du minuteur
    def _update_dashboard_metrics(self):
        """Met à jour toutes les métriques du Tableau de Bord, incluant le minuteur."""
        
        if self.service_running and self.polling_scheduler.last_check_time:
            # Calcul du temps restant
            now = time.time()
            next_check_timestamp = self.polling_scheduler.last_check_time + self.polling_scheduler.interval
            remaining_seconds = max(0, int(next_check_timestamp - now))
            
            # Conversion en format MM:SS
            minutes = remaining_seconds // 60
            seconds = remaining_seconds % 60
            self.time_until_next_check.set(f"{minutes:02d}:{seconds:02d}")
            
            # Mise à jour des autres métriques
            self.polling_status_db.set("ACTIF")
            last_time = datetime.fromtimestamp(self.polling_scheduler.last_check_time).strftime('%Y-%m-%d %H:%M:%S')
            self.last_check_status_db.set(last_time)
            self.last_check_status.set(f"Dernière vérification: {last_time.split(' ')[1]}")
            next_check_time_str = datetime.fromtimestamp(next_check_timestamp).strftime('%Y-%m-%d %H:%M:%S')
            self.next_check_time.set(next_check_time_str)
            
        else:
            self.polling_status_db.set("Inactif")
            self.last_check_status_db.set("Jamais")
            self.last_check_status.set("Dernière vérification: Jamais")
            self.next_check_time.set("Démarrer le Polling d'abord")
            # NOUVEAU: Affichage par défaut pour le minuteur
            self.time_until_next_check.set("--:--") 

        self.last_sync_success_db.set(self.last_sync_success.get())
        self.total_synced_count_db.set(str(self.total_synced_count.get()))
        
        # Rappeler cette méthode dans 1000ms (1 seconde)
        self.after(1000, self._update_dashboard_metrics)


    def _on_closing(self):
        """Gestionnaire d'événements à la fermeture de la fenêtre."""
        # Arrêter explicitement le serveur Flask si actif
        if self.flask_server_thread and self.flask_server_thread.is_alive():
              self.log_queue.put("--- Arrêt du serveur Flask en cours... ---")
              # Le daemon=True devrait s'en charger, mais une notification est utile.
              pass 
              
        if self.service_running:
            if messagebox.askyesno("Quitter l'Application", 
                                     "Le service de synchronisation est en cours. Voulez-vous l'arrêter et quitter ?"):
                if self.polling_scheduler:
                    self.polling_scheduler.stop()
                self.destroy()
            else:
                return 
        else:
            self.destroy() 


if __name__ == '__main__':
    if not os.path.exists('.env'):
        try:
            with open('.env', 'w') as f:
                f.write('FLASK_PORT=5000\n') 
        except Exception as e:
              messagebox.showerror("Erreur Fichier", f"Impossible de créer le fichier .env : {e}")
              sys.exit(1)
              
    app = StravaNotionGUI()
    app.mainloop()