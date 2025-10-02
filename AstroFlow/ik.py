import asyncio
from playwright.async_api import async_playwright, expect


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Set headless=True if you don’t want UI
        page = await browser.new_page()

        try:
            await page.goto('https://practicetestautomation.com/practice-test-login/')

            await page.fill('input[name="username"]', 'student')
            await page.fill('input[name="password"]', 'Password123')

            await page.click('button#submit')

            # Verify new page URL
            current_url = page.url
            assert 'practicetestautomation.com/logged-in-successfully/' in current_url, f"Expected URL to contain 'practicetestautomation.com/logged-in-successfully/', but got {current_url}"

            # Verify new page contains expected text
            content = await page.content()
            assert 'Congratulations' in content or 'successfully logged in' in content, "Expected text not found on the page"

            # Verify that Log out button is visible
            logout_button = page.locator("a:has-text('Log out')")
            await expect(logout_button).to_be_visible()

            print("✅ Log out button is displayed!")

            await browser.close()

        except Exception as e:
            print(f"An error occurred: {e}")
            await page.screenshot(path="screenshot.png")


if __name__ == "__main__":
    asyncio.run(run())
