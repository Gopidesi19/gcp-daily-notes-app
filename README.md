
# GCP Daily Notes Application

This project is a complete 3-tier web application designed to run on Google Cloud Platform. It allows users to write, save, and view daily notes through a simple web interface. The application is built with a Python Flask backend, a Firestore database, and is deployed using modern CI/CD practices with Cloud Build, Artifact Registry, and Cloud Run.

## Architecture Overview

The application follows a classic 3-tier architecture:

1.  **Frontend (Presentation Layer):** A simple HTML interface rendered by Flask Templates. It provides the user interface for note entry and viewing.
2.  **Application Layer:** A Python Flask backend running in a Docker container on Cloud Run. It handles HTTP requests, interacts with the database, and serves the frontend.
3.  **Data Layer:** Google Cloud Firestore is used as the NoSQL database to store and retrieve notes.

### Cloud Services Used

-   **Cloud Run:** Hosts the containerized Flask application.
-   **API Gateway:** Provides a secure, managed entry point for the application.
-   **Artifact Registry:** Stores the Docker container images.
-   **Cloud Build:** Automates the build, push, and deployment of the application.
-   **Firestore:** Serves as the persistent data store for notes.
-   **Cloud Monitoring & Logging:** Provide observability, metrics, and logs.
-   **Alerts & Notifications:** Configured to notify on application failures.

### Architecture Diagram

```
User Browser --> HTTPS --> API Gateway --> Cloud Run (Flask App) --> Firestore DB
```

---

## Implementation Stages

This guide will walk you through deploying the application from scratch.

### Stage 0: Prerequisites & Setup

Before you begin, ensure you have the following:

1.  **Google Cloud Account:** With an active project and billing enabled.
2.  **gcloud CLI:** [Installed and authenticated](https://cloud.google.com/sdk/docs/install).
3.  **Docker:** [Installed locally](https://docs.docker.com/get-docker/).

**1. Configure Environment Variables**

Set these variables to match your GCP project details. This will simplify the commands in later steps.

```sh
export PROJECT_ID="[YOUR_PROJECT_ID]"
export REGION="[YOUR_PREFERRED_REGION]" # e.g., us-central1
export GCLOUD_ACCOUNT=$(gcloud config get-value account)

gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION
```

**2. Enable Required Google APIs**

This command ensures all necessary services are enabled for your project.

```sh
gcloud services enable 
  run.googleapis.com 
  apigateway.googleapis.com 
  artifactregistry.googleapis.com 
  cloudbuild.googleapis.com 
  firestore.googleapis.com 
  logging.googleapis.com 
  monitoring.googleapis.com
```

### Stage 1: Data Layer (Firestore)

Create the Firestore database in "Native" mode, which is the standard for new projects.

```sh
gcloud firestore databases create --location=$REGION
```

### Stage 2: Application Layer (Cloud Run & CI/CD)

**1. Create an Artifact Registry Repository**

This repository will store the Docker images for our application.

```sh
gcloud artifacts repositories create daily-notes-repo 
  --repository-format=docker 
  --location=$REGION 
  --description="Docker repository for Daily Notes App"
```

**2. Grant Permissions to Cloud Build**

The Cloud Build service account needs permission to build and deploy.

```sh
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

# Grant Cloud Build rights to deploy to Cloud Run
gcloud projects add-iam-policy-binding $PROJECT_ID 
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" 
    --role="roles/run.admin"

# Grant Cloud Build rights to act as a user of the Cloud Run service account
gcloud iam service-accounts add-iam-policy-binding 
    $(gcloud iam service-accounts list --filter="displayName:Compute Engine default service account" --format="value(email)") 
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" 
    --role="roles/iam.serviceAccountUser"
```

**3. Automate Deployment with Cloud Build**

Submit the build process. Cloud Build will follow the instructions in `cloudbuild.yaml` to:
- Build the Docker image.
- Push the image to Artifact Registry.
- Deploy the new image to Cloud Run.

```sh
gcloud builds submit --config cloudbuild.yaml
```

The service name `gcp-daily-notes-app` is defined in the `cloudbuild.yaml` file.

### Stage 3: Frontend & Gateway (API Gateway)

**1. Create a Service Account for API Gateway**

The gateway needs a dedicated identity to securely invoke your Cloud Run service.

```sh
gcloud iam service-accounts create api-gateway-invoker
export GATEWAY_SA_EMAIL=$(gcloud iam service-accounts list --filter="displayName:api-gateway-invoker" --format="value(email)")

# Grant the new service account permission to invoke the Cloud Run service
gcloud run services add-iam-policy-binding gcp-daily-notes-app 
  --member="serviceAccount:${GATEWAY_SA_EMAIL}" 
  --role='roles/run.invoker' 
  --platform=managed
```

**2. Update the OpenAPI Configuration**

Before creating the gateway, you must insert your specific Cloud Run service URL into the `openapi.yaml` file.

- **First, get your Cloud Run service URL:**
  ```sh
  export SERVICE_URL=$(gcloud run services describe gcp-daily-notes-app --platform managed --format 'value(status.url)')
  echo "Your service URL is: $SERVICE_URL"
  ```
- **Then, replace the placeholder `[YOUR_SERVICE_URL_HERE]` in `openapi.yaml` with the URL you just retrieved.**

**3. Create the API Gateway**

This process creates the API definition and then the public gateway itself.

```sh
# Create the API config
gcloud api-gateway api-configs create daily-notes-config 
  --api=daily-notes-api --openapi-spec=openapi.yaml 
  --project=$PROJECT_ID --backend-auth-service-account=$GATEWAY_SA_EMAIL

# Create the gateway
gcloud api-gateway gateways create daily-notes-gateway 
  --api=daily-notes-api --api-config=daily-notes-config 
  --location=$REGION --project=$PROJECT_ID
```

**4. Get Your Public Application URL**

```sh
export GATEWAY_URL=$(gcloud api-gateway gateways describe daily-notes-gateway --location=$REGION --format="value(defaultHostname)")
echo "Application is now available at: https://${GATEWAY_URL}"
```

You can now access your application at the URL provided!

### Stage 4: Monitoring, Logging, and Alerts

-   **Logging:** All `print()` and `logging` statements from the Flask app, as well as request logs from Cloud Run and API Gateway, are automatically sent to [Cloud Logging](https://console.cloud.google.com/logs/viewer).
-   **Monitoring:** Key metrics like request latency, CPU usage, and error counts for both API Gateway and Cloud Run are available in [Cloud Monitoring](https://console.cloud.google.com/monitoring).
-   **Alerting:** To get notified of issues (e.g., a spike in 5xx server errors), you can create an alerting policy.
    1.  Go to the [Alerting section](https://console.cloud.google.com/monitoring/alerting) in the console.
    2.  Click **"Create Policy"**.
    3.  Select a metric, such as `Cloud Run Revision > Request Count` and filter by `response_code_class = 5xx`.
    4.  Set a threshold (e.g., "above 5 requests in 1 minute").
    5.  Configure a notification channel (e.g., Email, SMS) to receive alerts.

### Stage 5: How to Clean Up

To avoid incurring future charges, delete the created resources.

```sh
# Delete the API Gateway
gcloud api-gateway gateways delete daily-notes-gateway --location=$REGION
gcloud api-gateway api-configs delete daily-notes-config --api=daily-notes-api
gcloud api-gateway apis delete daily-notes-api

# Delete the Cloud Run service
gcloud run services delete gcp-daily-notes-app --platform=managed

# Delete the Artifact Registry repository
gcloud artifacts repositories delete daily-notes-repo --location=$REGION

# Delete the Firestore database (requires manual confirmation)
# You may also need to delete the storage bucket associated with it.

# To delete the entire project:
gcloud projects delete $PROJECT_ID
```
