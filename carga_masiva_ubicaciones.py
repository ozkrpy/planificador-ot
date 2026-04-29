import csv
from app import app, db
from models import Ubicacion

def sync_data_from_csv(file_path):
    """
    Reads the fully populated CSV and updates the Ubicacion 
    records directly by their Primary Key ID.
    """
    # Using the app context to access the database session
    with app.app_context():
        try:
            print('INICIO: ', Ubicacion.query.get(1).latitud)  # Debug: Check the initial state of the first record
            with open(file_path, mode='r', encoding='utf-8') as csvfile:
                # Assuming the CSV header matches your description:
                # id|url|latitude|longitude|main_street|
                # secondary_street|neighborhood|city|cluster_group
                reader = csv.DictReader(csvfile, delimiter='|')
                
                print(f"Starting synchronization from {file_path}...")
                update_count = 0

                for row in reader:
                    # Get the Ubicacion record by its ID
                    ubi_id = row.get('id')
                    ubicacion = Ubicacion.query.get(ubi_id)

                    if ubicacion:
                        # Map numerical and text data from the CSV
                        ubicacion.latitud = float(row['latitude'])
                        ubicacion.longitud = float(row['longitude'])
                        ubicacion.calle_principal = row['main_street']
                        ubicacion.calle_secundaria = row['secondary_street']
                        ubicacion.barrio = row['neighborhood']
                        ubicacion.ciudad = row['city']
                        
                        # Set the group field based on the cluster calculation
                        cluster_val = row['cluster_group']
                        if cluster_val == "-1":
                            ubicacion.grupo = "Sin Zona"
                        else:
                            ubicacion.grupo = f"Zona {cluster_val}"

                        update_count += 1
                        if update_count % 10 == 0:
                            print(f"Updated {update_count} records...")
                    else:
                        print(f"Warning: Ubicacion ID {ubi_id} not found.")

                # Commit all updates in a single transaction for speed
                db.session.commit()
                print(f"Success: {update_count} records synchronized.")
            print('FIN: ', Ubicacion.query.get(1).latitud)  # Debug: Check the final state of the first record
        except FileNotFoundError:
            print(f"Error: The file '{file_path}' was not found.")
        except KeyError as e:
            print(f"Error: Missing expected column in CSV: {e}")
        except Exception as e:
            db.session.rollback()
            print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # Ensure 'grouped_locations.csv' is the name of your latest file
    sync_data_from_csv('grouped_locations.csv')

# INICIO: https://maps.app.goo.gl/9STf5xAjCiT2R3KH6
# FIN: https://maps.app.goo.gl/9STf5xAjCiT2R3KH6

# INICIO:  None
# FIN:  -25.3546566