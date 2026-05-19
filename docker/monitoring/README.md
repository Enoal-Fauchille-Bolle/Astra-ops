# Monitoring — Prometheus + Grafana (test stack)

Stack de test locale. À terme : migrer dans K3s via ArgoCD pour bénéficier de kube-state-metrics.

## Démarrage rapide

```bash
cd docker/monitoring
docker compose up -d
```

| Service       | URL                     | Identifiants   |
| ------------- | ----------------------- | -------------- |
| Grafana       | http://localhost:3001   | admin / admin  |
| Prometheus    | http://localhost:9090   | —              |
| node-exporter | http://localhost:9100   | (métriques raw)|
| cAdvisor      | http://localhost:8082   | (métriques raw)|

## Ce qui est scrapé

- **node-exporter** → CPU, RAM, disque, réseau du host
- **cAdvisor** → métriques de chaque container Docker

## Prochaine étape — VPA data

Pour visualiser les recommendations VPA, il faut `kube-state-metrics` dans le cluster K3s.
Voir `k3s/kube-state-metrics/` (à créer) puis décommenter la section K3s dans `prometheus.yml`.

Métriques exposées par kube-state-metrics pour VPA :
- `kube_verticalpodautoscaler_status_recommendation_containerrecommendations_target`
- `kube_verticalpodautoscaler_status_recommendation_containerrecommendations_lowerbound`
- `kube_verticalpodautoscaler_status_recommendation_containerrecommendations_upperbound`
