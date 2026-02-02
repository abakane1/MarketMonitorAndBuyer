# -*- coding: utf-8 -*-
import streamlit as st
import time
from utils.strategy import analyze_volume_profile_strategy
from utils.storage import get_volume_profile, get_latest_production_log, save_production_log, load_production_log, delete_production_log
from utils.ai_parser import extract_bracket_content
from utils.config import load_config, get_allocation, set_allocation
from utils.monitor_logger import log_ai_heartbeat
from utils.database import db_get_history

import pandas as pd

import re
import datetime

def render_strategy_section(code: str, name: str, price: float, shares_held: int, avg_cost: float, total_capital: float, risk_pct: float, proximity_pct: float, pre_close: float = 0.0):
    """
    渲染策略分析区域 (算法 + AI)
    """
    
    # 1. Capital Allocation UI
    prompts = load_config().get("prompts", {}) # Load Prompts Early for Refinement Logic
    current_alloc = get_allocation(code)
    eff_capital = total_capital # Default
    
    with st.expander("⚙️ 资金配置 (Capital Allocation)", expanded=False):
        new_alloc = st.number_input(
            f"本股资金限额 (0表示使用总资金)",
            value=float(current_alloc),
            min_value=0.0,
            step=10000.0,
            format="%.0f",
            key=f"alloc_{code}",
            help="限制该股票的最大持仓市值。策略将利用此数值计算建议仓位。"
        )
        if st.button("保存限额", key=f"save_{code}"):
            set_allocation(code, new_alloc)
            st.success(f"已保存! 本股资金限额: {new_alloc}")
            time.sleep(0.5)
            st.rerun()
            
        st.markdown("---")
        # Base Position UI
        from utils.config import set_base_shares
        from utils.database import db_get_position
        # Use DB
        curr_pos = db_get_position(code)
        curr_base = curr_pos.get("base_shares", 0)
        
        new_base = st.number_input(
            f"🔒 底仓锁定 (Base Position)",
            value=int(curr_base),
            min_value=0,
            step=100,
            key=f"base_in_{code}",
            help="设置长期持有的底仓数量。AI 将被禁止卖出这部分筹码。"
        )
        if st.button("保存底仓", key=f"save_base_{code}"):
            set_base_shares(code, new_base)
            st.success(f"已锁定底仓: {new_base} 股")
            time.sleep(0.5)
            st.rerun()
            
        # [NEW] Dynamic Capital Allocation Logic
        from utils.config import get_stock_profit
        total_profit = get_stock_profit(code, price)
        
        real_alloc = float(current_alloc)
        
        # If allocation is 0 (unlimited), effectively it uses Total Capital
        # But here we want to solve "I set 200k limit but made 20k profit, allow 220k".
        if real_alloc > 0:
            effective_limit = real_alloc + total_profit
            # If profit is negative, effective limit reduces (conservative)
            # If profit is positive, effective limit increases (reinvestment)
            
            st.info(f"💰 有效资金限额: {effective_limit:,.0f} 元")
            st.caption(f"计算公式: 基础限额 {real_alloc:,.0f} + 累计盈亏 {total_profit:+,.0f}")
            
            # Override eff_capital for strategy
            eff_capital = effective_limit
        else:
            eff_capital = total_capital # Fallback to total if no specific limit
            
    # Calculate Strategy (Background calculation for AI Context)
    vol_profile_for_strat, vol_meta = get_volume_profile(code)
    strat_res = analyze_volume_profile_strategy(
        price, 
        vol_profile_for_strat, 
        eff_capital, 
        risk_pct, 
        current_shares=shares_held,
        proximity_threshold=proximity_pct
    )
    
    # --- Algorithm Section REMOVED ---


    # --- AI Section (Review / Pre-market) ---
    with st.expander("🧠 复盘与预判 (Review & Prediction)", expanded=True):
        # [UX] Toast Feedback
        toast_key = f"toast_msg_{code}"
        if toast_key in st.session_state:
            msg = st.session_state[toast_key]
            st.toast(msg, icon="✅")
            st.success(msg) # Persistent anchor
            del st.session_state[toast_key]

        st.markdown("---")
        
        # Check for Pending Draft
        pending_key = f"pending_ai_result_{code}"
        ai_strat_log = None
        
        if pending_key in st.session_state:
            # We have a draft, show it!
            ai_strat_log = st.session_state[pending_key]
            st.warning("⚠️ 新生成策略待确认 (Draft Mode)")
            
            # [Display Strategy Result]
            from components.strategy_display_helper import display_strategy_content
            display_strategy_content(ai_strat_log.get('result', ''))
            
            # [Display Reasoning]
            if ai_strat_log.get('reasoning'):
                with st.expander("💭 查看 AI 思考过程 (Reasoning)", expanded=False):
                    st.markdown(ai_strat_log['reasoning'])
            
            # --- Display Gemini Audit (Red Team) ---
            # --- Display Qwen Audit (Red Team) ---
            # --- STAGE 2: RED TEAM AUDIT ---
            if ai_strat_log.get('audit'):
                # [Display Audit Result]
                with st.expander(f"🔴 {ai_strat_log.get('red_model', 'Qwen')} 风控官审查报告 (Red Team Audit)", expanded=True):
                    st.markdown(ai_strat_log['audit'])
                    
                    # --- STAGE 3: REFINEMENT ---
                    if not ai_strat_log.get('is_refined'):
                        st.markdown("---")
                        
                        # [Refinement Workflow]
                        refine_preview_key = f"refine_preview_{code}"
                        
                        # A. Trigger Button
                        if refine_preview_key not in st.session_state:
                            if st.button("🔄 准备优化策略 (Prepare Refinement)", key=f"btn_prep_refine_{code}"):
                                with st.spinner("🤖 正在构建优化指令..."):
                                    blue_model = ai_strat_log.get('blue_model', 'DeepSeek')
                                    
                                    # Build Prompt
                                    sys_p, user_p = build_refinement_prompt(
                                        ai_strat_log.get('raw_context', ''), 
                                        ai_strat_log['result'], 
                                        ai_strat_log['audit'], 
                                        prompts
                                    )
                                    
                                    st.session_state[refine_preview_key] = {
                                        'sys_p': sys_p,
                                        'user_p': user_p,
                                        'model': blue_model
                                    }
                                    st.rerun()
                        
                        # B. Preview & Confirm
                        else:
                            r_data = st.session_state[refine_preview_key]
                            st.info(f"📝 确认优化指令 ({r_data['model']})")
                            
                            new_sys = st.text_area("System Prompt (Refine)", value=r_data['sys_p'], key=f"sys_r_{code}", height=100)
                            new_user = st.text_area("User Instruction (Refine)", value=r_data['user_p'], key=f"user_r_{code}", height=200)
                            
                            rc1, rc2 = st.columns([1, 1])
                            with rc1:
                                if st.button("🚀 确认执行优化 (Run Refinement)", key=f"btn_run_refine_{code}", type="primary"):
                                    # Get Key
                                    b_key = st.session_state.get("input_apikey", "")
                                    if r_data['model'] == "Qwen":
                                        b_key = st.session_state.get("input_qwen", "")
                                        if not b_key: b_key = load_config().get("settings", {}).get("qwen_api_key", "")
                                    
                                    if not b_key:
                                        st.error(f"Missing Key for {r_data['model']}")
                                    else:
                                        with st.spinner(f"♻️ {r_data['model']} 正在根据审查意见优化策略..."):
                                            from utils.ai_advisor import call_ai_model
                                            
                                            v2_plan, v2_reason = call_ai_model(
                                                r_data['model'].lower(), b_key, new_sys, new_user
                                            )
                                            
                                            if "Error" in v2_plan:
                                                st.error(v2_plan)
                                            else:
                                                # Update Session State
                                                st.session_state[pending_key]['result'] = f"{v2_plan}\n\n[Refined v2.0]"
                                                st.session_state[pending_key]['reasoning'] = f"{ai_strat_log.get('reasoning','')}\n\n--- 🔄 Refinement Logic ---\n{v2_reason}"
                                                st.session_state[pending_key]['is_refined'] = True
                                                
                                                # Capture Prompt
                                                if 'prompts_history' not in st.session_state[pending_key]:
                                                    st.session_state[pending_key]['prompts_history'] = {}
                                                st.session_state[pending_key]['prompts_history']['refine_sys'] = new_sys
                                                st.session_state[pending_key]['prompts_history']['refine_user'] = new_user
                                                
                                                del st.session_state[refine_preview_key]
                                                st.rerun()
                            with rc2:
                                if st.button("❌ 取消优化", key=f"btn_cancel_refine_{code}"):
                                    del st.session_state[refine_preview_key]
                                    st.rerun()
                    
                    # --- STAGE 4: FINAL VERDICT (Audit Round 2) ---
                    # Only show if Refined AND no Final Audit yet
                    if ai_strat_log.get('is_refined'):
                         st.markdown("---")
                         final_audit_key = f"final_audit_preview_{code}"
                         
                         if not ai_strat_log.get('final_audit'):
                             # [Trigger Final Audit]
                             red_model = ai_strat_log.get('red_model', 'Qwen')
                             st.info(f"⚖️ 等待红军 ({red_model}) 终极裁决 (Final Verdict)...")
                             
                             if final_audit_key not in st.session_state:
                                 if st.button(f"⚖️ 准备终审 (Prepare Final Verdict)", key=f"btn_prep_final_{code}"):
                                     with st.spinner("🤖 正在构建终审指令..."):
                                         from utils.ai_advisor import build_red_team_prompt
                                         # Context is V2 Plan
                                         bg_info = ai_strat_log.get('raw_context') or ai_strat_log.get('prompt', '')
                                         audit_ctx = {
                                             "code": code,
                                             "name": name,
                                             "price": price,
                                             "daily_stats": bg_info,  
                                             "deepseek_plan": ai_strat_log['result'] # This is V2 now
                                         }
                                         sys_p, user_p = build_red_team_prompt(audit_ctx, prompts, is_final_round=True)
                                         
                                         st.session_state[final_audit_key] = {
                                             'sys_p': sys_p, 'user_p': user_p, 'model': red_model
                                         }
                                         st.rerun()
                             else:
                                 # Preview
                                 fa_data = st.session_state[final_audit_key]
                                 st.warning(f"📝 确认终审指令 ({fa_data['model']})")
                                 f_sys = st.text_area("System (Final)", value=fa_data['sys_p'], key=f"sys_fa_{code}", height=100)
                                 f_usr = st.text_area("User (Final)", value=fa_data['user_p'], key=f"usr_fa_{code}", height=200)
                                 
                                 fc1, fc2 = st.columns(2)
                                 with fc1:
                                     if st.button("🚀 执行终审 (Run Final Verdict)", key=f"btn_run_final_{code}", type="primary"):
                                         # Key Check
                                         r_key = load_config().get("settings", {}).get("qwen_api_key", "")
                                         if fa_data['model'] == "DeepSeek": r_key = st.session_state.get("input_apikey", "")
                                         elif fa_data['model'] == "Qwen": r_key = st.session_state.get("input_qwen", "") or r_key

                                         if not r_key: st.error("Missing Key"); st.stop()
                                         
                                         with st.spinner(f"⚖️ {fa_data['model']} 正在宣判..."):
                                             from utils.ai_advisor import call_ai_model
                                             fa_res, _ = call_ai_model(fa_data['model'].lower(), r_key, f_sys, f_usr)
                                             if "Error" in fa_res: st.error(fa_res)
                                             else:
                                                 st.session_state[pending_key]['final_audit'] = fa_res
                                                 
                                                 # Capture Prompt
                                                 if 'prompts_history' not in st.session_state[pending_key]:
                                                     st.session_state[pending_key]['prompts_history'] = {}
                                                 st.session_state[pending_key]['prompts_history']['final_sys'] = f_sys
                                                 st.session_state[pending_key]['prompts_history']['final_user'] = f_usr
                                                 
                                                 del st.session_state[final_audit_key]
                                                 st.rerun()
                                 with fc2:
                                     if st.button("❌ 取消终审", key=f"btn_ccl_final_{code}"):
                                         del st.session_state[final_audit_key]
                                         st.rerun()
                                         
                         else:
                             # Display Final Audit
                             with st.expander(f"⚖️ {ai_strat_log.get('red_model','Qwen')} 终极裁决 (Final Verdict)", expanded=True):
                                 st.markdown(ai_strat_log['final_audit'])
                                
                             # --- STAGE 5: FINAL DECISION (Blue Team) ---
                             st.markdown("---")
                             final_exec_key = f"final_exec_preview_{code}"
                             
                             if not ai_strat_log.get('final_exec'):
                                 # Trigger Step 5
                                 blue_model = ai_strat_log.get('blue_model', 'DeepSeek')
                                 st.info(f"🏁 等待蓝军 ({blue_model}) 签署最终执行令...")
                                 
                                 if final_exec_key not in st.session_state:
                                      if st.button("🏁 准备最终执行令 (Prepare Execution)", key=f"btn_prep_exec_{code}"):
                                          with st.spinner("🤖 正在拟定执行令..."):
                                              from utils.ai_advisor import build_final_decision_prompt
                                              sys_fin, user_fin = build_final_decision_prompt(ai_strat_log['final_audit'], prompts)
                                              
                                              st.session_state[final_exec_key] = {
                                                  'sys_p': sys_fin,
                                                  'user_p': user_fin,
                                                  'model': blue_model
                                              }
                                              st.rerun()
                                 else:
                                      # Preview
                                      fe_data = st.session_state[final_exec_key]
                                      st.warning(f"📝 确认执行令指令 ({fe_data['model']})")
                                      fe_sys = st.text_area("System (Exec)", value=fe_data['sys_p'], key=f"sys_fe_{code}", height=100)
                                      fe_usr = st.text_area("User (Exec)", value=fe_data['user_p'], key=f"usr_fe_{code}", height=200) 
                                      
                                      ec1, ec2 = st.columns(2)
                                      with ec1:
                                          if st.button("🚀 签署执行令 (Sign Order)", key=f"btn_sign_exec_{code}", type="primary"):
                                               # Key Check
                                               b_key = st.session_state.get("input_apikey", "")
                                               if fe_data['model'] == "Qwen": 
                                                   b_key = st.session_state.get("input_qwen", "") or load_config().get("settings", {}).get("qwen_api_key", "")
                                               
                                               if not b_key: st.error("Missing Key"); st.stop()
                                               
                                               with st.spinner(f"🏁 {fe_data['model']} 正在签署..."):
                                                   from utils.ai_advisor import call_ai_model
                                                   exec_res, exec_reason = call_ai_model(fe_data['model'].lower(), b_key, fe_sys, fe_usr)
                                                   
                                                   if "Error" in exec_res: st.error(exec_res)
                                                   else:
                                                       st.session_state[pending_key]['final_exec'] = exec_res
                                                       
                                                       # RECONSTRUCT FULL RESULT for Parser
                                                       c_v2_full = st.session_state[pending_key].get('result', '')
                                                       c_audit1 = st.session_state[pending_key].get('audit', '')
                                                       c_audit2 = st.session_state[pending_key].get('final_audit', '')
                                                       
                                                       full_res = f"{exec_res}\n\n[Final Execution Order]"
                                                       full_res += f"\n\n--- 🔄 v2.0 Refined ---\n{c_v2_full}"
                                                       if c_audit2: full_res += f"\n\n--- ⚖️ Final Verdict ---\n{c_audit2}"
                                                       if c_audit1: full_res += f"\n\n--- 🔴 Round 1 Audit ---\n{c_audit1}"
                                                       
                                                       st.session_state[pending_key]['result'] = full_res
                                                       
                                                       old_r = st.session_state[pending_key].get('reasoning', '')
                                                       st.session_state[pending_key]['reasoning'] = f"{old_r}\n\n### [Final Decision]\n{exec_reason}"
                                                       
                                                       if 'prompts_history' not in st.session_state[pending_key]:
                                                             st.session_state[pending_key]['prompts_history'] = {}
                                                       st.session_state[pending_key]['prompts_history']['decision_sys'] = fe_sys
                                                       st.session_state[pending_key]['prompts_history']['decision_user'] = fe_usr
                                                       
                                                       del st.session_state[final_exec_key]
                                                       st.rerun()

                                      with ec2:
                                          if st.button("❌ 取消", key=f"btn_ccl_exec_{code}"):
                                              del st.session_state[final_exec_key]
                                              st.rerun()


            elif ai_strat_log.get('red_model') and ai_strat_log.get('red_model') != "None":
                # [Audit Missing -> Trigger Audit Workflow]
                red_model = ai_strat_log.get('red_model')
                audit_preview_key = f"audit_preview_{code}"
                
                st.info(f"🔴 等待红军 ({red_model}) 介入审查...")
                
                # A. Trigger Button
                if audit_preview_key not in st.session_state:
                   if st.button(f"🛡️ 准备红军审查 (Prepare {red_model} Audit)", key=f"btn_prep_audit_{code}"):
                       with st.spinner("🤖 正在构建审查指令..."):
                            from utils.ai_advisor import build_red_team_prompt
                            
                            # Prepare Context
                            # Use original raw prompt (contains News, Indicators, Fund Flow) as background
                            bg_info = ai_strat_log.get('raw_context') or ai_strat_log.get('prompt', 'No Data Available')
                            
                            audit_ctx = {
                                "code": code,
                                "name": name,
                                "price": price,
                                "daily_stats": bg_info,  # Inject FULL Context here
                                "deepseek_plan": ai_strat_log['result']
                            }
                            
                            sys_p, user_p = build_red_team_prompt(audit_ctx, prompts, is_final_round=False)
                            
                            st.session_state[audit_preview_key] = {
                                'sys_p': sys_p,
                                'user_p': user_p,
                                'model': red_model
                            }
                            st.rerun()
                
                # B. Preview & Confirm
                else:
                    a_data = st.session_state[audit_preview_key]
                    st.warning(f"📝 确认审查指令 ({a_data['model']})")
                    
                    new_sys = st.text_area("System Prompt (Audit)", value=a_data['sys_p'], key=f"sys_a_{code}", height=100)
                    new_user = st.text_area("User Instruction (Audit)", value=a_data['user_p'], key=f"user_a_{code}", height=200)
                    
                    ac1, ac2 = st.columns([1, 1])
                    with ac1:
                         if st.button(f"🚀 确认执行审查 (Run Audit)", key=f"btn_run_audit_{code}", type="primary"):
                             # Get Key
                             r_key = st.session_state.get("input_apikey", "") # Default to DS key check
                             if a_data['model'] == "Qwen":
                                 r_key = st.session_state.get("input_qwen", "")
                                 if not r_key: r_key = load_config().get("settings", {}).get("qwen_api_key", "")
                             elif a_data['model'] == "DeepSeek":
                                 r_key = st.session_state.get("input_apikey", "")
                             
                             if not r_key:
                                 st.error(f"Missing Key for {a_data['model']}")
                             else:
                                 with st.spinner(f"🔴 {a_data['model']} 正在进行风控审查..."):
                                     from utils.ai_advisor import call_ai_model
                                     
                                     audit_content, _ = call_ai_model(
                                         a_data['model'].lower(), r_key, new_sys, new_user
                                     )
                                     
                                     if "Error" in audit_content:
                                         st.error(audit_content)
                                     else:
                                         # Update Session State
                                         st.session_state[pending_key]['audit'] = audit_content
                                         
                                         # Capture Prompt
                                         if 'prompts_history' not in st.session_state[pending_key]:
                                             st.session_state[pending_key]['prompts_history'] = {}
                                         st.session_state[pending_key]['prompts_history']['audit1_sys'] = new_sys
                                         st.session_state[pending_key]['prompts_history']['audit1_user'] = new_user
                                         
                                         del st.session_state[audit_preview_key]
                                         st.rerun()
                    with ac2:
                        if st.button("❌ 跳过审查", key=f"btn_skip_audit_{code}"):
                            del st.session_state[audit_preview_key]
                            # Mark audit as skipped to stop pestering? Or just leave it None and allow user to Confirm Draft directly.
                            # Let's set it to "Skipped" to hide the prompt
                            st.session_state[pending_key]['audit'] = "【用户手动跳过审查】" 
                            st.rerun()
            
            # Action Bar
            col_conf, col_disc = st.columns(2)
            with col_conf:
                if st.button("✅ 确认入库 (Confirm)", key=f"btn_confirm_{code}", use_container_width=True):
                    # Save to disk
                    # 1. Formatting Full Result
                    full_result = f"{ai_strat_log.get('tag', '')} {ai_strat_log['result']}"
                    
                    if ai_strat_log.get('audit'):
                        full_result += f"\n\n--- 🔴 Round 1 Audit ---\n{ai_strat_log['audit']}"
                    
                    if ai_strat_log.get('final_audit'):
                        full_result += f"\n\n--- ⚖️ Final Verdict ---\n{ai_strat_log['final_audit']}"
                    
                    # 2. Formatting Full Prompt History
                    full_prompt_log = ai_strat_log['prompt'] # Default fallback
                    
                    ph = ai_strat_log.get('prompts_history', {})
                    if ph:
                        full_prompt_log = f"""
# 🧠 Round 1: Strategy Draft
## System
{ph.get('draft_sys', '')}
## User
{ph.get('draft_user', '')}

---
# 🛡️ Round 1: Red Audit
## System
{ph.get('audit1_sys', '')}
## User
{ph.get('audit1_user', '')}

---
# 🔄 Round 2: Refinement
## System
{ph.get('refine_sys', '')}
## User
{ph.get('refine_user', '')}

---
# ⚖️ Final Verdict
## System
{ph.get('final_sys', '')}
## User
{ph.get('final_user', '')}
"""
                    save_production_log(
                        code, 
                        full_prompt_log, 
                        full_result, 
                        ai_strat_log['reasoning'],
                        model=ai_strat_log.get('model', 'DeepSeek')
                    )
                    # Clear draft
                    del st.session_state[pending_key]
                    st.success("策略已入库！")
                    time.sleep(0.5)
                    st.rerun()
                    
            with col_disc:
                if st.button("🗑️ 放弃 (Discard)", key=f"btn_discard_{code}", use_container_width=True):
                    # Clear draft
                    del st.session_state[pending_key]
                    st.info("策略已放弃")
                    time.sleep(0.5)
                    st.rerun()
            
            st.markdown("---")
        
        # If no draft, load from disk
        if not ai_strat_log:
             ai_strat_log = get_latest_production_log(code)
        
        # DeepSeek Config
        settings = load_config().get("settings", {})
        deepseek_api_key = st.session_state.get("input_apikey", "")
        
        if ai_strat_log:
            content = ai_strat_log['result']
            reasoning = ai_strat_log.get('reasoning', '')
            ts = ai_strat_log['timestamp'][5:16]
            st.caption(f"📅 最后生成: {ts}")
            
            # --- Simple Parser (Reuse original logic) ---
            ai_signal = "N/A"
            pos_txt = "N/A"
            stop_loss_txt = "N/A"
            entry_txt = "N/A"
            take_profit_txt = "N/A"

            block_match = re.search(r"【决策摘要】(.*)", content, re.DOTALL)
            if block_match:
                block_content = block_match.group(1)
                s_match = re.search(r"方向:\s*(\[)?(.*?)(])?\n", block_content)
                if not s_match: s_match = re.search(r"方向:\s*(\[)?(.*?)(])?$", block_content, re.MULTILINE)
                if s_match: ai_signal = s_match.group(2).replace("[","").replace("]","").strip()
                
                e_match = re.search(r"建议价格:\s*(\[)?(.*?)(])?\n", block_content)
                if not e_match: e_match = re.search(r"建议价格:\s*(\[)?(.*?)(])?$", block_content, re.MULTILINE)
                if e_match: entry_txt = e_match.group(2).replace("[","").replace("]","").strip()
                    
                p_match = re.search(r"(?:建议|目标)?(?:股数|仓位):\s*(\[)?(.*?)(])?(?:\n|$)", block_content)
                if p_match: pos_txt = p_match.group(2).replace("[","").replace("]","").strip()
                    
                sl_match = re.search(r"止损(价格)?:\s*(\[)?(.*?)(])?\n", block_content)
                if not sl_match: sl_match = re.search(r"止损(价格)?:\s*(\[)?(.*?)(])?$", block_content, re.MULTILINE)
                if sl_match: stop_loss_txt = sl_match.group(3).replace("[","").replace("]","").strip()
                    
                tp_match = re.search(r"(止盈|目标)(价格)?:\s*(\[)?(.*?)(])?\n", block_content)
                if not tp_match: tp_match = re.search(r"(止盈|目标)(价格)?:\s*(\[)?(.*?)(])?$", block_content, re.MULTILINE)
                if tp_match: take_profit_txt = tp_match.group(4).replace("[","").replace("]","").strip()

            else:
                signal_match = re.search(r"【(买入|卖出|做空|观望|持有)】", content)
                ai_signal = signal_match.group(1) if signal_match else "N/A"
                lines = content.split('\n')
                for line in lines:
                    if "止损" in line: stop_loss_txt = line.split(":")[-1].strip().replace("元","")[:10]
                    if "止盈" in line or "目标" in line: take_profit_txt = line.split(":")[-1].strip().replace("元","")[:10]
                    if "股数" in line or "仓位" in line: pos_txt = line.split(":")[-1].strip()[:10]
            
            if "N/A" in ai_signal and "观望" in content: ai_signal = "观望"
            
            ai_col1, ai_col2, ai_col3, ai_col4, ai_col5 = st.columns(5)
            s_color = "grey"
            if ai_signal in ["买入", "做多"]: s_color = "green"
            if ai_signal in ["卖出", "做空"]: s_color = "red"
            pos_val, pos_note = extract_bracket_content(pos_txt if pos_txt != "N/A" else "--")
            sl_val, sl_note = extract_bracket_content(stop_loss_txt if stop_loss_txt != "N/A" else "--")
            tp_val, tp_note = extract_bracket_content(take_profit_txt if take_profit_txt != "N/A" else "--")
            entry_val, entry_note = extract_bracket_content(entry_txt if entry_txt != "N/A" else "--")

            ai_col1.markdown(f"**AI建议**: :{s_color}[{ai_signal}]")
            
            ai_col2.metric("建议价格", entry_val)
            if entry_note: ai_col2.caption(f"({entry_note})")
            
            ai_col3.metric("建议股数", pos_val)
            if pos_note: ai_col3.caption(f"({pos_note})")
            
            ai_col4.metric("止损参考", sl_val)
            if sl_note: ai_col4.caption(f"({sl_note})")
            
            ai_col5.metric("止盈参考", tp_val)
            if tp_note: ai_col5.caption(f"({tp_note})")
            
            with st.expander("📄 查看完整策略报告", expanded=False):
                st.markdown(content)
                if reasoning:
                    st.divider()
                    st.caption("AI 思考过程 (Chain of Thought)")
                    st.text(reasoning)

        else:
            st.info("👋 暂无 AI 独立策略记录。")

        st.markdown("---")
        # Control Buttons
        st.markdown("---")
        # Control Buttons
        from utils.time_utils import is_trading_time, get_target_date_for_strategy, get_market_session
        market_open = is_trading_time()
        session_status = get_market_session()
        
        # Display Base Position Info (if configured)
        from utils.database import db_get_position
        curr_pos_ui = db_get_position(code)
        base_s_ui = curr_pos_ui.get("base_shares", 0)
        if base_s_ui > 0:
             tradable_s_ui = max(0, shares_held - base_s_ui)
             st.info(f"🛡️ **风控护盾已激活** | 总持仓: {shares_held} | 🔒 底仓(Locked): **{base_s_ui}** | 🔄 可交易: **{tradable_s_ui}**")
        
        # Fund Flow History Display Moved to Dashboard
    with st.container():
        # Load Config/Prompts globally for this section
        prompts = load_config().get("prompts", {})
        
        col1, col2 = st.columns([3, 1])
        
        start_pre = False
        start_intra = False
        target_suffix_key = "proposer_premarket_suffix" # Default
        
        with col1:
            if session_status == "morning_break":
                # Noon Break: 11:30 - 13:00 -> Noon Review
                if st.button("☕ 生成午间复盘 (Morning Review)", key=f"btn_noon_{code}", type="primary", use_container_width=True):
                    target_suffix_key = "proposer_noon_suffix"
                    start_pre = True
                    
            elif session_status == "closed":
                # After Close: > 15:00 -> Daily Review
                if st.button("📝 生成全天复盘 (Daily Review)", key=f"btn_daily_{code}", type="primary", use_container_width=True):
                    target_suffix_key = "proposer_premarket_suffix"
                    start_pre = True
            else:
                # Trading Hours (or Pre-market before 9:15)
                # Show generic warning button
                if st.button("💡 生成即时预判 (Instant Preview)", key=f"btn_live_{code}", type="primary", use_container_width=True):
                    target_suffix_key = "proposer_premarket_suffix"
                    start_pre = True

        if start_pre:
            warning_msg = None
            if session_status == "trading":
                warning_msg = "⚠️ 警告: 市场正在交易中或未休盘。盘中生成的策略数据可能快速过时。"  

            # prompts loaded above
            if not deepseek_api_key:
                st.warning("请在侧边栏设置 DeepSeek API Key")
            else:
                with st.spinner(f"🧠 正在构建提示词上下文..."):
                    from utils.ai_advisor import build_advisor_prompt, call_deepseek_api
                    from utils.intel_manager import get_claims_for_prompt
                    from utils.intelligence_processor import summarize_intelligence
                    from utils.data_fetcher import aggregate_minute_to_daily, get_price_precision, analyze_intraday_pattern, get_stock_fund_flow, get_stock_fund_flow_history, get_stock_news, get_stock_news_raw
                    from utils.storage import load_minute_data
                    from utils.indicators import calculate_indicators
                    
                    # Logic to determine base price for Limit Calculation
                    # Default: Pre-Close (Yesterday's Close)
                    limit_base_price = pre_close
                    # If Pre-market Analysis for Tomorrow (Evening session), use Today's Close as base
                    if start_pre and datetime.datetime.now().time() > datetime.time(15, 0):
                        limit_base_price = price
                    
                    # Fetch Base Position
                    from utils.database import db_get_position
                    pos_data = db_get_position(code)
                    base_shares = pos_data.get("base_shares", 0)
                    tradable_shares = max(0, shares_held - base_shares)
                    
                    # Calculate Available Cash (Buying Power for this stock)
                    current_market_value = shares_held * price
                    available_cash = max(0.0, eff_capital - current_market_value)
                    
                    context = {
                        "base_shares": base_shares,
                        "tradable_shares": tradable_shares,
                        "limit_base_price": limit_base_price,
                        "code": code, 
                        "name": name, 
                        "name": name, 
                        "price": price, 
                        "pre_close": pre_close if pre_close > 0 else price,
                        "change_pct": (price - pre_close) / pre_close * 100 if pre_close > 0 else 0.0,
                        "cost": avg_cost,
                        "shares": shares_held,         # FIXED: Key for ai_advisor.py
                        "current_shares": shares_held, # Keep for backward compatibility if any
                        "available_cash": available_cash, # FIXED: Added available cash
                        "support": strat_res.get('support'), 
                        "resistance": strat_res.get('resistance'), 
                        "signal": strat_res.get('signal'),
                        "reason": strat_res.get('reason'), 
                        "quantity": strat_res.get('quantity'),
                        "target_position": strat_res.get('target_position', 0),
                        "stop_loss": strat_res.get('stop_loss'), 
                        "capital_allocation": current_alloc,
                        "total_capital": total_capital, 
                        "known_info": get_claims_for_prompt(code)
                    }
                    
                    
                    # [2-Stage Logic] Pre-process Intelligence if too long
                    raw_claims = get_claims_for_prompt(code) # Intel DB
                    news_items = get_stock_news_raw(code)
                    
                    final_research_context = raw_claims
                    if news_items:
                        full_news_text = "".join([n.get('title','')+n.get('content','') for n in news_items])
                        if len(full_news_text) > 1000 or len(news_items) > 5:
                            with st.spinner("🤖 正在进行第一阶段情报提炼 (Intelligence Refining)..."):
                                summary_intel = summarize_intelligence(deepseek_api_key, news_items, name)
                                if summary_intel:
                                    final_research_context += f"\n\n【最新市场情报摘要】\n{summary_intel}"
                        else:
                             # Short enough, append directly
                             news_str = ""
                             for n in news_items[:5]:
                                 news_str += f"- {n.get('date')} {n.get('title')}\n"
                             final_research_context += f"\n\n【最新新闻】\n{news_str}"

                    minute_df = load_minute_data(code)
                    tech_indicators = calculate_indicators(minute_df)
                    tech_indicators["daily_stats"] = aggregate_minute_to_daily(minute_df, precision=get_price_precision(code))
                    
                    intraday_pattern = analyze_intraday_pattern(minute_df)
                    
                    
                    # Force update history for Prompt Context (Ensure freshness before AI reads it)
                    # We pass the same dataframe structure, but force check API
                    ff_history_prompt = get_stock_fund_flow_history(code, force_update=True)
                    
                    # 1. Build Prompt
                    sys_p, user_p = build_advisor_prompt(
                        context, research_context=final_research_context, 
                        technical_indicators=tech_indicators, fund_flow_data=get_stock_fund_flow(code),
                        fund_flow_history=ff_history_prompt, prompt_templates=prompts,
                        intraday_summary=intraday_pattern,
                        suffix_key=target_suffix_key,
                        symbol=code
                    )
                    
                    # 2. Store in Session State for Preview
                    st.session_state[f"preview_prompt_{code}"] = {
                        "sys_p": sys_p,
                        "user_p": user_p,
                        "target_suffix_key": target_suffix_key,
                        "warning_msg": warning_msg,
                        "context_snapshot": context # Saved for Blue Legion (MoE)
                    }
                    st.rerun()

        # --- Prompt Preview and Confirmation ---
        preview_key = f"preview_prompt_{code}"
        if preview_key in st.session_state:
            preview_data = st.session_state[preview_key]
            
            st.info("🔎 **提示词预览 (Prompt Preview)** - 请确认后发送")
            
            if preview_data.get("warning_msg"):
                st.warning(preview_data["warning_msg"])
            
            with st.expander("查看完整提示词内容", expanded=True):
                full_text = f"【System Prompt】\n{preview_data['sys_p']}\n\n【User Prompt】\n{preview_data['user_p']}"
                st.text_area("Request Payload", value=full_text, height=300)
                
                # Token Count Approximation
                char_count = len(full_text)
                st.caption(f"总字符数: {char_count} (约 {int(char_count/1.5)} tokens)")
            
            # Gemini Toggle
            # Qwen Toggle
            # Model Selection UI
            st.caption("🤖 模型战队配置 (AI Team Config)")
            ms_c1, ms_c2 = st.columns(2)
            with ms_c1:
                blue_model = st.selectbox("🔵 蓝军 (进攻/策略)", ["DeepSeek"], index=0, key=f"blue_sel_{code}", help="负责生成交易计划 (Proposer)")
            with ms_c2:
                red_model = st.selectbox("🔴 红军 (防守/审查)", ["DeepSeek", "None"], index=0, key=f"red_sel_{code}", help="负责风险审计 (Reviewer)")
            
            # Auto-Drive Toggle
            auto_drive = st.checkbox("⚡ 极速模式 (Auto-Drive)", value=True, help="一键全自动：蓝军草案 -> 红军初审 -> 蓝军反思优化(v2.0) -> 红军终审", key=f"auto_drive_{code}")

            # Validate Keys (Dynamic)
            # Helper to get key (Registry handles this, but we check here for UI feedback)
            settings = load_config().get("settings", {})
            api_keys = {
                "deepseek_api_key": st.session_state.get("input_apikey") or settings.get("deepseek_api_key"),
                "qwen_api_key": st.session_state.get("input_qwen") or settings.get("qwen_api_key") or settings.get("dashscope_api_key")
            }
            
            # Legacy Key check for UI feedback
            ds_key_chk = api_keys["deepseek_api_key"]
            qwen_key_chk = api_keys["qwen_api_key"]
            
            # Helper to get key
            def get_key_for_model(m_name):
                if m_name == "DeepSeek": return ds_key_chk
                if m_name == "Qwen": return qwen_key_chk
                return ""

            p_col1, p_col2 = st.columns(2)
            with p_col1:
                if st.button(f"🚀 确认发送 (Send to {blue_model})", key=f"btn_send_{code}", use_container_width=True):
                    
                    target_key = get_key_for_model(blue_model)
                    if not target_key:
                        st.error(f"未检测到 {blue_model} API Key")
                    else:
                        from utils.expert_registry import ExpertRegistry
                        blue_expert = ExpertRegistry.get_expert(blue_model, api_keys)
                        red_expert = ExpertRegistry.get_expert(red_model, api_keys) if red_model != "None" else None
                        
                        if not blue_expert:
                             st.error(f"Failed to initialize Blue Expert: {blue_model}")
                             st.stop()

                        # --- AUTO DRIVE MODE ---
                        if auto_drive and red_expert:
                             step_logs = []
                             
                             if not get_key_for_model(red_model):
                                 st.error(f"Auto-Drive Aborted: Missing Key for Red Team ({red_model})")
                             else:
                                 try:
                                     with st.status("⚡ Auto-Drive 正在极速执行...", expanded=True) as status:
                                         # Step 1: Blue v1
                                         status.write(f"🧠 Step 1: {blue_model} 生成初始草案 (v1.0)...")
                                         
                                         c_snap = preview_data.get('context_snapshot', {})
                                         
                                         # Use 'raw_context' as well
                                         c1, r1, p1, moe_logs = blue_expert.propose(
                                            c_snap, prompts, 
                                            research_context=c_snap.get('known_info', ""),
                                            raw_context=preview_data['user_p']
                                         )
                                         
                                         if "Error" in c1:
                                             st.error(f"Generate Draft Failed: {c1}")
                                             status.update(label="❌ 执行中断", state="error")
                                             st.stop()
                                         step_logs.append(f"### [v1.0 Draft (Commander: {blue_model})]\n{c1}")
                                         
                                         # Step 2: Red Audit 1
                                         status.write(f"🛡️ Step 2: {red_model} 进行初审 (Audit Round 1)...")
                                         audit1, p_audit1 = red_expert.audit(c_snap, c1, prompts, is_final=False, raw_context=preview_data['user_p'])
                                         step_logs.append(f"### [Red Team Audit 1]\n{audit1}")
                                         
                                         # Step 3: Blue Refinement (v2)
                                         status.write(f"🔄 Step 3: {blue_model} 进行反思与优化 (Refining)...")
                                         c2, r2, p_refine = blue_expert.refine(preview_data['user_p'], c1, audit1, prompts)
                                         step_logs.append(f"### [v2.0 Refined Strategy]\n{c2}")
                                         
                                         # Step 4: Red Audit 2 (Final)
                                         status.write(f"⚖️ Step 4: {red_model} 进行终极裁决 (Final Verdict)...")
                                         audit2, p_audit2 = red_expert.audit(c_snap, c2, prompts, is_final=True, raw_context=preview_data['user_p'])
                                         step_logs.append(f"### [Final Verdict]\n{audit2}")
                                         
                                         # Step 5: Blue Final Decision (The Order)
                                         status.write(f"🏁 Step 5: {blue_model} 签署最终执行令 (Final Execution)...")
                                         c3, r3, p_decide = blue_expert.decide(audit2, prompts)
                                         step_logs.append(f"### [Final Decision]\n{c3}")

                                         # Construct Results
                                         final_result = c3 + "\n\n[Final Execution Order]"
                                         final_result += f"\n\n--- 📜 v1.0 Draft ---\n{c1}"
                                         final_result += f"\n\n--- 🔴 Round 1 Audit ---\n{audit1}"
                                         final_result += f"\n\n--- 🔄 v2.0 Refined ---\n{c2}"
                                         final_result += f"\n\n--- ⚖️ Final Verdict ---\n{audit2}"

                                         if "Error" in c3: pass
                                         
                                         final_reasoning = f"### [R1 Reasoning]\n{r1}\n\n### [R2 Refinement]\n{r2}\n\n### [Final Decision]\n{r3}"
                                         if moe_logs: final_reasoning = "\n".join(moe_logs) + "\n" + final_reasoning
                                         
                                         status.update(label="✅ 全流程执行完毕! 正在保存...", state="complete", expanded=False)
                                         
                                         # Save State
                                         strategy_tag = "【极速复盘】"
                                         save_payload = {
                                            'result': final_result, 
                                            'reasoning': final_reasoning, 
                                            'audit': audit1,             
                                            'final_audit': audit2, 
                                            'prompt': preview_data['user_p'],  
                                            'prompts_history': {
                                                'draft_sys': preview_data['sys_p'],
                                                'draft_user': preview_data['user_p'],
                                                'audit1': p_audit1,
                                                'refine': p_refine,
                                                'audit2': p_audit2,
                                                'decide': p_decide
                                            },
                                            'tag': strategy_tag,
                                            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                            'blue_model': blue_model,
                                            'red_model': red_model,
                                            'raw_context': preview_data['user_p'],
                                            'stage': 'auto_done',
                                            'final_exec': c3, 
                                            'is_refined': True
                                        }
                                         
                                         target_save_key = f"pending_ai_result_{code}"
                                         st.session_state[target_save_key] = save_payload
                                         st.session_state[f"toast_msg_{code}"] = "✅ 极速复盘已完成！请查看上方结果区域。"
                                         
                                         del st.session_state[preview_key]
                                         st.rerun()
                                         
                                 except Exception as e:
                                     st.error(f"❌ Auto-Drive Execution Error: {str(e)}")

                        # --- MANUAL MODE (Expert) ---
                        else:
                            # 1. Execute Blue Team (Manual Step 1)
                            with st.spinner(f"🧠 {blue_model} (Blue Team) 正在思考..."):
                                c_snap = preview_data.get('context_snapshot', {})
                                c1, reasoning, _, moe_logs = blue_expert.propose(
                                    c_snap, prompts, 
                                    research_context=c_snap.get('known_info', ""),
                                    raw_context=preview_data['user_p']
                                )
                            
                            if "Error" in c1:
                               st.error(c1)
                            else:
                                # Determine Tag
                                strategy_tag = "【盘前策略】"
                                if "noon" in preview_data.get('target_suffix_key', ''):
                                    strategy_tag = "【午间复盘】"
                                elif "intraday" in preview_data.get('target_suffix_key', ''):
                                    strategy_tag = "【盘中对策】"
                                elif "new_strategy" in preview_data.get('target_suffix_key', '') and session_status == "closed":
                                    strategy_tag = "【盘后复盘】"
                                    
                                # Success -> Save Draft, Move to Stage 2
                                final_reasoning = reasoning
                                if moe_logs: final_reasoning = "\n".join(moe_logs) + "\n" + reasoning
                                
                                st.session_state[f"pending_ai_result_{code}"] = {
                                    'result': c1, 
                                    'reasoning': final_reasoning, 
                                    'audit': None, 
                                    'prompt': preview_data['user_p'],
                                    'prompts_history': {'draft_sys': preview_data['sys_p'], 'draft_user': preview_data['user_p']},
                                    'tag': strategy_tag,
                                    'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    'blue_model': blue_model,
                                    'red_model': red_model,
                                    'raw_context': preview_data['user_p'],
                                    'context_snapshot': c_snap, 
                                    'stage': 'draft_created' 
                                }
                                del st.session_state[preview_key]
                                st.session_state[f"toast_msg_{code}"] = f"✅ 草案已生成！正在切换至详细视图..."
                                st.rerun()
                                


            with p_col2:
                if st.button("❌ 取消 (Cancel)", key=f"btn_cancel_p_{code}", use_container_width=True):
                    del st.session_state[preview_key]
                    st.rerun()
            
            st.markdown("---")


        # --- Nested History (Inside AI Analysis) ---
        st.markdown("---")
        with st.expander("📜 历史研报记录 (Research History)", expanded=False):
            logs = load_production_log(code)
            if not logs:
                st.info("暂无历史记录")
            else:
                # 1. Prepare Data for Matching Trades
                trades = db_get_history(code)
                # Filter trades: include only explicit buy/sell, exclude allocation/override
                real_trades = [t for t in trades if t['type'] in ['buy', 'sell'] and t.get('amount', 0) > 0]
                
                # Sort logs ascending for matching interval
                sorted_logs = sorted(logs, key=lambda x: x['timestamp'])
                
                history_data = []
                log_options = {}
                
                for i, log in enumerate(sorted_logs):
                    ts = log.get('timestamp', 'N/A')
                    
                    # Determine time window
                    start_time = ts
                    end_time = sorted_logs[i+1]['timestamp'] if i < len(sorted_logs) - 1 else datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Find matched trades
                    matched_tx = []
                    for t in real_trades:
                        t_ts = t['timestamp']
                        if start_time <= t_ts < end_time:
                            # Format: "Buy 100" or "Sell 500"
                            action_str = "买" if t['type'] == 'buy' else "卖"
                            matched_tx.append(f"{action_str} {int(t['amount'])}@{t['price']}")
                            
                    tx_str = "; ".join(matched_tx) if matched_tx else "-"
                    
                    # Parse simplified result
                    res_snippet = log.get('result', '')
                    # Try to extract Signal
                    s_match = re.search(r"方向:\s*(\[)?(.*?)(])?\n", res_snippet)
                    if not s_match: s_match = re.search(r"【(买入|卖出|做空|观望|持有)】", res_snippet)
                    signal_show = s_match.group(2) if s_match and len(s_match.groups()) >= 2 else (s_match.group(1) if s_match else "N/A")
                    if "N/A" in signal_show and "观望" in res_snippet[:100]: signal_show = "观望"

                    if "N/A" in signal_show and "观望" in res_snippet[:100]: signal_show = "观望"

                    # Determine Target Date using enforced logic
                    dt_ts = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                    target_date_str = get_target_date_for_strategy(dt_ts)
                    
                    # Extract Tag
                    tag = "盘中"
                    # Simple heuristic for tag display, but date is now rigorous
                    if "盘前" in res_snippet[:20] or dt_ts.hour >= 15 or dt_ts.hour < 9:
                        tag = "盘前"
                    if "盘中" in res_snippet[:20]:
                        tag = "盘中"

                    # Add to list (Insert at beginning to show latest first in table)
                    history_data.insert(0, {
                        "生成时间": ts,
                        "适用日期": target_date_str,
                        "类型": tag,
                        "AI建议": signal_show.replace("[","").replace("]",""),
                        "实际执行": tx_str,
                        "raw_log": log
                    })
                    
                    # Prepare options for selectbox (Reverse order essentially)
                    label = f"{ts} | {signal_show} | Exec: {tx_str}"
                    log_options[label] = log

                # 2. Show Summary Table
                st.caption("策略与执行追踪")
                df_hist = pd.DataFrame(history_data)
                st.dataframe(
                    df_hist[['适用日期', '类型', 'AI建议', '实际执行', '生成时间']], 
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "适用日期": st.column_config.TextColumn("适用日期 (Target)", width="small"),
                        "类型": st.column_config.TextColumn("类型", width="small"),
                        "生成时间": st.column_config.TextColumn("生成时间 (Created)", width="medium"),
                        "实际执行": st.column_config.TextColumn("实际执行 (基于此策略)", width="large"),
                        "AI建议": st.column_config.TextColumn("AI建议", width="small"),
                    }
                )

                # 3. Detail View
                st.divider()
                selected_label = st.selectbox("查看详情 (Select Detail)", options=list(log_options.keys())[::-1], key=f"hist_sel_{code}")
                
                if selected_label:
                    selected_log = log_options[selected_label]
                    # Find corresponding row to get tx_str easily (or recompute)
                    # We can just extract from label or matched logic. 
                    # Let's re-find in history_data
                    linked_tx = "N/A"
                    for item in history_data:
                        if item["raw_log"] == selected_log:
                            linked_tx = item["实际执行"]
                            break
                            
                    s_ts = selected_log.get('timestamp', 'N/A')
                    st.markdown(f"#### 🗓️ {s_ts}")
                    
                    if linked_tx != "-":
                        st.info(f"⚡ **关联执行**: {linked_tx}")
                        
                    res_text = selected_log.get('result', '')
                    
                    from components.strategy_display_helper import display_strategy_content
                    display_strategy_content(res_text)
                    
                    if selected_log.get('reasoning'):
                        r_content = selected_log['reasoning'].strip()
                        # Check if it's effectively empty (just headers)
                        is_empty = False
                        if "### [Round 1 Reasoning]" in r_content and len(r_content) < 100:
                             # Heuristic: if it only contains headers and newlines
                             pass 
                        
                        r_title = "💭 思考过程 (Chain of Thought)"
                        if not r_content or r_content == "N/A":
                            r_title += " [不可用]"
                        
                        with st.expander(r_title, expanded=False):
                            if r_content:
                                st.markdown(r_content)
                            else:
                                st.caption("此模型 (如 Qwen) 未提供思考过程元数据。")
                    
                    if selected_log.get('prompt'):
                        p_text = selected_log['prompt']
                        
                        # Detect if this is a "Mega Log" (v2.1+) or v2.6+ with details
                        details_json = selected_log.get('details')
                        has_details = False
                        if details_json:
                            import json
                            try:
                                details = json.loads(details_json)
                                if isinstance(details, dict) and 'prompts_history' in details:
                                    has_details = True
                                    ph = details['prompts_history']
                                    with st.expander("📝 全流程详情 (Full Process History)", expanded=True):
                                         h_tab1, h_tab2, h_tab3, h_tab4, h_tab5 = st.tabs(["Draft (草案)", "Audit1 (初审)", "Refine (反思)", "Audit2 (终审)", "Final (决策)"])
                                         with h_tab1: st.code(f"System:\n{ph.get('draft_sys','')}\n\nUser:\n{ph.get('draft_user','')}")
                                         with h_tab2: st.caption(f"Prompt Used:"); st.code(ph.get('audit1', 'N/A'))
                                         with h_tab3: st.caption(f"Prompt Used:"); st.code(ph.get('refine', 'N/A'))
                                         with h_tab4: st.caption(f"Prompt Used:"); st.code(ph.get('audit2', 'N/A'))
                                         with h_tab5: st.caption(f"Prompt Used:"); st.code(ph.get('decide', 'N/A'))
                            except:
                                pass
                        
                        if not has_details and "# 🧠 Round 1: Strategy Draft" in p_text:
                            with st.expander("📝 全流程详情 (Full Process History - Legacy)", expanded=True):
                                # ... existing logic ...
                                # Split by Headers
                                # We can uses Tabs for rounds
                                h_tab1, h_tab2, h_tab3, h_tab4 = st.tabs(["Draft (草案)", "Audit (初雪)", "Refine (反思)", "Final (终审)"])
                                
                                def extract_section(full_txt, start_marker, end_marker=None):
                                    try:
                                        p1 = full_txt.find(start_marker)
                                        if p1 == -1: return "N/A"
                                        p1 += len(start_marker)
                                        
                                        if end_marker:
                                            p2 = full_txt.find(end_marker, p1)
                                            if p2 == -1: return full_txt[p1:].strip()
                                            return full_txt[p1:p2].strip()
                                        else:
                                            return full_txt[p1:].strip()
                                    except:
                                        return "N/A"
                                
                                with h_tab1:
                                    st.caption("🔵 Blue Team - Initial Prompt")
                                    s1 = extract_section(p_text, "# 🧠 Round 1: Strategy Draft", "# 🛡️ Round 1: Red Audit")
                                    st.code(s1, language='text')

                                with h_tab2:
                                    st.caption("🔴 Red Team - Audit Round 1")
                                    s2 = extract_section(p_text, "# 🛡️ Round 1: Red Audit", "# 🔄 Round 2: Refinement")
                                    st.code(s2, language='text')

                                with h_tab3:
                                    st.caption("🔵 Blue Team - Refinement (Reaction to Audit)")
                                    s3 = extract_section(p_text, "# 🔄 Round 2: Refinement", "# ⚖️ Final Verdict")
                                    st.code(s3, language='text')
                                    
                                with h_tab4:
                                    st.caption("🔴 Red Team - Final Verdict")
                                    s4 = extract_section(p_text, "# ⚖️ Final Verdict")
                                    st.code(s4, language='text')

                        else:
                            # Legacy Display
                            with st.expander("📝 原始提示词 (Legacy Prompt)", expanded=False):
                                st.code(p_text, language='text')

                    if st.button("🗑️ 删除此记录", key=f"del_rsch_{code}_{s_ts}"):
                        if delete_production_log(code, s_ts):
                            st.success("已删除")
                            time.sleep(0.5)
                            st.rerun()
    
    return strat_res # Return strategy result if needed by dashboard
