"""
测试工具函数
"""

import asyncio
import time
import re
from typing import Any, Callable, Optional, Dict
from datetime import datetime
import json

from test_config import TestConfig


async def run_with_timeout_and_retry(
    func: Callable,
    timeout: float,
    max_retries: int = None,
    retry_delay: float = None
) -> Any:
    """
    带超时和重试的异步函数执行

    Args:
        func: 要执行的异步函数
        timeout: 超时时间(秒)
        max_retries: 最大重试次数（None则使用config默认值）
        retry_delay: 重试延迟(秒)（None则使用config默认值）

    Returns:
        函数执行结果

    Raises:
        asyncio.TimeoutError: 所有重试都超时
        Exception: 函数执行异常
    """
    if max_retries is None:
        max_retries = TestConfig.MAX_RETRIES
    if retry_delay is None:
        retry_delay = TestConfig.RETRY_DELAY

    for attempt in range(max_retries):
        try:
            result = await asyncio.wait_for(func(), timeout=timeout)
            return result

        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                print(f"  ⏱️  Timeout (attempt {attempt + 1}/{max_retries}), retrying...")
                await asyncio.sleep(retry_delay)
            else:
                print(f"  ❌ Timeout after {max_retries} attempts ({timeout}s each)")
                raise

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"  ⚠️  Error: {e}, retrying...")
                await asyncio.sleep(retry_delay)
            else:
                raise


def format_duration(seconds: float) -> str:
    """格式化时长"""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m{secs:.0f}s"


def print_test_header(section_num: int, section_name: str):
    """打印测试节标题"""
    print("\n" + "=" * 70)
    print(f"Section {section_num}: {section_name}")
    print("=" * 70 + "\n")


def print_test_case(case_num: int, user_input: str):
    """打印测试用例"""
    print(f"\nTest Case {case_num}: \"{user_input}\"")


def print_result(success: bool, message: str, indent: int = 2):
    """打印测试结果"""
    symbol = "✅" if success else "❌"
    spaces = " " * indent
    print(f"{spaces}{symbol} {message}")


def print_section_summary(results: Dict[str, Any]):
    """打印节测试摘要"""
    total = results.get("total", 0)
    passed = results.get("passed", 0)
    failed = results.get("failed", 0)
    duration = results.get("duration", 0)
    tool_calls = results.get("tool_calls", 0)

    print("\n" + "-" * 70)
    print("Section Summary:")
    print(f"  Total: {total} tests")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  ⏱️  Total Time: {format_duration(duration)}")
    if tool_calls > 0:
        print(f"  🔧 Tool Calls: {tool_calls}")
    print("-" * 70)


def verify_response_pattern(response: str, pattern: str) -> bool:
    """
    验证响应是否匹配预期模式

    Args:
        response: 响应文本
        pattern: 正则表达式模式

    Returns:
        是否匹配
    """
    return bool(re.search(pattern, response, re.IGNORECASE | re.DOTALL))


def verify_ambiguous_response(
    response: str,
    tool_calls: list,
    acceptable_outcomes: list
) -> str:
    """
    验证模糊命令的响应

    Args:
        response: 响应文本
        tool_calls: 工具调用列表
        acceptable_outcomes: 可接受的结果类型列表

    Returns:
        识别出的结果类型
    """
    response_lower = response.lower()

    # 检查是否请求澄清
    clarification_keywords = [
        "how much", "how many", "which", "where", "what",
        "clarify", "specify", "more details", "could you",
        "can you tell me", "need to know"
    ]
    if any(keyword in response_lower for keyword in clarification_keywords):
        return "clarification_request"

    # 检查是否礼貌拒绝
    decline_keywords = [
        "cannot", "can't", "unable", "unclear",
        "don't understand", "not sure", "need more",
        "ambiguous", "vague"
    ]
    if any(keyword in response_lower for keyword in decline_keywords):
        return "polite_decline"

    # 检查是否列出选项
    if any(word in response_lower for word in ["available", "options", "locations"]):
        return "list_available_locations"

    # 检查是否尝试合理解释
    if len(tool_calls) > 0:
        return "reasonable_interpretation"

    return "unknown"


def calculate_coordinate_error(
    actual: Dict[str, float],
    expected: Dict[str, float]
) -> Dict[str, float]:
    """
    计算坐标误差

    Args:
        actual: 实际坐标 {"x": ..., "y": ..., "yaw": ...}
        expected: 预期坐标

    Returns:
        误差字典 {"x": ..., "y": ..., "yaw": ...}
    """
    errors = {}

    for key in ["x", "y", "yaw"]:
        if key in expected:
            actual_val = actual.get(key, 0)
            expected_val = expected[key]
            errors[key] = abs(actual_val - expected_val)

    return errors


def generate_test_report(
    test_run_id: str,
    sections: list,
    total_duration: float
) -> Dict[str, Any]:
    """
    生成测试报告

    Args:
        test_run_id: 测试运行ID
        sections: 各节测试结果
        total_duration: 总时长

    Returns:
        报告字典
    """
    total_tests = sum(s.get("total", 0) for s in sections)
    passed_tests = sum(s.get("passed", 0) for s in sections)
    failed_tests = sum(s.get("failed", 0) for s in sections)
    passed_sections = sum(1 for s in sections if s.get("failed", 0) == 0)

    return {
        "test_run_id": test_run_id,
        "timestamp": datetime.now().isoformat(),
        "config": TestConfig.get_summary(),
        "sections": sections,
        "overall_summary": {
            "total_sections": len(sections),
            "passed_sections": passed_sections,
            "failed_sections": len(sections) - passed_sections,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "pass_rate": f"{passed_tests/total_tests*100:.1f}%" if total_tests > 0 else "0%",
            "total_duration": total_duration,
            "total_duration_formatted": format_duration(total_duration)
        }
    }


def save_json_report(report: Dict[str, Any], filename: str):
    """保存JSON格式报告"""
    filepath = TestConfig.REPORT_DIR / f"{filename}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n📄 JSON report saved: {filepath}")


def save_markdown_report(report: Dict[str, Any], filename: str):
    """保存Markdown格式报告"""
    filepath = TestConfig.REPORT_DIR / f"{filename}.md"

    with open(filepath, "w", encoding="utf-8") as f:
        # 标题
        f.write("# Agent System Test Report\n\n")
        f.write(f"**Test Run ID**: {report['test_run_id']}\n\n")
        f.write(f"**Timestamp**: {report['timestamp']}\n\n")

        # 总体摘要
        summary = report["overall_summary"]
        f.write("## Overall Summary\n\n")
        f.write(f"- **Total Sections**: {summary['total_sections']}\n")
        f.write(f"- **Passed Sections**: {summary['passed_sections']}\n")
        f.write(f"- **Total Tests**: {summary['total_tests']}\n")
        f.write(f"- **Passed Tests**: {summary['passed_tests']} ({summary['pass_rate']})\n")
        f.write(f"- **Failed Tests**: {summary['failed_tests']}\n")
        f.write(f"- **Total Duration**: {summary['total_duration_formatted']}\n\n")

        # 各节详情
        f.write("## Section Details\n\n")
        for section in report["sections"]:
            status = "✅ PASSED" if section.get("failed", 0) == 0 else "❌ FAILED"
            f.write(f"### Section {section['id']}: {section['name']} {status}\n\n")
            f.write(f"- Tests: {section['total']}\n")
            f.write(f"- Passed: {section['passed']}\n")
            f.write(f"- Failed: {section['failed']}\n")
            f.write(f"- Duration: {format_duration(section['duration'])}\n")

            if "tool_calls" in section:
                f.write(f"- Tool Calls: {section['tool_calls']}\n")

            f.write("\n")

    print(f"📄 Markdown report saved: {filepath}")


def print_final_summary(report: Dict[str, Any]):
    """打印最终摘要"""
    summary = report["overall_summary"]

    print("\n" + "=" * 70)
    print(" Final Test Summary")
    print("=" * 70 + "\n")

    print(f"Total Sections: {summary['total_sections']}")
    print(f"✅ Passed Sections: {summary['passed_sections']}")
    print(f"❌ Failed Sections: {summary['failed_sections']}")
    print()
    print(f"Total Tests: {summary['total_tests']}")
    print(f"✅ Passed: {summary['passed_tests']} ({summary['pass_rate']})")
    print(f"❌ Failed: {summary['failed_tests']}")
    print()
    print(f"⏱️  Total Duration: {summary['total_duration_formatted']}")

    if summary["failed_tests"] == 0:
        print("\n" + "🎉" * 35)
        print("All tests passed successfully!")
        print("🎉" * 35)
    else:
        print("\n⚠️  Some tests failed. Check the report for details.")

    print("\n" + "=" * 70 + "\n")
