
import json
import os
import sys
import uuid
from datetime import datetime

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.intel_manager import load_intel_db, save_intel_db

def structure_claims_by_date():
    print("Starting intelligence restructuring...")
    db = load_intel_db()
    
    total_processed = 0
    total_merged = 0
    
    for code, claims in db.items():
        if not claims:
            continue
            
        print(f"Processing {code} ({len(claims)} items)...")
        
        # Group by date YYYY-MM-DD
        grouped = {}
        processed_count = 0
        
        for item in claims:
            # Extract date from timestamp "YYYY-MM-DD HH:MM"
            ts = item.get("timestamp", "")
            if len(ts) >= 10:
                date_key = ts[:10]
            else:
                date_key = "unknown"
                
            if date_key not in grouped:
                grouped[date_key] = []
            grouped[date_key].append(item)
            processed_count += 1
            
        print(f"  - Grouped into {len(grouped)} dates.")
        
        new_claims_list = []
        
        # Merge items for each date
        # Sort dates descending (newest first)
        sorted_dates = sorted(grouped.keys(), reverse=True)
        
        for date_key in sorted_dates:
            group_items = grouped[date_key]
            
            # Sort items by time within the day
            group_items.sort(key=lambda x: x.get("timestamp", ""))
            
            # If only one item and it's already formatted (starts with •), keep it or format it?
            # To be consistent, let's reformat everything.
            
            merged_content_lines = []
            latest_ts = ""
            
            for item in group_items:
                content = item.get("content", "").strip()
                item_ts = item.get("timestamp", "")
                if item_ts > latest_ts:
                    latest_ts = item_ts
                    
                # Extract time HH:MM
                time_str = item_ts[11:16] if len(item_ts) >= 16 else "00:00"
                
                # Check if content already has bullets (maybe already merged?)
                if content.startswith("•"):
                    merged_content_lines.append(content)
                else:
                    merged_content_lines.append(f"• [{time_str}] {content}")
            
            combined_content = "\n".join(merged_content_lines)
            
            # Create new merged item
            # Use ID of the first item? No, new ID to be clean or keep one? 
            # Let's keep ID of the newest item maybe, or new random.
            # New random is safer to avoid confusion.
            
            # Status: If ANY item is verified, mark verified? 
            # If ANY is false, mark false? 
            # Or just pending. 
            # Let's say if ALL are verified -> verified. Else pending.
            statuses = [x.get("status") for x in group_items]
            if "false_info" in statuses:
                 final_status = "disputed" # Mixed bag
            elif all(s == "verified" for s in statuses):
                 final_status = "verified"
            else:
                 final_status = "pending"
                 
            merged_item = {
                "id": str(uuid.uuid4())[:8],
                "content": combined_content,
                "timestamp": latest_ts if latest_ts else f"{date_key} 00:00",
                "source": "Merged/Metaso", 
                "status": final_status,
                "note": "Automatically merged",
                "distinct_from": [] # Reset distinct as we merged content
            }
            new_claims_list.append(merged_item)
            
            if len(group_items) > 1:
                total_merged += len(group_items) - 1
                
        db[code] = new_claims_list
        total_processed += processed_count
        
    save_intel_db(db)
    print(f" restructuring complete. Processed {total_processed} items. Merged {total_merged} redundant entries.")

if __name__ == "__main__":
    structure_claims_by_date()
