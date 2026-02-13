# -*- coding: utf-8 -*-
import streamlit as st
import time
import json
import re
import datetime
from utils.storage import save_research_log, get_strategy_storage_path, save_daily_strategy
from utils.ai_parser import extract_bracket_content, parse_strategy_with_fallback
from utils.ai_advisor import build_refinement_prompt, build_red_team_prompt, build_final_decision_prompt, call_ai_model
from utils.config import load_config

def render_lab_strategy_panel(context, api_keys, prompts, total_capital=100000.0):
    """
    Renders the Strategy Generation Panel for Lab (Backtest Mode).
    
    Args:
        context (dict): The mock context built by backtest_utils.
        api_keys (dict): Dictionary of API keys.
        prompts (dict): Loaded prompts.
        total_capital (float): Current available capital/cash.
    """
    code = context['code']
    name = context.get('name', 'Unknown')
    target_date = context['date']
    
    # Unique Key Suffix for Lab isolation
    # We use code + date to ensure uniqueness if we ever render multiple days (though unlikely)
    # But usually just code is enough if we clear state on date change.
    # To be safe:
    u_key = f"{code}_{target_date}_lab"
    
    # Initialize Session State for this panel if needed
    pending_key = f"pending_strat_{u_key}"
    
    st.markdown(f"### 🧪 策略生成面板 ({target_date})")
    
    # 0. Context Display (Optional, for debugging/transparency)
    with st.expander("📊 查看模拟行情上下文 (Context Snapshot)", expanded=False):
        st.json(context)

    # 1. Check for Pending Draft
    ai_strat_log = None
    if pending_key in st.session_state:
        ai_strat_log = st.session_state[pending_key]
        st.warning("⚠️ [Lab] 新策略草稿待确认")
        
        # Display Result
        content = ai_strat_log.get('result', '')
        st.markdown(content)
        
        if ai_strat_log.get('reasoning'):
            with st.expander("💭 AI 思考过程", expanded=False):
                st.markdown(ai_strat_log['reasoning'])

        # --- RED TEAM ADUIT ---
        if ai_strat_log.get('audit'):
             with st.expander(f"🔴 {ai_strat_log.get('red_model', 'Qwen')} 风控审查", expanded=True):
                 st.markdown(ai_strat_log['audit'])
         
             # --- REFINEMENT ---
             if not ai_strat_log.get('is_refined'):
                 st.markdown("---")
                 refine_key = f"refine_prev_{u_key}"
                 
                 if refine_key not in st.session_state:
                     if st.button("🔄 [Lab] 优化策略", key=f"btn_ref_{u_key}"):
                         blue_model = ai_strat_log.get('blue_model', 'DeepSeek')
                         sys_p, user_p = build_refinement_prompt(
                             ai_strat_log.get('raw_context', ''),
                             ai_strat_log['result'],
                             ai_strat_log['audit'],
                             prompts
                         )
                         st.session_state[refine_key] = {'sys': sys_p, 'user': user_p, 'model': blue_model}
                        
                         # Capture Prompt
                         if 'prompts_history' not in st.session_state[pending_key]:
                             st.session_state[pending_key]['prompts_history'] = {}
                         st.session_state[pending_key]['prompts_history']['refine_sys'] = sys_p
                         st.session_state[pending_key]['prompts_history']['refine_user'] = user_p
                         
                         st.rerun()
                 else:
                     # Confirm Refine
                     r_data = st.session_state[refine_key]
                     st.info(f"优化指令预览 ({r_data['model']})")
                     # Simplified confirm
                     if st.button("🚀 执行优化", key=f"btn_run_ref_{u_key}"):
                         # Call Model
                         key = api_keys.get(f"{r_data['model'].lower()}_api_key")
                         if not key: st.error("No API Key"); st.stop()
                         
                         with st.spinner("Refining..."):
                             res, reason = call_ai_model(r_data['model'].lower(), key, r_data['sys'], r_data['user'])
                             
                             if "Error" in res: st.error(res)
                             else:
                                 # Update State
                                 st.session_state[pending_key]['draft_v1'] = st.session_state[pending_key]['result']
                                 st.session_state[pending_key]['result'] = f"{res}\n\n[Refined v2.0]"
                                 st.session_state[pending_key]['reasoning'] += f"\n\n--- Refine ---\n{reason}"
                                 st.session_state[pending_key]['is_refined'] = True
                                 del st.session_state[refine_key]
                                 st.rerun()
             
             # --- FINAL VERDICT ---
             if ai_strat_log.get('is_refined'):
                 final_audit_key = f"final_audit_{u_key}"
                 
                 if not ai_strat_log.get('final_audit'):
                     if final_audit_key not in st.session_state:
                         if st.button("⚖️ [Lab] 终极裁决", key=f"btn_fin_{u_key}"):
                             # Build Prompt
                             red_model = ai_strat_log.get('red_model', 'Qwen')
                             # ... logic mostly same as strategy_section
                             # Simplified for Lab: Use generic context or Draft V2
                             history = f"Draft: {ai_strat_log.get('draft_v1','')[:500]}...\nRefine: {ai_strat_log['result']}"
                             
                             audit_ctx = {
                                 "code": code, "name": name, "price": context['price'],
                                 "daily_stats": context['raw_context'],
                                 "deepseek_plan": ai_strat_log['result'],
                                 "history_summary": history
                             }
                             sys_p, user_p = build_red_team_prompt(audit_ctx, prompts, is_final_round=True)
                             st.session_state[final_audit_key] = {'sys': sys_p, 'user': user_p, 'model': red_model}
                            
                             # Capture Prompt
                             if 'prompts_history' not in st.session_state[pending_key]:
                                 st.session_state[pending_key]['prompts_history'] = {}
                             st.session_state[pending_key]['prompts_history']['final_sys'] = sys_p
                             st.session_state[pending_key]['prompts_history']['final_user'] = user_p
                             
                             st.rerun()
                     else:
                         fa_data = st.session_state[final_audit_key]
                         if st.button("🚀 执行裁决", key=f"btn_run_fin_{u_key}"):
                             key = api_keys.get(f"{fa_data['model'].lower()}_api_key")
                             if not key: st.error("No Key"); st.stop()
                             
                             with st.spinner("Verifying..."):
                                 res, _ = call_ai_model(fa_data['model'].lower(), key, fa_data['sys'], fa_data['user'])
                                 if "Error" in res: st.error(res)
                                 else:
                                     st.session_state[pending_key]['final_audit'] = res
                                     del st.session_state[final_audit_key]
                                     st.rerun()
                 
                 else:
                     st.markdown(f"**终极裁决**: {ai_strat_log['final_audit']}")
                     
                     # --- FINAL EXECUTION ---
                     final_exec_key = f"final_exec_{u_key}"
                     if not ai_strat_log.get('final_exec'):
                         if final_exec_key not in st.session_state:
                             if st.button("🏁 [Lab] 签署执行令", key=f"btn_exec_{u_key}"):
                                 blue_model = ai_strat_log.get('blue_model', 'DeepSeek')
                                 
                                 history_chain = [
                                     ai_strat_log.get('draft_v1', 'N/A'),
                                     ai_strat_log.get('audit', 'N/A'),
                                     ai_strat_log['result'],
                                     ai_strat_log['final_audit']
                                 ]
                                 
                                 fin_ctx = {
                                     'code': code, 'name': name, 'price': context['price'],
                                     'shares': 0, 'cost': 0, 'pre_close': context['pre_close'],
                                     'change_pct': (context['price'] - context['pre_close'])/context['pre_close']*100
                                 }
                                 
                                 sys_p, user_p = build_final_decision_prompt(history_chain, prompts, context_data=fin_ctx)
                                 st.session_state[final_exec_key] = {'sys': sys_p, 'user': user_p, 'model': blue_model}
                                
                                 # Capture Prompt
                                 if 'prompts_history' not in st.session_state[pending_key]:
                                     st.session_state[pending_key]['prompts_history'] = {}
                                 st.session_state[pending_key]['prompts_history']['exec_sys'] = sys_p
                                 st.session_state[pending_key]['prompts_history']['exec_user'] = user_p
                                 
                                 st.rerun()
                         else:
                             fe_data = st.session_state[final_exec_key]
                             if st.button("🚀 签署", key=f"btn_run_exec_{u_key}"):
                                 key = api_keys.get(f"{fe_data['model'].lower()}_api_key")
                                 with st.spinner("Signing..."):
                                     res, reason = call_ai_model(fe_data['model'].lower(), key, fe_data['sys'], fe_data['user'])
                                     
                                     full_res = f"{res}\n\n[Final Execution Order]"
                                     full_res += f"\n\n--- Refined ---\n{ai_strat_log['result']}"
                                     full_res += f"\n\n--- Verdict ---\n{ai_strat_log['final_audit']}"
                                     
                                     st.session_state[pending_key]['result'] = full_res
                                     st.session_state[pending_key]['reasoning'] += f"\n\n--- Exec Reason ---\n{reason}"
                                     st.session_state[pending_key]['final_exec'] = res
                                     del st.session_state[final_exec_key]
                                     st.rerun()

        # Audit Trigger (if missing)
        elif not ai_strat_log.get('audit'):
             audit_prev_key = f"audit_prev_{u_key}"
             if audit_prev_key not in st.session_state:
                 if st.button("🛡️ [Lab] 启动风控审查", key=f"btn_audit_{u_key}"):
                     red_model = "Qwen" # Default
                     # Build Prompt
                     # Use 'raw_context' in context
                     audit_ctx = {
                        "code": code, "name": name, "price": context['price'], "date": target_date,
                        "total_capital": total_capital,
                        "daily_stats": context['raw_context'],
                        "capital_flow": context['capital_flow_str'],
                        "research_context": context['research_context'],
                        "intraday_summary": context['intraday_summary'],
                        "deepseek_plan": ai_strat_log['result']
                     }
                     sys_p, user_p = build_red_team_prompt(audit_ctx, prompts, is_final_round=False)
                     st.session_state[audit_prev_key] = {'sys': sys_p, 'user': user_p, 'model': red_model}
                     
                     # Capture Prompt
                     if 'prompts_history' not in st.session_state[pending_key]:
                         st.session_state[pending_key]['prompts_history'] = {}
                     st.session_state[pending_key]['prompts_history']['audit1_sys'] = sys_p
                     st.session_state[pending_key]['prompts_history']['audit1_user'] = user_p
                     
                     st.rerun()
             else:
                 a_data = st.session_state[audit_prev_key]
                 if st.button("🚀 执行审查", key=f"btn_run_audit_{u_key}"):
                     key = api_keys.get(f"{a_data['model'].lower()}_api_key")
                     if not key: st.error("No Key"); st.stop()
                     with st.spinner("Auditing..."):
                         res, _ = call_ai_model(a_data['model'].lower(), key, a_data['sys'], a_data['user'])
                         if "Error" in res: st.error(res)
                         else:
                             st.session_state[pending_key]['audit'] = res
                             st.session_state[pending_key]['red_model'] = a_data['model']
                             del st.session_state[audit_prev_key]
                             st.rerun()

        # Confirm/Discard
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ [Lab] 保存策略", key=f"btn_save_{u_key}"):
                # Save to DB (strategy_logs) so Backtester can find it
                from utils.database import db_save_strategy_log
                
                # Construct Tag/Content
                # We save as a "Simulated" or "Lab" prompt?
                # The timestamp should be the Target Date + 09:25:00 (Pre-market)
                # so it is picked up by the simulator as a pre-market strategy.
                
                # We need to parse target_date. 
                # If target_date is YYYY-MM-DD
                save_ts = f"{target_date} 09:25:00"
                
                db_save_strategy_log(
                    code,
                    st.session_state[pending_key]['prompt'],
                    st.session_state[pending_key]['result'],
                    st.session_state[pending_key]['reasoning'],
                    model=st.session_state[pending_key]['blue_model'],
                    tag="[Lab/Backtest]",
                    custom_timestamp=save_ts, # Force timestamp override
                    details={'prompts_history': st.session_state[pending_key].get('prompts_history', {})}
                )
                
                # Also save to JSON for backup/daily view if needed
                save_daily_strategy(
                    code, target_date, 
                    st.session_state[pending_key]['result'],
                    st.session_state[pending_key]['reasoning'],
                    prompt=st.session_state[pending_key]['prompt']
                )
                
                del st.session_state[pending_key]
                st.success(f"策略已保存！(时间戳: {save_ts})")
                time.sleep(1)
                st.rerun()
        with c2:
            if st.button("🗑️ [Lab] 放弃", key=f"btn_del_{u_key}"):
                del st.session_state[pending_key]
                st.rerun()
                
    else:
        # No pending draft, show Generate button
        st.info(f"您可以基于 {target_date} 的历史数据生成策略。")
        
        # We need to construct the prompt first to show we are ready
        if st.button("⚡ [Lab] 生成历史回测策略", key=f"btn_gen_{u_key}", type="primary"):
            # 1. Build Base Prompt
            # We use 'proposer_premarket_suffix' usually for daily review
            suffix_key = "proposer_premarket_suffix"
            
            # Construct full prompt text
            # We can use build_advisor_prompt from ai_advisor but we need to inject our context
            # Actually build_advisor_prompt takes 'context' dict.
            # We just need to make sure our context has all keys.
            
            # Merge context with derived fields
            gen_ctx = context.copy()
            # Add derived
            gen_ctx['total_capital'] = total_capital
            gen_ctx['shares_held'] = 0 # Lab assumption? or input?
            gen_ctx['avg_cost'] = 0
            # User History
            gen_ctx['user_actions_summary'] = "无历史操作 (Lab Mode)"
            
            from utils.ai_advisor import build_advisor_prompt
            
            sys_p, user_p = build_advisor_prompt(
                context_data=gen_ctx,
                prompt_templates=prompts,
                suffix_key=suffix_key,
                research_context=gen_ctx.get('research_context', '')
            )
            
            # 2. Call AI
            key = api_keys.get("deepseek_api_key")
            if not key: st.error("No DeepSeek Key"); st.stop()
            
            with st.spinner("DeepSeek Thinking (Lab Mode)..."):
                res, reason = call_ai_model("deepseek", key, sys_p, user_p)
                
                if "Error" in res:
                    st.error(res)
                else:
                    # 3. Store in Pending
                    st.session_state[pending_key] = {
                        'result': res,
                        'reasoning': reason,
                        'prompt': user_p,
                        'blue_model': 'DeepSeek',
                        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'raw_context': context['raw_context'], # Save for audit
                        'context_snapshot': context, # Full snapshot
                        'prompts_history': {
                            'draft_sys': sys_p,
                            'draft_user': user_p
                        }
                    }
                    st.rerun()

