# Google Cloud ilk kurulum (zirvego100@gmail.com hesabi)
# Kullanim: .\infrastructure\gcp\setup.ps1 -ProjectId "your-project-id"
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [string]$Region = "europe-west1",
    [string]$ArtifactRepo = "bcai",
    [string]$Account = "zirvego100@gmail.com"
)

$ErrorActionPreference = "Stop"

Write-Host "GCP hesabi: $Account"
Write-Host "Proje: $ProjectId | Bolge: $Region"

gcloud auth login $Account
gcloud config set project $ProjectId
gcloud config set run/region $Region

$apis = @(
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com"
)

foreach ($api in $apis) {
    Write-Host "API etkinlestiriliyor: $api"
    gcloud services enable $api --project $ProjectId
}

Write-Host "Artifact Registry olusturuluyor..."
gcloud artifacts repositories describe $ArtifactRepo --location=$Region 2>$null
if ($LASTEXITCODE -ne 0) {
    gcloud artifacts repositories create $ArtifactRepo `
        --repository-format=docker `
        --location=$Region `
        --description="Black Crypto AI Bot container images"
}

Write-Host "Cloud Build servis hesabina Artifact Registry yazma izni..."
$projectNumber = gcloud projects describe $ProjectId --format="value(projectNumber)"
$cbSa = "$projectNumber@cloudbuild.gserviceaccount.com"
gcloud artifacts repositories add-iam-policy-binding $ArtifactRepo `
    --location=$Region `
    --member="serviceAccount:$cbSa" `
    --role="roles/artifactregistry.writer" | Out-Null

Write-Host ""
Write-Host "Kurulum tamamlandi."
Write-Host "Sonraki adimlar:"
Write-Host "  1. Cloud SQL PostgreSQL instance olusturun"
Write-Host "  2. Memorystore Redis veya Upstash URL ayarlayin"
Write-Host "  3. infrastructure/gcp/env.gcp.example -> env.gcp kopyalayip doldurun"
Write-Host "  4. .\infrastructure\gcp\deploy.ps1"
