"""
完整的 Playwright 浏览器自动化工具 - 参考 OpenClaw
"""

from typing import Optional, Dict, Any
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def register_tools(registry):
    """注册所有浏览器工具"""

    @registry.register_tool(
        name="browser_navigate",
        description="导航到 URL",
        toolset="browser",
        parameters={
            "url": {"type": "string", "description": "要导航的 URL"}
        }
    )
    async def navigate(url: str) -> str:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                response = await page.goto(url, timeout=30000)
                title = await page.title()
                current_url = page.url

                await browser.close()

                result = f"✓ 导航成功\n- URL: {current_url}\n- 标题: {title}\n- 状态: {response.status if response else 'OK'}"
                return result

        except ImportError:
            return "⚠️ Playwright 未安装。请运行: pip install playwright && playwright install chromium"
        except Exception as e:
            return f"✗ 导航失败: {e}"

    @registry.register_tool(
        name="browser_screenshot",
        description="截图",
        toolset="browser",
        parameters={
            "url": {"type": "string", "description": "要截图的 URL"},
            "full_page": {"type": "boolean", "description": "是否全屏截图"}
        }
    )
    async def take_screenshot(url: str, full_page: bool = False) -> str:
        try:
            from playwright.async_api import async_playwright

            Path("./data/screenshots").mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"./data/screenshots/screen_{timestamp}.png"

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=30000)
                await page.screenshot(path=filename, full_page=full_page)
                title = await page.title()
                await browser.close()

            result = f"✓ 截图成功\n- 标题: {title}\n- 文件: {filename}"
            return result

        except ImportError:
            return "⚠️ Playwright 未安装"
        except Exception as e:
            return f"✗ 截图失败: {e}"

    @registry.register_tool(
        name="browser_click",
        description="点击元素",
        toolset="browser",
        parameters={
            "url": {"type": "string", "description": "URL"},
            "selector": {"type": "string", "description": "CSS 选择器"}
        }
    )
    async def click(url: str, selector: str) -> str:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=30000)
                await page.click(selector, timeout=10000)
                title = await page.title()
                current_url = page.url
                await browser.close()

            result = f"✓ 点击成功\n- 选择器: {selector}\n- 新 URL: {current_url}\n- 标题: {title}"
            return result

        except Exception as e:
            return f"✗ 点击失败: {e}"

    @registry.register_tool(
        name="browser_type",
        description="填充输入框",
        toolset="browser",
        parameters={
            "url": {"type": "string", "description": "URL"},
            "selector": {"type": "string", "description": "CSS 选择器"},
            "text": {"type": "string", "description": "填充的文本"}
        }
    )
    async def type_text(url: str, selector: str, text: str) -> str:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=30000)
                await page.fill(selector, text)
                title = await page.title()
                await browser.close()

            return f"✓ 填充成功\n- 选择器: {selector}\n- 文本: {text[:50]}..."

        except Exception as e:
            return f"✗ 填充失败: {e}"

    @registry.register_tool(
        name="browser_get_text",
        description="获取元素文本",
        toolset="browser",
        parameters={
            "url": {"type": "string", "description": "URL"},
            "selector": {"type": "string", "description": "CSS 选择器"},
            "max_length": {"type": "number", "description": "最大长度"}
        }
    )
    async def get_text(url: str, selector: str, max_length: int = 4000) -> str:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=30000)
                await page.wait_for_selector(selector, timeout=10000)
                text = await page.text_content(selector)
                await browser.close()

            if text is None:
                text = ""

            content = text[:max_length] + ("..." if len(text) > max_length else "")
            result = f"✓ 获取文本成功\n- 长度: {len(text)}\n- 内容:\n{content}"
            return result

        except Exception as e:
            return f"✗ 获取文本失败: {e}"

    @registry.register_tool(
        name="browser_get_html",
        description="获取 HTML",
        toolset="browser",
        parameters={
            "url": {"type": "string", "description": "URL"},
            "selector": {"type": "string", "description": "CSS 选择器"}
        }
    )
    async def get_html(url: str, selector: Optional[str] = None) -> str:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=30000)

                if selector:
                    await page.wait_for_selector(selector, timeout=10000)
                    content = await page.inner_html(selector)
                else:
                    content = await page.content()

                await browser.close()

            result = f"✓ 获取 HTML 成功\n- 长度: {len(content)}\n- 内容:\n{content[:2000]}"
            return result

        except Exception as e:
            return f"✗ 获取 HTML 失败: {e}"

    @registry.register_tool(
        name="browser_evaluate",
        description="执行 JavaScript",
        toolset="browser",
        parameters={
            "url": {"type": "string", "description": "URL"},
            "script": {"type": "string", "description": "JS 脚本"}
        }
    )
    async def evaluate(url: str, script: str) -> str:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=30000)
                result = await page.evaluate(script)
                await browser.close()

            return f"✓ JS 执行成功\n- 结果: {result}"

        except Exception as e:
            return f"✗ JS 执行失败: {e}"

    logger.debug("浏览器工具注册完成")
