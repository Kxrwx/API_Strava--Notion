# models/ngrok_manager.py
import subprocess
import requests
import time
import os
import signal

class NgrokManager:
    """Gère le lancement et l'arrêt du tunnel ngrok pour exposer l'application Flask."""

    def __init__(self, flask_port):
        self.port = str(flask_port)
        self.ngrok_process = None
        self.api_url = "http://127.0.0.1:4040/api/tunnels"
        self.tunnel_url = None

    def _get_ngrok_executable(self):
        """Détermine le nom de l'exécutable ngrok en fonction du système."""
        if os.name == 'nt':  # Windows
            return 'ngrok.exe'
        return 'ngrok'

    def check_auth(self):
        """Vérifie si ngrok est accessible dans le PATH."""
        try:
            # Tente de lancer ngrok version pour vérifier l'accès
            subprocess.run([self._get_ngrok_executable(), 'version'], 
                           check=True, 
                           capture_output=True, 
                           text=True, 
                           timeout=5)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def start_tunnel(self):
        """Démarre le tunnel ngrok en arrière-plan et récupère l'URL publique."""
        
        # S'assurer que le tunnel précédent est arrêté
        if self.ngrok_process:
            self.stop_tunnel()

        ngrok_exe = self._get_ngrok_executable()
        
        # Commande pour démarrer ngrok et l'attacher au port Flask
        # Nous utilisons 'run' au lieu de 'http' pour les versions récentes de ngrok
        command = [ngrok_exe, 'http', self.port]
        
        # Démarrer ngrok sans bloquer l'application principale
        self.ngrok_process = subprocess.Popen(command, 
                                              stdout=subprocess.DEVNULL, 
                                              stderr=subprocess.DEVNULL)
        
        # Attendre que le tunnel soit établi et que l'API de ngrok soit disponible
        time.sleep(3) 

        try:
            # Interroger l'API ngrok locale pour obtenir l'URL publique
            response = requests.get(self.api_url, timeout=5)
            response.raise_for_status()
            
            tunnels = response.json()['tunnels']
            
            # Rechercher l'URL HTTPS (nécessaire pour le webhook Strava)
            for tunnel in tunnels:
                if tunnel['proto'] == 'https':
                    self.tunnel_url = tunnel['public_url']
                    return self.tunnel_url
            
            raise Exception("Aucun tunnel HTTPS trouvé via l'API ngrok.")

        except requests.exceptions.RequestException as e:
            self.stop_tunnel()
            raise Exception(f"Impossible de se connecter à l'API ngrok (port 4040). Erreur: {e}")
        except Exception as e:
            self.stop_tunnel()
            raise Exception(f"Erreur lors de la récupération de l'URL ngrok: {e}")

    def stop_tunnel(self):
        """Arrête le processus ngrok."""
        if self.ngrok_process:
            try:
                # Arrêter le processus
                if os.name == 'nt': # Windows
                    self.ngrok_process.terminate() 
                else: # Linux/Mac
                    os.kill(self.ngrok_process.pid, signal.SIGTERM)
                self.ngrok_process.wait(timeout=5)
            except Exception:
                # Tenter un kill si terminate échoue
                if self.ngrok_process.poll() is None:
                     self.ngrok_process.kill()
            finally:
                self.ngrok_process = None
                self.tunnel_url = None