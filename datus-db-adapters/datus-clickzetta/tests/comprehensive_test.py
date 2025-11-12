#!/usr/bin/env python3
"""ClickZetta 连接器完整功能测试脚本"""

import os
import sys

def main():
    print('=== ClickZetta 连接器完整功能测试 ===')
    print()

    # 测试环境变量加载
    print('1. 📋 环境变量验证')
    required_vars = [
        'CLICKZETTA_SERVICE', 'CLICKZETTA_USERNAME', 'CLICKZETTA_PASSWORD',
        'CLICKZETTA_INSTANCE', 'CLICKZETTA_WORKSPACE', 'CLICKZETTA_SCHEMA', 'CLICKZETTA_VCLUSTER'
    ]

    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        status = '✅' if value else '❌'
        display_value = '[HIDDEN]' if 'PASSWORD' in var else value
        print(f'   {status} {var}: {display_value}')
        if not value:
            missing_vars.append(var)

    if missing_vars:
        print(f'   ❌ 缺少必需的环境变量: {missing_vars}')
        return False

    print()

    # 测试基本连接
    print('2. 🔌 基本连接测试')
    try:
        import clickzetta
        connection = clickzetta.connect(
            service=os.getenv('CLICKZETTA_SERVICE'),
            username=os.getenv('CLICKZETTA_USERNAME'),
            password=os.getenv('CLICKZETTA_PASSWORD'),
            instance=os.getenv('CLICKZETTA_INSTANCE'),
            workspace=os.getenv('CLICKZETTA_WORKSPACE'),
            schema=os.getenv('CLICKZETTA_SCHEMA'),
            vcluster=os.getenv('CLICKZETTA_VCLUSTER')
        )
        print('   ✅ ClickZetta SDK 连接成功')
    except Exception as e:
        print(f'   ❌ ClickZetta SDK 连接失败: {e}')
        return False

    # 测试 SQL 查询
    print()
    print('3. 📊 SQL 查询测试')
    try:
        cursor = connection.cursor()

        # 测试简单查询
        cursor.execute('SELECT 1 as test_number, "Hello ClickZetta" as message')
        results = cursor.fetchall()
        print(f'   ✅ 基本查询成功: {results}')

        # 测试当前时间查询
        cursor.execute('SELECT current_timestamp();')
        time_results = cursor.fetchall()
        print(f'   ✅ 时间查询成功: {time_results[0] if time_results else "无结果"}')

        cursor.close()
    except Exception as e:
        print(f'   ❌ SQL 查询失败: {e}')

    # 测试元数据获取
    print()
    print('4. 🗂️ 元数据查询测试')
    try:
        cursor = connection.cursor()
        workspace = os.getenv('CLICKZETTA_WORKSPACE')
        schema = os.getenv('CLICKZETTA_SCHEMA')

        # 获取表列表
        cursor.execute(f'SHOW TABLES IN `{workspace}`.`{schema}`')
        tables = cursor.fetchall()
        table_count = len(tables) if tables else 0
        print(f'   ✅ 表列表获取成功: 发现 {table_count} 个表')

        if table_count > 0:
            print(f'   📝 示例表名: {tables[0][0] if tables else "无"}')

        cursor.close()
    except Exception as e:
        print(f'   ❌ 元数据查询失败: {e}')

    # 删除use_workspace相关测试，因为本来就不支持这个功能

    print()
    print('5. 🧹 资源清理')
    try:
        connection.close()
        print('   ✅ 连接已关闭')
    except Exception as e:
        print(f'   ❌ 连接关闭失败: {e}')

    print()
    print('🎉 真实连接测试完成！')
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)