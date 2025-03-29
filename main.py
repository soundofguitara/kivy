# main.py
import os
# Définir les variables d'environnement Kivy avant d'importer d'autres modules Kivy
# os.environ['KIVY_LOG_LEVEL'] = 'debug' # Pour plus d'infos de debug
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty
from kivy.clock import Clock
from kivy.utils import platform as kivy_platform
from kivy.logger import Logger
# from kivy.factory import Factory # No longer needed for ConfirmationPopup
from kivy.uix.popup import Popup # Import Popup base class

import db_manager
import excel_manager
import qr_scanner
from datetime import datetime

class ScanScreen(Screen):
    pass

class SearchScreen(Screen):
    pass

# Define ConfirmationPopup class in Python
class ConfirmationPopup(Popup):
    # Register the custom event type
    def __init__(self, **kwargs):
        self.register_event_type('on_confirm')
        super().__init__(**kwargs)

    # Define a default handler (can be overridden by bind)
    def on_confirm(self, *args):
        pass

class WarehouseApp(App):
    # États de l'application
    # 'IDLE': Attente scan produit
    # États de l'application
    # 'IDLE': Attente scan produit
    # 'WAITING_LOCATION_NEW': Produit scanné (palette nouvelle OU lot nouveau), attente scan emplacement
    # 'WAITING_LOCATION_MOVE': Produit scanné (palette existante), attente scan nouvel emplacement pour déplacement
    # 'WAITING_LOT_DECISION': Lot existe, palette nouvelle, attente choix utilisateur (Ajouter palette au lot / Annuler)
    # 'WAITING_PALETTE_DELETE': Attente scan palette à supprimer
    current_state = StringProperty('IDLE')
    # Stocke temporairement les données du produit/palette scanné
    temp_product_data = ObjectProperty(None, allownone=True)
    # Stocke les données de la palette à supprimer (pour confirmation et logging)
    palette_to_delete_data = ObjectProperty(None, allownone=True)
    # Stocke les enregistrements existants si le lot est trouvé
    existing_lot_records = ObjectProperty(None, allownone=True)

    def build(self):
        # Initialiser DB et Excel au démarrage
        try:
            db_manager.init_db()
            excel_manager.init_excel()
            Logger.info("APP: Base de données et fichier Excel initialisés.")
        except Exception as e:
            Logger.error(f"APP: Erreur lors de l'initialisation DB/Excel: {e}")
            # Afficher une erreur critique à l'utilisateur ici si nécessaire
        self.title = "Gestion d'Entrepôt Pharma"
        sm = ScreenManager()
        sm.add_widget(ScanScreen(name='scan_screen'))
        sm.add_widget(SearchScreen(name='search_screen'))
        return sm

    def on_start(self):
        # S'assurer que l'état initial est correct au démarrage
        self.reset_state()
        # Demander les permissions sur Android au démarrage (meilleure pratique)
        if kivy_platform == 'android':
            self.request_android_permissions()

    def request_android_permissions(self):
        try:
            from android.permissions import request_permissions, Permission, check_permission
            permissions_to_request = []
            if not check_permission(Permission.CAMERA):
                permissions_to_request.append(Permission.CAMERA)
            # Ajouter WRITE_EXTERNAL_STORAGE si nécessaire (selon où les fichiers sont stockés)
            # if not check_permission(Permission.WRITE_EXTERNAL_STORAGE):
            #     permissions_to_request.append(Permission.WRITE_EXTERNAL_STORAGE)

            if permissions_to_request:
                Logger.info(f"APP: Demande des permissions Android: {permissions_to_request}")
                request_permissions(permissions_to_request, self.permission_callback)
            else:
                 Logger.info("APP: Permissions Android déjà accordées.")

        except ImportError:
            Logger.warning("APP: Module de permissions Android non trouvé. Le scan pourrait échouer.")
        except Exception as e:
            Logger.error(f"APP: Erreur lors de la vérification/demande de permissions: {e}")

    def permission_callback(self, permissions, grants):
        Logger.info(f"APP: Résultats demande de permissions: {permissions}, {grants}")
        if all(grants):
            Logger.info("APP: Toutes les permissions nécessaires ont été accordées.")
        else:
            Logger.warning("APP: Certaines permissions ont été refusées. Fonctionnalités limitées.")
            # Informer l'utilisateur via un Popup ?

    def update_status(self, message, is_error=False):
        """Met à jour le label de statut sur l'écran de scan."""
        scan_screen = self.root.get_screen('scan_screen')
        if scan_screen:
            status_label = scan_screen.ids.status_label
            status_label.text = message
            if is_error:
                status_label.color = (1, 0, 0, 1) # Rouge
            else:
                status_label.color = (1, 1, 1, 1) # Blanc (ou couleur par défaut)
        Logger.info(f"STATUS: {message}")

    def reset_state(self):
        """Réinitialise l'état de l'application."""
        self.current_state = 'IDLE'
        self.temp_product_data = None
        self.existing_lot_records = None # Reset existing lot records
        scan_screen = self.root.get_screen('scan_screen')
        self.palette_to_delete_data = None # Reset delete data
        scan_screen = self.root.get_screen('scan_screen')
        if scan_screen:
            scan_screen.ids.scan_product_button.disabled = False
            scan_screen.ids.scan_location_button.disabled = True
            scan_screen.ids.delete_palette_button.disabled = False # Enable delete button
            self.update_status("Prêt. Choisissez une action.")

    def show_popup(self, title, message):
        """Affiche un popup simple avec un message."""
        popup = Popup(title=title,
                      content=Label(text=message),
                      size_hint=(0.8, 0.3))
        popup.open()

    def show_confirmation_popup(self, text, confirm_callback):
        """Affiche un popup de confirmation avec des boutons Confirmer/Annuler."""
        # Use the Python class directly instead of Factory
        popup = ConfirmationPopup()
        popup.ids.confirmation_text.text = text
        # Lie l'événement 'on_confirm' du popup à notre callback
        popup.bind(on_confirm=lambda instance: self._handle_confirmation(instance, confirm_callback))
        popup.open()

    def _handle_confirmation(self, popup_instance, confirm_callback):
        """Gère le clic sur 'Confirmer' dans le popup de confirmation."""
        popup_instance.dismiss() # Ferme le popup
        confirm_callback() # Exécute l'action de confirmation

    def scan_product(self):
        """Lance le scan du QR code produit."""
        if self.current_state != 'IDLE':
            self.update_status("Erreur: Action précédente non terminée.", True)
            return

        self.update_status("Scan du QR code Produit en cours...")
        # Exécuter le scan dans un thread ou via Clock pour ne pas bloquer l'UI (surtout avec webcam)
        # Ici, pour simplifier, appel direct (peut freezer sur Windows pendant le scan)
        # Décider quelle fonction de scan appeler en fonction de l'état
        if self.current_state == 'IDLE':
            Clock.schedule_once(self._perform_product_scan_add_move, 0.1)
        elif self.current_state == 'WAITING_PALETTE_DELETE':
             Clock.schedule_once(self._perform_product_scan_delete, 0.1)
        else:
            self.update_status(f"Erreur: État inattendu {self.current_state} pour scan produit.", True)


    def _perform_product_scan_add_move(self, dt):
        """Gère le scan produit pour l'ajout ou le déplacement."""
        qr_data, error = qr_scanner.scan_qr_code()

        if error:
            self.update_status(f"Erreur scan produit: {error}", True)
            self.reset_state()
            return

        if not qr_data:
            self.update_status("Aucun QR code produit trouvé.", True)
            self.reset_state() # Retour à l'état initial en cas d'erreur
            return

        self.update_status(f"QR Produit lu: {qr_data[:30]}...") # Afficher début pour confirmation
        product_data, parse_error = qr_scanner.parse_product_qr(qr_data)

        if parse_error:
            self.update_status(f"Erreur données produit: {parse_error}", True)
            self.reset_state() # Retour à l'état initial en cas d'erreur
            return

        self.temp_product_data = product_data # Stocker les données lues pour ajout/déplacement
        lot_number = product_data['lot_number']
        palette_number = product_data['palette_number']

        # Vérifier si le LOT existe déjà
        self.existing_lot_records = db_manager.check_existing_lot(lot_number)

        if self.existing_lot_records:
            Logger.info(f"APP: Lot {lot_number} existe déjà avec {len(self.existing_lot_records)} palette(s).")
            # Vérifier si la PALETTE spécifique existe DANS ce lot
            palette_exists_in_lot = any(rec['palette_number'] == palette_number for rec in self.existing_lot_records)

            if palette_exists_in_lot:
                # Cas 1: La palette spécifique existe déjà. Proposer de la déplacer.
                existing_palette_record = next((rec for rec in self.existing_lot_records if rec['palette_number'] == palette_number), None)
                current_location = existing_palette_record.get('location_id', 'N/A') if existing_palette_record else 'N/A'
                Logger.info(f"APP: Palette {palette_number} (Lot {lot_number}) existe déjà à l'emplacement {current_location}.")

                confirm_text = (f"Palette {palette_number} (Lot {lot_number})\n"
                                f"existe déjà à l'emplacement '{current_location}'.\n\n"
                                f"Voulez-vous scanner un nouvel emplacement pour la DÉPLACER ?")

                # Utiliser un popup spécifique ou le générique avec le bon callback
                self.show_confirmation_popup(
                    confirm_text,
                    self.prepare_for_location_scan_move # Confirmer -> préparer le déplacement
                )
                # L'état ne change qu'après confirmation via le callback

            else:
                # Cas 2: Le lot existe, mais cette palette est nouvelle. Proposer de l'ajouter.
                self.current_state = 'WAITING_LOT_DECISION' # Nouvel état d'attente de décision
                Logger.info(f"APP: Lot {lot_number} existe, mais la palette {palette_number} est nouvelle.")

                locations = [rec.get('location_id', 'N/A') for rec in self.existing_lot_records]
                locations_str = ", ".join(locations) if locations else "aucun emplacement connu"

                confirm_text = (f"Le Lot {lot_number} existe déjà (palette(s) à: {locations_str}).\n"
                                f"La palette {palette_number} est nouvelle pour ce lot.\n\n"
                                f"Voulez-vous AJOUTER cette nouvelle palette au lot ?")

                # Afficher un popup demandant si on ajoute la nouvelle palette
                # On réutilise show_confirmation_popup mais avec un callback différent
                self.show_confirmation_popup(
                    confirm_text,
                    self.prepare_for_location_scan_new # Confirmer -> préparer l'ajout
                )
                # L'état ne change qu'après confirmation via le callback

        else:
            # Cas 3: Le lot est entièrement nouveau. Préparer l'ajout directement.
            Logger.info(f"APP: Lot {lot_number} (Palette {palette_number}) est nouveau.")
            self.prepare_for_location_scan_new() # Préparer l'ajout


    def prepare_for_location_scan_new(self):
        """Prépare l'état pour scanner l'emplacement d'une NOUVELLE palette."""
        self.current_state = 'WAITING_LOCATION_NEW'
        scan_screen = self.root.get_screen('scan_screen')
        scan_screen.ids.scan_product_button.disabled = True
        scan_screen.ids.scan_location_button.disabled = False
        self.update_status(f"Ajout palette {self.temp_product_data['palette_number']}. Scannez l'emplacement.")

    def prepare_for_location_scan_move(self):
        """Prépare l'état pour scanner le NOUVEL emplacement d'une palette EXISTANTE."""
        self.current_state = 'WAITING_LOCATION_MOVE'
        scan_screen = self.root.get_screen('scan_screen')
        scan_screen.ids.scan_product_button.disabled = True
        scan_screen.ids.scan_location_button.disabled = False
        self.update_status(f"Déplacement palette {self.temp_product_data['palette_number']}. Scannez le nouvel emplacement.")

    def prepare_for_delete_scan(self):
        """Prépare l'état pour scanner la palette à supprimer."""
        if self.current_state != 'IDLE':
            self.update_status("Erreur: Terminez l'action en cours avant de supprimer.", True)
            return
        self.current_state = 'WAITING_PALETTE_DELETE'
        scan_screen = self.root.get_screen('scan_screen')
        scan_screen.ids.scan_product_button.disabled = False # On utilise ce bouton pour scanner la palette à supprimer
        scan_screen.ids.scan_location_button.disabled = True
        scan_screen.ids.delete_palette_button.disabled = True # Désactiver pendant l'opération
        self.update_status("Prêt à supprimer. Scannez le QR de la palette livrée.")

    def _perform_product_scan_delete(self, dt):
        """Gère le scan produit pour la suppression."""
        qr_data, error = qr_scanner.scan_qr_code()

        if error:
            self.update_status(f"Erreur scan palette à supprimer: {error}", True)
            self.reset_state() # Retour à l'état initial en cas d'erreur
            return

        if not qr_data:
            self.update_status("Aucun QR code palette trouvé pour suppression.", True)
            self.reset_state() # Retour à l'état initial
            return

        self.update_status(f"QR Palette à supprimer lu: {qr_data[:30]}...")
        product_data, parse_error = qr_scanner.parse_product_qr(qr_data)

        if parse_error:
            self.update_status(f"Erreur données palette à supprimer: {parse_error}", True)
            self.reset_state() # Retour à l'état initial
            return

        palette_number_to_delete = product_data['palette_number']

        # Vérifier si cette palette existe dans la DB
        existing_palette_data = db_manager.check_existing_palette(palette_number_to_delete)

        if existing_palette_data:
            self.palette_to_delete_data = existing_palette_data # Stocker les infos pour confirmation/log
            location = existing_palette_data.get('location_id', 'N/A')
            confirm_text = (f"Confirmer la suppression (livraison) de :\n"
                            f"Palette: {palette_number_to_delete}\n"
                            f"Produit: {existing_palette_data.get('product_name', 'N/A')}\n"
                            f"Lot: {existing_palette_data.get('lot_number', 'N/A')}\n"
                            f"Emplacement: {location}\n\n"
                            f"Êtes-vous sûr ?")
            self.show_confirmation_popup(confirm_text, self._execute_delete)
        else:
            self.update_status(f"Erreur: Palette {palette_number_to_delete} non trouvée dans la base de données.", True)
            self.reset_state() # Retour à l'état initial

    def _execute_delete(self):
        """Exécute la suppression après confirmation."""
        if not self.palette_to_delete_data:
            Logger.error("DELETE: Aucune donnée de palette à supprimer trouvée.")
            self.reset_state()
            return

        palette_number = self.palette_to_delete_data['palette_number']
        Logger.info(f"DELETE: Tentative de suppression de la palette {palette_number}")

        # 1. Supprimer de la base de données
        db_deleted = db_manager.delete_palette(palette_number)

        if db_deleted:
            # 2. Logger dans Excel
            # Ajouter timestamp de suppression
            self.palette_to_delete_data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            excel_logged = excel_manager.add_record_to_excel(self.palette_to_delete_data, action="DELETE")

            if excel_logged:
                self.update_status(f"Succès: Palette {palette_number} supprimée (livrée).")
            else:
                self.update_status(f"Succès DB, mais Erreur Excel lors de la suppression de {palette_number}.", True)
                # Que faire ici ? La DB est modifiée mais pas Excel...
        else:
            self.update_status(f"Échec: Erreur DB lors de la suppression de {palette_number}.", True)

        self.reset_state() # Réinitialiser l'état après l'opération


    def scan_location(self):
        """Lance le scan du QR code emplacement."""
        if self.current_state not in ['WAITING_LOCATION_NEW', 'WAITING_LOCATION_MOVE']:
            self.update_status("Erreur: Scannez d'abord un produit.", True)
            return

        self.update_status("Scan du QR code Emplacement en cours...")
        Clock.schedule_once(self._perform_location_scan, 0.1)


    def _perform_location_scan(self, dt):
        location_id, error = qr_scanner.scan_qr_code()

        if error:
            self.update_status(f"Erreur scan emplacement: {error}", True)
            # Ne pas reset complètement, permettre de réessayer le scan emplacement
            scan_screen = self.root.get_screen('scan_screen')
            scan_screen.ids.scan_location_button.disabled = False
            return

        if not location_id:
            self.update_status("Aucun QR code emplacement trouvé. Réessayez.", True)
            scan_screen = self.root.get_screen('scan_screen')
            scan_screen.ids.scan_location_button.disabled = False
            return

        # Normaliser l'ID d'emplacement scanné
        original_location_id = location_id.strip() # Garder l'original pour l'affichage si besoin
        normalized_location_id = db_manager.normalize_location_id(original_location_id)
        if not normalized_location_id:
            self.update_status(f"Erreur: ID d'emplacement '{original_location_id}' invalide après normalisation.", True)
            scan_screen = self.root.get_screen('scan_screen')
            if scan_screen:
                scan_screen.ids.scan_location_button.disabled = False
            return

        current_palette_number = self.temp_product_data['palette_number']

        # --- Vérifier si l'emplacement (normalisé) est déjà occupé ---
        occupying_palette = db_manager.get_palette_at_location(normalized_location_id) # Utiliser l'ID normalisé pour la vérification

        # Modification: Empêcher l'ajout/déplacement vers TOUT emplacement occupé,
        # même s'il est occupé par la palette qu'on est en train de déplacer (pour forcer un emplacement vide).
        if occupying_palette is not None:
            # L'emplacement est occupé
            # Afficher l'ID original ou normalisé ? Utilisons l'original pour que l'utilisateur le reconnaisse.
            error_msg = f"Emplacement {original_location_id} (={normalized_location_id}) déjà occupé par palette {occupying_palette}.\nVeuillez choisir un autre emplacement."
            self.show_popup("Erreur Emplacement", error_msg)
            self.update_status(error_msg, True)
            # Laisser le bouton de scan emplacement actif pour réessayer
            scan_screen = self.root.get_screen('scan_screen')
            if scan_screen:
                scan_screen.ids.scan_location_button.disabled = False
            return # Ne pas continuer

        # --- Si l'emplacement est libre ---
        # Afficher l'ID normalisé dans le message de statut pour confirmer ce qui est enregistré
        self.update_status(f"Emplacement {original_location_id} (={normalized_location_id}) valide. Enregistrement...")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # current_palette_number est déjà défini

        success = False
        action_description = ""

        if self.current_state == 'WAITING_LOCATION_NEW':
            # Ajouter la nouvelle palette (passer l'ID normalisé à la DB)
            self.temp_product_data['location_id'] = normalized_location_id # Stocker l'ID normalisé
            self.temp_product_data['timestamp'] = timestamp
            db_success = db_manager.add_palette(self.temp_product_data)
            if db_success:
                # Récupérer l'ID de la DB pour l'Excel (optionnel mais bien)
                new_record = db_manager.check_existing_palette(current_palette_number)
                if new_record:
                    self.temp_product_data['id'] = new_record['id']

                # Utiliser l'ID normalisé aussi pour Excel pour la cohérence
                excel_success = excel_manager.add_record_to_excel(self.temp_product_data, action="ADD")
                success = excel_success # Considérer l'ajout Excel comme partie du succès global ?
                action_description = f"Palette {current_palette_number} ajoutée à l'emplacement {normalized_location_id}."
            else:
                action_description = f"Erreur DB lors de l'ajout de {current_palette_number}."

        elif self.current_state == 'WAITING_LOCATION_MOVE':
            # Mettre à jour l'emplacement de la palette existante (passer l'ID normalisé à la DB)
            db_success = db_manager.update_palette_location(current_palette_number, normalized_location_id, timestamp)
            if db_success:
                 # Ajouter une ligne dans Excel pour l'historique de déplacement
                 data_for_excel = self.temp_product_data.copy() # Copier les infos produit
                 data_for_excel['location_id'] = normalized_location_id # Utiliser l'ID normalisé pour Excel
                 data_for_excel['timestamp'] = timestamp
                 # Essayer de récupérer l'ID DB existant
                 existing = db_manager.check_existing_palette(current_palette_number)
                 if existing: data_for_excel['id'] = existing['id']

                 excel_success = excel_manager.add_record_to_excel(data_for_excel, action="MOVE")
                 success = excel_success # Considérer l'ajout Excel comme partie du succès global ?
                 action_description = f"Palette {current_palette_number} déplacée vers {normalized_location_id}."
            else:
                action_description = f"Erreur DB lors du déplacement de {current_palette_number}."

        if success:
            self.update_status(f"Succès: {action_description}")
            self.reset_state()
        else:
            self.update_status(f"Échec: {action_description}", True)
            # Laisser l'utilisateur réessayer ou annuler ? Ici on reset.
            self.reset_state()


    def perform_search(self):
        """Exécute la recherche et affiche les résultats."""
        search_screen = self.root.get_screen('search_screen')
        query = search_screen.ids.search_input.text.strip()
        search_type_text = search_screen.ids.search_type_spinner.text
        results_label = search_screen.ids.search_results_label

        if not query:
            results_label.text = "[color=ff3333]Veuillez entrer un terme de recherche.[/color]"
            return

        search_by = 'lot_number' if search_type_text == 'Numéro de Lot' else 'product_name'
        results_label.text = f"Recherche en cours pour '{query}'..."

        try:
            results = db_manager.search_inventory(query, search_by)
            if not results:
                results_label.text = f"Aucun résultat trouvé pour '{query}'."
            else:
                formatted_results = f"[b]Résultats pour '{query}': ({len(results)} trouvé(s))[/b]\n\n"
                for record in results:
                    formatted_results += (
                        f"--------------------\n"
                        f"[b]Palette:[/b] {record['palette_number']}\n"
                        f"[b]Produit:[/b] {record['product_name']}\n"
                        f"[b]Lot:[/b] {record['lot_number']}\n"
                        f"Emplacement: {record.get('location_id', 'N/A')}\n"
                        f"Prix: {record.get('price', 'N/A')}\n"
                        f"Expiration: {record.get('expiry_date', 'N/A')}\n"
                        f"Boîtes/Colis: {record.get('boxes_per_package', 'N/A')}\n"
                        f"Dernière MàJ: {record.get('timestamp', 'N/A')}\n\n"
                    )
                results_label.text = formatted_results
                # Ajuster la hauteur du ScrollView si nécessaire (ou s'assurer que le Label le fait)
                results_label.height = results_label.texture_size[1]


        except Exception as e:
            results_label.text = f"[color=ff3333]Erreur lors de la recherche: {e}[/color]"
            Logger.error(f"SEARCH: Erreur pendant la recherche: {e}")


if __name__ == '__main__':
    WarehouseApp().run()
