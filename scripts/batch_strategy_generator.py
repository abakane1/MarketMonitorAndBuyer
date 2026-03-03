import os
import sys
import time
import json
import datetime
import schedule
import logging

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import load_config, get_allocation
from utils.database import db_get_position, db_get_history
from utils.storage import save_production_log, load_minute_data
from utils.prompt_manager import prompt_manager
from utils.expert_registry import ExpertRegistry
from utils.time_utils import get_beijing_time, get_target_date_for_strategy, is_trading_time
from utils.data_fetcher import get_stock_realtime_info, aggregate_minute_to_daily, get_price_precision, analyze_intraday_pattern, get_stock_fund_flow, get_stock_fund_flow_history, get_stock_news_raw
from utils.intel_manager import get_claims_for_prompt
from utils.intelligence_processor import summarize_intelligence
from utils.indicators import calculate_indicators
from utils.strategy import analyze_volume_profile_strategy
from utils.storage import get_volume_profile

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_strategy_for_stock(code, name, config, prompts, api_keys):
    """为单只股票生成策略并入库"""
    logger.info(f"开始为 {name}({code}) 生成策略...")
    
    # 获取实时信息和持仓信息
    realtime_info = get_stock_realtime_info(code)
    if not realtime_info:
        logger.error(f"无法获取 {name}({code}) 的实时行情数据，跳过策略生成。")
        return False
        
    price = realtime_info.get('price', 0.0)
    pre_close = realtime_info.get('pre_close', 0.0)
    
    pos_data = db_get_position(code)
    shares_held = pos_data.get("shares", 0)
    avg_cost = pos_data.get("cost", 0.0)
    base_shares = pos_data.get("base_shares", 0)
    tradable_shares = max(0, shares_held - base_shares)
    
    # 资金和风控配置
    settings = config.get("settings", {})
    total_capital = float(settings.get("total_capital", 1000000))
    risk_pct = float(settings.get("risk_pct", 0.05))
    proximity_pct = float(settings.get("proximity_pct", 0.03))
    
    current_alloc = get_allocation(code)
    eff_capital = float(current_alloc) if float(current_alloc) > 0 else total_capital
    available_cash = max(0.0, eff_capital - shares_held * price)
    
    # 量价和技术指标分析
    vol_profile_for_strat, _ = get_volume_profile(code)
    strat_res = analyze_volume_profile_strategy(
        price, vol_profile_for_strat, eff_capital, risk_pct, current_shares=shares_held, proximity_threshold=proximity_pct
    )
    
    # 获取用户近期操作历史
    try:
        user_history = db_get_history(code)
        valid_types = ['buy', 'sell', 'override', '买入', '卖出']
        tx_history = [h for h in user_history if h.get('type') in valid_types]
        recent_actions = tx_history[-3:] if tx_history else []
        action_strs = []
        for act in recent_actions:
            ts = act.get('timestamp', '')[:16]
            t_type = act.get('type', 'N/A')
            act_name = "买入" if t_type in ['buy', '买入'] else ("卖出" if t_type in ['sell', '卖出'] else "修正")
            amt = int(act.get('amount', 0))
            prc = act.get('price', 0)
            action_strs.append(f"{ts} {act_name} {amt}股@{prc}")
        user_actions_summary = "; ".join(action_strs) if action_strs else "无近期操作记录"
    except Exception as e:
        logger.error(f"获取操作历史记录失败: {e}")
        user_actions_summary = "获取记录失败"

    # 构建基础上下文
    limit_base_price = price if datetime.datetime.now().time() > datetime.time(15, 0) else (pre_close if pre_close > 0 else price)
    
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
        "shares": shares_held,
        "available_cash": available_cash,
        "support": strat_res.get('support'), 
        "resistance": strat_res.get('resistance'), 
        "signal": strat_res.get('signal'),
        "reason": strat_res.get('reason'), 
        "quantity": strat_res.get('quantity'),
        "target_position": strat_res.get('target_position', 0),
        "stop_loss": strat_res.get('stop_loss'), 
        "capital_allocation": current_alloc,
        "total_capital": total_capital, 
        "user_actions_summary": user_actions_summary
    }

    # 获取行情和情报数据
    raw_claims = get_claims_for_prompt(code)
    news_items = get_stock_news_raw(code)
    
    final_research_context = raw_claims
    if news_items:
        full_news_text = "".join([n.get('title','')+n.get('content','') for n in news_items])
        if len(full_news_text) > 1000 or len(news_items) > 5:
            # Note: Requires DeepSeek API Key for summarization
            ds_key = api_keys.get("deepseek_api_key")
            if ds_key:
                summary_intel = summarize_intelligence(ds_key, news_items, name)
                if summary_intel:
                    final_research_context += f"\n\n【最新市场情报摘要】\n{summary_intel}"
        else:
             news_str = ""
             for n in news_items[:5]:
                 news_str += f"- {n.get('date')} {n.get('title')}\n"
             final_research_context += f"\n\n【最新新闻】\n{news_str}"

    minute_df = load_minute_data(code)
    tech_indicators = calculate_indicators(minute_df)
    tech_indicators["daily_stats"] = aggregate_minute_to_daily(minute_df, precision=get_price_precision(code))
    intraday_pattern = analyze_intraday_pattern(minute_df)
    ff_history_prompt = get_stock_fund_flow_history(code, force_update=True)
    fund_flow_data = get_stock_fund_flow(code)

    # 确定生成的后缀类型（盘前、午间、复盘）
    now_time = datetime.datetime.now().time()
    if now_time >= datetime.time(15, 0):
        target_suffix_key = "proposer_premarket_suffix"
        strategy_tag = "【盘后复盘(批量)】"
    elif datetime.time(11, 30) <= now_time <= datetime.time(13, 0):
        target_suffix_key = "proposer_noon_suffix"
        strategy_tag = "【午间复盘(批量)】"
    else:
        target_suffix_key = "proposer_premarket_suffix"
        strategy_tag = "【盘中对策(批量)】"

    # 选择模型
    blue_model = "Kimi" if api_keys.get("kimi_api_key") else "DeepSeek"
    red_model = "DeepSeek" if api_keys.get("deepseek_api_key") else ("Kimi" if api_keys.get("kimi_api_key") else "None")
    
    if blue_model == "DeepSeek" and not api_keys.get("deepseek_api_key"):
        logger.error("未找到任何可用的 API Key 用于策略生成。")
        return False

    blue_expert = ExpertRegistry.get_expert(blue_model, api_keys)
    red_expert = ExpertRegistry.get_expert(red_model, api_keys) if red_model != "None" else None

    # 初始化生成上下文
    from utils.ai_advisor import build_advisor_prompt
    sys_p, user_p = build_advisor_prompt(
        context, research_context=final_research_context, 
        technical_indicators=tech_indicators, fund_flow_data=fund_flow_data,
        fund_flow_history=ff_history_prompt, prompt_templates=prompts,
        intraday_summary=intraday_pattern, suffix_key=target_suffix_key, symbol=code
    )

    try:
        # 执行完整的 Auto-Drive 流程
        logger.info(f"[{blue_model} & {red_model}] 开始生成和风控审核循环...")
        
        # 为了 A/B Test 记录版本号
        used_versions = {}
        if isinstance(prompts, tuple) and len(prompts) == 2:
            # 这是一个 (prompts, versions) 的元组，解构它
            prompt_contents, prompt_versions = prompts
            used_versions = prompt_versions
        else:
            prompt_contents = prompts
            used_versions = {k: "unknown" for k in prompt_contents.keys()}
            
        c1, r1, p1, moe_logs = blue_expert.propose(
            context, prompt_contents, 
            research_context=final_research_context,
            raw_context=user_p,
            intraday_summary=intraday_pattern,
            technical_indicators=tech_indicators,
            fund_flow_data=fund_flow_data,
            fund_flow_history=ff_history_prompt
        )
        if "Error" in c1:
            logger.error(f"草案生成失败: {c1}")
            return False
            
        round_history = [f"【回合 1 (草案)】\n思考: {r1}\n建议: {c1}"]
        
        # 可选的风控审查
        audit1_res = ""
        p_audit1 = ""
        audit2_res = ""
        p_audit2 = ""
        c2 = c1
        r2 = ""
        p_refine = ""
        c3 = c1
        r3 = ""
        p_decide = ""

        if red_expert:
            audit1_res, p_audit1 = red_expert.audit(context, c1, prompt_contents, is_final=False, raw_context=user_p)
            round_history.append(f"【回合 2 (一审审计)】\n审计报告: {audit1_res}")
            
            c2, r2, p_refine = blue_expert.refine(user_p, c1, audit1_res, prompt_contents)
            round_history.append(f"【回合 3 (优化反思)】\n反思逻辑: {r2}\n优化建议: {c2}")
            
            audit2_res, p_audit2 = red_expert.audit(context, c2, prompt_contents, is_final=True, raw_context=user_p)
            round_history.append(f"【回合 4 (红军终审)】\n最终裁决: {audit2_res}")
            
            c3, r3, p_decide = blue_expert.decide(round_history, prompt_contents, context_data=context)
        
        # 构建最终结果
        final_result = f"{strategy_tag} {c3}\n\n[Final Execution Order]"
        if red_expert:
            final_result += f"\n\n--- 📜 v1.0 Draft ---\n{c1}"
            final_result += f"\n\n--- 🔴 Round 1 Audit ---\n{audit1_res}"
            final_result += f"\n\n--- 🔄 v2.0 Refined ---\n{c2}"
            final_result += f"\n\n--- ⚖️ Final Verdict ---\n{audit2_res}"

        final_reasoning = ""
        if red_expert:
            final_reasoning = f"### [R1 Reasoning]\n{r1}\n\n### [R2 Refinement]\n{r2}\n\n### [Final Decision]\n{r3}"
        else:
            final_reasoning = f"### [Reasoning]\n{r1}"
            
        if moe_logs: 
            final_reasoning = "\n".join(moe_logs) + "\n" + final_reasoning

        full_prompt_log = f"""
# 🧠 Round 1: Strategy Draft
## System
{sys_p}
## User
{user_p}
"""
        if red_expert:
            full_prompt_log += f"""
---
# 🛡️ Round 1: Red Audit
{p_audit1}

---
# 🔄 Round 2: Refinement
{p_refine}

---
# ⚖️ Final Verdict
{p_audit2}

---
# 🏁 Final Decision
{p_decide}
"""

        # 保存策略记录
        details = {
            'versions': used_versions,
            'prompts_history': {
                'draft_sys': sys_p,
                'draft_user': user_p,
                'audit1': p_audit1,
                'refine': p_refine,
                'audit2': p_audit2,
                'decide': p_decide
            }
        }
        
        save_production_log(
            code, 
            full_prompt_log, 
            final_result, 
            final_reasoning,
            model=blue_model,
            details=json.dumps(details, ensure_ascii=False) if red_expert else None
        )
        logger.info(f"{name}({code}) 策略生成并入库成功。")
        return True

    except Exception as e:
        logger.error(f"{name}({code}) 策略生成过程中发生异常: {e}")
        return False

def run_batch_generation():
    """执行批量生成任务"""
    logger.info("开始执行批量策略生成任务...")
    
    # 获取需要盯盘的股票列表（从 Positions 和 Watchlist 中提取）
    config = load_config()
    settings = config.get("settings", {})
    
    prompts, versions = prompt_manager.get_all(enable_ab_test=True)
    if config.get("prompts"):
        # UI或其余地方动态编辑过覆盖的，暂时丢弃版本特征
        prompts.update(config.get("prompts"))
        for k in config.get("prompts").keys():
            versions[k] = "custom_override"
            
    api_keys = {
        "deepseek_api_key": settings.get("deepseek_api_key"),
        "qwen_api_key": settings.get("qwen_api_key") or settings.get("dashscope_api_key"),
        "kimi_api_key": settings.get("kimi_api_key"),
        "kimi_base_url": settings.get("kimi_base_url")
    }
    
    # 将 prompts 连带 version 信息打包成元组传给下层
    prompts_bundle = (prompts, versions)

    # 我们不仅为关注列表生成，还应当为持仓股票生成
    # 但为简单和明确起见，通常我们获取数据库中持有的股票和 config 里关注的股票
    watchlist = config.get("watchlist", [])
    
    # 为了避免重复，使用集合
    target_stocks = {}
    for item in watchlist:
        target_stocks[item['code']] = item.get('name', '未知')
        
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user_data.db")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT symbol, name FROM positions WHERE shares > 0")
        for row in cur.fetchall():
            target_stocks[row[0]] = row[1] if row[1] else '未知'
        conn.close()
    except Exception as e:
        logger.warning(f"无法读取持仓记录: {e}")

    logger.info(f"目标股票列表: {list(target_stocks.keys())}")
    
    success_count = 0
    for code, name in target_stocks.items():
        if generate_strategy_for_stock(code, name, config, prompts_bundle, api_keys):
            success_count += 1
        # 添加小延迟，避免 API 速率限制
        time.sleep(2)
        
    logger.info(f"批量任务执行完毕，共处理 {len(target_stocks)} 只股票，成功 {success_count} 只。")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cron":
        logger.info("启动定时调度服务...")
        # 配置定时任务
        # 11:30 生成午间复盘
        schedule.every().day.at("11:30").do(run_batch_generation)
        # 15:10 收盘后数据准备阶段结束，开始生成全天复盘
        schedule.every().day.at("15:10").do(run_batch_generation)
        # 你也可以添加更多的时间点
        
        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        # 手动执行一次
        logger.info("执行单词批量任务...")
        run_batch_generation()
