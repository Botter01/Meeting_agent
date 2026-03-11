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
    print("Email küldés fut...")
    emails = get_emails()

    approved_tasks = state['approved_items']

    tasks_by_person = {}
    for task in approved_tasks:
        assignee = task["assignee"]
        if assignee not in tasks_by_person:
            tasks_by_person[assignee] = []
        tasks_by_person[assignee].append(task)

    emails_sent = 0

    for person, tasks in tasks_by_person.items():
        email = next((v for k, v in emails.items() if person.lower() in k.lower()), None)
        
        body = f"""
                <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2F80ED;">Új feladatok</h2>
                    <p>Szia <b>{person}</b>!</p>
                    <p>A mai meeting alapján az alábbi feladatok lettek hozzád rendelve:</p>
                    
                    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                        <tr style="background-color: #2F80ED; color: white;">
                            <th style="padding: 10px; text-align: left;">Feladat</th>
                            <th style="padding: 10px; text-align: left;">Határidő</th>
                            <th style="padding: 10px; text-align: left;">Prioritás</th>
                        </tr>
                        {"".join([f'''
                        <tr style="border-bottom: 1px solid #eee;">
                            <td style="padding: 10px;">{t["task"]}</td>
                            <td style="padding: 10px;">{t["deadline"]}</td>
                            <td style="padding: 10px; color: {"red" if t["priority"] == "High" else "orange" if t["priority"] == "Medium" else "green"};">
                                {t["priority"]}
                            </td>
                        </tr>''' for t in tasks])}
                    </table>
                    
                    <h3 style="color: #2F80ED;">A meeting rövid összefoglalója:</h3>
                    <p style="background-color: #f5f5f5; padding: 15px; border-radius: 5px;">{state["summary"].replace(chr(10), "<br>")}</p>
                    <p style="color: #888; font-size: 12px;">Üdvözlettel,</p>
                    <p style="color: #888; font-size: 12px;">A Multi Millió Dolláros Meeting Agent</p>
                </body>
                </html>
                """
        
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = email
        msg["Subject"] = "Új feladatok"
        msg.attach(MIMEText(body, "html", "utf-8"))
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, email, msg.as_string())
        
        print(f"Email elküldve: {person} -> {email}")
        emails_sent += 1
    
    print(f"Összesen {emails_sent} email elküldve!")
    return state
    