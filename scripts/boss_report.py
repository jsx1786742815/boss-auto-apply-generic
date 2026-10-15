import sqlite3
import os
import json
from datetime import datetime, timedelta
from collections import Counter

def generate_report(db_path=None, output_format='text'):
    if db_path is None:
        db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'applications.db')
    
    if not os.path.exists(db_path):
        print("No database found")
        return
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    # 今日统计
    c.execute("SELECT COUNT(*) FROM applications WHERE apply_date=?", (today,))
    today_count = c.fetchone()[0]
    
    # 本周统计
    c.execute("SELECT COUNT(*) FROM applications WHERE apply_date > ?", (week_ago,))
    week_count = c.fetchone()[0]
    
    # 本月统计
    c.execute("SELECT COUNT(*) FROM applications WHERE apply_date > ?", (month_ago,))
    month_count = c.fetchone()[0]
    
    # 总计
    c.execute("SELECT COUNT(*) FROM applications")
    total = c.fetchone()[0]
    
    # 去重公司数
    c.execute("SELECT COUNT(DISTINCT company) FROM applications WHERE apply_date=?", (today,))
    today_companies = c.fetchone()[0]
    
    # 今日投递列表（含评分）
    c.execute("SELECT company, position, salary, score FROM applications WHERE apply_date=? ORDER BY score DESC, id", (today,))
    today_jobs = c.fetchall()
    
    # 评分分布
    c.execute("SELECT score FROM applications WHERE apply_date=?", (today,))
    scores = [row[0] for row in c.fetchall() if row[0] > 0]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    # 薪资分布
    c.execute("SELECT salary FROM applications WHERE apply_date=?", (today,))
    salaries = c.fetchall()
    salary_ranges = {'<10K': 0, '10-15K': 0, '15-20K': 0, '20-30K': 0, '30K+': 0, '未知': 0}
    for (sal,) in salaries:
        nums = [int(x) for x in sal.replace('K', '').replace('k', '').split('-') if x.isdigit()]
        if not nums:
            salary_ranges['未知'] += 1
        elif nums[0] < 10:
            salary_ranges['<10K'] += 1
        elif nums[0] < 15:
            salary_ranges['10-15K'] += 1
        elif nums[0] < 20:
            salary_ranges['15-20K'] += 1
        elif nums[0] < 30:
            salary_ranges['20-30K'] += 1
        else:
            salary_ranges['30K+'] += 1
    
    # 高频公司 TOP10
    c.execute("SELECT company, COUNT(*) as cnt FROM applications WHERE apply_date=? GROUP BY company ORDER BY cnt DESC LIMIT 10", (today,))
    top_companies = c.fetchall()
    
    # 历史趋势（最近14天）
    c.execute("SELECT apply_date, COUNT(*) FROM applications WHERE apply_date > ? GROUP BY apply_date ORDER BY apply_date", 
              ((datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d'),))
    trend = c.fetchall()
    
    conn.close()
    
    if output_format == 'json':
        report = {
            'date': today,
            'summary': {
                'today': today_count,
                'today_companies': today_companies,
                'week': week_count,
                'month': month_count,
                'total': total,
                'avg_score': round(avg_score, 1)
            },
            'salary_distribution': salary_ranges,
            'top_companies': [{'company': co, 'count': cnt} for co, cnt in top_companies],
            'trend': [{'date': d, 'count': c} for d, c in trend],
            'jobs': [{'company': co, 'position': pos, 'salary': sal, 'score': sc} for co, pos, sal, sc in today_jobs]
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    
    # Text format
    print("=" * 60)
    print(f"📊 BOSS直聘 投递日报 ({today})")
    print("=" * 60)
    
    print(f"\n📈 概览")
    print(f"  今日投递: {today_count} 个 | 去重公司: {today_companies} 家")
    print(f"  本周投递: {week_count} 个")
    print(f"  本月投递: {month_count} 个")
    print(f"  累计投递: {total} 个")
    print(f"  平均评分: {avg_score:.1f}/100")
    
    print(f"\n💰 薪资分布")
    for range_name, count in salary_ranges.items():
        if count > 0:
            bar = "█" * count
            print(f"  {range_name:8s} {bar} ({count})")
    
    if top_companies:
        print(f"\n🏢 高频公司 TOP10")
        for co, cnt in top_companies:
            print(f"  {co} ({cnt}个职位)")
    
    if trend:
        print(f"\n📉 最近14天趋势")
        for d, cnt in trend:
            bar = "█" * cnt
            print(f"  {d} {bar} ({cnt})")
    
    if today_jobs:
        print(f"\n📋 今日投递列表（按评分排序）")
        for i, (co, pos, sal, sc) in enumerate(today_jobs, 1):
            score_icon = "🔴" if sc < 60 else "🟡" if sc < 80 else "🟢"
            print(f"  {i:3d}. {score_icon} [{sc:2d}分] {pos} @ {co} - {sal}")
    
    print(f"\n{'=' * 60}")

if __name__ == "__main__":
    import sys
    fmt = 'json' if '--json' in sys.argv else 'text'
    generate_report(output_format=fmt)
