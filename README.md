# Asistente de IA para Slack

Este proyecto implementa un bot de Slack que utiliza la API de OpenAI para proporcionar respuestas inteligentes a los usuarios a través de mensajes directos.

## Características

- Integración con la API de OpenAI para generar respuestas inteligentes
- Interacción mediante mensajes directos en Slack
- Almacenamiento de conversaciones en BigQuery para análisis posteriores
- Configuración flexible mediante variables de entorno
- Sistema de registro de eventos para depuración

## Requisitos previos

- Python 3.8 o superior
- Una cuenta de [Slack](https://api.slack.com/) con permisos para crear aplicaciones
- Una cuenta de [OpenAI](https://platform.openai.com/) con acceso a la API
- (Opcional) Una cuenta de Google Cloud Platform con BigQuery habilitado

## Instalación

1. Clona el repositorio:
   ```bash
   git clone [URL_DEL_REPOSITORIO]
   cd template_ia
   ```

2. Crea y activa un entorno virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

## Configuración

1. Copia el archivo de ejemplo de variables de entorno:
   ```bash
   cp .env.example .env
   ```

2. Edita el archivo `.env` con tus credenciales:
   ```env
   # OpenAI Configuration
   OPENAI_API_KEY=tu_api_key_de_openai
   OPENAI_MODEL=gpt-4o-mini
   MAX_TOKENS=4000
   TEMPERATURE=0.3

   # Slack Configuration
   SLACK_BOT_TOKEN=tu_token_de_bot_de_slack
   SLACK_SIGNING_SECRET=tu_signing_secret_de_slack
   SLACK_APP_TOKEN=tu_app_token_de_slack

   # Configuración opcional de BigQuery
   BIGQUERY_PROJECT_ID=tu_proyecto_de_gcp
   BIGQUERY_DATASET=nombre_del_dataset
   BIGQUERY_TABLE=nombre_de_la_tabla
   GOOGLE_APPLICATION_CREDENTIALS_JSON=tu_json_de_credenciales
   ```

## Configuración en Slack

1. Crea una nueva aplicación en [Slack API](https://api.slack.com/apps)
2. Configura los siguientes permisos de OAuth & Permissions:
   - `chat:write`
   - `im:history`
   - `im:write`
   - `reactions:write`
3. Instala la aplicación en tu espacio de trabajo
4. Copia los tokens necesarios al archivo `.env`

## Ejecución

### Modo desarrollo

Para ejecutar la aplicación en modo desarrollo:

```bash
uvicorn app:fastapi_app --reload
```

### Producción con Gunicorn

Para producción, se recomienda usar Gunicorn con Uvicorn:

```bash
gunicorn -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000 app:fastapi_app
```

## Uso

1. Inicia una conversación directa con el bot en Slack
2. Envía un mensaje al bot y recibirás una respuesta generada por IA
3. El bot reaccionará con 👀 cuando esté procesando tu mensaje

## Estructura del proyecto

```
.
├── .env.example          # Plantilla de variables de entorno
├── .gitignore           # Archivos ignorados por Git
├── README.md            # Este archivo
├── app.py               # Código principal de la aplicación
├── requirements.txt     # Dependencias de Python
└── docker/              # Configuración de Docker (opcional)
```

## Despliegue

### Docker

Se incluye un `Dockerfile` para facilitar el despliegue con Docker:

```bash
# Construir la imagen
docker build -t asistente-ia-slack .

# Ejecutar el contenedor
docker run -d --name asistente-ia-slack --env-file .env -p 8000:8000 asistente-ia-slack
```

### Plataformas en la nube

La aplicación puede desplegarse en cualquier plataforma que soporte aplicaciones Python, como:
- Google Cloud Run
- AWS Elastic Beanstalk
- Heroku
- Render

## Monitoreo y registro

La aplicación registra eventos importantes en la consola. Para producción, se recomienda configurar un servicio de registro como:
- Google Cloud Logging
- AWS CloudWatch
- Datadog

## Contribución

1. Haz un fork del proyecto
2. Crea una rama para tu característica (`git checkout -b feature/nueva-caracteristica`)
3. Haz commit de tus cambios (`git commit -am 'Añade nueva característica'`)
4. Haz push a la rama (`git push origin feature/nueva-caracteristica`)
5. Abre un Pull Request

## Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo `LICENSE` para más información.

## Soporte

Si encuentras algún problema o tienes preguntas, por favor abre un issue en el repositorio.

---

Desarrollado con ❤️ por [Tu Nombre]
