[app]
title = Warehouse Manager
package.name = warehouseapp
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,db # Ajoutez db pour inclure la base si initialisée
version = 0.1
requirements = python3,kivy,pillow,openpyxl,pyzbar,plyer # opencv-python-headless removed for Android build compatibility
# OU si vous utilisez une autre méthode de scan Android (ex: pyzxing) ajoutez-la ici

orientation = portrait
# fullscreen = 0

android.permissions = CAMERA, INTERNET # Ajoutez WRITE_EXTERNAL_STORAGE si besoin
# android.presplash = data/presplash.png
# android.icon = data/icon.png

# --- Buildozer spécifique ---
# android.api = 31 # API cible, ajustez si nécessaire
# android.minapi = 21 # API minimale
# android.sdk = 24 # Version SDK (pourrait être obsolète, buildozer gère souvent ça)
# android.ndk = 23b # Version NDK (idem)

# --- Pour le scan QR avec Plyer/ZXing ---
# Si vous utilisez une bibliothèque qui nécessite une activité Android externe (comme ZXing via Plyer ou pyjnius)
# vous pourriez avoir besoin d'ajouter des dépendances ou des 'services' ici.
# Par exemple, si Plyer utilise zxing-android-embedded:
# android.gradle_dependencies = 'com.journeyapps:zxing-android-embedded:4.3.0' # Vérifiez la version !
# Ou si vous utilisez une recette python-for-android spécifique.
# Consultez la documentation de Plyer ou de la bibliothèque de scan choisie.
android.gradle_dependencies = 'com.journeyapps:zxing-android-embedded:4.3.0' # Ajout pour Plyer barcode scan

# --- Pour OpenCV sur Android ---
# Cela peut être complexe. Il faut souvent une recette python-for-android spécifique pour compiler OpenCV.
# p4a.local_recipes = /path/to/your/opencv/recipe # Si vous avez une recette locale
# p4a.branch = develop # Ou une branche spécifique de p4a si nécessaire

[buildozer]
log_level = 2
warn_on_root = 1
