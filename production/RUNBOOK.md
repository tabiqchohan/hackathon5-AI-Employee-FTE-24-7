# FlowSync Operations Runbook

## Incident Response & Operational Guide

---

## 1. Monitoring Commands

### Quick Health Check
```bash
# API health
curl http://localhost:8000/health | python -m json.tool

# Pod status
kubectl get pods -n flowsync

# Service status
kubectl get svc -n flowsync

# HPA status (auto-scaling)
kubectl get hpa -n flowsync

# Recent events
kubectl get events -n flowsync --sort-by='.lastTimestamp' | tail -20
```

### Detailed Diagnostics
```bash
# API logs
kubectl logs -n flowsync -l app.kubernetes.io/component=api --tail=100 -f

# Worker logs
kubectl logs -n flowsync -l app.kubernetes.io/component=worker --tail=100 -f

# Postgres logs
kubectl logs -n flowsync -l app.kubernetes.io/component=postgres --tail=50

# Pod details
kubectl describe pod -n flowsync -l app.kubernetes.io/component=api

# Database connectivity from inside a pod
kubectl exec -n flowsync deploy/flowsync-api -- \
  python -c "import os; from database import queries; import asyncio; \
  asyncio.run(queries.get_db_pool()); print('DB connected')"

# Kafka topic status (if using in-cluster Kafka)
kubectl exec -n flowsync flowsync-kafka-0 -- \
  kafka-run-class.sh kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 --topic fte.tickets.incoming
```

### Port Forward for Local Debugging
```bash
# Forward API
kubectl port-forward -n flows svc/flowsync-api 8000:80 &

# Forward Postgres (for direct queries)
kubectl port-forward -n flows svc/flowsync-postgres 5432:5432 &

# Direct DB query
PGPASSWORD=flowsync_secret psql -h localhost -U flowsync -d flowsync -c \
  "SELECT count(*) FROM tickets;"
```

---

## 2. Common Issues & Resolutions

### Issue: API pods crashlooping
**Symptoms:**
```
NAME                    READY   STATUS             RESTARTS
flowsync-api-abc123     0/1     CrashLoopBackOff   5
```

**Diagnosis:**
```bash
kubectl logs -n flowsync deploy/flowsync-api --tail=50
kubectl describe pod -n flowsync -l app.kubernetes.io/component=api | grep -A5 "State:"
```

**Likely causes:**
| Cause | Fix |
|-------|-----|
| Missing OPENAI_API_KEY | `kubectl set env deploy/flowsync-api OPENAI_API_KEY=sk-... -n flowsync` |
| DB connection failure | Check DB pod: `kubectl get pod -n flowsync -l app.kubernetes.io/component=postgres` |
| Image pull error | Verify image: `kubectl get deploy flowsync-api -n flowsync -o yaml | grep image` |
| OOMKilled | Increase memory limit in deployment-api.yaml |

### Issue: Worker pods not processing messages
**Symptoms:**
```
kubectl logs -n flowsync deploy/flowsync-worker --tail=20
# Output: "Kafka unavailable, operating in direct-processing mode"
```

**Diagnosis:**
```bash
# Check Kafka pod
kubectl get pods -n flowsync -l app.kubernetes.io/component=kafka

# Check Kafka logs
kubectl logs -n flowsync -l app.kubernetes.io/component=kafka --tail=50

# Test Kafka connectivity
kubectl exec -n flowsync deploy/flowsync-worker -- \
  python -c "from kafka_client import FTEKafkaProducer, Topics; \
  import asyncio; p = FTEKafkaProducer(); asyncio.run(p.start()); print('Kafka OK')"
```

**Fixes:**
- If Kafka is down: Restart Kafka pods or check Strimzi operator
- If using managed Kafka: Verify bootstrap servers in ConfigMap
- Temporary fallback: Workers process directly without Kafka (degraded mode)

### Issue: High latency on API responses
**Symptoms:**
```bash
# 95th percentile > 5 seconds
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/health
```

**Diagnosis:**
```bash
# Check HPA
kubectl get hpa -n flowsync

# Check CPU/Memory usage
kubectl top pods -n flowsync

# Check if scaling up
kubectl describe hpa flowsync-api-hpa -n flowsync
```

**Fixes:**
- If HPA maxed: Increase `maxReplicas` in hpa.yaml (API: up to 20, Worker: up to 30)
- If DB bottleneck: Check Postgres slow queries: `kubectl exec -n flowsync flowsync-postgres-0 -- psql -U flowsync -d flowsync -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"`
- If OpenAI API slow: Consider switching to faster model or adding timeout

### Issue: Database connection pool exhausted
**Symptoms:**
```
WARNING | Database pool not available
Error retrieving customer history
```

**Diagnosis:**
```bash
# Check Postgres connections
kubectl exec -n flowsync flowsync-postgres-0 -- psql -U flowsync -d flowsync -c \
  "SELECT count(*) FROM pg_stat_activity WHERE datname = 'flowsync';"

# Check pool config
kubectl get configmap flowsync-config -n flowsync -o yaml | grep POOL
```

**Fixes:**
- Increase DB_POOL_MAX_SIZE in configmap.yaml (default: 20)
- Add connection pooler (PgBouncer) for high traffic
- Restart API pods to reset pool: `kubectl rollout restart deploy/flowsync-api -n flowsync`

### Issue: Escalation rate too high
**Symptoms:**
```bash
# Check worker stats
kubectl logs -n flowsync deploy/flowsync-worker --tail=100 | grep -i "escalat"
# >30% of messages being escalated
```

**Diagnosis:**
- Check escalation logs for common triggers
- Review knowledge base coverage (missing KB articles cause escalation)
- Check sentiment analysis accuracy

**Fixes:**
- Add more knowledge base articles
- Tune escalation thresholds in workers/message_processor.py
- Review system prompt in agent/prompts.py for overly aggressive escalation rules

---

## 3. Scaling Guide

### Manual Scaling
```bash
# Scale API
kubectl scale deploy/flowsync-api --replicas=5 -n flowsync

# Scale Workers
kubectl scale deploy/flowsync-worker --replicas=10 -n flowsync
```

### Auto-Scaling (HPA)
Current HPA config:
| Component | Min | Max | CPU Target | Memory Target |
|-----------|-----|-----|------------|---------------|
| API | 3 | 10 | 70% | 80% |
| Worker | 3 | 15 | 70% | 80% |

To adjust, edit `k8s/hpa.yaml`:
```yaml
spec:
  minReplicas: 5    # Increase minimum
  maxReplicas: 20   # Increase maximum
  metrics:
    - resource:
        target:
          averageUtilization: 50  # Scale earlier (more aggressive)
```

### When to Scale
| Metric | Threshold | Action |
|--------|-----------|--------|
| CPU utilization | >70% sustained | Scale up |
| Memory utilization | >80% sustained | Scale up or increase limits |
| API response time p95 | >3s | Scale API |
| Kafka lag | >1000 messages | Scale workers |
| Error rate | >5% | Investigate before scaling |
| DB connections | >80% of pool | Increase pool size or add PgBouncer |

---

## 4. Deployment Procedures

### Rolling Update
```bash
# Build new image
docker build -t flowsync/flowsync-api:v1.1.0 --target api -f Dockerfile .
docker push flowsync/flowsync-api:v1.1.0

# Update deployment
kubectl set image deploy/flowsync-api api=flowsync/flowsync-api:v1.1.0 -n flowsync

# Monitor rollout
kubectl rollout status deploy/flowsync-api -n flowsync

# Rollback if needed
kubectl rollout undo deploy/flowsync-api -n flowsync
```

### ConfigMap Update
```bash
# Edit configmap
kubectl edit configmap flowsync-config -n flowsync

# Restart pods to pick up changes
kubectl rollout restart deploy/flowsync-api -n flowsync
kubectl rollout restart deploy/flowsync-worker -n flowsync
```

### Secrets Rotation
```bash
# Update secret
kubectl create secret generic flowsync-secrets \
  --from-literal=DB_PASSWORD='new-password' \
  --from-literal=OPENAI_API_KEY='sk-new-key' \
  --from-literal=JWT_SECRET='new-jwt-secret' \
  -n flowsync --dry-run=client -o yaml | kubectl apply -f -

# Restart pods
kubectl rollout restart deploy/flowsync-api -n flowsync
kubectl rollout restart deploy/flowsync-worker -n flowsync
```

---

## 5. Backup & Recovery

### Database Backup
```bash
# Backup PostgreSQL
kubectl exec -n flowsync flowsync-postgres-0 -- \
  pg_dump -U flowsync flowsync > flowsync-backup-$(date +%Y%m%d).sql

# Restore
kubectl exec -i -n flowsync flowsync-postgres-0 -- \
  psql -U flowsync flowsync < flowsync-backup-20250101.sql
```

### Disaster Recovery
1. **API down:** Scale up new pods, check DB/Kafka connectivity
2. **DB down:** Restore from backup, restart API pods
3. **Kafka down:** Workers operate in direct-processing mode (degraded)
4. **Full outage:** `./k8s/deploy.sh teardown` then `./k8s/deploy.sh production`

---

## 6. Alerting Thresholds (Recommended)

| Metric | Warning | Critical |
|--------|---------|----------|
| API error rate | >5% for 5min | >20% for 5min |
| API p95 latency | >2s | >5s |
| Worker error rate | >10% for 10min | >30% for 10min |
| DB connections | >80% of pool | >95% of pool |
| Kafka lag | >500 messages | >5000 messages |
| Escalation rate | >25% of messages | >50% of messages |
| Pod restarts | >3 in 1 hour | >10 in 1 hour |
| Disk usage (Postgres) | >70% | >90% |
