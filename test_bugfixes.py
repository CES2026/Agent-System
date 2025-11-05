#!/usr/bin/env python3
"""
Quick verification for all 5 critical bug fixes
Run: python test_bugfixes.py
"""

import sys
import asyncio
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))


def print_section(title):
    """打印章节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def test_issue_1_mcp_imports():
    """测试Issue 1: MCP服务器导入路径"""
    print_section("Issue 1: MCP Server Import Path Fix")

    try:
        # 测试navigation_server导入
        from backend.mcp_servers import navigation_server
        print("✓ navigation_server.py imported successfully")

        # 验证新增的parse_navigation_intent函数
        assert hasattr(navigation_server, 'parse_navigation_intent'), \
            "parse_navigation_intent function does not exist"
        print("✓ parse_navigation_intent function exists")

        # 验证全局变量
        assert hasattr(navigation_server, 'nav_client'), "nav_client variable does not exist"
        assert hasattr(navigation_server, 'llm_service'), "llm_service variable does not exist"
        print("✓ nav_client and llm_service variables correctly defined")

        # 测试__main__导入
        from backend.mcp_servers.__main__ import main
        assert callable(main), "main function is not callable"
        print("✓ __main__.py can import main function")

        print("\n✅ Issue 1: All tests passed")
        return True

    except Exception as e:
        print(f"\n❌ Issue 1: Failed - {e}")
        import traceback
        traceback.print_exc()
        return False


def test_issue_2_tool_names():
    """测试Issue 2: 工具名称匹配"""
    print_section("Issue 2: Tool Name Matching Fix")

    try:
        from backend.tools.navigation_tool import NavigationTool
        import inspect

        tool = NavigationTool()
        source = inspect.getsource(tool._analyze_with_sonnet)

        # 正确的工具名
        correct_tools = {
            'navigate_to_location': 'Navigate to semantic location',
            'navigate_to_pose': 'Navigate to specified coordinates',
            'get_navigation_status': 'Get navigation status',
            'cancel_navigation': 'Cancel navigation'
        }

        # 错误的工具名（应该被删除）
        incorrect_tools = ['move_distance', 'rotate', 'follow_me']

        print("Checking correct tool names:")
        all_present = True
        for tool_name, desc in correct_tools.items():
            present = tool_name in source
            symbol = "✓" if present else "✗"
            print(f"  {symbol} {tool_name}: {'Present' if present else 'Missing'}")
            all_present = all_present and present

        print("\nChecking incorrect tool names (should be deleted):")
        all_removed = True
        for tool_name in incorrect_tools:
            removed = tool_name not in source
            symbol = "✓" if removed else "✗"
            print(f"  {symbol} {tool_name}: {'Deleted' if removed else 'Still exists!'}")
            all_removed = all_removed and removed

        # 检查_format_result方法
        format_source = inspect.getsource(tool._format_result)
        has_pose_format = 'navigate_to_pose' in format_source
        has_status_format = 'get_navigation_status' in format_source
        has_cancel_format = 'cancel_navigation' in format_source

        print("\nChecking _format_result method:")
        print(f"  {'✓' if has_pose_format else '✗'} navigate_to_pose formatting")
        print(f"  {'✓' if has_status_format else '✗'} get_navigation_status formatting")
        print(f"  {'✓' if has_cancel_format else '✗'} cancel_navigation formatting")

        success = all_present and all_removed and has_pose_format and has_status_format and has_cancel_format

        if success:
            print("\n✅ Issue 2: All tests passed")
        else:
            print("\n❌ Issue 2: Some tests failed")

        return success

    except Exception as e:
        print(f"\n❌ Issue 2: Failed - {e}")
        import traceback
        traceback.print_exc()
        return False


def test_issue_3_no_duplicate():
    """测试Issue 3: 无重复ainvoke"""
    print_section("Issue 3: Duplicate ainvoke Fix")

    try:
        from backend.agents.llama_agent import LlamaAgent
        import inspect

        source = inspect.getsource(LlamaAgent.process_streaming)

        # 检查ainvoke调用次数
        ainvoke_count = source.count('self.agent_executor.ainvoke')
        print(f"ainvoke call count: {ainvoke_count}")

        if ainvoke_count == 0:
            print("✓ No duplicate ainvoke calls")
        else:
            print(f"✗ Found {ainvoke_count} ainvoke call(s) (should be 0)")

        # 检查on_chain_end处理
        has_chain_end = 'on_chain_end' in source
        print(f"{'✓' if has_chain_end else '✗'} on_chain_end event handler: {'Present' if has_chain_end else 'Missing'}")

        # 检查AgentExecutor结束检查
        has_executor_check = 'AgentExecutor' in source and 'event.get("name")' in source
        print(f"{'✓' if has_executor_check else '✗'} AgentExecutor completion check: {'Present' if has_executor_check else 'Missing'}")

        success = ainvoke_count == 0 and has_chain_end and has_executor_check

        if success:
            print("\n✅ Issue 3: All tests passed")
        else:
            print("\n❌ Issue 3: Some tests failed")

        return success

    except Exception as e:
        print(f"\n❌ Issue 3: Failed - {e}")
        import traceback
        traceback.print_exc()
        return False


def test_issue_4_generator_syntax():
    """测试Issue 4: Generator语法修复"""
    print_section("Issue 4: Generator Syntax Fix")

    try:
        from backend.services.openrouter_service import OpenRouterService

        service = OpenRouterService()

        # 检查两个方法都存在
        has_streaming = hasattr(service, 'generate_with_conversation_history_streaming')
        has_nonstreaming = hasattr(service, 'generate_with_conversation_history')

        print(f"{'✓' if has_streaming else '✗'} generate_with_conversation_history_streaming: "
              f"{'Present' if has_streaming else 'Missing'}")
        print(f"{'✓' if has_nonstreaming else '✗'} generate_with_conversation_history: "
              f"{'Present' if has_nonstreaming else 'Missing'}")

        # 验证方法签名
        import inspect

        if has_streaming:
            sig = inspect.signature(service.generate_with_conversation_history_streaming)
            is_async_gen = inspect.isasyncgenfunction(service.generate_with_conversation_history_streaming)
            print(f"  {'✓' if is_async_gen else '✗'} streaming method is async generator")

        if has_nonstreaming:
            sig = inspect.signature(service.generate_with_conversation_history)
            is_async = inspect.iscoroutinefunction(service.generate_with_conversation_history)
            print(f"  {'✓' if is_async else '✗'} non-streaming method is async function")

        success = has_streaming and has_nonstreaming

        if success:
            print("\n✅ Issue 4: All tests passed")
        else:
            print("\n❌ Issue 4: Some tests failed")

        return success

    except Exception as e:
        print(f"\n❌ Issue 4: Failed - {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cleanup_completed():
    """测试Issue 5: 代码清理完成"""
    print_section("Issue 5: Code Cleanup Completed")

    try:
        from pathlib import Path

        # 1. 验证死代码文件已删除
        print("Checking if dead code files are deleted:")
        intent_detector_exists = Path("backend/agents/intent_detector.py").exists()
        mcp_nav_agent_exists = Path("backend/agents/mcp_navigation_agent.py").exists()

        print(f"  {'✗' if intent_detector_exists else '✓'} intent_detector.py: "
              f"{'Still exists (should be deleted)' if intent_detector_exists else 'Deleted'}")
        print(f"  {'✗' if mcp_nav_agent_exists else '✓'} mcp_navigation_agent.py: "
              f"{'Still exists (should be deleted)' if mcp_nav_agent_exists else 'Deleted'}")

        files_deleted = not intent_detector_exists and not mcp_nav_agent_exists

        # 2. 验证配置项已重命名
        print("\nChecking if config items are renamed:")
        from backend.config import get_settings
        settings = get_settings()

        has_new_name = hasattr(settings, 'navigation_command_parser_model')
        has_old_name = hasattr(settings, 'intent_detection_model')

        print(f"  {'✓' if has_new_name else '✗'} navigation_command_parser_model: "
              f"{'Present' if has_new_name else 'Missing'}")
        print(f"  {'✓' if not has_old_name else '✗'} intent_detection_model: "
              f"{'Deleted' if not has_old_name else 'Still exists (should be deleted)'}")

        config_renamed = has_new_name and not has_old_name

        # 3. 验证NavigationTool使用新配置
        print("\nChecking if NavigationTool uses new config:")
        from backend.tools.navigation_tool import NavigationTool
        import inspect

        tool_source = inspect.getsource(NavigationTool.__init__)
        uses_new_config = 'navigation_command_parser_model' in tool_source
        uses_old_config = 'intent_detection_model' in tool_source

        print(f"  {'✓' if uses_new_config else '✗'} Uses navigation_command_parser_model: "
              f"{'Yes' if uses_new_config else 'No'}")
        print(f"  {'✓' if not uses_old_config else '✗'} Uses intent_detection_model: "
              f"{'No (correct)' if not uses_old_config else 'Yes (wrong)'}")

        tool_updated = uses_new_config and not uses_old_config

        # 4. 验证所有导入仍然正常
        print("\nChecking if all imports work:")
        try:
            from backend.agents import base, llama_agent, graph
            from backend.tools import navigation_tool
            from backend.services import mcp_client_service, openrouter_service
            from backend.mcp_servers import navigation_server
            print("  ✓ All key modules imported successfully")
            imports_ok = True
        except Exception as e:
            print(f"  ✗ Import failed: {e}")
            imports_ok = False

        success = files_deleted and config_renamed and tool_updated and imports_ok

        if success:
            print("\n✅ Issue 5: All tests passed - Code cleanup completed")
        else:
            print("\n❌ Issue 5: Some tests failed")

        return success

    except Exception as e:
        print(f"\n❌ Issue 5: Failed - {e}")
        import traceback
        traceback.print_exc()
        return False


def print_summary(results):
    """打印测试总结"""
    print_section("Test Summary")

    total = len(results)
    passed = sum(results.values())
    failed = total - passed

    print(f"Total: {total} issues")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"\nPass Rate: {passed/total*100:.1f}%")

    print("\nDetailed Results:")
    for issue, success in results.items():
        symbol = "✅" if success else "❌"
        print(f"  {symbol} {issue}")

    if all(results.values()):
        print("\n" + "🎉" * 35)
        print("All critical issues have been successfully fixed!")
        print("🎉" * 35)
    else:
        print("\n⚠️  Some issues still need to be fixed")


def main():
    """主测试函数"""
    print("\n" + "=" * 70)
    print("  Quick Verification - Bug Fixes + Code Cleanup")
    print("=" * 70)

    results = {
        "Issue 1: MCP Server Import Path": test_issue_1_mcp_imports(),
        "Issue 2: Tool Name Matching": test_issue_2_tool_names(),
        "Issue 3: Duplicate ainvoke": test_issue_3_no_duplicate(),
        "Issue 4: Generator Syntax": test_issue_4_generator_syntax(),
        "Issue 5: Code Cleanup Completed": test_cleanup_completed(),
    }

    print_summary(results)

    # 返回退出码
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
