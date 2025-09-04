#!/bin/bash

# Set version and image name
VERSION="1.0.1"
IMAGE_NAME="alberth121484/vokse"

# Build the Docker image
echo "Building Docker image ${IMAGE_NAME}:${VERSION}..."
docker build -t ${IMAGE_NAME}:${VERSION} .

# Tag as latest
echo "Tagging as latest..."
docker tag ${IMAGE_NAME}:${VERSION} ${IMAGE_NAME}:latest

# Push the Docker images
echo "Pushing Docker images..."
docker push ${IMAGE_NAME}:${VERSION}
docker push ${IMAGE_NAME}:latest

echo -e "\n✅ Image successfully built and pushed to Docker Hub:"
echo "- ${IMAGE_NAME}:${VERSION}"
echo "- ${IMAGE_NAME}:latest"
