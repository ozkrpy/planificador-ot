import requests
import re
import numpy as np
from app import app, db
from models import Ubicacion
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from sklearn.cluster import DBSCAN

def resolve_url_and_coords(url):
    """
    Expands URLs and prioritizes !3d/!4d metadata for 
    centimeter-level precision.
    """
    if not url or not url.startswith('http'):
        return None, None
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(
            url, 
            headers=headers, 
            allow_redirects=True, 
            timeout=15
        )
        final_url = response.url
        
        # 1. High-Precision Match (!3d is the actual pin metadata)
        precise_match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', final_url)
        if precise_match:
            return float(precise_match.group(1)), float(precise_match.group(2))

        # 2. Fallback Match (The @ or query= format)
        pattern = re.compile(
            r'(!3d|@|query=)(-?\d{1,2}\.\d+)[,\!](4d|-?\d{1,3}\.\d+)'
        )
        match = pattern.search(final_url)
        if match:
            lat = float(match.group(2))
            lon = float(match.group(3))
            if str(lon).endswith('d'):
                lon = float(str(lon).replace('d', ''))
            return lat, lon
    except Exception as e:
        print(f"  × URL Error: {e}")
    return None, None

def update_geo_info():
    with app.app_context():
        print("--- Starting Final Geo-Sync ---")
        # ubicaciones = Ubicacion.query.filter(Ubicacion.id==49).all()
        ubicaciones = Ubicacion.query.all()
        
        # 5-second delay to be 100% safe with Nominatim
        geolocator = Nominatim(user_agent="familiaruffinellivera@gmail.com")
        reverse_geocode = RateLimiter(geolocator.reverse, min_delay_seconds=5)
        
        valid_records = []
        coords_list = []

        for ubi in ubicaciones:
            print(f"Processing ID {ubi.id}: {ubi.nombre_sucursal}...")
            lat, lon = resolve_url_and_coords(ubi.coordenadas_url)
            
            if lat and lon:
                ubi.latitud, ubi.longitud = lat, lon
                try:
                    location = reverse_geocode(f"{lat}, {lon}")
                    if location and 'address' in location.raw:
                        addr = location.raw['address']
                        
                        # Street Logic: Prioritize road, then fallback
                        ubi.calle_principal = addr.get('road', 'calle_principal-sin-definir')
                        
                        # Intersection Logic
                        ubi.calle_secundaria = addr.get('junction', 
                                               addr.get('railway', 'calle_secundaria-sin-definir'))
                        
                        # Neighborhood Logic: Prioritize 'neighbourhood' then 'suburb'
                        ubi.barrio = addr.get('neighbourhood', 
                                     addr.get('suburb', 'barrio-sin-definir'))
                        
                        # City Logic
                        ubi.ciudad = addr.get('city', 
                                     addr.get('town', 
                                     addr.get('village', 'ciudad-sin-definir')))
                        
                        print(f"  → Found: {ubi.calle_principal} in {ubi.barrio}")
                except Exception:
                    pass # Fallbacks already set in previous logic if needed
                
                valid_records.append(ubi)
                coords_list.append([lat, lon])
            else:
                # Mark everything as undefined if URL fails
                ubi.calle_principal = 'calle_principal-sin-definir'
                ubi.calle_secundaria = 'calle_secundaria-sin-definir'
                ubi.barrio = 'barrio-sin-definir'
                ubi.ciudad = 'ciudad-sin-definir'
                ubi.grupo = 'grupo-sin-definir'

            print(f"DEBUG: Full Address for ID {ubi.id}: {location.raw.get('display_name')}")
            print(f"  → nombre: {ubi.nombre_sucursal}, Lat: {ubi.latitud}, Lon: {ubi.longitud}, Barrio: {ubi.barrio}, Ciudad: {ubi.ciudad}, calle_principal: {ubi.calle_principal}, calle_secundaria: {ubi.calle_secundaria}   ")

        # Clustering Logic (5km)
        if coords_list:
            print("\nGrouping by proximity...")
            kms_per_radian = 6371.0088
            epsilon = 5.0 / kms_per_radian
            dbscan = DBSCAN(eps=epsilon, min_samples=2, metric='haversine').fit(np.radians(coords_list))
            
            for i, ubi in enumerate(valid_records):
                cluster_id = dbscan.labels_[i]
                ubi.grupo = f"Zona {cluster_id}" if cluster_id != -1 else "grupo-sin-definir"

        try:
            db.session.commit()
            print("\n✔ Update Successful.")
        except Exception as e:
            db.session.rollback()
            print(f"✘ Error: {e}")

if __name__ == '__main__':
    update_geo_info()

# import os
# import sys

# import requests
# import re
# import numpy as np
# from app import app, db
# from models import Ubicacion
# from geopy.geocoders import Nominatim
# from geopy.extra.rate_limiter import RateLimiter
# from sklearn.cluster import DBSCAN

# def resolve_url_and_coords(url):
#     """
#     Expands URLs and uses a prioritized regex to find the 
#     most precise coordinates available in the metadata.
#     """
#     if not url or not url.startswith('http'):
#         return None, None
#     try:
#         headers = {'User-Agent': 'Mozilla/5.0'}
#         response = requests.get(
#             url, 
#             headers=headers, 
#             allow_redirects=True, 
#             timeout=15
#         )
#         final_url = response.url
        
#         # 1. PRIORITY: Look for !3d (lat) and !4d (lon) 
#         # These are usually the high-precision pin coordinates.
#         precise_match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', final_url)
#         if precise_match:
#             return float(precise_match.group(1)), float(precise_match.group(2))

#         # 2. FALLBACK: Look for the @ format or query= format
#         pattern = re.compile(
#             r'(!3d|@|query=)(-?\d{1,2}\.\d+)[,\!](4d|-?\d{1,3}\.\d+)'
#         )
#         match = pattern.search(final_url)
        
#         if match:
#             lat = float(match.group(2))
#             lon = float(match.group(3))
#             if str(lon).endswith('d'):
#                 lon = float(str(lon).replace('d', ''))
#             return lat, lon
            
#     except Exception as e:
#         print(f"  × Error: {e}")
        
#     return None, None

# def update_geo_info():
#     """
#     Main execution loop: Reads coordenadas_url, extracts data,
#     updates address fields, and clusters into zones.
#     """
#     with app.app_context():
#         print("--- Starting Geolocation Database Sync ---")
        
#         # Retrieve the current URI from config
#         active_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
#         env_status = os.environ.get('FLASK_ENV')

#         print("-" * 50)
#         print(f"ENVIRONMENT: {env_status}")
#         print(f"ACTIVE DB:   {active_uri}")
#         print("-" * 50)
#         print(f"DEBUG: Using Database at -> {app.config['SQLALCHEMY_DATABASE_URI']}")

#         # Safety Lock: Prevent accidental staging updates
#         if "staging" in active_uri.lower() and env_status == 'development':
#             print("ERROR: Environment is 'development' but DB is 'staging'!")
#             print("Check your config logic. Aborting.")
#             # sys.exit()
#             app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ot_planning_dev.db'
#             app.config['DEBUG'] = True
#             print(f"DEBUG: Using Database at -> {app.config['SQLALCHEMY_DATABASE_URI']}")

#         ubicaciones = Ubicacion.query.filter(Ubicacion.id==73).all()  # Replace 1 with the actual ID you want to filter
#         for u in ubicaciones:
#             print(f"ID {u.id}: {u.nombre_sucursal} - URL: {u.coordenadas_url}") 
#         if not ubicaciones:
#             print("No records found in the Ubicacion table.")
#             return

#         # Initialize Geocoder with a 5-second delay for maximum safety
#         geolocator = Nominatim(user_agent="familiaruffinellivera@gmail.com")
#         reverse_geocode = RateLimiter(
#             geolocator.reverse, 
#             min_delay_seconds=5
#         )
        
#         valid_for_clustering = []
#         coords_for_clustering = []

#         for ubi in ubicaciones:
#             print(f"Processing: {ubi.nombre_sucursal} (ID: {ubi.id})...")
            
#             # Step 1: Resolve the URL into hard coordinates
#             lat, lon = resolve_url_and_coords(ubi.coordenadas_url)
            
#             if lat and lon:
#                 ubi.latitud = lat
#                 ubi.longitud = lon
                
#                 # Step 2: Reverse Geocode to get address details
#                 try:
#                     location = reverse_geocode(f"{lat}, {lon}")
#                     if location and 'address' in location.raw:
#                         addr = location.raw['address']
                        
#                         # 1. Improved Street Extraction
#                         # We prioritize 'road', but if 'road' gives us a residential street 
#                         # when an 'avenue' or 'highway' is available, we can cross-check.
                        
#                         # Attempt to find the most 'important' name in the address dict
#                         possible_street_keys = ['road', 'highway', 'pedestrian', 'amenity']
#                         street_found = "calle_principal-sin-definir"
                        
#                         for key in possible_street_keys:
#                             if key in addr:
#                                 val = addr.get(key)
#                                 # If the result is Félix de Azara but we want the Avenue, 
#                                 # sometimes OSM provides the intersection context.
#                                 street_found = val
#                                 break
                        
#                         ubi.calle_principal = street_found

#                         # 2. Improved Secondary Street (The Intersection)
#                         # Often, the 'other' street in the intersection is hidden in 
#                         # 'neighbourhood' or 'hamlet' if not in 'junction'.
#                         ubi.calle_secundaria = addr.get(
#                             'junction', 
#                             addr.get('railway', 'calle_secundaria-sin-definir')
#                         )

#                         # 3. Handle specific Asunción cases (Manual override or logic check)
#                         # If you find that the coordinates are highly sensitive, you can 
#                         # also check the 'display_name' which often contains both streets.
#                         display_name = location.raw.get('display_name', '')
#                         if "Choferes del Chaco" in display_name and ubi.calle_principal != "Choferes del Chaco":
#                             # If the prominent name is in the full string but not the 'road' key
#                             ubi.calle_principal = "Avenida Choferes del Chaco"
#                     else:
#                         ubi.calle_principal = 'calle_principal-sin-definir'
#                         ubi.calle_secundaria = 'calle_secundaria-sin-definir'
#                         ubi.barrio = 'barrio-sin-definir'
#                         ubi.ciudad = 'ciudad-sin-definir'
#                 except Exception:
#                     ubi.calle_principal = 'calle_principal-sin-definir'
#                     ubi.calle_secundaria = 'calle_secundaria-sin-definir'
#                     ubi.barrio = 'barrio-sin-definir'
#                     ubi.ciudad = 'ciudad-sin-definir'

#                 valid_for_clustering.append(ubi)
#                 coords_for_clustering.append([lat, lon])
#             else:
#                 # If URL is invalid, reset fields to 'sin-definir'
#                 print(f"  ! Invalid URL for ID {ubi.id}")
#                 ubi.calle_principal = 'calle_principal-sin-definir'
#                 ubi.calle_secundaria = 'calle_secundaria-sin-definir'
#                 ubi.barrio = 'barrio-sin-definir'
#                 ubi.ciudad = 'ciudad-sin-definir'
#                 ubi.grupo = 'grupo-sin-definir'
#             print(f"DEBUG: Full Address for ID {ubi.id}: {location.raw.get('display_name')}")
#             print(f"  → nombre: {ubi.nombre_sucursal}, Lat: {ubi.latitud}, Lon: {ubi.longitud}, Barrio: {ubi.barrio}, Ciudad: {ubi.ciudad}, calle_principal: {ubi.calle_principal}, calle_secundaria: {ubi.calle_secundaria}   ")

#         # Step 3: Radius-based Clustering (DBSCAN)
#         if coords_for_clustering:
#             print("\nGrouping zones (5km radius)...")
#             kms_per_radian = 6371.0088
#             epsilon = 5.0 / kms_per_radian
            
#             coords_rad = np.radians(coords_for_clustering)
#             dbscan = DBSCAN(
#                 eps=epsilon, 
#                 min_samples=2, 
#                 metric='haversine', 
#                 algorithm='ball_tree'
#             ).fit(coords_rad)

#             for i, ubi in enumerate(valid_for_clustering):
#                 label = dbscan.labels_[i]
#                 if label == -1:
#                     ubi.grupo = "grupo-sin-definir"
#                 else:
#                     ubi.grupo = f"Zona {label}"

#         # Step 4: Final Database Save
#         try:
#             print("\nSaving updates to the database...")
#             db.session.commit()
#             print("\n✔ Update completed. All records synchronized.")
#         except Exception as e:
#             db.session.rollback()
#             print(f"\n✘ Database Error: {e}")

# if __name__ == '__main__':
#     update_geo_info()