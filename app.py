from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import sqlite3
from pypinyin import pinyin, Style, load_single_dict
import shutil
import os
import atexit
from datetime import datetime
import re

# ====== 新增：多音字姓氏拼音纠错字典 ======
load_single_dict({
    ord('阚'): 'kàn',
    ord('单'): 'shàn',
    ord('解'): 'xiè',
    ord('仇'): 'qiú',
    ord('查'): 'zhā',
    ord('曾'): 'zēng',
    ord('区'): 'ōu',
    ord('朴'): 'piáo',
    ord('繁'): 'pó'
})
# ==========================================

app = Flask(__name__)


# ====== 新增：每次运行结束时的自动备份逻辑 ======
def backup_database():
    """在服务器关闭时自动复制数据库文件，并自动清理过期备份（仅保留最近10个）"""
    if os.path.exists('score_system.db'):
        if not os.path.exists('backups'):
            os.makedirs('backups')

        # 1. 创建新备份
        now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"backups/score_system_backup_{now_str}.db"
        shutil.copy('score_system.db', backup_filename)
        print(f"\n✅ [系统安全提示] 运行已结束！当前数据已自动备份至: {backup_filename}")

        # 2. 清理旧备份，只保留最近 10 个
        try:
            # 获取 backups 目录下所有的 .db 文件，它们按时间命名，所以默认就是按时间排序的
            backups = sorted([f for f in os.listdir('backups') if f.endswith('.db')])

            # 如果备份数量超过 10 个，就把最老的文件删掉，直到只剩 10 个
            while len(backups) > 10:
                oldest_backup = backups.pop(0)  # 拿出排在最前面的（最老的）
                os.remove(os.path.join('backups', oldest_backup))
                print(f"♻️ [系统清理] 已自动删除过期备份: {oldest_backup}")
        except Exception as e:
            print(f"⚠️ [系统清理] 清理旧备份时出错: {e}")


atexit.register(backup_database)
# ===================================================

HTML_PAGE = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>极简分数登记系统</title>

    <script>
        document.addEventListener('visibilitychange', function() {
            if (document.visibilityState === 'visible') {
                location.reload(); 
            }
        });
    </script>

    <style>
        /* 新增：AI助手样式 */
        .ai-btn { background-color: #673AB7; color: white; border-radius: 50%; width: 50px; height: 50px; display: flex; justify-content: center; align-items: center; font-size: 24px; cursor: pointer; box-shadow: 0 4px 15px rgba(103,58,183,0.4); transition: transform 0.2s, box-shadow 0.2s; border: none; }
        .ai-btn:hover { transform: scale(1.1); box-shadow: 0 6px 20px rgba(103,58,183,0.6); }
        .ai-modal-content { display: flex; flex-direction: column; gap: 15px; }
        .ai-input { padding: 12px; font-size: 16px; border: 2px solid #673AB7; border-radius: 8px; outline: none; }

        html { scroll-behavior: smooth; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; max-width: 900px; margin: 0 auto; background-color: #f0f2f5; color: #333;}
        .card { background: white; padding: 20px; margin-bottom: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        h3, h4 { margin-top: 0; color: #2c3e50; }

        select, button, textarea, input[type="text"], input[type="number"] { padding: 10px; margin: 6px 0; width: 100%; box-sizing: border-box; font-size: 15px; border-radius: 6px; border: 1px solid #ccc;}
        .btn-submit { background-color: #4CAF50; color: white; border: none; font-weight: bold; cursor: pointer; margin-top: 10px;}
        .btn-small { padding: 4px 8px; font-size: 12px; border-radius: 4px; border: none; cursor: pointer;}
        .btn-danger { background-color: #ffebee; color: #d32f2f; }

        .class-tabs { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }
        .class-btn { flex: 1; min-width: 80px; padding: 10px; text-align: center; background: #fff; text-decoration: none; color: #555; border-radius: 8px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.05);}
        .class-btn.active { background: #1976d2; color: white; }

        .student-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 15px; }
        @media (max-width: 600px) { .student-grid { grid-template-columns: 1fr; } }

        .student-card { background: #fff; padding: 12px 15px; border-radius: 8px; border: 1px solid #e0e0e0; display: flex; justify-content: space-between; align-items: center; position: relative; cursor: default; transition: box-shadow 0.2s;}
        .student-card:hover { box-shadow: 0 6px 12px rgba(0,0,0,0.1); border-color: #bbdefb;}
        .score { font-weight: bold; color: #e74c3c; font-size: 18px;}
        .custom-checkbox { width: 18px; height: 18px; cursor: pointer; margin: 0; }

        @keyframes blink-highlight {
            0% { background-color: #fff; box-shadow: 0 0 0px #2196F3; }
            50% { background-color: #e3f2fd; box-shadow: 0 0 15px #2196F3; border-color: #2196F3; }
            100% { background-color: #fff; box-shadow: 0 0 0px transparent; }
        }
        .blink { animation: blink-highlight 1.5s ease-in-out; }

        .hover-panel { display: none; position: absolute; top: calc(100% + 5px); left: 50%; transform: translateX(-50%); width: 280px; background: #fff; border: 1px solid #ddd; box-shadow: 0 8px 24px rgba(0,0,0,0.15); z-index: 100; padding: 15px; border-radius: 8px;}
        .hover-panel::before { content: ""; position: absolute; top: -15px; left: 0; width: 100%; height: 15px;}
        .student-card:hover .hover-panel, .hover-panel:hover { display: block; }
        .hover-title-link { display: block; text-decoration: none; color: inherit; border-bottom: 1px solid #eee; padding-bottom: 8px; margin-bottom: 10px; transition: color 0.2s; }
        .hover-title-link:hover { color: #2196F3; }

        details { background: #fff8e1; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        summary { font-weight: bold; cursor: pointer; color: #f57c00; outline: none; font-size: 16px;}
        .settings-section { background: white; padding: 15px; border-radius: 8px; margin-top: 10px; border: 1px solid #ffe0b2;}
        hr { border: 0; border-top: 1px dashed #ccc; margin: 15px 0;}

        .floating-btn-group { position: fixed; bottom: 30px; right: 30px; display: flex; flex-direction: column; gap: 10px; z-index: 1000; align-items: center;}
        .float-btn { width: 50px; height: 50px; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 24px; font-weight: bold; text-decoration: none; box-shadow: 0 4px 10px rgba(0,0,0,0.2); transition: transform 0.2s, background-color 0.2s; cursor: pointer; border: none;}
        .float-btn:hover { transform: translateY(-3px); }
        .btn-rank { background-color: #FF9800; color: white; }
        .btn-rank:hover { background-color: #F57C00; }
        .btn-top { background-color: #2196F3; color: white; }
        .btn-top:hover { background-color: #1976d2; }

        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 2000; align-items: center; justify-content: center; backdrop-filter: blur(3px);}
        .modal-content { background: white; padding: 25px; border-radius: 12px; width: 90%; max-width: 400px; max-height: 80vh; overflow-y: auto; position: relative; box-shadow: 0 10px 30px rgba(0,0,0,0.2);}

        .detail-table { width: 100%; border-collapse: collapse; text-align: left; margin-top: 10px; }
        .detail-table th { padding: 12px; background-color: #f5f5f5; border-bottom: 2px solid #ddd; color: #555; }
        .detail-table td { padding: 12px; border-bottom: 1px dashed #eee; }

        .keyboard-tip { background: #e8f5e9; color: #2e7d32; padding: 10px; border-radius: 8px; text-align: center; font-size: 14px; margin-top: -5px; margin-bottom: 15px; border: 1px solid #c8e6c9;}
    </style>
</head>
<body id="page-top">
    <h2 style="text-align: center; margin-bottom: 5px;">👩‍🏫 班级计分板</h2>
    <div class="keyboard-tip">⌨️ 小技巧：直接在键盘上按下学生姓名<b>拼音首字母</b>（如's'），即可瞬间定位并高亮！</div>

    <div class="class-tabs">
        {% for c in all_classes %}
        <a href="/?class_name={{ c }}" class="class-btn {% if current_class == c %}active{% endif %}">{{ c }}</a>
        {% endfor %}
    </div>

    <div class="card" style="border-top: 4px solid #4CAF50; position: sticky; top: 10px; z-index: 50;">
        <h3 style="margin-top: 0; display: flex; justify-content: space-between; align-items: center;">
            <span>✨ 批量快速登记 (当前: {{ current_class }})</span>
            <span style="font-size: 14px; color: #666; font-weight: normal;">👇 第一步：勾选下方学生</span>
        </h3>
        <form id="batchScoreForm" action="/add_score" method="POST" style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center;" onsubmit="return document.querySelectorAll('input[name=\\'student_ids\\']:checked').length > 0 ? true : (alert('⚠️ 请至少在下方勾选一名学生！') || false);">
            <input type="hidden" name="current_class" value="{{ current_class }}">
            <select name="item_id" required style="flex: 2; min-width: 200px; margin: 0;">
                <option value="">-- 第二步：选择加减分项目 --</option>
                {% for item in items %}
                <option value="{{ item[0] }}">{{ item[1] }} ({{ item[2] }}分)</option>
                {% endfor %}
            </select>
            <button type="submit" class="btn-submit" style="flex: 1; margin: 0; min-width: 100px;">✅ 提交选中分数</button>
        </form>
    </div>

    <h3 style="margin-top: 30px; margin-bottom: 0;">📋 班级名单 <span style="font-size: 14px; font-weight: normal; color: #888;">(已按拼音 A-Z 排序)</span></h3>
    <div class="student-grid">
        {% for student in students %}
        <div class="student-card" data-pinyin="{{ student_initials[student[0]] }}">
            <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; margin: 0; overflow: hidden;">
                <input type="checkbox" name="student_ids" value="{{ student[0] }}" form="batchScoreForm" class="custom-checkbox" style="flex-shrink: 0;">
                <strong style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ student[2] }}</strong>
            </label>
            
            <div style="text-align: right; line-height: 1.2; flex-shrink: 0; margin-left: 10px;">
                <span class="score">{{ student[3] }} 分</span><br>
                <span style="font-size: 12px; color: #aaa; font-family: monospace;">
                    <span style="color: #4CAF50;" title="累计加分">+{{ student[4] }}</span> | <span style="color: #e74c3c;" title="累计扣分">{{ student[5] }}</span>
                </span>
            </div>
            <div class="hover-panel">
                <a href="/?class_name={{ current_class }}&view_all_id={{ student[0] }}#bottom-detail-section" class="hover-title-link">
                    <h4 style="margin: 0; display: flex; justify-content: space-between; align-items: center;">
                        <span>📅 【{{ student[2] }}】明细</span>
                        <span style="font-size: 12px; color: #2196F3; font-weight: normal;">🔍 点击查看全部</span>
                    </h4>
                </a>

                {% if student[0] in student_logs %}
                    {% for log in student_logs[student[0]] %}
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; font-size: 14px; border-bottom: 1px dashed #eee; padding-bottom: 5px;">
                        <div>
                            <span style="color: #999; font-size: 12px;">{{ log[4][5:16] }}</span><br>
                            <strong>{{ log[2] }}</strong> ({{ log[3] }}分)
                        </div>
                        <form action="/delete_log" method="POST" style="margin: 0;">
                            <input type="hidden" name="log_id" value="{{ log[0] }}">
                            <input type="hidden" name="current_class" value="{{ current_class }}">
                            <button type="submit" class="btn-small btn-danger" onclick="return confirm('确定撤销吗？');">撤销</button>
                        </form>
                    </div>
                    {% endfor %}
                {% else %}
                    <p style="color: #999; text-align: center; font-size: 14px;">近期无记录</p>
                {% endif %}
            </div>
        </div>
        {% else %}
        <p style="color: #999; text-align: center; grid-column: span 3;">当前班级没有学生</p>
        {% endfor %}
    </div>

    <details style="margin-top: 40px;">
        <summary>⚙️ 展开高级设置 (加减分项目、班级管理、导入)</summary>

        <div class="settings-section">
            <h4>📝 加减分项目管理</h4>
            <form action="/add_item" method="POST" style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px; align-items: center;">
                <input type="hidden" name="current_class" value="{{ current_class }}">
                <input type="text" name="item_name" placeholder="项目名称(如: 迟到)" required style="flex: 2; min-width: 150px; margin: 0;">
                <input type="number" name="default_score" placeholder="分值(如: -1)" required style="flex: 1; min-width: 80px; margin: 0;">
                <button type="submit" style="background: #FF9800; color: white; border: none; border-radius: 6px; cursor: pointer; padding: 10px 20px; flex: none; width: auto; white-space: nowrap; margin: 0;">➕ 添加新项目</button>
            </form>
            <div style="max-height: 150px; overflow-y: auto;">
                {% for item in items %}
                <div style="display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px dashed #eee;">
                    <span>{{ item[1] }} <strong style="color: #e74c3c;">({{ item[2] }}分)</strong></span>
                    <form action="/delete_item" method="POST" style="margin: 0;">
                        <input type="hidden" name="item_id" value="{{ item[0] }}">
                        <input type="hidden" name="current_class" value="{{ current_class }}">
                        <button type="submit" class="btn-small btn-danger" onclick="return confirm('确定删除该计分项目吗？');">删除</button>
                    </form>
                </div>
                {% endfor %}
            </div>
        </div>

        <div class="settings-section">
            <h4>🏫 班级管理</h4>
            <form action="/rename_class" method="POST" style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px; align-items: center;">
                <select name="old_name" required style="flex: 1; min-width: 120px; margin: 0;">
                    <option value="">-- 选择原班级 --</option>
                    {% for c in all_classes %}
                    <option value="{{ c }}">{{ c }}</option>
                    {% endfor %}
                </select>
                <input type="text" name="new_name" placeholder="输入新名称" required style="flex: 1; min-width: 120px; margin: 0;">
                <button type="submit" style="background:#4CAF50; color:white; border:none; border-radius:6px; cursor:pointer; padding: 10px 20px; flex: none; width: auto; white-space: nowrap; margin: 0;">修改名称</button>
            </form>

            <form action="/delete_class" method="POST" onsubmit="return confirm('危险！确定要彻底删除该班级吗？');" style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center;">
                <select name="class_to_delete" required style="flex: 1; min-width: 200px; margin: 0;">
                    <option value="">-- 选择要彻底删除的班级 --</option>
                    {% for c in all_classes %}
                    <option value="{{ c }}">{{ c }}</option>
                    {% endfor %}
                </select>
                <button type="submit" style="background:#f44336; color:white; border:none; border-radius:6px; cursor:pointer; padding: 10px 20px; flex: none; width: auto; white-space: nowrap; margin: 0;">🗑️ 删除该班级</button>
            </form>
            
            <hr style="border: 0; border-top: 1px dashed #ccc; margin: 15px 0;">
            <h4 style="margin-top: 0;">👤 学生管理</h4>
            <form action="/delete_student" method="POST" onsubmit="return confirm('危险！删除该学生将同时清空其所有的加减分记录，确定吗？');" style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center;">
                <input type="hidden" name="current_class" value="{{ current_class }}">
                <select name="student_id_to_delete" required style="flex: 1; min-width: 200px; margin: 0;">
                    <option value="">-- 选择要删除的本班学生 --</option>
                    {% for student in students %}
                    <option value="{{ student[0] }}">{{ student[2] }} (学号: {{ student[1] }})</option>
                    {% endfor %}
                </select>
                <button type="submit" style="background:#e53935; color:white; border:none; border-radius:6px; cursor:pointer; padding: 10px 20px; flex: none; width: auto; white-space: nowrap; margin: 0;">🗑️ 删除该生</button>
            </form>
            </div>
        </div>

        <div class="settings-section">
            <h4>📥 批量导入学生名单</h4>
            <form action="/import_students" method="POST">
                <input type="hidden" name="current_class" value="{{ current_class }}">
                <textarea name="student_data" rows="3" placeholder="从Excel复制：学号(Tab)姓名(Tab)班级"></textarea>
                <button type="submit" class="btn-submit" style="background:#2196F3;">🚀 一键录入系统</button>
            </form>
        </div>

        <div class="settings-section">
            <h4>🔢 批量导入已有分数</h4>
            <form action="/import_scores" method="POST">
                <input type="hidden" name="current_class" value="{{ current_class }}">
                <textarea name="score_data" rows="3" placeholder="从Excel复制两列：学号(Tab)已有分数  (例如：202601    15)"></textarea>
                <button type="submit" class="btn-submit" style="background:#9C27B0;">⚡ 一键导入分数</button>
            </form>
        </div>
    </details>
    
    </details> <details style="margin-top: 20px; background: #ffebee; border: 1px solid #ffcdd2; border-radius: 8px; padding: 15px;">
        <summary style="color: #d32f2f; font-weight: bold; font-size: 16px; cursor: pointer; outline: none;">
            🚨 遇到问题？点击查看【数据恢复教程】
        </summary>
        <div style="padding: 15px; background: white; border-radius: 8px; margin-top: 15px; border: 1px dashed #ef9a9a; color: #333; line-height: 1.6; font-size: 15px;">
            <h4 style="margin-top: 0; color: #d32f2f;">⏪ 如何将数据恢复到之前的状态？</h4>
            <p style="margin-top: 0;">系统每次关闭时，都会自动把当时的成绩单保存在电脑的 <b>backups</b> 文件夹中（仅保留最近 10 次）。如果数据被不小心搞乱了，请按照以下 4 步无损恢复：</p>
            <ol style="margin-bottom: 0; padding-left: 20px;">
                <li style="margin-bottom: 8px;"><b>关闭系统：</b> 关闭服务器。</li>
                <li style="margin-bottom: 8px;"><b>找到备份：</b> 打开代码所在的文件夹，进入 <code>backups</code> 文件夹，找到你想要恢复的那个时间点的文件（例如：<code>score_system_backup_20260318_163005.db</code>）。</li>
                <li style="margin-bottom: 8px;"><b>替换文件：</b> 把这个备份文件<b>复制</b>到外面一层（和 app.py 在同一个文件夹里），并将其重命名为绝对准确的 <b><code>score_system.db</code></b> （如果提示覆盖原文件，请点击确定）。</li>
                <li><b>重启系统：</b> 重新在黑框框里输入 <code>python app.py</code> 回车，刷新网页，数据就完美穿越回来啦！</li>
            </ol>
        </div>
    </details>

    {% if view_all_id %}
    <div id="bottom-detail-section" class="card" style="margin-top: 40px; border-top: 4px solid #2196F3; background-color: #f4f9ff;">
        <h3>📋 【{{ view_all_name }}】的全部明细</h3>
        <div style="max-height: 400px; overflow-y: auto; background: white; border-radius: 8px; border: 1px solid #ddd;">
            <table class="detail-table">
                <thead><tr><th>时间</th><th>计分项目</th><th>分值变动</th><th>操作</th></tr></thead>
                <tbody>
                    {% for log in view_all_logs %}
                    <tr>
                        <td style="color: #888; font-size: 14px;">{{ log[3] }}</td>
                        <td style="font-weight: bold;">{{ log[1] }}</td>
                        <td style="font-weight: bold; color: {% if log[2] > 0 %}#4CAF50{% else %}#e74c3c{% endif %};">{% if log[2] > 0 %}+{% endif %}{{ log[2] }}</td>
                        <td>
                            <form action="/delete_log" method="POST" style="margin: 0;">
                                <input type="hidden" name="log_id" value="{{ log[0] }}">
                                <input type="hidden" name="current_class" value="{{ current_class }}">
                                <input type="hidden" name="view_all_id" value="{{ view_all_id }}">
                                <button type="submit" class="btn-small btn-danger" onclick="return confirm('确定撤销这条记录吗？');">撤销记录</button>
                            </form>
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="4" style="text-align: center; padding: 30px; color: #999;">无任何加减分记录。</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        <a href="/?class_name={{ current_class }}" style="display: block; text-align: center; margin-top: 20px; color: #555; text-decoration: none; font-weight: bold;">❌ 关闭明细面板</a>
    </div>
    {% endif %}

    <div class="floating-btn-group" style="bottom: 100px;"> 
        <button onclick="document.getElementById('aiModal').style.display='flex'" class="ai-btn" title="呼叫智能助手">✨</button>
        <button onclick="document.getElementById('rankingModal').style.display='flex'" class="float-btn btn-rank" title="查看班级排行榜">🏆</button>
        <a href="#page-top" class="float-btn btn-top" title="回到顶部" style="line-height: 50px; text-align: center;">↑</a>
    </div>

    <div id="aiModal" class="modal-overlay" onclick="if(event.target === this) this.style.display='none'">
        <div class="modal-content ai-modal-content">
            <h3 style="margin-top:0; color: #673AB7;">✨ 智能记分助手</h3>
            <p style="margin: 0; color: #666; font-size: 14px;">支持自然语言，例如：<br><i>“给张三加2分”</i> 或 <i>“李四上课走神扣1分”</i></p>
            <input type="hidden" id="aiCurrentClass" value="{{ current_class }}">
            <textarea id="aiInput" class="ai-input" rows="3" placeholder="请在这里输入您的指令..."></textarea>
            <button onclick="processAICommand()" class="btn-submit" style="background: #673AB7; margin-top: 0;">🚀 分析并生成操作</button>
            <div id="aiResult" style="margin-top: 10px; font-size: 15px; color: #333; white-space: pre-wrap; display: none; background: #f3e5f5; padding: 15px; border-radius: 8px;"></div>
            <button id="aiConfirmBtn" onclick="executeAICommand()" class="btn-submit" style="display: none; background: #4CAF50;">✅ 确定执行</button>
        </div>
    </div>

    <div id="rankingModal" class="modal-overlay" onclick="if(event.target === this) this.style.display='none'">
        <div class="modal-content">
            <h3 style="margin-top:0; border-bottom: 2px solid #eee; padding-bottom: 10px;">🏆 {{ current_class }} 排行榜</h3>
            <button onclick="document.getElementById('rankingModal').style.display='none'" style="position:absolute; top:20px; right:20px; background:none; border:none; font-size:20px; cursor:pointer;">❌</button>

            <div style="margin-top: 15px;">
                {% for student in ranked_students %}
                <div style="display: flex; justify-content: space-between; padding: 10px 5px; border-bottom: 1px dashed #eee; font-size: 16px;">
                    <span>
                        <strong style="color: #888; display: inline-block; width: 25px;">{{ loop.index }}</strong> 
                        {{ student[2] }}
                    </span>
                    <strong style="color: #e74c3c;">{{ student[3] }} 分</strong>
                </div>
                {% else %}
                <p style="text-align: center; color: #999;">暂无数据</p>
                {% endfor %}
            </div>
        </div>
    </div>

    <script>
// ====== AI 助手的交互逻辑 ======
        let pendingCommandPayload = null; 

        async function processAICommand() {
            const text = document.getElementById('aiInput').value;
            const currentClass = document.getElementById('aiCurrentClass').value;
            const resultDiv = document.getElementById('aiResult');
            const confirmBtn = document.getElementById('aiConfirmBtn');
            
            if (!text.trim()) return;
            
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = "⏳ 正在努力解析中...";
            confirmBtn.style.display = 'none';

            try {
                const response = await fetch('/ai_parse', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: text, current_class: currentClass })
                });
                const data = await response.json();

                if (data.status === 'success') {
                    // 改用 flex 而不是 inline-flex，让外层的 grid 来控制宽度
                    let studentCheckboxes = data.matched_students.map(s => 
                        `<label style="display:flex; align-items:center; gap:5px; cursor:pointer; margin:0; overflow:hidden;">
                            <input type="checkbox" class="ai-student-cb" value="${s.id}" style="width:18px; height:18px; margin:0; flex-shrink:0;" checked>
                            <strong style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${s.name}</strong>
                         </label>`
                    ).join('');

                    let color = data.score_change > 0 ? '#4CAF50' : '#e74c3c';
                    let sign = data.score_change > 0 ? '+' : '';

                    // 注意这里的 HTML 代码我都顶格写了，这样就不会有奇怪的缩进
                    // 外层包裹的 div 用了 Grid 网格布局，强制均分 3 列
                    resultDiv.innerHTML = `💡 <b>解析成功！</b><br>
                        <strong>将执行：</strong> 因为【${data.item_name}】分值变动 <span style="color:${color}; font-weight:bold;">${sign}${data.score_change}</span> 分。<br>
                        <hr style="border:0; border-top:1px dashed #ccc; margin:10px 0;">
                        <strong style="color:#673AB7;">请确认要执行的学生（可取消勾选）：</strong><br>
                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; padding: 10px 0;">
                            ${studentCheckboxes}
                        </div>`;
                    
                    // 暂存分数和项目ID，等点击确认时再读取勾选的人
                    pendingCommandPayload = {
                        item_id: data.item_id,
                        score_change: data.score_change
                    };
                    confirmBtn.style.display = 'block';   
                } else {
                    resultDiv.innerHTML = data.msg; 
                }
            } catch (err) {
                resultDiv.innerHTML = "❌ 解析失败，请检查网络。";
            }
        }

        async function executeAICommand() {
            if (!pendingCommandPayload) return;

            // 核心升级5：收集当前弹窗里所有被打勾的学生的ID
            const checkedBoxes = document.querySelectorAll('.ai-student-cb:checked');
            if (checkedBoxes.length === 0) {
                alert("⚠️ 请至少保留一名学生！");
                return;
            }

            const studentIds = Array.from(checkedBoxes).map(cb => cb.value);
            pendingCommandPayload.student_ids = studentIds; // 将数组塞入发给后台的包裹中

            try {
                const response = await fetch('/ai_execute', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(pendingCommandPayload)
                });
                const data = await response.json();
                if (data.status === 'success') {
                    location.reload(); 
                } else {
                    alert("执行失败：" + data.msg);
                }
            } catch (err) {
                alert("提交失败！");
            }
        }

        // 键盘快捷键逻辑
        document.addEventListener('keydown', function(e) {
            if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;
            const key = e.key.toLowerCase();
            if (/^[a-z]$/.test(key)) {
                const cards = document.querySelectorAll(`.student-card[data-pinyin="${key}"]`);
                if (cards.length > 0) {
                    const firstCard = cards[0];
                    const rect = firstCard.getBoundingClientRect();
                    const targetY = window.scrollY + rect.top - (window.innerHeight * 0.25);
                    window.scrollTo({ top: targetY, behavior: 'smooth' });
                    cards.forEach(card => {
                        card.classList.remove('blink');
                        void card.offsetWidth; 
                        card.classList.add('blink');
                    });
                }
            }
        });
    </script>
</body>
</html>
"""


def get_db_connection():
    return sqlite3.connect('score_system.db')


@app.route('/')
def home():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT class_name FROM students ORDER BY class_name")
    all_classes = [row[0] for row in cursor.fetchall()]
    if not all_classes:
        all_classes = ['暂无班级']
    current_class = request.args.get('class_name')
    if not current_class or current_class not in all_classes:
        current_class = all_classes[0]

    # 核心升级：利用 SQL 的 CASE 语句，不仅算总分，还分别把正数和负数挑出来求和
    cursor.execute('''
        SELECT s.id, s.student_id, s.name, 
               IFNULL(SUM(l.score_change), 0) as total_score,
               IFNULL(SUM(CASE WHEN l.score_change > 0 THEN l.score_change ELSE 0 END), 0) as positive_score,
               IFNULL(SUM(CASE WHEN l.score_change < 0 THEN l.score_change ELSE 0 END), 0) as negative_score
        FROM students s
        LEFT JOIN score_logs l ON s.id = l.student_id
        WHERE s.class_name = ?
        GROUP BY s.id
    ''', (current_class,))
    raw_students = cursor.fetchall()

    student_initials = {}
    student_pinyin_for_sort = {}

    for s in raw_students:
        sid = s[0]
        name = s[2]
        try:
            full_pinyin_list = pinyin(name, style=Style.NORMAL)
            full_pinyin_str = ''.join([item[0] for item in full_pinyin_list]).lower()
            initial = full_pinyin_str[0] if full_pinyin_str else ''
        except:
            full_pinyin_str = name
            initial = ''

        student_initials[sid] = initial
        student_pinyin_for_sort[sid] = full_pinyin_str

    students = sorted(raw_students, key=lambda x: student_pinyin_for_sort.get(x[0], ''))
    ranked_students = sorted(students, key=lambda x: x[3], reverse=True)

    cursor.execute("SELECT id, item_name, default_score FROM score_items")
    items = cursor.fetchall()

    cursor.execute('''
        SELECT l.id, l.student_id, i.item_name, l.score_change, l.created_at
        FROM score_logs l
        JOIN score_items i ON l.item_id = i.id
        WHERE l.student_id IN (SELECT id FROM students WHERE class_name = ?)
        ORDER BY l.created_at DESC
    ''', (current_class,))
    all_logs = cursor.fetchall()
    student_logs = {}
    for log in all_logs:
        sid = log[1]
        if sid not in student_logs:
            student_logs[sid] = []
        if len(student_logs[sid]) < 5:
            student_logs[sid].append(log)

    view_all_id = request.args.get('view_all_id')
    view_all_logs = []
    view_all_name = ""

    if view_all_id:
        cursor.execute("SELECT name FROM students WHERE id = ?", (view_all_id,))
        name_res = cursor.fetchone()
        if name_res:
            view_all_name = name_res[0]

        cursor.execute('''
            SELECT l.id, i.item_name, l.score_change, l.created_at
            FROM score_logs l
            JOIN score_items i ON l.item_id = i.id
            WHERE l.student_id = ?
            ORDER BY l.created_at DESC
        ''', (view_all_id,))
        view_all_logs = cursor.fetchall()

    conn.close()
    return render_template_string(HTML_PAGE,
                                  students=students, items=items,
                                  current_class=current_class, all_classes=all_classes,
                                  student_logs=student_logs,
                                  view_all_id=view_all_id, view_all_logs=view_all_logs, view_all_name=view_all_name,
                                  ranked_students=ranked_students, student_initials=student_initials)


@app.route('/add_score', methods=['POST'])
def add_score():
    student_ids = request.form.getlist('student_ids')
    item_id = request.form.get('item_id')
    current_class = request.form.get('current_class')

    if student_ids and item_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT default_score FROM score_items WHERE id = ?", (item_id,))
        res = cursor.fetchone()
        if res:
            score_change = res[0]
            for sid in student_ids:
                cursor.execute("INSERT INTO score_logs (student_id, item_id, score_change) VALUES (?, ?, ?)",
                               (sid, item_id, score_change))
        conn.commit()
        conn.close()
    return redirect(url_for('home', class_name=current_class))


@app.route('/delete_log', methods=['POST'])
def delete_log():
    log_id = request.form.get('log_id')
    current_class = request.form.get('current_class')
    view_all_id = request.form.get('view_all_id')
    if log_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM score_logs WHERE id = ?", (log_id,))
        conn.commit()
        conn.close()
    if view_all_id:
        return redirect(url_for('home', class_name=current_class, view_all_id=view_all_id) + "#bottom-detail-section")
    return redirect(url_for('home', class_name=current_class))


@app.route('/add_item', methods=['POST'])
def add_item():
    item_name = request.form.get('item_name')
    default_score = request.form.get('default_score')
    current_class = request.form.get('current_class')
    if item_name and default_score:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO score_items (item_name, default_score) VALUES (?, ?)", (item_name, default_score))
        conn.commit()
        conn.close()
    return redirect(url_for('home', class_name=current_class))


@app.route('/delete_item', methods=['POST'])
def delete_item():
    item_id = request.form.get('item_id')
    current_class = request.form.get('current_class')
    if item_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM score_items WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
    return redirect(url_for('home', class_name=current_class))


@app.route('/rename_class', methods=['POST'])
def rename_class():
    old_name = request.form.get('old_name')
    new_name = request.form.get('new_name').strip()
    if old_name and new_name:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE students SET class_name = ? WHERE class_name = ?", (new_name, old_name))
        conn.commit()
        conn.close()
    return redirect(url_for('home', class_name=new_name))


@app.route('/delete_class', methods=['POST'])
def delete_class():
    class_to_delete = request.form.get('class_to_delete')
    if class_to_delete:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM score_logs WHERE student_id IN (SELECT id FROM students WHERE class_name = ?)",
                       (class_to_delete,))
        cursor.execute("DELETE FROM students WHERE class_name = ?", (class_to_delete,))
        conn.commit()
        conn.close()
    return redirect(url_for('home'))


# ====== 新增核心逻辑：删除单个学生 ======
@app.route('/delete_student', methods=['POST'])
def delete_student():
    student_id_to_delete = request.form.get('student_id_to_delete')
    current_class = request.form.get('current_class')

    if student_id_to_delete:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 为了保证数据库干净，必须先删除这个学生所有的分数流水账
        cursor.execute("DELETE FROM score_logs WHERE student_id = ?", (student_id_to_delete,))
        # 然后再把这个学生从名单里删掉
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id_to_delete,))

        conn.commit()
        conn.close()

    return redirect(url_for('home', class_name=current_class))

@app.route('/import_students', methods=['POST'])
def import_students():
    data = request.form.get('student_data')
    current_class = request.form.get('current_class')

    if data:
        conn = get_db_connection()
        cursor = conn.cursor()
        lines = data.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            parts = line.split('\t')
            if len(parts) < 3:
                parts = line.split()

            if len(parts) >= 3:
                student_id = str(parts[0]).strip()
                name = str(parts[1]).strip()
                class_name = str(parts[2]).strip()

                try:
                    cursor.execute("INSERT INTO students (student_id, name, class_name) VALUES (?, ?, ?)",
                                   (student_id, name, class_name))
                except sqlite3.IntegrityError:
                    cursor.execute("SELECT class_name FROM students WHERE student_id = ?", (student_id,))
                    existing = cursor.fetchone()

                    if existing and existing[0] != class_name:
                        new_student_id = f"{class_name}_{student_id}"
                        try:
                            cursor.execute("INSERT INTO students (student_id, name, class_name) VALUES (?, ?, ?)",
                                           (new_student_id, name, class_name))
                        except sqlite3.IntegrityError:
                            cursor.execute("UPDATE students SET name = ? WHERE student_id = ?",
                                           (name, new_student_id))
                    else:
                        cursor.execute("UPDATE students SET name = ? WHERE student_id = ?",
                                       (name, student_id))

        conn.commit()
        conn.close()

    return redirect(url_for('home', class_name=current_class))


@app.route('/import_scores', methods=['POST'])
def import_scores():
    data = request.form.get('score_data')
    current_class = request.form.get('current_class')

    if data:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM score_items WHERE item_name = '历史分数导入'")
        item_res = cursor.fetchone()
        if not item_res:
            cursor.execute("INSERT INTO score_items (item_name, default_score) VALUES ('历史分数导入', 0)")
            item_id = cursor.lastrowid
        else:
            item_id = item_res[0]

        lines = data.strip().split('\n')
        for line in lines:
            parts = line.split('\t')
            if len(parts) >= 2:
                student_id_str = parts[0].strip()
                try:
                    score_val = float(parts[1].strip())
                except ValueError:
                    continue

                cursor.execute("SELECT id FROM students WHERE student_id = ? AND class_name = ?",
                               (student_id_str, current_class))
                student_res = cursor.fetchone()

                if student_res:
                    internal_sid = student_res[0]
                    cursor.execute("INSERT INTO score_logs (student_id, item_id, score_change) VALUES (?, ?, ?)",
                                   (internal_sid, item_id, score_val))
        conn.commit()
        conn.close()

    return redirect(url_for('home', class_name=current_class))


# ====== 新增：智能助手语义解析与执行逻辑 ======
@app.route('/ai_parse', methods=['POST'])
def ai_parse():
    data = request.json
    text = data.get('text', '')
    current_class = data.get('current_class', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    text_clean = text.replace(" ", "")
    # 获取用户输入指令的纯拼音字符串 (比如：geichenjiahaojiayifen)
    text_pinyin = ''.join([p[0] for p in pinyin(text_clean, style=Style.NORMAL)]).lower()

    cursor.execute("SELECT id, name FROM students WHERE class_name = ?", (current_class,))
    students = cursor.fetchall()

    # 核心升级1：支持多选与拼音模糊匹配
    matched_students = []
    for s in students:
        s_name = s[1]
        s_pinyin = ''.join([p[0] for p in pinyin(s_name, style=Style.NORMAL)]).lower()

        # 如果汉字完全匹配，或者拼音包含在输入的拼音中，都算匹配成功！
        if s_name in text_clean or (s_pinyin and s_pinyin in text_pinyin):
            matched_students.append({'id': s[0], 'name': s_name})

    if not matched_students:
        return jsonify(
            {"status": "error", "msg": "🤖 抱歉，我没有在您的指令中匹配到当前班级的任何学生姓名（支持同音字识别）。"})

    score_match = re.search(r'(加|扣|减|\+|-|加上|减去|扣除)\s*(\d+(?:\.\d+)?|[一二两三四五六七八九十]+)', text)
    if not score_match:
        names_str = "、".join([m['name'] for m in matched_students])
        return jsonify({"status": "error", "msg": f"🤖 我找到【{names_str}】了，但没听懂要加减多少分。"})

    action = score_match.group(1)
    num_str = score_match.group(2)
    cn_map = {'一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
    if num_str in cn_map:
        num = float(cn_map[num_str])
    else:
        try:
            num = float(num_str)
        except ValueError:
            num = 1.0

    final_score = num if action in ['加', '+', '加上'] else -num

    cursor.execute("SELECT id, item_name FROM score_items")
    items = cursor.fetchall()
    matched_item = None
    for item in items:
        if item[1] in text_clean:
            matched_item = {'id': item[0], 'name': item[1]}
            break

    if not matched_item:
        cursor.execute("SELECT id FROM score_items WHERE item_name = '智能助手记分'")
        res = cursor.fetchone()
        if not res:
            cursor.execute("INSERT INTO score_items (item_name, default_score) VALUES ('智能助手记分', 0)")
            item_id = cursor.lastrowid
            conn.commit()
        else:
            item_id = res[0]
        matched_item = {'id': item_id, 'name': '智能助手记分'}

    conn.close()

    # 核心升级2：不再返回写死的字符串，而是把数据打包发给前端自己画多选框
    return jsonify({
        "status": "success",
        "matched_students": matched_students,
        "item_name": matched_item['name'],
        "item_id": matched_item['id'],
        "score_change": final_score
    })


@app.route('/ai_execute', methods=['POST'])
def ai_execute():
    data = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 核心升级3：现在接收到的是一个包含了多人的数组，循环写入数据库
        for sid in data['student_ids']:
            cursor.execute("INSERT INTO score_logs (student_id, item_id, score_change) VALUES (?, ?, ?)",
                           (sid, data['item_id'], data['score_change']))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})


if __name__ == '__main__':
    print("支持 AI 助手功能版服务器已启动！请访问: http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
