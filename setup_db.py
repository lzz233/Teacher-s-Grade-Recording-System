import sqlite3

# 1. 重新连接数据库
conn = sqlite3.connect('score_system.db')
cursor = conn.cursor()

# 2. 创建全新的“学生表”（注意这里多了一个 class_name）
cursor.execute('''
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    class_name TEXT NOT NULL,  -- 这是我们新加的“班级”标签
    status TEXT DEFAULT 'active'
)
''')

# 3. 创建“计分项目表”和“分数流水表”（和之前一样）
cursor.execute('''
CREATE TABLE IF NOT EXISTS score_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT NOT NULL,
    default_score REAL NOT NULL,
    category TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS score_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    score_change REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    note TEXT,
    FOREIGN KEY (student_id) REFERENCES students (id),
    FOREIGN KEY (item_id) REFERENCES score_items (id)
)
''')

# 4. 预先录入四个班级的测试学生
try:
    # 一班学生
    cursor.execute("INSERT INTO students (student_id, name, class_name) VALUES ('101', '赵大', '一班')")
    cursor.execute("INSERT INTO students (student_id, name, class_name) VALUES ('102', '钱二', '一班')")
    # 二班学生
    cursor.execute("INSERT INTO students (student_id, name, class_name) VALUES ('201', '孙三', '二班')")
    cursor.execute("INSERT INTO students (student_id, name, class_name) VALUES ('202', '李四', '二班')")
    # 三班学生
    cursor.execute("INSERT INTO students (student_id, name, class_name) VALUES ('301', '周五', '三班')")
    # 四班学生
    cursor.execute("INSERT INTO students (student_id, name, class_name) VALUES ('401', '吴六', '四班')")

    # 录入常用的计分规则
    cursor.execute("INSERT INTO score_items (item_name, default_score, category) VALUES ('按时交作业', 1, '学习')")
    cursor.execute("INSERT INTO score_items (item_name, default_score, category) VALUES ('课堂积极发言', 2, '学习')")
    cursor.execute("INSERT INTO score_items (item_name, default_score, category) VALUES ('上课走神', -1, '纪律')")
    print("太棒了！带分班功能的新数据库初始化成功！")
except sqlite3.IntegrityError:
    print("数据库已存在。")

conn.commit()
conn.close()