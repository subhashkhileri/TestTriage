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
    if [ -f "k8s/secrets-template.yaml" ]; then
        echo "🔐 Creating secrets from template..."
        oc apply -f k8s/secrets-template.yaml
        echo "✅ Secrets created successfully"
    else
        echo "⚠️  Secrets not found and no template available. Please create secrets first:"
        echo "   1. Copy k8s/secrets-template.yaml to k8s/secrets.yaml"
        echo "   2. Replace placeholder values with your actual credentials"
        echo "   3. Run: oc apply -f k8s/secrets.yaml"
        echo "   4. Then re-run this script"
        exit 1
    fi
else
    echo "✅ Secrets found"
fi

# Build the container image using OpenShift's built-in Docker build
echo "🔨 Building container image..."
oc new-build --binary --name=$IMAGE_NAME --strategy=docker 2>/dev/null || true
oc start-build $IMAGE_NAME --from-dir=. --follow --wait

echo "✅ Container image built successfully"

# Apply Kubernetes manifests
echo "🚀 Deploying application..."
oc apply -f k8s/deployment.yaml
oc apply -f k8s/service.yaml
oc apply -f k8s/route.yaml

# Set the deployment to use the built image from the ImageStream
echo "🔗 Linking deployment to built image..."
oc set image deployment/slack-bot slack-bot=$IMAGE_NAME:latest

# Wait for deployment to be ready
echo "⏳ Waiting for deployment to be ready..."
oc rollout status deployment/slack-bot --timeout=300s

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