
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import get_position, get_allocation, get_history

def verify():
    print("Verifying database access via utils.config...")
    
    # Test read
    pos = get_position("600076")
    print(f"Position 600076: {pos}")
    assert pos.get("shares") == 26000, "Shares mismatch for 600076"
    
    alloc = get_allocation("600076")
    print(f"Allocation 600076: {alloc}")
    assert alloc == 150000.0, "Allocation mismatch"
    
    hist = get_history("600076")
    print(f"History count 600076: {len(hist)}")
    assert len(hist) > 0, "History empty"
    
    print("Verification Passed!")

if __name__ == "__main__":
    verify()
