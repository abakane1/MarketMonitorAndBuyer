# -*- coding: utf-8 -*-
import streamlit as st
import time
import json
from utils.strategy import analyze_volume_profile_strategy
from utils.storage import get_volume_profile, get_latest_production_log, save_production_log, load_production_log, delete_production_log
from utils.ai_parser import extract_bracket_content
from utils.config import load_config, get_allocation, set_allocation
from utils.monitor_logger import log_ai_heartbeat
from utils.database import db_get_history, db_get_position, db_save_strategy_execution_log
from utils.ai_advisor import build_advisor_prompt, call_deepseek_api, build_refinement_prompt
from utils.ai_parser import extract_bracket_content, parse_strategy_with_fallback

import pandas as pd

import re
import datetime
from utils.prompt_loader import load_all_prompts
from utils.time_utils import get_target_date_for_strategy, get_beijing_time, is_trading_time, get_market_session
from utils.asset_classifier import get_asset_type_and_tags

def render_strategy_section(code: str, name: str, price: float, shares_held: int, avg_cost: float, total_capital: float, risk_pct: float, proximity_pct: float, pre_close: float = 0.0):
    """
    渲染策略分析区域 (算法 + AI)
    """
    # 0. Global API Config (Moved to top to prevent UnboundLocalError)
    config = load_config()
    settings = config.get("settings", {})
    
    # Load MD prompts and merge
    prompts = load_all_prompts()
    if config.get("prompts"):
        prompts.update(config.get("prompts"))
    api_keys = {
        "deepseek_api_key": st.session_state.get("input_apikey") or settings.get("deepseek_api_key"),
        "qwen_api_key": st.session_state.get("input_qwen") or settings.get("qwen_api_key") or settings.get("dashscope_api_key"),
        "kimi_api_key": st.session_state.get("input_kimi") or settings.get("kimi_api_key"),
        "kimi_base_url": st.session_state.get("input_kimi_url") or settings.get("kimi_base_url")
    }

    # 1. Capital Allocation UI
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
        
        # [Dual-Track System] 资产阵营提示
        asset_info = get_asset_type_and_tags(code)
        st.info(f"{asset_info['badge']} | {asset_info['description']}")
        
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
                with st.expander(f"🔴 {ai_strat_log.get('red_model', 'DeepSeek')} 风控官审查报告 (Red Team Audit)", expanded=True):
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
                                    # Get Key from registry-ready api_keys dict
                                    b_key = api_keys.get("deepseek_api_key", "")
                                    if r_data['model'] == "Kimi":
                                        b_key = api_keys.get("kimi_api_key", "")
                                    
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
                                                # [HISTORY] Save Draft v1 before overwrite
                                                st.session_state[pending_key]['draft_v1'] = st.session_state[pending_key].get('result', '')
                                                
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
                             red_model = ai_strat_log.get('red_model', 'Kimi')
                             st.info(f"⚖️ 等待红军 ({red_model}) 终极裁决 (Final Verdict)...")
                             
                             if final_audit_key not in st.session_state:
                                 if st.button(f"⚖️ 准备终审 (Prepare Final Verdict)", key=f"btn_prep_final_{code}"):
                                     with st.spinner("🤖 正在构建终审指令..."):
                                         from utils.ai_advisor import build_red_team_prompt
                                         # Context is V2 Plan
                                         # Context is V2 Plan
                                         bg_info = ai_strat_log.get('raw_context') or ai_strat_log.get('prompt', '')
                                         
                                         # [HISTORY] Construct Full Debate History for Final Verdict
                                         draft_msg = ai_strat_log.get('draft_v1', '(Data Missing)')
                                         audit_msg = ai_strat_log.get('audit', '(Data Missing)')
                                         
                                         # Extract Refinement Reasoning (Last part of reasoning log)
                                         full_r = ai_strat_log.get('reasoning', '')
                                         refine_r = full_r.split("--- 🔄 Refinement Logic ---")[-1] if "--- 🔄 Refinement Logic ---" in full_r else "N/A"
                                         
                                         history_txt = f"""
【历史回溯 (History)】
1. **Draft v1.0 (蓝军初稿)**:
{draft_msg[:1000]}... (truncated)

2. **Audit Round 1 (红军初审)**:
{audit_msg}

3. **Refinement Logic (蓝军反思)**:
{refine_r}
"""
                                         audit_ctx = {
                                             "code": code,
                                             "name": name,
                                             "price": price,
                                             "daily_stats": bg_info,  
                                             "deepseek_plan": ai_strat_log['result'], # This is V2 now
                                             "history_summary": history_txt
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
                                         # Key Check using centralized api_keys
                                         r_key = api_keys.get("deepseek_api_key", "") # Default: DeepSeek for audit
                                         if fa_data['model'] == "DeepSeek": r_key = api_keys.get("deepseek_api_key", "")
                                         elif fa_data['model'] == "Kimi": r_key = api_keys.get("kimi_api_key", "")

                                         if not r_key: st.error(f"Missing Key for {fa_data['model']}"); st.stop()
                                         
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
                             with st.expander(f"⚖️ {ai_strat_log.get('red_model','DeepSeek')} 终极裁决 (Final Verdict)", expanded=True):
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
                                              
                                              # [HISTORY] Assemble Full Timeline for Final Decision
                                              history_chain = [
                                                  ai_strat_log.get('draft_v1', '(Missing Draft v1)'),
                                                  ai_strat_log.get('audit', '(Missing Audit R1)'),
                                                  ai_strat_log.get('result', '(Missing Refined v2)'), # This is v2
                                                  ai_strat_log.get('final_audit', '(Missing Final Verdict)')
                                              ]
                                              
                                              # Re-construct context for re-injection
                                              # Use draft raw_context if available
                                              fin_ctx = {
                                                  'code': code, 'name': name, 'price': price,
                                                  'shares': shares_held, 'cost': avg_cost, 
                                                  'pre_close': pre_close, 
                                                  'change_pct': (price - pre_close)/pre_close*100 if pre_close else 0
                                              }
                                              
                                              sys_fin, user_fin = build_final_decision_prompt(history_chain, prompts, context_data=fin_ctx)
                                              
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
                                               b_key = api_keys.get("deepseek_api_key", "")
                                               if fe_data['model'] == "Qwen": 
                                                   b_key = api_keys.get("qwen_api_key", "")
                                               elif fe_data['model'] == "Kimi":
                                                   b_key = api_keys.get("kimi_api_key", "")
                                               
                                               if not b_key: st.error(f"Missing Key for {fe_data['model']}"); st.stop()
                                               
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
                            
                            c_snap = ai_strat_log.get('context_snapshot', {}) or {}
                            
                            # Use get() for safety as snapshot might be partial
                            
                            # Prepare Date
                            # datetime module already imported at top level
                            
                            prompts = load_all_prompts()
                            # Merge overrides from config if any
                            if config.get("prompts"):
                                prompts.update(config.get("prompts"))

                            gen_time_str = ai_strat_log.get('time')
                            if gen_time_str:
                                try:
                                    gen_time = datetime.datetime.strptime(gen_time_str, "%Y-%m-%d %H:%M:%S")
                                except:
                                    gen_time = get_beijing_time()
                            else:
                                gen_time = get_beijing_time()
                            
                            date_val = get_target_date_for_strategy(gen_time)

                            audit_ctx = {
                                "code": code,
                                "name": name,
                                "price": price,
                                "date": date_val,
                                "total_capital": total_capital,
                                "daily_stats": bg_info, # Fallback to full context text
                                "capital_flow": c_snap.get('capital_flow_str', 'Check Daily Stats'),
                                "research_context": ai_strat_log.get('raw_context') or ai_strat_log.get('prompt', 'N/A'),
                                "intraday_summary": c_snap.get('intraday_summary', 'Check Daily Stats'),
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
                             r_key = api_keys.get("deepseek_api_key", "")
                             if a_data['model'] == "Qwen":
                                 r_key = api_keys.get("qwen_api_key", "")
                             elif a_data['model'] == "Kimi":
                                 r_key = api_keys.get("kimi_api_key", "")
                             elif a_data['model'] == "DeepSeek":
                                 r_key = api_keys.get("deepseek_api_key", "")
                             
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
                    
                    # [Task 13: Execution Tracking] Extract AI decisions
                    draft_v1 = ai_strat_log.get('draft_v1', ai_strat_log['result'])
                    db_save_strategy_execution_log(
                        symbol=code,
                        strategy_id=strategy_uuid,
                        ai_action=ai_action,
                        ai_price=ai_price,
                        ai_qty=ai_qty,
                        final_action=final_action,
                        final_price=final_price,
                        final_qty=final_qty,
                        is_altered=is_altered,
                        reasoning=f"Draft v1 -> User Accepted. Prompt used: {ai_strat_log.get('prompt_version', 'default')}"
                    )
                    
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
                        model=ai_strat_log.get('model', 'DeepSeek'),
                        details=json.dumps({'prompts_history': ph}, ensure_ascii=False) if ph else None
                    )
                    # Clear draft
                    del st.session_state[pending_key]
                    st.success("策略已入库！")
                    time.sleep(0.5)
                    st.rerun()
                    
            with col_disc:
                if st.button("🗑️ 放弃 (Discard)", key=f"btn_discard_{code}", use_container_width=True):
                    # [Task 13: Execution Tracking]
                    draft_v1 = ai_strat_log.get('draft_v1', ai_strat_log['result'])
                    # [Task 13: Execution Tracking]
                    draft_v1 = ai_strat_log.get('draft_v1', ai_strat_log['result'])
                    
                    try:
                        ai_price = float(re.search(r"(\d+(\.\d+)?)", str(v1_parsed.get('price', 0))).group(1)) if v1_parsed.get('price') else 0.0
                    except: ai_price = 0.0
                    
                    ai_qty = int(v1_parsed.get('shares', 0) or 0)
                    ai_action = v1_parsed.get('direction', '观望')
                    strategy_uuid = ai_strat_log.get('timestamp', str(time.time()))
                    
                    db_save_strategy_execution_log(
                        symbol=code,
                        strategy_id=strategy_uuid,
                        ai_action=ai_action,
                        ai_price=ai_price,
                        ai_qty=ai_qty,
                        final_action="放弃",
                        final_price=0.0,
                        final_qty=0,
                        is_altered=1,
                        reasoning=f"User Discarded. Prompt used: {ai_strat_log.get('prompt_version', 'default')}"
                    )
                    
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
            
            # --- Simple Parser (Scenario Aware) ---
            # Use the robust parser from utils.ai_parser
            parsed_res = parse_strategy_with_fallback(content)
            
            ai_signal = parsed_res.get("direction", "N/A")
            entry_txt = str(parsed_res.get("price")) if parsed_res.get("price") else "N/A"
            pos_txt = str(parsed_res.get("shares")) if parsed_res.get("shares") else "N/A"
            stop_loss_txt = str(parsed_res.get("stop_loss")) if parsed_res.get("stop_loss") else "N/A"
            take_profit_txt = str(parsed_res.get("take_profit")) if parsed_res.get("take_profit") else "N/A"
            
            # Scenario Key Extraction (Still useful to keep bespoke if needed, or move to parser later)
            scenario_key_txt = ""
            block_match = re.search(r"【决策摘要】(.*)", content, re.DOTALL)
            if block_match:
                block_content = block_match.group(1)
                sk_match = re.search(r"场景重点:\s*(\[)?(.*?)(])?\n", block_content)
                if not sk_match: sk_match = re.search(r"场景重点:\s*(.*)", block_content)
                if sk_match: scenario_key_txt = sk_match.group(2) if len(sk_match.groups())>1 else sk_match.group(1)
            
            if "N/A" in ai_signal and "观望" in content: ai_signal = "观望"

            
            # --- New UI Layout: Scenario-Tactics Header ---
            s_color = "grey"
            if ai_signal in ["买入", "做多"]: s_color = "green"
            elif ai_signal in ["卖出", "做空"]: s_color = "red"
            
            pos_val, pos_note = extract_bracket_content(pos_txt if pos_txt != "N/A" else "--")
            sl_val, sl_note = extract_bracket_content(stop_loss_txt if stop_loss_txt != "N/A" else "--")
            tp_val, tp_note = extract_bracket_content(take_profit_txt if take_profit_txt != "N/A" else "--")
            entry_val, entry_note = extract_bracket_content(entry_txt if entry_txt != "N/A" else "--")

            # 1. Primary Action Row
            st.subheader(f"🎯 AI 执行令: :{s_color}[{ai_signal}]")
            
            # [MOVED/SIMPLIFIED] Logic for notes display
            notes_html = ""
            if entry_val != "--": notes_html += f"📍 **建议区间**: {entry_val} " + (f"({entry_note})" if entry_note else "") + " | "
            if sl_val != "--": notes_html += f"🛡️ **止损**: {sl_val} " + (f"({sl_note})" if sl_note else "") + " | "
            if tp_val != "--": notes_html += f"💰 **止盈**: {tp_val} " + (f"({tp_note})" if tp_note else "")

            if notes_html:
                st.markdown(notes_html.rstrip(" | "))
            
            # 2. Strategy & Scenario Details (Wide)
            st.markdown(f"🚩 **建议股数/风控注记**: {pos_val} " + (f" *({pos_note})*" if pos_note else ""))
            
            # [NEW] Scenario Tactics Highlighting
            scenario_match = re.search(r"【场景对策】(.*?)【", content, re.DOTALL)
            if not scenario_match: scenario_match = re.search(r"【场景对策】(.*)", content, re.DOTALL)
            
            if scenario_match or scenario_key_txt:
                with st.container():
                    st.info(f"🎭 **今日命门 & 场景推演**\n\n**场景核心**: {scenario_key_txt if scenario_key_txt else '见完整报告'}\n\n" + 
                            (scenario_match.group(1).strip() if scenario_match else ""))
            
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
        # from utils.time_utils import is_trading_time, get_target_date_for_strategy, get_market_session
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
        # Load prompts needed for strategy generation
        prompts = load_config().get("prompts", {})
        
        col1, col2 = st.columns([3, 1])

        
        start_pre = False
        start_intra = False
        target_suffix_key = "proposer_premarket_suffix" # Default
        
        with col1:
            if session_status == "morning_break":
                # Noon Break: 11:30 - 13:00 -> Noon Review
                if st.button("☕ 生成午间复盘 (Noon Strategy)", key=f"btn_noon_{code}", type="primary", use_container_width=True):
                    target_suffix_key = "proposer_noon_suffix"
                    start_pre = True
                    
            elif session_status == "closed":
                # After Close: > 15:00 -> Daily Review / Tomorrow Prep
                if st.button("📝 生成全天复盘 (Daily Review/Tomorrow Plan)", key=f"btn_daily_{code}", type="primary", use_container_width=True):
                    target_suffix_key = "proposer_premarket_suffix"
                    start_pre = True
            elif session_status == "pre_market":
                # Pre-Market: 9:00 - 9:30 -> Opening Preparation
                if st.button("🌤️ 生成盘前规划 (Opening Plan)", key=f"btn_pre_{code}", type="primary", use_container_width=True):
                    target_suffix_key = "proposer_premarket_suffix"
                    start_pre = True
            else:
                # Trading Hours: Now Enabled [v4.5]
                if st.button("🔥 生成盘中焦点 (Intraday Analysis)", key=f"btn_live_{code}", type="primary", use_container_width=True):
                     # Check if specific intraday prompt exists, else fallback to premarket (with injected context)
                     if "proposer_intraday_suffix" in prompts:
                         target_suffix_key = "proposer_intraday_suffix"
                     else:
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
                    from utils.intel_manager import get_claims_for_prompt
                    from utils.intelligence_processor import summarize_intelligence
                    from utils.data_fetcher import aggregate_minute_to_daily, get_price_precision, analyze_intraday_pattern, get_stock_fund_flow, get_stock_fund_flow_history, get_stock_news, get_stock_news_raw
                    from utils.storage import load_minute_data
                    from utils.indicators import calculate_indicators
                    
                    # [P2-3 Fix] Add Exception Handling for Strategy Generation
                    try:
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
                        
                        # [User Actions Context] Fetch recent history for AI context
                        try:
                            user_history = db_get_history(code)
                            # Filter out system logs like base_position/allocation
                            valid_types = ['buy', 'sell', 'override', '买入', '卖出']
                            tx_history = [h for h in user_history if h.get('type') in valid_types]
                            # Get last 3 actions
                            recent_actions = tx_history[-3:] if tx_history else []
                            if recent_actions:
                                action_strs = []
                                for act in recent_actions:
                                    ts = act.get('timestamp', '')[:16] # Date and HH:MM
                                    t_type = act.get('type', 'N/A')
                                    act_name = "买入" if t_type in ['buy', '买入'] else ("卖出" if t_type in ['sell', '卖出'] else "修正")
                                    amt = int(act.get('amount', 0))
                                    prc = act.get('price', 0)
                                    action_strs.append(f"{ts} {act_name} {amt}股@{prc}")
                                user_actions_summary = "; ".join(action_strs)
                            else:
                                user_actions_summary = "无近期操作记录"
                        except Exception as e:
                            print(f"Error fetching user history: {e}")
                            user_actions_summary = "获取记录失败"

                        context = {
                            "base_shares": base_shares,
                            "tradable_shares": tradable_shares,
                            "limit_base_price": limit_base_price,
                            "code": code, 
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
                            "known_info": get_claims_for_prompt(code),
                            "user_actions_summary": user_actions_summary # FIXED: Injected missing key
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
                        
                        # [Noon Review Enhanced] Calculate Morning Stats (Fixed for Datetime Index)
                        morning_stats = {}
                        if not minute_df.empty and '时间' in minute_df.columns:
                            try:
                                # 1. ensure datetime
                                if not pd.api.types.is_datetime64_any_dtype(minute_df['时间']):
                                    minute_df['时间'] = pd.to_datetime(minute_df['时间'])
                                
                                # 2. Filter for Latest Date (Today)
                                latest_date = minute_df['时间'].dt.date.iloc[-1]
                                today_df = minute_df[minute_df['时间'].dt.date == latest_date]
                                
                                # 3. Filter for Morning Session (09:30 - 11:30)
                                # Using 11:31 to be safe inclusive of 11:30:00
                                import datetime as dt_module
                                m_start = dt_module.time(9, 30)
                                m_end = dt_module.time(11, 31) 
                                
                                m_df = today_df[
                                    (today_df['时间'].dt.time >= m_start) & 
                                    (today_df['时间'].dt.time < m_end)
                                ]
                                
                                if not m_df.empty:
                                    m_open = m_df.iloc[0]['收盘']
                                    if '开盘' in m_df.columns: 
                                        # Use the first minute's open if available, or just first record
                                        m_open = m_df.iloc[0]['开盘'] if m_df.iloc[0]['开盘'] > 0 else m_df.iloc[0]['收盘']
                                    
                                    m_close = m_df.iloc[-1]['收盘']
                                    m_high = m_df['最高'].max() if '最高' in m_df.columns else m_df['收盘'].max()
                                    m_low = m_df['最低'].min() if '最低' in m_df.columns else m_df['收盘'].min()
                                    m_vol = m_df['成交量'].sum()
                                    
                                    morning_stats = {
                                        "morning_open": m_open,
                                        "morning_high": m_high,
                                        "morning_low": m_low,
                                        "morning_close": m_close,
                                        "morning_vol": m_vol
                                    }
                                    context.update(morning_stats)
                            except Exception as e:
                                print(f"Morning Stats Calc Error: {e}")
    
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
                            "context_snapshot": context, # Saved for Blue Legion (MoE)
                            # Additional data for DeepSeekExpert.propose()
                            "intraday_summary": intraday_pattern,
                            "technical_indicators": tech_indicators,
                            "fund_flow_data": get_stock_fund_flow(code),
                            "fund_flow_history": ff_history_prompt,
                            "research_context": final_research_context
                        }

                    except Exception as e:
                        import traceback
                        error_trace = traceback.format_exc()
                        print(f"Strategy Generation Error for {code}:\n{error_trace}")
                        st.error(f"❌ 策略生成失败: {str(e)}")
                        
                        # Instead of rerunning and wiping the error, we stop here to show the error
                        if f"preview_prompt_{code}" in st.session_state:
                           del st.session_state[f"preview_prompt_{code}"]
                    else:
                        # Only rerun if successful
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
                blue_model = st.selectbox("🔵 蓝军 (进攻/策略)", ["Kimi", "DeepSeek"], index=0, key=f"blue_sel_{code}", help="负责生成交易计划 (Proposer)")
            with ms_c2:
                red_model = st.selectbox("🔴 红军 (防守/审查)", ["DeepSeek", "Kimi", "None"], index=0, key=f"red_sel_{code}", help="负责风险审计 (Reviewer)")
            
            # Auto-Drive Toggle
            auto_drive = st.checkbox("⚡ 极速模式 (Auto-Drive)", value=True, help="一键全自动：蓝军草案 -> 红军初审 -> 蓝军反思优化(v2.0) -> 红军终审", key=f"auto_drive_{code}")

            # Legacy Key check for UI feedback
            ds_key_chk = api_keys["deepseek_api_key"]
            
            # Helper to get key
            def get_key_for_model(m_name):
                if m_name == "DeepSeek": return ds_key_chk
                if m_name == "Kimi": return api_keys["kimi_api_key"]
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
                                         
                                         # [Robustness Fix] Ensure context_snapshot is a dict
                                         c_snap_raw = preview_data.get('context_snapshot', {})
                                         if isinstance(c_snap_raw, str):
                                             st.warning("⚠️ 检测到上下文快照格式异常 (String)，已自动重置为空。")
                                             c_snap = {}
                                         else:
                                             c_snap = c_snap_raw
                                             
                                         round_history = []
                                         
                                         # Use 'raw_context' as well
                                         c1, r1, p1, moe_logs = blue_expert.propose(
                                            c_snap, prompts, 
                                            research_context=preview_data.get('research_context', c_snap.get('known_info', "")),
                                            raw_context=preview_data['user_p'],
                                            intraday_summary=preview_data.get('intraday_summary'),
                                            technical_indicators=preview_data.get('technical_indicators'),
                                            fund_flow_data=preview_data.get('fund_flow_data'),
                                            fund_flow_history=preview_data.get('fund_flow_history')
                                         )
                                         
                                         if "Error" in c1:
                                             st.error(f"Generate Draft Failed: {c1}")
                                             status.update(label="❌ 执行中断", state="error")
                                             st.stop()
                                         step_logs.append(f"### [v1.0 Draft (Commander: {blue_model})]\n{c1}")
                                         round_history.append(f"【回合 1 (草案)】\n思考: {r1}\n建议: {c1}")
                                         
                                         # Step 2: Red Audit 1
                                         status.write(f"🛡️ Step 2: {red_model} 进行初审 (Audit Round 1)...")
                                         audit1, p_audit1 = red_expert.audit(c_snap, c1, prompts, is_final=False, raw_context=preview_data['user_p'])
                                         step_logs.append(f"### [Red Team Audit 1]\n{audit1}")
                                         round_history.append(f"【回合 2 (一审审计)】\n审计报告: {audit1}")
                                         
                                         # Step 3: Blue Refinement (v2)
                                         status.write(f"🔄 Step 3: {blue_model} 进行反思与优化 (Refining)...")
                                         c2, r2, p_refine = blue_expert.refine(preview_data['user_p'], c1, audit1, prompts)
                                         step_logs.append(f"### [v2.0 Refined Strategy]\n{c2}")
                                         round_history.append(f"【回合 3 (优化反思)】\n反思逻辑: {r2}\n优化建议: {c2}")
                                         
                                         # Step 4: Red Audit 2 (Final)
                                         status.write(f"⚖️ Step 4: {red_model} 进行终极裁决 (Final Verdict)...")
                                         audit2, p_audit2 = red_expert.audit(c_snap, c2, prompts, is_final=True, raw_context=preview_data['user_p'])
                                         step_logs.append(f"### [Final Verdict]\n{audit2}")
                                         round_history.append(f"【回合 4 (红军终审)】\n最终裁决: {audit2}")
                                         
                                         # Step 5: Blue Final Decision (The Order)
                                         status.write(f"🏁 Step 5: {blue_model} 签署最终执行令 (Final Execution)...")
                                         c3, r3, p_decide = blue_expert.decide(round_history, prompts, context_data=c_snap)
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
                    
                    # --- Parse Cumulative Result ---
                    cumulative_data = {}
                    main_display_text = res_text
                    
                    # Markers
                    markers = {
                        'draft': "--- 📜 v1.0 Draft ---",
                        'audit1': "--- 🔴 Round 1 Audit ---",
                        'refine': "--- 🔄 v2.0 Refined ---",
                        'audit2': "--- ⚖️ Final Verdict ---",
                        'final_marker': "[Final Execution Order]"
                    }
                    
                    if markers['draft'] in res_text:
                        # It's a cumulative log
                        try:
                            # Split by Draft First to get the Head (Final Decision)
                            parts = res_text.split(markers['draft'])
                            main_display_text = parts[0].strip()
                            remaining = parts[1] if len(parts) > 1 else ""
                            
                            # Extract Draft
                            if markers['audit1'] in remaining:
                                p_draft = remaining.split(markers['audit1'])
                                cumulative_data['draft'] = p_draft[0].strip()
                                remaining = p_draft[1]
                            
                            # Extract Audit1
                            if markers['refine'] in remaining:
                                p_a1 = remaining.split(markers['refine'])
                                cumulative_data['audit1'] = p_a1[0].strip()
                                remaining = p_a1[1]
                                
                            # Extract Refine
                            if markers['audit2'] in remaining:
                                p_ref = remaining.split(markers['audit2'])
                                cumulative_data['refine'] = p_ref[0].strip()
                                cumulative_data['audit2'] = p_ref[1].strip()
                        except:
                            pass # Fallback to showing everything if parse fails

                    from components.strategy_display_helper import display_strategy_content
                    display_strategy_content(main_display_text)
                    
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
                            # import json # Moved to top level
                            try:
                                details = json.loads(details_json)
                                if isinstance(details, dict) and 'prompts_history' in details:
                                    has_details = True
                                    ph = details['prompts_history']
                                    with st.expander("📝 全流程详情 (Full Process History)", expanded=True):
                                        h_tab1, h_tab2, h_tab3, h_tab4, h_tab5 = st.tabs(["Draft (草案)", "Audit1 (初审)", "Refine (反思)", "Audit2 (终审)", "Final (决策)"])
                                        
                                        def show_prompt_in_tab(tab, ph_data, prefix, title="Prompt", result_content=None):
                                            with tab:
                                                if result_content:
                                                    st.markdown(f"#### 🧠 {title} Result")
                                                    st.markdown(result_content)
                                                    st.divider()

                                                sys_p = ph_data.get(f"{prefix}_sys")
                                                user_p = ph_data.get(f"{prefix}_user")
                                                
                                                # Fallback for old keys or auto-drive single keys
                                                combined = ph_data.get(prefix)
                                                
                                                if sys_p or user_p:
                                                    if sys_p:
                                                        st.caption("System Prompt")
                                                        st.code(sys_p, language='text')
                                                    if user_p:
                                                        st.caption("User Prompt")
                                                        st.code(user_p, language='text')
                                                elif combined:
                                                    st.caption(f"{title} (Combined)")
                                                    st.code(combined, language='text')
                                                else:
                                                    st.caption("No prompt data available for this step.")

                                        show_prompt_in_tab(h_tab1, ph, "draft", "Draft", cumulative_data.get('draft'))
                                        show_prompt_in_tab(h_tab2, ph, "audit1", "Audit Round 1", cumulative_data.get('audit1'))
                                        show_prompt_in_tab(h_tab3, ph, "refine", "Refinement", cumulative_data.get('refine'))
                                        
                                        with h_tab4:
                                            res_a2 = cumulative_data.get('audit2')
                                            if 'final_sys' in ph or 'final_user' in ph:
                                                show_prompt_in_tab(st, ph, "final", "Final Verdict", res_a2) 
                                            else:
                                                show_prompt_in_tab(st, ph, "audit2", "Final Verdict", res_a2)

                                        with h_tab5:
                                            # Final Decision is mainly displayed above, but we can show it here too if needed
                                            # But usually 'main_display_text' is the final decision.
                                            if 'exec_sys' in ph or 'exec_user' in ph:
                                                show_prompt_in_tab(st, ph, "exec", "Final Decision")
                                            elif 'decision_sys' in ph:
                                                show_prompt_in_tab(st, ph, "decision", "Final Decision")
                                            else:
                                                show_prompt_in_tab(st, ph, "decide", "Final Decision")
                            except:
                                pass
                        
                        if not has_details and "# 🧠 Round 1: Strategy Draft" in p_text:
                            with st.expander("📝 全流程详情 (Full Process History - Legacy)", expanded=True):
                                # 使用完整的 section marker 进行切割，避免被内容中的 --- 截断
                                h_tab1, h_tab2, h_tab3, h_tab4 = st.tabs(["1. Draft (草案)", "2. Audit (初审)", "3. Refine (反思)", "4. Final (决策)"])
                                
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
                                    st.caption("🔵 Blue Team - Initial Strategy Proposal")
                                    # 使用 section marker 而非 --- 作为边界
                                    s1 = extract_section(p_text, "# 🧠 Round 1: Strategy Draft", "# 🛡️ Round 1: Red Audit")
                                    st.code(s1, language='text')

                                with h_tab2:
                                    st.caption("🔴 Red Team - Risk & Consistency Audit (Round 1)")
                                    s2 = extract_section(p_text, "# 🛡️ Round 1: Red Audit", "# 🔄 Round 2: Refinement")
                                    st.code(s2, language='text')

                                with h_tab3:
                                    st.caption("🔵 Blue Team - Refined Strategy based on Audit")
                                    s3 = extract_section(p_text, "# 🔄 Round 2: Refinement", "# ⚖️ Final Verdict")
                                    st.code(s3, language='text')
                                    
                                with h_tab4:
                                    st.caption("⚖️ Blue Commander - Final Signature")
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
