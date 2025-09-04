import os
import logging
import threading
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, Response, status, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import openai
from loguru import logger
from dotenv import load_dotenv
import uvicorn
from google.cloud import bigquery
from google.oauth2 import service_account
import asyncio
from typing import Dict, Set
import pytz
#Prueba
# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logger.opt(colors=True)

# Store processed event IDs to prevent duplicate processing
processed_events: Set[str] = set()

# BigQuery Configuration
BIGQUERY_PROJECT_ID = os.getenv("BIGQUERY_PROJECT_ID", "neto-cloud")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "agente_vokse")
BIGQUERY_TABLE = os.getenv("BIGQUERY_TABLE", "chat_messages")
BIGQUERY_LOCATION = os.getenv("BIGQUERY_LOCATION", "us-central1")

# Initialize BigQuery client as None
bigquery_client = None

# Configure Google Cloud credentials
try:
    creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if creds_json and creds_json.strip() != "":
        try:
            # Parse the JSON to ensure it's valid
            credentials_info = json.loads(creds_json)
            
            # Verify required fields are present
            required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
            for field in required_fields:
                if field not in credentials_info:
                    logger.error(f"Missing required field in credentials: {field}")
                    raise ValueError(f"Missing required field: {field}")
            
            # Create credentials from the parsed JSON
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            
            # Initialize BigQuery client with explicit credentials
            bigquery_client = bigquery.Client(
                project=credentials_info.get('project_id', BIGQUERY_PROJECT_ID),
                credentials=credentials,
                location=BIGQUERY_LOCATION
            )
            
            # Test the connection with a simple query
            test_query = f"""
                SELECT 1 as test_value
                FROM `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.__TABLES__`
                LIMIT 1
            """
            bigquery_client.query(test_query).result()
            
            logger.info("BigQuery client initialized and connection tested successfully")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in GOOGLE_APPLICATION_CREDENTIALS_JSON: {str(e)}")
            logger.debug(f"JSON content: {creds_json[:200]}...")  # Log first 200 chars of the JSON
            raise
        except Exception as e:
            logger.error(f"Error initializing or testing BigQuery client: {str(e)}", exc_info=True)
            raise
    else:
        logger.warning("GOOGLE_APPLICATION_CREDENTIALS_JSON is not set or empty, BigQuery logging will be disabled")
except Exception as e:
    logger.error(f"Unexpected error during BigQuery initialization: {str(e)}", exc_info=True)
    bigquery_client = None

# Initialize FastAPI app
fastapi_app = FastAPI()

# Initialize Slack app
slack_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Configure retry handler for Slack client
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

# Add rate limit retry handler
rate_limit_handler = RateLimitErrorRetryHandler(max_retry_count=2)
slack_app.client.retry_handlers.append(rate_limit_handler)

# Get the bot's user ID to identify bot messages
bot_id = None
try:
    auth_response = slack_app.client.auth_test()
    bot_id = auth_response["user_id"]
    logger.info(f"Bot user ID: {bot_id}")
except Exception as e:
    logger.error(f"Error getting bot user ID: {str(e)}")

# Event handler for the Slack Events API
@fastapi_app.post("/slack/events")
async def slack_events(request: Request):
    try:
        # Get raw body for signature verification
        body_bytes = await request.body()
        body_str = body_bytes.decode('utf-8')
        
        # Parse JSON data
        try:
            data = await request.json()
        except Exception as e:
            logger.error(f"Error parsing JSON: {str(e)}")
            return JSONResponse(status_code=400, content={"error": "Invalid JSON"})
        
        # Generate a unique ID for this event
        event_id = f"{data.get('event_id') or ''}:{data.get('event', {}).get('ts') or ''}"
        
        # Check if we've already processed this event
        if event_id in processed_events:
            logger.info(f"Skipping already processed event: {event_id}")
            return {"status": "already_processed"}
            
        # Add to processed events
        processed_events.add(event_id)
        
        # Log the request for debugging
        logger.info("\n" + "="*50)
        logger.info(f"SLACK EVENT RECEIVED - ID: {event_id}")
        logger.info(f"Type: {data.get('type')}")
        
        # Handle URL verification challenge
        if data.get("type") == "url_verification":
            logger.info("URL verification challenge received")
            return JSONResponse(content={"challenge": data.get("challenge")})
        
        # Verify request signature
        signature = request.headers.get('x-slack-signature')
        timestamp = request.headers.get('x-slack-request-timestamp')
        
        if not signature or not timestamp:
            logger.warning("Missing Slack signature or timestamp in headers")
            return JSONResponse(status_code=401, content={"error": "Missing signature or timestamp"})
        
        # Verify the request signature
        from slack_sdk.signature import SignatureVerifier
        signing_secret = os.environ.get("SLACK_SIGNING_SECRET")
        if not signing_secret:
            logger.error("SLACK_SIGNING_SECRET not found in environment")
            return JSONResponse(status_code=500, content={"error": "Server configuration error"})
            
        verifier = SignatureVerifier(signing_secret)
        
        if not verifier.is_valid(body=body_str, timestamp=timestamp, signature=signature):
            logger.warning("Invalid request signature")
            return JSONResponse(status_code=401, content={"error": "Invalid signature"})
        
        # Process event
        if data.get("type") == "event_callback":
            event = data.get("event", {})
            event_type = event.get("type")
            
            # Log the complete event for debugging
            logger.info(f"Processing event type: {event_type}")
            
            # Handle message events
            if event_type == "message" and not event.get("bot_id"):
                # Skip message_changed and other subtypes
                if event.get('subtype'):
                    return {"status": "ignored - message subtype"}
                
                channel_id = event.get("channel")
                user_id = event.get("user")
                text = event.get("text", "").strip()
                
                # Skip empty messages
                if not text:
                    return {"status": "ignored - empty message"}
                
                # Handle direct messages
                if event.get("channel_type") == "im":
                    logger.info(f"Processing DM from user {user_id}: {text}")
                    
                    try:
                        # Add "eyes" reaction to show we've seen the message
                        slack_app.client.reactions_add(
                            channel=channel_id,
                            timestamp=event.get("ts"),
                            name="eyes"
                        )
                        
                        # Process the message and generate response
                        await process_message(channel_id, user_id, text, event)
                        
                        # Change reaction to white check mark in green circle when done
                        slack_app.client.reactions_remove(
                            channel=channel_id,
                            timestamp=event.get("ts"),
                            name="eyes"
                        )
                        slack_app.client.reactions_add(
                            channel=channel_id,
                            timestamp=event.get("ts"),
                            name="white_check_mark"
                        )
                        
                    except Exception as e:
                        logger.error(f"Error processing message: {str(e)}", exc_info=True)
                        # If there was an error, remove eyes and add X
                        slack_app.client.reactions_remove(
                            channel=channel_id,
                            timestamp=event.get("ts"),
                            name="eyes"
                        )
                        slack_app.client.reactions_add(
                            channel=channel_id,
                            timestamp=event.get("ts"),
                            name="x"
                        )
                
                # Handle mentions in channels
                elif f"<@{bot_id}>" in text:
                    logger.info(f"Processing mention in channel {channel_id} from user {user_id}")
                    # Remove the mention from the message
                    clean_text = text.replace(f'<@{bot_id}>', '').strip()
                    
                    try:
                        # Add "eyes" reaction to show we've seen the message
                        slack_app.client.reactions_add(
                            channel=channel_id,
                            timestamp=event.get("ts"),
                            name="eyes"
                        )
                        
                        # Process the message and generate response
                        await process_message(channel_id, user_id, clean_text, event)
                        
                        # Change reaction to white check mark in green circle when done
                        slack_app.client.reactions_remove(
                            channel=channel_id,
                            timestamp=event.get("ts"),
                            name="eyes"
                        )
                        slack_app.client.reactions_add(
                            channel=channel_id,
                            timestamp=event.get("ts"),
                            name="white_check_mark"
                        )
                        
                    except Exception as e:
                        logger.error(f"Error processing mention: {str(e)}", exc_info=True)
                        # If there was an error, remove eyes and add X
                        slack_app.client.reactions_remove(
                            channel=channel_id,
                            timestamp=event.get("ts"),
                            name="eyes"
                        )
                        slack_app.client.reactions_add(
                            channel=channel_id,
                            timestamp=event.get("ts"),
                            name="x"
                        )
            
            # Return 200 OK to acknowledge receipt
            return {"status": "ok"}
        
        # Return 200 OK for any other event type to prevent retries
        return {"status": "event type not processed"}
        
    except Exception as e:
        logger.error(f"Unexpected error in slack_events endpoint: {str(e)}", exc_info=True)
        # Don't add to processed_events if there was an error, so we can retry
        if 'event_id' in locals() and event_id in processed_events:
            processed_events.remove(event_id)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

async def process_message(channel_id, user_id, message, event):
    """Process a message and generate a response."""
    try:
        # Get conversation history
        conversation_history = get_conversation_history(channel_id, user_id)
        
        # Prepare messages for the AI model
        messages = [
            {"role": "system", "content": "Eres un asistente útil que responde preguntas de manera amable y profesional."}
        ]
        
        # Add conversation history
        for msg in conversation_history:
            if msg.get("message_text"):
                messages.append({"role": "user", "content": msg.get("message_text")})
            if msg.get("bot_response"):
                messages.append({"role": "assistant", "content": msg.get("bot_response")})
        
        # Add the current message
        messages.append({"role": "user", "content": message})
        
        # Get AI response - this is the only part that needs to be awaited
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: get_chat_completion(
                messages=messages,
                model=os.environ.get("OPENAI_MODEL", "gpt-4"),
                max_tokens=1000,
                temperature=0.7
            )
        )
        
        ai_response = response.choices[0].message.content
        
        # Send the response - non-blocking
        slack_app.client.chat_postMessage(
            channel=channel_id,
            text=ai_response
        )
        
        # Save to database - non-blocking
        message_data = {
            "message_ts": datetime.utcfromtimestamp(float(event.get("ts"))).strftime('%Y-%m-%d %H:%M:%S'),
            "channel_id": channel_id,
            "user_id": user_id,
            "message_text": message,
            "bot_response": ai_response,
            "message_type": event.get("type", "message"),
            "input_tokens": response.usage.get("prompt_tokens", 0),
            "output_tokens": response.usage.get("completion_tokens", 0),
            "total_tokens": response.usage.get("total_tokens", 0)
        }
        
        if not save_to_bigquery(message_data):
            logger.error("Failed to save message to database")
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        raise

# Health check endpoint
@fastapi_app.get("/health")
async def health_check():
    # Check if required services are available
    status = {
        "status": "ok",
        "services": {
            "bigquery": bigquery_client is not None,
            "openai": "OPENAI_API_KEY" in os.environ,
            "slack": all(k in os.environ for k in ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET"])
        }
    }
    return status

# Make the app callable for Gunicorn
app = fastapi_app

# Configure OpenAI
openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set")

# Set API key for OpenAI 0.28.1
openai.api_key = openai_api_key

# Simple wrapper for chat completions
def get_chat_completion(messages, model=None, max_tokens=1000, temperature=0.3):
    response = openai.ChatCompletion.create(
        model=model or os.environ.get("OPENAI_MODEL", "gpt-4"),
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature
    )
    return response

def save_to_bigquery(message_data):
    """Guarda un mensaje en BigQuery.
    
    Args:
        message_data (dict): Diccionario con los datos del mensaje a guardar.
        
    Returns:
        bool: True si el mensaje se guardó correctamente, False en caso contrario.
    """
    global bigquery_client
    
    if not bigquery_client:
        logger.error("BigQuery client no está inicializado. Verificando credenciales...")
        # Intentar reinicializar el cliente
        try:
            creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
            if creds_json and creds_json.strip() != "":
                credentials_info = json.loads(creds_json)
                credentials = service_account.Credentials.from_service_account_info(credentials_info)
                bigquery_client = bigquery.Client(
                    project=credentials_info.get('project_id', BIGQUERY_PROJECT_ID),
                    credentials=credentials,
                    location=BIGQUERY_LOCATION
                )
                logger.info("BigQuery client reinitialized successfully")
            else:
                logger.error("No se encontraron credenciales de Google Cloud")
                return False
        except Exception as e:
            logger.error(f"Error al reinicializar BigQuery client: {str(e)}")
            return False
    
    if not message_data or not isinstance(message_data, dict):
        logger.error(f"Datos de mensaje inválidos: {message_data}")
        return False
    
    try:
        # Asegurar que los datos tengan el formato correcto
        mexico_tz = pytz.timezone('America/Mexico_City')
        current_time = datetime.now(mexico_tz)
        
        row = {
            'user_id': str(message_data['user_id']),
            'message_ts': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'channel_id': str(message_data['channel_id']),
            'message_text': str(message_data['message_text'])[:10000],
            'bot_response': str(message_data.get('bot_response', ''))[:10000],
            'message_type': message_data.get('message_type', 'message'),
            'input_tokens': int(message_data.get('input_tokens', 0)),
            'output_tokens': int(message_data.get('output_tokens', 0)),
            'total_tokens': int(message_data.get('total_tokens', 0)),
            'created_at': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': current_time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        table_ref = f"{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}"
        
        try:
            # Verificar si la tabla existe
            bigquery_client.get_table(table_ref)
            
            # Insertar datos
            errors = bigquery_client.insert_rows_json(table_ref, [row])
            
            if errors:
                logger.error(f"Error al insertar en BigQuery: {errors}")
                return False
                
            logger.info(f"Mensaje guardado en BigQuery exitosamente. ID: {message_data.get('user_id')}-{message_data.get('message_ts', '')}")
            return True
            
        except Exception as e:
            logger.error(f"Error al acceder a la tabla {table_ref}: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Error inesperado al guardar en BigQuery: {str(e)}", exc_info=True)
        return False

def get_conversation_history(channel_id, user_id, limit=10):
    """Obtiene el historial de conversación para un usuario y canal específicos."""
    global bigquery_client
    
    if not bigquery_client:
        logger.error("BigQuery client no está inicializado en get_conversation_history")
        return []
    
    try:
        query = f"""
            SELECT 
                message_text,
                bot_response,
                message_ts
            FROM 
                `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
            WHERE 
                channel_id = @channel_id 
                AND user_id = @user_id
                AND message_type = 'message'
            ORDER BY 
                message_ts DESC
            LIMIT @limit
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("channel_id", "STRING", channel_id),
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        )
        
        query_job = bigquery_client.query(query, job_config=job_config)
        results = query_job.result()
        
        # Convertir los resultados a una lista de diccionarios
        history = []
        for row in results:
            if row.message_text:  # Solo agregar si hay un mensaje
                history.append({
                    'message_text': row.message_text,
                    'bot_response': row.bot_response or ""
                })
        
        # Invertir el orden para tener el más antiguo primero
        return history
        
    except Exception as e:
        logger.error(f"Error al obtener el historial de conversación: {str(e)}")
        return []

def start_fastapi():
    uvicorn.run(
        "app:fastapi_app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 3000)),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        workers=1,
        reload=False
    )

def start_slack():
    logger.info("Slack app configured to use HTTP events")
    # Verify we can make API calls
    try:
        auth_test = slack_app.client.auth_test()
        logger.info(f"Slack auth test successful: {auth_test}")
    except Exception as e:
        logger.error(f"Slack auth test failed: {str(e)}")

# This will be called when the module is imported by Gunicorn
# or when run directly with Python
if __name__ == "__main__":
    # When running directly with Python
    fastapi_thread = threading.Thread(target=start_fastapi, daemon=True)
    fastapi_thread.start()
    
    try:
        start_slack()
    except Exception as e:
        logger.error(f"Failed to start Slack: {str(e)}")
        raise
else:
    # When running with Gunicorn, we need to start Slack in a separate thread
    import atexit
    import signal
    
    def start_slack_background():
        try:
            logger.info("Starting Slack handler in background thread...")
            start_slack()
        except Exception as e:
            logger.error(f"Error in Slack handler: {str(e)}")
    
    # Start Slack in a background thread
    slack_thread = threading.Thread(target=start_slack_background, daemon=True)
    slack_thread.start()
    
    # Cleanup function
    def cleanup():
        logger.info("Shutting down Slack handler...")
        # Add any cleanup code here if needed
    
    # Register cleanup function
    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, lambda signum, frame: cleanup())
