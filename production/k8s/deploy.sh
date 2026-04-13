#!/usr/bin/env bash
# FlowSync Customer Success AI Agent -- Deploy Script
# =====================================================
# Automates the deployment of FlowSync to Kubernetes.
#
# Usage:
#   ./deploy.sh minikube          # Deploy to local minikube
#   ./deploy.sh production        # Deploy to cloud cluster (requires context set)
#   ./deploy.sh status            # Check deployment status
#   ./deploy.sh teardown          # Remove all FlowSync resources
#   ./deploy.sh logs api          # View API logs
#   ./deploy.sh logs worker       # View worker logs
#   ./deploy.sh port-forward      # Forward local port to API

set -euo pipefail

NAMESPACE="flowsync"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="${SCRIPT_DIR}/k8s"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() { echo -e "${BLUE}[FLOW]${NC} $1"; }
ok()  { echo -e "${GREEN}[ OK ]${NC} $1"; }
warn(){ echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERR ]${NC} $1"; }

# ──────────────────────────────────────────────────────────────
# DEPLOY TO MINIKUBE
# ──────────────────────────────────────────────────────────────
deploy_minikube() {
    log "Starting Minikube deployment..."

    # Check minikube
    if ! command -v minikube &>/dev/null; then
        err "minikube not found. Install from https://minikube.sigs.k8s.io/docs/start/"
        exit 1
    fi

    # Start minikube if not running
    if ! minikube status &>/dev/null; then
        log "Starting minikube..."
        minikube start --cpus=4 --memory=8192 --disk-size=40g
    fi

    # Enable addons
    log "Enabling minikube addons..."
    minikube addons enable metrics-server 2>/dev/null || true
    minikube addons enable ingress 2>/dev/null || true

    # Ensure we use minikube context
    kubectl config use-context minikube

    # Build Docker image in minikube
    log "Building Docker image in minikube..."
    eval $(minikube docker-env)
    docker build -t flowsync/flowsync-api:latest -t flowsync/flowsync-worker:latest \
        -f "${SCRIPT_DIR}/Dockerfile" "${SCRIPT_DIR}"

    # Create namespace
    log "Creating namespace..."
    kubectl apply -f "${K8S_DIR}/namespace.yaml" 2>/dev/null || true

    # Create secrets (with placeholder values for minikube)
    log "Creating secrets..."
    kubectl create secret generic flowsync-secrets \
        --from-literal=DB_PASSWORD='flowsync_secret' \
        --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY:-sk-placeholder}" \
        --from-literal=JWT_SECRET='minikube-jwt-secret' \
        --namespace="${NAMESPACE}" 2>/dev/null || \
        warn "Secrets already exist (use 'kubectl delete secret flowsync-secrets -n flowsync' to recreate)"

    # Deploy everything
    log "Applying Kubernetes manifests..."
    kubectl apply -f "${K8S_DIR}/configmap.yaml"
    kubectl apply -f "${K8S_DIR}/postgres.yaml" 2>/dev/null || warn "Postgres manifest failed (may already exist)"
    kubectl apply -f "${K8S_DIR}/deployment-api.yaml"
    kubectl apply -f "${K8S_DIR}/deployment-worker.yaml"
    kubectl apply -f "${K8S_DIR}/service.yaml"
    kubectl apply -f "${K8S_DIR}/hpa.yaml"

    # Wait for Postgres
    log "Waiting for PostgreSQL to be ready..."
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=postgres \
        --namespace="${NAMESPACE}" --timeout=120s 2>/dev/null || \
        warn "Postgres not ready (may need more time)"

    # Wait for API
    log "Waiting for API pods to be ready..."
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=api \
        --namespace="${NAMESPACE}" --timeout=180s 2>/dev/null || \
        warn "API pods not ready yet (check with: ./deploy.sh status)"

    # Minikube service URL
    local api_url
    api_url=$(minikube service flowsync-api-external -n flowsync --url 2>/dev/null | head -1 || echo "N/A")

    ok "Minikube deployment complete!"
    echo ""
    log "API URL: ${api_url}"
    log "Test: curl ${api_url}/health"
    log "Docs: curl ${api_url}/docs"
    log "Status: ./deploy.sh status"
    echo ""
    log "Port-forward alternative: ./deploy.sh port-forward"
}

# ──────────────────────────────────────────────────────────────
# DEPLOY TO PRODUCTION (cloud)
# ──────────────────────────────────────────────────────────────
deploy_production() {
    log "Starting production deployment..."

    # Check prerequisites
    if ! command -v kubectl &>/dev/null; then
        err "kubectl not found"
        exit 1
    fi

    # Check context
    local context
    context=$(kubectl config current-context 2>/dev/null || echo "none")
    if [ "${context}" = "none" ]; then
        err "No kubectl context set. Run: gcloud container clusters get-credentials <name>"
        exit 1
    fi
    log "Using context: ${context}"

    # Build and push Docker images
    log "Building Docker images..."
    docker build -t flowsync/flowsync-api:latest --target api -f "${SCRIPT_DIR}/Dockerfile" "${SCRIPT_DIR}"
    docker build -t flowsync/flowsync-worker:latest --target worker -f "${SCRIPT_DIR}/Dockerfile" "${SCRIPT_DIR}"

    # Tag and push to registry
    local registry="${REGISTRY:-ghcr.io/your-org}"
    log "Pushing images to ${registry}..."
    docker tag flowsync/flowsync-api:latest "${registry}/flowsync-api:latest"
    docker tag flowsync/flowsync-worker:latest "${registry}/flowsync-worker:latest"
    docker push "${registry}/flowsync-api:latest"
    docker push "${registry}/flowsync-worker:latest"

    # Create secrets (must have real values)
    if [ -z "${OPENAI_API_KEY:-}" ]; then
        err "OPENAI_API_KEY environment variable not set"
        exit 1
    fi

    log "Creating secrets..."
    kubectl create secret generic flowsync-secrets \
        --from-literal=DB_PASSWORD="${DB_PASSWORD:-flowsync_secret}" \
        --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY}" \
        --from-literal=JWT_SECRET="${JWT_SECRET:-$(openssl rand -base64 32)}" \
        --namespace="${NAMESPACE}" 2>/dev/null || \
        warn "Secrets already exist"

    # Deploy
    log "Applying manifests..."
    kubectl apply -f "${K8S_DIR}/namespace.yaml"
    kubectl apply -f "${K8S_DIR}/configmap.yaml"
    kubectl apply -f "${K8S_DIR}/deployment-api.yaml"
    kubectl apply -f "${K8S_DIR}/deployment-worker.yaml"
    kubectl apply -f "${K8S_DIR}/service.yaml"
    kubectl apply -f "${K8S_DIR}/hpa.yaml"

    # Ingress (if available)
    if [ -f "${K8S_DIR}/ingress.yaml" ]; then
        log "Applying ingress..."
        kubectl apply -f "${K8S_DIR}/ingress.yaml" 2>/dev/null || \
            warn "Ingress failed (may need Ingress controller)"
    fi

    ok "Production deployment initiated!"
    log "Monitor: kubectl get pods -n ${NAMESPACE} -w"
    log "Status:  ./deploy.sh status"
}

# ──────────────────────────────────────────────────────────────
# STATUS
# ──────────────────────────────────────────────────────────────
show_status() {
    log "FlowSync Deployment Status"
    echo "========================"
    echo ""

    log "Pods:"
    kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=flowsync 2>/dev/null || \
        err "No FlowSync pods found"
    echo ""

    log "Services:"
    kubectl get svc -n "${NAMESPACE}" 2>/dev/null || \
        err "No services found"
    echo ""

    log "HPA:"
    kubectl get hpa -n "${NAMESPACE}" 2>/dev/null || \
        warn "HPA not available (install metrics-server)"
    echo ""

    log "Events (last 10):"
    kubectl get events -n "${NAMESPACE}" --sort-by='.lastTimestamp' 2>/dev/null | tail -10 || true
}

# ──────────────────────────────────────────────────────────────
# TEARDOWN
# ──────────────────────────────────────────────────────────────
teardown() {
    log "Tearing down FlowSync deployment..."

    read -p "This will delete all FlowSync resources. Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log "Aborted"
        exit 0
    fi

    kubectl delete -f "${K8S_DIR}/hpa.yaml" 2>/dev/null || true
    kubectl delete -f "${K8S_DIR}/ingress.yaml" 2>/dev/null || true
    kubectl delete -f "${K8S_DIR}/deployment-api.yaml" 2>/dev/null || true
    kubectl delete -f "${K8S_DIR}/deployment-worker.yaml" 2>/dev/null || true
    kubectl delete -f "${K8S_DIR}/service.yaml" 2>/dev/null || true
    kubectl delete -f "${K8S_DIR}/postgres.yaml" 2>/dev/null || true
    kubectl delete -f "${K8S_DIR}/kafka.yaml" 2>/dev/null || true
    kubectl delete -f "${K8S_DIR}/configmap.yaml" 2>/dev/null || true
    kubectl delete secret flowsync-secrets -n "${NAMESPACE}" 2>/dev/null || true
    kubectl delete namespace "${NAMESPACE}" 2>/dev/null || true

    ok "FlowSync resources removed"
}

# ──────────────────────────────────────────────────────────────
# LOGS
# ──────────────────────────────────────────────────────────────
show_logs() {
    local component="${1:-api}"
    log "Showing ${component} logs..."
    kubectl logs -n "${NAMESPACE}" -l "app.kubernetes.io/component=${component}" -f 2>/dev/null || \
        err "No ${component} pods found"
}

# ──────────────────────────────────────────────────────────────
# PORT FORWARD
# ──────────────────────────────────────────────────────────────
port_forward() {
    log "Forwarding localhost:8000 to flowsync-api..."
    kubectl port-forward -n "${NAMESPACE}" \
        svc/flowsync-api 8000:80 &
    local pid=$!
    log "API available at http://localhost:8000"
    log "Docs at http://localhost:8000/docs"
    log "Press Ctrl+C to stop"

    trap "kill ${pid} 2>/dev/null; log 'Port forwarding stopped'" INT TERM
    wait ${pid} 2>/dev/null || true
}

# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────
case "${1:-help}" in
    minikube)     deploy_minikube ;;
    production)   deploy_production ;;
    status)       show_status ;;
    teardown)     teardown ;;
    logs)         show_logs "${2:-api}" ;;
    port-forward) port_forward ;;
    help|*)
        echo "FlowSync Kubernetes Deploy Script"
        echo ""
        echo "Usage: $0 <command> [args]"
        echo ""
        echo "Commands:"
        echo "  minikube          Deploy to local minikube cluster"
        echo "  production        Deploy to cloud cluster (set context first)"
        echo "  status            Show deployment status"
        echo "  teardown          Remove all FlowSync resources"
        echo "  logs [component]  View logs (api|worker|postgres)"
        echo "  port-forward      Forward localhost:8000 to API"
        echo "  help              Show this help"
        ;;
esac
