from notion_client import Client
from dotenv import load_dotenv
import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()
today = datetime.now().strftime("%Y-%m-%d-%H:%M")

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
TASK_TRACKER_ID = os.getenv("TASK_TRACKER_ID")
SUMMARY_PAGE_ID = os.getenv("SUMMARY_PAGE_ID")
CONTACT_PAGE_ID = os.getenv("CONTACT_PAGE_ID")
EMAIL_SENDER = os.getenv("EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASS")

notion = Client(auth=NOTION_TOKEN)

def notion_uploader(state):
    print("Notion feltöltés fut...")
    
    notion.pages.create(
        parent={"page_id": SUMMARY_PAGE_ID},
        properties={
            "title": {
                "title": [{"text": {"content": f"Meeting összefoglaló - {today}"}}]
            }
        },
        children=[
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": state["summary"]}}]
                }
            }
        ]
    )
    
    for item in state["approved_items"]:
        print(f"Feltöltés: {item}")
        notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties={
                "Task Name": {
                    "title": [{"text": {"content": item["task"]}}]
                },
                "Assignee": {
                    "rich_text": [{"text": {"content": item["assignee"]}}]
                },
                "Due Date": {
                    "date": {"start": item["deadline"]}
                },
                "Status": {
                    "status": {"name": "Not started"}
                },
                "Priority": {
                    "select": {"name": item.get("priority", "Low")}
                }
            }
        )
    
    return state

def get_emails():
    response = notion.data_sources.query(CONTACT_PAGE_ID)
    emails = {}
    for  resp in response['results']:
        emails.update({resp['properties']['Name']['title'][0]['plain_text']:resp['properties']['Email']['email']})
    
    return emails

def email_sender(state):
    emails = get_emails()

    approved_tasks = state['approved_items']

    tasks_by_person = {}
    for task in approved_tasks:
        assignee = task["assignee"]
        if assignee not in tasks_by_person:
            tasks_by_person[assignee] = []
        tasks_by_person[assignee].append(task)

    for task in approved_tasks:
        assignee = task['assignee']
        email = next((v for k, v in emails.items() if assignee.lower() in k.lower()), None)
    


