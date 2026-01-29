import streamlit as st

def display_strategy_content(res_text):
    """
    Helper to display strategy result with Tabs if it detects multi-step markers.
    """
    if not res_text: return

    # Check for Mega Log Markers
    # Auto-detect v3 markers (Final Decision) or v2 markers (Audit)
    has_audit = "--- 🔴 Round 1 Audit ---" in res_text
    has_decision = "[Final Execution Order]" in res_text or "--- 🏁 Final Exec ---" in res_text
    
    if has_audit or has_decision:
        st.caption("📋 策略全流程报告 (Full Process Report)")
        
        # Detect Version: v3 has 5 steps
        is_v3 = has_decision or ("--- 🔄 v2.0 Refined ---" in res_text and "[Refined v2.0]" not in res_text[:50])
        # Note: In v2.1, Refined was at top. In v3.0, Final Exec is at top.
        
        tabs_list = []
        if is_v3:
             tabs_list = ["🏁 定稿 (Final)", "📜 初稿 (v1.0)", "🔴 初审 (R1)", "📘 优化 (v2.0)", "⚖️ 终审 (Verifier)"]
             t5, t1, t2, t3, t4 = st.tabs(tabs_list)
        else:
             tabs_list = ["📜 初稿 (v1.0)", "🔴 初审 (R1)", "📘 优化 (v2.0)", "⚖️ 终审 (Verifier)"]
             t1, t2, t3, t4 = st.tabs(tabs_list)
             t5 = None

        s_final_exec = "N/A"
        s_v2 = "N/A"    
        s_v1 = "N/A"    
        s_audit1 = "N/A"
        s_audit2 = "N/A"
        
        try:
            # 1. Parse Step 5 (Top of v3)
            # It usually ends before "--- 📜 v1.0 Draft ---"
            # Or if v2.1, Top is v2.0
            
            # Robust extraction by splitting on markers
            # Markers mapping
            MARKER_DRAFT = "--- 📜 v1.0 Draft ---"
            MARKER_AUDIT1 = "--- 🔴 Round 1 Audit ---"
            MARKER_REFINE = "--- 🔄 v2.0 Refined ---" # in v3
            MARKER_FINAL = "--- ⚖️ Final Verdict ---"
            
            # Helper to extract between markers
            def get_between(text, start, end_list):
                if start:
                    if start not in text: return "N/A"
                    temp = text.split(start)[1]
                else:
                    temp = text # Start from beginning
                
                # Find earliest end marker
                best_end_idx = len(temp)
                for end in end_list:
                    if end in temp:
                        idx = temp.find(end)
                        if idx < best_end_idx: best_end_idx = idx
                
                return temp[:best_end_idx].strip()
            
            # Extract Sections based on known structure
            
            # Step 5: Final Exec (Top of file for v3)
            if is_v3:
                s_final_exec = get_between(res_text, None, [MARKER_DRAFT, MARKER_AUDIT1])
            
            # Step 1: Draft
            s_v1 = get_between(res_text, MARKER_DRAFT, [MARKER_AUDIT1, MARKER_REFINE])
            
            # Step 2: Audit 1
            s_audit1 = get_between(res_text, MARKER_AUDIT1, [MARKER_REFINE, MARKER_FINAL])
            
            # Step 3: Refine
            # In v3, it has explicit marker. In v2 legacy, it might be at top
            if MARKER_REFINE in res_text:
                s_v2 = get_between(res_text, MARKER_REFINE, [MARKER_FINAL])
            elif not is_v3:
                # v2 legacy: Top of file is v2
                s_v2 = get_between(res_text, None, [MARKER_DRAFT, MARKER_AUDIT1])
            
            # Step 4: Final Verdict
            s_audit2 = get_between(res_text, MARKER_FINAL, []) # To end
            
        except Exception as e:
            st.error(f"解析报告结构失败: {e}")

        # Render Tabs
        if t5:
             with t5: 
                 st.caption("Step 5: 最终执行令 (Commander Order)")
                 st.markdown(s_final_exec)
                 
        with t1: st.markdown(s_v1)
        with t2: st.markdown(s_audit1)
        with t3: st.markdown(s_v2)
        with t4: 
            st.caption("Step 4: 红军终极裁决")
            if s_audit2 != "N/A": st.markdown(s_audit2)
            else: st.info("无终审记录")
             
    else:
        # Legacy / Single Pass Display
        st.markdown(res_text)
