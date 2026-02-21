import logging
import os
from typing import Dict

import google_auth_httplib2
import httplib2
import requests
from dotenv import load_dotenv
from flask import Flask, Response, abort, request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from jinja2 import Template
from weasyprint import HTML

# --- LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

# --- CONFIGURATION ---
BASEROW_API_URL = os.getenv("BASEROW_API_URL")
BASEROW_TOKEN = os.getenv("BASEROW_TOKEN")
TABLE_ID = os.getenv("TABLE_ID")

GOOGLE_CREDENTIALS_FILE = os.path.join(BASE_DIR, "service_account.json")
GOOGLE_DRIVE_PARENT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID")

TEMPLATE_FILE = os.path.join(BASE_DIR, "profile_template.html")
API_ENDPOINT = os.getenv(
    "API_ENDPOINT", "https://localhost:8000"
)  # Defaults to localhost when testing

# Set up Google Drive Client
try:
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE, scopes=["https://www.googleapis.com/auth/drive"]
    )

    # Explicitly define the PythonAnywhere proxy
    proxy_info = httplib2.ProxyInfo(
        proxy_type=httplib2.socks.PROXY_TYPE_HTTP,
        proxy_host="proxy.server",
        proxy_port=3128,
    )

    # Attach the proxy to an httplib2 instance
    http_instance = httplib2.Http(proxy_info=proxy_info)

    # Bind your credentials to the proxied http instance
    authed_http = google_auth_httplib2.AuthorizedHttp(creds, http=http_instance)

    # Pass the proxied http to the build function
    drive_service = build("drive", "v3", http=authed_http)

    logger.info("Google Drive service initialized successfully with Proxy routing.")
except Exception as e:
    logger.error(f"Failed to initialize Google Drive service: {e}", exc_info=True)


# --- Student Details PDF Generator ---
@app.route("/student-details/<int:student_id>", methods=["GET"])
def generate_sponsor_pdf(student_id):
    logger.info(f"PDF generation requested for student ID: {student_id}")

    headers = {
        "Authorization": f"Token {BASEROW_TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.get(
        f"{BASEROW_API_URL}{TABLE_ID}/{student_id}/?user_field_names=true",
        headers=headers,
    )

    if response.status_code != 200:
        logger.warning(
            f"Failed to fetch student {student_id} from Baserow. Status: {response.status_code}"
        )
        abort(404, description="Student record not found")

    student_data = response.json()

    with open(TEMPLATE_FILE, "r", encoding="utf-8") as file:
        html_template = file.read()

    template = Template(html_template)
    rendered_html = template.render(student=student_data)
    pdf_bytes = HTML(string=rendered_html).write_pdf()

    logger.info(f"Successfully generated PDF for student ID: {student_id}")
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{student_data.get("Full Name", "Student")}_{student_id}.pdf"'
        },
    )


# --- Baserow Webhook Receiver ---
@app.route("/handle-new-record", methods=["POST"])
def handle_new_record():
    logger.info("--- Incoming Webhook Triggered ---")
    try:
        payload: Dict = request.get_json()

        # Verify event type
        if payload.get("event_type") != "rows.created":
            logger.info(f"Ignored webhook. Event type was: {payload.get('event_type')}")
            return {"status": "ignored", "reason": "Not a row creation event"}

        items = payload.get("items", [])
        if not items:
            logger.warning("Webhook payload contained no items.")
            return {"status": "error", "reason": "No items in payload"}

        # Extract data
        student_data: Dict = items[0]
        row_id = student_data.get("id")

        if row_id == 0:
            logger.info("Webhook test payload (ID 0) received and ignored.")
            return {
                "status": "ignored",
                "reason": "Row ID invalid/Webhook test successful, your pick.",
            }

        student_name = student_data.get("Full Name", "Unknown")
        table_id = payload.get("table_id")

        logger.info(f"Processing new record: {student_name} (ID: {row_id})")

        # Create the Google Drive Folder
        logger.info(f"Attempting to create Google Drive folder for {student_name}...")
        folder_name = f"{row_id} - {student_name}"
        folder_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [GOOGLE_DRIVE_PARENT_FOLDER_ID],
        }

        folder = (
            drive_service.files()
            .create(body=folder_metadata, fields="id, webViewLink")
            .execute()
        )
        folder_id = folder.get("id")
        folder_link = folder.get("webViewLink")
        logger.info(f"Folder created successfully. Link: {folder_link}")

        logger.info("Updating folder permissions to public read-only...")
        permission_metadata = {"type": "anyone", "role": "reader"}
        drive_service.permissions().create(
            fileId=folder_id, body=permission_metadata, fields="id"
        ).execute()
        logger.info("Permissions updated successfully.")

        # Form profile link
        profile_link = f"{API_ENDPOINT}/student-details/{row_id}"

        # Update Baserow
        logger.info(f"Attempting to update Baserow table {table_id}, row {row_id}...")
        headers = {
            "Authorization": f"Token {BASEROW_TOKEN}",
            "Content-Type": "application/json",
        }

        update_url = f"{BASEROW_API_URL}{table_id}/{row_id}/?user_field_names=true"
        update_data = {"Google Drive Link": folder_link, "Profile": profile_link}

        response = requests.patch(update_url, headers=headers, json=update_data)

        # If Baserow rejects the update, log exactly why before crashing
        if not response.ok:
            logger.error(
                f"Baserow Update Failed! Status: {response.status_code}, Response Data: {response.text}"
            )

        response.raise_for_status()

        logger.info(f"--- Successfully processed and updated student {row_id} ---")
        return {"status": "success", "folder_name": folder_name, "link_added": True}

    except Exception as e:
        # exc_info=True prints the full traceback to the logs so you can find the exact line
        logger.error(f"CRITICAL ERROR in webhook: {str(e)}", exc_info=True)
        return {"status": "error", "reason": str(e)}
