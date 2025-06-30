#!/bin/bash

# Google Cloud Run Deployment Script for Browserbase Scraper
# Make sure you have gcloud CLI installed and authenticated

set -e

# Configuration
PROJECT_ID="your-gcp-project-id"
SERVICE_NAME="browserbase-scraper"
REGION="us-central1"
BUCKET_NAME="your-scraper-results"

echo "🚀 Starting deployment to Google Cloud Run..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install it first."
    exit 1
fi

# Set the project
echo "📋 Setting GCP project to: $PROJECT_ID"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable storage.googleapis.com

# Create storage bucket if it doesn't exist
echo "📦 Creating storage bucket: $BUCKET_NAME"
gsutil mb gs://$BUCKET_NAME 2>/dev/null || echo "Bucket already exists or you don't have permission"

# Build and deploy to Cloud Run
echo "🏗️ Building and deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --source . \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 1 \
    --timeout 3600 \
    --set-env-vars "GCS_BUCKET_NAME=$BUCKET_NAME" \
    --set-env-vars "BROWSERBASE_API_KEY=$BROWSERBASE_API_KEY" \
    --set-env-vars "BROWSERBASE_PROJECT_ID=$BROWSERBASE_PROJECT_ID"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')

echo "✅ Deployment complete!"
echo "📡 Service URL: $SERVICE_URL"
echo ""
echo "🕒 To create a daily scheduler, run:"
echo "gcloud scheduler jobs create http $SERVICE_NAME-daily \\"
echo "    --schedule='0 9 * * *' \\"
echo "    --uri='$SERVICE_URL' \\"
echo "    --http-method=POST \\"
echo "    --location=$REGION"
echo ""
echo "🔍 Test the deployment:"
echo "curl -X POST $SERVICE_URL"
echo ""
echo "📊 Check status:"
echo "curl $SERVICE_URL/status" 