# Ummu Aytam (Marayu) Foundation - Scholarship Database Integration Service

## About the Foundation
The **Ummu Aytam (Marayu) Foundation** is a Nigerian-owned and based NGO dedicated to addressing the needs of orphans and less privileged children. Through the delivery of customized educational and vocational programs, the foundation actively works to uplift and empower vulnerable children within the community. 

A core initiative of the foundation is its **Scholarship Program**, which connects sponsors with children in need, facilitating the funding of their education from their current academic stage through to university graduation.

## Support the Foundation
The Ummu Aytam (Marayu) Foundation relies on the generosity of sponsors and donors to keep our educational and vocational programs running. If you are interested in sponsoring a child's education or supporting our mission to uplift orphans and less privileged children, please get in touch or contribute directly.

### Bank Account Details
* **Account Name:** Ummu Aytam Marayu Foundation
* **Account Number:** 0520160847
* **Bank Name:** GT BANK

### Contact Information
* **Email:** ummuaytam@gmail.com
* **Hotline:** 07030543334, 08023338768, 08030735066
* **Address:** No. 168, College Road, Unguwan Dosa, Kaduna

## System Architecture Overview
To manage the administrative overhead of the Scholarship Program, the foundation utilizes a centralized Baserow database. This repository houses the custom **API & Webhook Service** that acts as the bridge between the Baserow database, Google Drive, and external sponsors. 


The service is built with **[FastAPI / Flask]** and automates heavy data-handling tasks to ensure a seamless experience for both the foundation's administrative team and the educational sponsors.

## Core Features

### 1. Automated Google Drive Provisioning (Webhook)
When a new student is onboarded into the scholarship program and their record is created in the Baserow database, Baserow fires a webhook payload to this service. 
* The application intercepts the payload and parses the student's unique ID and name.
* It securely authenticates with the Google Drive API via a headless Service Account.
* A dedicated, uniquely named folder is automatically generated in the foundation's master Drive.
* The service then updates the student's Baserow record with the direct link to their new Drive folder, ensuring all future documents (report cards, receipts, etc.) are neatly organized without manual data entry.

### 2. Dynamic Student Profile Generation (API)
To provide sponsors with a professional overview of the student they are supporting, this service features an endpoint that generates highly formatted, printable A4 PDF profiles on the fly.
* The application queries the Baserow REST API for the specific student's latest data (including demographic information, medical history, academic standing, and photographs).
* The JSON data is injected into a custom HTML/Jinja2 template.
* Using `WeasyPrint`, the HTML is rendered directly into a PDF in-memory and served instantly to the browser.
* This ensures sponsors always see real-time, perfectly formatted data without the foundation needing to manually design or update PDF files.

## Tech Stack
* **Framework:** [FastAPI / Flask]
* **PDF Rendering:** WeasyPrint, Jinja2
* **External Integrations:** Baserow REST API, Google Drive API v3
* **Authentication:** Google OAuth2 (Service Account)

## Notice
This repository is public for transparency and portfolio purposes. However, it is a purpose-built internal tool customized specifically for the Ummu Aytam (Marayu) Foundation's data schema and operational workflow. It does not include execution instructions, deployment configurations, or environment variables, and it is not intended to be cloned or deployed by external users.
