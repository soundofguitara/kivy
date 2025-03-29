# qr_scanner.py
import platform
import time
import datetime # Ajout de l'import manquant
from kivy.logger import Logger # Pour logguer les infos Kivy

# --- Implémentation Windows (Webcam) ---
def scan_qr_windows():
    try:
        import cv2
        from pyzbar import pyzbar
    except ImportError:
        Logger.error("SCANNER: Les bibliothèques 'opencv-python' et 'pyzbar' sont nécessaires sur Windows.")
        return None, "Bibliothèques manquantes: opencv-python, pyzbar"

    # Essayer d'ouvrir la caméra avant (souvent index 0) puis la suivante
    cap = None
    preferred_camera_index = 0 # Indice préféré pour la caméra avant
    fallback_camera_index = 1 # Indice de secours
    Logger.info(f"SCANNER: Tentative d'ouverture de la caméra index {preferred_camera_index} (CAP_DSHOW)...")
    cap = cv2.VideoCapture(preferred_camera_index, cv2.CAP_DSHOW)

    if not cap or not cap.isOpened():
        Logger.warning(f"SCANNER: Échec ouverture caméra index {preferred_camera_index}. Tentative avec index {fallback_camera_index}...")
        cap = cv2.VideoCapture(fallback_camera_index, cv2.CAP_DSHOW)
        if not cap or not cap.isOpened():
             Logger.error(f"SCANNER: Impossible d'ouvrir les caméras index {preferred_camera_index} ou {fallback_camera_index}.")
             return None, "Caméra inaccessible"
        else:
             Logger.info(f"SCANNER: Caméra index {fallback_camera_index} ouverte.")
    else:
        Logger.info(f"SCANNER: Caméra index {preferred_camera_index} ouverte.")


    Logger.info("SCANNER: Recherche de QR code...")
    found = False
    qr_data = None
    error_msg = "Aucun QR code détecté"

    start_time = time.time()
    timeout = 10 # secondes

    while time.time() - start_time < timeout:
        ret, frame = cap.read()
        if not ret:
            error_msg = "Erreur de lecture de la caméra"
            break

        # Détecter et décoder les QR codes
        barcodes = pyzbar.decode(frame)
        if barcodes:
            for barcode in barcodes:
                if barcode.type == 'QRCODE':
                    qr_data = barcode.data.decode('utf-8')
                    Logger.info(f"SCANNER: QR Code détecté: {qr_data}")
                    found = True
                    # Dessiner un rectangle autour (optionnel, pour debug visuel si affichage)
                    # (x, y, w, h) = barcode.rect
                    # cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    break # Prendre le premier QR code trouvé
            if found:
                break

        # cv2.imshow('QR Scanner - Appuyez sur Q pour quitter', frame) # Retiré car cause l'erreur OpenCV
        # if cv2.waitKey(1) & 0xFF == ord('q'): # Retiré car lié à imshow
        #     Logger.info("SCANNER: Scan annulé par l'utilisateur (touche Q).")
        #     error_msg = "Scan annulé par l'utilisateur"
        #     break

        # Ajouter une petite pause si nécessaire pour éviter 100% CPU, bien que cap.read() puisse suffire
        time.sleep(0.01)


    cap.release()
    # cv2.destroyAllWindows() # Retiré car lié à imshow
    Logger.info("SCANNER: Caméra fermée.")

    if found:
        return qr_data, None
    else:
        return None, error_msg

# --- Implémentation Android (Utilisation de Plyer ou Pyjnius/ZXing) ---
def scan_qr_android():
    # Méthode 1: Utilisation de Plyer (plus simple si disponible et suffisant)
    try:
        from plyer import barcode
        # Note: Nécessite d'ajouter 'barcode' aux permissions Android dans buildozer.spec
        # et potentiellement une bibliothèque de scan comme ZXing via buildozer
        Logger.info("SCANNER: Tentative de scan via Plyer...")
        # Cette fonction est bloquante et devrait lancer l'activité de scan
        barcode_data = barcode.scan() # Peut nécessiter un appel asynchrone ou dans un thread
        if barcode_data:
             Logger.info(f"SCANNER: QR Code détecté via Plyer: {barcode_data.decode('utf-8')}")
             return barcode_data.decode('utf-8'), None
        else:
             Logger.warning("SCANNER: Aucun QR code scanné via Plyer ou annulé.")
             return None, "Scan annulé ou aucun QR code trouvé"

    except Exception as e:
        Logger.error(f"SCANNER: Erreur avec Plyer barcode: {e}. Vérifiez les permissions et dépendances.")
        # Tenter une autre méthode si nécessaire ou retourner une erreur
        return None, f"Erreur Plyer: {e}"

    # Méthode 2: Utilisation de Pyjnius + ZXing (plus complexe, plus de contrôle)
    # Cela nécessiterait d'intégrer une activité de scan Android via Pyjnius.
    # C'est plus avancé et dépasse le cadre d'une réponse simple.
    # Il faudrait:
    # 1. Inclure la bibliothèque ZXing Android dans le buildozer.spec.
    # 2. Utiliser Pyjnius pour lancer l'Intent de scan ZXing.
    # 3. Récupérer le résultat de l'Intent.
    # Logger.warning("SCANNER: Méthode Pyjnius/ZXing non implémentée dans cet exemple.")
    # return None, "Scan Android non implémenté (Pyjnius)"


# --- Fonction principale de scan ---
def scan_qr_code():
    """Lance le scan QR adapté à la plateforme."""
    os_name = platform.system()
    Logger.info(f"SCANNER: Détection de la plateforme: {os_name}")

    if os_name == "Windows":
        return scan_qr_windows()
    elif os_name == "Linux":
         # Linux peut utiliser la même méthode que Windows si webcam et libs sont installées
         Logger.warning("SCANNER: Utilisation de la méthode Windows/Webcam pour Linux.")
         return scan_qr_windows()
    elif platform.system() == "Darwin": # macOS
         Logger.warning("SCANNER: Utilisation de la méthode Windows/Webcam pour macOS.")
         return scan_qr_windows()
    else:
        # Supposons Android si ce n'est pas Windows/Linux/macOS (à affiner si nécessaire)
        # Vérification plus robuste possible via os.environ ou kivy.utils.platform
        from kivy.utils import platform as kivy_platform
        if kivy_platform == 'android':
            Logger.info("SCANNER: Plateforme Android détectée.")
            # --- Vérifier les permissions avant de scanner ---
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([Permission.CAMERA]) # Demander la permission caméra
                # Idéalement, attendre le résultat de la demande de permission...
                # Pour cet exemple, on suppose qu'elle sera accordée ou a été accordée
            except ImportError:
                 Logger.warning("SCANNER: Impossible d'importer les permissions Android. Le scan pourrait échouer.")
            except Exception as e:
                 Logger.error(f"SCANNER: Erreur lors de la demande de permission caméra: {e}")

            return scan_qr_android()
        else:
            Logger.error(f"SCANNER: Plateforme '{os_name}' / '{kivy_platform}' non supportée pour le scan QR.")
            return None, f"Plateforme non supportée: {kivy_platform}"

def parse_product_qr(data):
    """
    Parse les données du QR code produit.
    Format attendu (exemple, séparé par ';'):
    Nom;Prix;AAAA-MM-JJ;Lot123;BoxesParColis;PaletteNum
    """
    try:
        parts = data.strip().split(';')
        if len(parts) == 6:
            product_data = {
                'product_name': parts[0],
                'price': float(parts[1].replace(',', '.')), # Gérer virgule ou point décimal
                'expiry_date': parts[2], # Valider le format ? (ex: YYYY-MM-DD)
                'lot_number': parts[3],
                'boxes_per_package': int(parts[4]),
                'palette_number': parts[5]
            }
            # Validation basique (à améliorer)
            # Utiliser datetime.datetime.strptime
            datetime.datetime.strptime(product_data['expiry_date'], '%Y-%m-%d') # Valide format date
            return product_data, None
        else:
            return None, f"Format QR produit incorrect. Attendu 6 champs séparés par ';', obtenu {len(parts)}."
    except ValueError as e:
        return None, f"Erreur de conversion des données QR produit: {e}"
    except Exception as e:
        return None, f"Erreur inattendue lors du parsing QR produit: {e}"

# Note: Le QR code de l'emplacement contient juste l'ID de l'emplacement.
# Pas besoin de fonction de parsing spécifique, on utilise directement la donnée.
