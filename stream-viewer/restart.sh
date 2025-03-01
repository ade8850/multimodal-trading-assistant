#!/bin/bash
# Script per riavviare i container docker-compose con ricostruzione completa

set -e  # Esci immediatamente se un comando restituisce un codice di errore

echo "=== Fermando i container in esecuzione ==="
docker-compose down

echo "=== Rimuovendo eventuali immagini orfane ==="
docker image prune -f

echo "=== Ricostruendo le immagini senza cache ==="
docker-compose build --no-cache

echo "=== Avviando i container ==="
docker-compose up -d

echo "=== Stato dei container ==="
docker-compose ps

echo "=== Log del backend (ultimi 10 righe) ==="
sleep 2  # Attendi che i container siano avviati
docker-compose logs --tail=10 backend

echo "=== Stream Viewer pronto su http://localhost:3000 ==="