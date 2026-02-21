import os
from typing import Dict

import requests
from dotenv import load_dotenv
from flask import Flask, Response, abort, request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from jinja2 import Template
from weasyprint import HTML

app = Flask(__name__)

load_dotenv()

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
creds = service_account.Credentials.from_service_account_file(
    str(GOOGLE_CREDENTIALS_FILE), scopes=["https://www.googleapis.com/auth/drive"]
)
drive_service = build("drive", "v3", credentials=creds)


# --- Student Details PDF Generator ---
@app.route("/student-details/<int:student_id>", methods=["GET"])
def generate_sponsor_pdf(student_id):
    # Baserow API request headers
    headers = {
        "Authorization": f"Token {BASEROW_TOKEN}",
        "Content-Type": "application/json",
    }

    # Send request
    response = requests.get(
        f"{BASEROW_API_URL}{TABLE_ID}/{student_id}/?user_field_names=true",
        headers=headers,
    )

    if response.status_code != 200:
        abort(404, description="Student record not found")

    # Parse student data from API response
    student_data = response.json()

    # Read the template from the standalone HTML file
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as file:
        html_template = file.read()

    # Render template with student data and write to PDF with weasyprint
    template = Template(html_template)
    rendered_html = template.render(student=student_data)
    pdf_bytes = HTML(string=rendered_html).write_pdf()

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="student_{student_id}.pdf"'},
    )


# --- Baserow Webhook Receiver ---
@app.route("/handle-new-record", methods=["POST"])
def handle_new_record():
    try:
        payload: Dict = request.get_json()
        # print(payload)

        # Verify event type (only row creations are accepted)
        if payload.get("event_type") != "rows.created":
            return {"status": "ignored", "reason": "Not a row creation event"}

        items = payload.get("items", [])
        if not items:
            return {"status": "error", "reason": "No items in payload"}

        # Extract data from Baserow payload
        student_data: Dict = items[0]
        row_id = student_data.get("id")

        # Skip if row ID is 0 (webhook test run, do not continue)
        if row_id == 0:
            return {
                "status": "ignored",
                "reason": "Row ID invalid/Webhook test successful, your pick.",
            }

        student_name = student_data.get("Full Name", "Unknown")
        table_id = payload.get("table_id")

        # Create the Google Drive Folder
        folder_name = f"{row_id} - {student_name}"
        folder_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [GOOGLE_DRIVE_PARENT_FOLDER_ID],
        }

        # Execute folder creation
        folder = (
            drive_service.files()
            .create(body=folder_metadata, fields="id, webViewLink")
            .execute()
        )
        folder_link = folder.get("webViewLink")

        # Form profile link pointing to weasyprint endpoint
        profile_link = f"{API_ENDPOINT}/student-details/{row_id}"

        # Update the Baserow Record with the newly created Drive link
        headers = {
            "Authorization": f"Token {BASEROW_TOKEN}",
            "Content-Type": "application/json",
        }

        update_url = f"{BASEROW_API_URL}{table_id}/{row_id}/?user_field_names=true"
        update_data = {"Google Drive Link": folder_link, "Profile": profile_link}

        response = requests.patch(update_url, headers=headers, json=update_data)
        response.raise_for_status()

        return {"status": "success", "folder_name": folder_name, "link_added": True}
    except Exception as e:
        # TODO: send email to myself later for notification
        return {"status": "error", "reason": str(e)}
