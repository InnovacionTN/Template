import os
import json
from google.cloud import bigquery
from google.oauth2 import service_account
from datetime import datetime
import logging
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bigquery_diagnostic.log')
    ]
)
logger = logging.getLogger(__name__)

def check_bigquery_connection():
    """Verificar la conexión y el estado de BigQuery."""
    try:
        logger.info("Iniciando verificación de conexión a BigQuery...")
        
        # Cargar variables de entorno
        project_id = os.getenv("BIGQUERY_PROJECT_ID", "neto-cloud")
        dataset_id = os.getenv("BIGQUERY_DATASET", "agente_vokse")
        table_id = os.getenv("BIGQUERY_TABLE", "chat_messages")
        location = os.getenv("BIGQUERY_LOCATION", "us-central1")
        creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        
        if not creds_json:
            logger.error("ERROR: No se encontró GOOGLE_APPLICATION_CREDENTIALS_JSON en las variables de entorno")
            logger.info("Asegúrate de que el archivo .env contenga esta variable")
            return False
            
        logger.info(f"Proyecto: {project_id}")
        logger.info(f"Conjunto de datos: {dataset_id}")
        logger.info(f"Tabla: {table_id}")
        
        # Parsear credenciales
        try:
            credentials_info = json.loads(creds_json)
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            logger.info("✓ Credenciales de servicio analizadas correctamente")
        except json.JSONDecodeError as e:
            logger.error(f"ERROR: No se pudo analizar el JSON de credenciales: {str(e)}")
            logger.info("Verifica que el formato del JSON sea correcto en el archivo .env")
            return False
            
        # Inicializar cliente de BigQuery
        try:
            client = bigquery.Client(
                project=project_id,
                credentials=credentials,
                location=location
            )
            logger.info(f"✓ Cliente de BigQuery inicializado para el proyecto: {project_id}")
        except Exception as e:
            logger.error(f"ERROR: No se pudo inicializar el cliente de BigQuery: {str(e)}")
            return False
            
        # Verificar si existe el dataset
        dataset_ref = f"{project_id}.{dataset_id}"
        try:
            dataset = client.get_dataset(dataset_ref)
            logger.info(f"✓ Dataset encontrado: {dataset_id}")
            logger.info(f"  - Ubicación: {dataset.location}")
            logger.info(f"  - Creado: {dataset.created}")
        except Exception as e:
            logger.error(f"ERROR: No se encontró el dataset '{dataset_id}': {str(e)}")
            logger.info(f"Por favor, crea el dataset '{dataset_id}' en el proyecto {project_id}")
            return False
            
        # Verificar si existe la tabla
        table_ref = f"{project_id}.{dataset_id}.{table_id}"
        try:
            table = client.get_table(table_ref)
            logger.info(f"✓ Tabla encontrada: {table_id}")
            logger.info(f"  - Columnas: {[field.name for field in table.schema]}")
        except Exception as e:
            logger.error(f"ERROR: No se encontró la tabla '{table_id}': {str(e)}")
            logger.info(f"Por favor, crea la tabla '{table_id}' en el dataset {dataset_id}")
            return False
            
        # Verificar inserción de datos
        print("\nProbando inserción de datos de prueba...")
        try:
            test_data = {
                'user_id': 'test_user',
                'message_ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'channel_id': 'test_channel',
                'message_text': 'Mensaje de prueba',
                'bot_response': 'Respuesta de prueba',
                'message_type': 'test',
                'input_tokens': 10,
                'output_tokens': 20,
                'total_tokens': 30,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            errors = client.insert_rows_json(table_ref, [test_data])
            if not errors:
                print("✓ Inserción de prueba exitosa")
                # Verificar que los datos se insertaron
                query = f"""
                    SELECT * 
                    FROM `{project_id}.{dataset_id}.{table_id}`
                    WHERE user_id = 'test_user'
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                query_job = client.query(query)
                results = list(query_job)
                if results:
                    print("✓ Verificación de datos exitosa")
                    return True
                else:
                    print("✗ No se pudo verificar la inserción")
                    return False
            else:
                print(f"✗ Error en la inserción: {errors}")
                return False
        except Exception as e:
            print(f"✗ Error durante la inserción: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"ERROR inesperado: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("DIAGNÓSTICO DE CONEXIÓN A BIGQUERY")
    print("="*60 + "\n")
    
    success = check_bigquery_connection()
    
    print("\n" + "="*60)
    if success:
        print("✓ PRUEBA COMPLETADA CON ÉXITO")
    else:
        print("✗ SE ENCONTRARON ERRORES")
    print("="*60 + "\n")
    
    print("Revisa el archivo 'bigquery_diagnostic.log' para más detalles.")
    print("Si hay errores, comparte el contenido de este archivo para ayudarte mejor.")
    print("\n" + "-"*60)
