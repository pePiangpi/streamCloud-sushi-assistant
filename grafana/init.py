import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_USER = os.getenv("GRAFANA_ADMIN_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_ADMIN_PASSWORD", "admin")

PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_DB = os.getenv("POSTGRES_DB", "sushi")
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")

# Use Basic Auth instead of an API Key
AUTH = (GRAFANA_USER, GRAFANA_PASSWORD)

def wait_for_grafana():
    print("Waiting for Grafana to start up...")
    while True:
        try:
            response = requests.get(f"{GRAFANA_URL}/api/health")
            if response.status_code == 200:
                print("Grafana is up and running!")
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(2)

def create_or_update_datasource():
    headers = {"Content-Type": "application/json"}
    datasource_payload = {
        "name": "PostgreSQL",
        "type": "postgres",
        "url": f"{PG_HOST}:{PG_PORT}",
        "access": "proxy",
        "user": PG_USER,
        "database": PG_DB,
        "basicAuth": False,
        "isDefault": True,
        "jsonData": {"sslmode": "disable", "postgresVersion": 1500},
        "secureJsonData": {"password": PG_PASSWORD},
    }

    # Pass auth=AUTH directly
    response = requests.get(f"{GRAFANA_URL}/api/datasources/name/{datasource_payload['name']}", auth=AUTH, headers=headers)

    if response.status_code == 200:
        datasource_id = response.json()["id"]
        print(f"Updating existing datasource ID: {datasource_id}")
        response = requests.put(f"{GRAFANA_URL}/api/datasources/{datasource_id}", auth=AUTH, headers=headers, json=datasource_payload)
    else:
        print("Creating new datasource...")
        response = requests.post(f"{GRAFANA_URL}/api/datasources", auth=AUTH, headers=headers, json=datasource_payload)

    if response.status_code in [200, 201]:
        print("Datasource configured successfully!")
        return response.json().get("datasource", {}).get("uid") or response.json().get("uid")
    else:
        print(f"Failed to configure datasource: {response.text}")
        return None

def create_dashboard(datasource_uid):
    headers = {"Content-Type": "application/json"}
    
    try:
        with open("dashboard.json", "r") as f:
            dashboard_json = json.load(f)
    except FileNotFoundError:
        print("Error: dashboard.json not found in the current folder.")
        return

    # Update panels with the correct datasource UID
    for panel in dashboard_json.get("panels", []):
        if isinstance(panel.get("datasource"), dict):
            panel["datasource"]["uid"] = datasource_uid
        elif isinstance(panel.get("targets"), list):
            for target in panel["targets"]:
                if isinstance(target.get("datasource"), dict):
                    target["datasource"]["uid"] = datasource_uid

    dashboard_json.pop("id", None)
    dashboard_json.pop("uid", None)
    dashboard_json.pop("version", None)

    payload = {"dashboard": dashboard_json, "overwrite": True, "message": "Automated setup"}
    
    # Pass auth=AUTH directly
    response = requests.post(f"{GRAFANA_URL}/api/dashboards/db", auth=AUTH, headers=headers, json=payload)

    if response.status_code == 200:
        print("Dashboard imported successfully!")
    else:
        print(f"Failed to import dashboard: {response.text}")

def main():
    wait_for_grafana()
    # Skip the API key creation step entirely
    datasource_uid = create_or_update_datasource()
    if not datasource_uid:
        return
    create_dashboard(datasource_uid)

if __name__ == "__main__":
    main()