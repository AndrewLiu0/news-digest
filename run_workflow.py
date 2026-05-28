import uuid
from datetime import datetime
from main import agent
from dotenv import load_dotenv

load_dotenv()

def run_full_briefing():
    print("--- 🚀 Starting Full US-China Strategic Briefing Workflow 🚀 ---")
    
    # Initialize state
    initial_state = {
        "raw_items": [],
        "processed_items": [],
        "filtered_items": [],
        "additional_sources": [],
        "scraped_content": [],
        "run_timestamp": datetime.now().isoformat()
    }
    
    # Configuration for the run
    config = {"configurable": {"thread_id": f"cli-run-{uuid.uuid4().hex[:8]}"}}
    
    print("\nStarting execution... (This may take 1-2 minutes)")
    
    try:
        # We use stream to provide real-time updates in the terminal
        final_path = ""
        for output in agent.stream(initial_state, config):
            for node_name, state_update in output.items():
                print(f"✅ Node [{node_name}] completed.")
                if state_update and "final_report_path" in state_update:
                    final_path = state_update["final_report_path"]
        
        print("\n--- ✨ Workflow Complete! ✨ ---")
        if final_path:
            print(f"Check your directory for the new entry: {final_path}")
        else:
            print("The report was generated successfully.")
        
    except Exception as e:
        print(f"\n❌ Workflow failed: {e}")

if __name__ == "__main__":
    run_full_briefing()
