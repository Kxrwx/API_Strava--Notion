# app.py

from flask import Flask, request, redirect, url_for, jsonify
import os
import sys

# Importez les classes de modèles (ConfigManager et StravaClient)
# Elles seront utilisées via les instances passées en argument.
from models.config_manager import ConfigManager
from models.strava_client import StravaClient

# --- Initialisation de l'application Flask ---
app = Flask(__name__)
# Une clé secrète est nécessaire pour les sessions Flask
app.secret_key = os.urandom(24) 


@app.route('/auth/callback')
def strava_callback():
    """
    Réception du code d'autorisation de Strava. 
    Les instances de client et config sont récupérées via le contexte 'app.config'.
    """
    
    # Récupérer les instances du contexte Flask (stockées par run_flask_server)
    strava_client_local = app.config.get('STRAVA_CLIENT')
    
    if not strava_client_local:
         # Erreur de configuration si on arrive ici
         return "Erreur Interne du Serveur: Client Strava non initialisé.", 500
         
    code = request.args.get('code')
    
    if code:
        try:
            # 1. Échange du code contre le Refresh Token
            strava_client_local.exchange_code_for_token(code)
            
            # 2. Rafraîchissement pour obtenir l'Access Token tout de suite (optionnel mais propre)
            strava_client_local.refresh_access_token() 
            
            # Message de succès affiché dans le navigateur de l'utilisateur
            return (f"<h1>Authentification Strava Réussie!</h1>"
                    f"<p>Le Refresh Token a été sauvegardé dans le fichier .env.</p>"
                    f"<p>Vous pouvez fermer cette fenêtre de navigateur.</p>")
        except Exception as e:
            return f"Erreur lors de l'échange de code: {e}", 500
            
    return "Code d'autorisation manquant.", 400


# --- Fonction de Démarrage en Thread ---
def run_flask_server(config_manager_instance, strava_client_instance):
    """
    Lance le serveur Flask. C'est cette fonction qui est appelée par gui.py dans un nouveau thread.
    Les instances de ConfigManager et StravaClient sont passées ici.
    """
    
    # Stocker les instances dans le contexte de l'application Flask pour usage dans les routes
    app.config['CONFIG_MANAGER'] = config_manager_instance
    app.config['STRAVA_CLIENT'] = strava_client_instance
    
    # Récupérer le port configuré
    port_str = config_manager_instance.get("FLASK_PORT")
    if port_str and port_str.isdigit():
        port = int(port_str)
    else:
        port = 5000
        print("Avertissement: FLASK_PORT non défini ou invalide, utilisant le port 5000.")
        
    print(f"Démarrage du micro-serveur Flask sur http://0.0.0.0:{port}...")
    print("Veuillez effectuer l'autorisation Strava dans le navigateur qui va s'ouvrir.")
    
    # use_reloader=False et debug=False sont ESSENTIELS pour le threading
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

    
if __name__ == '__main__':
    # Logique de démarrage pour les tests manuels de app.py
    try:
        # NOTE: Assurez-vous que ConfigManager et StravaClient sont bien importables
        cfg = ConfigManager()
        st_client = StravaClient(cfg)
        run_flask_server(cfg, st_client)
    except Exception as e:
        print(f"Erreur lors du lancement manuel de app.py: {e}")
        sys.exit(1)