"""
Browser Automation Tools - References OpenClaw's Playwright integration
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def register_tools(registry):
    """Register browser automation tools"""

    @registry.register_tool(
        name="browser_navigate",
        description="Navigate to a URL in browser",
        toolset="browser",
        parameters={
            "url": {"type": "string", "description": "URL to navigate to"},
        },
    )
    async def browser_navigate(url: str) -> str:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=30000)
                title = await page.title()
                await browser.close()
                return f"Navigated to {url}, title: {title}"
        except ImportError:
            return "Error: playwright not installed. Run: pip install playwright && playwright install chromium"
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="browser_screenshot",
        description="Take a screenshot of a webpage",
        toolset="browser",
        parameters={
            "url": {"type": "string", "description": "URL to screenshot"},
            "full_page": {"type": "boolean", "description": "Screenshot full page"},
        },
    )
    async def browser_screenshot(url: str, full_page: bool = False) -> str:
        try:
            from playwright.async_api import async_playwright
            from pathlib import Path
            from datetime import datetime

            Path("./data/screenshots").mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"./data/screenshots/browser_{timestamp}.png"

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=30000)
                await page.screenshot(path=filepath, full_page=full_page)
                await browser.close()
                return f"Screenshot saved: {filepath}"
        except ImportError:
            return "Error: playwright not installed"
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="browser_click",
        description="Click an element on the page",
        toolset="browser",
        parameters={
            "selector": {"type": "string", "description": "CSS selector"},
        },
    )
    async def browser_click(selector: str) -> str:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.click(selector, timeout=5000)
                await browser.close()
                return f"Clicked element: {selector}"
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="browser_fill",
        description="Fill a form field",
        toolset="browser",
        parameters={
            "selector": {"type": "string", "description": "CSS selector"},
            "value": {"type": "string", "description": "Value to fill"},
        },
    )
    async def browser_fill(selector: str, value: str) -> str:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.fill(selector, value)
                await browser.close()
                return f"Filled {selector} with: {value[:50]}..."
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="browser_get_text",
        description="Get text content from page",
        toolset="browser",
        parameters={
            "selector": {"type": "string", "description": "CSS selector"},
            "max_length": {"type": "number", "description": "Max text length"},
        },
    )
    async def browser_get_text(selector: str, max_length: int = 4000) -> str:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.wait_for_selector(selector, timeout=5000)
                text = await page.text_content(selector)
                await browser.close()
                if text and len(text) > max_length:
                    text = text[:max_length] + "..."
                return text or "No text found"
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="browser_evaluate",
        description="Execute JavaScript on page",
        toolset="browser",
        parameters={
            "script": {"type": "string", "description": "JavaScript code"},
        },
    )
    async def browser_evaluate(script: str) -> str:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                result = await page.evaluate(script)
                await browser.close()
                return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"

    logger.debug("Browser tools registered")
