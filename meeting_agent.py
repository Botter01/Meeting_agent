from notion_client import Client
from dotenv import load_dotenv
import os

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
TASK_TRACKER_ID = os.getenv("TASK_TRACKER_ID")
SUMMARY_PAGE_ID = os.getenv("SUMMARY_PAGE_ID")

notion = Client(auth=NOTION_TOKEN)

def notion_uploader(state):
    print("🔵 Notion feltöltés fut...")
    
    notion.pages.create(
        parent={"page_id": SUMMARY_PAGE_ID},
        properties={
            "title": {
                "title": [{"text": {"content": "Meeting összefoglaló"}}]
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