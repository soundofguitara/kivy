# db_manager.py
import sqlite3
import os
from datetime import datetime
from kivy.app import App # Pour obtenir le chemin user_data_dir
from kivy.logger import Logger # Importer Logger

DATABASE_NAME = 'database.db'

def get_db_path():
    """Retourne le chemin complet vers le fichier de base de données."""
    # Stocke la DB dans un endroit accessible en écriture sur toutes les plateformes
    try:
        # Si l'application Kivy est en cours d'exécution
        app_dir = App.get_running_app().user_data_dir
        # Créer le répertoire s'il n'existe pas (plus sûr)
        os.makedirs(app_dir, exist_ok=True)
    except AttributeError:
        # Sinon (par exemple, lors de l'exécution de scripts autonomes ou de tests)
        # Utiliser le répertoire du script comme fallback, mais logguer un avertissement
        app_dir = os.path.dirname(os.path.abspath(__file__))
        Logger.warning(f"DB: Pas d'application Kivy active. Utilisation du répertoire local: {app_dir}")
        # Créer le répertoire s'il n'existe pas (également pour le cas hors-app)
        os.makedirs(app_dir, exist_ok=True)
    db_path = os.path.join(app_dir, DATABASE_NAME)
    # Logger.info(f"DB: Chemin de la base de données utilisé: {db_path}") # Optionnel: peut être verbeux
    return db_path

def normalize_location_id(location_id):
    """Normalise un ID d'emplacement (ex: supprime les points et espaces)."""
    if location_id is None:
        return None
    # Supprimer les points et les espaces superflus
    return location_id.replace('.', '').strip()

def init_db():
    """Initialise la base de données et crée la table si elle n'existe pas."""
    db_path = get_db_path()
    Logger.info(f"DB: Tentative d'initialisation de la base de données à: {db_path}")
    conn = None # Initialiser conn à None
    try:
        conn = get_db_connection() # Utiliser la fonction get_db_connection pour la cohérence
        if conn is None:
             # get_db_connection loggue déjà l'erreur
             Logger.error("DB: Échec de l'obtention de la connexion pour l'initialisation.")
             return # Ne pas continuer si la connexion échoue

        cursor = conn.cursor()
        Logger.info("DB: Connexion établie. Création de la table 'inventory' si elle n'existe pas...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                palette_number TEXT NOT NULL,
                product_name TEXT NOT NULL,
                price REAL,
                expiry_date TEXT,
                lot_number TEXT NOT NULL,
                boxes_per_package INTEGER,
                location_id TEXT,
                timestamp TEXT NOT NULL,
                UNIQUE(palette_number) -- On suppose que le numéro de palette est unique
            )
        ''')
        # Ajouter un index pour accélérer les recherches
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_lot_number ON inventory (lot_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_product_name ON inventory (product_name)')
        conn.commit()
        Logger.info("DB: Table 'inventory' et index vérifiés/créés avec succès.")
    except sqlite3.Error as e:
        Logger.error(f"DB: Erreur SQLite lors de l'initialisation de la table/index: {e}")
        if conn:
            conn.rollback() # Annuler les changements partiels si possible
    except Exception as e:
        Logger.error(f"DB: Erreur inattendue lors de l'initialisation: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close() # Assurer la fermeture de la connexion
            Logger.info("DB: Connexion d'initialisation fermée.")


def get_db_connection():
    """Crée et retourne une connexion à la base de données."""
    db_path = get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        # Utiliser Row pour accéder aux colonnes par nom
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        Logger.error(f"DB: Erreur de connexion à la base de données {db_path}: {e}")
        return None

def check_existing_palette(palette_number):
    """Vérifie si une palette existe et retourne ses infos si oui."""
    conn = get_db_connection()
    if not conn: return None
    record_dict = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM inventory WHERE palette_number = ?", (palette_number,))
        record = cursor.fetchone()
        if record:
            # Retourner sous forme de dictionnaire pour un accès facile par nom de colonne
            columns = [description[0] for description in cursor.description]
            record_dict = dict(zip(columns, record))
    except sqlite3.Error as e:
        Logger.error(f"DB: Erreur lors de la vérification de la palette {palette_number}: {e}")
    finally:
        conn.close()
    return record_dict

def get_palette_at_location(location_id):
    """Vérifie si un emplacement est occupé et retourne le numéro de palette si oui (utilise l'ID normalisé)."""
    conn = get_db_connection()
    normalized_loc_id = normalize_location_id(location_id) # Normaliser
    if not conn or normalized_loc_id is None: return None
    palette_num = None
    try:
        cursor = conn.cursor()
        # Chercher une palette à cet emplacement spécifique (normalisé)
        cursor.execute("SELECT palette_number FROM inventory WHERE location_id = ?", (normalized_loc_id,)) # Utiliser l'ID normalisé
        record = cursor.fetchone()
        if record:
            palette_num = record['palette_number']
            Logger.info(f"DB: Emplacement {location_id} est occupé par palette {palette_num}.")
        # else: Logger.info(f"DB: Emplacement {location_id} est libre.") # Optionnel
    except sqlite3.Error as e:
        Logger.error(f"DB: Erreur lors de la vérification de l'emplacement {normalized_loc_id}: {e}")
    finally:
        if conn:
            conn.close()
    return palette_num # Retourne le numéro de palette ou None

def check_existing_lot(lot_number):
    """Vérifie si un numéro de lot existe déjà dans la base de données."""
    conn = get_db_connection()
    if not conn: return []
    records_list = []
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM inventory WHERE lot_number = ?", (lot_number,))
        records = cursor.fetchall()
        if records:
            # Retourner la liste des enregistrements existants pour ce lot
            columns = [description[0] for description in cursor.description]
            records_list = [dict(zip(columns, record)) for record in records]
    except sqlite3.Error as e:
        Logger.error(f"DB: Erreur lors de la vérification du lot {lot_number}: {e}")
    finally:
        conn.close()
    return records_list # Retourne une liste vide si le lot n'existe pas ou en cas d'erreur

def add_palette(data):
    """Ajoute une nouvelle palette à la base de données (utilise l'ID d'emplacement normalisé)."""
    conn = get_db_connection()
    normalized_loc_id = normalize_location_id(data.get('location_id')) # Normaliser
    if not conn: return False
    success = False
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO inventory (
                palette_number, product_name, price, expiry_date, lot_number,
                boxes_per_package, location_id, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['palette_number'], data['product_name'], data.get('price'),
            data['expiry_date'], data['lot_number'], data.get('boxes_per_package'),
            normalized_loc_id, data['timestamp'] # Utiliser l'ID normalisé
        ))
        conn.commit()
        Logger.info(f"DB: Palette {data['palette_number']} ajoutée avec succès à l'emplacement {normalized_loc_id}.")
        success = True
    except sqlite3.IntegrityError:
        Logger.error(f"DB: La palette {data['palette_number']} existe déjà (Violation d'unicité).")
        conn.rollback() # Important en cas d'erreur
    except sqlite3.Error as e:
        Logger.error(f"DB: Erreur SQLite lors de l'ajout de la palette {data['palette_number']}: {e}")
        conn.rollback()
    except Exception as e:
        Logger.error(f"DB: Erreur inattendue lors de l'ajout de la palette {data['palette_number']}: {e}")
        conn.rollback()
    finally:
        conn.close()
    return success

def update_palette_location(palette_number, location_id, timestamp):
    """Met à jour l'emplacement et le timestamp d'une palette existante (utilise l'ID d'emplacement normalisé)."""
    conn = get_db_connection()
    normalized_loc_id = normalize_location_id(location_id) # Normaliser
    if not conn: return False
    success = False
    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE inventory
            SET location_id = ?, timestamp = ?
            WHERE palette_number = ?
        ''', (normalized_loc_id, timestamp, palette_number)) # Utiliser l'ID normalisé
        conn.commit()
        if cursor.rowcount > 0:
            Logger.info(f"DB: Emplacement de la palette {palette_number} mis à jour vers {normalized_loc_id}.")
            success = True
        else:
            Logger.warning(f"DB: Palette {palette_number} non trouvée pour la mise à jour d'emplacement {normalized_loc_id}.")
            # Considérer ceci comme un échec car l'update n'a pas eu lieu
    except sqlite3.Error as e:
        Logger.error(f"DB: Erreur SQLite lors de la mise à jour de l'emplacement pour {palette_number}: {e}")
        conn.rollback()
    except Exception as e:
        Logger.error(f"DB: Erreur inattendue lors de la mise à jour de l'emplacement pour {palette_number}: {e}")
        conn.rollback() # Corrected indentation
    finally:
        conn.close()
    return success

def delete_palette(palette_number):
    """Supprime une palette de la base de données par son numéro."""
    conn = get_db_connection()
    if not conn: return False
    success = False
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM inventory WHERE palette_number = ?", (palette_number,))
        conn.commit()
        if cursor.rowcount > 0:
            Logger.info(f"DB: Palette {palette_number} supprimée avec succès.")
            success = True
        else:
            # Si rowcount est 0, la palette n'existait pas (ou plus)
            Logger.warning(f"DB: Tentative de suppression de la palette {palette_number}, mais elle n'a pas été trouvée.")
            # On peut considérer cela comme un "succès" relatif car la palette n'est plus là,
            # ou comme un échec si on s'attendait à ce qu'elle existe.
            # Choisissons de retourner False pour indiquer que l'état attendu n'a pas été trouvé.
            success = False
    except sqlite3.Error as e:
        Logger.error(f"DB: Erreur SQLite lors de la suppression de la palette {palette_number}: {e}")
        conn.rollback()
    except Exception as e:
        Logger.error(f"DB: Erreur inattendue lors de la suppression de la palette {palette_number}: {e}")
        conn.rollback()
    finally:
        conn.close()
    return success

def search_inventory(query, search_by='lot_number'):
    """Recherche dans l'inventaire par numéro de lot ou nom de produit."""
    conn = get_db_connection()
    if not conn: return []
    results_list = []
    try:
        cursor = conn.cursor()
        sql_query = ""
        params = ('%' + query + '%',)

        if search_by == 'lot_number':
            sql_query = "SELECT * FROM inventory WHERE lot_number LIKE ?"
        elif search_by == 'product_name':
            sql_query = "SELECT * FROM inventory WHERE product_name LIKE ?"
        else:
            Logger.warning(f"DB: Type de recherche non valide: {search_by}")
            return []

        cursor.execute(sql_query, params)
        results = cursor.fetchall()
        if results:
            columns = [description[0] for description in cursor.description]
            # Convertir les résultats en liste de dictionnaires
            results_list = [dict(zip(columns, row)) for row in results]
            Logger.info(f"DB: Recherche pour '{query}' ({search_by}) a retourné {len(results_list)} résultat(s).")
        else:
             Logger.info(f"DB: Aucune correspondance trouvée pour '{query}' ({search_by}).")

    except sqlite3.Error as e:
        Logger.error(f"DB: Erreur SQLite lors de la recherche pour '{query}' ({search_by}): {e}")
    except Exception as e:
         Logger.error(f"DB: Erreur inattendue lors de la recherche pour '{query}' ({search_by}): {e}")
    finally:
        if conn:
            conn.close()
    return results_list

# Initialiser la DB au démarrage du module si nécessaire
# init_db() # Il est préférable de l'appeler explicitement depuis main.py
