import os
import re
from dotenv import load_dotenv
from api.monitor import monitor
from mysql.connector import connect, Error
from typing import Annotated, List
from langchain_core.tools import tool

load_dotenv()


# ---------------------------------------------------------------------------
# SQL 只读守卫
# ---------------------------------------------------------------------------

# Cache for valid table names to avoid repeated metadata queries
_valid_tables_cache: dict = {}


def _get_valid_table_names(config: dict) -> set:
    """
    Get valid table names from database metadata.
    Uses caching to avoid repeated queries.

    Args:
        config: Database configuration dict

    Returns:
        Set of valid table names (lowercase for case-insensitive comparison)
    """
    db_name = config.get("database", "")
    cache_key = f"{config.get('host')}:{config.get('port')}:{db_name}"

    if cache_key in _valid_tables_cache:
        return _valid_tables_cache[cache_key]

    try:
        with connect(**config) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                valid_names = {table[0].lower() for table in tables}
                _valid_tables_cache[cache_key] = valid_names
                return valid_names
    except Exception:
        # If we can't get metadata, return empty set (will reject all)
        return set()


def _validate_table_name(table_name: str, config: dict) -> tuple[bool, str]:
    """
    Validate table name against database metadata.

    Args:
        table_name: The table name to validate
        config: Database configuration dict

    Returns:
        Tuple of (is_valid, actual_table_name or error_message)
    """
    if not table_name or not table_name.strip():
        return False, "表名不能为空"

    # Basic sanitization first
    safe_name = table_name.replace("`", "").replace(";", "").split()[0].strip()

    if not safe_name:
        return False, "无效的表名"

    # Get valid table names from DB metadata
    valid_tables = _get_valid_table_names(config)

    # Case-insensitive check
    if safe_name.lower() not in valid_tables:
        return False, f"数据表 '{table_name}' 不存在或无权访问"

    # Find the actual case-correct table name
    # Need to do this because SQL is case-sensitive for identifiers in some configs
    actual_name = None
    for t in valid_tables:
        if t.lower() == safe_name.lower():
            # Query the actual name from DB
            try:
                with connect(**config) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SHOW TABLES")
                        for row in cursor.fetchall():
                            if row[0].lower() == safe_name.lower():
                                actual_name = row[0]
                                break
            except Exception:
                actual_name = safe_name
            break

    if actual_name is None:
        actual_name = safe_name

    return True, actual_name


_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|RENAME|GRANT|REVOKE"
    r"|LOCK|UNLOCK|CALL|LOAD|HANDLER|IMPORT)\b",
    re.IGNORECASE,
)

_ALLOWED_PREFIX = re.compile(
    r"^\s*(SELECT|SHOW|DESCRIBE|DESC|EXPLAIN|WITH)\b",
    re.IGNORECASE,
)


def _is_read_only_sql(sql: str) -> tuple[bool, str]:
    """
    Reject queries that are obviously not read-only.
    Requires a known read-only leading keyword AND rejects forbidden keywords.
    Returns (True, "") for acceptable queries, (False, reason) otherwise.
    """
    if not sql or not sql.strip():
        return False, "SQL 语句不能为空"

    # Reject multiple statements (semi-colon trick)
    stripped = sql.strip().rstrip(";").strip()
    if ";" in stripped:
        return False, "不允许执行多条 SQL 语句"

    # Positive check: must start with an allowed read-only keyword
    if not _ALLOWED_PREFIX.match(stripped):
        return False, "仅允许 SELECT / SHOW / DESCRIBE / EXPLAIN / WITH 等只读查询"

    # Negative check: reject forbidden keywords anywhere in the statement
    if _FORBIDDEN_KEYWORDS.search(stripped):
        return False, "仅允许 SELECT / SHOW / DESCRIBE / EXPLAIN 等只读查询"

    return True, ""


# 加载配置文件方便后续使用
def get_db_config():
    """Get database configuration from environment variables."""
    config = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "database": os.getenv("MYSQL_DATABASE"),
        "charset": os.getenv("MYSQL_CHARSET", "utf8mb4"),
        "collation": os.getenv("MYSQL_COLLATION", "utf8mb4_unicode_ci"),
        "autocommit": True,
        "sql_mode": os.getenv("MYSQL_SQL_MODE", "TRADITIONAL"),
    }
    # 移除 None 值（核心必要操作）
    config = {k: v for k, v in config.items() if v is not None}

    # 补充：校验核心配置是否存在（可选但推荐）
    required_keys = ["user", "password", "database"]
    missing_keys = [k for k in required_keys if k not in config]
    if missing_keys:
        raise ValueError(f"缺失数据库核心配置：{', '.join(missing_keys)}")

    return config


# 定义查看数据库表的工具
"""
【mysql.connector 核心 API 说明（针对 connect/cursor）】
1. connect 函数：
   - 作用：建立与 MySQL 数据库的连接，返回一个 Connection 对象；
   - 使用方式：connect(**config)，config 为包含 host/user/password 等的字典；
   - 上下文管理器：推荐用 with 语句（with connect(**config) as conn），自动关闭连接，避免资源泄露；
   - 核心属性/方法：
     - conn.cursor(): 创建游标对象（执行 SQL 的核心）；
     - conn.commit(): 提交事务（autocommit=True 时无需手动调用）；
     - conn.close(): 关闭连接（with 语句自动执行）。
2. cursor 游标对象：
   - 作用：执行 SQL 语句、获取查询结果的核心对象；
   - 创建方式：conn.cursor()；
   - 上下文管理器：with conn.cursor() as cursor，自动关闭游标；
   - 核心方法：
     - cursor.execute(sql): 执行单条 SQL 语句（如 SHOW TABLES/SELECT/INSERT）；
     - cursor.executemany(sql, params): 批量执行 SQL 语句（如批量插入）；
     - cursor.close(): 关闭游标（with 语句自动执行）。
3. 【重点】cursor 执行 DQL/DML 后的结果解析：
   ▶ DQL（数据查询语言，如 SELECT/SHOW）：查询类操作，返回「数据结果集」
     - 核心方法：
       1. cursor.fetchall(): 获取所有结果（返回列表，每个元素是元组，如 [(1, '张三'), (2, '李四')]）；
       2. cursor.fetchone(): 获取一条结果（返回元组，如 (1, '张三')，多次调用可遍历所有结果）；
       3. cursor.fetchmany(n): 获取前 n 条结果（返回列表）；
       4. cursor.column_names: 获取查询结果的列名（列表，如 ['id', 'name']）；
     - 解析技巧：将「列名 + 元组结果」转为字典（更易读），如 {'id': 1, 'name': '张三'}。
   ▶ DML（数据操作语言，如 INSERT/UPDATE/DELETE）：修改类操作，无「数据结果集」
     - 核心属性：
       1. cursor.rowcount: 返回受影响的行数（整数，如 INSERT 1 条返回 1，UPDATE 3 条返回 3）；
       2. cursor.lastrowid: INSERT 操作后，返回新增记录的自增 ID（仅对有自增主键的表有效）；
     - 解析技巧：通过 rowcount 判断操作是否生效，lastrowid 获取新增数据的主键。
4. 异常处理：
   - Error: mysql.connector 专属异常类，捕获所有数据库操作异常（如连接失败、SQL 语法错误）；
   - 推荐方式：try-except Error as e 捕获异常，返回友好提示。
"""


@tool
def list_sql_tables() -> Annotated[str, "数据库中可用的表名列表，以逗号分隔"]:
    """
    列出配置的 MySQL 数据库中所有可用的表。
    核心用途：
        AI Agent 需要查看数据库中有哪些表时调用，为后续执行 SQL 查询提供基础信息。
    返回值：
        str: 成功时返回 "可用数据表：表1, 表2, ..."；
             配置缺失时返回错误提示；
             执行异常时返回具体错误信息。
    异常处理：
        捕获数据库连接/执行 SQL 时的所有 Error 异常，返回可读的错误信息，避免 Agent 崩溃。
    """
    # 埋点监控：记录工具调用行为（便于分析工具使用频率）
    monitor.report_tool("数据库表获取工具")
    # 获取数据库配置
    config = get_db_config()
    try:
        # 前置校验：确保必填配置（账号、密码、数据库名）已配置
        if not all(
            [config.get("user"), config.get("password"), config.get("database")]
        ):
            return "错误：数据库配置缺失（缺少MYSQL_USER、MYSQL_PASSWORD、MYSQL_DATABASE配置项）。"
        # 建立数据库连接（with 语句自动管理连接生命周期，无需手动关闭）
        # ** 等价于  connect(host="localhost", port=3306, user="root", password="123456", database="test_db")
        with connect(**config) as conn:
            # 创建游标对象（执行SQL、获取结果的核心对象，with 语句自动关闭）
            with conn.cursor() as cursor:
                # 执行 DQL 语句：查询数据库中所有表名（SHOW TABLES 属于 DQL 范畴）
                cursor.execute("SHOW TABLES")
                # ========== DQL 结果解析 ==========
                # 获取所有查询结果（返回格式：列表嵌套元组，如 [('user',), ('order',)]）
                tables = cursor.fetchall()
                # 处理数据库中无表的情况
                if not tables:
                    return "数据库中未找到任何数据表。"
                # 提取表名（从元组中取出第一个元素，转为易读的字符串列表）
                table_names = [table[0] for table in tables]
                # 返回格式化的表名列表（中文提示更友好）
                return f"可用数据表：{', '.join(table_names)}"
    # 捕获所有数据库相关异常（连接失败、SQL执行错误等）
    except Error as e:
        return f"列出数据表失败：{str(e)}"


@tool
def get_table_data(
    table_name: Annotated[str, "要读取数据的表名"],
) -> Annotated[str, "表的前 100 行数据（CSV 格式）"]:
    """
    读取指定 MySQL 数据表的前 100 行数据，返回 CSV 格式结果。
    """
    # 埋点监控：记录工具调用行为及目标表名
    """
    csv数据结构
    1. 列分隔符	用英文逗号 , 分隔每一列（不能用中文逗号）
    2. 行分隔符	用换行符 \n 分隔每一行数据
    3. 表头（可选）	第一行是列名（id,name,age），可选但推荐加
    4. 数据行	从第二行开始是实际数据，每行字段数和表头一致
    5. 字段类型	所有字段都是字符串（数字也以字符串存储）
    """
    monitor.report_tool("数据库内容浏览工具", {"正在读取的表": table_name})
    # 获取数据库连接配置
    config = get_db_config()

    try:
        # 前置校验：确保数据库账号、密码、库名配置完整
        if not all(
            [config.get("user"), config.get("password"), config.get("database")]
        ):
            return "错误：数据库配置缺失（请检查账号、密码、数据库名）。"

        # Security: Validate table name against DB metadata before executing any SQL
        is_valid, result = _validate_table_name(table_name, config)
        if not is_valid:
            return f"错误：{result}"

        # Use the validated (and case-corrected) table name
        safe_table_name = result

        # Security: Escape any backticks in the validated identifier by doubling them
        # This prevents SQL injection via table names containing backticks
        escaped_table_name = safe_table_name.replace("`", "``")

        # 建立数据库连接（with自动管理连接生命周期，无需手动关闭）
        with connect(**config) as conn:
            # 创建游标（执行SQL、获取结果的核心对象，with自动关闭）
            with conn.cursor() as cursor:
                # 执行查询：读取指定表的前100行数据
                # safe_table_name is validated and backticks are escaped, safe to use with backticks
                cursor.execute(f"SELECT * FROM `{escaped_table_name}` LIMIT 100")

                # 校验结果：cursor.description为空表示表无效/无数据
                # cursor.description 是游标执行SQL后的「结果集元数据」，返回值类型：tuple | None
                # - 有数据/表有效：返回包含列信息的元组（每个元素对应一列的描述）
                # - 无数据/表无效：返回 None
                if cursor.description is None:
                    return f"数据表 {table_name} 为空或表名无效。"

                # 提取列名：从游标描述中获取表的字段名
                # cursor.description 示例（对应user表）：
                # (name, type_code, display_size, internal_size, precision, scale, null_ok)
                # (
                #     ('id', 3, None, 11, 11, 0, False),   # 第一列：id的元数据（字段名、类型、长度等）
                #     ('name', 253, None, 20, 20, 0, True),# 第二列：name的元数据
                #     ('age', 3, None, 11, 11, 0, True)    # 第三列：age的元数据
                # )
                # 代码逻辑：遍历cursor.description的每个元组，取第一个元素（字段名）
                # desc[0] 就是取每个列元组的「字段名」
                # 数据类型：
                #   cursor.description → tuple[tuples, ...]
                #   desc → tuple
                #   desc[0] → str
                #   columns → list[str]
                columns = [desc[0] for desc in cursor.description]
                # columns 示例结果：['id', 'name', 'age']（列表，每个元素是字符串类型的列名）

                # 提取数据行：获取查询结果的所有行（元组列表格式）
                # cursor.fetchall() 会获取SQL执行后的所有数据行
                # 数据类型：
                #   rows → list[tuple, ...]（列表，每个元素是元组，元组内是每行的字段值）
                rows = cursor.fetchall()
                # rows 示例结果：[(1, '张三', 25), (2, '李四', 30)]

                # 转换数据行：将每行元组转为CSV格式字符串
                # 核心逻辑：
                #   1. 遍历rows中的每个元组（每行数据）
                #   2. 用map(str, row)把元组内的所有元素转为字符串（避免数字/字符串混合拼接报错）
                #   3. 用",".join(...)把转成字符串的字段值用逗号连接，形成CSV行
                # 数据类型：
                #   row → tuple（如 (1, '张三', 25)）
                #   map(str, row) → 迭代器（如 ['1', '张三', '25']）
                #   ",".join(...) → str（如 "1,张三,25"）
                #   result → list[str]
                """
                # 示例1：把列表里的每个数字转成浮点数
                nums = [1, 2, 3]
                result = map(float, nums)
                print(list(result))  # 输出：[1.0, 2.0, 3.0]

                # 把row里的每个元素转成字符串
                processed = map(str, row)
                # 转成列表查看结果（迭代器需要转列表才能直观看到）
                print(list(processed))
                # 输出：['1', '张三', '25']
                """
                result = [",".join(map(str, row)) for row in rows]
                # result 示例结果：['1,张三,25', '2,李四,30']

                # 构造CSV表头：列名用逗号分隔
                # 核心逻辑：把columns列表（['id', 'name', 'age']）用逗号连接成字符串
                # 数据类型：
                #   columns → list[str]
                #   header → str
                header = ",".join(columns)
                # header 示例结果："id,name,age"

                # 返回完整CSV数据（表头+数据行，每行换行分隔）
                # 核心逻辑：
                #   1. 表头和数据行之间用换行符\n分隔
                #   2. 数据行之间也用\n分隔（因为result是列表，"\n".join(result)会把列表元素用\n连接）
                # 数据类型：
                #   f"{header}\n" + "\n".join(result) → str（完整的CSV格式字符串）
                return f"{header}\n" + "\n".join(result)
                # 最终返回结果示例（字符串类型）：
                # """
                # id,name,age
                # 1,张三,25
                # 2,李四,30
                # """

    # 捕获数据库操作异常并返回友好提示
    except Error as e:
        # logger.error(f"Failed to read table {table_name}: {str(e)}")
        return f"读取数据表 {table_name} 失败：{str(e)}"


@tool
def execute_sql_query(
    query: Annotated[str, "要执行的 SQL 查询语句（仅支持只读查询）"],
) -> Annotated[str, "查询结果或成功消息"]:
    """在 MySQL 数据库上执行自定义 SQL 查询。仅支持只读查询（SELECT/SHOW/DESCRIBE/EXPLAIN）。"""
    # 读取安全守卫：拒绝写操作 / DDL / 多语句
    ok, reason = _is_read_only_sql(query)
    if not ok:
        return f"错误：{reason}"

    monitor.report_tool("数据库查询工具")
    # 获取数据库连接配置（账号、密码、库名等）
    config = get_db_config()
    # 强制关闭 autocommit，防止隐式写入提交
    config["autocommit"] = False
    try:
        # 前置校验：确保核心数据库配置（账号、密码、库名）完整
        if not all(
            [config.get("user"), config.get("password"), config.get("database")]
        ):
            return "错误：数据库配置缺失（请检查账号、密码、数据库名）。"
        # 建立数据库连接（with 语句自动管理连接生命周期，无需手动关闭）
        with connect(**config) as conn:
            # 创建游标对象（执行 SQL、获取结果/影响行数的核心对象）
            with conn.cursor() as cursor:
                # 执行传入的自定义 SQL 语句
                cursor.execute(query)
                # ========== 区分 DQL/DML 语句处理结果 ==========
                # cursor.description 不为空 → 是查询类语句（DQL：SELECT/SHOW 等）
                if cursor.description is not None:
                    # 提取查询结果的列名（用于构造返回表头）
                    columns = [desc[0] for desc in cursor.description]
                    # 提取查询结果的所有行数据（元组列表格式）
                    rows = cursor.fetchall()

                    # 处理查询结果为空的情况（有列名但无数据）
                    if not rows:
                        return (
                            f"查询执行成功，无数据返回。涉及列名：{', '.join(columns)}"
                        )

                    # 构造 CSV 格式的返回结果（表头+数据行）
                    result_lines = []
                    result_lines.append(",".join(columns))  # 追加表头
                    for row in rows:
                        # 每行数据转字符串后用逗号分隔，避免类型拼接报错
                        result_lines.append(",".join(map(str, row)))

                    # 返回完整的 CSV 格式查询结果
                    return "\n".join(result_lines)

                # cursor.description 为空 → 意外：只读守卫应已拦截此类语句
                else:
                    return (
                        "操作已拦截：仅允许只读查询（SELECT/SHOW/DESCRIBE/EXPLAIN）。"
                    )

    # 捕获所有数据库操作异常，返回中文错误提示
    except Error as e:
        return f"执行 SQL 失败：{str(e)}"
