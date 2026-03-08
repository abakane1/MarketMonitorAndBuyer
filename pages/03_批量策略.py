# pages/03_批量策略.py
import streamlit as st
import json
import time
from datetime import datetime, timedelta

# 假设 batch_strategy.py 在根目录
import sys
sys.path.append('..')
from batch_strategy import get_generator

st.set_page_config(page_title="批量策略生成", page_icon="📊")

st.title("📊 批量策略生成器")

# 初始化生成器
generator = get_generator()

# 使用 session state 存储状态
if 'generation_started' not in st.session_state:
    st.session_state.generation_started = False

# ========== 关注列表管理 ==========
st.header("📝 关注列表")

watchlist = generator.load_watchlist()

col1, col2 = st.columns([3, 1])

with col1:
    # 显示当前关注列表
    st.write(f"当前关注 **{len(watchlist)}** 只股票:")
    
    for i, stock in enumerate(watchlist):
        cols = st.columns([1, 2, 1, 1])
        with cols[0]:
            st.text(stock['code'])
        with cols[1]:
            stock['name'] = st.text_input("名称", stock.get('name', ''), 
                                          key=f"name_{i}", label_visibility="collapsed")
        with cols[2]:
            stock['priority'] = st.number_input("优先级", 0, 10, 
                                                stock.get('priority', 0), 
                                                key=f"prio_{i}", label_visibility="collapsed")
        with cols[3]:
            if st.button("🗑️", key=f"del_{i}"):
                watchlist.pop(i)
                generator.save_watchlist(watchlist)
                st.rerun()

with col2:
    # 添加新股票
    st.subheader("添加股票")
    new_code = st.text_input("股票代码", placeholder="如: 588710")
    new_name = st.text_input("名称", placeholder="如: 科创50ETF")
    new_priority = st.number_input("优先级", 0, 10, 0)
    
    if st.button("➕ 添加", use_container_width=True):
        if new_code:
            watchlist.append({
                'code': new_code,
                'name': new_name,
                'priority': new_priority
            })
            generator.save_watchlist(watchlist)
            st.success(f"已添加 {new_code}")
            st.rerun()

# 保存修改
if st.button("💾 保存关注列表", use_container_width=True):
    generator.save_watchlist(watchlist)
    st.success("保存成功!")

st.divider()

# ========== 批量生成控制 ==========
st.header("🚀 批量生成")

col1, col2, col3 = st.columns(3)

with col1:
    # 选择日期
    default_date = datetime.now() + timedelta(days=1)
    strategy_date = st.date_input("策略日期", default_date)
    
with col2:
    # 选择股票（可多选）
    stock_options = [f"{s['code']} - {s['name']}" for s in watchlist]
    selected = st.multiselect("选择股票（留空=全部）", stock_options)

with col3:
    st.write("")  # 占位
    st.write("")

# 解析选中的股票代码
selected_codes = None
if selected:
    selected_codes = [s.split(' - ')[0] for s in selected]

# 显示当前队列状态
status = generator.get_status()
queue_status = status['queue']

st.info(f"""
📊 队列状态:  
- ⏳ 等待: {queue_status['pending']}  
- 🔄 运行中: {queue_status['running']}  
- ✅ 完成: {queue_status['completed']}  
- ❌ 失败: {queue_status['failed']}
""")

# 控制按钮
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("▶️ 开始批量生成", type="primary", 
                 disabled=status['running'],
                 use_container_width=True):
        result = generator.start_batch_generation(
            codes=selected_codes,
            date=str(strategy_date)
        )
        if result['success']:
            st.session_state.generation_started = True
            st.success(result['message'])
        else:
            st.error(result['error'])
        st.rerun()

with col2:
    if st.button("⏹️ 停止生成", 
                 disabled=not status['running'],
                 use_container_width=True):
        generator.stop_generation()
        st.warning("已发送停止信号")
        st.rerun()

with col3:
    if st.button("🧹 清理已完成", use_container_width=True):
        generator.queue.clear_completed()
        st.success("已清理")
        st.rerun()

# ========== 进度显示 ==========
if status['running'] or queue_status['completed'] > 0:
    st.header("📈 生成进度")
    
    # 进度条
    total = queue_status['total']
    completed = queue_status['completed'] + queue_status['failed']
    if total > 0:
        progress = completed / total
        st.progress(progress, text=f"{completed}/{total} 完成 ({progress*100:.0f}%)")
    
    # 显示最近的生成结果
    st.subheader("最近结果")
    
    for item in reversed(queue_status['items']):
        with st.expander(f"{item['code']} - {item['name']} ({item['status']})"):
            st.write(f"**状态**: {item['status']}")
            st.write(f"**创建时间**: {item['created_at']}")
            
            if item['status'] == 'completed' and item['result']:
                result = item['result']
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("信号", result.get('signal', 'N/A'))
                with col2:
                    st.metric("置信度", f"{result.get('confidence', 0)*100:.0f}%")
                with col3:
                    st.metric("建议仓位", result.get('position', {}).get('action', 'N/A'))
                
                st.write(f"**推理**: {result.get('reasoning', 'N/A')}")
                
                # 保存到系统按钮
                if st.button(f"💾 保存 {item['code']} 到系统", key=f"save_{item['id']}"):
                    # 这里调用你的保存函数
                    # save_strategy_to_db(item['code'], result)
                    st.success(f"已保存 {item['code']}")
            
            elif item['status'] == 'failed':
                st.error(f"错误: {item.get('error', '未知错误')}")

# 自动刷新
if status['running']:
    st.write("*页面每3秒自动刷新*")
    time.sleep(3)
    st.rerun()
