# Ejecutar con Docker

## Requisitos previos
- Docker y Docker Compose instalados en tu sistema
- Cuenta en Docker Hub (solo para subir la imagen)
- Archivo `.env` configurado con tus credenciales

## Construir la imagen localmente

```bash
# Construir la imagen
docker build -t alberth121484/vokse:1.0.1 .

# O para la última versión
docker build -t alberth121484/vokse:latest .
```

## Ejecutar el contenedor

```bash
docker run -d \
  --name vokse-bot \
  -e OPENAI_API_KEY=tu_api_key_aqui \
  -e SLACK_BOT_TOKEN=tu_slack_bot_token \
  -e SLACK_SIGNING_SECRET=tu_slack_signing_secret \
  -e SLACK_APP_TOKEN=tu_slack_app_token \
  alberth121484/vokse:1.0.1
```

## Variables de entorno necesarias

Asegúrate de configurar estas variables de entorno al ejecutar el contenedor:

- `OPENAI_API_KEY`: Tu clave de API de OpenAI
- `SLACK_BOT_TOKEN`: Token de bot de Slack
- `SLACK_SIGNING_SECRET`: Secreto de firma de Slack
- `SLACK_APP_TOKEN`: Token de aplicación de Slack
- `OPENAI_MODEL`: (Opcional) Modelo de OpenAI a utilizar (por defecto: gpt-4o-mini)
- `MAX_TOKENS`: (Opcional) Máximo de tokens para la respuesta (por defecto: 4000)
- `TEMPERATURE`: (Opcional) Temperatura para la generación (por defecto: 0.3)

## Subir la imagen a Docker Hub

1. Inicia sesión en Docker Hub:
   ```bash
   docker login -u alberth121484
   ```

2. Construye y etiqueta la imagen:
   ```bash
   docker build -t alberth121484/vokse:1.0.1 .
   docker tag alberth121484/vokse:1.0.1 alberth121484/vokse:latest
   ```

3. Sube las imágenes:
   ```bash
   docker push alberth121484/vokse:1.0.1
   docker push alberth121484/vokse:latest
   ```

## Usar Docker Compose

1. Copia el archivo `.env.example` a `.env` y configura las variables de entorno:
   ```bash
   cp .env.example .env
   # Edita el archivo .env con tus credenciales
   ```

2. Inicia el servicio con Docker Compose:
   ```bash
   docker-compose up -d
   ```

3. Para ver los logs:
   ```bash
   docker-compose logs -f
   ```

4. Para detener el servicio:
   ```bash
   docker-compose down
   ```

## Usar el script de construcción

También puedes usar el script `build_and_push.sh` para automatizar el proceso de construcción y subida:

```bash
chmod +x build_and_push.sh
./build_and_push.sh
```
