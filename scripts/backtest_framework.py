import pandas as pd
import numpy as np
import os
import json
from datetime import datetime

class PerformanceAnalyzer:
    """
    量化绩效分析核心骨架 (P0阶段支撑模块)。
    为未来的回测及真实交易流水评估提供底层算法库。
    """
    def __init__(self, initial_capital=100000.0):
        self.initial_capital = initial_capital
        
    def calculate_metrics(self, daily_pnl: list) -> dict:
        """
        根据每日盈亏序列计算核心量化指标
        daily_pnl: [{'date': '2023-01-01', 'pnl': 100}, ...]
        """
        if not daily_pnl:
            return {
                "total_return_pct": 0.0,
                "win_rate": 0.0,
                "win_loss_ratio": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "total_trades_days": 0
            }
            
        df = pd.DataFrame(daily_pnl)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # 1. 胜率计算
        winning_days = len(df[df['pnl'] > 0])
        total_days = len(df)
        win_rate = winning_days / total_days if total_days > 0 else 0
        
        # 2. 盈亏比计算 (Profit & Loss Ratio)
        avg_profit = df[df['pnl'] > 0]['pnl'].mean() if winning_days > 0 else 0
        losing_days = len(df[df['pnl'] < 0])
        avg_loss = abs(df[df['pnl'] < 0]['pnl'].mean()) if losing_days > 0 else 0
        pl_ratio = avg_profit / avg_loss if avg_loss > 0 else (999.0 if avg_profit > 0 else 0.0)
        
        # 3. 最大回撤计算 (Max Drawdown)
        df['cumulative_pnl'] = df['pnl'].cumsum()
        df['equity'] = self.initial_capital + df['cumulative_pnl']
        df['peak'] = df['equity'].cummax()
        df['drawdown'] = (df['peak'] - df['equity']) / df['peak']
        max_drawdown = df['drawdown'].max()
        
        # 4. 夏普比率计算 (Sharpe Ratio), 假设 252 个交易日，无风险利率 3%
        daily_returns = df['equity'].pct_change().dropna()
        if len(daily_returns) > 1:
            mean_return = daily_returns.mean()
            std_return = daily_returns.std()
            sharpe_ratio = (mean_return * 252 - 0.03) / (std_return * np.sqrt(252)) if std_return > 0 else 0.0
        else:
            sharpe_ratio = 0.0
            
        return {
            "total_return_pct": (df['equity'].iloc[-1] / self.initial_capital) - 1,
            "win_rate": win_rate,
            "win_loss_ratio": pl_ratio,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "total_trades_days": total_days
        }

    def generate_report(self, ai_metrics: dict, human_metrics: dict, output_dir: str = "reports"):
        """
        生成人机对照 Markdown 报告并保存为 JSON/MD
        """
        # 获取与当前脚本相对路径平齐的 reports 文件夹
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        target_dir = os.path.join(base_dir, output_dir)
        
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate Markdown Data
        md_content = f"""# 📈 A股量化盯盘系统 - 策略绩效评估报告

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**模型配置**: DeepSeek/Kimi 等AI策略执行记录对照人类基准

---

## 📊 核心量化指标对抗 (AI vs 人类)

| 测评维度 | 🤖 AI自动化策略 | 🧑 模拟/人类基准组 | 当期优胜 |
|:---|:---:|:---:|:---:|
| **累计净收益率** | **{ai_metrics.get('total_return_pct', 0)*100:.2f}%** | {human_metrics.get('total_return_pct', 0)*100:.2f}% | {'🤖 AI' if ai_metrics.get('total_return_pct', 0) > human_metrics.get('total_return_pct', 0) else '🧑 人类'} |
| **交易胜率 (Win Rate)** | **{ai_metrics.get('win_rate', 0)*100:.2f}%** | {human_metrics.get('win_rate', 0)*100:.2f}% | {'🤖' if ai_metrics.get('win_rate', 0) > human_metrics.get('win_rate', 0) else '🧑'} |
| **盈亏比 (P/L Ratio)** | **{ai_metrics.get('win_loss_ratio', 0):.2f}** | {human_metrics.get('win_loss_ratio', 0):.2f} | {'🤖' if ai_metrics.get('win_loss_ratio', 0) > human_metrics.get('win_loss_ratio', 0) else '🧑'} |
| **最大回撤 (Max Drawdown)** | **{ai_metrics.get('max_drawdown', 0)*100:.2f}%** | {human_metrics.get('max_drawdown', 0)*100:.2f}% | {'🤖' if ai_metrics.get('max_drawdown', 0) < human_metrics.get('max_drawdown', 1) else '🧑'} |
| **夏普比率 (Sharpe Ratio)** | **{ai_metrics.get('sharpe_ratio', 0):.2f}** | {human_metrics.get('sharpe_ratio', 0):.2f} | {'🤖' if ai_metrics.get('sharpe_ratio', 0) > human_metrics.get('sharpe_ratio', 0) else '🧑'} |

> ℹ️ *风险提示: [最大回撤]代表极端亏损水平，该数值越低说明防御能力越强。[夏普比率]衡量承受单位风险获得的超额回报，越高说明风险性价比越好。*

---
        """
        # 保存 Markdown
        md_path = os.path.join(target_dir, f"report_{timestamp}.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
            
        # 保存 JSON 进行机器归档
        json_path = os.path.join(target_dir, f"report_{timestamp}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": timestamp,
                "ai_metrics": ai_metrics,
                "human_metrics": human_metrics
            }, f, ensure_ascii=False, indent=4)
            
        return md_path, json_path

if __name__ == "__main__":
    # 模拟沙盘数据演示 (Smoke Test)
    analyzer = PerformanceAnalyzer(initial_capital=500000)
    
    test_ai_pnl = [
        {'date': '2023-11-01', 'pnl': 2500},
        {'date': '2023-11-02', 'pnl': -1200},
        {'date': '2023-11-03', 'pnl': 3800},
        {'date': '2023-11-04', 'pnl': -500},
        {'date': '2023-11-05', 'pnl': 4200}
    ]
    test_human_pnl = [
        {'date': '2023-11-01', 'pnl': -1000},
        {'date': '2023-11-02', 'pnl': -3000},
        {'date': '2023-11-03', 'pnl': 5000},
        {'date': '2023-11-04', 'pnl': -2400},
        {'date': '2023-11-05', 'pnl': 800}
    ]
    
    print("正在执行演算对比...")
    ai_m = analyzer.calculate_metrics(test_ai_pnl)
    hu_m = analyzer.calculate_metrics(test_human_pnl)
    md_file, json_file = analyzer.generate_report(ai_m, hu_m)
    
    print(f"✅ 生成回测分析报告成功:\n - {md_file}\n - {json_file}")
