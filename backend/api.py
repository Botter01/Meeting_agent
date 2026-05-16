from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import json
import os
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from dotenv import load_dotenv
from notion import notion_uploader_tool, email_sender_tool, today
from langfuse import get_client
from langfuse.langchain import CallbackHandler
from langgraph.graph import StateGraph, END
from typing import TypedDict

load_dotenv()

app = FastAPI(title="Meeting Agent API")


async def run_graph_stream(transcript):

    def send(event: str, data: dict):
        return f"data: {json.dumps({'event': event, **data})}\n\n"

    yield send("status", {"message": "Langfuse inicializálás..."})

    langfuse = get_client()
    langfuse_handler = CallbackHandler()

    if langfuse.auth_check():
        yield send("status", {"message": "Langfuse autentikáció sikeres!"})
    else:
        yield send("status", {"message": "Langfuse autentikáció sikertelen!"})

    summary_llm = ChatNVIDIA(
        model="meta/llama-3.3-70b-instruct",
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
        approved_items: list
        critic_approved: bool
        critic_feedback: str
        retry_count: int


    def summarizer(state):
        response = summary_llm.invoke(f"""
            Az alábbi meeting transzkriptet foglald össze magyarul, tömören.
            
            Fontos szabályok:
            - Ne használj felsorolást, FOLYÓ szövegként írj
            - NE másold vissza a transzkriptet!
            - Készíts a az összefoglalás felé egy résztvevő listát, a résztvevők nevével és pozíciójukkal, ha nincs pozicíója valakinek, akkor ne írj a neve mellé semmit
            - Ne sorolj fel senkit többször
            - Ne ismételj neveket
            - Adj egy címet a meetingnek
            
            Példa output:
            Cím: Új menü bemutatás                 

            Petra - Szakács
            Márk - Pincér
            Zsolt - 
            ----------------------                                                     
            "A megbeszélésen Petra elmagyarázta a csapatnak az új menü elemeit, és megkérte a Márkot hogy nagyon figyeljen a VIP vendégekre. Márk elfogadta a felkérést és elment az öltözőbe és Zsolt irigykedet."
            
            Transzkript:
            {state['transcript']}
        """)
        return {**state, "summary": response.content}

    def extractor(state):
        feedback = state.get("critic_feedback", "")
        rejected_items = state.get("action_items", [])

        if feedback:
            input_section = f"""
                Javítandó itemek:
                {json.dumps(rejected_items, ensure_ascii=False)}
                
                Hibák amiket javítani kell:
                {feedback}
            """
            transcript_section = ""
        else:
            input_section = ""
            transcript_section = f"""
                Transzkript:
                {state['transcript']}
            """

        response = summary_llm.invoke(f"""
            {"Az alábbi hibás action itemeket javítsd ki." if feedback else "Az alábbi meeting transzkriptből nyerd ki az összes action itemet."}
            
            Mai dátum: {today}
            Ha a szövegben "holnap", "jövő héten" szerepel, számold ki a pontos dátumot!

            SZIGORÚ SZABÁLYOK:
            - Csak JSON formátumban válaszolj, semmi más szöveg!
            - Minden taskhoz legyen: task, assignee, deadline, priority
            - Taskok nevébe NE rakj dátumot, NE rakj a task nevébe dátumot!
            - A deadline formátuma KIZÁRÓLAG: YYYY-MM-DD
            - Ha nincs konkrét felelős vagy deadline, hagyd ki!
            - A priority értéke KIZÁRÓLAG: High, Medium, Low
            
            Példa helyes output:
            [
                {{"task": "Bevásárlás a bulira", "assignee": "Lola", "deadline": "2026-03-15", "priority": "High"}},
                {{"task": "Takarítás", "assignee": "Anna", "deadline": "2026-03-28", "priority": "Low"}}
            ]
            
            {input_section}
            {transcript_section}
            
            JSON output:
        """)

        raw = response.content.strip().removeprefix("```json").removesuffix("```").strip()
        try:
            action_items = json.loads(raw)
        except Exception:
            action_items = rejected_items

        return {**state, "action_items": action_items}

    def critic(state):
        response = critic_llm.invoke(f"""
            Ellenőrizd az alábbi action itemeket a transzkript alapján.
                                     
            Mai dátum: {today}
            Ha a szövegben "holnap", "jövő héten" szerepel, számold ki a pontos dátumot!
            
            MINDEN itemhez add vissza:
            - az eredeti item összes mezőjét
            - egy "approved" mezőt: true ha helyes, false ha hibás
            - egy "feedback" mezőt: ha false, mi a probléma; ha true, üres string
            
            SZABÁLYOK:
            - task nevében nem lehet dátum
            - deadline KIZÁRÓLAG YYYY-MM-DD formátumú lehet
            - priority KIZÁRÓLAG High, Medium, Low lehet
            - Ne találj ki hibát ami nincs!
            
            Csak JSON formátumban válaszolj, semmi más szöveg!
            
            Transzkript:
            {state['transcript']}
            
            Action itemek:
            {json.dumps(state['action_items'], ensure_ascii=False)}
        """)

        raw = response.content.strip().removeprefix("```json").removesuffix("```").strip()
        try:
            reviewed_items = json.loads(raw)
        except Exception:
            reviewed_items = [{**item, "approved": True, "feedback": ""} for item in state["action_items"]]

        approved_items = state.get("approved_items", []) + [i for i in reviewed_items if i.get("approved")]
        rejected_items = [i for i in reviewed_items if not i.get("approved")]
        all_approved = len(rejected_items) == 0
        feedback = "\n".join([f"- {i['task']}: {i['feedback']}" for i in rejected_items])

        return {**state, "action_items": rejected_items, "approved_items": approved_items,
                "critic_approved": all_approved,
                "retry_count": state.get("retry_count", 0),
                "critic_feedback": feedback}

    def should_retry(state):
        if not state["critic_approved"] and state["retry_count"] < 3:
            return "retry"
        return "continue"

    def increment_retry(state):
        return {**state, "retry_count": state.get("retry_count", 0) + 1}

    builder = StateGraph(MeetingState)
    builder.add_node("summarizer", summarizer)
    builder.set_entry_point("summarizer")
    builder.add_node("extractor", extractor)
    builder.add_edge("summarizer", "extractor")
    builder.add_node("critic", critic)
    builder.add_edge("extractor", "critic")
    builder.add_node("increment_retry", increment_retry)
    builder.add_node("notion_uploader", notion_uploader_tool)
    builder.add_conditional_edges("critic", should_retry, {
        "retry": "increment_retry",
        "continue": "notion_uploader"
    })
    builder.add_edge("increment_retry", "extractor")
    builder.add_node("email_sender", email_sender_tool)
    builder.add_edge("notion_uploader", "email_sender")
    builder.add_edge("email_sender", END)
    graph = builder.compile().with_config({"callbacks": [langfuse_handler]})

    steps = {
        "summarizer": "Összefoglaló készítés...",
        "extractor": "Action itemek kinyerése...",
        "critic": "Critic ellenőrzés...",
        "increment_retry": "Újrapróbálkozás...",
        "notion_uploader": "Notion feltöltés...",
        "email_sender": "Emailek küldése...",
    }

    final_state = None
    async for chunk in graph.astream({
        "transcript": transcript,
        "summary": "",
        "action_items": [],
        "approved_items": [],
        "critic_approved": False,
        "critic_feedback": "",
        "retry_count": 0
    }):
        for node_name, node_state in chunk.items():
            label = steps.get(node_name, node_name)
            yield send("step", {"node": node_name, "message": label})
            final_state = node_state

    if final_state:
        yield send("done", {
            "summary": final_state.get("summary", ""),
            "approved_items": final_state.get("approved_items", []),
            "retry_count": final_state.get("retry_count", 0)
        })
    else:
        yield send("error", {"message": "Nem sikerült eredményt kapni."})


@app.post("/run")
async def run_agent(file: UploadFile = File(...)):
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Csak .txt fájlt fogadunk el.")

    content = await file.read()
    try:
        transcript = content.decode("utf-8")
    except UnicodeDecodeError:
        transcript = content.decode("latin-1")

    return StreamingResponse(
        run_graph_stream(transcript),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.get("/health")
def health():
    return {"status": "ok"}
