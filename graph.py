from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from dotenv import load_dotenv
import os
import json

load_dotenv()

with open("transcript.txt", "r", encoding="utf-8") as f:
    transcript = f.read()

llm = ChatNVIDIA(
    model="meta/llama-3.2-3b-instruct",
    api_key=os.getenv("NVIDIA_API_KEY"), 
    temperature=0.2,
    top_p=0.7
)

critic_llm = ChatNVIDIA(
    model="meta/llama-3.3-70b-instruct",
    api_key=os.getenv("NVIDIA_API_KEY"), 
    temperature=0.2,
    top_p=0.7
)

class MeetingState(TypedDict):
    transcript: str
    summary: str
    action_items: list
    critic_approved: bool
    critic_feedback: str
    retry_count: int

def summarizer(state):
    print("🔵 Summarizer fut...")
    response = llm.invoke(f"""
        Az alábbi meeting transzkriptet foglald össze magyarul, tömören.
        
        Fontos szabályok:
        - Tartsd meg az összes nevet és dátumot
        - Ne használj felsorolást, folyó szövegként írj
        - NE másold vissza a transzkriptet!
        - MAXIMUM 15 mondatban foglald össze, semmi több!
        - KÖTELEZŐ minden konkrét dátumot és határidőt belerakni
        - KÖTELEZŐ minden nevet és felelőst belerakni
        
        Példa output:
        "A megbeszélésen Péter ismertette a sprint állását. Anna a főoldal redesignt péntekig befejezi, 
        a dashboardot március 28-ra vállalja. Balázs az autentikációs bugot március 18-ra javítja..."
        
        Transzkript:
        {state['transcript']}
    """)
    return {**state, "summary": response.content}


def extractor(state):
    print("🔵 Ext fut...")
    feedback = state.get("critic_feedback", "")
    feedback_section = f"""
        Az előző próbálkozásban ezek voltak a hibák, javítsd őket:
        {feedback}
    """ if feedback else ""
    response = critic_llm.invoke(f"""
        Az alábbi meeting transzkriptből nyerd ki az összes action itemet.
        
        SZIGORÚ SZABÁLYOK:
        - Csak JSON formátumban válaszolj, semmi más szöveg!
        - Minden taskhoz legyen: task, assignee, deadline
        - A deadline formátuma: YYYY-MM-DD
        - Ha olyan feladatot találsz amihez nincs a szövegben konkrét felelős vagy deadline az NEM kell
        
        Példa helyes output:
        [
            {{"task": "Bevásárlás a bulira", "assignee": "Lola", "deadline": "2026-03-15"}},
            {{"task": "Takarítás", "assignee": "Anna", "deadline": "2026-03-28"}}
        ]
        
        {feedback_section}                  

        Transzkript:
        {state['transcript']}
        
        JSON output:
    """)
    
    raw = response.content.strip().removeprefix("```json").removesuffix("```").strip()
    action_items = json.loads(raw)
    
    return {**state, "action_items": action_items}


def critic(state):
    print("🔵 Crit fut...")
    response = critic_llm.invoke(f"""
        Ellenőrizd hogy az alábbi action itemek teljesek-e a transzkript alapján.
        
        SZABÁLYOK:
        - Ha minden rendben, írj APPROVED: true-t és ne írj FEEDBACK-et
        - Ha van hiba, írj APPROVED: false-t és CSAK a hibákat sorold fel
        - A deadline KIZÁRÓLAG YYYY-MM-DD formátumú lehet, ha nem az, az hiba
        - Ne írd le mi egyezik, CSAK ami hibás vagy hiányzik!
        
        VÁLASZOD pontosan így nézzen ki:
        APPROVED: true vagy false
        FEEDBACK: [csak a hibák felsorolva, semmi más]
        
        Transzkript:
        {state['transcript']}
        
        Jelenlegi action itemek:
        {json.dumps(state['action_items'], ensure_ascii=False)}
    """)
    
    raw = response.content.strip()
    approved = "APPROVED: true" in raw
    feedback_part = raw.split("FEEDBACK:")[-1].strip() if "FEEDBACK:" in raw else ""
    print(f"📝 Critic feedback: {feedback_part}")
    
    retry_count = state.get("retry_count", 0)
    return {**state, "critic_approved": approved, "retry_count": retry_count, "critic_feedback": feedback_part} 


def should_retry(state):
    if not state["critic_approved"] and state["retry_count"] < 3:
        return "retry"
    return "continue"

def increment_retry(state):
    print(f"🔄 Retry {state.get('retry_count', 0) + 1}/3...")
    return {**state, "retry_count": state.get("retry_count", 0) + 1}


builder = StateGraph(MeetingState)
builder.add_node("summarizer", summarizer)
builder.set_entry_point("summarizer")
builder.add_node("extractor", extractor)
builder.add_edge("summarizer", "extractor")
builder.add_node("critic", critic)
builder.add_edge("extractor", "critic")
builder.add_node("increment_retry", increment_retry)
builder.add_conditional_edges("critic", should_retry, {
    "retry": "increment_retry",
    "continue": END
})
builder.add_edge("increment_retry", "extractor")
graph = builder.compile()

result = graph.invoke({
    "transcript": transcript,
    "summary": "",
    "action_items":[],
    "critic_approved": False,
    "retry_count": 0
})

print(f"Summary result: {result["summary"]}")
print(f"\n\nAction Items: {result["action_items"]}")
print(f"\n\nCritic verdict: {result["critic_approved"]}")

with open("graph.png", "wb") as f:
    f.write(graph.get_graph().draw_mermaid_png())