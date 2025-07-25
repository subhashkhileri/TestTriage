#!/bin/bash

# Deploy Slack Bot to OpenShift Container Platform
set -e

# Configuration
PROJECT_NAME="slack-bot"
IMAGE_NAME="slack-bot"

echo "🚀 Deploying Slack Bot to OpenShift Container Platform"

# Check if oc command is available
if ! command -v oc &> /dev/null; then
    echo "❌ Error: 'oc' command not found. Please install OpenShift CLI."
    exit 1
fi

# Check if logged in to OpenShift
if ! oc whoami &> /dev/null; then
    echo "❌ Error: Not logged in to OpenShift. Please run 'oc login' first."
    exit 1
fi

echo "✅ OpenShift CLI available and logged in"

# Create or switch to project
echo "📁 Creating/switching to project: $PROJECT_NAME"
oc new-project $PROJECT_NAME 2>/dev/null || oc project $PROJECT_NAME

# Check if secrets exist, if not, create them from template
if ! oc get secret slack-secrets &> /dev/null; then
    echo "⚠️  Secrets not found and no template available. Please create secrets"
else
    echo "✅ Secrets found"
fi

# Build the container image using OpenShift's built-in Docker build
echo "🔨 Building container image..."
oc new-build --binary --name=$IMAGE_NAME --strategy=docker 2>/dev/null || true

# Create a temporary directory with only necessary files
echo "📦 Preparing build context (excluding venv and unnecessary files)..."
BUILD_DIR=$(mktemp -d)
trap "rm -rf $BUILD_DIR" EXIT

# Copy files excluding venv, k8s, and other unnecessary directories
rsync -av --exclude='venv/' --exclude='k8s/' --exclude='.git/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.log' --exclude='.DS_Store' . "$BUILD_DIR/"

# Start build with clean directory
oc start-build $IMAGE_NAME --from-dir="$BUILD_DIR" --follow --wait

# Clean up build directory immediately after build
echo "🗑️  Cleaning up build directory..."
rm -rf "$BUILD_DIR"

echo "✅ Container image built successfully"

# Apply Kubernetes manifests
echo "🚀 Deploying application..."
oc apply -f k8s/pvc.yaml
oc apply -f k8s/deployment.yaml
oc apply -f k8s/service.yaml
oc apply -f k8s/route.yaml

# The deployment.yaml already has the correct image reference to the internal registry
echo "✅ Deployment applied with correct image reference"

# Wait for deployment to be ready
# echo "⏳ Waiting for deployment to be ready..."
# oc rollout status deployment/slack-bot --timeout=300s

# Get the route URL
ROUTE_URL=$(oc get route slack-bot-route -o jsonpath='{.spec.host}')
echo "✅ Deployment complete!"
echo "🌐 Application URL: https://$ROUTE_URL"
echo ""
echo "📝 Next steps:"
echo "   1. Update your Slack app's Request URL to: https://$ROUTE_URL"
echo "   2. Test your bot by mentioning it in a Slack channel"
echo ""
echo "🔍 To check logs: oc logs -f deployment/slack-bot" 